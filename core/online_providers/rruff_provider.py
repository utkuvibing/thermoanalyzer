"""RRUFF online provider — mineral Raman spectra via RamanSPy or direct download."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.online_providers.base import OnlineProvider, OnlineSearchResult

logger = logging.getLogger(__name__)

RRUFF_DOWNLOAD_BASE = "https://rruff.info/zipped_data_files"


class RRUFFProvider:
    """Access RRUFF mineral Raman spectra for matching."""

    provider_id = "rruff"
    provider_name = "RRUFF"
    supported_analysis_types = ("RAMAN",)

    def __init__(self) -> None:
        self._cached_spectra: list[dict[str, Any]] | None = None

    def is_available(self) -> bool:
        """RRUFF is available if httpx is installed (for direct download)."""
        try:
            import httpx
            return True
        except ImportError:
            return False

    def search_by_spectrum(
        self,
        analysis_type: str,
        axis: list[float],
        signal: list[float],
        *,
        top_n: int = 10,
    ) -> list[OnlineSearchResult]:
        """Search RRUFF by spectrum similarity — uses pre-loaded cache if available."""
        if not axis or not signal:
            return []

        spectra = self._load_cached_spectra()
        if not spectra:
            logger.info("RRUFF spectra cache is empty — run bulk ingest to populate")
            return []

        import numpy as np

        obs_axis = np.asarray(axis, dtype=float)
        obs_signal = np.asarray(signal, dtype=float)
        obs_norm = float(np.linalg.norm(obs_signal))
        if obs_norm == 0:
            return []
        obs_unit = obs_signal / obs_norm

        scored: list[tuple[float, dict[str, Any]]] = []
        for entry in spectra:
            try:
                ref_axis = np.asarray(entry["axis"], dtype=float)
                ref_signal = np.asarray(entry["signal"], dtype=float)
                # Interpolate reference to observed axis
                interp_signal = np.interp(obs_axis, ref_axis, ref_signal)
                ref_norm = float(np.linalg.norm(interp_signal))
                if ref_norm == 0:
                    continue
                ref_unit = interp_signal / ref_norm
                cosine = float(np.dot(obs_unit, ref_unit))
                scored.append((cosine, entry))
            except Exception:
                continue

        scored.sort(key=lambda x: -x[0])
        results: list[OnlineSearchResult] = []
        for score, entry in scored[:top_n]:
            # Convert numpy arrays to plain lists for dataclass fields
            entry_axis = entry.get("axis", [])
            entry_signal = entry.get("signal", [])
            if hasattr(entry_axis, "tolist"):
                entry_axis = entry_axis.tolist()
            if hasattr(entry_signal, "tolist"):
                entry_signal = entry_signal.tolist()
            results.append(OnlineSearchResult(
                candidate_id=str(entry.get("candidate_id", "")),
                candidate_name=str(entry.get("candidate_name", "")),
                provider=self.provider_name,
                analysis_type="RAMAN",
                source_url=str(entry.get("source_url", "")),
                attribution="RRUFF Project - https://rruff.info",
                axis=list(entry_axis) if entry_axis else [],
                signal=list(entry_signal) if entry_signal else [],
                formula=str(entry.get("formula", "")),
                extra={"cosine_score": round(score, 4)},
            ))
        return results

    def search_by_peaks(
        self,
        analysis_type: str,
        peaks: list[dict[str, float]],
        *,
        top_n: int = 10,
        tolerance_deg: float = 0.3,
    ) -> list[OnlineSearchResult]:
        return []  # Raman provider — peak search not applicable

    def _load_cached_spectra(self) -> list[dict[str, Any]]:
        """Load cached RRUFF spectra from installed library packages."""
        if self._cached_spectra is not None:
            return self._cached_spectra

        try:
            from core.reference_library import get_reference_library_manager
            manager = get_reference_library_manager()
            entries = manager.load_entries("RAMAN")
            self._cached_spectra = [
                e for e in entries
                if str(e.get("provider", "")).upper() in {"RRUFF", "ROD"}
            ]
        except Exception:
            self._cached_spectra = []

        return self._cached_spectra
