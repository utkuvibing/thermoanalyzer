# ThermoAnalyzer Multi-Modal Expansion

## What This Is

ThermoAnalyzer is a vendor-independent analysis workbench currently centered on stable DSC/TGA workflows.  
This milestone expands the product into a multi-modal platform by adding production-grade XRD, XRF, FTIR, Raman, and stable DTA workflows without breaking the existing DSC/TGA core.

## Core Value

A scientist can load heterogeneous instrument data and get reproducible, traceable, scientifically defensible results from one unified workflow.

## Requirements

### Validated

- x Stable DSC analysis workflow exists in production codebase.
- x Stable TGA analysis workflow exists in production codebase.
- x Project archive and report/export flow exists for stable paths.
- x DTA analysis pipeline exists but is still marked experimental in product messaging and backend limits.

### Active

- [ ] Build a modality/plugin architecture so each analysis family can be integrated with consistent contracts.
- [ ] Promote DTA from experimental to stable in UI, backend, validation, and reporting.
- [ ] Add FTIR and Raman MVP workflows with robust import, preprocessing, peak/similarity analysis, and reporting.
- [ ] Add XRD MVP workflow for pattern processing and qualitative phase identification.
- [ ] Add XRF MVP workflow for spectrum processing and semi-quantitative element analysis.
- [ ] Generalize compare/report/export contracts to handle all stable modalities.

### Out of Scope

- Full Rietveld refinement in first XRD release - high complexity, separate advanced phase.
- Full FP-grade XRF quantification and advanced matrix corrections in first XRF release - separate advanced phase.
- End-to-end multi-modal ML fusion in initial delivery - deferred after stable modality foundations.

## Context

- Existing architecture is thermal-first and contains multiple DSC/TGA assumptions in backend batch and report layers.
- Data I/O is centralized in `core/data_io.py` and currently recognizes DSC/TGA/DTA/unknown.
- DTA processing and UI exist but desktop preview/stable messaging and backend execution paths still prioritize DSC/TGA.
- User provided a detailed roadmap document (`Thermoanalyzer Gelistirme Yol Haritasi.pdf`) with plugin architecture, format support targets, and algorithm references.

## Constraints

- **Compatibility**: Existing DSC/TGA production behavior must not regress - current users depend on it.
- **Traceability**: Every new modality must preserve processing context, validation context, and report provenance.
- **Incremental Delivery**: Start with MVP per modality, then advanced scientific capabilities in later phases.
- **Maintainability**: Avoid hard-coding modality logic across UI/backend; use shared contracts and registry patterns.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build modality/plugin contracts before adding major new analyzers | Prevent repeated ad-hoc wiring and future regressions | - Pending |
| Stabilize DTA before XRD/XRF heavy integration | Lowest-risk/high-value upgrade using existing processor code | - Pending |
| Deliver FTIR/Raman MVP before XRD/XRF advanced features | Faster user-visible expansion with existing preprocessing foundations | - Pending |
| Keep advanced Rietveld/FP and ML fusion out of MVP scope | Reduce delivery risk and keep phase goals testable | - Pending |

---
*Last updated: 2026-03-11 after gsd-new-project initialization*
