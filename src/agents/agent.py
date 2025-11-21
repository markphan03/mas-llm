from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.language_models import BaseChatModel

from agents.base_agent import BaseAgent
from graphstate import GraphState
from agents.AGENT_PROMPTS import SYSTEM_PROMPTS


class Agent(BaseAgent):
    def __init__(self, base_model: BaseChatModel, rank: int):
        """
        base_model - base model 
        """
        self.base_model = base_model
        self.rank = rank
        self.name = self.get_name()
        self.stop = False
        prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPTS["genai"])
        self.genai = prompt | base_model | StrOutputParser()

    def get_name(self) -> str:
        return f"agent_{self.rank}"
    
    def is_done(self, state: GraphState, **kwargs):
        # if state["responses"][self.name]["other_responses"] is not None:
        #     print("Is Done executing")
        #     return True
        # return False
        if self.stop:
            return True
        return False

    def _execute(self, state: GraphState, **kwargs) -> GraphState:
        
        model_dict = {
            self.name: 
                    {
                        "model_name": self.base_model.model_dump().get("model"),
                        "response": "",
                        "other_responses": {},
                        "vote": [],
                    }
        }
        
        if state["responses"] is None or \
            self.name not in state["responses"].keys():
            response = self.genai.invoke({"question": state["question"], "context": state["context"]})
            model_dict[self.name]["response"] = response
        else:
            
            self.stop = True
                # for i in range(3):
                #     current_agent = f"agent_{i+1}"
                #     if current_agent != self.name:
                #         model_dict[self.name]["other_responses"] = \
                #             {current_agent: state["responses"][current_agent]["response"]}
                        
            # print(model_dict)
        
        
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

