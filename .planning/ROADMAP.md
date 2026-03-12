# Roadmap: ThermoAnalyzer Multi-Modal Expansion

## Overview

This roadmap expands ThermoAnalyzer from a thermal-first tool into a stable multi-modal analysis platform while protecting existing DSC/TGA production behavior. Phases are ordered by dependency: foundation contracts first, then modality delivery, then cross-modality quality/reporting hardening.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation Contracts and Execution Path** - Establish plugin contracts and generic backend execution without DSC/TGA regressions. (completed 2026-03-11)
- [x] **Phase 2: DTA Stabilization** - Promote DTA to fully stable UX, validation, backend, and reporting behavior. (completed 2026-03-12)
- [ ] **Phase 3: FTIR and Raman MVP** - Deliver stable spectral workflows for import, preprocessing, analysis, and export.
- [ ] **Phase 4: XRD MVP** - Deliver stable diffraction workflow with qualitative phase identification.
- [ ] **Phase 5: XRF MVP** - Deliver stable elemental screening workflow with semi-quant outputs.
- [ ] **Phase 6: Cross-Modality Quality and Reporting Hardening** - Enforce provenance, validation gates, regression coverage, and modality-aware guidance/reporting across all stable modalities.

## Phase Details

### Phase 1: Foundation Contracts and Execution Path
**Goal**: New and existing analysis families run through a shared contract and generic backend execution path while preserving DSC/TGA behavior.
**Depends on**: Nothing (first phase)
**Requirements**: ARCH-01, ARCH-02, ARCH-04
**Success Criteria** (what must be TRUE):
  1. A modality can be registered through one contract and becomes runnable through the same import, preprocess, analyze, serialize, and report hook lifecycle.
  2. Existing DSC/TGA workflows produce baseline-equivalent results after refactor (no behavior regressions).
  3. Backend single-run and batch execution paths accept stable analysis types through generic handling instead of DSC/TGA-only branching.
**Plans**: TBD

### Phase 2: DTA Stabilization
**Goal**: DTA becomes a first-class stable workflow across UI, backend execution, validation, and export/report behavior.
**Depends on**: Phase 1
**Requirements**: DTA-01, DTA-02, DTA-03, DTA-04
**Success Criteria** (what must be TRUE):
  1. Users can start DTA from both Streamlit and desktop navigation without preview-only restrictions.
  2. DTA datasets are accepted in stable backend run, batch, and report paths.
  3. DTA validation applies production pass/warn/fail rules with method-context checks that block invalid stable reporting cases.
  4. DTA outputs appear in stable export/report artifacts with modality-appropriate summaries.
**Plans**: TBD

### Phase 3: FTIR and Raman MVP
**Goal**: Users can run end-to-end FTIR/Raman analysis from import to exported results in stable workflows.
**Depends on**: Phase 1
**Requirements**: SPC-01, SPC-02, SPC-03, SPC-04
**Success Criteria** (what must be TRUE):
  1. Users can import FTIR/Raman datasets from text/CSV and JCAMP-DX MVP formats into normalized internal structures.
  2. Users can run configurable preprocessing chains including smoothing, baseline correction, and normalization.
  3. Users can run peak detection and similarity matching against reference libraries with traceable scores.
  4. FTIR/Raman results can be saved, compared at modality level, and included in export/report outputs.
**Plans**: TBD

### Phase 4: XRD MVP
**Goal**: Users can run XRD pattern workflows for preprocessing, peak extraction, and qualitative phase candidate identification.
**Depends on**: Phase 1
**Requirements**: XRD-01, XRD-02, XRD-03, XRD-04
**Success Criteria** (what must be TRUE):
  1. Users can import `.xy`, `.dat`, and `.cif` XRD files into one normalized internal representation.
  2. Users can run baseline/preprocessing and robust peak detection on XRD datasets.
  3. Users receive qualitative phase candidate matches with traceable confidence outputs.
  4. XRD results can be saved and included in report/export artifacts with method context.
**Plans**: TBD

### Phase 5: XRF MVP
**Goal**: Users can run XRF workflows for preprocessing, element screening, and semi-quantitative reporting.
**Depends on**: Phase 1
**Requirements**: XRF-01, XRF-02, XRF-03, XRF-04
**Success Criteria** (what must be TRUE):
  1. Users can import XRF data from CSV and limited HDF5/NeXus MVP paths where available.
  2. Users can run baseline/preprocessing and line/peak deconvolution for element screening.
  3. Users receive semi-quantitative concentration estimates with explicit confidence and limitation annotations.
  4. XRF results can be saved and included in report/export artifacts with method context.
**Plans**: TBD

### Phase 6: Cross-Modality Quality and Reporting Hardening
**Goal**: All stable modalities meet consistent provenance, validation, regression, reporting, and user-guidance quality bars.
**Depends on**: Phase 2, Phase 3, Phase 4, Phase 5
**Requirements**: ARCH-03, QUAL-01, QUAL-02, QUAL-03, QUAL-04
**Success Criteria** (what must be TRUE):
  1. Each stable modality preserves processing payload, method context, and provenance in saved artifacts and generated reports.
  2. Validation gates block invalid datasets from stable reporting for every stable modality.
  3. Report generator and CSV/XLSX summaries are modality-aware across stable modalities without DSC/TGA-only assumptions.
  4. Regression tests cover existing DSC/TGA and all new stable modalities and pass as a release gate.
  5. Streamlit and desktop workflow guidance accurately communicates stable versus experimental scope.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation Contracts and Execution Path | 3/3 | Complete    | 2026-03-11 |
| 2. DTA Stabilization | 3/3 | Complete | 2026-03-12 |
| 3. FTIR and Raman MVP | 2/3 | In Progress|  |
| 4. XRD MVP | 3/4 | In Progress|  |
| 5. XRF MVP | 0/TBD | Not started | - |
| 6. Cross-Modality Quality and Reporting Hardening | 0/TBD | Not started | - |

