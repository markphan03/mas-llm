from typing import Literal, List
from graphstate import GraphState
from agents.agent import Agent

class Vote:
    def __init__(
        self,
        agents: List[Agent],
        method: Literal["borda", "approval"] = "approval"
    ):
        self.name = self.get_name()
        self.agents = agents
        self.method = method
        self.voting_continue = True

    def get_name(self):
        return "vote_manager"


    def is_continue(self, state: GraphState):
        return self.voting_continue

    # ----------------------------------------------------------------------
    # Node execution – must return a dict for state update
    # ----------------------------------------------------------------------
    def execute(self, state: GraphState):
        """
        Perform a voting elimination and update the state.
        Returns a partial state dict.
        """

        if self.method != "approval":
            raise NotImplementedError("Only approval voting implemented.")

        winners = state["winners"]
        responses = state["responses"]

        # ---- Step 1: count scores ----
        scores = self._collect_scores(responses, winners)

        # ---- Step 2: eliminate low scorers ----
        new_winners = self._eliminate(scores)

        # ---- Step 3: termination condition ----
        self.voting_continue = not (len(new_winners) <= 2 or len(new_winners) == len(winners))

        return {
            "winners": new_winners,
            "agent_scores": scores,
        }

    

    # ----------------------------------------------------------------------
    # Helper: score aggregation
    # ----------------------------------------------------------------------
    def _collect_scores(self, responses, agents):
    
        scores = {a: 0 for a in agents}

        for _, agent_res in responses.items():
            votes = agent_res["vote"]
            if votes is not None:
                for agent, decision in votes.items():
                    if decision == "approve":
                        scores[agent] += 1

        return scores

    # ----------------------------------------------------------------------
    # Helper: elimination
    # ----------------------------------------------------------------------
    def _eliminate(self, scores):
        avg = sum([score for _, score in scores.items()]) / len(scores)
        return [a for a in scores.keys() if scores[a] >= avg]
