# Phase 3 Research: FTIR and Raman MVP (03)

## Objective
Answer: What do we need to know to plan Phase 3 (FTIR and Raman MVP) well?

Scope: deliver stable FTIR/Raman workflows from import to preprocessing, peak/similarity analysis, save/compare, and export/report while preserving existing stable DSC/TGA/DTA behavior.

## Inputs Reviewed
- `.planning/phases/03-ftir-and-raman-mvp/03-CONTEXT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/STATE.md`
- `core/data_io.py`
- `core/modalities/*`
- `core/execution_engine.py`
- `core/batch_runner.py`
- `core/processing_schema.py`
- `core/preprocessing.py`
- `core/baseline.py`
- `core/peak_analysis.py`
- `core/validation.py`
- `core/result_serialization.py`
- `core/report_generator.py`
- `backend/app.py`
- `backend/detail.py`
- `backend/models.py`
- `backend/exports.py`
- `ui/compare_page.py`
- `ui/components/column_mapper.py`
- `desktop/electron/index.html`
- `desktop/electron/renderer.js`
- relevant tests under `tests/`

## Context-Locked Decisions (from 03-CONTEXT)
- Wavenumber-first axis expectation with warning-based review for ambiguity.
- Permissive import for recoverable structure plus explicit review warnings.
- JCAMP-DX MVP limited to single-spectrum core files.
- Modality ambiguity resolved by user confirmation at low confidence.
- Guided preprocessing with advanced toggle; default order `Smooth -> Baseline -> Normalize`.
- Top-N matching output with `0-100 + band` confidence and traceable evidence.
- Explicit no-match saved state (not forced auto-pick).
- Compare must be modality-specific (FTIR with FTIR, Raman with Raman).
- Export/report should include low-confidence runs with caution language.

## Current Baseline (What Exists Today)
- Stable modality system currently includes only `DSC`, `DTA`, `TGA` in `core/modalities/registry.py`; all stable API validation and compare defaults derive from this.
- `analysis_state_key` supports only DSC/DTA/TGA prefixes in `core/modalities/state_keys.py`.
- Generic execution plumbing already exists in `core/execution_engine.py`, but `core/batch_runner.py` implements executors only for DSC/TGA/DTA.
- Import engine (`core/data_io.py`) is thermal-centered (`temperature/signal/time` roles and DSC/TGA/DTA detection); no FTIR/Raman/JCAMP parser exists.
- Reusable preprocessing primitives exist:
  - smoothing/normalization/interpolation in `core/preprocessing.py`
  - baseline methods in `core/baseline.py`
  - peak utilities in `core/peak_analysis.py`
- Compare/report surfaces are partially modality-aware but still heavily thermal-assumptive:
  - Streamlit compare page is DSC/TGA-only.
  - Desktop copy/navigation and compare behavior center on DSC/DTA/TGA.
  - report generator has several DSC/TGA-specific branches and tables.

## Requirement Mapping (SPC-01..SPC-04)

### SPC-01: Import supports text/CSV + JCAMP-DX baseline formats
Current state:
- No FTIR/Raman modality in import type inference.
- No JCAMP parser path.
- column mapper offers only DSC/TGA/DTA.

Gap to close:
- Add FTIR/Raman inference and metadata-aware review warnings.
- Add JCAMP-DX single-spectrum parser and normalized spectrum payload.
- Add low-confidence modality confirmation path.
- Persist import confidence/warnings in metadata compatible with existing validation/report channels.

Planning note:
- Keep import normalization contract explicit for downstream processor compatibility:
  - axis array (wavenumber or Raman shift)
  - intensity array
  - axis unit + signal unit
  - inferred modality + confidence metadata

### SPC-02: Configurable preprocessing chain
Current state:
- building blocks exist but no spectral pipeline contract/templates.
- processing schema has no FTIR/Raman templates.

Gap to close:
- Extend processing schema with FTIR/Raman templates and section names.
- Implement guided defaults with advanced overrides matching context decisions.
- Ensure saved records preserve preprocessing method context for traceability.

Planning note:
- Reuse current `ensure_processing_payload` pattern instead of introducing parallel schemas.
- Add deterministic method-context keys for spectral runs to keep report/export stable.

### SPC-03: Peak detection + similarity matching with traceable scores
Current state:
- thermal peak detection exists; no spectral reference matching framework exists.
- no spectral library asset contract in core/backends.

Gap to close:
- define spectral peak extraction path and matching contract.
- introduce reference-library representation (MVP local asset format or embedded fixtures).
- produce Top-N output with normalized score, band, and evidence fields.
- support explicit no-match status with caution semantics.

Planning note:
- Keep matching strategy deterministic and auditable (for reportability).
- Avoid adding heavyweight external dependencies unless required; current stack can support MVP cosine/correlation matching via `numpy/scipy`.

### SPC-04: Save, modality-level compare, export/report inclusion
Current state:
- stable result serialization contract exists and is extensible.
- compare/report fronts still bias to thermal modalities and some DSC/TGA branches.

Gap to close:
- add stable FTIR/Raman record serializers and summaries.
- extend compare workspace eligibility and UI paths to modality-specific FTIR/Raman lanes.
- update export/report sections to include spectral summaries and caution handling for low-confidence/no-match.

Planning note:
- maintain existing stable-vs-experimental semantics by keeping FTIR/Raman MVP in stable path only when validation passes.

## Architecture Pattern Recommendations

1. Registry-first modality onboarding (same as Phase 1/2)
- Add stable `FTIR` and `RAMAN` entries in modality registry.
- add deterministic state-key prefixes (`ftir_state_`, `raman_state_`).
- keep execution dispatch through `run_single_analysis` / `run_batch_analysis`.

2. Import adapter layering
- keep `read_thermal_data` intact for thermal files.
- add spectral import helper(s) and route based on modality or inferred type.
- use shared metadata confidence fields so existing diagnostics/report plumbing works.

3. Spectral processing payload standardization
- extend `core/processing_schema.py`:
  - template catalogs for FTIR/Raman
  - spectral signal pipeline sections
  - analysis steps (`peak_detection`, `similarity_matching`)

4. Matching engine contract
- define clear input/output schema:
  - inputs: preprocessed spectrum + library candidates
  - outputs: ranked matches with score, confidence band, evidence pointers
- ensure row-level serialization can power CSV/report without custom one-off formatters.

5. Report-safe scientific context
- extend `core/result_serialization.py` scientific context builders for FTIR/Raman.
- keep caution language explicit for no-match/low-confidence runs as context requires.

## Do Not Hand-Roll
- do not fork stable execution path for FTIR/Raman; use existing registry/engine.
- do not introduce a second result-record contract; keep `make_result_record` shape.
- do not bypass `processing_schema`; spectral pipelines should be first-class there.
- do not silently drop low-confidence/no-match runs from reports.
- do not mix FTIR and Raman in one compare lane by default.

## Major Risks and Mitigations

1. Scope bleed into advanced spectroscopy features
- Risk: overextending MVP into complex chemometric stacks.
- Mitigation: keep to Top-N matching + traceable evidence and no-match semantics.

2. Import ambiguity and false modality assignment
- Risk: mislabeled runs causing invalid analysis.
- Mitigation: confidence gating + user confirmation on low-confidence inference.

3. Report regressions due to thermal assumptions
- Risk: FTIR/Raman records fail report generation or render poorly.
- Mitigation: targeted report tests and modality branches that preserve existing DSC/TGA behavior.

4. Compare UX inconsistency across Streamlit and desktop
- Risk: backend supports modalities but UIs still constrain to thermal assumptions.
- Mitigation: explicit plan tasks for both UI surfaces, not backend-only changes.

5. Test coverage gap for spectral contracts
- Risk: fragile rollout and hidden regressions.
- Mitigation: add modality dispatch, import, processing schema, matching serialization, and export/report tests.

## Validation Architecture

### Validation Goal
Guarantee stable FTIR/Raman outputs are traceable and report-safe while preserving existing stable modality behavior.

### Layered Gates
1. Import gate (SPC-01)
- parser structure validity
- recoverable vs unrecoverable malformed input handling
- confidence/warning persistence

2. Processing-context gate (SPC-02)
- required preprocessing steps recorded
- template id and method context presence

3. Analysis-output gate (SPC-03)
- ranked output schema validity
- confidence band and evidence fields present
- explicit no-match representation accepted as valid-but-cautioned output

4. Export/report gate (SPC-04)
- stable record can be serialized, flattened, and rendered in DOCX/CSV
- low-confidence/no-match caution text appears as required

### Nyquist-Oriented Sampling Plan
- quick verification after each task commit:
  - focused spectral + modality dispatch tests
- full verification after each wave:
  - full backend/core/report regression suite

### Minimal Rule Seeds
- `SPC-C01`: unsupported or unrecoverable spectral file format -> fail
- `SPC-C02`: missing axis or intensity payload after import -> fail
- `SPC-C03`: missing similarity result schema fields for saved stable result -> fail
- `SPC-W01`: low import confidence requiring user review -> warn
- `SPC-W02`: low confidence/no-match analytical outcome -> warn with caution

## Test Strategy (Phase 3)

### New or Updated Test Areas
- `tests/test_data_io.py`
  - FTIR/Raman inference and warning behavior
  - JCAMP single-spectrum import normalization
- `tests/test_processing_schema.py`
  - FTIR/Raman template support and step persistence
- `tests/test_modality_registry.py`
  - stable registry/state-key includes FTIR/Raman
- `tests/test_backend_modality_dispatch.py`
  - API accepts FTIR/Raman stable analysis_type
- `tests/test_batch_runner.py`
  - FTIR/Raman executor outcomes and summary rows
- `tests/test_validation.py`
  - spectral validation pass/warn/fail rules
- `tests/test_result_serialization.py`
  - FTIR/Raman stable record shape + scientific context
- `tests/test_backend_exports.py`, `tests/test_report_generator.py`, `tests/test_export_report.py`
  - FTIR/Raman inclusion in export/report and caution handling

### Regression Guard
- keep existing DSC/TGA/DTA tests green as release gate for this phase.

## Suggested Plan Decomposition (for Planner)

Wave 1 (foundation and contracts)
- registry + state key + processing schema extension for FTIR/Raman.
- import contract scaffolding and type inference plumbing.

Wave 2 (import + preprocessing implementation)
- text/CSV + JCAMP single-spectrum import.
- preprocessing chain execution with guided defaults + advanced overrides.

Wave 3 (analysis and persistence)
- peak extraction + similarity matching engine.
- stable serializers, validation rules, and backend run/batch integration.

Wave 4 (compare/report + hardening)
- Streamlit + desktop compare/report modality updates.
- export/report narrative and caution handling.
- full regression sweep and gap closure.

## Recommendation
Use an incremental contract-first rollout:
- extend registry/schema first,
- deliver import + preprocessing next,
- then matching + serialization,
- finish with compare/report integration and regression hardening.

This ordering minimizes risk of partial modality support and aligns directly with SPC-01..SPC-04 plus the context decisions locked in discuss-phase.