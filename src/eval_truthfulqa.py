import json
import random
import numpy as np
from typing import Dict, Any, List
from io import StringIO
from sklearn.metrics import accuracy_score
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer

from langchain_ollama import ChatOllama
from graphstate import GraphState
from workflow import create_graph
from agents.agent import Agent
from agents.vote import Vote


# =======================================
#  RANDOM SEED
# =======================================
SEED = 42
random.seed(SEED)
np.random.seed(SEED)


# =======================================
#  SETUP AGENTS
# =======================================
agents = [
    Agent(ChatOllama(model="llama3.1"), rank=1),
    Agent(ChatOllama(model="gemma3:12b"), rank=2),
    Agent(ChatOllama(model="deepseek-r1"), rank=3),
]

vote_manager = Vote(agents=agents, method="approval")


# ===========================
#  FINAL ANSWER GENERATION
# ===========================
def generate_final_answer(voting_state: Dict[str, Any], agents: list[Agent]):
    """Pick the winning agent to generate final answer from other responses"""
    question = voting_state.get("question", "")
    context = voting_state.get("context", "")
    responses = voting_state.get("responses", {})
    vote_counts = voting_state.get("agent_scores", {})

    # 1. Determine Winning Agent
    max_votes = max(vote_counts.values())
    winners = [agent for agent, score in vote_counts.items() if score == max_votes]
    chosen_agent_name = random.choice(winners)

    # 2. Get the corresponding agent object
    agent_lookup = {f"agent_{a.rank}": a for a in agents}
    chosen_agent = agent_lookup[chosen_agent_name]
    chosen_agent_record = responses[chosen_agent_name]

    # 3. Prepare summarization prompt
    other_responses = chosen_agent_record.get("other_responses", {})
    formatted_responses = "\n\n".join(
        f"{agent_name}: {text}" for agent_name, text in other_responses.items()
    )

    final_prompt = f"""
        You are the final evaluator.
        Question: {question}

        Context:
        {context}

        Other model responses:
        {formatted_responses}

        Produce the best single final answer.
        """.strip()

    # 4. Execute final LLM
    llm = chosen_agent.base_model
    result = llm.invoke(final_prompt)
    result_text = (
        result.content if hasattr(result, "content") else str(result)
    )

    return result_text


# =======================================
#  LOAD TRUTHFULQA DATASET
#  (Adapt to your file location)
# =======================================
from datasets import load_dataset

truthqa_dataset = load_dataset("domenicrosati/TruthfulQA")

train_samples = truthqa_dataset["train"]
print(f"Loaded {len(train_samples)} samples from TruthfulQA")



# =======================================
#  EVALUATION RESULT STORAGE
# =======================================
gold_texts = []
pred_texts = []
exact_matches = []
bleu_scores = []
rouge_scores = []


# ROUGE scorer setup
rouge = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)


# =======================================
#  MAIN EVALUATION LOOP
# =======================================
for i, sample in enumerate(train_samples):
    if i == 100:  # Limit to first 100 samples for quicker testing
        break
    question = sample.get("Question", "").strip()
    gold_answer = sample.get("Best Answer", "").strip()

    # ========== Build Initial State ==========
    state: GraphState = {
        "question": question,
        "context": "",  # TruthfulQA generally requires no external context
        "winners": [f"agent_{a.rank}" for a in agents],
    }

    # ========== Run Multi-Agent Pipeline ==========
    graph = create_graph(agents, vote_manager)
    voting_state = graph.invoke(state)

    final_answer = generate_final_answer(voting_state, agents)

    # ========== Store Predictions ==========
    gold_texts.append(gold_answer)
    pred_texts.append(final_answer)

    # Exact match
    exact_matches.append(1 if final_answer.lower() == gold_answer.lower() else 0)

    # BLEU
    smoothie = SmoothingFunction().method2
    bleu = sentence_bleu(
        [gold_answer.split()],
        final_answer.split(),
        smoothing_function=smoothie,
    )
    bleu_scores.append(bleu)

    # ROUGE-L
    r = rouge.score(gold_answer, final_answer)["rougeL"].fmeasure
    rouge_scores.append(r)

    if (i + 1) % 25 == 0:
        print(f"Processed {i + 1}/{len(train_samples)}")


# =======================================
#  METRIC RESULTS
# =======================================
accuracy = sum(exact_matches) / len(exact_matches)
avg_bleu = sum(bleu_scores) / len(bleu_scores)
avg_rouge = sum(rouge_scores) / len(rouge_scores)

print("\n=========== TruthfulQA Results ===========")
print(f"Exact Match Accuracy: {accuracy:.4f}")
print(f"Avg BLEU Score:       {avg_bleu:.4f}")
print(f"Avg ROUGE-L Score:    {avg_rouge:.4f}")


# =======================================
#  WRITE DETAILED MARKDOWN REPORT
# =======================================
md = StringIO()
md.write("# TruthfulQA Multi-Agent Evaluation\n\n")
md.write("## Overall Metrics\n")
md.write(f"- Exact Match Accuracy: **{accuracy:.4f}**\n")
md.write(f"- Average BLEU Score: **{avg_bleu:.4f}**\n")
md.write(f"- Average ROUGE-L Score: **{avg_rouge:.4f}**\n\n")

md.write("## Per-Sample Results\n")
for i, (gold, pred) in enumerate(zip(gold_texts, pred_texts)):
    md.write(f"### Sample {i+1}\n")
    md.write(f"**Question:** {train_samples[i]['Question']}\n\n")
    md.write(f"**Gold Answer:**\n```\n{gold}\n```\n")
    md.write(f"**Model Final Answer:**\n```\n{pred}\n```\n\n")
    md.write("---\n")

with open("../docs/truthfulqa_results.md", "w", encoding="utf-8") as f:
    f.write(md.getvalue())

print("\nMarkdown report saved to truthfulqa_results.md")
