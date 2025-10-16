from typing import List, Dict, Any
from typing_extensions import TypedDict

class GraphState(TypedDict):
    question_context: tuple[str, str]  # pair of (question, context)
    responses: Dict[str, Dict[str, Any]]  
    # e.g., {"BaseModel_1": {"response": "answer1", "hallu_type": "...", "reason": "..."}




    
