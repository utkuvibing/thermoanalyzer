# S04: Xrd Mvp

**Goal:** Establish XRD modality and import foundations so Phase 4 execution can proceed on stable contracts.
**Demo:** Establish XRD modality and import foundations so Phase 4 execution can proceed on stable contracts.

## Must-Haves


## Tasks

- [x] **T01: 04-xrd-mvp 01** `est:13min`
  - Establish XRD modality and import foundations so Phase 4 execution can proceed on stable contracts.

Purpose: satisfy XRD-01 with stable XRD onboarding in registry/dispatch and normalized `.xy/.dat/.cif` MVP import behavior.
Output: registry/state-key/adapter updates, bounded XRD import normalization, and dispatch/import regression tests.
- [x] **T02: 04-xrd-mvp 02** `est:11min`
  - Implement XRD preprocessing and robust peak extraction after import/registry foundations are established.

Purpose: satisfy XRD-02 with template-driven XRD preprocessing plus deterministic peak detection and validation context requirements.
Output: processing schema extensions, batch/execution engine XRD path, and processing/validation tests.
- [x] **T03: 04-xrd-mvp 03** `est:12min`
  - Deliver qualitative XRD phase-candidate matching with traceable confidence and caution-safe semantics.

Purpose: satisfy XRD-03 by implementing deterministic candidate matching, evidence-rich outputs, and validation/serialization compatibility.
Output: qualitative matching engine behavior in execution path plus validation and serialization contracts/tests.
- [x] **T04: 04-xrd-mvp 04** `est:38 min`
  - Complete Phase 4 integration so XRD stable outputs are usable in save/compare/export/report workflows.

Purpose: satisfy XRD-04 by wiring XRD through artifact and compare surfaces with method context and caution-aware reporting.
Output: backend compare/export/report integration, UI compare support, and final validation-map/regression updates.

## Files Likely Touched

- `core/modalities/registry.py`
- `core/modalities/state_keys.py`
- `core/modalities/adapters.py`
- `core/data_io.py`
- `ui/components/column_mapper.py`
- `backend/app.py`
- `tests/test_modality_registry.py`
- `tests/test_data_io.py`
- `tests/test_backend_modality_dispatch.py`
- `core/processing_schema.py`
- `core/batch_runner.py`
- `core/execution_engine.py`
- `core/validation.py`
- `tests/test_processing_schema.py`
- `tests/test_batch_runner.py`
- `tests/test_validation.py`
- `core/batch_runner.py`
- `core/validation.py`
- `core/result_serialization.py`
- `tests/test_batch_runner.py`
- `tests/test_validation.py`
- `tests/test_result_serialization.py`
- `backend/detail.py`
- `backend/models.py`
- `backend/exports.py`
- `ui/compare_page.py`
- `core/report_generator.py`
- `tests/test_backend_details.py`
- `tests/test_backend_exports.py`
- `tests/test_export_report.py`
- `tests/test_report_generator.py`
- `.planning/phases/04-xrd-mvp/04-VALIDATION.md`
