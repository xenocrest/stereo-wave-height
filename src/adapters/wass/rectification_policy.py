"""Fail-fast capability model for WASS rectification-policy experiments."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RectificationPolicy:
    """One immutable OpenCV stereo-rectification policy."""

    test_id: str
    alpha: float
    zero_disparity: bool

    def __post_init__(self) -> None:
        if not self.test_id or not 0.0 <= self.alpha <= 1.0:
            raise ValueError("rectification policy requires an id and alpha in [0,1]")


CANDIDATE_A_POLICY_MATRIX = (
    RectificationPolicy("A0", 0.0, True),
    RectificationPolicy("A1", 0.5, True),
    RectificationPolicy("A2", 1.0, True),
    RectificationPolicy("A3", 0.0, False),
)


@dataclass(frozen=True)
class ProductionWassRectificationCapability:
    """Observed WASS 1.11 policy, which is compiled rather than configured."""

    alpha: float = 1.0
    zero_disparity: bool = False
    runtime_policy_configurable: bool = False

    def supports(self, policy: RectificationPolicy) -> bool:
        """Return true only when the requested policy equals the compiled policy."""
        return (
            self.runtime_policy_configurable
            or (policy.alpha == self.alpha and policy.zero_disparity == self.zero_disparity)
        )

    def require_supported(self, policy: RectificationPolicy) -> None:
        """Reject unsupported tests instead of silently changing K/D/R/T or WASS."""
        if not self.supports(policy):
            raise RuntimeError(
                f"rectification policy {policy.test_id} is unsupported by the production "
                "WASS runtime interface; do not emulate it by changing calibration parameters"
            )
