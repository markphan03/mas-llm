from typing import List, Dict, Any, Annotated
from typing_extensions import TypedDict


class GraphState(TypedDict):
    question: str
    context: str
    responses: Annotated[dict, lambda x, y: {**x, **y}]  # merge rule
    visited: set
    # e.g., {"BaseModel_1": {"response": "answer1", "hallu_type": "...", "reason": "..."}



    
