# Task — MaterialScope

**Purpose:** One active migration slice — scope, goal, and acceptance only.

## Status (2026-04-18): Shared Figure Persistence + Branding Upload Feedback — implemented

**Goal:** Fix real end-to-end figure persistence for all analysis modalities so saved results, PDF/DOCX export, and project save/load consistently carry figures; add immediate pre-save branding logo selection feedback in Dash export UI.

**In scope**

- `backend/app.py`: auto-register result snapshot figure during saved `/analysis/run` and `/workspace/{project_id}/batch/run` flows; ensure artifacts include `figure_keys` and `report_figure_key`.
- `core/figure_render.py`: centralize Plotly PNG rendering with resilient fallback path.
- `dash_app/components/analysis_page.py`, `dash_app/pages/dta.py`: route existing Dash capture to shared renderer helper.
- `dash_app/pages/export.py`: add immediate pre-save branding upload feedback (`branding-logo-selection`) from upload contents.
- Tests: `tests/test_backend_workflow.py`, `tests/test_analysis_page_components.py`, `tests/test_dta_dash_page.py`, `tests/test_export_dash_page.py`.

**Out of scope**

- Analysis algorithms and modality-specific scientific logic.
- Result schema redesign or export/report contract redesign.
- Streamlit legacy surface refactors.
- Localization dictionary expansion for this slice.

**Acceptance**

- Real running Dash app validation confirms:
  - saved DTA and FTIR results register figures in shared state,
  - exported DOCX/PDF include figure images,
  - project save/load preserves figures and result figure linkage,
  - branding logo selection shows immediate pre-save feedback.
- `pytest tests/test_analysis_page_components.py tests/test_export_dash_page.py` passes.
- `pytest tests/test_backend_workflow.py -k "auto_registers_figure"` passes.
- `pytest tests/test_dta_dash_page.py -k "capture_dta_figure"` passes.
