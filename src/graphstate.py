from typing import List, Dict, Any, Annotated
from typing_extensions import TypedDict


class GraphState(TypedDict):
    question: str
    context: str
    example: str  # example correct answer - one-shot
    winners: list  # agents that win the vote 
    agent_scores: dict[str, int]
    responses: Annotated[dict, lambda x, y: {**x, **y}]  # merge rule
    # e.g., {"BaseModel_1": {"response": "answer1", "hallu_type": "...", "reason": "..."}



    
