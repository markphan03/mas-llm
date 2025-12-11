import re
import random
import math
from typing import Literal, List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.graphstate import GraphState
from src.agents.agent import Agent
from src.agents.AGENT_PROMPTS import SYSTEM_PROMPTS


class Vote:
    def __init__(
        self,
        agents: List[Agent],
        method: Literal["borda", "approval"] = "approval"
    ):
        self.name = self.get_name()
        self.agents = agents
        self.num_agents = len(agents)
        self.method = method
        self.voting_continue = True

    def get_name(self):
        return "vote_manager"

    def is_continue(self, state: GraphState):
        """Vote loop only runs when more than 1 agent exists"""
        if self.num_agents <= 1:
            return False
        return self.voting_continue

    # ----------------------------------------------------------------------
    # Score Aggregation
    # ----------------------------------------------------------------------
    def _collect_weighted_scores(self, responses, agents):
        """Collect approval votes from each agent. 
        Each approval vote is weighted differently corresponding to the agent's response relevancy
        For example, there is high-confident approval vote - low confident approval vote"""
        scores = {agent: 0 for agent in agents}
        for _, agent_res in responses.items():
            votes = agent_res.get("vote", {})
            if not votes:
                continue

            for agent_name, decision_meta in votes.items():
                decision = decision_meta["decision"]
                response_score = decision_meta["response_score"]
                if agent_name in scores:
                    if decision == "approve":
                        bonus = 1 + response_score
                        scores[agent_name] += bonus
                    else:
                        scores[agent_name] += response_score

        return scores

    # ----------------------------------------------------------------------
    # Elimination Logic
    # ----------------------------------------------------------------------
    def _eliminate(self, scores):
        """Keep all agents whose score >= avg score."""
        avg = sum(scores.values()) / len(scores)
        # print(avg)
        # for agent, score in scores.items():
        #     print(f"Agent - {agent} - Score - {score}")
        # print([agent for agent, score in scores.items() if score >= avg])
        return [agent for agent, score in scores.items() if score >= avg]

    # ----------------------------------------------------------------------
    # Voting Node Execution
    # ----------------------------------------------------------------------
    def execute(self, state: GraphState):
        """Run approval voting round."""
        # ============================================================
        # SPECIAL CASE — only 1 agent → skip all voting logic
        # ============================================================
        if self.num_agents <= 1:
            self.voting_continue = False

            # create trivial score for the only agent
            only_agent = self.agents[0].name
            return {
                "winners": [only_agent],
                "agent_scores": {only_agent: 1}
            }

        # ============================================================
        # Normal multi-agent case
        # ============================================================
        if self.method != "approval":
            raise NotImplementedError("Only approval voting implemented.")

        winners = state["winners"]
        responses = state["responses"]

        scores = self._collect_weighted_scores(responses, winners)
        new_winners = self._eliminate(scores)

        # stop when winners list stop changing OR floor of (half of winners) remain
        self.voting_continue = not (
            len(new_winners) <= math.floor(self.num_agents/2) or new_winners == winners
        )

        return {
            "winners": new_winners,
            "agent_scores": scores,
        }

    # ----------------------------------------------------------------------
    # FINAL ANSWER GENERATION
    # ----------------------------------------------------------------------
    def generate_final_answer(self, state: GraphState, agents: list[Agent]):
        """
        When voting ends, choose the winning agent and summarize their
        approved peers' answers.
        """

        question = state.get("question", "")
        context = state.get("context", "")
        responses = state.get("responses", {})
        agent_scores = state.get("agent_scores", {})

        # ============================================================
        # SPECIAL CASE — Only one agent in the system
        # ============================================================
        if self.num_agents <= 1:
            only_agent = agents[0]
            raw_answer = only_agent.response or responses[only_agent.name]["response"]
            return re.sub(r"<think>.*?</think>", "", raw_answer, flags=re.DOTALL)

        # ============================================================
        # Multi-agent final selection
        # ============================================================
        max_votes = max(agent_scores.values())
        winners = [agent for agent, score in agent_scores.items() if score == max_votes]
        chosen_agent_name = winners[0] if len(winners) == 1 else random.choice(winners) 

        agent_lookup = {f"agent_{a.rank}": a for a in agents}
        chosen_agent = agent_lookup[chosen_agent_name]
        chosen_agent_record = responses[chosen_agent_name]

        response = chosen_agent_record.get("response", "")
        other_responses = chosen_agent_record.get("other_responses", {})
        
        votes = chosen_agent_record.get("vote", {}) or {}

        formatted_responses = "\n\n"
        for agent_name, text in other_responses.items():
            # Safe: returns {} instead of None
            if votes.get(agent_name, {}).get("decision") == "approve":
                formatted_responses += f"{agent_name}: {text}\n"

        final_prompt = ChatPromptTemplate.from_template(
            SYSTEM_PROMPTS["summarization"]
        )

        llm = final_prompt | chosen_agent.base_model | StrOutputParser()
        raw_result = llm.invoke({
            "question": question,
            "context": context,
            "response": response,
            "formatted_responses": formatted_responses
        })

        result_text = (
            raw_result.content if hasattr(raw_result, "content") else str(raw_result)
        )

        # remove <think> for reasoning models
        return re.sub(r"<think>.*?</think>", "", result_text, flags=re.DOTALL)

    