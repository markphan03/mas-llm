import re
import random
import numpy as np
import json

from dotenv import load_dotenv
from typing import Dict, Any
from io import StringIO

from langchain_openai import OpenAIEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.graphstate import GraphState
from src.workflow import create_graph
from src.agents import Agent, Vote

from src.agents.AGENT_PROMPTS import SYSTEM_PROMPTS

import time

start = time.perf_counter()

# ===========================
#  SEEDING FOR REPRODUCIBILITY
# ===========================
load_dotenv()
SEED = 42
random.seed(SEED)
np.random.seed(SEED)


# ===========================
#  AGENT SETUP
# ===========================
embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
)
NUMBER_OF_AGENTS = 1
agents = [
    # Agent(ChatOllama(model="llama3.1", seed=SEED), embd_model=embeddings, num_agents=NUMBER_OF_AGENTS, rank=1),
    # Agent(ChatOllama(model="deepseek-r1", seed=SEED), embd_model=embeddings, num_agents=NUMBER_OF_AGENTS, rank=1),
    Agent(ChatOllama(model="mistral", seed=SEED), embd_model=embeddings, num_agents=NUMBER_OF_AGENTS, rank=1),
]


vote_manager = Vote(agents=agents, method="approval")


# ===========================
#  INITIAL GRAPH STATE
# ===========================
state: GraphState = {
    "question": "What is the capital of France?",
    "context": (
        "Paris first became the capital of France in 508 AD under King Clovis I. "
        "It lost this status for a time but regained it under Hugh Capet in 987, "
        "with its position as the permanent capital becoming firmly established "
        "under the Capetian dynasty."
    ),
    "example": "",
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
# def generate_final_answer(voting_state: Dict[str, Any], agents: list[Agent], md_buffer: StringIO):
#     """Pick the winning agent to generate final answer from other responses"""
#     question = voting_state.get("question", "")
#     context = voting_state.get("context", "")
#     responses = voting_state.get("responses", {})
#     vote_counts = voting_state.get("agent_scores", {})

#     # 1. Determine Winning Agent
#     max_votes = max(vote_counts.values())
#     winners = [agent for agent, score in vote_counts.items() if score == max_votes]
#     chosen_agent_name = random.choice(winners)

#     # 2. Get the corresponding agent object
#     agent_lookup = {f"agent_{a.rank}": a for a in agents}
#     chosen_agent = agent_lookup[chosen_agent_name]
#     chosen_agent_record = responses[chosen_agent_name]

#     selection_log = (
#         f"Selected Agent: {chosen_agent_name} "
#         f"({chosen_agent.base_model.model_dump().get('model')}) "
#         f"with {max_votes} votes"
#     )
#     md_buffer.write(f"\n## Winner Selection\n```\n{selection_log}\n```\n")

#     # 3. Prepare summarization prompt
#     other_responses = chosen_agent_record.get("other_responses", {})
#     votes = chosen_agent_record.get("vote", {})
#     formatted_responses = "\n\n"
#     for agent_name, text in other_responses.items():
#         approve = votes.get(agent_name, "")
#         # print(approve)   # keep your debug print
#         if approve != "approve":
#             continue
#         formatted_responses += f"{agent_name}: {text}\n"
#     # print(formatted_responses)

#     final_prompt = f"""
#         You are the final evaluator.
#         Question: {question}

#         Context:
#         {context}

#         Other model responses:
#         {formatted_responses}

#         Produce the best single final answer. Keep it concise and accurate in one or two sentences.
#         """.strip()

#     # 4. Execute final LLM
#     llm = chosen_agent.base_model
#     result = llm.invoke(final_prompt)
#     result_text = (
#         result.content if hasattr(result, "content") else str(result)
#     )
#     # For - reasoning model - Remove <think>...</think> and return only actual response
#     result_text = re.sub(r"<think>.*?</think>", "", result_text, flags=re.DOTALL)

#     md_buffer.write("\n## Final Consolidated Answer\n")
#     md_buffer.write("```\n" + result_text.strip() + "\n```\n")

#     return result


def generate_final_answer(state: GraphState, agents: list[Agent], md_buffer: StringIO):
    """
    When voting ends, choose the winning agent and summarize their
    approved peers' answers.
    """

    question = state.get("question", "")
    context = state.get("context", "")
    responses = state.get("responses", {})
    agent_scores = state.get("agent_scores", {})

    # ============================================================
    # SPECIAL CASE — Only one agent in the system
    # ============================================================
    if NUMBER_OF_AGENTS <= 1:
        only_agent = agents[0]
        raw_answer = only_agent.response or responses[only_agent.name]["response"]
        return re.sub(r"<think>.*?</think>", "", raw_answer, flags=re.DOTALL)

    # ============================================================
    # Multi-agent final selection
    # ============================================================
    max_votes = max(agent_scores.values())
    winners = [agent for agent, score in agent_scores.items() if score == max_votes]
    chosen_agent_name = winners[0] if len(winners) == 1 else random.choice(winners) 

    agent_lookup = {f"agent_{a.rank}": a for a in agents}
    chosen_agent = agent_lookup[chosen_agent_name]
    chosen_agent_record = responses[chosen_agent_name]
    
    selection_log = (
        f"Selected Agent: {chosen_agent_name} "
        f"({chosen_agent.base_model.model_dump().get('model')}) "
        f"with {max_votes} votes"
    )
    md_buffer.write(f"\n## Winner Selection\n```\n{selection_log}\n```\n")

    response = chosen_agent_record.get("response", "")
    other_responses = chosen_agent_record.get("other_responses", {})
    
    votes = chosen_agent_record.get("vote", {}) or {}

    formatted_responses = "\n\n"
    for agent_name, text in other_responses.items():
        if votes.get(agent_name).get("decision") == "approve":
            formatted_responses += f"{agent_name}: {text}\n"

    final_prompt = ChatPromptTemplate.from_template(
        SYSTEM_PROMPTS["summarization"]
    )

    llm = final_prompt | chosen_agent.base_model | StrOutputParser()
    raw_result = llm.invoke({
        "question": question,
        "context": context,
        "response": response,
        "formatted_responses": formatted_responses
    })

    result_text = (
        raw_result.content if hasattr(raw_result, "content") else str(raw_result)
    )

        # For - reasoning model - Remove <think>...</think> and return only actual response
    result_text = re.sub(r"<think>.*?</think>", "", result_text, flags=re.DOTALL)

    md_buffer.write("\n## Final Consolidated Answer\n")
    md_buffer.write("```\n" + result_text.strip() + "\n```\n")

    return raw_result



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

    end = time.perf_counter()
    elapsed = end - start  # seconds (float)

    minutes = int(elapsed // 60)
    seconds = elapsed % 60

    print(f"Time: {minutes}:{seconds:05.2f}")
    md_buffer.write(f"Time: {minutes}:{seconds:05.2f}")
    md_buffer.write("\n```\n")

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
