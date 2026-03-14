"""Online provider registry and engine orchestrator."""

from __future__ import annotations

import logging
import os
from typing import Any

from core.online_providers.base import OnlineProvider, OnlineSearchResult

logger = logging.getLogger(__name__)

_PROVIDERS: dict[str, OnlineProvider] = {}
_ENGINE_INSTANCE: OnlineLibraryEngine | None = None


def online_search_enabled() -> bool:
    """Check if online search is enabled via environment variable."""
    return os.getenv("THERMOANALYZER_ONLINE_SEARCH", "true").strip().lower() in {"true", "1", "yes", "on"}


def register_provider(provider: OnlineProvider) -> None:
    """Register an online provider."""
    _PROVIDERS[provider.provider_id] = provider


def get_online_engine() -> OnlineLibraryEngine:
    """Get or create the singleton online library engine."""
    global _ENGINE_INSTANCE
    if _ENGINE_INSTANCE is None:
        _ENGINE_INSTANCE = OnlineLibraryEngine()
        _auto_register_providers()
    return _ENGINE_INSTANCE


def _auto_register_providers() -> None:
    """Auto-register all built-in providers."""
    try:
        from core.online_providers.mp_provider import MaterialsProjectProvider
        mp = MaterialsProjectProvider()
        if mp.is_available():
            register_provider(mp)
            logger.info("Registered Materials Project online provider")
    except Exception as exc:
        logger.debug("Materials Project provider not available: %s", exc)

    try:
        from core.online_providers.cod_provider import CODProvider
        cod = CODProvider()
        if cod.is_available():
            register_provider(cod)
            logger.info("Registered COD online provider")
    except Exception as exc:
        logger.debug("COD provider not available: %s", exc)

    try:
        from core.online_providers.rruff_provider import RRUFFProvider
        rruff = RRUFFProvider()
        if rruff.is_available():
            register_provider(rruff)
            logger.info("Registered RRUFF online provider")
    except Exception as exc:
        logger.debug("RRUFF provider not available: %s", exc)


class OnlineLibraryEngine:
    """Orchestrates queries across registered online providers."""

    def __init__(self) -> None:
        self._cache: dict[str, list[OnlineSearchResult]] = {}

    @property
    def providers(self) -> dict[str, OnlineProvider]:
        return dict(_PROVIDERS)

    def provider_status(self) -> list[dict[str, Any]]:
        """Return availability status for all providers."""
        rows: list[dict[str, Any]] = []
        for pid, provider in _PROVIDERS.items():
            try:
                available = provider.is_available()
            except Exception:
                available = False
            rows.append({
                "provider_id": pid,
                "provider_name": provider.provider_name,
                "available": available,
                "analysis_types": list(provider.supported_analysis_types),
            })
        return rows

    def search_references(
        self,
        analysis_type: str,
        *,
        axis: list[float] | None = None,
        signal: list[float] | None = None,
        peaks: list[dict[str, float]] | None = None,
        top_n: int = 10,
        tolerance_deg: float = 0.3,
    ) -> list[OnlineSearchResult]:
        """Query all registered providers and return merged results."""
        if not online_search_enabled():
            return []

        token = analysis_type.upper()
        results: list[OnlineSearchResult] = []

        for provider in _PROVIDERS.values():
            if token not in provider.supported_analysis_types:
                continue
            try:
                if token in {"FTIR", "RAMAN"} and axis and signal:
                    hits = provider.search_by_spectrum(
                        token, axis, signal, top_n=top_n
                    )
                    results.extend(hits)
                elif token == "XRD" and peaks:
                    hits = provider.search_by_peaks(
                        token, peaks, top_n=top_n, tolerance_deg=tolerance_deg
                    )
                    results.extend(hits)
            except Exception as exc:
                logger.warning("Online provider %s failed: %s", provider.provider_id, exc)
                continue

        return results[:top_n * 3]  # Return more than needed, let matcher rank

    def search_as_reference_entries(
        self,
        analysis_type: str,
        *,
        axis: list[float] | None = None,
        signal: list[float] | None = None,
        peaks: list[dict[str, float]] | None = None,
        top_n: int = 10,
        tolerance_deg: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Search and convert results to batch_runner-compatible reference entries."""
        results = self.search_references(
            analysis_type,
            axis=axis,
            signal=signal,
            peaks=peaks,
            top_n=top_n,
            tolerance_deg=tolerance_deg,
        )
        return [r.to_reference_entry() for r in results]
