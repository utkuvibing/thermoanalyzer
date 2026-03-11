---
phase: 02
slug: dta-stabilization
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-12
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none |
| **Quick smoke command** | `pytest -q tests/test_modality_registry.py -k "dta or stable"` |
| **Full suite command** | `pytest -q` |
| **Smoke runtime target** | `< 30 seconds` |

---

## Sampling Rate

- **After every task commit:** Run the task-specific smoke command from the per-task map (`< 30s` target).
- **After every plan wave:** Run the corresponding wave-gate suite (`WG-1`, `WG-2`, `WG-3`) before moving forward.
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds (task smoke loop)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Smoke Command (`<30s` target) | Wave Gate | File Exists | Status |
|---------|------|------|-------------|-----------|--------------------------------|-----------|-------------|--------|
| 02-01-01 | 01 | 1 | DTA-02 | unit | `pytest -q tests/test_modality_registry.py -k "dta or stable"` | WG-1 | ✅ | ✅ green |
| 02-01-02 | 01 | 1 | DTA-02 | unit/integration | `pytest -q tests/test_batch_runner.py -k "dta or batch"` | WG-1 | ✅ | ✅ green |
| 02-01-03 | 01 | 1 | DTA-02 | integration | `pytest -q tests/test_backend_modality_dispatch.py -k "analysis_type or dta"` | WG-1 | ✅ | ✅ green |
| 02-02-01 | 02 | 2 | DTA-03 | unit | `pytest -q tests/test_validation.py -k "dta or pass or warn or fail"` | WG-2 | ✅ | ✅ green |
| 02-02-02 | 02 | 2 | DTA-04 | unit | `pytest -q tests/test_result_serialization.py -k "dta and (stable or status or context)"` | WG-2 | ✅ | ✅ green |
| 02-02-03 | 02 | 2 | DTA-04 | integration | `pytest -q tests/test_report_generator.py tests/test_export_report.py -k "dta or stable"` | WG-2 | ✅ | ✅ green |
| 02-03-01 | 03 | 3 | DTA-01 | integration | `pytest -q tests/test_backend_workflow.py -k "dta or workflow"` | WG-3 | ✅ | ✅ green |
| 02-03-02 | 03 | 3 | DTA-01 | integration | `pytest -q tests/test_backend_workflow.py -k "desktop or dta"` | WG-3 | ✅ | ✅ green |
| 02-03-03 | 03 | 3 | DTA-01 | regression/integration | `pytest -q tests/test_dsc_tga_parity.py tests/test_backend_api.py tests/test_backend_workflow.py` | WG-3 | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave Gate Commands

- **WG-1 (Plan 01 / Wave 1):** `pytest -q tests/test_modality_registry.py tests/test_batch_runner.py tests/test_backend_modality_dispatch.py`
- **WG-2 (Plan 02 / Wave 2):** `pytest -q tests/test_validation.py tests/test_result_serialization.py tests/test_report_generator.py tests/test_export_report.py tests/test_backend_exports.py`
- **WG-3 (Plan 03 / Wave 3):** `pytest -q tests/test_backend_api.py tests/test_backend_workflow.py tests/test_dsc_tga_parity.py`

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Streamlit DTA appears in primary nav (not preview-gated) and experimental copy is removed | DTA-01 | Streamlit navigation/copy assertions are not fully covered by automated tests | Launch app, verify DTA in primary section, verify preview toggle no longer controls DTA visibility, and confirm stable wording |
| Desktop DTA nav/view is enabled in primary group and preview-only DTA button is removed/retired | DTA-01 | Desktop Electron renderer UX is difficult to fully validate through current headless suite | Launch desktop shell, verify primary DTA navigation entry, run a DTA dataset flow, confirm no experimental-only DTA messaging |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Per-task smoke loop feedback latency < 30s
- [x] Wave-gate suites (`WG-1..WG-3`) executed at wave boundaries
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved (2026-03-12)
