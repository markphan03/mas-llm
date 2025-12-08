# Install dependencies if needed
# !pip install langchain ragas nest_asyncio

import nest_asyncio
import asyncio
from langchain_ollama import ChatOllama
from ragas.metrics.collections import BleuScore

# Allow async in Jupyter
nest_asyncio.apply()

# -----------------------------
# Ollama Chat model via LangChain
# -----------------------------
llm = ChatOllama(model="llama3.1", temperature=0.0)

# -----------------------------
# Async Ragas BLEU evaluation
# -----------------------------
def eval_bleu(reference: str, query: str):
    """
    Evaluate Ollama response against reference using Ragas BLEU
    """
    prompt = f"Answer this question:\n{query}\nAnswer:"

    # Use LangChain ChatOllama to get response
    response = llm.predict(prompt)

    scorer = BleuScore()
    result = scorer.ascore(
        reference=reference,
        response=response
    )

    print("Query:", query)
    print("Reference:", reference)
    print("Generated:", response)
    print("BLEU Score:", result.value)
    print("-" * 50)

    return result.value

# -----------------------------
# Example usage
# -----------------------------
query = "Where is the Eiffel Tower located?"
reference = "The Eiffel Tower is located in Paris."

bleu_score = eval_bleu(reference, query)
bleu_score