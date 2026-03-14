# M001: Migration

**Vision:** ThermoAnalyzer is a vendor-independent analysis workbench currently centered on stable DSC/TGA workflows.

## Success Criteria


## Slices

- [x] **S01: Foundation Contracts And Execution Path** `risk:medium` `depends:[]`
  > After this: Establish the foundation contract and registry layer for stable modalities before touching backend routing.
- [x] **S02: Dta Stabilization** `risk:medium` `depends:[S01]`
  > After this: Stabilize DTA in backend modality contracts and execution routing before UI/report promotion.
- [ ] **S03: Ftir And Raman Mvp** `risk:medium` `depends:[S02]`
  > After this: Establish Phase 3 import and modality foundations before analysis implementation.
- [x] **S04: Xrd Mvp** `risk:medium` `depends:[S03]`
  > After this: Establish XRD modality and import foundations so Phase 4 execution can proceed on stable contracts.
- [ ] **S05: Xrf Mvp** `risk:medium` `depends:[S04]`
  > After this: unit tests prove xrf-mvp works
- [ ] **S06: Cross Modality Quality And Reporting Hardening** `risk:medium` `depends:[S05]`
  > After this: unit tests prove cross-modality-quality-and-reporting-hardening works
