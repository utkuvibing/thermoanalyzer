"""Helpers for analysis-state key naming."""

from __future__ import annotations


_PREFIX_BY_ANALYSIS_TYPE = {
    "DSC": "dsc_state",
    "DTA": "dta_state",
    "TGA": "tga_state",
}


def analysis_state_key(analysis_type: str | None, dataset_key: str) -> str:
    """Return deterministic analysis-state key for stable modalities."""
    token = str(analysis_type or "").upper().strip()
    prefix = _PREFIX_BY_ANALYSIS_TYPE.get(token)
    if prefix is None:
        raise ValueError(f"Unsupported stable analysis_type for state key: {token or 'UNKNOWN'}")
    return f"{prefix}_{dataset_key}"
