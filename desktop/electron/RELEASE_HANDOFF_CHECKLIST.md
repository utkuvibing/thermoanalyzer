# ThermoAnalyzer Desktop - Release Handoff Checklist

Run this checklist before sending a demo build to professors.

## Build Integrity

1. Build bundled backend:
- `cd desktop/electron`
- `npm run build:backend`
- Verify: `desktop/backend_bundle/dist/thermoanalyzer_backend/thermoanalyzer_backend.exe` exists.

2. Build NSIS installer artifact:
- `npm run build:win:nsis`
- Verify: `release/electron/ThermoAnalyzer-Setup-<version>-x64.exe` exists.

3. Optional unpacked validation build:
- `npm run build:win:dir`
- Verify: `release/electron/win-unpacked/` exists.

## Automated Confidence Checks

1. Desktop startup path checks:
- `npm run test:desktop-smoke`

2. Core regression suite:
- From repo root: `pytest -q`

## Manual Demo Confidence Checks

Use:
- `desktop/electron/CLEAN_MACHINE_SMOKE_CHECKLIST.md`

Minimum pass criteria:
- app starts
- backend starts
- import works
- DSC/TGA single run works
- project save/load works
- CSV export works
- DOCX export works
- batch run works

## Release Notes Payload

Include in handoff message:
- build filename
- build date
- known scope statement: stable DSC/TGA desktop workflow + batch/export/report prep
- known non-goals: preview modules not included, no installer signing in this build
- troubleshooting note: startup diagnostics logs are under `%APPDATA%\\ThermoAnalyzer Desktop\\logs`
