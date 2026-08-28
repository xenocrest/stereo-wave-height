"""Local spatial surface-completion experiments on frozen WASS observations."""

from .mls import HoldoutResult, evaluate_holdout, quadratic_mls_predict

__all__ = ["HoldoutResult", "evaluate_holdout", "quadratic_mls_predict"]
