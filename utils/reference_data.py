"""Calibration standards and reference data for thermal analysis.

Provides melting-point and decomposition standards used in DSC / TGA / DTA
calibration, together with helpers that compare measured temperatures against
known values and return colour-coded deviation information.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ReferencePoint:
    name: str
    temperature_c: float
    event_type: str          # "melting", "decomposition", "transition"
    enthalpy_j_g: Optional[float] = None
    standard: str = ""       # e.g. "ASTM E967"
    notes: str = ""


# ── DSC melting-point calibration standards ──────────────────────────────────
DSC_MELTING_STANDARDS: List[ReferencePoint] = [
    ReferencePoint("Indium (In)",    156.6,  "melting", 28.7,  "ASTM E967", "Primary DSC calibrant"),
    ReferencePoint("Tin (Sn)",       231.9,  "melting", 60.2,  "ASTM E967", ""),
    ReferencePoint("Lead (Pb)",      327.5,  "melting", 23.0,  "",          "Rarely used due to toxicity"),
    ReferencePoint("Zinc (Zn)",      419.5,  "melting", 108.4, "ASTM E967", ""),
    ReferencePoint("Aluminum (Al)",  660.3,  "melting", 397.0, "",          "High-temperature calibrant"),
    ReferencePoint("Silver (Ag)",    961.8,  "melting", 104.8, "",          ""),
    ReferencePoint("Gold (Au)",     1064.2,  "melting", 63.7,  "",          ""),
]

# ── TGA decomposition calibration standards ──────────────────────────────────
TGA_DECOMPOSITION_STANDARDS: List[ReferencePoint] = [
    ReferencePoint("CaC₂O₄·H₂O  Step 1",  200.0, "decomposition", None, "ASTM E1131",
                   "Dehydration → CaC₂O₄ (12.3% mass loss)"),
    ReferencePoint("CaC₂O₄·H₂O  Step 2",  500.0, "decomposition", None, "ASTM E1131",
                   "CO loss → CaCO₃ (19.2% mass loss)"),
    ReferencePoint("CaC₂O₄·H₂O  Step 3",  780.0, "decomposition", None, "ASTM E1131",
                   "CO₂ loss → CaO (30.1% mass loss)"),
]

# Merged lookup list
_ALL_STANDARDS = DSC_MELTING_STANDARDS + TGA_DECOMPOSITION_STANDARDS


def find_nearest_reference(
    temperature_c: float,
    threshold_c: float = 15.0,
    analysis_type: str = "DSC",
) -> Optional[ReferencePoint]:
    """Return the closest reference point within *threshold_c* degrees.

    Parameters
    ----------
    temperature_c : float
        Measured peak or onset temperature in °C.
    threshold_c : float
        Maximum acceptable distance (°C) to consider a match.
    analysis_type : str
        ``"DSC"`` / ``"DTA"`` searches melting standards first;
        ``"TGA"`` searches decomposition standards first.

    Returns
    -------
    ReferencePoint or None
    """
    if analysis_type in ("DSC", "DTA"):
        pool = DSC_MELTING_STANDARDS + TGA_DECOMPOSITION_STANDARDS
    else:
        pool = TGA_DECOMPOSITION_STANDARDS + DSC_MELTING_STANDARDS

    best: Optional[ReferencePoint] = None
    best_dist = float("inf")
    for ref in pool:
        dist = abs(temperature_c - ref.temperature_c)
        if dist < best_dist:
            best_dist = dist
            best = ref
    if best is not None and best_dist <= threshold_c:
        return best
    return None


def render_reference_comparison(
    temperature_c: float,
    analysis_type: str = "DSC",
    threshold_c: float = 15.0,
) -> Optional[str]:
    """Return a Markdown string comparing *temperature_c* to the nearest
    calibration standard, or ``None`` if no match is found.

    Colour coding:
    - <2 °C  → green
    - <5 °C  → yellow / orange
    - >=5 °C → red
    """
    ref = find_nearest_reference(temperature_c, threshold_c, analysis_type)
    if ref is None:
        return None

    delta = temperature_c - ref.temperature_c
    abs_delta = abs(delta)

    if abs_delta < 2:
        colour = "🟢"
    elif abs_delta < 5:
        colour = "🟡"
    else:
        colour = "🔴"

    sign = "+" if delta >= 0 else ""
    line = (
        f"{colour} **Ref:** {ref.name} ({ref.temperature_c:.1f} °C) — "
        f"ΔT = {sign}{delta:.1f} °C"
    )
    if ref.enthalpy_j_g is not None:
        line += f" | ΔH_ref = {ref.enthalpy_j_g:.1f} J/g"
    if ref.standard:
        line += f" | {ref.standard}"
    return line
