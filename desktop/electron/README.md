# Electron Desktop Skeleton (Tranche 7)

This directory contains a minimal desktop workflow shell for early migration tranches.

What it does:
- launches local backend in two modes:
  - development mode: Python source backend (`backend/main.py`)
  - packaged mode: bundled backend executable (`resources/backend/thermoanalyzer_backend.exe`)
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
- does not replace current Streamlit packaging flow yet

## Run (development)

From repo root:

```powershell
cd desktop\electron
npm install
npm start
```

Optional environment variable:
- `TA_PYTHON` to override Python executable used for backend launch.
- `TA_BACKEND_EXE` to override packaged-backend executable path for diagnostics.

## Packaging (Windows demo build)

1. Install Node dependencies:

```powershell
cd desktop\electron
npm install
```

2. Build bundled backend executable:

```powershell
npm run build:backend
```

3. Build portable Windows desktop app:

```powershell
npm run build:win:portable
```

Expected outputs:
- bundled backend: `desktop/backend_bundle/dist/thermoanalyzer_backend/thermoanalyzer_backend.exe`
- packaged desktop app: `release/electron/ThermoAnalyzerDesktop-0.1.0-x64.exe`

Optional unpacked build output:

```powershell
npm run build:win:dir
```

Output:
- `release/electron/win-unpacked/`

## Startup Path Smoke Test

Run startup path resolver smoke checks:

```powershell
npm run test:startup-paths
```
