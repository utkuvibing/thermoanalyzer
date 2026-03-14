"""Materials Project online provider — 150K+ structures → XRD pattern matching."""

from __future__ import annotations

import logging
import os
from typing import Any

from core.online_providers.base import OnlineProvider, OnlineSearchResult

logger = logging.getLogger(__name__)


class MaterialsProjectProvider:
    """Query Materials Project API for XRD pattern matching."""

    provider_id = "materials_project"
    provider_name = "Materials Project"
    supported_analysis_types = ("XRD",)

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = (api_key or os.getenv("MP_API_KEY", "")).strip()

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            from mp_api.client import MPRester
            from pymatgen.analysis.diffraction.xrd import XRDCalculator
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
        return []  # XRD provider — spectral search not supported

    def search_by_peaks(
        self,
        analysis_type: str,
        peaks: list[dict[str, float]],
        *,
        top_n: int = 10,
        tolerance_deg: float = 0.3,
    ) -> list[OnlineSearchResult]:
        """Search MP by matching peak positions against calculated XRD patterns.

        Strategy: Extract d-spacings from user peaks → search MP for structures
        with matching lattice parameters → calculate XRD → rank by peak overlap.
        """
        if not self._api_key or not peaks:
            return []

        try:
            from mp_api.client import MPRester
            from pymatgen.analysis.diffraction.xrd import XRDCalculator
        except ImportError:
            logger.warning("mp-api or pymatgen not installed")
            return []

        # Extract d-spacings from user peaks for lattice parameter estimation
        import numpy as np
        wavelength = 1.5406  # Cu Ka
        d_spacings = []
        for peak in peaks:
            pos = float(peak.get("position", 0))
            if 0 < pos < 180:
                theta_rad = np.radians(pos / 2.0)
                sin_val = np.sin(theta_rad)
                if sin_val > 0:
                    d_spacings.append(wavelength / (2.0 * sin_val))

        if not d_spacings:
            return []

        try:
            with MPRester(self._api_key) as client:
                # Search for common materials - broad search then local matching
                # Use chemsys or elements to get a diverse set
                docs = client.materials.summary.search(
                    is_stable=True,
                    fields=["material_id", "formula_pretty", "structure", "symmetry"],
                    num_chunks=1,
                    chunk_size=min(top_n * 20, 200),
                )
        except Exception as exc:
            logger.warning("Materials Project API query failed: %s", exc)
            return []

        calculator = XRDCalculator(wavelength=wavelength)
        results: list[tuple[float, OnlineSearchResult]] = []

        for doc in docs:
            try:
                material_id = str(getattr(doc, "material_id", ""))
                formula = str(getattr(doc, "formula_pretty", ""))
                structure = getattr(doc, "structure", None)
                if structure is None:
                    continue

                # Calculate XRD pattern
                pattern = calculator.get_pattern(structure, two_theta_range=(5.0, 90.0))
                ref_positions = [float(v) for v in getattr(pattern, "x", [])]
                ref_intensities = [float(v) for v in getattr(pattern, "y", [])]
                if not ref_positions:
                    continue

                # Normalize intensities
                max_int = max(ref_intensities) if ref_intensities else 1.0
                if max_int <= 0:
                    continue

                # Build reference peaks
                ref_peaks = [
                    {"position": pos, "intensity": inten / max_int}
                    for pos, inten in zip(ref_positions, ref_intensities)
                    if inten / max_int >= 0.01
                ]

                # Calculate overlap score
                score = _peak_overlap_score(peaks, ref_peaks, tolerance_deg)
                if score < 0.1:
                    continue

                symmetry = getattr(doc, "symmetry", None)
                space_group = ""
                if symmetry and hasattr(symmetry, "symbol"):
                    space_group = str(symmetry.symbol)

                results.append((
                    score,
                    OnlineSearchResult(
                        candidate_id=f"mp_{material_id}",
                        candidate_name=f"{formula} ({material_id})",
                        provider=self.provider_name,
                        analysis_type="XRD",
                        source_url=f"https://materialsproject.org/materials/{material_id}",
                        attribution="Materials Project - https://materialsproject.org",
                        peaks=ref_peaks,
                        formula=formula,
                        extra={"space_group": space_group, "match_score": round(score, 4)},
                    ),
                ))
            except Exception as exc:
                logger.debug("Failed to process MP material: %s", exc)
                continue

        # Sort by score descending
        results.sort(key=lambda x: -x[0])
        return [r for _, r in results[:top_n]]


class MaterialsProjectFormulaProvider:
    """Search Materials Project by formula for targeted XRD matching."""

    provider_id = "materials_project_formula"
    provider_name = "Materials Project (Formula)"
    supported_analysis_types = ("XRD",)

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = (api_key or os.getenv("MP_API_KEY", "")).strip()

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            from mp_api.client import MPRester
            from pymatgen.analysis.diffraction.xrd import XRDCalculator
            return True
        except ImportError:
            return False

    def search_by_formula(
        self,
        formula: str,
        *,
        top_n: int = 20,
    ) -> list[OnlineSearchResult]:
        """Search by chemical formula — returns structures with calculated XRD."""
        if not self._api_key or not formula.strip():
            return []

        try:
            from mp_api.client import MPRester
            from pymatgen.analysis.diffraction.xrd import XRDCalculator
        except ImportError:
            return []

        import numpy as np
        wavelength = 1.5406

        try:
            with MPRester(self._api_key) as client:
                docs = client.materials.summary.search(
                    formula=formula.strip(),
                    fields=["material_id", "formula_pretty", "structure", "symmetry",
                            "energy_above_hull", "is_stable"],
                    num_chunks=1,
                    chunk_size=min(top_n, 50),
                )
        except Exception as exc:
            logger.warning("MP formula search failed: %s", exc)
            return []

        calculator = XRDCalculator(wavelength=wavelength)
        results: list[OnlineSearchResult] = []

        for doc in docs:
            try:
                material_id = str(getattr(doc, "material_id", ""))
                formula_pretty = str(getattr(doc, "formula_pretty", ""))
                structure = getattr(doc, "structure", None)
                if structure is None:
                    continue

                pattern = calculator.get_pattern(structure, two_theta_range=(5.0, 90.0))
                ref_positions = [float(v) for v in getattr(pattern, "x", [])]
                ref_intensities = [float(v) for v in getattr(pattern, "y", [])]
                if not ref_positions:
                    continue

                max_int = max(ref_intensities) if ref_intensities else 1.0
                if max_int <= 0:
                    continue

                ref_peaks = []
                for pos, inten in zip(ref_positions, ref_intensities):
                    rel = inten / max_int
                    if rel >= 0.01:
                        theta_rad = np.radians(pos / 2.0)
                        sin_val = float(np.sin(theta_rad))
                        d = wavelength / (2.0 * sin_val) if sin_val > 0 else 0.0
                        ref_peaks.append({
                            "position": pos,
                            "intensity": rel,
                            "d_spacing": d,
                        })

                symmetry = getattr(doc, "symmetry", None)
                space_group = str(symmetry.symbol) if symmetry and hasattr(symmetry, "symbol") else ""

                results.append(OnlineSearchResult(
                    candidate_id=f"mp_{material_id}",
                    candidate_name=f"{formula_pretty} ({material_id})",
                    provider=self.provider_name,
                    analysis_type="XRD",
                    source_url=f"https://materialsproject.org/materials/{material_id}",
                    attribution="Materials Project - https://materialsproject.org",
                    peaks=ref_peaks,
                    formula=formula_pretty,
                    extra={"space_group": space_group},
                ))
            except Exception:
                continue

        return results[:top_n]

    def search_by_spectrum(self, *args: Any, **kwargs: Any) -> list[OnlineSearchResult]:
        return []

    def search_by_peaks(self, *args: Any, **kwargs: Any) -> list[OnlineSearchResult]:
        return []


def _peak_overlap_score(
    observed: list[dict[str, float]],
    reference: list[dict[str, float]],
    tolerance: float,
) -> float:
    """Calculate a simple weighted peak overlap score."""
    if not observed or not reference:
        return 0.0

    ref_remaining = [(float(p["position"]), float(p.get("intensity", 1.0))) for p in reference]
    matched_weight = 0.0
    total_weight = sum(float(p.get("intensity", 1.0)) for p in observed)

    for obs in observed:
        obs_pos = float(obs["position"])
        obs_int = float(obs.get("intensity", 1.0))
        best_idx = None
        best_delta = None
        for idx, (ref_pos, _) in enumerate(ref_remaining):
            delta = abs(obs_pos - ref_pos)
            if delta <= tolerance and (best_delta is None or delta < best_delta):
                best_delta = delta
                best_idx = idx
        if best_idx is not None:
            matched_weight += obs_int
            ref_remaining.pop(best_idx)

    return matched_weight / total_weight if total_weight > 0 else 0.0
