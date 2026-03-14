# T01: 04-xrd-mvp 01

**Slice:** S04 — **Milestone:** M001

## Description

Establish XRD modality and import foundations so Phase 4 execution can proceed on stable contracts.

Purpose: satisfy XRD-01 with stable XRD onboarding in registry/dispatch and normalized `.xy/.dat/.cif` MVP import behavior.
Output: registry/state-key/adapter updates, bounded XRD import normalization, and dispatch/import regression tests.

## Must-Haves

- [ ] "Stable modality contracts include XRD with deterministic state key mapping and registry-driven backend acceptance."
- [ ] "XRD import supports `.xy` and `.dat` measured-pattern paths plus bounded `.cif` MVP handling with explicit unsupported messaging."
- [ ] "Normalized XRD datasets persist axis-role, unit, and wavelength provenance needed by downstream processing and reporting."

## Files

- `core/modalities/registry.py`
- `core/modalities/state_keys.py`
- `core/modalities/adapters.py`
- `core/data_io.py`
- `ui/components/column_mapper.py`
- `backend/app.py`
- `tests/test_modality_registry.py`
- `tests/test_data_io.py`
- `tests/test_backend_modality_dispatch.py`
