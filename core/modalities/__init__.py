"""Modality contract and registry package."""

from core.modalities.contracts import ModalityAdapter, ModalitySpec
from core.modalities.registry import get_modality, require_stable_modality, stable_analysis_types
from core.modalities.state_keys import analysis_state_key

__all__ = [
    "ModalityAdapter",
    "ModalitySpec",
    "analysis_state_key",
    "get_modality",
    "require_stable_modality",
    "stable_analysis_types",
]
