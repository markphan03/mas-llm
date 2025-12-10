import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel

from src.agents.AGENT_PROMPTS import SYSTEM_PROMPTS


### TODO: Inefficient for future development - processing entire dataset - should only process 1 data only

class TruthScore(BaseModel): 
    """ Binary score for hallucination present in generation answer. """ 
    binary_score: bool = Field(
        description="Answer is grounded in the facts, 'True' or 'False'" )

class TruthfulGrader():
    def __init__(self, base_model: BaseChatModel, **kwargs):
        truth_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPTS["truthful_prompt"]),
                ("human", "Here is the question {question} \n\n "
                "Correct answer for that question is: \n\n {correct_answer} \n\n "
                "LLM answer: {generation} "),
            ]
        )
        structured_llm_grader = base_model.with_structured_output(TruthScore)
        self.truthful_grader = truth_prompt | structured_llm_grader
        super().__init__(**kwargs)

    def calculate_truthful_accuracy(self, gen_dataset: list, save_path: str = None) -> float:
        """
        Compute truthful accuracy and optionally update the dataset by adding 
        a new key 'is_truthful' to each entry, then saving the updated JSON.
        """
        truth_classes = []

        for data in gen_dataset:
            id = data["id"]
            question = data["question"]
            gold_answer = data["gold_answer"]
            pred_answer = data["pred_answer"]

            truth_class = self.truthful_grader.invoke(
                {
                    "question": question,
                    "correct_answer": gold_answer,
                    "generation": pred_answer,
                }
            ).binary_score

            print(f"Sample {id} - truth class {truth_class}")

            # Convert boolean → integer
            truth_int = 1 if truth_class else 0
            truth_classes.append(truth_int)

            # 🔥 Add new key-value pair
            data["is_truthful"] = truth_class

        # Save updated JSON if requested
        if save_path is not None:
            with open(save_path, "w") as f:
                json.dump(gen_dataset, f, indent=4)

        # Compute accuracy
        score = sum(truth_classes) / len(truth_classes)
        return score
    
    def calculate_truthful_accuracy_2(self, question, reference, hypothesis) -> float:
        """
        Compute truthful accuracy and optionally update the dataset by adding 
        a new key 'is_truthful' to each entry, then saving the updated JSON.
        """
        

        truth_class = self.truthful_grader.invoke(
            {
                "question": question,
                "correct_answer": reference,
                "generation": hypothesis,
            }
        ).binary_score

        print(f"Sample {id} - truth class {truth_class}")

        # Convert boolean → integer
        truth_class = 1 if truth_class else 0
        return truth_class

