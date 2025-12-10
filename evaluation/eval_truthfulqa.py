import re
import json
import random
import numpy as np

from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, Any, List
from io import StringIO
from sklearn.metrics import accuracy_score
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer
from comet import download_model, load_from_checkpoint

from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from src.graphstate import GraphState
from src.workflow import create_graph
from src.agents.agent import Agent
from src.agents.vote import Vote
from src import TruthfulGrader

# =======================================
#  RANDOM SEED
# =======================================
load_dotenv()

SEED = 42
random.seed(SEED)
np.random.seed(SEED)


# =======================================
#  SETUP AGENTS
# =======================================
NUMBER_OF_AGENTS = 1
agents = [
    Agent(ChatOllama(model="llama3.1", seed=SEED), num_agents=NUMBER_OF_AGENTS, rank=1),
    Agent(ChatOllama(model="deepseek-r1", seed=SEED), num_agents=NUMBER_OF_AGENTS, rank=2),
    Agent(ChatOllama(model="mistral", seed=SEED), num_agents=NUMBER_OF_AGENTS, rank=3),
]

vote_manager = Vote(agents=agents, method="approval")


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

bleu1_scores = []
bleu4_scores = []
rouge1_scores = []
rougeL_scores = []
truthful_scores = []

scores_logs = []

# ROUGE scorer setup
rouge = rouge_scorer.RougeScorer(['rouge1', 'rougeL'], use_stemmer=True)


# Truthful Grader 
llm = "gpt-4o-mini"
truthful_scorer = TruthfulGrader(base_model=ChatOpenAI(model=llm))
# =======================================
#  MAIN EVALUATION LOOP
# =======================================
for i, sample in enumerate(train_samples):
    # RESET AGENTS FOR NEW QUESTION
    for agent in agents:
        agent.reset()

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
    final_answer = vote_manager.generate_final_answer(voting_state, agents)

    # ========== Store Predictions ==========
    gold_texts.append(gold_answer)
    pred_texts.append(final_answer)

    # BLEU-1
    smoothie = SmoothingFunction().method2
    bleu1 = sentence_bleu(
        [gold_answer.split()],
        final_answer.split(),
        smoothing_function=smoothie,
        weights=(1, 0, 0, 0)
    )
    bleu1_scores.append(bleu1)

    # BLEU-4
    bleu4 = sentence_bleu(
        [gold_answer.split()],
        final_answer.split(),
        smoothing_function=smoothie,
        weights=(0.25, 0.25, 0.25, 0.25)
    )
    bleu4_scores.append(bleu4)

    # ROUGE-1 and ROUGE-L
    scores = rouge.score(gold_answer, final_answer)
    rouge1_score = scores['rouge1'].fmeasure
    rougeL_score = scores['rougeL'].fmeasure

    rougeL_scores.append(rougeL_score)
    rouge1_scores.append(rouge1_score)

    # Truthful Accuracy
    truthful_score = truthful_scorer.calculate_truthful_accuracy_2(question, gold_answer, final_answer)
    truthful_scores.append(truthful_score)

    scores_log = f"Sample {i+1}: BLEU1={bleu1:.4f} BLUE4={bleu4:.4f} ROUGE1={rouge1_score:.4f} ROUGEL={rougeL_score:.4f} Truthful_Score={True if truthful_score else False}"
    scores_logs.append(scores_log)
    print(scores_log)

    

    if (i + 1) % 25 == 0:
        print(f"Processed {i + 1}/{len(train_samples)}")


# Load COMET model once (recommended: "Unbabel/wmt22-comet-da")
MODEL_PATH = download_model("Unbabel/wmt22-comet-da")
model = load_from_checkpoint(MODEL_PATH)


def cal_comet_score(hypotheses, references, sources=None):
    """
    Compute COMET scores.

    hypotheses: list[str]
    references: list[str]
    sources:    list[str] or None (many COMET models require sources)
    
    Returns: list of COMET scores (floats)
    """

    # Prepare batch
    data = []
    for h, r in zip(hypotheses, references):
        data.append({
            "src": "" if sources is None else sources,  # source can be empty string
            "mt": h,
            "ref": r,
        })

    # Compute scores
    model_output = model.predict(data, batch_size=16, gpus=1)
    return model_output.system_score


comet_score = cal_comet_score(gold_texts, pred_texts)

# =======================================
#  METRIC RESULTS
# =======================================
# Compute averages
avg_bleu1 = sum(bleu1_scores) / len(bleu1_scores)
avg_bleu4 = sum(bleu4_scores) / len(bleu4_scores)
avg_rouge1 = sum(rouge1_scores) / len(rouge1_scores)
avg_rougeL = sum(rougeL_scores) / len(rougeL_scores)
avg_truthful = sum(truthful_scores) / len(truthful_scores)

print("\n=========== TruthfulQA Results ===========")
print(f"Average BLEU-1 Score:   {avg_bleu1:.4f}")
print(f"Average BLEU-4 Score:   {avg_bleu4:.4f}")
print(f"Average ROUGE-1 Score:  {avg_rouge1:.4f}")
print(f"Average ROUGE-L Score:  {avg_rougeL:.4f}")
print(f"Average COMET Score: {comet_score:.4f}")
print(f"Average Truthful Score: {avg_truthful:.4f}")

# =======================================
#  SAVE PER-SAMPLE RESULTS TO JSON
# =======================================
import json

results_json = []

for i, (gold, pred) in enumerate(zip(gold_texts, pred_texts)):
    entry = {
        "id": i + 1,
        "question": train_samples[i]["Question"],
        "gold_answer": gold,
        "pred_answer": pred,
        "is_truthful": True if truthful_scores[i] else False,
    }
    results_json.append(entry)

project_root = Path(__file__).parent.parent
json_output_path = project_root / "docs" / "truthfulqa_results.json"

with open(json_output_path, "w", encoding="utf-8") as jf:
    json.dump(results_json, jf, indent=4, ensure_ascii=False)

print(f"JSON results saved to {json_output_path}")


# =======================================
#  WRITE DETAILED MARKDOWN REPORT
# =======================================
md = StringIO()
md.write("# TruthfulQA Multi-Agent Evaluation\n\n")
md.write("## Overall Metrics\n")
md.write(f"- Average BLEU-1 Score: **{avg_bleu1:.4f}**\n")
md.write(f"- Average BLEU-4 Score: **{avg_bleu4:.4f}**\n")
md.write(f"- Average ROUGE-1 Score: **{avg_rouge1:.4f}**\n")
md.write(f"- Average ROUGE-L Score: **{avg_rougeL:.4f}**\n\n")
md.write(f"- Average COMET Score: **{comet_score:.4f}**\n\n")
md.write(f"- Average Truthful Score: **{avg_truthful:.4f}**\n\n")

md.write("## Per-Sample Results\n")
for i, (gold, pred) in enumerate(zip(gold_texts, pred_texts)):
    md.write(f"### Sample {i+1}\n {scores_logs[i]}\n\n")
    md.write(f"**Question:** {train_samples[i]['Question']}\n\n")
    md.write(f"**Gold Answer:**\n```\n{gold}\n```\n")
    md.write(f"**Model Final Answer:**\n```\n{pred}\n```\n\n")
    md.write("---\n")

doc_file = project_root / "docs" / "truthfulqa_results.md"

with open(doc_file, "w", encoding="utf-8") as f:
    f.write(md.getvalue())

print("\nMarkdown report saved to truthfulqa_results.md")

