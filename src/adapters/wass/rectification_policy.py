"""Configuration model for WASS fixed-calibration rectification policy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


CALIB_ZERO_DISPARITY = 1024


@dataclass(frozen=True)
class RectificationPolicy:
    """One immutable OpenCV stereo-rectification policy.

    ``alpha`` and ``zero_disparity`` affect rectification only.  They never
    alter camera intrinsics, distortion coefficients, or stereo extrinsics.
    """

    alpha: float = 1.0
    zero_disparity: bool = False
    test_id: str = "DEFAULT"

    def __post_init__(self) -> None:
        if isinstance(self.alpha, bool) or not isinstance(self.alpha, (int, float)):
            raise TypeError("rectification alpha must be a number")
        if not self.test_id or not 0.0 <= float(self.alpha) <= 1.0:
            raise ValueError("rectification policy requires an id and alpha in [0,1]")
        if not isinstance(self.zero_disparity, bool):
            raise TypeError("zero_disparity must be boolean")

    @property
    def flags(self) -> int:
        """Return the OpenCV flag value derived from ``zero_disparity``."""
        return CALIB_ZERO_DISPARITY if self.zero_disparity else 0

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], *, test_id: str = "CONFIGURED") -> "RectificationPolicy":
        """Parse the ``rectification`` mapping without implicit coercion."""
        if not isinstance(value, Mapping):
            raise TypeError("rectification policy must be a mapping")
        allowed = {"alpha", "zero_disparity"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown rectification policy fields: {sorted(unknown)}")
        return cls(
            alpha=value.get("alpha", 1.0),
            zero_disparity=value.get("zero_disparity", False),
            test_id=test_id,
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RectificationPolicy":
        """Load a policy from the experiment YAML schema."""
        candidate: str | None = None
        alpha: float | None = None
        zero_disparity: bool | None = None
        in_rectification = False
        for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
            line = raw_line.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            if not line.startswith(" "):
                in_rectification = line == "rectification:"
                if line.startswith("candidate:"):
                    candidate = line.split(":", 1)[1].strip()
                continue
            if in_rectification:
                key, separator, raw_value = line.strip().partition(":")
                if not separator:
                    raise ValueError("invalid rectification policy YAML line")
                value = raw_value.strip()
                if key == "alpha":
                    alpha = float(value)
                elif key == "zero_disparity":
                    if value not in {"true", "false"}:
                        raise ValueError("zero_disparity must be true or false")
                    zero_disparity = value == "true"
                else:
                    raise ValueError(f"unknown rectification policy field: {key}")
        if candidate != "FULL_CALIBRATION":
            raise ValueError("rectification policy is restricted to FULL_CALIBRATION")
        mapping: dict[str, Any] = {}
        if alpha is not None:
            mapping["alpha"] = alpha
        if zero_disparity is not None:
            mapping["zero_disparity"] = zero_disparity
        return cls.from_mapping(mapping, test_id=candidate)

    def wass_config_lines(self) -> tuple[str, str]:
        """Return the two lines consumed by the policy-capable WASS runtime."""
        boolean = "true" if self.zero_disparity else "false"
        return (
            f"RECTIFICATION_ALPHA={float(self.alpha):g}",
            f"RECTIFICATION_ZERO_DISPARITY={boolean}",
        )


CANDIDATE_A_POLICY_MATRIX = (
    RectificationPolicy(0.0, True, "A0"),
    RectificationPolicy(0.5, True, "A1"),
    RectificationPolicy(1.0, True, "A2"),
    RectificationPolicy(0.0, False, "A3"),
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
