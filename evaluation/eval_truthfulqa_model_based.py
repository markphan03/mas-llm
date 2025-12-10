import json
import random
import numpy as np
import asyncio
import time

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from src import TruthfulGrader, ResponseRelevancyScorer

load_dotenv()

# -----------------------------------------------------------
# Utilities
# -----------------------------------------------------------
def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)

def load_records(path: str, limit: int = None):
    with open(path, "r") as f:
        data = json.load(f)
    return data if limit is None else data[:limit]

# -----------------------------------------------------------
# Main
# -----------------------------------------------------------
async def main():
    set_seed(42)

    filepath = "docs/llama3.1_truthfulqa_results.json"
    llm = "gpt-4o-mini"
    embedding = "text-embedding-3-small"
    records = load_records(filepath)

    truthful_scorer = TruthfulGrader(base_model=ChatOpenAI(model=llm))
    truthful_score = truthful_scorer.calculate_truthful_accuracy(records, save_path=filepath)
    # response_relevancy_scorer = ResponseRelevancyScorer(llm, embedding)

    # print(f"[{time.time():.2f}] Starting parallel tasks...")

    # -------------------------------------------------------
    # Add debug print wrappers to detect parallelism
    # -------------------------------------------------------

    # async def run_truthful():
    #     print(f"[{time.time():.2f}] TruthfulGrader START")
    #     result = await asyncio.to_thread(
    #         truthful_scorer.calculate_truthful_accuracy,
    #         records,
    #         filepath,
    #     )
    #     print(f"[{time.time():.2f}] TruthfulGrader END")
    #     return result

    # async def run_relevancy():
    #     print(f"[{time.time():.2f}] ResponseRelevancy START")
    #     result = await response_relevancy_scorer.cal_response_relevancy(
    #         records, save_path=filepath
    #     )
    #     print(f"[{time.time():.2f}] ResponseRelevancy END")
    #     return result

    # # -------------------------------------------------------
    # # Execute them simultaneously
    # # -------------------------------------------------------
    # truthful_score, relevancy_score = await asyncio.gather(
    #     run_truthful(),
    #     run_relevancy(),
    # )

    # print(f"[{time.time():.2f}] All tasks finished.")
    print("Truthful accuracy:", truthful_score)
    # print("Response Relevancy Score:", relevancy_score)

# -----------------------------------------------------------
# Entry point
# -----------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
