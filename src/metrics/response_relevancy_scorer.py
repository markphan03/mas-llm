import numpy as np
from langchain_core.embeddings import Embeddings


class ResponseRelevancyScorer():
    def __init__(self, embd_model: Embeddings):
        self.embd_model = embd_model
    
    def embed_text(self, text):
        return self.embd_model.embed_documents(text)
    
    def cosine_similarity(self, vec1, vec2):
        dot_prod = (vec1 @ vec2.T)
        norm_prod = (np.linalg.norm(vec1, axis=1, keepdims=True) * np.linalg.norm(vec2, axis=1, keepdims=True).T)
        cosine_matrix = dot_prod / norm_prod
        score = cosine_matrix.mean()
        return score

    def calculate_response_relevancy(self, question: str, correct_example: str, response: str): # In evaluation, context could be gold answer
        vec_qc = self.embed_text(question + "\n\n" + correct_example)
        vec_res = self.embed_text(response)
        return self.cosine_similarity(np.array(vec_qc), np.array(vec_res))