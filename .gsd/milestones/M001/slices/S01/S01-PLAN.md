# S01: Foundation Contracts And Execution Path

**Goal:** Establish the foundation contract and registry layer for stable modalities before touching backend routing.
**Demo:** Establish the foundation contract and registry layer for stable modalities before touching backend routing.

## Must-Haves


## Tasks

- [x] **T01: 01-foundation-contracts-and-execution-path 01** `est:45min`
  - Establish the foundation contract and registry layer for stable modalities before touching backend routing.

Purpose: Satisfy ARCH-01 first with a concrete, testable modality interface and explicit registration model that Phase 2+ can extend.
Output: New modality contract package, DSC/TGA adapter implementations, centralized stable state-key resolver, and contract tests.
- [x] **T02: 01-foundation-contracts-and-execution-path 02** `est:70min`
  - Migrate backend execution paths to registry-driven generic dispatch while preserving API compatibility.

Purpose: Deliver ARCH-04 without regressing existing DSC/TGA behavior, using the contract layer from Plan 01.
Output: A reusable execution engine plus endpoint refactors for single run, batch run, and compare workspace analysis_type validation.
- [x] **T03: 01-foundation-contracts-and-execution-path 03** `est:55min`
  - Lock Phase 1 regression parity and compatibility so the new execution architecture can ship safely.

Purpose: Satisfy ARCH-02 as a release gate by proving behavior parity and state compatibility after Plans 01-02.
Output: Dedicated parity tests, persistence compatibility assertions, and updated validation strategy mapping for ARCH-01/02/04.

## Files Likely Touched

- `core/modalities/__init__.py`
- `core/modalities/contracts.py`
- `core/modalities/adapters.py`
- `core/modalities/registry.py`
- `core/modalities/state_keys.py`
- `tests/test_modality_registry.py`
- `core/execution_engine.py`
- `backend/app.py`
- `backend/detail.py`
- `backend/models.py`
- `tests/test_backend_api.py`
- `tests/test_backend_batch.py`
- `tests/test_backend_details.py`
- `tests/test_backend_modality_dispatch.py`
- `tests/test_dsc_tga_parity.py`
- `tests/test_project_io.py`
- `tests/test_backend_api.py`
- `tests/test_backend_batch.py`
- `tests/test_backend_modality_dispatch.py`
- `.planning/phases/01-foundation-contracts-and-execution-path/01-VALIDATION.md`
