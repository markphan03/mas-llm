from typing import List, Dict, Any, Annotated
from typing_extensions import TypedDict

def keep_state(x, y):
    return x if x is not None else x

class GraphState(TypedDict):
    question: str
    context: str
    responses: Annotated[dict, lambda x, y: {**x, **y}]  # merge rule
    # e.g., {"BaseModel_1": {"response": "answer1", "hallu_type": "...", "reason": "..."}




    
