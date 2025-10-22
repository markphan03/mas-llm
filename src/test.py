from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.language_models import BaseChatModel

from graphstate import GraphState
from workflow import create_graph
from agents.base_model import BaseModel
from agents.hallucination_classifier import HallucinationClassifier
import pprint


# Wrap ChatOllama instances with your BaseModel so they expose `execute`
base_models = [
    BaseModel(ChatOllama(model="llama3.1"), rank=1),
    BaseModel(ChatOllama(model="deepseek-r1"), rank=2),
]

hallu_classifier = HallucinationClassifier(ChatOllama(model="llama3.1"))


# --- Run example ---
inputs: GraphState = {
    "question": "What is the capital of France?",
    "context": "Capital of France is Paris",
}

inputs: GraphState = {
    "question": "",
    "context": "",
}

graph = create_graph(base_models, 
                     hallu_classifier
                     )

# Run graph — this returns the **final merged output**
final_state = graph.invoke(inputs)

# Pretty print cleanly
pprint.pprint(final_state)