# T03: 03-ftir-and-raman-mvp 03

**Slice:** S03 — **Milestone:** M001

## Description

Complete Phase 3 integration at compare/export/report surfaces and lock regression gates.

Purpose: satisfy SPC-04 by delivering modality-level FTIR/Raman compare and stable export/report inclusion.
Output: Streamlit + desktop compare integration, backend compare/export updates, report caution semantics, and final validation map updates.

## Must-Haves

- [ ] "FTIR and Raman stable results are saveable, compareable at modality level, and exportable in existing stable artifact flows."
- [ ] "Compare UX enforces modality-specific spectral comparison defaults and does not mix FTIR/Raman lanes by default."
- [ ] "Report/export outputs include balanced spectral summaries with explicit caution language for low-confidence/no-match outcomes."

## Files

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
