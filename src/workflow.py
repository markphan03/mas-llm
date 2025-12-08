from langgraph.graph import StateGraph, START, END

from src.agents.agent import Agent
from src.graphstate import GraphState
from src.agents.vote import Vote


def create_graph(agents: list[Agent], vote_manager: Vote):

    workflow = StateGraph(GraphState)

    # ---------------------------------------------------------
    # 1. Register all agent nodes
    # ---------------------------------------------------------
    
    for agent in agents:
        workflow.add_node(agent.get_name(), agent.execute)
    
    # ---- ----
    workflow.add_node(vote_manager.get_name(), vote_manager.execute)

    # ---------------------------------------------------------
    # 2. Add edges for each agent
    # ---------------------------------------------------------
    for agent in agents:

        # Every agent starts from the beginning
        workflow.add_edge(START, agent.get_name())

        # -----------------------------------------------------
        # Add the conditional edges
        #
        # agent.is_continue must return one of:
        #    "vote_manager" or "agent_n.o"
        # -----------------------------------------------------
        workflow.add_conditional_edges(
            agent.get_name(),
            agent.is_continue,
            {
                False: vote_manager.get_name(),
                True: agent.get_name()
            }
        )
    
    # Add the conditional edges for vote_manager
    # If voting still happening, vote_manager continues.
    # Otherwise, vote_manager exits.
    workflow.add_conditional_edges(
        vote_manager.get_name(),
        vote_manager.is_continue,
        {
            True: vote_manager.get_name(),
            False: END
        }
    )

    return workflow.compile()

