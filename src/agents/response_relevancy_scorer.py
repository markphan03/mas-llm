import json
from openai import AsyncOpenAI
from ragas.metrics.result import MetricResult
from ragas.llms import llm_factory
from ragas.embeddings.base import embedding_factory
from ragas.metrics.collections import AnswerRelevancy

### TODO: Inefficient for future development - processing entire dataset - should only process 1 data only

class ResponseRelevancyScorer():
    def __init__(self, llm: str, embedding: str, **kwargs):
        client = AsyncOpenAI()
        self.llm = llm_factory(llm, client=client)
        self.embeddings = embedding_factory("openai", model=embedding, client=client)
        self.scorer = AnswerRelevancy(llm=self.llm, embeddings=self.embeddings)
    
    async def cal_response_relevancy(self, gen_dataset: list, save_path: str = None) -> float:
        """
            Compute the Answer Relevancy score between a user input and a model response.

            The **Answer Relevancy** metric measures how well a response aligns with the
            original user input. It ranges from 0 to 1, with higher scores indicating that
            the response directly and appropriately addresses the user's intent. This metric
            focuses on relevance rather than factual correctness and penalizes responses that
            are incomplete, off-topic, or overly verbose.

            The metric is computed using the following procedure:

            1. **Generate artificial questions** (default: N = 3) based on the model response.
            These generated questions are designed to reflect the content of the response.

            2. **Embed both the user input and the generated questions.**
            Let:
                - E_o  = embedding of the user input
                - E_gi = embedding of the i-th generated question

            3. **Compute cosine similarity** between E_o and each E_gi.

            4. **Average the similarities** to obtain the final Answer Relevancy score:

                Answer Relevancy = (1 / N) * Σ cosine_similarity(E_gi, E_o)

                Or explicitly:

                    Answer Relevancy = (1 / N) * Σ [ (E_gi · E_o) / (||E_gi|| * ||E_o||) ]

            Parameters
            ----------
            user_input : str
                The original user query + factual answer.
            response : str
                The model's generated answer.

            Returns
            -------
            float
                The Mean of Answer Relevancy score. While typically within the range [0, 1],
                cosine similarity can theoretically range from -1 to 1.

            Notes
            -----
            - N is the number of generated questions (default is 3, configurable via a
            `strictness` parameter in some implementations).
            - This metric evaluates *relevance*, not factual accuracy.
        """
        relevant_scores = []
        for data in gen_dataset:
            id = data["id"]
            question = data["question"]
            gold_answer = data["gold_answer"]
            pred_answer = data["pred_answer"]

            score = await self.scorer.ascore(
                user_input= question + "\n\n" + gold_answer,
                response=pred_answer
            )
            score = score.value
            
            relevant_scores.append(score)
            data["relevant_score"] = score
            print(f"Sample {id} - Relevancy Score {score}")

        # Save updated JSON if requested
        if save_path is not None:
            with open(save_path, "w") as f:
                json.dump(gen_dataset, f, indent=4)
        return sum(relevant_scores) / len(relevant_scores)
    
    