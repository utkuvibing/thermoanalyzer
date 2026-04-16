# Active task — MaterialScope

**Purpose:** **One active migration slice**—scope, goal, and **acceptance** only. Workflow philosophy: **`.cursor/rules/00-workflow.mdc`**. Durable design decisions: **`.ai/DECISIONS.md`** only.

**Title:** Dash DTA — smoothing param overrides + undo/redo scaffold (Phase 1 parity slice)

**Status (handoff 2026-04-16):** **Complete — committed + pushed** as `040f31d` on `origin/web-dash-plotly-migration`. Phase 2 (baseline + peak controls, literature compare, figure capture) is the next slice; rewrite this file when the user sends the Phase 2 prompt.

## Goal

Prove the per-step parameter override channel end-to-end for Dash DTA with the smallest user-visible change: expose **smoothing** controls (method, window length, polyorder, sigma) with **Apply / Undo / Redo / Reset** in `dash_app/pages/dta.py`, persist the draft in `dcc.Store`s, and forward the draft to `/analysis/run` as `processing_overrides`. This unblocks baseline/peak controls (same channel) in a subsequent slice without a big-bang rewrite.

*(Rationale: plan `Dash DTA parity audit`, sections 4-6.)*

## In-scope

- **`backend/models.py`** — add optional `processing_overrides: dict[str, Any] | None` to `AnalysisRunRequest`.
- **`backend/app.py`** — new private `_apply_processing_overrides` helper; `/analysis/run` merges overrides into `state[analysis_state_key(...)]["processing"]` via `core.processing_schema.update_processing_step` / `update_method_context` before `run_single_analysis`.
- **`dash_app/api_client.py`** — `analysis_run(...)` gains an optional `processing_overrides` kwarg forwarded in the POST body.
- **`dash_app/pages/dta.py`** — smoothing controls card; `dcc.Store`s `dta-processing-default` / `dta-processing-draft` / `dta-processing-undo` / `dta-processing-redo`; buttons `dta-smooth-apply-btn` / `dta-undo-btn` / `dta-redo-btn` / `dta-reset-btn`; pure helpers `_default_processing_draft`, `_normalize_smoothing_values`, `_apply_draft_section`, `_push_undo`, `_do_undo`, `_do_redo`, `_do_reset`, `_smoothing_overrides_from_draft`; `run_dta_analysis` now reads the draft and forwards overrides.
- **`tests/test_dta_dash_page.py`** — added helper unit tests (normalize + apply + undo/redo/reset + overrides extractor + layout), backend override propagation test (`/analysis/run` honors `processing_overrides`), unsupported-section rejection (400), and `api_client.analysis_run` forwarding test.

## Out-of-scope

- **Baseline and peak-detection** controls (Phase 2 via same override channel).
- **Full `dbc.Tabs` stepwise layout** (Phase 3).
- **Preset save/load/delete panel** (Phase 3; `core.preset_store` reuse).
- **Manual literature-compare panel** in Results Summary (Phase 2; endpoint exists).
- **Figure capture for Report Center** (`artifacts.figure_keys` + PNG bytes) (Phase 2).
- **`core/` scientific changes**, **Streamlit `ui/`** changes, **other Dash modalities**, repo-wide cleanup.

## Acceptance criteria

- [x] `/analysis/run` accepts `processing_overrides` and merges per-step values into `state[state_key].processing` before execution; result detail reflects the overridden values (e.g. `signal_pipeline.smoothing.window_length == 21`).
- [x] Unsupported override sections return HTTP 400 (e.g. `normalization` for DTA).
- [x] Dash DTA page exposes smoothing controls + Apply/Undo/Redo/Reset buttons; draft/undo/redo/default stores present in layout; Run forwards draft as `processing_overrides`.
- [x] Existing DTA Dash page tests still pass (24 pre-slice, 35 after).
- [x] No `core/` scientific code changed; no Streamlit changes; no other Dash modality pages changed.
- [x] **Verification recorded** with outcome:
  - **Primary (targeted):** `python -m pytest tests/test_dta_dash_page.py -q --tb=short` → **pass** (35 tests).
  - **Backend sanity (adjacent):** `python -m pytest tests/test_backend_api.py tests/test_backend_modality_dispatch.py tests/test_backend_startup.py -q --tb=short` → **pass** (34 passed, 2 skipped).
- [x] **`.ai/DECISIONS.md`** — one entry for the override approach (see that file).
- [x] **`.ai/SESSION.md`** updated for carryover / next step.
- [x] **Commit / push** — committed + pushed as `040f31d` on `origin/web-dash-plotly-migration` on user request (2026-04-16); scope limited to the 9 Phase 1 files, unrelated tracked-file drift kept out of the commit.

## Quick checklist

1. [x] Read `dash_app/pages/dta.py`, `dash_app/components/analysis_page.py`, `dash_app/api_client.py`, `backend/app.py`, `backend/models.py`, `core/batch_runner.py`, `core/processing_schema.py` before editing.
2. [x] Implement only the smoothing override channel + scaffolding; no drift into baseline/peaks/literature/presets/figure-capture.
3. [x] Run targeted + adjacent verification; record outcomes above.
