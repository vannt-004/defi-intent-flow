import numpy as np


class AHPEngine:
    RI = {
        1: 0.0,
        2: 0.0,
        3: 0.58,
        4: 0.90,
        5: 1.12,
        6: 1.24,
        7: 1.32,
        8: 1.41,
        9: 1.45,
        10: 1.49,
    }

    @classmethod
    def calculate_weights(cls, matrix: list[list[float]]) -> list[float]:
        A = np.array(matrix, dtype=float)
        cls._validate_matrix(A)
        n = A.shape[0]
        row_products = np.prod(A, axis=1)
        weights = np.power(row_products, 1.0 / n)
        weights /= np.sum(weights)
        return weights.tolist()

    @classmethod
    def consistency_report(
        cls,
        matrix: list[list[float]],
        weights: list[float] | None = None,
    ) -> dict[str, float]:
        A = np.array(matrix, dtype=float)
        cls._validate_matrix(A)
        n = A.shape[0]
        W = np.array(weights if weights is not None else cls.calculate_weights(matrix))
        weighted_sum = A @ W
        lambda_max = float(np.mean(weighted_sum / W))
        ci = float((lambda_max - n) / (n - 1)) if n > 1 else 0.0
        ri = cls.RI.get(n, cls.RI[10])
        cr = float(ci / ri) if ri > 0 else 0.0
        return {
            "lambda_max": lambda_max,
            "ci": ci,
            "cr": cr,
        }

    @classmethod
    def ensure_consistent(cls, matrix: list[list[float]], threshold: float = 0.10) -> dict[str, float]:
        report = cls.consistency_report(matrix)
        if report["cr"] > threshold:
            raise ValueError(
                f"AHP comparison matrix is inconsistent: CR={report['cr']:.4f} > {threshold:.2f}"
            )
        return report

    @staticmethod
    def _validate_matrix(A: np.ndarray) -> None:
        if A.ndim != 2 or A.shape[0] != A.shape[1]:
            raise ValueError("AHP comparison matrix must be square")
        if np.any(A <= 0):
            raise ValueError("AHP comparison matrix values must be positive")
