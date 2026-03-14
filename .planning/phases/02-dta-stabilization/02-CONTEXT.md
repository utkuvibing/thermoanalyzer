# Phase 2: DTA Stabilization - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Promote DTA from preview/experimental behavior to a stable first-class workflow across Streamlit and desktop navigation, backend run/batch execution, validation gates, and export/report outputs.

Scope is limited to stabilizing existing DTA capability inside current product boundaries; no new modality capabilities are added in this phase.

</domain>

<decisions>
## Implementation Decisions

### Backend Stability Contract
- DTA becomes a first-class stable analysis type in modality registry and execution-engine dispatch.
- Stable DTA dataset eligibility is `DTA` and `UNKNOWN`.
- Stable DTA run/batch APIs use default template `dta.general` while allowing explicit catalog selection (including `dta.thermal_events`).
- DTA analysis state uses dedicated deterministic keys: `dta_state_<dataset_key>`.

### UI Promotion and Messaging
- Streamlit promotes DTA into primary stable navigation (not behind preview toggle).
- Desktop promotes DTA into primary navigation with an enabled stable view; preview-locked DTA button is retired.
- DTA copy/messaging is updated from experimental wording to stable-scope wording.
- Kinetics and deconvolution remain preview-locked; only DTA is promoted in Phase 2.

### Validation and Reporting Behavior
- Add DTA-specific stable validation rules with explicit pass/warn/fail semantics and method-context-aware checks.
- Stable DTA blocks only on critical context/integrity gaps; non-critical issues remain warnings.
- DTA serialized results are classified as `stable` (not `experimental`) for Phase 2 stable flows.
- DTA is included in standard stable export/report outputs without experimental warning sections for DTA records.

### Claude's Discretion
- Exact threshold values and rule-level implementation details for DTA validation checks, as long as critical-gap blocking policy is preserved.
- Exact UI layout/placement details for primary DTA entries in Streamlit and desktop while honoring existing visual patterns.
- Exact report narrative templates for DTA stable summaries, as long as they are modality-appropriate and integrated with existing report structure.

</decisions>

<specifics>
## Specific Ideas

No additional freeform product references were provided beyond the locked choices above; implement using existing architecture and conventions.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/modalities/registry.py`, `core/modalities/adapters.py`, `core/modalities/state_keys.py`: stable modality contract/registry pattern ready for DTA onboarding.
- `core/execution_engine.py`: registry-backed single and batch execution paths already used by stable modalities.
- `core/processing_schema.py`: DTA workflow templates already defined (`dta.general`, `dta.thermal_events`).
- `ui/dta_page.py`: full DTA pipeline UI and result persistence exists today (currently experimental messaging/status).

### Established Patterns
- Stable modality gating is centralized through `require_stable_modality()` and `stable_analysis_types()`.
- Backend endpoints normalize unsupported stable analysis types to explicit allowed-set errors.
- Result/report pipeline separates records by `status` (`stable` vs `experimental`) via `partition_results_by_status`.
- Desktop/Streamlit currently use explicit stable-scope messaging and preview-module grouping to communicate support levels.

### Integration Points
- Streamlit: `app.py` primary nav + preview toggle blocks where DTA currently lives.
- Desktop: `desktop/electron/index.html` preview group and `desktop/electron/renderer.js` nav labels/toggle/eligibility rules.
- Backend: `backend/app.py`, `backend/detail.py`, and `core/execution_engine.py` for stable run/batch/compare handling.
- Reporting/export: `core/result_serialization.py`, `core/report_generator.py`, and `backend/exports.py`.

</code_context>

<deferred>
## Deferred Ideas

None - discussion stayed within Phase 2 scope.

</deferred>

---

*Phase: 02-dta-stabilization*
*Context gathered: 2026-03-12*
