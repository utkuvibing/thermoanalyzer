# S03: Ftir And Raman Mvp

**Goal:** Establish Phase 3 import and modality foundations before analysis implementation.
**Demo:** Establish Phase 3 import and modality foundations before analysis implementation.

## Must-Haves


## Tasks

- [x] **T01: 03-ftir-and-raman-mvp 01** `est:8 min`
  - Establish Phase 3 import and modality foundations before analysis implementation.

Purpose: satisfy SPC-01 with stable FTIR/Raman onboarding through registry/state contracts and normalized MVP import behavior.
Output: FTIR/Raman stable type registration, spectral import normalization with warning/confidence handling, and import/dispatch tests.
- [x] **T02: 03-ftir-and-raman-mvp 02** `est:18 min`
  - Implement stable FTIR/Raman preprocessing and analysis engine behavior after import foundations.

Purpose: satisfy SPC-02 and SPC-03 with configurable preprocessing, ranked similarity outputs, and explicit no-match handling.
Output: spectral processing schema + execution + validation + serialization coverage.
- [x] **T03: 03-ftir-and-raman-mvp 03** `est:5 min`
  - Complete Phase 3 integration at compare/export/report surfaces and lock regression gates.

Purpose: satisfy SPC-04 by delivering modality-level FTIR/Raman compare and stable export/report inclusion.
Output: Streamlit + desktop compare integration, backend compare/export updates, report caution semantics, and final validation map updates.

## Files Likely Touched

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
- `core/processing_schema.py`
- `core/batch_runner.py`
- `core/execution_engine.py`
- `core/validation.py`
- `core/result_serialization.py`
- `core/report_generator.py`
- `tests/test_processing_schema.py`
- `tests/test_batch_runner.py`
- `tests/test_validation.py`
- `tests/test_result_serialization.py`
- `ui/compare_page.py`
- `app.py`
- `desktop/electron/index.html`
- `desktop/electron/renderer.js`
- `backend/detail.py`
- `backend/models.py`
- `backend/exports.py`
- `core/report_generator.py`
- `tests/test_backend_details.py`
- `tests/test_backend_exports.py`
- `tests/test_export_report.py`
- `tests/test_backend_workflow.py`
- `.planning/phases/03-ftir-and-raman-mvp/03-VALIDATION.md`
