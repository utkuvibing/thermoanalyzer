# T03: 01-foundation-contracts-and-execution-path 03

**Slice:** S01 — **Milestone:** M001

## Description

Lock Phase 1 regression parity and compatibility so the new execution architecture can ship safely.

Purpose: Satisfy ARCH-02 as a release gate by proving behavior parity and state compatibility after Plans 01-02.
Output: Dedicated parity tests, persistence compatibility assertions, and updated validation strategy mapping for ARCH-01/02/04.

## Must-Haves

- [ ] "DSC/TGA single-run and batch outputs remain baseline-equivalent after registry/dispatch refactor for stable workflows."
- [ ] "Project archive save/load still restores existing dsc_state_* and tga_state_* data without compatibility breaks."
- [ ] "Phase 1 has explicit automated regression gates that fail on execution-path or compatibility drift."

## Files

- `tests/test_dsc_tga_parity.py`
- `tests/test_project_io.py`
- `tests/test_backend_api.py`
- `tests/test_backend_batch.py`
- `tests/test_backend_modality_dispatch.py`
- `.planning/phases/01-foundation-contracts-and-execution-path/01-VALIDATION.md`
