from typing import Dict, Any

from agents.agent import Agent
from graphstate import GraphState


class ResponseAggregator(Agent):
    """Aggregate responses from multiple BaseModel nodes into a single state field.

    The aggregator expects `state['responses']` to be a dict where nodes append
    their own entries. This agent will collect them and produce
    `state['aggregated_responses']` for downstream consumption.
    """

    def __init__(self):
        pass

    def get_name(self) -> str:
        return "ResponseAggregator"

    def _execute(self, state: GraphState, **kwargs) -> GraphState:
        responses = state.get("responses", {})
        # normalized aggregator: ensure it's a dict of model_name -> info
        if not isinstance(responses, dict):
            state["aggregated_responses"] = {}
            return state

        # simply copy the collected responses under a new key for clarity
        state["aggregated_responses"] = responses.copy()
        return state
