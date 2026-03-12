---
phase: 04
slug: xrd-mvp
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-12
updated: 2026-03-12
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none |
| **Quick run command** | `pytest -q tests/test_backend_details.py tests/test_backend_exports.py tests/test_export_report.py tests/test_report_generator.py -k "xrd or compare or export or report"` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task-scoped verify command from PLAN.md.
- **After every plan wave:** Run `pytest -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | XRD-01 | unit+integration | `pytest -q tests/test_modality_registry.py tests/test_data_io.py tests/test_backend_modality_dispatch.py` | ✅ | ✅ green |
| 04-02-01 | 02 | 2 | XRD-02 | unit | `pytest -q tests/test_processing_schema.py tests/test_batch_runner.py tests/test_validation.py` | ✅ | ✅ green |
| 04-03-01 | 03 | 3 | XRD-03 | unit | `pytest -q tests/test_batch_runner.py tests/test_validation.py tests/test_result_serialization.py` | ✅ | ✅ green |
| 04-04-01 | 04 | 4 | XRD-04 | integration | `pytest -q tests/test_backend_details.py tests/test_backend_exports.py tests/test_export_report.py tests/test_report_generator.py -k "xrd or compare or export or report"` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_data_io.py` — add XRD import edge-case stubs for `.xy`, `.dat`, `.cif` bounded support
- [x] `tests/test_batch_runner.py` — add XRD preprocessing/peak-detection deterministic baseline fixtures
- [x] `tests/test_result_serialization.py` — add XRD candidate-evidence schema guard assertions

---

## Release Gate Commands

- **Phase-4 scoped release gate:** `pytest -q tests/test_backend_details.py tests/test_backend_exports.py tests/test_export_report.py tests/test_report_generator.py -k "xrd or compare or export or report"` (status: ✅ pass)
- **Full-suite release gate:** `pytest -q` (status: ✅ pass)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Compare lane UX messaging for XRD in Streamlit/desktop | XRD-04 | UI wording and interaction quality | Run app flows, create XRD dataset, confirm modality lane and caution wording in compare/report previews |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 180s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved (2026-03-12)