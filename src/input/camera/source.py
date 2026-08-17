"""Abstract boundary for future hardware-synchronized stereo acquisition."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import StereoFramePair


class LiveStereoCameraSource(ABC):
    """Vendor-neutral live source to be implemented after hardware selection."""

    @abstractmethod
    def open(self) -> None:
        """Open both configured cameras without inferring device identities."""

    @abstractmethod
    def read(self) -> StereoFramePair:
        """Return one hardware-paired frame with timestamp provenance."""

    @abstractmethod
    def close(self) -> None:
        """Release acquisition resources."""
