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
        
        response = self.genai.invoke({"question": state["question"], "context": state["context"]})
        model_dict = {
            f"BaseModel_{self.rank}": 
                {
                    "response": response,
                    "hallu_type": (None, "UNKNOWN"),  # Placeholder for hallucination type
                    "reason": "",  #  Placeholder for hallucination reason
                }
        }
        # Merge this model's output into state['responses'] so multiple models
        # can run in parallel and contribute their entries without clobbering.
        # if "responses" not in state or not isinstance(state["responses"], dict):
        #     state["responses"] = {}
        # state["responses"].update(model_dict)
        # print(state["question"])
        return {"responses": model_dict}
      

    # def _execute(self, state: GraphState, **kwargs) -> GraphState:
    #     def _run(state: GraphState):
           
    #         prompt = ChatPromptTemplate.from_messages([
    #             (
    #                 "system",
    #                 "You are a thoughtful and supportive assistant who provides emotionally intelligent and practical advice."
    #             ),
    #             (
    #                 "user",
    #                 (
    #                     "Given the context below, provide a calm, healthy, and actionable response.\n\n"
    #                     "Context: {context}\n\n"
    #                     "Question: {question}\n\n"
    #                     "Your response should focus on emotional well-being, mindset improvement, and practical steps."
    #                 ),
    #             ),
    #         ])
    #         chain = prompt | self.base_model | StrOutputParser()

    #         answer = chain.invoke({
    #             "question": state["question"],
    #             "context": state["context"],
    #         })

    #         return {"responses": {self.base_model.get_name(): answer}}

    #     return _run

