# T04: 04-xrd-mvp 04

**Slice:** S04 — **Milestone:** M001

## Description

Complete Phase 4 integration so XRD stable outputs are usable in save/compare/export/report workflows.

Purpose: satisfy XRD-04 by wiring XRD through artifact and compare surfaces with method context and caution-aware reporting.
Output: backend compare/export/report integration, UI compare support, and final validation-map/regression updates.

## Must-Haves

- [ ] "Stable XRD results are saveable and present in compare/export/report flows with method context and provenance visibility."
- [ ] "Compare and artifact layers enforce modality-aware XRD eligibility instead of silently mixing incompatible modalities."
- [ ] "Export/report narratives include explicit qualitative-confidence caution language to avoid overclaiming phase identification certainty."

## Files

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
