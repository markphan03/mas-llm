from abc import ABC, abstractmethod
from graphstate import GraphState

class Agent(ABC):

    @abstractmethod
    def _execute(self, state: GraphState, **kwargs) -> GraphState:
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the agent’s name."""
        pass

    def execute(self, state: GraphState, **kwargs) -> GraphState:
        return self._execute(state, **kwargs)
        
