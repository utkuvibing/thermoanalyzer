# Bugs

Use this file as a lightweight bug worklog. Add a new section whenever a bug is reproduced, investigated, or fixed.

---

## Bug Entry Template

### Title
Short bug summary.

### Date
YYYY-MM-DD

### Repro
1. Step one
2. Step two
3. Observed failure

### Suspected Cause
Brief hypothesis before the fix.

### Attempted Fix
What was tried first, if anything.

### Actual Fix
What changed in the final patch.

### Verification
- Tests run
- Manual verification
- Residual risk

---

### Title
Legacy report-generator CSV contract drifted from normalized result exports

### Date
2026-03-07

### Repro
1. Run `pytest -q`.
2. Observe failures in `tests/test_report_generator.py`.
3. See header/content assertions expecting the old kinetics-only CSV schema instead of the normalized flat record export currently produced by `core/report_generator.generate_csv_summary()`.

### Suspected Cause
The repo migrated report/export flows to normalized result records, but `tests/test_report_generator.py` remained on the old pre-normalization CSV contract.

### Attempted Fix
Brownfield hardening pass aligns tests and report/export helpers to the normalized record contract instead of restoring the deprecated CSV format.

### Actual Fix
Update report/export tests to validate normalized flat record output and extend exports to carry optional processing/provenance/validation metadata in a backward-compatible way.

### Verification
- Run `pytest -q`
- Confirm `tests/test_export_report.py` and `tests/test_project_io.py` still pass with normalized records
- Residual risk: downstream external tooling that assumed the old CSV layout would need an explicit legacy export helper

### Title
Legacy tuple validator drifted away from the current ThermalDataset model

### Date
2026-03-07

### Repro
1. Open `utils/validators.py`.
2. Inspect `validate_thermal_dataset()`.
3. See it expecting legacy attributes like `temperature_column`, `heat_flow_column`, and `sample_mass_mg` that the current `core.data_io.ThermalDataset` no longer uses.

### Suspected Cause
The repo kept the old tuple-based validator API for compatibility, but its dataset-level implementation was never updated after the standardized `temperature` / `signal` DataFrame contract and the new structured validator were introduced.

### Attempted Fix
Do not delete the public helper outright; keep its scalar validation helpers and replace only the stale dataset-level path.

### Actual Fix
Rewrite `utils/validators.py` as a compatibility layer that preserves the `(is_valid, message)` return type while delegating dataset-level checks to `core.validation.validate_thermal_dataset()`.

### Verification
- Run `pytest tests/test_validation.py -q`
- Confirm legacy wrapper returns `True` for valid current datasets and surfaces structured failure messages for invalid ones
- Residual risk: any third-party caller that relied on the old verbose message wording may observe text differences, but the public tuple shape is preserved

### Title
Saved workflow templates lacked stable internal IDs and DSC/TGA reports hid method context

### Date
2026-03-07

### Repro
1. Save a DSC or TGA result.
2. Inspect the normalized record `processing` payload and generated report.
3. Observe that the saved payload carried only a user-facing workflow label, and the report showed mostly generic key/value blocks rather than DSC/TGA-specific method context such as calibration, sign convention, atmosphere, and reference visibility.

### Suspected Cause
The first hardening tranche standardized payload structure but did not introduce stable template identifiers or domain-specific report rendering, so brownfield compatibility was preserved at the cost of method traceability.

### Attempted Fix
Avoid changing the normalized record contract or archive format; add stable template IDs inside the existing `processing` dict and derive richer report summaries from existing record metadata plus validation checks.

### Actual Fix
Extend `core.processing_schema` to backfill `workflow_template_id` / `workflow_template_label`, harden `core.validation` with DSC/TGA-specific checks, and teach `core.report_generator` to render domain-specific method summaries for DSC/TGA while keeping flat CSV export unchanged.

### Verification
- Run `pytest tests/test_validation.py tests/test_report_generator.py tests/test_export_report.py tests/test_project_io.py -q`
- Run `pytest -q`
- Confirm old label-only payloads still normalize correctly and project archives round-trip with the richer processing dict
- Residual risk: template labels remain user-facing strings, so multilingual labels can still differ even when the stable internal ID is identical

### Title
TGA reference matching could incorrectly fall back to DSC melting standards

### Date
2026-03-07

### Repro
1. Build a TGA processing payload with a reference temperature near 155 °C.
2. Call `build_calibration_reference_context(..., analysis_type="TGA", reference_temperature_c=155.0)`.
3. Observe that the reference state becomes `reference_checked` against `Indium (In)` instead of remaining unmatched for TGA.

### Suspected Cause
`utils.reference_data.find_nearest_reference()` searched TGA decomposition standards first but then also considered DSC melting standards, so a TGA midpoint could be matched to an unrelated DSC calibrant if it was numerically closer.

### Attempted Fix
Keep the helper brownfield and local; restrict the reference pool by analysis modality instead of introducing a new calibration engine or archive schema.

### Actual Fix
Limit `find_nearest_reference()` to DSC/DTA melting standards for DSC/DTA analyses and TGA decomposition standards for TGA analyses, then add a regression test that asserts a 155 °C TGA event remains `reference_out_of_window`.

### Verification
- Run `pytest tests/test_validation.py tests/test_project_io.py -q`
- Run `pytest -q`
- Confirm TGA project round-trip keeps `reference_out_of_window` for the 155 °C synthetic step while 200 °C still matches `CaC₂O₄·H₂O  Step 1`

### Title
Batch runner relied on private DSC processor state for saved signal snapshots

### Date
2026-03-07

### Repro
1. Read `core/batch_runner.py`.
2. Observe that the DSC batch path captures `smoothed` and `corrected` arrays via `DSCProcessor._signal`.
3. Note that this creates an external dependency on a private implementation detail rather than the processor's public snapshot API.

### Suspected Cause
The first batch MVP optimized for minimal code reuse and reached into the processor internals to capture intermediate arrays, even though `get_result()` already exposes the current signal snapshot.

### Attempted Fix
Avoid changing `DSCProcessor` itself; replace the private-state reads with public `get_result()` snapshots after `normalize()` and after `correct_baseline()`.

### Actual Fix
Update `core.batch_runner` to capture DSC `smoothed` / `corrected` arrays through `processor.get_result().smoothed_signal` instead of `processor._signal`, and add deterministic batch regression tests so the saved summaries/rows remain stable for the same input and template.

### Verification
- Run `pytest tests/test_batch_runner.py tests/test_dsc_processor.py -q`
- Run `pytest -q`
- Confirm the batch runner no longer reads `DSCProcessor._signal` directly while DSC batch results remain numerically stable

### Title
Ambiguous low-range TGA auto mode silently defaulted to percent

### Date
2026-03-07

### Repro
1. Load a TGA dataset with low-range mass values near `100 -> 90` and no trustworthy signal-unit label.
2. Run the stable TGA workflow or a TGA batch template with the default auto settings.
3. Observe that the processor uses the percent path because `max(signal) <= 105`, but the saved workflow context does not clearly record that the result depended on an ambiguous auto inference.

### Suspected Cause
`core.tga_processor.TGAProcessor` only used the hidden `raw_mass.max() > 105` heuristic, and the brownfield save/validation flows did not persist or report whether the run was declared as auto, explicitly percent, or explicitly absolute mass.

### Attempted Fix
Keep the default auto behavior for backward compatibility, but introduce an additive unit-mode context that records declared mode, resolved mode, inference basis, and review status. Reuse that context in validation, TGA page state, batch execution, and report rendering instead of redesigning the export or archive contracts.

### Actual Fix
Add `unit_mode` support and a shared `resolve_tga_unit_interpretation()` helper in `core.tga_processor`, persist declared/resolved mode through `core.processing_schema`, surface ambiguous low-range auto cases as review warnings in `core.validation`, and thread the same context through `ui.tga_page`, `core.batch_runner`, and `core.report_generator`.

### Verification
- Run `pytest tests/test_tga_processor.py tests/test_validation.py tests/test_batch_runner.py tests/test_report_generator.py -q`
- Run `pytest -q`
- Confirm explicit `percent` / `absolute_mass` modes stay deterministic, unambiguous auto cases resolve cleanly, and ambiguous low-range auto inputs are still processed compatibly but flagged for review

### Title
Import heuristics silently overclaimed confidence for ambiguous lab exports

### Date
2026-03-07

### Repro
1. Load a generic DSC/TGA text export where the headers are weak, overlapping, or partially edited, for example a semicolon-delimited sheet with columns like `Weight (mW)` or a generic `Signal` column.
2. Let `core.data_io.read_thermal_data()` infer the mapping automatically.
3. Observe that the import previously selected a signal column, analysis type, vendor, and signal unit without preserving enough uncertainty context for the user to review the guess.

### Suspected Cause
`core.data_io.guess_columns()` relied on first-match and numeric-fallback heuristics that favored choosing *some* plausible column over recording ambiguity. Vendor and unit inference were similarly shallow, and the resulting uncertainty was not surfaced through metadata or validation.

### Attempted Fix
Keep the brownfield import architecture and existing `ThermalDataset` shape, but make the inference pipeline additive and review-aware: score likely columns more carefully, detect conflicting cues, classify confidence, and persist structured import warnings/metadata that the existing validation and UI layers can surface.

### Actual Fix
Harden `core.data_io` so import now records additive `import_confidence`, `import_warnings`, `import_review_required`, `inferred_analysis_type`, `inferred_signal_unit`, `inferred_vendor`, and vendor-confidence metadata. Preserve current behavior for clear TA/NETZSCH/generic exports, but downgrade ambiguous signal/unit/vendor cases to explicit review warnings instead of hidden certainty. Reuse the same context in `core.validation`, `ui.home`, and `ui.components.data_preview`, and add regression coverage for generic, delimited, vendor-like, ambiguous, and misleading-header cases.

### Verification
- Run `pytest tests/test_data_io.py tests/test_validation.py -q`
- Run `pytest -q`
- Run `pytest --collect-only -q`
- Confirm clear TA/NETZSCH/generic imports still resolve cleanly, while ambiguous header/unit cases now carry explicit review metadata and warnings

### Title
Windows beta installer was not prerequisite-aware for professor-side runtime setup

### Date
2026-03-07

### Repro
1. Review `packaging/windows/build_beta_installer.ps1` and `packaging/windows/ThermoAnalyzer_Beta.iss`.
2. Observe that the beta build previously packaged the app and created `Setup.exe`, but it did not stage or check compatibility prerequisites beyond the bundled onedir runtime.
3. Note that the installer also lacked sanity checks for writable `%LOCALAPPDATA%` runtime setup and free-space conditions, which increased the chance of professor-side install friction.

### Suspected Cause
The first packaging tranche intentionally optimized for the smallest viable installer path: PyInstaller `onedir` plus Inno Setup. That preserved the app architecture, but it left prerequisite handling implicit instead of making the installer act like a true bootstrapper.

### Attempted Fix
Keep the same packaging path and GitHub Actions automation, but make the build stage the official Microsoft VC++ redistributable, verify its Authenticode signature, and let Inno Setup handle prerequisite checks and minimal compatibility installation without requiring Python, pip, or PATH changes on the professor side.

### Actual Fix
Update `packaging/windows/build_beta_installer.ps1` to download or accept a local official `vc_redist.x64.exe`, verify it is Microsoft-signed, and pass it into the installer build. Harden `packaging/windows/ThermoAnalyzer_Beta.iss` with install-time free-space and writable-runtime checks plus conditional VC++ compatibility installation. Also tighten the packaged launcher and professor/builder docs so the expected flow is still a one-click `Setup.exe` with minimal prompts.

### Verification
- Run `python -m py_compile packaging/windows/launcher.py tests/test_windows_launcher.py`
- Run `pytest -q`
- Manually confirm the installer script now references `vc_redist.x64.exe`, free-space checks, and writable `%LOCALAPPDATA%` runtime validation
- Confirm GitHub Actions still builds the same `ThermoAnalyzer_Beta_Setup_<APP_VERSION>.exe` artifact through the unchanged workflow entry point

### Title
GitHub Actions Windows packaging failed on PyInstaller presence probe in PowerShell

### Date
2026-03-08

### Repro
1. Run the `Build Windows Beta Installer` workflow on `windows-latest`.
2. Reach the `Build Windows beta installer` step.
3. Observe failure in `packaging/windows/build_beta_installer.ps1` at `& $PythonExe -c "import PyInstaller" 2>$null | Out-Null`.

### Suspected Cause
The probe intentionally depends on a non-zero native exit code when `PyInstaller` is missing, but under CI PowerShell settings this emits a `NativeCommandError` and aborts before the script can evaluate `$LASTEXITCODE`.

### Attempted Fix
Keep the same packaging path and install behavior, but avoid a failing native-command probe by replacing `import PyInstaller` with a `find_spec()`-based check that reports presence via stdout.

### Actual Fix
In `packaging/windows/build_beta_installer.ps1`, replace the non-zero-exit `import PyInstaller` probe with `importlib.util.find_spec('PyInstaller')` output parsing (`"1"` present, otherwise install), leaving the existing `pip install pyinstaller` path unchanged.

### Verification
- Reproduce `NativeCommandError` behavior with a failing Python import under PowerShell `Stop` mode and native-command error handling enabled.
- Verify the new `find_spec` probe returns `present=0` without throwing in the same PowerShell mode.
- Run script syntax check: `powershell -NoProfile -Command "[void][ScriptBlock]::Create((Get-Content 'packaging/windows/build_beta_installer.ps1' -Raw))"`.
- Residual risk: if Python itself is unavailable/broken, the script still fails early, which is correct for packaging.

### Title
PyInstaller spec crashed on `__file__` lookup during local Windows build

### Date
2026-03-08

### Repro
1. Run `powershell -ExecutionPolicy Bypass -File packaging\windows\build_beta_installer.ps1`.
2. Reach PyInstaller stage.
3. Observe `NameError: name '__file__' is not defined` from `packaging/windows/ThermoAnalyzerLauncher.spec`.

### Suspected Cause
`ThermoAnalyzerLauncher.spec` assumed `__file__` is always defined, but PyInstaller can execute spec code with `SPECPATH` and without `__file__`.

### Attempted Fix
Keep current packaging flow; only harden spec root resolution to support both execution modes.

### Actual Fix
Update `packaging/windows/ThermoAnalyzerLauncher.spec` to resolve `SPEC_ROOT` from `__file__` when available, otherwise fall back to PyInstaller-provided `SPECPATH` (or `Path.cwd()` as final fallback).

### Verification
- Re-run `powershell -ExecutionPolicy Bypass -File packaging\windows\build_beta_installer.ps1` and confirm build passes the former `__file__` failure point.
- Residual risk: full build can still fail later if local prerequisites (for example `ISCC.exe`) are missing, which is expected.

### Title
Windows build script expected PyInstaller output in the wrong dist/work paths

### Date
2026-03-08

### Repro
1. Run `powershell -ExecutionPolicy Bypass -File packaging\windows\build_beta_installer.ps1`.
2. Let PyInstaller finish successfully.
3. Observe script failure: `PyInstaller output was not created at C:\thermoanalyzer\packaging\windows\dist\ThermoAnalyzerLauncher` while PyInstaller reports output under `C:\thermoanalyzer\dist`.

### Suspected Cause
The script assumed PyInstaller would emit into `packaging/windows/dist`, but the command did not set `--distpath`/`--workpath`, so PyInstaller defaulted to current working directory paths.

### Attempted Fix
Keep existing folder structure and checks; pass explicit output directories to PyInstaller.

### Actual Fix
In `packaging/windows/build_beta_installer.ps1`, update the PyInstaller invocation to include `--distpath $distRoot` and `--workpath $buildRoot`.

### Verification
- Re-run `powershell -ExecutionPolicy Bypass -File packaging\windows\build_beta_installer.ps1`.
- Confirm PyInstaller writes into `packaging\windows\dist` and the script proceeds past `Assert-PackagedRuntime`.
- Residual risk: installer compile still requires local Inno Setup (`ISCC.exe`) availability.

### Title
Electron renderer became partially truncated during UI shell refactor

### Date
2026-03-10

### Repro
1. Open `desktop/electron/renderer.js` after the initial shell parity edit.
2. Observe the file ended around helper declarations and no longer attached event handlers.
3. Start desktop app and see broken/non-functional interactions due to missing renderer logic.

### Suspected Cause
Large one-shot patch/edit attempt exceeded tooling limits and left `renderer.js` in a partially written state.

### Attempted Fix
Tried replacing the whole file in a single edit call; it failed due command/path-length constraints in the tool wrapper.

### Actual Fix
Restore the last known-good renderer from git baseline, then apply incremental small patches to map logic to the new app-shell IDs and move raw payload outputs to Diagnostics.

### Verification
- Run `node --check desktop/electron/renderer.js`
- Run `npm run test:desktop-smoke`
- Run `pytest -q`
- Residual risk: deeper per-page UI/UX parity with Streamlit is still pending in future tranches
