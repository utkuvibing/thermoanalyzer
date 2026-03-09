# ThermoAnalyzer Desktop - Clean Machine Smoke Checklist

Use this checklist on a fresh Windows machine before professor demo handoff.

## Preconditions

- Windows 10/11 x64 machine with no Python requirement.
- Build artifact available:
  - `ThermoAnalyzer-Desktop-<version>-x64.exe` (portable)
- At least one known-good DSC/TGA CSV sample file ready for import.

## Smoke Steps

1. Launch app
- Action: Double-click `ThermoAnalyzer-Desktop-<version>-x64.exe`.
- Verify:
  - Main window opens as `ThermoAnalyzer Desktop`.
  - No immediate backend startup error dialog appears.

2. Backend startup
- Action: Wait for initial status card to populate.
- Verify:
  - Health shows `ok`.
  - Version endpoint returns app version + project extension.

3. Create workspace
- Action: Click `New Workspace`.
- Verify:
  - Workspace ID appears.
  - Empty dataset/result tables are visible without errors.

4. Import dataset
- Action: Click `Import Dataset` and pick a valid DSC/TGA file.
- Verify:
  - Imported dataset appears in dataset list.
  - Dataset detail panel shows validation summary and preview data.

5. Run single analysis
- Action: Choose `DSC` or `TGA`, then click `Run Analysis`.
- Verify:
  - Analysis status indicates execution outcome.
  - Result appears in results list.
  - Result detail panel shows summary/processing/validation/provenance.

6. Save and reload project archive
- Action: Click `Save Workspace`, save `.thermozip`, then `Open .thermozip` and load that same file.
- Verify:
  - Workspace reloads successfully.
  - Dataset/result lists and details remain available after reload.

7. CSV export
- Action: Go to export section, keep at least one saved result selected, click `Export Results CSV`.
- Verify:
  - Save dialog appears.
  - CSV file is created and non-empty.

8. DOCX report generation
- Action: Click `Generate DOCX Report`.
- Verify:
  - Save dialog appears.
  - DOCX file is created and opens in Word/LibreOffice.

9. Batch run
- Action: In compare/batch section, select at least two datasets when possible, click `Run Batch On Compare Selection`.
- Verify:
  - Batch summary appears with per-dataset `saved` / `blocked` / `failed`.
  - Saved outcomes produce new result IDs in results list.

10. Restart confidence
- Action: Close app and launch again.
- Verify:
  - App starts cleanly again without backend startup dialog.

## If Startup Fails

- Capture dialog text and diagnostics log path shown by the app.
- Collect `startup-*.log` from `%APPDATA%\\ThermoAnalyzer Desktop\\logs`.
- Share both the log and exact build filename.
