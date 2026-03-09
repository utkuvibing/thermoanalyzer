# Electron Desktop Skeleton (Tranche 5)

This directory contains a minimal desktop workflow shell for early migration tranches.

What it does:
- launches local Python backend (`backend/main.py`)
- waits for `/health`
- opens an Electron window
- shows backend status + version
- supports a minimal workflow:
  - create/load workspace (`.thermozip`)
  - list datasets and results
  - inspect dataset details (metadata, units, validation, data preview)
  - inspect result details (summary, processing, validation, provenance, review)
  - view/update basic compare workspace selection state
  - inspect richer workspace context (active dataset, latest result, compare state, recent history)
  - set active dataset explicitly for workspace state
  - manage compare selected datasets with add/remove/clear actions
  - run a minimal synchronous DSC/TGA batch on compare-selected datasets with per-dataset outcomes
  - inspect export/report preparation (exportable saved results + metadata)
  - generate/download normalized results CSV for selected saved results
  - generate/download DOCX report for selected saved results
  - import a dataset file
  - run one DSC/TGA analysis on a selected dataset
  - save workspace to `.thermozip`

What it does not do:
- does not migrate full Streamlit page parity
- does not change scientific algorithms
- does not replace current Windows packaging flow yet

## Run (development)

From repo root:

```powershell
cd desktop\electron
npm install
npm start
```

Optional environment variable:
- `TA_PYTHON` to override Python executable used for backend launch.
