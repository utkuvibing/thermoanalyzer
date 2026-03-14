# Phase 1: Foundation Contracts and Execution Path - Context

**Gathered:** 2026-03-11  
**Status:** Ready for planning  
**Source:** Direct user request + PROJECT/REQUIREMENTS/ROADMAP alignment

<domain>
## Phase Boundary

This phase builds the shared modality contract and generic execution path required for all later modality work (DTA stabilization, FTIR/Raman, XRD, XRF), while preserving existing DSC/TGA behavior.

It does **not** include full feature delivery for new modalities; it only establishes the foundation that makes those phases safe and consistent.

</domain>

<decisions>
## Implementation Decisions

### Contract and Registry
- Introduce a modality contract that standardizes: import -> preprocess -> analyze -> serialize -> report hooks.
- Registry/discovery should be explicit and testable (no hidden global branching logic).
- Existing DSC and TGA implementations must be adapted to this contract in Phase 1.

### Backend Execution Path
- Remove DSC/TGA-only branching in stable run/batch paths and route through generic analysis-type handling.
- Keep backward compatibility for existing API payload shapes where possible.
- Block unsupported modality invocations with explicit validation errors instead of implicit fallthrough.

### Regression Safety
- Phase 1 must include regression tests for DSC/TGA behavior equivalence before and after refactor.
- Use incremental refactor strategy; do not rewrite the whole pipeline in one step.

### Claude's Discretion
- Internal naming conventions for contract interfaces and adapter classes.
- Exact module/file layout for registry and execution dispatcher.
- Whether to use a pure plugin loader or registry-first static mapping in this phase (as long as requirement outcomes hold).

</decisions>

<specifics>
## Specific Ideas

- Align with the previously researched direction: plugin/modality architecture as first-class foundation.
- Keep scientific context/provenance handling centralized to avoid each modality reinventing serialization rules.
- Make phase outputs execution-ready for immediate Phase 2 onboarding.

</specifics>

<deferred>
## Deferred Ideas

- Full Rietveld refinement (XRD advanced)
- Full FP quantitative XRF flow
- Multi-modal ML fusion features

</deferred>

---

*Phase: 01-foundation-contracts-and-execution-path*  
*Context gathered: 2026-03-11*
