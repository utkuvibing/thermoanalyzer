# Desktop Backend Bundle

This folder contains the Windows-focused backend freezing path used by the Electron desktop package.

## Goal

Build a local backend executable so the packaged Electron app does not require system Python.

## Build Command

From repository root:

```powershell
python .\desktop\backend_bundle\build_backend.py --clean
```

Expected output:

- `desktop/backend_bundle/dist/thermoanalyzer_backend/thermoanalyzer_backend.exe`

## Notes

- This bundle keeps backend API contracts unchanged; it only changes runtime distribution.
- Build machine must have PyInstaller installed in the active Python environment.
