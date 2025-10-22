from langgraph.graph import StateGraph, START, END
from agents.base_model import BaseModel
from agents.hallucination_classifier import HallucinationClassifier

from graphstate import GraphState


def create_graph(
    base_models: list[BaseModel],
    hallu_classifier: HallucinationClassifier,
):
    workflow = StateGraph(GraphState)

    # create agents (LLM nodes)
    for base_model in base_models:
        workflow.add_node(base_model.get_name(), base_model.execute)

    # create Hallu Classifier
    workflow.add_node(hallu_classifier.get_name(), hallu_classifier.execute)

    for base_model in base_models:
        workflow.add_edge(START, base_model.get_name())
        # workflow.add_edge(base_model.get_name(),END)
        workflow.add_edge(base_model.get_name(), hallu_classifier.get_name())

    workflow.add_edge(hallu_classifier.get_name(), END)


    return workflow.compile()
