# ThermoAnalyzer Codex Guide

## Project Scope
- Build a vendor-independent DSC/TGA analysis workbench on top of Streamlit.
- Protect scientific correctness, reproducible exports, and project round-trip behavior.
- Keep `core/` computation-focused and UI-independent whenever possible.

## Non-Goals
- Do not invent new product features unless explicitly requested.
- Do not touch auth, billing, deployment, packaging, or infrastructure unless explicitly requested.
- Do not broaden scope into a general LIMS or compliance platform during routine tasks.

## Core Commands
- Install dependencies: `pip install -r requirements.txt`
- Run app locally: `streamlit run app.py`
- Run full test suite: `pytest -q`
- Run a focused test file: `pytest tests/<name>.py -q`

## Working Rules
- For any multi-file change or architecture-impacting task, start with a short plan.
- If the task is large, long-running, or likely to span multiple turns, document it in [plans.md](/C:/thermoanalyzer/plans.md) before implementation.
- Before saying work is done, run the relevant tests. This repo does not currently have a dedicated lint or typecheck command; do not claim they were run unless you added/configured them.
- Keep fixes minimal when the request is a bug fix.
- Do not change API/data shapes casually. If you change the normalized result schema, update `core/result_serialization.py`, `core/report_generator.py`, `core/project_io.py`, related UI pages, and tests together.
- When a bug is investigated or fixed, add a concise entry to [bugs.md](/C:/thermoanalyzer/bugs.md) with repro, suspected cause, attempted fix, and actual fix.

## Directory Notes
- `core/`: numerical methods, serialization, report/project IO. Keep free of Streamlit dependencies unless there is a strong reason.
- `ui/`: Streamlit pages and presentation logic only.
- `utils/`: session, i18n, licensing, and small helpers. Avoid moving domain analysis logic here.
- `tests/`: add or update regression coverage when behavior changes.

## Definition Of Done
- Requested behavior is implemented with minimal scope creep.
- Relevant tests pass locally, or any test gap/blocker is stated explicitly.
- User-facing changes are reflected in the appropriate page/report/export flow.
- Schema or workflow changes include regression coverage when feasible.

## Review Expectations
- Prioritize correctness, regressions, data loss risk, export/report breakage, and analysis integrity.
- Flag missing tests when behavior changes without coverage.
- Summaries should mention what changed, what was verified, and any residual risks.
