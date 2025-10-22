# from pydantic import BaseModel, Field
# from langchain.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import StrOutputParser
# from typing import Any

# from graphstate import GraphState
# from agents.agent import Agent
# from agents.AGENT_PROMPTS import SYSTEM_PROMPTS

# # TODO: Create HallucinationType as a BERT classification model

# HALLU_DICT = {
#     0: "NOT_HALLUCINATED",
#     1: "FACTUAL_FABRICATION",
#     2: "FACTUAL_CONTRADICTION",
#     3: "INSTRUCTION_INCONSISTENCY",
#     4: "CONTEXT_INCONSISTENCY",
#     5: "LOGICAL_INCONSISTENCY",
# }

# # class HallucinationTypeBERT(BaseModel):
# #     """BERT Classification model output for hallucination type."""

# class HallucinationType(BaseModel): 
#     hallu_type: int = Field(
#         description=(
#             "Integer code for hallucination type (0..5) where 0=NOT_HALLUCINATED, "
#             "1=FACTUAL_FABRICATION, 2=FACTUAL_CONTRADICTION, 3=INSTRUCTION_INCONSISTENCY, "
#             "4=CONTEXT_INCONSISTENCY, 5=LOGICAL_INCONSISTENCY"
#         ),
#     )
    

# class HallucinationClassifier(Agent):
#     def __init__(self, base_model: Any, **kwargs):
#         hallu_type_prompt = ChatPromptTemplate.from_messages(
#             [
#                 ("system", SYSTEM_PROMPTS["hallu_classifier"]),
#                 ("human", "Question {question} \n\n Context: \n\n {context} \n\n LLM generation: {generation}"),
#             ]
#         )

#         hallu_reason_prompt = ChatPromptTemplate.from_messages(
#             [
#                 ("system", SYSTEM_PROMPTS["hallu_reason"]),
#                 ("human", "Question {question} \n\n Context: \n\n {documents} \n\n LLM generation: {generation} \\n Hallucnation type: {hallu_type}"),
#             ]
#         )
#         hallu_classifier = base_model.with_structured_output(HallucinationType)
#         self.hallu_type_classifier_chain = hallu_type_prompt | hallu_classifier
#         self.hallu_classifier_reason_chain = hallu_reason_prompt | base_model | StrOutputParser()
#         super().__init__(**kwargs)

#     def get_name(self):
#         return "Hallucination Classifier"


#     def _execute(self, state, **kwargs):
#         return self.classify_hallucination(state)

    
#     def classify_hallucination(self, state: GraphState):
#         """
#         Classify hallucination type for each model response in the state.
#         This function iterates over `state['responses']` (expected to be a mapping
#         from model name to a dict that contains at least a 'response' key) and
#         attaches `hallu_type` and a placeholder `reason` to each entry.
#         """
#         try:
#             question, context = state.get("question_context")
#         except Exception:
#             question, context = (None, None)

#         responses = state.get("responses", {})
#         # If responses is not a mapping of model_name -> info dict, do nothing
#         if not isinstance(responses, dict):
#             return state

#         # TODO: Add logic to run in parallel if many models' response
#         for model_name, info in list(responses.items()):
#             if not isinstance(info, dict):
#                 continue
#             response = info.get("response")
#             if not response:
#                 continue

#             try:
#                 out = self.hallu_type_classifier_chain.invoke(
#                     {"question": question, "documents": context, "generation": response}
#                 )
#                 hallu_type_int = out.hallu_type
#             except Exception:
#                 hallu_type_int = None

#             hallu_type = HALLU_DICT[hallu_type_int] if hallu_type_int in HALLU_DICT else "UNKNOWN"
#             try:
#                 reason = self.hallu_classifier_reason_chain.invoke(
#                     {
#                         "question": question,
#                         "documents": context,
#                         "generation": response,
#                         "hallu_type": hallu_type,
#                     }
#                 )
#             except Exception:
#                 reason = ""

#             state["responses"][model_name]["hallu_type"] = (hallu_type_int, HALLU_DICT.get(hallu_type_int)) if hallu_type_int is not None else (None, "UNKNOWN")
#             state["responses"][model_name]["reason"] = reason

#         return state


from pydantic import BaseModel, Field
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from typing import Any

from graphstate import GraphState
from agents.agent import Agent
from agents.AGENT_PROMPTS import SYSTEM_PROMPTS

# TODO: Create HallucinationType as a BERT classification model
# class HallucinationTypeBERT(BaseModel):
#     """BERT Classification model output for hallucination type."""

# ====================================
# Hallucination type definitions
# ====================================

HALLU_DICT = {
    0: "NOT_HALLUCINATED",
    1: "FACTUAL_FABRICATION",
    2: "FACTUAL_CONTRADICTION",
    3: "INSTRUCTION_INCONSISTENCY",
    4: "CONTEXT_INCONSISTENCY",
    5: "LOGICAL_INCONSISTENCY",
}


class HallucinationType(BaseModel):
    hallu_type: int = Field(
        description=(
            "Integer code for hallucination type (0..5) where 0=NOT_HALLUCINATED, "
            "1=FACTUAL_FABRICATION, 2=FACTUAL_CONTRADICTION, 3=INSTRUCTION_INCONSISTENCY, "
            "4=CONTEXT_INCONSISTENCY, 5=LOGICAL_INCONSISTENCY"
        ),
    )


# ====================================
# Hallucination Classifier Agent
# ====================================

class HallucinationClassifier(Agent):
    def __init__(self, base_model: Any, **kwargs):
        hallu_type_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPTS["hallu_classifier"]),
                (
                    "human",
                    "Question: {question}\n\nContext:\n\n{context}\n\nLLM generation:\n{generation}",
                ),
            ]
        )

        hallu_reason_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPTS["hallu_reason"]),
                (
                    "human",
                    "Question: {question}\n\nContext:\n\n{documents}\n\n"
                    "LLM generation:\n{generation}\nHallucination type: {hallu_type}",
                ),
            ]
        )

        hallu_classifier = base_model.with_structured_output(HallucinationType)
        self.hallu_type_classifier_chain = hallu_type_prompt | hallu_classifier
        self.hallu_classifier_reason_chain = hallu_reason_prompt | base_model | StrOutputParser()

        super().__init__(**kwargs)

    def get_name(self):
        return "Hallucination Classifier"

    def _execute(self, state: GraphState, **kwargs):
        """Run hallucination classification and only return updated responses."""
        updated_responses = self.classify_hallucination(state)
        # FIX: return only partial update instead of entire state
        return {"responses": updated_responses}

    def classify_hallucination(self, state: GraphState):
        """
        Classify hallucination type for each model response in the state.
        Returns only the updated responses (not the full state).
        """
        question = state.get("question", None)
        context = state.get("context", None)
        responses = state.get("responses", {})

        if not isinstance(responses, dict):
            return {}

        updated_responses = {}

        # TODO: Add logic to parallelize when multiple models exist
        for model_name, info in list(responses.items()):
            if not isinstance(info, dict):
                continue

            response = info.get("response")
            if not response:
                continue

            # --- classify hallucination type ---
            try:
                out = self.hallu_type_classifier_chain.invoke(
                    {"question": question, "context": context, "generation": response}
                )
                hallu_type_int = out.hallu_type
            except Exception:
                hallu_type_int = None

            hallu_type = HALLU_DICT.get(hallu_type_int, "UNKNOWN")

            # --- get reasoning ---
            try:
                reason = self.hallu_classifier_reason_chain.invoke(
                    {
                        "question": question,
                        "documents": context,
                        "generation": response,
                        "hallu_type": hallu_type,
                    }
                )
            except Exception:
                reason = ""

            # --- update result ---
            updated_responses[model_name] = {
                **info,
                "hallu_type": (
                    hallu_type_int,
                    hallu_type if hallu_type_int is not None else (None, "UNKNOWN"),
                ),
                "reason": reason,
            }

        return updated_responses
