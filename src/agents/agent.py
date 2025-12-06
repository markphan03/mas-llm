from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.language_models import BaseChatModel

from agents.base_agent import BaseAgent
from graphstate import GraphState
from agents.AGENT_PROMPTS import SYSTEM_PROMPTS

import re
import json

NUMBER_OF_AGENTS = 3

class Agent(BaseAgent):
    def __init__(self, base_model: BaseChatModel, rank: int):
        """
        base_model - base model 
        """
        self.base_model = base_model
        self.rank = rank
        self.name = self.get_name()
        self.response = ""
        self.other_responses = {}
        self.vote = {}
        self.is_execute = True  # True when agent is on - False when agent is off(executing job)
        prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPTS["genai"])
        self.genai = prompt | base_model | StrOutputParser()
        voting_prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPTS["voting"])
        self.voting_ai = voting_prompt | base_model | StrOutputParser()

    def get_name(self) -> str:
        return f"agent_{self.rank}"
    
    def is_continue(self, state, **kwargs):
        return self.is_execute
    
    def extract_vote(self, text: str) -> str:
        match = re.search(r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}", text)
        if not match:
            return None
        try:
            json_result= json.loads(match.group(0))
        except json.JSONDecodeError:
            json_result = None
        return json_result
    
    def _execute(self, state: GraphState, **kwargs) -> GraphState:
        model_dict = {
                self.name: 
                    {
                        "model_name": self.base_model.model_dump().get("model"),
                        "response": self.response,
                        "other_responses": self.other_responses,
                        "vote": self.vote,
                    }

            }
      
        # Get the current response entry (or None if missing)
        agent_state = state["responses"].get(self.name, {})
        existing_response = (
            agent_state
            .get("response")
        )

        # Step 1: Generate its own response
        if existing_response is None:
            self.response = self.genai.invoke({
                "question": state["question"],
                "context": state["context"]
            })
            
            model_dict[self.name]["response"] = self.response

        # Step 2: Gather other agents' responses
        for i in range(1, NUMBER_OF_AGENTS+1):
            current_agent = f"agent_{i}"
            if current_agent != self.name:
                current_agent_response = (
                    state["responses"]
                    .get(current_agent, {})
                    .get("response")
                )
                if current_agent_response is not None:
                    self.other_responses[current_agent] = current_agent_response

        # Step 3: Vote other agents' responses
        if len(self.other_responses) == NUMBER_OF_AGENTS-1:
            model_dict[self.name]["other_responses"] = self.other_responses

            # voting 
            self.vote = self.voting_ai.invoke({
                "question": state["question"],
                "context": state["context"],
                "other_responses": model_dict[self.name]["other_responses"],
            })

            self.vote = self.extract_vote(self.vote)

            model_dict[self.name]["vote"] = self.vote

            self.is_execute = False

        return {"responses": model_dict}

      

