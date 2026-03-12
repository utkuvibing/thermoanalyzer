"""Central registry for stable modality specs."""

from __future__ import annotations

from core.modalities.adapters import DSCAdapter, DTAAdapter, FTIRAdapter, RAMANAdapter, TGAAdapter, XRDAdapter
from core.modalities.contracts import ModalitySpec


_REGISTRY: dict[str, ModalitySpec] = {
    "DSC": ModalitySpec(
        analysis_type="DSC",
        stable=True,
        default_workflow_template_id="dsc.general",
        adapter=DSCAdapter(),
    ),
    "DTA": ModalitySpec(
        analysis_type="DTA",
        stable=True,
        default_workflow_template_id="dta.general",
        adapter=DTAAdapter(),
    ),
    "TGA": ModalitySpec(
        analysis_type="TGA",
        stable=True,
        default_workflow_template_id="tga.general",
        adapter=TGAAdapter(),
    ),
    "FTIR": ModalitySpec(
        analysis_type="FTIR",
        stable=True,
        default_workflow_template_id="ftir.general",
        adapter=FTIRAdapter(),
    ),
    "RAMAN": ModalitySpec(
        analysis_type="RAMAN",
        stable=True,
        default_workflow_template_id="raman.general",
        adapter=RAMANAdapter(),
    ),
    "XRD": ModalitySpec(
        analysis_type="XRD",
        stable=True,
        default_workflow_template_id="xrd.general",
        adapter=XRDAdapter(),
    ),
}


def _normalize_analysis_type(analysis_type: str | None) -> str:
    return str(analysis_type or "").upper().strip()


def get_modality(analysis_type: str | None) -> ModalitySpec | None:
    """Return modality spec if registered, otherwise None."""
    return _REGISTRY.get(_normalize_analysis_type(analysis_type))


def require_stable_modality(analysis_type: str | None) -> ModalitySpec:
    """Return stable modality spec or raise ValueError."""
    token = _normalize_analysis_type(analysis_type)
    spec = _REGISTRY.get(token)
    if spec is None or not spec.stable:
        raise ValueError(f"Unsupported stable analysis_type: {token or 'UNKNOWN'}")
    return spec


def stable_analysis_types() -> tuple[str, ...]:
    """Return sorted stable analysis types."""
    return tuple(sorted(key for key, value in _REGISTRY.items() if value.stable))
