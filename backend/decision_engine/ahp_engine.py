import numpy as np


class AHPEngine:
    RI = [0.0, 0.0, 0.58, 0.90, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49]

    @classmethod
    def calculate_weights(cls, matrix: list[list[float]]) -> list[float]:
        A = np.array(matrix, dtype=float)
        n = A.shape[0]
        row_products = np.prod(A, axis=1)
        weights = np.power(row_products, 1.0 / n)
        weights /= np.sum(weights)
        return weights.tolist()