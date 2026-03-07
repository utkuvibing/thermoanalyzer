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
- it allows prerequisite checks and compatibility-runtime bootstrapping without changing the app itself

## Build prerequisites

Build on a Windows machine with:

- Python 3.10+ available on PATH
- the repo checked out locally
- dependencies installed with `pip install -r requirements.txt`
- Inno Setup 6 installed
- internet access to download the official Microsoft VC++ Redistributable during packaging, unless you pass a local signed copy with `-VcRedistPath`

PyInstaller is installed automatically by the build script if it is missing from the active Python environment.
The build script also downloads the current official `vc_redist.x64.exe` from Microsoft, verifies the Authenticode signature, and embeds it into the installer as a compatibility prerequisite.

## Build the installer

From the repo root:

```powershell
packaging\windows\build_beta_installer.bat
```

Or directly:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build_beta_installer.ps1
```

If you already have a local official VC++ redistributable installer, you can reuse it:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build_beta_installer.ps1 -VcRedistPath "C:\installers\vc_redist.x64.exe"
```

If Inno Setup is not installed in the default location, pass the compiler path:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build_beta_installer.ps1 -IsccPath "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

## Build the installer in GitHub Actions

The repo now includes a GitHub Actions workflow:

```text
Build Windows Beta Installer
```

### Manual trigger

1. Open the repository on GitHub.
2. Go to **Actions**.
3. Select **Build Windows Beta Installer**.
4. Click **Run workflow**.
5. Wait for the Windows job to finish.
6. Open the completed run and download the artifact from the **Artifacts** section.

### Automatic trigger

The same workflow also runs when you push a tag that starts with:

```text
v*
```

Example:

```powershell
git tag v2.0.0-beta1
git push origin v2.0.0-beta1
```

## Expected artifact

GitHub Actions uploads the final installer as an artifact named:

```text
ThermoAnalyzer_Beta_Setup_<APP_VERSION>.exe
```

Example:

```text
ThermoAnalyzer_Beta_Setup_2.0.exe
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
- performs install-time sanity checks for free disk space and the writable per-user runtime directory
- checks for the Microsoft Visual C++ runtime and attempts to install the official compatibility package automatically if the system copy is missing

## What the professor sees

1. Double-click `ThermoAnalyzer_Beta_Setup_<APP_VERSION>.exe`
2. Click `Next`
3. Click `Install`
4. If Windows does not already have the required Microsoft compatibility runtime, Setup may show one Windows permission prompt for the bundled official runtime installer
5. Click `Finish`
6. Launch ThermoAnalyzer from the final page, the Start Menu, or the optional desktop shortcut

Professors still do **not** need Python, pip, PATH edits, or terminal commands.

## Legal / distribution notes

- The installer embeds the unmodified official Microsoft Visual C++ Redistributable installer.
- ThermoAnalyzer does **not** vendor that binary in the git repo; it is staged during the build.
- Redistribution and use remain subject to Microsoft's Visual Studio / Visual C++ redistributable license terms.
- If your organization requires legal review, point them to Microsoft's current redistributable downloads and license terms before distribution.

## Known beta limitations

- the app still runs in the browser; the installer does not turn it into a native desktop UI
- some Windows systems may still show a first-launch firewall or browser prompt
- if the machine is missing the Microsoft VC++ runtime, Windows may show a one-time permission prompt while Setup installs the bundled compatibility package
- the packaged folder is larger than a simple script bundle because `onedir` is used for reliability
