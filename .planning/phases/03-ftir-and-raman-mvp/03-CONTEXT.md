# Phase 3: FTIR and Raman MVP - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver stable FTIR/Raman workflows from import through preprocessing, analysis, save/compare, and export/report inside existing stable product flows. This phase clarifies implementation behavior for that scope only; new capabilities outside FTIR/Raman MVP remain out of scope.

</domain>

<decisions>
## Implementation Decisions

### Import Acceptance Policy
- Default spectral axis expectation is wavenumber-first (cm^-1), with warning-based review when metadata or structure is ambiguous.
- Partially malformed text/CSV imports should be accepted when core numeric structure is recoverable, but marked review-required with explicit warnings.
- JCAMP-DX MVP scope is single-spectrum core support first; advanced/multi-spectrum variants should be explicitly marked unsupported in this phase.
- FTIR vs Raman modality resolution should use auto-inference with explicit user confirmation when confidence is low.

### Preprocessing Experience
- Stable MVP should provide guided defaults with an advanced toggle, not fully manual-first controls.
- Default processing chain order is Smooth -> Baseline -> Normalize.
- Domain-sensible preprocessing defaults should be prefilled but remain editable by users.
- Preprocessing settings should persist per saved run for traceability, with reuse as a starting point allowed.

### Similarity and Evidence Presentation
- Primary analysis output should be Top-N ranked candidate matches, not single-only or pass/fail-only outputs.
- Similarity confidence should be shown as normalized 0-100 score plus qualitative banding (high/medium/low).
- Each candidate should include traceable evidence by default: key-peak agreement plus overlay view.
- Low-confidence outcomes should produce explicit no-match state (saved with transparent limitations), not forced auto-pick or hard-block behavior.

### Save, Compare, and Export/Report Behavior
- Comparison should be modality-specific by default (FTIR with FTIR, Raman with Raman).
- Saved result summaries should emphasize sample identity, processing context/template, and top-match confidence.
- Export/report default depth should be balanced scientific summary (processing context + top candidates + confidence bands + primary evidence artifact).
- Low-confidence/no-match runs should be included in export/report outputs with explicit caution/limitation language.

### Claude's Discretion
- Exact UX layout and wording for guided vs advanced preprocessing controls.
- Exact threshold boundaries used for confidence band labels.
- Exact table/figure composition details for balanced scientific report sections.

</decisions>

<specifics>
## Specific Ideas

No additional external product references were added beyond the decisions above; implementation can follow existing product language/style conventions.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/preprocessing.py`: reusable smoothing/normalization/interpolation primitives for spectral pipelines.
- `core/baseline.py`: baseline-correction method catalog (asls/airpls/modpoly/imodpoly/snip/rubberband/linear/spline) suitable for configurable preprocessing chains.
- `core/peak_analysis.py`: reusable peak detection/characterization primitives that can inform spectral peak workflows.
- `core/modalities/*` + `core/execution_engine.py`: stable modality registry + generic single/batch execution paths already in place for onboarding new stable types.

### Established Patterns
- Stable workflows are registry-driven (`require_stable_modality`, `stable_analysis_types`) and use deterministic analysis-state key patterns.
- Processing payloads are normalized through `core/processing_schema.py` with template IDs, signal pipeline blocks, analysis steps, and method context.
- Stable outputs use normalized result records with `summary`, `rows`, `processing`, `validation`, `provenance`, and `scientific_context`.

### Integration Points
- Import path: `core/data_io.py` and `backend/app.py:/dataset/import` currently thermal-oriented (`temperature/signal/time`, DSC/TGA/DTA inference) and will need FTIR/Raman-compatible extensions.
- UI import mapping: `ui/components/column_mapper.py` is currently limited to DSC/TGA/DTA type choices.
- Compare/output surfaces: backend compare workspace supports registry-driven analysis types, but Streamlit and desktop compare/nav copy are still largely DSC/TGA/DTA-oriented and need FTIR/Raman alignment.
- Reporting/export: `backend/exports.py`, `core/result_serialization.py`, and `core/report_generator.py` provide existing artifact paths that need FTIR/Raman modality-aware summary/evidence content.

</code_context>

<deferred>
## Deferred Ideas

None - discussion stayed within Phase 3 scope.

</deferred>

---

*Phase: 03-ftir-and-raman-mvp*
*Context gathered: 2026-03-12*
