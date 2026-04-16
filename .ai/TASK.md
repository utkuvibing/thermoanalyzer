# Active task — MaterialScope

**Purpose:** **One active migration slice**—scope, goal, and **acceptance** only. Workflow philosophy: **`.cursor/rules/00-workflow.mdc`**. Durable design decisions: **`.ai/DECISIONS.md`** only.

**Title:** Dash DTA — manual literature compare panel + figure capture for Report Center (Phase 2b parity slice) + i18n + palette fixup for Phase 2a/2b chrome

**Status (opened 2026-04-16):** In progress. Follows Phase 2a (baseline + peak-detection overrides, local only — not yet committed). Together Phase 2a + Phase 2b close the DTA parity gaps identified in the original audit, leaving Phase 3 (stepwise tabs, presets, richer summary) and Phase 4 (polish) as the remaining work. A follow-up **i18n + palette fixup** (2026-04-16) then translated every Phase 2a/2b panel string to TR+EN and realigned two out-of-palette buttons to the codebase palette convention.

## Goal

Close the last two Streamlit-vs-Dash DTA parity gaps that depend on a completed analysis:

1. **Manual literature compare panel** — let a user fetch literature matches for the saved DTA result via the existing `POST /workspace/{project_id}/results/{result_id}/literature/compare` endpoint and render the claims / comparisons / citations in the Results Summary.
2. **Figure capture for Report Center** — ensure a successful DTA run publishes a PNG figure the Report Center picks up via `artifacts.figure_keys` + `state["figures"]`, matching how `ui/dta_page.py::_store_dta_result` writes a figure entry today.

*(Rationale: plan `Dash DTA parity audit` sections 4-6. Streamlit already populates `state["figures"]` per modality; `backend/exports.py::_selected_figures` uses `core.result_serialization.collect_figure_keys` to assemble the report figure set. The Dash path currently never writes figures, so Report Center exports for Dash-saved DTA results have no figures.)*

## Approach summary

Two deliberately independent sub-slices bundled into one slice because they share no code surface:

**A. Figure capture (modality-agnostic backend + DTA-specific client hook)**
- Add a new backend endpoint `POST /workspace/{project_id}/results/{result_id}/figure` that accepts a base64 PNG + label, writes bytes into `state["figures"][label]`, and de-dupes the label into `state["results"][result_id]["artifacts"]["figure_keys"]`. The endpoint is modality-agnostic so Phase 3+ can reuse it for DSC/TGA/XRD/etc.
- Add `dash_app/api_client.register_result_figure(project_id, result_id, png_bytes, *, label, replace=False)`.
- In `dash_app/pages/dta.py`: new callback `capture_dta_figure` triggered by successful run (`Input("dta-latest-result-id", "data")`). It fetches detail, rebuilds the figure via the existing `_build_figure`, renders to PNG via `plotly.io.to_image(..., format="png", engine="kaleido")`, and calls `register_result_figure`. Dedup per result_id via a new `dcc.Store` `dta-figure-captured`. Failures (e.g. kaleido missing) degrade gracefully (no crash, logged).

**B. Literature compare panel**
- Add `dash_app/api_client.literature_compare(project_id, result_id, *, max_claims=3, persist=False, provider_ids=None, filters=None, user_documents=None)`.
- In `dash_app/pages/dta.py`: new `_literature_compare_card()` rendered in the Results Summary column below the result metrics. Controls: `max_claims` number input, `persist` checkbox (default False), Compare button. Gated on `dta-latest-result-id` presence. Renders returned `literature_claims` + `literature_comparisons` + `citations` in a compact structure.

## In-scope

- **`backend/models.py`** — new `ResultFigureRegisterRequest(figure_png_base64: str, figure_label: str, replace: bool = False)` and `ResultFigureRegisterResponse(project_id, result_id, figure_key, figure_keys)`.
- **`backend/app.py`** — new `@app.post("/workspace/{project_id}/results/{result_id}/figure", response_model=ResultFigureRegisterResponse)`; 404 on unknown `result_id`, 400 on bad base64 or empty label.
- **`dash_app/api_client.py`** — `literature_compare(...)` + `register_result_figure(...)`.
- **`dash_app/pages/dta.py`** — literature-compare card (new `_literature_compare_card()` + `compare_literature` callback + `render_literature_compare_chrome` locale callback); figure-capture callback `capture_dta_figure` + new `dcc.Store` `dta-figure-captured`; results summary column re-layout to include the new card.
- **`tests/test_dta_dash_page.py`** — tests for: api_client literature_compare forwarding, api_client register_result_figure forwarding, backend figure-register endpoint (happy path + 404 unknown result_id + 400 bad base64), layout wiring (literature card + figure-captured store), literature-compare callback renders claims + gated on result_id.

## Out-of-scope (explicitly deferred)

- Presets save/load/delete panel (Phase 3; `core.preset_store` reuse).
- Full `dbc.Tabs` stepwise layout (Phase 3).
- Quality dashboard, raw-tab metadata, translation polish, keyboard shortcuts (Phase 4).
- `core/` scientific changes; any Streamlit `ui/` changes; any other Dash modality.
- Any **provider registry mutation** UI (e.g. add/remove providers) — panel uses defaults/None so backend picks the default provider for DTA.
- **Automatic** figure re-capture on theme / locale change — only on result_id change.
- Exposing all backend literature fields (`filters`, multiple user_documents) in the UI — keep panel minimal; backend supports them via the api_client helper for future panels.

## Acceptance criteria

- [x] `POST /workspace/{pid}/results/{rid}/figure` writes PNG bytes into `state["figures"]` and de-dupes the label into `state["results"][rid]["artifacts"]["figure_keys"]`; 404 on unknown `rid`, 400 on bad base64 / empty label, 409 on duplicate label without `replace=True`.
- [x] `api_client.register_result_figure` base64-encodes PNG bytes and POSTs correctly; `api_client.literature_compare` forwards `provider_ids`, `max_claims`, `persist`, `filters`, `user_documents` and returns response JSON.
- [x] DTA Results Summary includes a literature-compare card that is disabled without a saved `result_id` and enabled afterwards; Compare button calls the endpoint and renders claims + comparisons + citations sections.
- [x] After a successful run, the `capture_dta_figure` callback fires once per result_id, posts a PNG, and updates `dta-figure-captured`; callback degrades silently when `plotly.io.to_image` raises (kaleido missing).
- [x] Existing 43 DTA Dash-page tests still pass; new Phase 2b tests pass (total: 53 passing, up from 43 in Phase 2a).
- [x] No `core/` scientific code changed; no Streamlit changes; no other Dash modality pages changed.
- [x] **Verification recorded** with outcome:
  - Primary (targeted): `python -m pytest tests/test_dta_dash_page.py -q --tb=short` → **53 passed** (Phase 2a was 43; +10 Phase 2b tests).
  - Backend sanity (adjacent): `python -m pytest tests/test_backend_api.py tests/test_backend_modality_dispatch.py tests/test_backend_startup.py tests/test_backend_exports.py -q --tb=short` → **45 passed, 2 skipped** (unchanged from baseline).
- [x] `.ai/DECISIONS.md` — entry added: "2026-04-16 — Dash figure capture: client-side PNG + modality-agnostic backend endpoint" (kaleido in Dash client, modality-agnostic endpoint, alternatives considered and rejected).
- [x] `.ai/SESSION.md` + `.ai/TASK.md` updated on completion.
- [x] **i18n + palette fixup (2026-04-16):** `utils/i18n.py` gained TR+EN entries for all `dash.analysis.dta.{smoothing,baseline,peaks,literature,undo_btn,redo_btn,reset_btn}.*` keys referenced by Phase 1/2a/2b chrome+status callbacks (previously the `_t(...)` / `_literature_t(...)` wrappers were silently falling back to hardcoded English because the keys were never in the bundle). `dash_app/pages/dta.py`: `dta-reset-btn` `color="warning"` → `"secondary"` outline (Bootstrap yellow is not overridden in `dash_app/assets/style.css` and clashed with the cream/parchment palette — `secondary` outline is the same style used by Undo/Redo and by the Home stepper back buttons); `dta-literature-compare-btn` `color="info"` → `"primary"` (Bootstrap cyan not overridden; `primary` is the standard apply/compare button class, matching Apply Smoothing / Apply Baseline / Apply Peaks / Save Project / Run). No backend changes. **Verify:** `python -m pytest tests/test_dta_dash_page.py -q` → **53 passed**; `python -m pytest tests/ -q -k "dash or i18n or dta or literature"` → **236 passed, 560 deselected, 8 warnings**.
- [ ] **Commit / push** — on user request only (Phase 2a + Phase 2b + i18n/palette fixup currently staged together in working tree).

## Quick checklist

1. [x] Read `/literature/compare` endpoint shape (`backend/app.py:674-736`, `backend/models.py:362-377`), Streamlit figure path (`ui/dta_page.py:76-130`), Report Center figure collection (`backend/exports.py:135-153`, `core/result_serialization.py:1844-1861`), `core/batch_runner.py` result-record creation (`artifacts={}` — batch_runner does not write figures).
2. [x] Implement figure-register endpoint + api_client helpers + DTA page panel + capture callback. No drift into other modalities, presets, tabs, or locale polish.
3. [x] Run targeted + adjacent verification; record outcomes above.
