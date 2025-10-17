from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.language_models import BaseChatModel

from agents.agent import Agent
from graphstate import GraphState
from agents.AGENT_PROMPTS import SYSTEM_PROMPTS


class BaseModel(Agent):
    def __init__(self, base_model: BaseChatModel, rank: int):
        """
        base_model - base model 
        """
        self.base_model = base_model
        self.rank = rank
        prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPTS["genai"])
        self.genai = prompt | base_model | StrOutputParser()

    def get_name(self) -> str:
        return f"BaseModel_{self.rank}"

    def _execute(self, state: GraphState, **kwargs) -> GraphState:
        question = state["question"]
        context = state["context"]
        response = self.genai.invoke({"question": question, "context": context})
        model_dict = {
            f"BaseModel_{self.rank}": 
                {
                    "response": response,
                    "hallu_type_int": None,  # Placeholder for hallucination type
                    "reason": "",  #  Placeholder for hallucination reason
                }
        }
        # Merge this model's output into state['responses'] so multiple models
        # can run in parallel and contribute their entries without clobbering.
        if "responses" not in state or not isinstance(state["responses"], dict):
            state["responses"] = {}
        state["responses"].update(model_dict)
        return state

