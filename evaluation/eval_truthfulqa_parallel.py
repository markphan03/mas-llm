import os
import json
import random
import numpy as np
from io import StringIO
from typing import List, Dict, Any, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from datasets import load_dataset
from sklearn.metrics import accuracy_score
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer
from tqdm import tqdm

# Import your project modules (must be available in worker processes)
from langchain_ollama import ChatOllama
from graphstate import GraphState
from workflow import create_graph
from agents.agent import Agent
from agents.vote import Vote

# ---------------------------
# Config
# ---------------------------
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# Number of GPUs/workers to use. Set to 2, 3, or 4 depending on your machine.
NUM_GPUS = 2

# Agent model specs — choose the models you want
AGENT_SPECS = [
    {"model": "llama3.1", "rank": 1},
    {"model": "gemma3:12b", "rank": 2},
    {"model": "deepseek-r1", "rank": 3},
]

# Dataset and output
DATASET_NAME = "domenicrosati/TruthfulQA"
OUTPUT_MD = "/docs/truthfulqa_results.md"

# ---------------------------
# Utility: generate_final_answer (same logic as your original function)
# ---------------------------
def generate_final_answer(voting_state: Dict[str, Any], agents: List[Agent]):
    """
    Pick the winning agent to produce the final answer, given a voting_state and list of Agent objects.
    This function assumes agent ranks are unique and that voting_state contains:
      - question
      - context
      - responses (mapping agent_<rank> -> metadata)
      - agent_scores (mapping agent_<rank> -> score)
    """
    question = voting_state.get("question", "")
    context = voting_state.get("context", "")
    responses = voting_state.get("responses", {})
    vote_counts = voting_state.get("agent_scores", {})

    # Determine winning agent(s)
    max_votes = max(vote_counts.values())
    winners = [agent for agent, score in vote_counts.items() if score == max_votes]
    chosen_agent_name = random.choice(winners)

    # Map to Agent object
    agent_lookup = {f"agent_{a.rank}": a for a in agents}
    chosen_agent = agent_lookup[chosen_agent_name]
    chosen_agent_record = responses[chosen_agent_name]

    # Prepare prompt with other responses
    other_responses = chosen_agent_record.get("other_responses", {})
    formatted_responses = "\n\n".join(f"{agent_name}: {text}" for agent_name, text in other_responses.items())

    final_prompt = f"""
You are the final evaluator.
Question: {question}

Context:
{context}

Other model responses:
{formatted_responses}

Produce the best single final answer.
""".strip()

    # Invoke the chosen agent's base LLM
    llm = chosen_agent.base_model
    result = llm.invoke(final_prompt)
    result_text = result.content if hasattr(result, "content") else str(result)
    return result_text

# ---------------------------
# Worker function
# ---------------------------
def worker_process(
    gpu_index: int,
    indices: List[int],
    dataset_shard: List[Dict[str, Any]],
    agent_specs: List[Dict[str, Any]],
    seed: int = SEED,
) -> Dict[str, Any]:
    """
    Runs on a single process bound to gpu_index. Processes dataset_shard indices and returns results.
    """
    # MAKE THIS PROCESS USE THE CORRESPONDING GPU
    # Setting CUDA_VISIBLE_DEVICES makes the first visible GPU in this process be the assigned GPU.
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_index)
    # Optionally, if your SDK reads a different env var, set it here too.
    # e.g., os.environ["DEVICE"] = f"cuda:{0}"

    # Re-seed per worker for reproducibility
    random.seed(seed + gpu_index)
    np.random.seed(seed + gpu_index)

    # Determine device string for frameworks that use it (Torch will see cuda:0 because of CUDA_VISIBLE_DEVICES)
    device = "cuda:0" if torch_available() else "cpu"

    # Instantiate agents locally (models will load onto device)
    agents = []
    for spec in agent_specs:
        model_name = spec["model"]
        rank = spec["rank"]
        # If your ChatOllama supports 'device' kwarg, pass it. If not, rely on CUDA_VISIBLE_DEVICES.
        llm = ChatOllama(model=model_name, device=device) if chatollama_accepts_device() else ChatOllama(model=model_name)
        agents.append(Agent(llm, rank=rank))

    vote_manager = Vote(agents=agents, method="approval")

    # create_graph inside worker
    graph = create_graph(agents, vote_manager)

    # ROUGE scorer
    rouge = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    smoothie = SmoothingFunction().method2

    # Accumulators
    results = []
    for local_idx, sample_idx in enumerate(indices):
        sample = dataset_shard[local_idx]  # dataset_shard is already sliced for this worker
        question = sample.get("Question", "").strip()
        gold_answer = sample.get("Best Answer", "").strip()

        state: GraphState = {
            "question": question,
            "context": "",
            "winners": [f"agent_{a.rank}" for a in agents],
        }

        # Run the multi-agent graph pipeline (synchronous per sample)
        voting_state = graph.invoke(state)
        final_answer = generate_final_answer(voting_state, agents)

        # Compute metrics
        exact = 1 if final_answer.strip().lower() == gold_answer.strip().lower() else 0
        bleu = sentence_bleu([gold_answer.split()], final_answer.split(), smoothing_function=smoothie)
        rouge_l = rouge.score(gold_answer, final_answer)["rougeL"].fmeasure

        results.append({
            "sample_index": sample_idx,
            "question": question,
            "gold": gold_answer,
            "pred": final_answer,
            "exact": exact,
            "bleu": bleu,
            "rouge": rouge_l,
        })

    return {"gpu_index": gpu_index, "results": results}

# ---------------------------
# Helpers to check APIs availability (best-effort)
# ---------------------------
def chatollama_accepts_device() -> bool:
    # Quick probe: inspect ChatOllama __init__ signature
    try:
        import inspect
        sig = inspect.signature(ChatOllama)
        return "device" in sig.parameters
    except Exception:
        return False

def torch_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False

# ---------------------------
# Main orchestration
# ---------------------------
def main(num_gpus: int = NUM_GPUS):
    # Load dataset once in the main process (we will pass shards)
    ds = load_dataset(DATASET_NAME)
    train = ds["train"]
    total = len(train)
    print(f"Loaded {total} samples from TruthfulQA")

    # Build a list of indices and split evenly by num_gpus (simple contiguous split)
    indices = list(range(total))
    shard_sizes = [(total // num_gpus) + (1 if i < (total % num_gpus) else 0) for i in range(num_gpus)]
    shards = []
    cur = 0
    for size in shard_sizes:
        shard_idx = indices[cur: cur + size]
        # Create a list of sample dicts for this shard to send to worker
        shard_samples = [train[idx] for idx in shard_idx]
        shards.append((shard_idx, shard_samples))
        cur += size

    # Launch worker processes
    all_results = []
    with ProcessPoolExecutor(max_workers=num_gpus) as exe:
        futures = []
        for gpu_idx in range(num_gpus):
            shard_idx, shard_samples = shards[gpu_idx]
            # Pass only the per-shard samples to avoid heavy pickling of full dataset
            fut = exe.submit(worker_process, gpu_idx, shard_idx, shard_samples, AGENT_SPECS, SEED)
            futures.append(fut)

        # Gather results
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Gathering worker results"):
            worker_res = fut.result()
            all_results.extend(worker_res["results"])

    # Sort results by sample_index (original order)
    all_results = sorted(all_results, key=lambda x: x["sample_index"])

    # Aggregate metrics
    exact_matches = [r["exact"] for r in all_results]
    bleu_scores = [r["bleu"] for r in all_results]
    rouge_scores = [r["rouge"] for r in all_results]

    accuracy = sum(exact_matches) / len(exact_matches)
    avg_bleu = sum(bleu_scores) / len(bleu_scores)
    avg_rouge = sum(rouge_scores) / len(rouge_scores)

    # Write Markdown report
    md = StringIO()
    md.write("# TruthfulQA Multi-Agent Evaluation (multi-GPU)\n\n")
    md.write("## Overall Metrics\n")
    md.write(f"- Exact Match Accuracy: **{accuracy:.4f}**\n")
    md.write(f"- Average BLEU Score: **{avg_bleu:.4f}**\n")
    md.write(f"- Average ROUGE-L Score: **{avg_rouge:.4f}**\n\n")

    md.write("## Per-Sample Results\n")
    for i, r in enumerate(all_results):
        md.write(f"### Sample {i+1}\n")
        md.write(f"**Question:** {r['question']}\n\n")
        md.write(f"**Gold Answer:**\n```\n{r['gold']}\n```\n")
        md.write(f"**Model Final Answer:**\n```\n{r['pred']}\n```\n\n")
        md.write("---\n")

    os.makedirs(os.path.dirname(OUTPUT_MD), exist_ok=True)
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(md.getvalue())

    print("\n=========== TruthfulQA Results ===========")
    print(f"Exact Match Accuracy: {accuracy:.4f}")
    print(f"Avg BLEU Score:       {avg_bleu:.4f}")
    print(f"Avg ROUGE-L Score:    {avg_rouge:.4f}")
    print(f"\nMarkdown report saved to {OUTPUT_MD}")

# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    main()
