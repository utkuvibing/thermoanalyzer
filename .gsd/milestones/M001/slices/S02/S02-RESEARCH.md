# Phase 2 Research: DTA Stabilization (02)

## Objective
Answer: What do we need to know to plan Phase 2 (DTA Stabilization) well?

Scope: Promote DTA from preview/experimental behavior to stable first-class behavior across Streamlit and desktop navigation, backend run/batch execution, validation, and export/report outputs.

## Inputs Reviewed
- `.planning/phases/02-dta-stabilization/02-CONTEXT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/STATE.md`
- `backend/app.py`
- `backend/detail.py`
- `core/modalities/*`
- `core/execution_engine.py`
- `core/result_serialization.py`
- `core/validation.py`
- `app.py`
- `desktop/electron/index.html`
- `desktop/electron/renderer.js`
- `ui/dta_page.py`
- `backend/exports.py`
- `core/report_generator.py`
- Relevant tests under `tests/`

## Current Baseline (What Exists Today)
- DTA workflow UI exists in Streamlit (`ui/dta_page.py`), but is explicitly experimental in messaging and save behavior.
- Stable modality registry currently includes only DSC/TGA (`core/modalities/registry.py:9-22`).
- Backend run/batch engine is registry-backed (`core/execution_engine.py:116`, `core/execution_engine.py:195`) and therefore currently excludes DTA.
- Batch execution kernel (`core/batch_runner.py`) only implements DSC/TGA executors and throws for other types (`core/batch_runner.py:113-133`).
- DTA serialization exists but is explicitly experimental (`core/result_serialization.py:760`, `core/result_serialization.py:778`).
- Validation accepts DTA as a known type but has no DTA-specific workflow checks (only DSC/TGA branches) (`core/validation.py:15`, `core/validation.py:407-425`).
- Report/export pipeline is status-driven (stable vs experimental) and already includes DTA records generically if present (`core/report_generator.py:1701-1702`, `core/result_serialization.py:1025-1034`).
- Streamlit and desktop both keep DTA behind preview/experimental messaging:
  - Streamlit: preview toggle + preview nav section (`app.py:385-406`)
  - Desktop: disabled preview DTA button (`desktop/electron/index.html:494-499`)

## Requirement Mapping (DTA-01..DTA-04)

### DTA-01: DTA is available as stable workflow in Streamlit and desktop navigation
Current state:
- Streamlit DTA page is only added when preview toggle is on (`app.py:401-406`).
- DTA page itself warns it is outside stability guarantee (`ui/dta_page.py:132-136`).
- Desktop has no active DTA view; only disabled preview button (`desktop/electron/index.html:496`).
- Desktop copy repeatedly frames stable scope as DSC/TGA only (`desktop/electron/renderer.js:240-241`, `desktop/electron/renderer.js:253`).

Gap to close:
- Promote DTA into primary navigation in both shells.
- Remove DTA preview-only and experimental-only wording for Phase 2 stable DTA scope.
- Implement/enable an actual desktop DTA workflow view (not just nav label change).

Planning note:
- Desktop is the larger unknown here because the current desktop app has DSC/TGA views but no DTA view section.

### DTA-02: DTA is accepted by backend run/batch/report paths where stable analyses are supported
Current state:
- Stable registry excludes DTA (`core/modalities/registry.py:9-22`).
- State-key mapping excludes DTA (`core/modalities/state_keys.py:6-18`).
- `run_single_analysis` and `run_batch_analysis` require stable modality (`core/execution_engine.py:116`, `core/execution_engine.py:195`).
- Batch kernel rejects non-DSC/TGA (`core/batch_runner.py:113-133`).

Gap to close:
- Add DTA to stable registry + state key map with key `dta_state_<dataset_key>`.
- Add DTA stable adapter eligibility `{"DTA", "UNKNOWN"}` (locked decision).
- Add DTA batch/single execution path in batch kernel and wire to execution engine.
- Ensure default template is `dta.general` and explicit template override supports `dta.thermal_events`.

Planning note:
- The registry change alone is insufficient; without batch-runner DTA execution, backend run fails at runtime.

### DTA-03: DTA validation rules are productionized with pass/warn/fail semantics and method context checks
Current state:
- Validator supports DTA unit hints but no DTA-specific checks beyond generic data/metadata checks (`core/validation.py:15-23`, `core/validation.py:407-425`).
- DTA UI saves validation output but without a DTA-specific stable rule set (`ui/dta_page.py:120`).

Gap to close:
- Add DTA-specific validation branch with explicit critical blockers vs warnings.
- Add method-context-aware DTA checks (template id, sign convention, reference/calibration context if present).
- Ensure blocking policy follows context decision: only critical integrity/context gaps block stable path.

Planning note:
- Validation architecture should be defined before execution code finalization to avoid churn in summary-row semantics and report consistency.

### DTA-04: DTA outputs are included in stable export/report artifacts with modality-appropriate summaries
Current state:
- Export preparation includes all valid results regardless of modality (`backend/exports.py:41-48`).
- Report partitions records by `status`; DTA currently lands in experimental section because serializer marks it experimental (`core/result_serialization.py:778`, `core/report_generator.py:1779-1783`).
- DTA scientific context includes explicit experimental limitation text (`core/result_serialization.py:287-289`).
- Report method/reference helper logic is DSC/TGA-specific for some sections (`core/report_generator.py:1225`, `core/report_generator.py:1259`).

Gap to close:
- Emit stable DTA records (`status="stable"`) for Phase 2 stable flow.
- Remove/replace experimental-only DTA scientific-context language.
- Confirm DTA summary/method sections are scientifically appropriate (generic method summary may be acceptable minimum; DTA-specific section is better).

Planning note:
- Most export/report plumbing is already modality-agnostic; main work is record semantics + DTA narrative quality.

## Critical Gaps and Risks

1. Registry/runtime mismatch risk (high)
- If DTA is added to stable registry without adding DTA execution in batch runner, run/batch paths fail (`core/batch_runner.py:133`).

2. State-key contract gap (high)
- DTA stable execution via execution engine requires `analysis_state_key("DTA", ...)` but DTA key is not defined (`core/modalities/state_keys.py:6-18`).

3. Desktop workflow gap (high)
- Desktop currently has no DTA view and keeps DTA as disabled preview nav item (`desktop/electron/index.html:496`).

4. Validation under-specification (high)
- DTA has no dedicated stable method-context checks, so pass/warn/fail policy is not productionized.

5. Reporting semantics inconsistency (medium)
- DTA can appear in reports but currently as experimental with explicit experimental limitations (`core/result_serialization.py:287-289`, `:778`).

6. Type-token inconsistency risk (medium)
- Some paths use `UNKNOWN`, some `unknown`; DTA UI dataset filter currently checks `("DTA", "unknown")` (`ui/dta_page.py:57`) while Phase 2 decision locks `DTA` + `UNKNOWN` eligibility.

7. Test debt risk (high)
- Existing tests assert stable set is DSC/TGA only (`tests/test_modality_registry.py:22`, `tests/test_backend_modality_dispatch.py:77`, `:110`, `tests/test_backend_details.py:112`).
- There are almost no DTA backend/validation/report contract tests yet.

## Implementation Options

### Option A (Recommended): Extend existing stable execution contract to include DTA end-to-end
What it means:
- Add DTA to modality registry/state keys.
- Implement DTA batch kernel executor in `core/batch_runner.py` using `DTAProcessor` + standardized processing/provenance/validation/serialization.
- Promote DTA UI copy/nav from preview to stable.
- Keep shared export/report architecture; switch DTA record classification to stable for stable flow.

Why recommended:
- Reuses existing architecture (modality registry, execution_engine, batch summary/reporting contracts).
- Lowest conceptual debt and best alignment with Phase 1 contract-first design.

Tradeoffs:
- Requires coordinated updates across backend + both UIs + tests in one phase.

### Option B: Backend-stable first, desktop DTA view minimal MVP
What it means:
- Complete backend stabilization first (registry, execution, validation, serialization, report).
- Desktop DTA view ships as a minimal run/save/result-inspection page, with deeper ergonomics deferred.

Why plausible:
- De-risks backend contract completion and Phase traceability first.

Tradeoffs:
- Desktop UX parity with Streamlit will initially be lower.

### Option C: Only reclassify existing Streamlit DTA save as stable
Not recommended.
- Fails DTA-02 backend run/batch stabilization intent and leaves desktop/nav/report inconsistencies.

## Validation Architecture

Validation objective: deterministic, explainable DTA gatekeeping with pass/warn/fail semantics, where only critical integrity/context failures block stable save/export paths.

### 1) Validation Layers
1. Import-time dataset integrity (existing):
- Non-empty frame, required columns, numeric/monotonic temperature, signal usability, plausible unit warnings.

2. Pre-run stable eligibility gate (new DTA rules):
- Runs before DTA execution in batch/single pipelines.
- Blocks only critical issues.

3. Post-run method-context validation (new DTA rules):
- Validates saved processing/method context and peak outputs before final stable serialization.

4. Report-time consistency checks (existing + minor DTA additions):
- Ensure DTA records have coherent summary/rows/validation payload and stable status for stable path.

### 2) DTA Rule Catalog (proposed seed for 02-VALIDATION.md)
Critical fail rules (block stable save):
- `DTA-C01`: Temperature not strictly increasing / out-of-bounds.
- `DTA-C02`: Signal unusable (all non-numeric/empty).
- `DTA-C03`: Unsupported analysis/template mismatch (e.g., DTA run without DTA processing context).
- `DTA-C04`: Method context explicitly indicates invalid calibration/reference state when marked required by chosen template.

Warn rules (non-blocking):
- `DTA-W01`: Missing recommended metadata (`sample_mass`, `heating_rate`, etc.).
- `DTA-W02`: Signal unit unusual for DTA.
- `DTA-W03`: Missing or non-standard sign convention in method context.
- `DTA-W04`: No reference candidate detected for event-temperature anchoring.
- `DTA-W05`: Peak count is zero or very high given dataset length (quality advisory, not blocker).

Pass criteria:
- No critical issues, warnings optional.

### 3) Method-Context Checks (required by DTA-03)
Check fields in standardized processing payload:
- `processing.analysis_type == "DTA"`
- `processing.workflow_template_id in {"dta.general", "dta.thermal_events"}`
- `processing.method_context.sign_convention_label` present
- Signal pipeline/analysis steps recorded consistently with selected template
- Optional but recommended: calibration/reference acceptance fields when available

### 4) Output Contract
Validation object shape remains consistent with existing contract:
- `status`: `pass|warn|fail`
- `issues`: blocking findings
- `warnings`: advisory findings
- `checks`: machine-readable rule outputs for reports/diagnostics

### 5) Gating Policy
- Block stable result persistence only when `status == fail`.
- Keep warnings visible in UI, batch summary, and report appendix.
- Ensure batch summary `validation_status` mirrors validation result.

## Test Strategy

### Unit tests (new/updated)
- `tests/test_modality_registry.py`
  - stable types include DTA
  - DTA state key mapping (`dta_state_<dataset_key>`)
  - DTA adapter dataset eligibility (`DTA`, `UNKNOWN`)
- `tests/test_batch_runner.py`
  - DTA batch execution saved path
  - DTA blocked path on fail validation
  - DTA template handling (`dta.general`, `dta.thermal_events`)
- `tests/test_validation.py`
  - DTA-specific pass/warn/fail rule coverage and method-context checks
- `tests/test_result_serialization.py`
  - stable DTA serialization status and scientific-context semantics
- `tests/test_report_generator.py` / `tests/test_export_report.py`
  - DTA stable records appear under stable analyses
  - no DTA experimental disclaimer in stable flow

### Backend API integration tests
- `analysis/run` accepts DTA
- `workspace/{id}/batch/run` accepts DTA and returns normalized summary rows
- compare workspace accepts DTA from stable set
- exports include DTA stable records end-to-end

### UI tests / smoke checks
- Streamlit: DTA visible in primary nav (no preview gate), save message stable-scoped
- Desktop: DTA primary nav entry is enabled and can execute/save through backend
- Regression: DSC/TGA behavior unchanged

## Plan Decomposition Hints (Likely Waves)

Wave 1: Stable contract wiring
- Registry + state key + backend stable analysis set updates.
- Update tests that currently hardcode DSC/TGA-only stable set.

Wave 2: Backend DTA execution path
- Implement DTA executor in batch runner.
- Wire template defaults and method context for `dta.general` and `dta.thermal_events`.

Wave 3: DTA validation productionization
- Add DTA-specific validator branch and rule catalog.
- Integrate blocking/warning semantics with batch/single summary outputs.

Wave 4: Serialization/report stabilization
- Classify stable DTA records as `status="stable"`.
- Update DTA scientific context from experimental wording to stable wording.
- Verify report rendering sections for DTA quality.

Wave 5: UI promotion
- Streamlit nav/copy promotion and DTA page stable messaging.
- Desktop nav promotion plus enabled DTA workflow view.
- Final regression + export/report UX checks.

## Open Questions to Resolve During Planning
- Desktop DTA UX depth for Phase 2: parity with Streamlit DTA page vs minimal stable run/save flow.
- Exact `dta.thermal_events` defaults and how they differ from `dta.general` in method context.
- Which DTA validation warnings should be promoted to blockers for specific templates (if any).
- Whether to add DTA-specific report method table now or keep generic method summary in Phase 2.

## Recommended Planning Direction
Plan Phase 2 as a contract-first backend stabilization with synchronized UI promotion:
- Treat backend stable DTA execution + validation + serialization semantics as critical path.
- Treat desktop DTA view enablement as a required deliverable (not optional), but keep first iteration minimal if needed.
- Use explicit DTA rule IDs and machine-readable checks so 02-VALIDATION.md can map rules to tests and UAT directly.