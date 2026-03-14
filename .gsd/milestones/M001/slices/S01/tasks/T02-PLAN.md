# T02: 01-foundation-contracts-and-execution-path 02

**Slice:** S01 — **Milestone:** M001

## Description

Migrate backend execution paths to registry-driven generic dispatch while preserving API compatibility.

Purpose: Deliver ARCH-04 without regressing existing DSC/TGA behavior, using the contract layer from Plan 01.
Output: A reusable execution engine plus endpoint refactors for single run, batch run, and compare workspace analysis_type validation.

## Must-Haves

- [ ] "Backend single-run and batch endpoints resolve stable analysis types through registry-backed generic dispatch instead of DSC/TGA-only branching."
- [ ] "Unsupported or unstable analysis types fail with explicit validation errors, not implicit fallthrough."
- [ ] "Compare workspace analysis type validation uses the stable registry set and remains backward compatible for existing DSC/TGA projects."

## Files

- `core/execution_engine.py`
- `backend/app.py`
- `backend/detail.py`
- `backend/models.py`
- `tests/test_backend_api.py`
- `tests/test_backend_batch.py`
- `tests/test_backend_details.py`
- `tests/test_backend_modality_dispatch.py`
