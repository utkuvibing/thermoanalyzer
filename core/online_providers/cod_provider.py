"""COD online provider — 500K+ crystal structures → XRD pattern matching."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from core.online_providers.base import OnlineProvider, OnlineSearchResult

logger = logging.getLogger(__name__)

COD_SEARCH_URL = "https://www.crystallography.net/cod/result"
COD_CIF_BASE = "https://www.crystallography.net/cod/{cod_id}.cif"


class CODProvider:
    """Query COD for crystal structures and calculate XRD patterns."""

    provider_id = "cod"
    provider_name = "COD"
    supported_analysis_types = ("XRD",)

    def is_available(self) -> bool:
        try:
            from pymatgen.analysis.diffraction.xrd import XRDCalculator
            from pymatgen.core import Structure
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
        return []  # XRD only

    def search_by_peaks(
        self,
        analysis_type: str,
        peaks: list[dict[str, float]],
        *,
        top_n: int = 10,
        tolerance_deg: float = 0.3,
    ) -> list[OnlineSearchResult]:
        """Search COD by fetching structures and matching calculated XRD patterns."""
        if not peaks:
            return []
        # COD doesn't have a great peak-search API, so this provider
        # works best with formula-based searches
        return []

    def search_by_formula(
        self,
        formula: str,
        *,
        top_n: int = 20,
    ) -> list[OnlineSearchResult]:
        """Search COD by chemical formula and return structures with calculated XRD."""
        if not formula.strip():
            return []

        try:
            from pymatgen.analysis.diffraction.xrd import XRDCalculator
            from pymatgen.core import Structure
        except ImportError:
            return []

        import numpy as np
        wavelength = 1.5406

        # Search COD for structures matching the formula
        cod_ids = self._search_cod_ids(formula, max_results=min(top_n * 3, 60))
        if not cod_ids:
            return []

        calculator = XRDCalculator(wavelength=wavelength)
        results: list[OnlineSearchResult] = []

        for cod_id in cod_ids[:min(len(cod_ids), top_n * 2)]:
            try:
                cif_text = self._fetch_cif(cod_id)
                if not cif_text:
                    continue
                structure = Structure.from_str(cif_text, fmt="cif")
                reduced_formula = str(structure.composition.reduced_formula)

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

                results.append(OnlineSearchResult(
                    candidate_id=f"cod_{cod_id}",
                    candidate_name=f"{reduced_formula} (COD {cod_id})",
                    provider=self.provider_name,
                    analysis_type="XRD",
                    source_url=f"https://www.crystallography.net/cod/{cod_id}.html",
                    attribution="Crystallography Open Database - https://www.crystallography.net",
                    peaks=ref_peaks,
                    formula=reduced_formula,
                ))
            except Exception as exc:
                logger.debug("Failed to process COD %s: %s", cod_id, exc)
                continue

        return results[:top_n]

    def _search_cod_ids(self, formula: str, max_results: int = 50) -> list[str]:
        """Search COD for matching structure IDs by formula."""
        try:
            response = httpx.get(
                COD_SEARCH_URL,
                params={"formula": formula.strip(), "format": "json"},
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return [str(item.get("file", "")) for item in data[:max_results] if item.get("file")]
            return []
        except Exception as exc:
            logger.debug("COD search failed for formula '%s': %s", formula, exc)
            return []

    def _fetch_cif(self, cod_id: str) -> str:
        """Download a CIF file from COD."""
        try:
            url = COD_CIF_BASE.format(cod_id=cod_id)
            response = httpx.get(url, timeout=10.0)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            logger.debug("Failed to fetch CIF for COD %s: %s", cod_id, exc)
            return ""
