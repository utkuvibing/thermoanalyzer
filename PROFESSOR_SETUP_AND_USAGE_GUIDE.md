# Professor Setup and Usage Guide

This guide is intended to help professors and lab users install ThermoAnalyzer quickly, run it locally, and evaluate the current stable beta workflow.

For the Turkish version, use [PROFESOR_KURULUM_VE_KULLANIM_KILAVUZU.md](PROFESOR_KURULUM_VE_KULLANIM_KILAVUZU.md).

## 1. What is currently stable?
The current stable beta scope includes:

- DSC analysis
- TGA analysis
- Compare Workspace
- Batch Template Runner
- Report / export generation
- Project save / load with `.thermozip`

Preview-only areas that should not be treated as production-ready:

- DTA
- Kinetics
- Peak deconvolution

## 2. What professors need

- A Windows computer
- The provided `ThermoAnalyzer_Beta_Setup.exe` installer

For the beta distribution, **no Python, pip, dependency installation, or terminal usage is required**.
The installer also checks the local runtime prerequisites automatically.

## 3. Installation

1. Double-click `ThermoAnalyzer_Beta_Setup.exe`.
2. Follow the installer steps with `Next`.
3. Leave the desktop-shortcut option enabled if you want quick access.
4. Click `Finish` to complete the installation and optionally launch the app immediately.

If the Windows machine is missing a Microsoft compatibility runtime used by packaged scientific libraries, Setup may show a single permission prompt and install it automatically. No manual download is required.

After installation:

- a `ThermoAnalyzer Beta` shortcut is available in the Start Menu
- an optional desktop shortcut is created
- the app launches with a single click and opens in the default browser

Notes:

- some Windows systems may show a first-launch browser or local-network prompt
- some Windows systems may show a one-time Microsoft runtime permission prompt during Setup if the compatibility package is missing
- the app still runs locally on the professor's computer; it is not a cloud-hosted session

## 4. Recommended usage workflow

1. Launch the app and upload a DSC or TGA file.
2. Review the `Import Confidence`, `Import Review`, inferred analysis type, and signal-unit information.
3. Fix the column mapping manually if needed.
4. Use Compare Workspace to inspect overlays.
5. Run the analysis from the DSC or TGA page.
6. Save the result into the session.
7. If needed, apply the same workflow template across compatible runs with the Batch Template Runner.
8. Use the `Report Center` page to generate:
   - DOCX / PDF reports
   - CSV / XLSX exports
   - `.thermozip` project archives
   - a support snapshot

## 5. Recommended file types

- CSV
- TXT / TSV
- XLSX / XLS

Best current import reliability:

- generic delimited exports with clear headers
- TA-like text exports
- NETZSCH-like text exports

## 6. Important caveats

- If an import carries review warnings, manually confirm the data type, signal column, and unit before trusting the run.
- Preview modules are outside the stable beta promise.
- Proprietary binary formats are not part of the current supported scope.
- Missing calibration metadata should not be treated as full scientific acceptance.

## 7. How to report issues
When possible, attach:

- the original input file
- the exact page / workflow used
- the observed versus expected result
- screenshots
- `thermoanalyzer_support_snapshot.json`
- the related `.thermozip` archive

## 8. Additional documents

- Turkish setup and usage guide: [PROFESOR_KURULUM_VE_KULLANIM_KILAVUZU.md](PROFESOR_KURULUM_VE_KULLANIM_KILAVUZU.md)
- Beta-scope and feedback guide: [PROFESSOR_BETA_GUIDE.md](PROFESSOR_BETA_GUIDE.md)
