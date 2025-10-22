import random
import numpy as np
import torch

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.language_models import BaseChatModel

from graphstate import GraphState
from workflow import create_graph
from agents.base_model import BaseModel
from agents.hallucination_classifier import HallucinationClassifier
import pprint


# --- Set all seeds ---
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

# --- Ollama models with deterministic parameters ---
def make_deterministic_model(model_name: str):
    """Return a ChatOllama model with fixed randomness control."""
    return ChatOllama(
        model=model_name,
        temperature=0.0,   # fully deterministic
        top_p=1.0,
        seed=SEED          # seed control (supported in recent Ollama versions)
    )

# Wrap ChatOllama instances with BaseModel so they expose `execute`
base_models = [
    BaseModel(make_deterministic_model("llama3.1"), rank=1),
    BaseModel(make_deterministic_model("deepseek-r1"), rank=2),
]

hallu_classifier = HallucinationClassifier(make_deterministic_model("deepseek-r1"))

# --- Run example ---
# --- Example Run ---
inputs = {
    "question": "What is the capital of France?",
    "context": (
        "Paris first became the capital of France in 508 AD under King Clovis I. "
        "It lost this status for a time but regained it under Hugh Capet in 987, "
        "with its position as the permanent capital becoming firmly established "
        "under the Capetian dynasty."
    ),
}

graph = create_graph(base_models, hallu_classifier)

# Run graph — this returns the **final merged output**
final_state = graph.invoke(inputs)

# Pretty print cleanly
pprint.pprint(final_state)

