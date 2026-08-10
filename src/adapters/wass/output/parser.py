"""Version-specific WASS output parser contract.

No raw WASS field is assumed here. Each verified WASS/gridder version may
provide a parser that declares its own ``format_id`` and returns the canonical
project structure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from .model import StandardizedGrid3D


@runtime_checkable
class WassOutputParser(Protocol):
    """Contract for a verified, version-specific WASS output parser."""

    format_id: str

    def parse(self, source: Path) -> StandardizedGrid3D:
        """Parse ``source`` without guessing unknown fields, units, or axes."""
        ...
