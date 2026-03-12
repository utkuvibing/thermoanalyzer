# Requirements: ThermoAnalyzer Multi-Modal Expansion

**Defined:** 2026-03-11  
**Core Value:** A scientist can load heterogeneous instrument data and get reproducible, traceable, scientifically defensible results from one unified workflow.

## v1 Requirements

### Architecture and Platform

- [ ] **ARCH-01**: System provides a modality registry/contract so each analysis family exposes standardized import, preprocess, analyze, serialize, and report hooks.
- [ ] **ARCH-02**: Existing DSC/TGA features continue to work without behavior regressions after architecture refactor.
- [ ] **ARCH-03**: Processing payload, method context, and provenance are preserved consistently across all new stable modalities.
- [ ] **ARCH-04**: Backend batch execution and single-run APIs accept stable modalities via generic analysis type handling.

### DTA Stabilization

- [x] **DTA-01**: DTA is available as stable workflow in Streamlit and desktop navigation (not preview-locked).
- [x] **DTA-02**: DTA is accepted by backend run/batch/report paths where stable analyses are supported.
- [x] **DTA-03**: DTA validation rules are productionized with pass/warn/fail semantics and method context checks.
- [x] **DTA-04**: DTA outputs are included in stable export/report artifacts with modality-appropriate summaries.

### FTIR and Raman MVP

- [x] **SPC-01**: FTIR/Raman import supports open text/CSV plus JCAMP-DX baseline formats for MVP.
- [x] **SPC-02**: FTIR/Raman preprocessing supports smoothing, baseline correction, normalization, and configurable pipelines.
- [x] **SPC-03**: FTIR/Raman analysis supports peak detection and similarity matching against reference libraries.
- [x] **SPC-04**: FTIR/Raman results can be saved, compared at modality level, and exported/reported.

### XRD MVP

- [ ] **XRD-01**: XRD import supports MVP formats (`.xy`, `.dat`, `.cif`) with normalized internal representation.
- [ ] **XRD-02**: XRD pipeline supports baseline/preprocess and robust peak detection.
- [ ] **XRD-03**: XRD analysis provides qualitative phase candidate matching with traceable confidence outputs.
- [ ] **XRD-04**: XRD results can be saved and included in report/export flows with method context.

### XRF MVP

- [ ] **XRF-01**: XRF import supports MVP formats (CSV plus limited HDF5/NeXus path where available).
- [ ] **XRF-02**: XRF pipeline supports baseline/preprocess and line/peak deconvolution for element screening.
- [ ] **XRF-03**: XRF analysis provides semi-quantitative concentration estimates with explicit confidence/limitations.
- [ ] **XRF-04**: XRF results can be saved and included in report/export flows with method context.

### Quality, Validation, and Reporting

- [ ] **QUAL-01**: Test suite includes regression coverage for existing DSC/TGA and new stable modalities.
- [ ] **QUAL-02**: Each stable modality has validation gates that can block invalid datasets from stable reporting.
- [ ] **QUAL-03**: Report generator and CSV/XLSX summaries become modality-aware without DSC/TGA-only assumptions.
- [ ] **QUAL-04**: User-facing workflow guidance reflects stable vs experimental scope accurately across Streamlit and desktop.

## v2 Requirements

### XRD Advanced

- **XRD-A01**: Rietveld refinement workflow with fit quality diagnostics and phase quantification.

### XRF Advanced

- **XRF-A01**: Fundamental-parameters based quantitative workflow with matrix-effect handling.

### Multi-Modal Intelligence

- **ML-01**: Cross-modality feature fusion for assisted interpretation and anomaly surfacing.
- **ML-02**: Material-class recommendation models from DTA/DSC + spectral + diffraction evidence.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full GSAS-II/Rietveld production UX in MVP | Too large for initial modality onboarding; requires dedicated advanced phase |
| Full FP-calibrated XRF quant as default MVP path | Needs calibration strategy and heavy scientific validation |
| Real-time cloud collaboration stack | Not required for current desktop/streamlit product trajectory |
| Hardware control/instrument driver integration | Current project scope is data analysis, not instrument orchestration |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ARCH-01 | Phase 1 | Completed (2026-03-11) |
| ARCH-02 | Phase 1 | Completed (2026-03-11) |
| ARCH-03 | Phase 6 | Pending |
| ARCH-04 | Phase 1 | Completed (2026-03-11) |
| DTA-01 | Phase 2 | Complete |
| DTA-02 | Phase 2 | Complete |
| DTA-03 | Phase 2 | Complete |
| DTA-04 | Phase 2 | Complete |
| SPC-01 | Phase 3 | Complete |
| SPC-02 | Phase 3 | Complete |
| SPC-03 | Phase 3 | Complete |
| SPC-04 | Phase 3 | Complete |
| XRD-01 | Phase 4 | Pending |
| XRD-02 | Phase 4 | Pending |
| XRD-03 | Phase 4 | Pending |
| XRD-04 | Phase 4 | Pending |
| XRF-01 | Phase 5 | Pending |
| XRF-02 | Phase 5 | Pending |
| XRF-03 | Phase 5 | Pending |
| XRF-04 | Phase 5 | Pending |
| QUAL-01 | Phase 6 | Pending |
| QUAL-02 | Phase 6 | Pending |
| QUAL-03 | Phase 6 | Pending |
| QUAL-04 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0

---
*Requirements defined: 2026-03-11*  
*Last updated: 2026-03-11 after roadmap creation*
