# agent.py
import re
import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings

from src.agents.base_agent import BaseAgent
from src.graphstate import GraphState
from src.agents.AGENT_PROMPTS import SYSTEM_PROMPTS
from src.metrics.response_relevancy_scorer import ResponseRelevancyScorer


class Agent(BaseAgent):
    def __init__(self, base_model: BaseChatModel, num_agents: int, rank: int, embd_model: Embeddings = None):
        self.base_model = base_model
        self.rank = rank
        self.name = self.get_name()
        self.num_agents = num_agents
        self.response = None
        self.other_responses = {}
        self.vote = {}
        self.is_execute = True

        # generation model
        gen_prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPTS["genai"])
        self.genai = gen_prompt | base_model | StrOutputParser()

        # voting model
        voting_prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPTS["voting"])
        self.voting_ai = voting_prompt | base_model | StrOutputParser()

        # embedding model + response relevancy scorer
        self.embd_model = embd_model
        self.response_relevancy_scorer = ResponseRelevancyScorer(self.embd_model)


    def reset(self):
        self.response = None
        self.other_responses = {}
        self.vote = {}
        self.is_execute = True

    def get_name(self) -> str:
        return f"agent_{self.rank}"

    def is_continue(self, state, **kwargs):
        """Return True → keep looping; False → stop."""
        return self.is_execute

    # ----------------------------------------------
    # Extract JSON { ... } from LLM output
    # ----------------------------------------------
    def extract_vote(self, text: str):
        match = re.search(r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}", text)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    # ----------------------------------------------
    # Main execution
    # ----------------------------------------------
    def _execute(self, state: GraphState, **kwargs) -> GraphState:

        # Pull existing state for this agent
        agent_state = state["responses"].get(self.name, {})
        question = state["question"]
        context = state["context"]
        example = state["example"]
        # ==========================================================
        # STEP 1 — Generate self response (only ONCE)
        # ==========================================================
        if agent_state.get("response") is None:
            self.response = self.genai.invoke({
                "question": question,
                "context": context
            })

        # ==========================================================
        # STEP 2 — Collect other agent responses
        # ==========================================================
        self.other_responses = {}
        for i in range(1, self.num_agents + 1):
            name = f"agent_{i}"
            if name == self.name:
                continue  # skip self

            resp = state["responses"].get(name, {}).get("response")
            if resp is not None:
                self.other_responses[name] = resp

        # ==========================================================
        # STEP 3 — Voting Logic
        #    Only happens when NUMBER_OF_AGENTS > 1
        # ==========================================================
        if self.num_agents > 1:

            # Only vote when all other agents responded
            if len(self.other_responses) == self.num_agents - 1:
                vote_raw = self.voting_ai.invoke({
                    "question": question,
                    "context": context,
                    "other_responses": self.other_responses
                })

                self.vote = self.extract_vote(vote_raw)
                # Calculate Agent Score - TODO: Add Parallelism + Refactor code
                if self.vote is not None:
                    for agent, value in self.vote.items():
                        agent_res = self.other_responses.get(agent, {})
                        response_score = self.response_relevancy_scorer.calculate_response_relevancy(
                            question=question,
                            correct_example=example,
                            response=agent_res      
                        )
                        self.vote[agent] = {
                            "decision": value, # approval/reject
                            "response_score": response_score # cosine similarity score of agent's response to question
                        }
                self.is_execute = False

        else:
            # ======================================================
            # SPECIAL CASE: Only 1 agent → No votes needed
            # ======================================================
            self.vote = {}
            self.is_execute = False   # stop immediately

        # ==========================================================
        # Return updated state
        # ==========================================================
        return {
            "responses": {
                self.name: {
                    "model_name": self.base_model.model_dump().get("model"),
                    "response": self.response,
                    "other_responses": self.other_responses,
                    "vote": self.vote
                }
            }
        }
