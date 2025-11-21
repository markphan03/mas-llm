from langgraph.graph import StateGraph, START, END
from agents.agent import Agent

from graphstate import GraphState


def create_graph(
    agents: list[Agent],
):
    workflow = StateGraph(GraphState)

    # create agents (LLM nodes)
    for agent in agents:
        workflow.add_node(agent.get_name(), agent.execute)



    for agent in agents:
        workflow.add_edge(START, agent.get_name())
        for other_model in agents:
            if agent != other_model:
                print(f"Connect {agent.get_name()} with {other_model.get_name()}")   
                # workflow.add_edge(agent.get_name(), other_model.get_name())

        workflow.add_conditional_edges(
            agent.get_name(),
            agent.is_done,
            {
                True: END,
                False: agent.get_name()
            },
        )
        # workflow.add_edge(agent.get_name(), END)

        
            

        
   

    return workflow.compile()
