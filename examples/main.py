import re
import random
import numpy as np
import json
from typing import Dict, Any
from io import StringIO

from langchain_ollama import ChatOllama

from src.graphstate import GraphState
from src.workflow import create_graph
from src.agents import Agent, Vote


# ===========================
#  SEEDING FOR REPRODUCIBILITY
# ===========================
SEED = 42
random.seed(SEED)
np.random.seed(SEED)


# ===========================
#  AGENT SETUP
# ===========================
NUMBER_OF_AGENTS = 3
agents = [
    Agent(ChatOllama(model="llama3.1"), num_agents=NUMBER_OF_AGENTS, rank=1),
    Agent(ChatOllama(model="gemma3:12b"), num_agents=NUMBER_OF_AGENTS, rank=2),
    Agent(ChatOllama(model="deepseek-r1"), num_agents=NUMBER_OF_AGENTS, rank=3),
]

vote_manager = Vote(agents=agents, method="approval")


# ===========================
#  INITIAL GRAPH STATE
# ===========================
# state: GraphState = {
#     "question": "What is the capital of France?",
#     "context": (
#         "Paris first became the capital of France in 508 AD under King Clovis I. "
#         "It lost this status for a time but regained it under Hugh Capet in 987, "
#         "with its position as the permanent capital becoming firmly established "
#         "under the Capetian dynasty."
#     ),
#     "winners": [f"agent_{i}" for i in range(1, len(agents) + 1)]
# }

state: GraphState = {
    "question": "Why do matadors wave red capes?",
    "context":  "",
    "winners": [f"agent_{i}" for i in range(1, len(agents) + 1)]
}


# ===========================
#  BUILD AND EXECUTE GRAPH
# ===========================
voting_graph = create_graph(agents, vote_manager)
voting_state = voting_graph.invoke(state)


# ===========================
#  FINAL ANSWER GENERATION
# ===========================
def generate_final_answer(voting_state: Dict[str, Any], agents: list[Agent], md_buffer: StringIO):
    """Pick the winning agent to generate final answer from other responses"""
    question = voting_state.get("question", "")
    context = voting_state.get("context", "")
    responses = voting_state.get("responses", {})
    vote_counts = voting_state.get("agent_scores", {})

    # 1. Determine Winning Agent
    max_votes = max(vote_counts.values())
    winners = [agent for agent, score in vote_counts.items() if score == max_votes]
    chosen_agent_name = random.choice(winners)

    # 2. Get the corresponding agent object
    agent_lookup = {f"agent_{a.rank}": a for a in agents}
    chosen_agent = agent_lookup[chosen_agent_name]
    chosen_agent_record = responses[chosen_agent_name]

    selection_log = (
        f"Selected Agent: {chosen_agent_name} "
        f"({chosen_agent.base_model.model_dump().get('model')}) "
        f"with {max_votes} votes"
    )
    md_buffer.write(f"\n## Winner Selection\n```\n{selection_log}\n```\n")

    # 3. Prepare summarization prompt
    other_responses = chosen_agent_record.get("other_responses", {})
    votes = chosen_agent_record.get("vote", {})
    formatted_responses = "\n\n"
    for agent_name, text in other_responses.items():
        approve = votes.get(agent_name, "")
        # print(approve)   # keep your debug print
        if approve != "approve":
            continue
        formatted_responses += f"{agent_name}: {text}\n"
    # print(formatted_responses)

    final_prompt = f"""
        You are the final evaluator.
        Question: {question}

        Context:
        {context}

        Other model responses:
        {formatted_responses}

        Produce the best single final answer. Keep it concise and accurate in one or two sentences.
        """.strip()

    # 4. Execute final LLM
    llm = chosen_agent.base_model
    result = llm.invoke(final_prompt)
    result_text = (
        result.content if hasattr(result, "content") else str(result)
    )
    # For - reasoning model - Remove <think>...</think> and return only actual response
    result_text = re.sub(r"<think>.*?</think>", "", result_text, flags=re.DOTALL)

    md_buffer.write("\n## Final Consolidated Answer\n")
    md_buffer.write("```\n" + result_text.strip() + "\n```\n")

    return result


# ===========================
#  WRITE TO MARKDOWN FILE
# ===========================
def write_output_to_markdown(final_state, final_result, filename="example_output.md"):
    md_buffer = StringIO()

    md_buffer.write("# Multi-Agent Voting Result\n\n")

    # Final state printed in JSON
    md_buffer.write("## Final State (JSON)\n```json\n")
    md_buffer.write(json.dumps(final_state, indent=4))
    md_buffer.write("\n```\n")

    # Generate final result and capture logs into same buffer
    generate_final_answer(final_state, agents, md_buffer)

    from pathlib import Path

    # Get the path to the project root (one level up from examples/)
    project_root = Path(__file__).parent.parent

    # Path to the docs folder
    docs_file = project_root / "docs" / filename
    print(project_root)
    # Open the file
    with open(docs_file, "w", encoding="utf-8") as f:

        f.write(md_buffer.getvalue())


# ===========================
#  RUN PIPELINE
# ===========================
final_result = write_output_to_markdown(voting_state, None)
print("Markdown output saved to final_output.md")
