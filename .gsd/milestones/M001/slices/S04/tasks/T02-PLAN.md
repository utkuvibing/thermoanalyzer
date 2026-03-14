# T02: 04-xrd-mvp 02

**Slice:** S04 — **Milestone:** M001

## Description

Implement XRD preprocessing and robust peak extraction after import/registry foundations are established.

Purpose: satisfy XRD-02 with template-driven XRD preprocessing plus deterministic peak detection and validation context requirements.
Output: processing schema extensions, batch/execution engine XRD path, and processing/validation tests.

## Must-Haves

- [ ] "XRD processing is template-driven with reproducible defaults for axis normalization, smoothing, baseline correction, and peak extraction."
- [ ] "Stable run and batch execution include robust XRD peak detection controls (prominence, distance, width) with deterministic outputs."
- [ ] "Validation gates require processing and peak-detection context before stable artifact eligibility."

## Files

- `core/processing_schema.py`
- `core/batch_runner.py`
- `core/execution_engine.py`
- `core/validation.py`
- `tests/test_processing_schema.py`
- `tests/test_batch_runner.py`
- `tests/test_validation.py`
