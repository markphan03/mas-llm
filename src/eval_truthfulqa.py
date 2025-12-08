import re
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


# ROUGE scorer setup
rouge = rouge_scorer.RougeScorer(['rouge1', 'rougeL'], use_stemmer=True)


# =======================================
#  MAIN EVALUATION LOOP
# =======================================
for i, sample in enumerate(train_samples):
    if i == 50:
        break
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

    print(f"Sample {i+1}: BLEU1={bleu1:.4f} BLUE4={bleu4:.4f} ROUGE1={rouge1_score:.4f} ROUGEL={rougeL_score:.4f}")
    if (i + 1) % 25 == 0:
        print(f"Processed {i + 1}/{len(train_samples)}")


# =======================================
#  METRIC RESULTS
# =======================================
# Compute averages
avg_bleu1 = sum(bleu1_scores) / len(bleu1_scores)
avg_bleu4 = sum(bleu4_scores) / len(bleu4_scores)
avg_rouge1 = sum(rouge1_scores) / len(rouge1_scores)
avg_rougeL = sum(rougeL_scores) / len(rougeL_scores)

print("\n=========== TruthfulQA Results ===========")
print(f"Average BLEU-1 Score:   {avg_bleu1:.4f}")
print(f"Average BLEU-4 Score:   {avg_bleu4:.4f}")
print(f"Average ROUGE-1 Score:  {avg_rouge1:.4f}")
print(f"Average ROUGE-L Score:  {avg_rougeL:.4f}")

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

