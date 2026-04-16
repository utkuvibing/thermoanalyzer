# Decisions — MaterialScope

**This file is the only durable log for design, architecture, and workflow commitments.** Session notes belong in **`.ai/SESSION.md`**; slice completion in **`.ai/TASK.md`**; defects in **`.ai/BUGS.md`**. Process details: **`.cursor/rules/00-workflow.mdc`**.

---

## 2026-04-16 — Single implementation thread

**Decision:** Prefer **one main implementation thread** per task (sequential beats, one contributor stance).

**Reason:** Reduces conflicting edits, duplicated planning, and “handoff fiction” that does not match how work is done in-repo.

---

## 2026-04-16 — Repository files as external memory

**Decision:** Treat **`.ai/*`**, **`.cursor/rules/*`**, and the codebase as the **source of continuity**; chat is auxiliary.

**Reason:** Inspectable state; fewer stale assumptions.

---

## 2026-04-16 — Modality-by-modality migration

**Decision:** Advance Dash + Plotly **by modality or bounded slice**, not big-bang UI rewrites.

**Reason:** Small blast radius; easier verification; protects working surfaces.

---

## 2026-04-16 — Small verifiable increments

**Decision:** Default to **small diffs** with **explicit verification** before calling a slice done.

**Reason:** Migration-era drift; incremental proof catches regressions early.

---

## 2026-04-16 — Dash DTA parity: per-step param overrides via `/analysis/run`

**Decision:** For Dash DTA parity with Streamlit's interactive pipeline, introduce a single **additive** backend channel — `AnalysisRunRequest.processing_overrides: dict[str, dict] | None` — keyed by processing section name (`smoothing`, `baseline`, `peak_detection`, `method_context`). The backend merges overrides into `state[analysis_state_key(analysis_type, dataset_key)]["processing"]` via the canonical `core.processing_schema.update_processing_step` / `update_method_context` helpers **before** calling `run_single_analysis`. The existing `core._build_processing_payload` already merges `existing_processing` over template defaults, so user-tuned params win automatically with **zero `core/` changes**. Dash side keeps the draft payload in `dcc.Store`s with a separate `undo` stack, `redo` stack, and `default` snapshot; Apply mutates the draft, Run flushes it as the overrides field.

**Reason:** Smallest blast radius for unlocking all P1 DTA controls (smoothing, baseline, peaks) from one channel. Preserves Streamlit's record/state shape (`serialize_dta_result`, `make_result_record`). Avoids a parallel Dash-only processing architecture. Testable end-to-end through `/analysis/run` + `/workspace/{pid}/results/{rid}`.

**Consequence / future:** Phase 2 reuses this channel for baseline + peak_detection. Phase 2 still needs a separate **figure capture** path (PNG bytes + `artifacts.figure_keys`) before DTA records appear correctly in Report Center exports — the override channel does not address that. Presets (Phase 3) and literature compare panel (Phase 2) do not depend on this decision.

---

## 2026-04-16 — Dash figure capture: client-side PNG + modality-agnostic backend endpoint

**Decision:** Figure capture for Dash-saved results is performed in the **Dash client** via `plotly.io.to_image(..., engine="kaleido")` and POSTed to a new modality-agnostic backend endpoint `POST /workspace/{project_id}/results/{result_id}/figure`. The endpoint accepts `{figure_png_base64, figure_label, replace}`, writes bytes into `state["figures"][label]`, and de-dupes the label into `state["results"][result_id]["artifacts"]["figure_keys"]`. On the DTA page a dedicated `capture_dta_figure` callback fires on `dta-latest-result-id` change, deduped per result_id via a new `dcc.Store` (`dta-figure-captured`). Failures (e.g. kaleido missing) degrade silently — the Report Center simply has no figure for that result, same as today.

**Alternatives considered:**
- *Server-side figure generation after run:* rejected because the backend currently has no modality-aware figure service; building one would duplicate `dash_app/pages/<modality>.py` rendering logic (trace selection, theming, annotations) and couple the backend to Dash/Plotly-specific styling.
- *Capture inside `display_result`:* rejected because `display_result` also re-fires on theme / locale changes, causing repeated kaleido renders and unnecessary POSTs per result.

**Reason:** Smallest change that closes the Report Center parity gap for Dash-saved results. The backend endpoint is intentionally **modality-agnostic** so DSC/TGA/XRD/FTIR Dash pages can reuse it in later phases without new backend work. Streamlit continues to write figures via `st.session_state["figures"]` in `ui/*_page.py` — unchanged. Export paths (`backend/exports.py::_selected_figures`, `core.result_serialization.collect_figure_keys`) continue to read from `state["figures"]` + `artifacts.figure_keys` — unchanged.

**Consequence / future:** Each Dash modality page needs its own thin `capture_<modality>_figure` callback that reuses the `go.Figure` builder for that page and calls `api_client.register_result_figure(...)`. The `dta-figure-captured` dedup store pattern should be reused (e.g. `dsc-figure-captured`). If kaleido ever moves out of `requirements.txt` the capture step silently no-ops — consider adding a health check in Phase 4 polish if this becomes visible to users.
