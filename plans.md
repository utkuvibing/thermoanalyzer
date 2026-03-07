# Plans

Use this file for large features, cross-cutting refactors, or work that should stay visible across multiple Codex sessions.

---

## Plan Template

### Title
Short name for the work item.

### Objective
What is changing and why?

### Definition Of Done
- Concrete acceptance criteria
- User-visible outcome
- Verification outcome

### Constraints
- What must not change?
- Compatibility constraints
- Scope boundaries

### Impact Analysis
- Affected modules/files
- Data shape or API implications
- User workflow implications

### Risks
- Regression risks
- Migration risks
- Test gaps

### Migration / Rollout Strategy
- Backward compatibility notes
- Order of implementation
- Rollback approach if needed

### Test Strategy
- Unit/integration/manual checks to run
- Commands to execute

### Progress Log
- [ ] Step 1
- [ ] Step 2
- [ ] Step 3

### Notes
Open questions, decisions, follow-ups.

---

## Title
Brownfield Product Hardening - Export, Validation, and Provenance

### Objective
Stabilize the normalized export/report contract, replace the stale dataset validator path with a real validation gate, and add backward-compatible provenance fields so DSC/TGA workflows become more reproducible and defensible without rewriting the repo.

### Definition Of Done
- `pytest -q` passes with the report/export contract aligned to normalized result records.
- Imported datasets are validated before entering the stable analysis workflow.
- Saved result records can optionally carry processing, provenance, validation, and review data.
- DOCX/PDF/CSV exports surface the new record metadata without breaking current DSC/TGA workflows.

### Constraints
- Keep the existing Streamlit shell and normalized result record shape backward-compatible.
- Do not rewrite analysis engines or change core dataset/session flows.
- Preserve `.thermozip` loading for older archives.

### Impact Analysis
- Affected modules: `core/report_generator.py`, `core/result_serialization.py`, `core/data_io.py`, `core/project_io.py`, `ui/home.py`, `ui/dsc_page.py`, `ui/tga_page.py`, `ui/kinetics_page.py`, `ui/components/history_tracker.py`.
- Tests to update/add: `tests/test_report_generator.py`, `tests/test_export_report.py`, `tests/test_project_io.py`, plus new validation coverage.
- User workflow impact: import will show validation feedback earlier; reports will include method/provenance context.

### Risks
- CSV export row counts will change once processing/provenance/validation sections are flattened.
- Extra record fields must remain optional to avoid breaking older saved results.
- UI pages may expose additional warnings for datasets that previously loaded silently.

### Migration / Rollout Strategy
- Implement optional fields first in result serialization.
- Align report/export consumers and tests to the normalized contract.
- Add validation gate in a warnings-first manner, only blocking clearly invalid datasets.
- Keep preview modules marked as preview; only harden shared normalized export paths this round.

### Test Strategy
- Run `pytest -q`.
- Run focused suites for report/export/project IO during development.
- Verify old records without optional fields still pass `split_valid_results`.

### Progress Log
- [x] Add repo worklog entries
- [x] Stabilize normalized report/export contract
- [x] Add validation gate and provenance fields
- [x] Update UI save flows for DSC/TGA/kinetics
- [x] Verify with tests

### Notes
- This is the first hardening tranche from the broader brownfield productization roadmap, not the full 6-month scope.

---

## Title
Report/Test Coverage Recovery and Processing Schema Standardization

### Objective
Recover report/export regression coverage on the normalized result contract, replace the stale legacy validator implementation with a compatibility wrapper, and standardize DSC/TGA processing payloads without changing the normalized record schema or analysis architecture.

### Definition Of Done
- Report/export tests cover DOCX target writes, normalized CSV rows, and XLSX summary visibility without restoring the deprecated CSV contract.
- `utils/validators.py` delegates dataset-level validation to `core.validation` while preserving the legacy tuple API.
- DSC/TGA pages save a versioned, standardized processing payload that remains backward-compatible for exports and project round-trips.
- Reports expose method summary plus clearer validation/provenance tables.

### Constraints
- Keep the normalized result contract unchanged.
- No batch runner, calibration engine, or architecture migration in this tranche.
- Preserve existing project/archive compatibility.

### Impact Analysis
- Runtime files: `core/report_generator.py`, `core/processing_schema.py`, `ui/dsc_page.py`, `ui/tga_page.py`, `utils/validators.py`.
- Tests: `tests/test_report_generator.py`, `tests/test_export_report.py`, `tests/test_validation.py`.
- User workflow impact: saved DSC/TGA results now carry a consistent processing schema; reports show clearer method/validation/provenance context.

### Risks
- Added processing aliases must stay compatible with older saved records and flat exports.
- Localized TGA workflow labels remain user-facing strings; the schema standardizes structure, not label canonicalization.
- Report wording changes can affect brittle string assertions if new downstream tests are added carelessly.

### Migration / Rollout Strategy
- Add the processing helper first.
- Update DSC/TGA pages to write the standardized payload while preserving legacy top-level keys.
- Improve report section rendering and expand tests against the normalized contract.
- Replace the stale validator implementation last with a compatibility wrapper and regression tests.

### Test Strategy
- Run `pytest tests/test_report_generator.py tests/test_export_report.py tests/test_validation.py -q`.
- Run `pytest -q`.
- Run `pytest --collect-only -q` to compare test count.

### Progress Log
- [x] Add `core.processing_schema` helper and wire DSC/TGA pages to it
- [x] Improve DOCX/PDF method, validation, and provenance rendering
- [x] Restore report/export regression coverage on the normalized contract
- [x] Replace stale `utils.validators` dataset path with compatibility wrapper
- [ ] Verify final pytest totals and residual risk

### Notes
- This tranche intentionally does not resurrect the deprecated kinetics-only CSV export contract.

---

## Title
DSC/TGA Validation Hardening and Domain-Specific Report Visibility

### Objective
Strengthen DSC/TGA-specific validation around calibration, sign convention, atmosphere, unit plausibility, and step-analysis context; move workflow templates onto stable internal IDs with preserved labels; and make reports show domain-specific method summaries without changing the normalized export contract.

### Definition Of Done
- DSC/TGA validation checks include method-context details when processing metadata is available.
- Saved `processing` payloads carry stable template IDs plus user-facing labels, while still preserving the legacy `workflow_template` field.
- DOCX/PDF reports render DSC/TGA method summaries with calibration/reference visibility instead of only generic processing tables.
- Existing `.thermozip` archives and legacy label-only processing payloads remain readable.

### Constraints
- No rewrite, no architecture migration, no batch runner, no calibration engine.
- Keep normalized CSV/XLSX/DOCX record contracts unchanged.
- Stay within existing `core/`, `ui/`, and `tests/` structure.

### Impact Analysis
- Runtime files: `core/processing_schema.py`, `core/validation.py`, `ui/dsc_page.py`, `ui/tga_page.py`, `core/report_generator.py`.
- Regression files: `tests/test_validation.py`, `tests/test_report_generator.py`, `tests/test_export_report.py`, `tests/test_project_io.py`.
- User-visible change: reports and validation warnings become more scientifically specific for DSC/TGA.

### Risks
- Template IDs must backfill correctly from legacy label-only payloads.
- New validation warnings must not incorrectly block existing datasets that only lack optional lab metadata.
- Domain-specific report wording increases string-sensitivity in tests.

### Migration / Rollout Strategy
- Extend `core.processing_schema` first so old payloads backfill IDs/labels.
- Feed standardized processing into validation and saved results.
- Render domain-specific report summaries from existing normalized records plus validation metadata.
- Verify project round-trip with richer `processing` payloads.

### Test Strategy
- Run `pytest tests/test_validation.py tests/test_report_generator.py tests/test_export_report.py tests/test_project_io.py -q`.
- Run `pytest -q`.
- Run `pytest --collect-only -q`.

### Progress Log
- [x] Add stable workflow template IDs with label backfill
- [x] Harden DSC/TGA validation checks
- [x] Render domain-specific DSC/TGA method summaries in reports
- [x] Update regression coverage and project round-trip assertions
- [ ] Verify final collect-count delta and residual risk

### Notes
- Compatibility is preserved by keeping `workflow_template` as a label alias while adding `workflow_template_id` and `workflow_template_label`.

---

## Title
Calibration/Reference Hardening and Support Diagnostics

### Objective
Promote calibration/reference status to first-class saved context for DSC/TGA results, add structured logging with stable error IDs, and expose a support snapshot download path without changing the normalized result/export contract or `.thermozip` format.

### Definition Of Done
- DSC/TGA saved `processing` / `provenance` payloads carry explicit calibration/reference state.
- Reports show calibration/reference state clearly for DSC/TGA.
- Import, project load, DSC analysis, TGA analysis, and export/report generation errors emit stable error IDs and land in a structured diagnostics log.
- Users can download a serialized support snapshot from the report center.

### Constraints
- No rewrite, no architecture migration, no batch runner, no archive schema change.
- Keep normalized CSV/XLSX flat export headers unchanged.
- Do not persist diagnostics/support state inside `.thermozip` archives.

### Impact Analysis
- Runtime files: `app.py`, `ui/home.py`, `ui/dsc_page.py`, `ui/tga_page.py`, `ui/export_page.py`, `core/provenance.py`, `core/validation.py`, `core/report_generator.py`, `utils/reference_data.py`, `utils/session_state.py`, plus new `utils/diagnostics.py`.
- Tests: existing report/export/project/validation tests plus new diagnostics coverage.
- User workflow impact: richer DSC/TGA saved context and a new support snapshot download in the report center.

### Risks
- Support logs are local filesystem artifacts; path handling must stay resilient in Streamlit runs.
- Calibration/reference state must remain additive so old results still render as “not recorded” rather than failing validation.
- Error IDs should be shown only on actual failures, not on normal warnings.

### Migration / Rollout Strategy
- Add diagnostics helper and session keys first.
- Thread calibration/reference context into DSC/TGA save flows.
- Improve report rendering and add export-center support snapshot.
- Verify no archive contract changes by keeping project round-trip tests green.

### Test Strategy
- Run `pytest tests/test_diagnostics.py tests/test_report_generator.py tests/test_export_report.py tests/test_project_io.py tests/test_validation.py -q`.
- Run `pytest -q`.
- Run `pytest --collect-only -q`.

### Progress Log
- [x] Add diagnostics helper and support snapshot serializer
- [x] Add calibration/reference context to DSC/TGA save flows
- [x] Render calibration/reference status in reports
- [x] Add structured error IDs to import/project/analysis/export/report failures
- [x] Verify final collect-count delta and residual risk

### Notes
- Support diagnostics remain session-local and downloadable; they are intentionally not embedded into project archives in this tranche.
- `pytest --collect-only -q` increased from 162 to 165 after adding diagnostics coverage and a modality-specific TGA reference regression.

---

## Title
Compare Workspace Batch Template Runner MVP

### Objective
Add a brownfield batchable template runner for DSC/TGA on top of the existing compare workspace so the same stable workflow template can be applied to multiple compatible datasets while reusing the current processing schema, validation, provenance, and export/report flows.

### Definition Of Done
- Users can select multiple compatible DSC or TGA datasets in the compare workspace and apply one workflow template to all selected runs.
- Each successful dataset saves a normal stable result record with the existing processing/provenance/validation structure and stable template ID.
- Per-dataset validation failures and analysis exceptions are surfaced in a batch summary with stable diagnostics instead of aborting the full batch.
- Compare workspace stores a batch summary that round-trips through existing project archives and appears in generated reports.

### Constraints
- No rewrite, no architecture migration, no normalized result/export contract changes, no archive schema changes.
- Stay limited to DSC/TGA and the existing compare workspace.
- Reuse existing validation, provenance, diagnostics, and report/export flows.

### Impact Analysis
- Runtime files: `core/batch_runner.py`, `ui/compare_page.py`, `core/report_generator.py`.
- Regression files: `tests/test_batch_runner.py`, `tests/test_report_generator.py`, `tests/test_project_io.py`.
- User-visible change: compare workspace gains a batch template runner plus a saved batch summary that existing report/export flows can reuse.

### Risks
- Batch defaults must be conservative so they do not imply richer per-template method control than the repo currently has.
- Per-dataset failures must remain isolated so one bad dataset does not prevent other selected runs from saving.
- Stored batch summary data must remain additive inside `comparison_workspace` to preserve old archive compatibility.

### Migration / Rollout Strategy
- Add a small UI-independent batch helper first.
- Wire compare workspace to run the helper per selected dataset and collect stable diagnostics.
- Render saved batch summary in reports using the existing comparison workspace payload.
- Verify project round-trip without touching `core.project_io`.

### Test Strategy
- Run `pytest tests/test_batch_runner.py tests/test_report_generator.py tests/test_project_io.py -q`.
- Run `pytest -q`.
- Run `pytest --collect-only -q`.

### Progress Log
- [x] Add core batch helper for DSC/TGA template execution
- [x] Wire compare workspace batch UI and saved summary
- [x] Render compare-workspace batch summary in reports
- [x] Add regression coverage and verify collect-count delta

### Notes
- Batch summary will be stored inside `comparison_workspace` so old archives stay readable and new archives round-trip without a manifest change.
- `pytest --collect-only -q` increased from 165 to 168 after adding dedicated batch-runner coverage.

---

## Title
Batch Runner Outcome Hardening and Summary Clarity

### Objective
Harden the compare-workspace batch runner UX by standardizing per-dataset outcomes (`saved` / `blocked` / `failed`), improving batch summary visibility and filtering, and making reports/export preview show batch totals plus failure reasons and error IDs more clearly.

### Definition Of Done
- Batch summary rows consistently use `saved`, `blocked`, or `failed`.
- Compare workspace shows clearer batch totals and lets the user filter batch rows by outcome.
- Report/export preview surfaces batch totals, failure reasons, and error IDs from the saved compare workspace state.
- Existing result/provenance/validation/export flows remain unchanged.

### Constraints
- No rewrite, no architecture migration, no `.thermozip` compatibility break, no flat export schema change.
- Keep using the current processing/provenance/validation/result flows.
- Stay within DSC/TGA batch MVP usability only.

### Impact Analysis
- Runtime files: `core/batch_runner.py`, `ui/compare_page.py`, `core/report_generator.py`, `ui/export_page.py`.
- Regression files: `tests/test_batch_runner.py`, `tests/test_report_generator.py`, `tests/test_export_report.py`.
- User-visible change: clearer batch outcome categories, filters, totals, and failure diagnostics in compare/report/export views.

### Risks
- Older saved batch summaries may still contain legacy `error` labels and must normalize safely to `failed`.
- Failure reasons should remain concise enough to display in tables without breaking report readability.
- No new result/export schema should leak out of the compare workspace state.

### Migration / Rollout Strategy
- Normalize batch summary rows in one place first.
- Reuse the normalized rows in compare workspace, report generation, and export preview.
- Keep saved summary data additive inside `comparison_workspace`.

### Test Strategy
- Run `pytest tests/test_batch_runner.py tests/test_report_generator.py tests/test_export_report.py -q`.
- Run `pytest -q`.
- Run `pytest --collect-only -q`.

### Progress Log
- [x] Normalize batch outcome categories and failure metadata
- [x] Improve compare workspace visibility and filtering
- [x] Improve report/export preview batch clarity
- [x] Add regression coverage and verify collect-count delta

### Notes
- Legacy `execution_status="error"` rows will be displayed as `failed` without mutating archive structure.
- `pytest --collect-only -q` increased from 168 to 170 after adding batch outcome normalization and export-preview coverage.

---

## Title
DSC/TGA Reproducibility and Calibration Acceptance Hardening

### Objective
Improve DSC/TGA scientific reliability inside the current brownfield repo by reducing fragile private-state reliance, enriching saved processing context with stable template/version information, centralizing calibration acceptance logic, and adding deterministic regression coverage for common DSC/TGA cases.

### Definition Of Done
- Batch runner no longer depends on private processor state where a public snapshot is sufficient.
- Saved DSC/TGA processing carries stable template/version context additively.
- Calibration acceptance logic is centralized, explicit, and regression-tested for all four supported states.
- Deterministic regression fixtures cover Tg-like DSC, melting/crystallization DSC, single-step TGA, multi-step TGA, noisy TGA, percent input, and mg input without changing archive or export contracts.

### Constraints
- No processor rewrite, no architecture migration, no normalized export contract change, no archive compatibility break.
- Keep batch/provenance/validation/report flows intact.
- Avoid touching unrelated modules.

### Impact Analysis
- Runtime files: `core/batch_runner.py`, `core/processing_schema.py`, `core/provenance.py`, `core/validation.py`.
- Regression files: `tests/conftest.py`, `tests/test_dsc_processor.py`, `tests/test_tga_processor.py`, `tests/test_batch_runner.py`, `tests/test_validation.py`.
- Process record: `bugs.md` for any concrete hardening bug fixed during the tranche.

### Risks
- Adding template-version context will expand `processing` payload contents, so tests must assert additive compatibility rather than exact old payload equality.
- TGA absolute-mass ambiguity near 100 units cannot be solved safely without an explicit unit input, so tests should lock only the unambiguous current paths.
- Deterministic fixtures must remain simple enough that numerical drift signals a real regression rather than fixture instability.

### Migration / Rollout Strategy
- Replace private-state reads with public processor snapshots first.
- Add template-version and calibration acceptance context through existing payload helpers.
- Expand deterministic fixtures and regression tests around current behavior.
- Verify the full suite before touching any recent batch/report flows.

### Test Strategy
- Run `pytest tests/test_dsc_processor.py tests/test_tga_processor.py tests/test_batch_runner.py tests/test_validation.py -q`.
- Run `pytest -q`.
- Run `pytest --collect-only -q`.

### Progress Log
- [x] Document and remove current private-state reliance in batch runner
- [x] Add additive template/version and calibration acceptance context
- [x] Add deterministic DSC/TGA regression fixtures and tests
- [x] Verify full suite and collect-count delta

### Notes
- The current risky private-state dependency is the direct use of `DSCProcessor._signal` in `core/batch_runner.py`; the goal is to remove that dependency without changing DSC numerics.
- Verification complete: focused regression run passed, `pytest -q` passed with `180 passed, 5 warnings`, and `pytest --collect-only -q` reported `180` collected tests (`+10` versus the previous `170` baseline).

---

## Title
TGA Unit-Mode Hardening for Ambiguous Inputs

### Objective
Make TGA unit interpretation explicit, reviewable, and reproducible inside the current brownfield flow by introducing an additive declared/resolved unit-mode context, preserving current auto defaults, and surfacing ambiguous low-range auto cases without changing normalized export or archive contracts.

### Definition Of Done
- TGA processing payloads carry declared and resolved unit mode plus auto-inference context.
- Validation distinguishes clear vs ambiguous auto-mode cases and warns on ambiguous low-range inputs.
- TGA processor accepts explicit `unit_mode` while preserving current default auto behavior.
- Saved TGA records and reports expose the richer unit interpretation context without changing the flat export schema.

### Constraints
- No TGAProcessor rewrite, no batch/provenance/report redesign, no archive format change, no flat CSV/XLSX contract change.
- Preserve current behavior for unambiguous inputs.
- Keep all changes additive and backward-compatible.

### Impact Analysis
- Runtime files: `core/tga_processor.py`, `core/processing_schema.py`, `core/validation.py`, `core/batch_runner.py`, `ui/tga_page.py`, `core/report_generator.py`.
- Regression files: `tests/test_tga_processor.py`, `tests/test_validation.py`, `tests/test_batch_runner.py`, `tests/test_report_generator.py`.
- Process record: `bugs.md` for the ambiguous low-range auto-mode hardening note.

### Risks
- Auto mode now prefers recorded signal units when they are available, which can change low-range mg-labeled runs from the old hidden percent path to the explicit absolute-mass path.
- Ambiguous low-range auto inputs intentionally keep the old percent numerics for compatibility, so scientific ambiguity is reduced through review signaling rather than a forced numeric change.
- Compare-workspace batch runs still need an existing TGA state if the user wants to override auto mode before running a batch template.

### Migration / Rollout Strategy
- Add a shared TGA unit-interpretation helper first.
- Persist declared/resolved unit mode through the existing processing payload.
- Reuse the same helper in validation, UI save flow, batch execution, and report rendering.
- Add deterministic regression coverage before verifying the full suite.

### Test Strategy
- Run `pytest tests/test_tga_processor.py tests/test_validation.py tests/test_batch_runner.py tests/test_report_generator.py -q`.
- Run `pytest -q`.
- Run `pytest --collect-only -q`.

### Progress Log
- [x] Add explicit TGA unit-mode context while preserving default auto behavior
- [x] Surface ambiguous low-range auto-mode review warnings without changing flat export or archive contracts
- [x] Persist declared/resolved unit mode through TGA UI and batch flows
- [x] Add deterministic processor/validation/batch/report regressions and verify full-suite delta

### Notes
- Ambiguous `auto` cases now keep the existing percent-processing path but are marked for review through validation/report context.
- Verification complete: focused regression run passed, `pytest -q` passed with `188 passed, 5 warnings`, and `pytest --collect-only -q` reported `188` collected tests (`+8` versus the previous `180` baseline).

---

## Title
Import Hardening and Professor Beta Pack

### Objective
Improve real-world DSC/TGA import reliability for professor beta testing by making import heuristics safer, review-aware, and better documented without changing the normalized result contract or project archive format.

### Definition Of Done
- `core.data_io` produces additive import-confidence and import-warning metadata for ambiguous imports.
- Clearly unambiguous TA/NETZSCH/generic delimited exports still import successfully.
- Validation surfaces import uncertainty so existing report/provenance flows can reflect it.
- Stable vs preview scope is tightened in the app messaging and repo docs.
- A concise professor beta guide exists inside the repo.

### Constraints
- No import architecture rewrite, no result/export schema change, no archive format change, no batch redesign.
- Only minimal UI touches around the existing import/preview flow.
- Focus on shipping confidence rather than adding new features.

### Impact Analysis
- Runtime files: `core/data_io.py`, `core/validation.py`, `ui/home.py`, `ui/components/data_preview.py`, `ui/components/workflow_guide.py`, `app.py`, `README.md`.
- Regression files: `tests/test_data_io.py`, `tests/test_validation.py`.
- Beta pack file: `PROFESSOR_BETA_GUIDE.md`.
- Process record: `bugs.md` for the import ambiguity hardening note.

### Risks
- More ambiguous files will now import with explicit review warnings instead of silent confidence.
- Vendor detection remains heuristic for text exports and still falls back to `Generic` when evidence is weak.
- README and UI messaging become narrower by design to avoid overclaiming during the beta.

### Migration / Rollout Strategy
- Add additive import metadata in `core.data_io` first.
- Reuse the metadata in validation and the existing home/data-preview surfaces.
- Tighten stable/preview wording and add the professor beta guide.
- Verify targeted import tests, then the full suite and collect-count delta.

### Test Strategy
- Run `pytest tests/test_data_io.py tests/test_validation.py -q`.
- Run `pytest -q`.
- Run `pytest --collect-only -q`.

### Progress Log
- [x] Add additive import-confidence and import-warning metadata
- [x] Harden column/type/unit/vendor inference for common text exports
- [x] Surface import review context in validation and the current import UI
- [x] Add professor beta guide and tighten stable vs preview messaging
- [x] Verify targeted import tests plus full-suite collect-count delta

### Notes
- Ambiguous imports now prefer explicit review metadata over hidden certainty; they are not silently promoted to the stable workflow as fully trusted.
- Verification complete: focused import/validation regression run passed, `pytest -q` passed with `197 passed, 5 warnings`, and `pytest --collect-only -q` reported `197` collected tests (`+9` versus the previous `188` baseline).

---

## Title
Windows Beta Installer Packaging

### Objective
Prepare the current Streamlit-based ThermoAnalyzer build for professor beta distribution as a Windows installer that requires no Python, pip, or terminal usage on the professor side.

### Definition Of Done
- A practical Windows packaging path exists for the current repo without rewriting the app.
- The packaged app launches from a desktop shortcut or Start Menu entry and opens the current local Streamlit workflow in the browser.
- Build scripts, installer config, and release instructions exist inside the repo.
- Professor-facing install instructions are updated to prefer the installer path over source setup.

### Constraints
- No architecture rewrite, no framework migration, no normalized result/export contract changes, and no `.thermozip` compatibility changes.
- Keep the current browser-based Streamlit runtime for beta delivery.
- Prefer the smallest reliable packaging path over an ambitious native desktop rewrite.

### Impact Analysis
- Packaging files: `packaging/windows/launcher.py`, `packaging/windows/ThermoAnalyzerLauncher.spec`, `packaging/windows/ThermoAnalyzer_Beta.iss`, `packaging/windows/build_beta_installer.ps1`, `packaging/windows/build_beta_installer.bat`, `packaging/windows/README.md`.
- Runtime support: `utils/diagnostics.py` for writable packaged log location.
- Repo docs: `README.md`, `PROFESOR_KURULUM_VE_KULLANIM_KILAVUZU.md`, `PROFESSOR_SETUP_AND_USAGE_GUIDE.md`, `PROFESSOR_BETA_GUIDE.md`, `.gitignore`.

### Risks
- Streamlit packaging is more reliable in `onedir` mode than `onefile`, but the installed folder will be larger.
- Browser-based local apps can still trigger first-launch firewall or browser prompts on some Windows systems.
- The installer build depends on Inno Setup being present on the build machine; that tool is not vendored in the repo.

### Migration / Rollout Strategy
- Add a small launcher that starts the current app locally and opens the browser.
- Package the launcher plus the existing repo runtime with PyInstaller `onedir`.
- Wrap the output with Inno Setup for desktop and Start Menu shortcuts.
- Update professor docs to use the installer flow instead of source setup.

### Test Strategy
- Run `python -m py_compile` on the packaging launcher and any runtime support files touched.
- Run `pytest -q` to confirm the existing app behavior still passes unchanged.
- Manually verify the build scripts and installer config for path consistency.

### Progress Log
- [x] Add launcher, PyInstaller spec, and Inno Setup installer config
- [x] Add build scripts and builder-facing packaging instructions
- [x] Update professor-facing install docs to the installer-first workflow
- [x] Verify syntax and full pytest suite

### Notes
- Chosen path: PyInstaller `onedir` + Inno Setup, so the current Streamlit app stays browser-based but installs like a normal Windows beta application.
- Verification complete: `python -m py_compile` passed for the launcher/spec/runtime support files, `pytest tests/test_diagnostics.py -q` passed, and `pytest -q` passed with `198 passed, 5 warnings`.
- Full installer generation was not executed in this environment because Inno Setup (`ISCC.exe`) was not present on the machine, but the build scripts and installer config were added and path-checked.
- GitHub Actions automation now reuses the same packaging path through `.github/workflows/windows-beta-installer.yml` and uploads `ThermoAnalyzer_Beta_Setup_<APP_VERSION>.exe` as an artifact.

---

## Title
Prerequisite-Aware Windows Bootstrap Installer

### Objective
Harden the current Windows beta installer into a prerequisite-aware bootstrapper so professors can install and launch ThermoAnalyzer without Python, pip, PATH edits, or manual runtime preparation.

### Definition Of Done
- The existing `PyInstaller onedir + Inno Setup` delivery path remains intact.
- The build process stages any external prerequisite installers that are still useful for compatibility hardening.
- The final `Setup.exe` checks install/runtime sanity and handles prerequisite installation automatically or with minimal guidance.
- GitHub Actions continues to produce the same one-click `Setup.exe` artifact.
- Professor-facing install docs describe the real install flow succinctly.

### Constraints
- No architecture rewrite, no framework migration, no normalized result/export changes, and no `.thermozip` compatibility changes.
- Keep the current browser-based Streamlit runtime and existing packaging workflow.
- Do not push Python, pip, PATH edits, or other technical setup steps onto the professor.

### Impact Analysis
- Packaging scripts: `packaging/windows/build_beta_installer.ps1`, `packaging/windows/build_beta_installer.bat`, `packaging/windows/ThermoAnalyzer_Beta.iss`.
- Packaged runtime launcher: `packaging/windows/launcher.py`.
- Builder/professor docs: `packaging/windows/README.md`, `PROFESSOR_SETUP_AND_USAGE_GUIDE.md`, `PROFESOR_KURULUM_VE_KULLANIM_KILAVUZU.md`, `PROFESSOR_BETA_GUIDE.md`.
- Repo tracking: `bugs.md`.

### Risks
- Visual C++ Redistributable installation may trigger a one-time Windows elevation prompt on systems where the runtime is absent.
- The build now depends on downloading the official Microsoft redistributable during packaging unless an explicit local path is supplied.
- Installer-side Pascal Script changes cannot be unit-tested through `pytest`; verification is limited to path/syntax review plus the unchanged Python test suite.

### Migration / Rollout Strategy
- Keep the current onedir bundle self-contained for Python and app dependencies.
- Stage the official Microsoft VC++ redistributable during the build and embed it into the installer without committing binaries to the repo.
- Add installer-side checks for free space and writable per-user runtime directories.
- Attempt silent/minimal VC++ compatibility installation only when the system runtime is missing.
- Update builder and professor docs to describe the new bootstrap behavior.

### Test Strategy
- Run `python -m py_compile packaging/windows/launcher.py`.
- Run `pytest -q`.
- Manually inspect the packaging scripts and GitHub Actions path consistency.

### Progress Log
- [x] Stage and verify external prerequisite payloads during the build
- [x] Add installer-side prerequisite checks and compatibility-runtime handling
- [x] Update docs for builder and professor bootstrap flow
- [x] Verify syntax plus the unchanged Python test suite

### Notes
- The desired professor flow remains `Setup.exe -> Next -> Install -> Finish -> Launch ThermoAnalyzer`.
- The bootstrapper should prefer bundling over manual setup and keep any unavoidable prerequisite handling as quiet and minimal as possible.
- The build script now downloads or accepts a local official `vc_redist.x64.exe`, verifies the Microsoft Authenticode signature, and embeds it into the installer without checking binaries into git.
- The Inno Setup bootstrapper now validates install/runtime disk space, checks that `%LOCALAPPDATA%\ThermoAnalyzer Beta` is writable, and conditionally installs the VC++ compatibility package while keeping the existing per-user installer flow.
- Verification complete: PowerShell parsing passed for `packaging/windows/build_beta_installer.ps1`, `python -m py_compile packaging/windows/launcher.py tests/test_windows_launcher.py` passed, `pytest tests/test_windows_launcher.py -q` passed, and the full suite passed with `199 passed, 5 warnings`.
- Full installer compilation was still not executed in this environment because `ISCC.exe` is not installed on the machine; GitHub Actions remains the supported automated build path for the final `Setup.exe` artifact.

---

## Title
Professor-Friendly Packaged Help Files

### Objective
Replace the Markdown-only packaged help surface with simpler Turkish-first end-user help files that non-technical professors can open easily from the installed application.

### Definition Of Done
- The installed docs folder includes a concise Turkish `README.txt`.
- The installed docs folder includes a concise Turkish `HELP.html` for easier reading.
- Start Menu shortcuts expose the Turkish-first simple help files instead of only Markdown documents.
- Existing Markdown docs remain in the repo for deeper reference and developer use.

### Constraints
- No installer redesign, no architecture rewrite, no workflow redesign, no normalized export/result changes, and no `.thermozip` changes.
- Keep the current packaging path and app behavior intact.
- Keep the help wording short, practical, and non-technical.

### Impact Analysis
- New packaged docs: `packaging/windows/end_user_docs/README.txt`, `packaging/windows/end_user_docs/HELP.html`.
- Installer wiring: `packaging/windows/ThermoAnalyzer_Beta.iss`.
- Builder note: `packaging/windows/README.md`.

### Risks
- None on the app/runtime side; this tranche only changes packaged documentation exposure.
- The HTML help should remain simple enough to render correctly with any default browser on Windows.

### Migration / Rollout Strategy
- Add Turkish-first TXT + HTML help files.
- Keep the existing packaged Markdown files if still useful, but stop making them the primary Start Menu help surface.
- Expose the Turkish HTML help as the primary packaged help shortcut and keep the TXT file as a fallback.

### Test Strategy
- Run `pytest -q` to confirm no behavior regression from installer/doc packaging edits.
- Manually inspect the installer script for packaged file and shortcut changes.

### Progress Log
- [x] Add Turkish-first TXT and HTML help files
- [x] Update the installer docs payload and Start Menu shortcuts
- [x] Verify the unchanged test suite

### Notes
- Chosen path: package both TXT and HTML. `README.txt` is the most robust fallback, and `HELP.html` is the easiest primary reading experience for non-technical professors.
- The installer now copies `packaging/windows/end_user_docs/README.txt` and `packaging/windows/end_user_docs/HELP.html` into `{app}\docs`.
- Start Menu help exposure is now Turkish-first: `Yardim` opens the HTML help page and `Hizli Baslangic` opens the TXT quick guide.
- Verification complete: `pytest -q` passed with `199 passed, 5 warnings`.
