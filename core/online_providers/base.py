"""Base class and result types for online reference-library providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class OnlineSearchResult:
    """One candidate returned by an online provider."""

    candidate_id: str
    candidate_name: str
    provider: str
    analysis_type: str
    source_url: str = ""
    attribution: str = ""

    # For spectral providers (FTIR / RAMAN):
    axis: list[float] = field(default_factory=list)
    signal: list[float] = field(default_factory=list)

    # For XRD providers:
    peaks: list[dict[str, float]] = field(default_factory=list)

    # Extra metadata
    formula: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_reference_entry(self) -> dict[str, Any]:
        """Convert to the dict format expected by batch_runner reference matching."""
        import numpy as np

        base: dict[str, Any] = {
            "candidate_id": self.candidate_id,
            "candidate_name": self.candidate_name,
            "provider": self.provider,
            "package_id": f"online_{self.provider.lower().replace(' ', '_')}",
            "package_version": "live",
            "attribution": self.attribution,
            "source_url": self.source_url,
            "priority": 0,
        }
        if self.axis and self.signal:
            base["axis"] = np.asarray(self.axis, dtype=float)
            base["signal"] = np.asarray(self.signal, dtype=float)
        if self.peaks:
            base["peaks"] = list(self.peaks)
        if self.formula:
            base["formula"] = self.formula
        if self.extra:
            base.update(self.extra)
        return base


@runtime_checkable
class OnlineProvider(Protocol):
    """Contract for an online reference-library provider."""

    provider_id: str
    provider_name: str
    supported_analysis_types: tuple[str, ...]

    def search_by_spectrum(
        self,
        analysis_type: str,
        axis: list[float],
        signal: list[float],
        *,
        top_n: int = 10,
    ) -> list[OnlineSearchResult]:
        """Search by spectrum signal (FTIR / RAMAN)."""
        ...

    def search_by_peaks(
        self,
        analysis_type: str,
        peaks: list[dict[str, float]],
        *,
        top_n: int = 10,
        tolerance_deg: float = 0.3,
    ) -> list[OnlineSearchResult]:
        """Search by peak positions (XRD)."""
        ...

    def is_available(self) -> bool:
        """Check if the provider is properly configured and reachable."""
        ...
