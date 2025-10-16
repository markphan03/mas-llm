from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.language_models import BaseChatModel

from agents.agent import Agent
from src.graphstate import GraphState
from AGENT_PROMPTS import SYSTEM_PROMPTS


class BaseModel(Agent):
    def __init__(self, base_model: BaseChatModel, rank):
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
        question, context = state["question_context"]
        response = self.genai.invoke({"question": question, "context": context})
        model_dict = {
            "response": response,
            "hallu_type": None,  # Placeholder for hallucination type
            "reason": "",  #  Placeholder for hallucination reason
        }
        state["responses"] = model_dict
        return state

