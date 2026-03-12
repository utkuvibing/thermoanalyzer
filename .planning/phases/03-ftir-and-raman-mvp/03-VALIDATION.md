---
phase: 03
slug: ftir-and-raman-mvp
status: executed
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-12
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none - Wave 0 optional |
| **Quick run command** | `pytest -q tests/test_data_io.py tests/test_processing_schema.py tests/test_modality_registry.py tests/test_backend_modality_dispatch.py tests/test_validation.py tests/test_result_serialization.py tests/test_backend_details.py tests/test_backend_workflow.py tests/test_backend_exports.py tests/test_export_report.py tests/test_report_generator.py` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~240 seconds |

---

## Sampling Rate

- **After every task commit:** Run targeted plan commands for the touched subsystem (import/processing/compare/export).
- **After every plan wave:** Run `pytest -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 240 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | SPC-01 | unit/integration | `pytest -q tests/test_modality_registry.py tests/test_data_io.py tests/test_backend_modality_dispatch.py -k "ftir or raman"` | ✅ | ✅ green |
| 03-02-01 | 02 | 2 | SPC-02, SPC-03 | unit/integration | `pytest -q tests/test_processing_schema.py tests/test_batch_runner.py tests/test_validation.py tests/test_result_serialization.py tests/test_report_generator.py -k "ftir or raman or caution or no_match"` | ✅ | ✅ green |
| 03-03-01 | 03 | 3 | SPC-04 | integration | `pytest -q tests/test_backend_details.py tests/test_backend_workflow.py -k "compare or ftir or raman"` | ✅ | ✅ green |
| 03-03-02 | 03 | 3 | SPC-04 | integration | `pytest -q tests/test_backend_exports.py tests/test_export_report.py tests/test_report_generator.py -k "ftir or raman or caution"` | ✅ | ✅ green |
| 03-03-03 | 03 | 3 | SPC-04 | regression | `pytest -q tests/test_backend_workflow.py -k "compare or export"` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] SPC-01 import/modality coverage lives in `tests/test_modality_registry.py`, `tests/test_data_io.py`, and `tests/test_backend_modality_dispatch.py`.
- [x] SPC-02 preprocessing/template coverage lives in `tests/test_processing_schema.py`.
- [x] SPC-03 matching/serialization/validation coverage lives in `tests/test_batch_runner.py`, `tests/test_validation.py`, and `tests/test_result_serialization.py`.
- [x] SPC-04 compare/export/report coverage lives in `tests/test_backend_details.py`, `tests/test_backend_workflow.py`, `tests/test_backend_exports.py`, `tests/test_export_report.py`, and `tests/test_report_generator.py`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Streamlit and desktop compare UI present modality-specific FTIR/Raman lanes with correct labels and caution messaging | SPC-04 | UI wording/layout and interaction quality are not fully asserted by current automated suite | Run app shells, import one FTIR and one Raman dataset, verify compare selectors do not mix modalities by default, confirm low-confidence/no-match caution text appears in exported report preview. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 240s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** complete
