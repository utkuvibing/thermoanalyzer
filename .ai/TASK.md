# Active task — MaterialScope

**Purpose:** **One active migration slice**—scope, goal, and **acceptance** only. Workflow philosophy: `**.cursor/rules/00-workflow.mdc`**. Durable design decisions: `**.ai/DECISIONS.md**` only.

**Title:** Dash DTA — processing preset save/load/delete via new backend endpoints + api_client + DTA preset panel (Phase 3b parity slice)

**Status (opened 2026-04-16):** In progress. Follows Phase 3a (stepwise tabs, local only — not yet committed; user asked to commit the whole Phase 3 at once). Phase 3b adds the preset CRUD surface the Streamlit `ui/components/preset_manager.py` already offers to the Dash DTA page, via four new FastAPI routes backed by the existing `core.preset_store` SQLite store, matching `dash_app/api_client.py` helpers, and a new preset card rendered inside the Processing tab.

## Goal

Bring Streamlit-DTA processing-preset parity to the Dash DTA page by exposing the existing `core.preset_store` through the backend and wiring a preset panel into the Processing tab:

1. Persist user processing presets across sessions (save / list / load / delete) without leaving the Dash DTA page.
2. Applying a preset restores its `workflow_template_id` in the workflow dropdown **and** replays its `processing` section onto the current draft, while pushing the previous draft onto the existing Undo stack.
3. The preset count / max (10 per analysis, per `core.preset_store.MAX_PRESETS_PER_ANALYSIS`) is visible to the user; server rejects overflow and reports clear errors.

## Approach summary

- Add four FastAPI routes under `/presets/{analysis_type}` backed by `core.preset_store` (no project scoping — presets are user-wide, matching Streamlit). Map `PresetLimitError` → 409, `PresetStoreError` → 400, missing → 404.
- Add new pydantic models: `PresetSummary`, `PresetListResponse`, `PresetSaveRequest`, `PresetSaveResponse`, `PresetLoadResponse`, `PresetDeleteResponse`.
- Add four `dash_app/api_client.py` helpers (`list_analysis_presets`, `save_analysis_preset`, `load_analysis_preset`, `delete_analysis_preset`).
- In `dash_app/pages/dta.py`, add a `_preset_controls_card()` rendered as the first card in the Processing tab, plus a `dcc.Store("dta-preset-refresh")` that signals list reloads on save/delete. New callbacks: preset list refresh, apply, save, delete, action-button enabling, locale chrome.
- Add TR+EN i18n keys under `dash.analysis.dta.presets.*`.
- Isolate backend tests from real user storage by setting `MATERIALSCOPE_HOME` to a tmp path (same pattern `tests/test_preset_store.py` already uses).

## In-scope

- `**backend/models.py`** — add 6 preset pydantic models.
- `**backend/app.py**` — add 4 routes (`GET /presets/{analysis_type}`, `POST /presets/{analysis_type}`, `GET /presets/{analysis_type}/{preset_name}`, `DELETE /presets/{analysis_type}/{preset_name}`).
- `**dash_app/api_client.py**` — add 4 helpers.
- `**dash_app/pages/dta.py**` — add `_preset_controls_card()`, mount it as the first child of the Processing tab, add `dcc.Store("dta-preset-refresh")`, add 5 callbacks (refresh-list, apply, save, delete, action-button-enable) and one locale-chrome callback.
- `**utils/i18n.py**` — add TR+EN entries under `dash.analysis.dta.presets.*`.
- `**tests/test_backend_presets_api.py**` (new) — 8 endpoint tests (list, save, upsert, limit, invalid-name, load-404, delete-200, delete-404) with `MATERIALSCOPE_HOME` monkeypatched to `tmp_path`.
- `**tests/test_dta_dash_page.py**` — append 7 Phase 3b tests (panel IDs mounted in Processing tab, 4 api_client helper forwarding tests, apply-callback mutates draft + template, refresh-callback populates dropdown).

## Out-of-scope (explicitly deferred)

- Phase 3c — richer Results Summary parity (dataset metadata, applied processing summary, quality metrics).
- Auto-advancing tabs after apply/save (still out of scope for 3c as well — Phase 4).
- Preset export/import across machines.
- Other modalities (DSC, TGA, FTIR, Raman, XRD) — this slice touches only the DTA page, but the backend routes are analysis-agnostic and will serve future slices without rework.

## Acceptance criteria

- Backend exposes `GET /presets/DTA`, `POST /presets/DTA`, `GET /presets/DTA/{name}`, `DELETE /presets/DTA/{name}` with the token pattern used by the rest of `backend/app.py` and with the 6 new response/request models listed above.
- `PresetLimitError` surfaces as HTTP 409; `PresetStoreError` (invalid name/payload, unsupported analysis_type) surfaces as HTTP 400; missing preset on load/delete surfaces as 404.
- `dash_app/api_client.py` exposes `list_analysis_presets`, `save_analysis_preset`, `load_analysis_preset`, `delete_analysis_preset` matching the route shape.
- Processing tab on the DTA page renders the new preset card with: title, count/max caption, preset dropdown, Apply + Delete buttons, new-name input, Save button, status region.
- Applying a preset restores `workflow_template_id` (via `dta-template-select.value`) + replays `processing` onto `dta-processing-draft`, pushes prior draft onto `dta-processing-undo`, and shows a success status message. Unknown template ids are ignored (dash.no_update).
- Saving / deleting re-fetches the list via `dta-preset-refresh`; save respects `MAX_PRESETS_PER_ANALYSIS` and surfaces 409 as an error status; invalid preset names surface 400 as an error status (asserted by the backend tests; the Dash-side callbacks route the backend message into the status region verbatim).
- TR and EN strings for the new chrome, buttons, and status messages are present in `utils/i18n.py` under `dash.analysis.dta.presets.*`; EN fallback is handled via existing `translate_ui()`.
- All existing 57 Phase-3a DTA Dash-page tests still pass; all existing preset_store + backend tests still pass.
- **Verification recorded** with outcome (2026-04-16, Windows):
  - Primary (backend): `python -m pytest tests/test_backend_presets_api.py -x -q` → **10 passed** in 3.67s (list empty, save+list, upsert-no-slot, limit→409, empty-name→400, load→404, load happy, delete+404-on-second, token required, unsupported-type→400).
  - Primary (dash): `python -m pytest tests/test_dta_dash_page.py -x -q` → **69 passed** in 7.22s (57 → 69 with +12 Phase 3b tests: panel IDs in Processing tab, preset-refresh store, 4 api_client helper forwarding tests, apply-pushes-undo+updates-draft+template, apply-ignores-unknown-template, refresh populates list, refresh reports backend error, chrome TR/EN flip, button disabled-when-empty).
  - Preset parity (legacy + new): `python -m pytest tests/test_backend_presets_api.py tests/test_preset_store.py -q` → **14 passed** in 3.07s.
  - Adjacent: `python -m pytest tests/ -q -k "preset or dash or backend_api or i18n"` → **164 passed, 1 skipped, 657 deselected, 8 warnings** in 21.06s. No regressions.
- `.ai/SESSION.md` + `.ai/TASK.md` updated on completion.
- **Commit / push** — still pending; user deferred until **all** of Phase 3 is done (3a + 3b + 3c).

## Quick checklist

1. [x] Added 6 preset models in `backend/models.py` (`PresetSummary`, `PresetListResponse`, `PresetSaveRequest`, `PresetSaveResponse`, `PresetLoadResponse`, `PresetDeleteResponse`).
2. [x] Added 4 routes in `backend/app.py` next to the figure-register / compare routes; mapped `PresetLimitError` → 409, `PresetStoreError` → 400, missing → 404. All gated by `_require_token` via `X-TA-Token`.
3. [x] Added 4 helpers in `dash_app/api_client.py` following the `register_result_figure` / `literature_compare` style.
4. [x] Added 19 TR+EN keys under `dash.analysis.dta.presets.`* in `utils/i18n.py` (chrome, captions, placeholders, success/error messages).
5. [x] Added `_preset_controls_card()` + `dcc.Store("dta-preset-refresh")` + 6 callbacks in `dash_app/pages/dta.py` (`render_dta_preset_chrome`, `refresh_dta_preset_options`, `toggle_dta_preset_action_buttons`, `apply_dta_preset`, `save_dta_preset`, `delete_dta_preset`). Card is mounted as the first `dbc.Tab` child of the Processing tab, so all preset controls share the Processing-tab step with the other user-tunable controls.
6. [x] Added `tests/test_backend_presets_api.py` (10 tests) and appended 12 Phase 3b tests in `tests/test_dta_dash_page.py`.
7. [x] Ran targeted + adjacent verification; outcomes recorded above.

## Post-3b follow-up (2026-04-16, same day)

**Bug fix — user-reported:** `Could not save preset: name '_combined_processing_overrides' is not defined`. The `save_dta_preset` callback referenced a non-existent helper; the actual helper in `dash_app/pages/dta.py` is `_overrides_from_draft`. Fixed inline. Added 3 regression tests that exercise the `save_dta_preset` / `delete_dta_preset` callback **bodies** (not just the api_client shape) so the next undefined-symbol regression gets caught before it ships:

- `test_save_dta_preset_forwards_overrides_and_returns_refresh_bump` — runs the callback with a mocked `api_client.save_analysis_preset`, asserts all three processing sections (smoothing, baseline, peak_detection) + the template id + name reach the helper, the refresh token bumps, and the name input clears.
- `test_save_dta_preset_reports_backend_failure_without_bumping_refresh` — asserts the error branch returns `dash.no_update` for refresh + name (no token churn) and surfaces the backend message in the status region.
- `test_delete_dta_preset_bumps_refresh_and_clears_selection` — symmetric exercise of the delete callback body.

**Feature — inline help hints on every DTA processing control (pre-3c polish):** Users asked for short explanations of what each setting does and which direction to tune. Added an `html.Small` with `className="form-text text-muted d-block mt-1"` under **every** user-tunable control across the Processing tab:

- Smoothing card: method / window / polyorder / sigma (4 hints).
- Baseline card: method / lam / p (3 hints).
- Peak-detection card: detect_exo / detect_endo / prominence / distance (4 hints).
- Preset card: single overview hint right under the card title (1 hint).

Each hint has a stable DOM id (e.g. `dta-smooth-method-hint`) and is populated via the **existing** per-card chrome callbacks extended with extra `Output` entries — no new callbacks, no new stores. 12 new TR+EN i18n keys under `dash.analysis.dta.{smoothing,baseline,peaks}.help.`* + 1 under `dash.analysis.dta.presets.help.overview`. Each hint text is 1 sentence that names the effect and gives a direction cue ("raise to ignore noise; lower to catch subtle events").

**Verification (2026-04-16, Windows):**

- `python -m pytest tests/test_dta_dash_page.py -x -q` → **76 passed** in 5.02s (was 69; +3 save/delete regression + 4 hint-rendering tests).
- `python -m pytest tests/ -q -k "preset or dash or backend_api or i18n or dta"` → **197 passed, 1 skipped, 631 deselected, 8 warnings** in 21.02s. No regressions.

