# Phase 4 Research: XRD MVP (04)

## Objective
Answer: What do we need to know to plan Phase 4 (XRD MVP) well?

Phase goal from roadmap: deliver stable XRD workflows for import, preprocessing, robust peak extraction, qualitative phase candidate matching, and save/export/report integration.

## Inputs Reviewed
- `.planning/REQUIREMENTS.md`
- `.planning/STATE.md`
- `.planning/ROADMAP.md`
- `.planning/PROJECT.md`
- `.planning/phases/01-foundation-contracts-and-execution-path/01-RESEARCH.md`
- `.planning/phases/03-ftir-and-raman-mvp/03-RESEARCH.md`
- `.planning/phases/03-ftir-and-raman-mvp/03-01-PLAN.md`
- `.planning/phases/03-ftir-and-raman-mvp/03-02-PLAN.md`
- `.planning/phases/03-ftir-and-raman-mvp/03-03-PLAN.md`
- Core implementation seams:
  - `core/modalities/*`
  - `core/execution_engine.py`
  - `core/batch_runner.py`
  - `core/data_io.py`
  - `core/processing_schema.py`
  - `core/validation.py`
  - `core/result_serialization.py`
  - `core/report_generator.py`
  - `backend/app.py`, `backend/detail.py`, `backend/models.py`
  - `ui/compare_page.py`, `ui/components/column_mapper.py`, `ui/home.py`
- Relevant tests under `tests/` (registry, dispatch, batch runner, validation, data I/O, exports/report)

Pattern check:
- `.claude/skills` and `.agents/skills` do not exist in this repository, so no repo-local skill patterns were available.

## Current Baseline (What Exists Before Phase 4)
- Stable modality contract/registry path is already established and used by backend run/batch dispatch.
- Stable modalities currently are `DSC`, `DTA`, `FTIR`, `RAMAN`, `TGA`.
- `XRD` is currently unsupported in:
  - modality registry,
  - deterministic state-key mapping,
  - batch execution (`execute_batch_template`),
  - processing schema catalogs,
  - validation workflow branches,
  - serialization/report modality branches.
- Data import currently supports thermal plus FTIR/RAMAN/JCAMP MVP, but not `.xy`, `.dat`, `.cif` XRD pathways.
- Existing tests explicitly assert `XRD` is unsupported in modality registry.

Implication: this phase is not a greenfield rewrite. It is a registry-first modality onboarding task, following the Phase 3 pattern.

## Requirement Mapping (XRD-01..XRD-04)

### XRD-01: Import `.xy`, `.dat`, `.cif` with normalized internal representation
Current gap:
- No XRD type in `read_thermal_data` or column mapper options.
- No parser path for `.xy/.dat/.cif`.

Planning guidance:
- Keep `ThermalDataset` contract (standardized columns `temperature` + `signal`) and encode XRD axis semantics in metadata/method context.
- Define XRD axis metadata explicitly:
  - `xrd_axis_role` (`two_theta` or `d_spacing`)
  - `xrd_axis_unit` (`deg`, `angstrom`)
  - `xrd_wavelength_angstrom` (default and provenance)
- Parse `.xy/.dat` as measured pattern inputs.
- Scope `.cif` MVP explicitly as a reference-source path (phase candidate library input), not full Rietveld-grade structural refinement.
- Use Phase-3-style bounded parser policy: explicit unsupported messages for out-of-scope CIF variants.

### XRD-02: Baseline/preprocess + robust peak detection
Current gap:
- No XRD template catalog and no XRD processing branch.

Planning guidance:
- Add XRD workflow templates in processing schema with explicit defaults.
- Add an XRD execution path in batch runner with these steps:
  - axis normalization/sort
  - smoothing
  - baseline/background estimation
  - baseline-corrected signal
  - peak detection with deterministic settings and top-N constraints
- Reuse proven payload pattern (`ensure_processing_payload`, `update_processing_step`, `update_method_context`).
- Do not use the current minimal spectral local-maxima helper as-is for XRD robustness. Use `scipy.signal.find_peaks`-grade logic with prominence/width/distance controls.

### XRD-03: Qualitative phase candidate matching with traceable confidence
Current gap:
- No XRD matching contract/output schema.

Planning guidance:
- Implement deterministic qualitative matching (not quantification, not Rietveld):
  - observed peaks vs candidate reference peaks
  - position tolerance and optional intensity weighting
  - top-N candidate ranking
- Persist traceable evidence fields per candidate:
  - shared peak count
  - weighted overlap ratio
  - mean |delta 2theta|
  - major unmatched reference peaks
  - metric/tolerance parameters used
- Keep confidence output explicit and cautious (`high/medium/low/no_match`) with no forced identification.
- Preserve Phase-3 no-match pattern: valid saved output with caution semantics.

### XRD-04: Save + report/export inclusion with method context
Current gap:
- No XRD stable registry entry, state key, serializer, or report method summary branch.

Planning guidance:
- Add XRD as stable modality in registry and adapters with dataset eligibility (`XRD`, `UNKNOWN`).
- Add deterministic state key (`xrd_state_{dataset_key}`).
- Add XRD stable record serialization with:
  - summary fields (`peak_count`, `match_status`, `top_phase`, `top_score`, `confidence_band`)
  - rows of ranked phase candidates with evidence payload
  - processing/provenance/validation/review blocks
- Extend report/export flattening and method-summary rendering to include XRD-specific processing context and caution language.

## Standard Stack
- Keep current stack and dependencies for MVP:
  - `numpy`, `pandas`, `scipy`, `pybaselines` already available.
  - backend/UI/report stack unchanged.
- Avoid adding heavy crystallography dependencies in first pass unless CIF coverage goals cannot be met with bounded parser rules.

Decision gate:
- If CIF reality in target datasets requires full crystallographic simulation, decide early whether to:
  - add a dedicated dependency, or
  - narrow CIF support to reflection-list CIF with explicit unsupported messaging for the rest.

## Architecture Patterns to Reuse
1. Registry-first onboarding
- Add XRD to `core/modalities/registry.py`, `core/modalities/adapters.py`, and `core/modalities/state_keys.py` first.

2. Contract-preserving processing payload
- Extend `core/processing_schema.py` with XRD sections/templates, not ad-hoc payload fields.

3. Batch kernel as source of truth
- Implement XRD in `core/batch_runner.py` and let backend run/batch dispatch flow through existing execution engine.

4. Caution-safe stable serialization
- Follow FTIR/RAMAN pattern where no-match or low-confidence can still be valid stable outputs with warnings.

5. Report/export inclusion through normalized records
- Keep all downstream artifacts fed from normalized result records rather than modality-specific side channels.

## Proposed XRD Data Contract (MVP)
- Dataset contract (imported pattern):
  - `data.temperature`: canonical x-axis numeric vector (2theta preferred)
  - `data.signal`: intensity vector
  - `data_type`: `XRD`
  - `units.temperature`: `deg` for 2theta or `angstrom` when d-spacing preserved
  - `units.signal`: `counts` or `a.u.`
- Metadata contract additions:
  - `xrd_axis_role`
  - `xrd_axis_unit`
  - `xrd_wavelength_angstrom`
  - `xrd_geometry` (optional)
  - `reference_library` or `xrd_reference_library` (candidate peak lists and IDs)

Recommendation:
- Canonicalize to 2theta internally when possible. Store original-axis provenance in metadata.

## Validation Architecture

### Validation Goal
Ensure XRD stable outputs are traceable, reproducible, and caution-safe without overclaiming qualitative phase identification.

### Layered Gates
1. Import gate (XRD-01)
- Required standardized columns and numeric coercion.
- Axis role/unit recognition and wavelength context presence.
- `.cif` support boundary enforcement with explicit unsupported messages.

2. Processing-context gate (XRD-02)
- Workflow template id/label/version recorded.
- Baseline/preprocessing and peak detection context recorded.
- Peak detection parameters validated (`prominence`, `distance`, `width`, bounds).

3. Analysis-output gate (XRD-03)
- Ranked candidate schema validity.
- Confidence band and evidence fields present.
- No-match output accepted as valid cautionary record.

4. Artifact gate (XRD-04)
- Stable record serializes and flattens for CSV/XLSX.
- DOCX/PDF report sections render XRD method summary and caution semantics.

### Rule Seed Set (for planner/test authoring)
- `XRD-C01`: Missing or non-numeric x/signal columns after import -> fail.
- `XRD-C02`: Unsupported/invalid XRD template id for stable reporting -> fail.
- `XRD-C03`: Missing peak-detection or matching context for saved XRD stable result -> fail.
- `XRD-C04`: Matched output missing `top_phase_id` or evidence payload -> fail.
- `XRD-W01`: CIF parsed with partial metadata or fallback assumptions -> warn.
- `XRD-W02`: Reference library empty/limited -> warn with caution state.
- `XRD-W03`: Match status is `no_match` or `low_confidence` -> warn, but keep stable save valid.

### Nyquist Sampling Plan
- After each task commit: targeted tests on touched XRD subsystem.
- After each wave: full regression (`pytest -q`) to guard DSC/TGA/DTA/FTIR/RAMAN.

## Do Not Hand-Roll
- Do not fork backend run/batch endpoints for XRD-specific dispatch.
- Do not invent a second record/export schema for XRD.
- Do not bypass `processing_schema` for XRD method context.
- Do not silently convert no-match to hard failures or forced matches.
- Do not promise full-Rietveld/CIF-universal support in MVP.

## Major Risks and Early Decisions
1. CIF scope ambiguity
- Risk: some CIF files lack directly usable reflection lists.
- Decision needed in planning: bounded reflection-list support vs new dependency.

2. Axis convention drift
- Risk: mixed 2theta/d-spacing assumptions break matching.
- Mitigation: canonical internal axis + explicit metadata provenance.

3. False confidence in phase identification
- Risk: qualitative matches interpreted as definitive phase proof.
- Mitigation: enforce caution wording and confidence-band semantics in validation/report layers.

4. Regression in stable modality contract
- Risk: adding XRD breaks current stable type assumptions/tests.
- Mitigation: update registry/state-key/dispatch tests first and keep sorted stable list deterministic.

5. UI scope mismatch
- Risk: backend supports XRD while workflow guidance still implies DSC/TGA-centric stable path.
- Mitigation: ensure compare workspace/type selectors and report/export UX expose XRD cleanly; document any deferred full-page UX work.

## Test Strategy (Planner-Ready)
- `tests/test_modality_registry.py`
  - stable type list includes `XRD`
  - state key mapping includes `xrd_state_*`
  - `XRD` is no longer unknown/unsupported.
- `tests/test_backend_modality_dispatch.py`
  - `/analysis/run` and `/batch/run` accept XRD
  - dataset eligibility errors are explicit.
- `tests/test_data_io.py`
  - `.xy/.dat` normalized import
  - bounded `.cif` import behavior (supported subset + explicit unsupported cases).
- `tests/test_processing_schema.py`
  - XRD templates and sections.
- `tests/test_batch_runner.py`
  - deterministic XRD preprocessing/peak extraction/matching.
  - no-match caution output.
- `tests/test_validation.py`
  - XRD pass/warn/fail rules and caution states.
- `tests/test_result_serialization.py`
  - XRD stable record shape and scientific context.
- `tests/test_backend_details.py`, `tests/test_backend_workflow.py`
  - compare workspace XRD lane behavior.
- `tests/test_backend_exports.py`, `tests/test_export_report.py`, `tests/test_report_generator.py`
  - XRD report/export rendering and caution language.

## Suggested Plan Decomposition for Phase 4

Wave 1: Contracts + import foundation (XRD-01)
- Registry/adapters/state keys for XRD.
- Column mapper and import pathways for `.xy/.dat/.cif` MVP.
- Dispatch and import tests first.

Wave 2: Processing + peak extraction (XRD-02)
- XRD processing schema templates.
- Batch runner XRD preprocessing and robust peak detection.
- Validation context for processing requirements.

Wave 3: Phase matching + stable record shape (XRD-03)
- Deterministic qualitative matching engine.
- XRD serialization and validation enrichment for confidence/evidence.
- No-match/low-confidence caution semantics.

Wave 4: Compare/export/report integration and hardening (XRD-04)
- Compare workspace and method summary/report branches for XRD.
- Export preparation and artifact coverage.
- Full regression sweep and validation map completion.

## Recommendation
Plan Phase 4 as a strict extension of the existing stable-modality architecture, not as a special-case branch.

Most important planning choices to lock before execution:
1. Exact CIF MVP boundary and failure messaging.
2. Canonical XRD axis/wavelength representation contract.
3. Confidence/evidence schema for qualitative phase matching.
4. Caution policy for no-match and low-confidence outcomes.

If those four are decided up front, `XRD-01..XRD-04` can be implemented with the same low-regression, wave-based pattern proven in Phase 3.
