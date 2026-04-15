"""Pure helpers for Compare overlay axes and analysis-state series selection (no Dash page registration)."""


def axis_titles(analysis_type: str) -> tuple[str, str]:
    """X and Y axis titles for compare overlay."""
    upper = (analysis_type or "").upper()
    if upper == "FTIR":
        return "Wavenumber (cm^-1)", "Intensity (a.u.)"
    if upper == "RAMAN":
        return "Raman shift (cm^-1)", "Intensity (a.u.)"
    if upper == "XRD":
        return "2theta (deg)", "Intensity (a.u.)"
    if upper == "TGA":
        return "Temperature (C)", "Mass or signal (a.u.)"
    return "Temperature (C)", "Signal (a.u.)"


def pick_best_series(curves: dict) -> tuple[list, list, str] | None:
    """Return (x, y, source_label) from analysis-state payload, or None if unusable."""
    x = curves.get("temperature") or []
    if not x:
        return None
    n = len(x)
    corrected = curves.get("corrected") or []
    smoothed = curves.get("smoothed") or []
    raw = curves.get("raw_signal") or []
    if len(corrected) == n:
        return x, corrected, "corrected"
    if len(smoothed) == n:
        return x, smoothed, "smoothed"
    if len(raw) == n:
        return x, raw, "raw"
    return None
