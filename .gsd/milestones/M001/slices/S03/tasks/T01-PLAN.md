# T01: 03-ftir-and-raman-mvp 01

**Slice:** S03 — **Milestone:** M001

## Description

Establish Phase 3 import and modality foundations before analysis implementation.

Purpose: satisfy SPC-01 with stable FTIR/Raman onboarding through registry/state contracts and normalized MVP import behavior.
Output: FTIR/Raman stable type registration, spectral import normalization with warning/confidence handling, and import/dispatch tests.

## Must-Haves

- [ ] "Stable modality contracts include FTIR and RAMAN with deterministic state keys and registry-driven dispatch compatibility."
- [ ] "Import supports FTIR/Raman text and CSV normalization with confidence-driven warning metadata and low-confidence modality confirmation paths."
- [ ] "JCAMP-DX MVP ingestion is bounded to single-spectrum core cases with explicit unsupported handling for out-of-scope variants."

## Files

- `core/modalities/registry.py`
- `core/modalities/state_keys.py`
- `core/modalities/adapters.py`
- `core/processing_schema.py`
- `core/data_io.py`
- `ui/components/column_mapper.py`
- `backend/app.py`
- `tests/test_modality_registry.py`
- `tests/test_data_io.py`
- `tests/test_backend_modality_dispatch.py`
