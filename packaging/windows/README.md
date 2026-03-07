# Windows Beta Packaging

This folder contains the minimum-risk Windows beta packaging flow for the current Streamlit-based ThermoAnalyzer repo.

## Chosen packaging path

- **Runtime packaging:** PyInstaller `onedir`
- **Installer:** Inno Setup 6
- **Launch model:** small Windows launcher executable that starts the local Streamlit app and opens the default browser

Why this path was chosen:

- it keeps the current app and repo structure intact
- it does not require a desktop-framework rewrite
- it is more reliable for Streamlit, SciPy, Plotly, Kaleido, and report dependencies than a fragile `onefile` beta build
- it gives professors an installer, a Start Menu entry, and an optional desktop shortcut

## Build prerequisites

Build on a Windows machine with:

- Python 3.10+ available on PATH
- the repo checked out locally
- dependencies installed with `pip install -r requirements.txt`
- Inno Setup 6 installed

PyInstaller is installed automatically by the build script if it is missing from the active Python environment.

## Build the installer

From the repo root:

```powershell
packaging\windows\build_beta_installer.bat
```

Or directly:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build_beta_installer.ps1
```

If Inno Setup is not installed in the default location, pass the compiler path:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build_beta_installer.ps1 -IsccPath "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

## Output

The final installer is written to:

```text
release\ThermoAnalyzer_Beta_Setup_<APP_VERSION>.exe
```

Intermediate PyInstaller output is written to:

```text
packaging\windows\dist\
packaging\windows\build\
```

## What the packaged app does

- installs a local launcher executable
- stores writable runtime data under `%LOCALAPPDATA%\ThermoAnalyzer Beta`
- seeds `.streamlit\config.toml` into the user runtime directory on first launch
- starts the app on `127.0.0.1` and opens the browser automatically
- keeps support logs out of `Program Files`

## Known beta limitations

- the app still runs in the browser; the installer does not turn it into a native desktop UI
- some Windows systems may still show a first-launch firewall or browser prompt
- the packaged folder is larger than a simple script bundle because `onedir` is used for reliability
