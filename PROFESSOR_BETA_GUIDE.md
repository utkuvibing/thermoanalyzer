# Professor Beta Guide

For installation and day-to-day usage instructions, use the setup guide that matches your language first:

- Turkish: [PROFESOR_KURULUM_VE_KULLANIM_KILAVUZU.md](PROFESOR_KURULUM_VE_KULLANIM_KILAVUZU.md)
- English: [PROFESSOR_SETUP_AND_USAGE_GUIDE.md](PROFESSOR_SETUP_AND_USAGE_GUIDE.md)

This file is the shorter beta-scope and feedback guide.

For professor beta distribution, the expected installation path is the Windows installer build. Professors should not need Python, pip, or terminal commands.

## Scope
This beta is intended for controlled academic evaluation of the current stable workflow:

- DSC analysis
- TGA analysis
- Compare Workspace
- Batch Template Runner
- Report / export generation
- Project save / load with `.thermozip`

Preview-only modules remain available behind the preview toggle and are **not** part of the stable beta promise:

- DTA
- Kinetics
- Peak deconvolution

## Recommended Files
Use exported text or spreadsheet files from existing instruments:

- CSV
- TXT / TSV
- XLSX / XLS

Best current import reliability:

- generic delimited exports with clear headers
- TA-style text exports
- NETZSCH-style text exports

Avoid relying on this beta for:

- proprietary binary formats
- poorly labeled columns without manual review
- mixed or partially edited exports where units were removed

## Recommended Test Workflow
1. Import one or more DSC/TGA runs.
2. Check the reported import confidence, inferred analysis type, inferred signal unit, and any import warnings.
3. Confirm column mapping and key metadata:
   - sample name
   - sample mass
   - heating rate
   - atmosphere for TGA
   - calibration metadata if available
4. Use Compare Workspace for overlay review.
5. Run DSC or TGA analysis on a validated run.
6. Save the stable result to the session.
7. Export:
   - normalized result summary
   - DOCX/PDF report
   - `.thermozip` project archive
8. If testing repeatability, run the Batch Template Runner on multiple compatible runs.

## What To Test Carefully
- import correctness on your real lab exports
- whether the inferred analysis type is correct
- whether the inferred signal unit is correct
- whether batch-applied templates give repeatable outputs on similar runs
- whether saved projects reopen with the same stable results
- whether report content matches the analysis settings and run context

## What Not To Trust Yet
- preview modules as production-ready analysis workflows
- ambiguous imports that carry review warnings unless you manually confirm them
- unsupported or proprietary file formats
- any workflow that depends on missing calibration metadata being treated as fully verified

## Most Valuable Feedback
- files that import with the wrong data type, wrong signal column, wrong unit, or wrong vendor
- files that only work after manual column mapping
- DSC/TGA runs that produce scientifically suspicious results even though import looks clean
- report wording that is misleading or omits critical method context
- project archives that do not reopen into the same practical working state

## How To Report Issues
Please include:

- the original input file if it can be shared
- the exact page and workflow that were used
- the observed problem
- the expected result
- screenshots if a plot or table looks wrong
- exported support snapshot JSON
- `.thermozip` archive if the issue is reproducible from a saved project

## Support Snapshot
The current build can export a support snapshot from **Report Preview -> Support Diagnostics**.

Recommended bug-report attachments:

- `thermoanalyzer_support_snapshot.json`
- the relevant input file(s)
- the generated `.thermozip` archive, if available

## Practical Beta Boundary
If a workflow stays inside:

- Import
- Compare Workspace
- DSC or TGA
- Batch Template Runner
- Report / export
- Project save / load

then it is inside the current controlled academic beta scope.
