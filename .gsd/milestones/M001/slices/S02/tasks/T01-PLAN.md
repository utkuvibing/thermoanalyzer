# T01: 02-dta-stabilization 01

**Slice:** S02 — **Milestone:** M001

## Description

Stabilize DTA in backend modality contracts and execution routing before UI/report promotion.

Purpose: satisfy DTA-02 by making DTA a true stable analysis type in registry and run/batch execution paths.
Output: registry/state-key/adapter updates, DTA-capable backend execution wiring, and dispatch tests that prove stable DTA acceptance.

## Must-Haves

- [ ] "DTA is accepted as a stable analysis type by backend single-run and batch-run validation paths through registry-based dispatch."
- [ ] "Stable DTA dataset eligibility allows DTA and UNKNOWN datasets, with deterministic state key mapping dta_state_<dataset_key>."
- [ ] "DTA execution uses stable workflow template defaults (dta.general) while honoring explicit template overrides including dta.thermal_events."

## Files

- `core/modalities/registry.py`
- `core/modalities/adapters.py`
- `core/modalities/state_keys.py`
- `core/batch_runner.py`
- `core/execution_engine.py`
- `backend/app.py`
- `tests/test_modality_registry.py`
- `tests/test_batch_runner.py`
- `tests/test_backend_modality_dispatch.py`
