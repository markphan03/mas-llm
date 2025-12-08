from abc import ABC, abstractmethod
from src.graphstate import GraphState

class BaseAgent(ABC):

    @abstractmethod
    def _execute(self, state: GraphState, **kwargs) -> GraphState:
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the agent’s name."""
        pass

    def execute(self, state: GraphState, **kwargs) -> GraphState:
        return self._execute(state, **kwargs)
        
