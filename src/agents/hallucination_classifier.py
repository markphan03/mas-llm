from pydantic import BaseModel, Field
from langchain.prompts import ChatPromptTemplate
from typing import Any

from src.graphstate import GraphState
from agents.agent import Agent
from agents.AGENT_PROMPTS import SYSTEM_PROMPTS

class HallucinationType(BaseModel):
    hallu_type: int = Field(
        description=(
            "Integer code for hallucination type (0..5) where 0=NOT_HALLUCINATED, "
            "1=FACTUAL_FABRICATION, 2=FACTUAL_CONTRADICTION, 3=INSTRUCTION_INCONSISTENCY, "
            "4=CONTEXT_INCONSISTENCY, 5=LOGICAL_INCONSISTENCY"
        ),
    )
    

class HallucinationClassifier(Agent):
    def __init__(self, base_model: Any, **kwargs):

        # TODO: 
        hallu_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPTS["hallucination_checker"]),
                ("human", "Set of facts: \n\n {documents} \n\n LLM generation: {generation}"),
            ]
        )
        hallu_classifier = base_model.with_structured_output(HallucinationType)
        self.hallu_type_classifier_chain = hallu_prompt | hallu_classifier
        # self.hallu_classifier_reason_chain = 
        super().__init__(**kwargs)

    def get_name(self):
        return "Hallucination Classifier"


    def _execute(self, state, **kwargs):
        return self.classify_hallucination(state)

    
    def classify_hallucination(self, state: GraphState):
        """
        Classify hallucination type for each model response in the state.
        This function iterates over `state['responses']` (expected to be a mapping
        from model name to a dict that contains at least a 'response' key) and
        attaches `hallu_type` and a placeholder `reason` to each entry.
        """
        try:
            question, context = state.get("question_context", (None, None))
        except Exception:
            question, context = (None, None)

        responses = state.get("responses", {})
        # If responses is not a mapping of model_name -> info dict, do nothing
        if not isinstance(responses, dict):
            return state

        # TODO: Add logic to run in parallel if many models' response
        for model_name, info in list(responses.items()):
            if not isinstance(info, dict):
                continue
            response = info.get("response")
            if not response:
                continue

            try:
                out = self.hallu_type_classifier_chain.invoke(
                    {"documents": context, "generation": response}
                )
                hallu_type = out.hallu_type
            except Exception:
                hallu_type = None

            state["responses"][model_name]["hallu_type"] = hallu_type
            state["responses"][model_name]["reason"] = ""  # TODO: Add reason generation logic

        return state


    