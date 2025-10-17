from langgraph.graph import StateGraph, START, END
from agents.base_model import BaseModel
from agents.aggregator import ResponseAggregator
# from agents.hallucination_classifier import HallucinationClassifier

from graphstate import GraphState


def create_graph(
    base_models: list[BaseModel],
    # hallu_classifier: HallucinationClassifier,
):
    workflow = StateGraph(GraphState)

    # create agents (LLM nodes)
    for base_model in base_models:
        workflow.add_node(base_model.get_name(), base_model.execute)

    # create aggregator node
    aggregator = ResponseAggregator()
    workflow.add_node(aggregator.get_name(), aggregator.execute)

    # connect START -> each base model -> aggregator -> END
    for base_model in base_models:
        workflow.add_edge(START, base_model.get_name())
        workflow.add_edge(base_model.get_name(), aggregator.get_name())

    workflow.add_edge(aggregator.get_name(), END)

    return workflow.compile()
