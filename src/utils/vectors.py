import numpy as np


def cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    query = query / np.linalg.norm(query)
    matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix @ query
