"""Tests for the DSC Dash analysis page module."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import dash
import dash_bootstrap_components as dbc

# Ensure project root is importable
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dash import dcc, html


@pytest.fixture(autouse=True)
def _ensure_dash_app():
    """Create a minimal Dash app so dash.register_page() works."""
    import dash

    try:
        dash.get_app()
    except Exception:
        app = dash.Dash(
            __name__,
            use_pages=True,
            pages_folder="",
            suppress_callback_exceptions=True,
        )
        app.layout = html.Div(dash.page_container)
    yield


def _import_dsc_page():
    import dash_app.pages.dsc as mod

    return mod


def test_dsc_page_module_imports():
    mod = _import_dsc_page()
    assert hasattr(mod, "layout")
    assert hasattr(mod, "_DSC_TEMPLATE_IDS")
    assert hasattr(mod, "_DSC_ELIGIBLE_TYPES")


def test_layout_contains_parity_ids_and_stores():
    mod = _import_dsc_page()
    layout_str = str(mod.layout)

    expected_ids = [
        "dsc-left-tabs",
        "dsc-tab-setup-shell",
        "dsc-tab-processing-shell",
        "dsc-tab-run-shell",
        "dsc-processing-default",
        "dsc-processing-draft",
        "dsc-processing-undo",
        "dsc-processing-redo",
        "dsc-preset-refresh",
        "dsc-preset-select",
        "dsc-preset-save-btn",
        "dsc-smooth-apply-btn",
        "dsc-baseline-apply-btn",
        "dsc-peak-apply-btn",
        "dsc-tg-apply-btn",
        "dsc-result-dataset-summary",
        "dsc-result-metrics",
        "dsc-result-quality",
        "dsc-result-raw-metadata",
        "dsc-result-figure",
        "dsc-result-derivative",
        "dsc-result-event-cards",
        "dsc-result-table",
        "dsc-result-processing",
        "dsc-prerun-dataset-info",
        "dsc-literature-compare-btn",
    ]
    for element_id in expected_ids:
        assert element_id in layout_str, f"Missing layout element: {element_id}"


def test_layout_places_figure_before_event_cards():
    mod = _import_dsc_page()
    layout_str = str(mod.layout)
    assert layout_str.index("dsc-result-figure") < layout_str.index("dsc-result-derivative")
    assert layout_str.index("dsc-result-derivative") < layout_str.index("dsc-result-event-cards")


def test_default_processing_draft_has_all_sections():
    mod = _import_dsc_page()
    defaults = mod._default_processing_draft()

    assert set(defaults.keys()) == {"smoothing", "baseline", "peak_detection", "glass_transition"}
    assert defaults["smoothing"]["method"] == "savgol"
    assert defaults["baseline"]["method"] == "asls"
    assert defaults["baseline"].get("region") is None
    assert defaults["peak_detection"]["direction"] == "both"
    assert defaults["peak_detection"]["prominence"] is None
    assert defaults["peak_detection"]["distance"] is None
    assert defaults["glass_transition"] == {"mode": "auto", "region": None}


def test_normalize_peak_detection_values_sanitizes_direction_and_distance():
    mod = _import_dsc_page()

    normalized = mod._normalize_peak_detection_values("nonsense", prominence=-3, distance=0)
    assert normalized == {"direction": "both", "prominence": None, "distance": None}

    up = mod._normalize_peak_detection_values("up", prominence=0.12, distance=8)
    assert up == {"direction": "up", "prominence": 0.12, "distance": 8}


def test_undo_redo_reset_cycle_for_processing_draft():
    mod = _import_dsc_page()

    defaults = mod._default_processing_draft()
    edited = mod._apply_draft_section(defaults, "smoothing", {"method": "gaussian", "sigma": 3.4})
    undo = mod._push_undo([], defaults)

    restored, undo_after, redo_after = mod._do_undo(edited, undo, [])
    assert restored == defaults
    assert undo_after == []
    assert redo_after == [edited]

    reapplied, undo_next, redo_next = mod._do_redo(restored, undo_after, redo_after)
    assert reapplied == edited
    assert undo_next == [defaults]
    assert redo_next == []

    reset, undo_reset, redo_reset = mod._do_reset(edited, [], [{"stale": True}], defaults)
    assert reset == defaults
    assert undo_reset == [edited]
    assert redo_reset == []


def test_overrides_from_draft_includes_all_user_sections():
    mod = _import_dsc_page()

    overrides = mod._overrides_from_draft(
        {
            "smoothing": {"method": "savgol", "window_length": 15, "polyorder": 3},
            "baseline": {"method": "asls", "lam": 1e6, "p": 0.01, "region": [40.0, 200.0]},
            "peak_detection": {"direction": "down", "prominence": 0.02, "distance": 4},
            "glass_transition": {"mode": "auto", "region": [90.0, 180.0]},
            "other": {"ignored": True},
        }
    )

    assert set(overrides.keys()) == {"smoothing", "baseline", "peak_detection", "glass_transition"}
    assert overrides["baseline"]["region"] == [40.0, 200.0]


def test_normalize_baseline_values_optional_region():
    mod = _import_dsc_page()

    base = mod._normalize_baseline_values("asls", 1e6, 0.01, False, 10, 200)
    assert base["region"] is None

    restricted = mod._normalize_baseline_values("asls", 1e6, 0.01, True, 30.0, 180.0)
    assert restricted["region"] == [30.0, 180.0]


def test_build_derivative_panel_renders_when_dtg_present(monkeypatch):
    mod = _import_dsc_page()
    import dash_app.api_client as api_client

    monkeypatch.setattr(
        api_client,
        "analysis_state_curves",
        lambda _p, _t, _k: {
            "temperature": [100.0, 110.0, 120.0],
            "dtg": [0.01, 0.02, -0.01],
            "has_dtg": True,
        },
    )

    panel = mod._build_derivative_panel("proj", "ds", "light", "en", locale_data="en")
    assert "dsc-derivative-helper" in str(getattr(panel, "className", "") or "")
    assert isinstance(panel.children[2], dcc.Graph)


def test_build_derivative_panel_hidden_without_dtg(monkeypatch):
    mod = _import_dsc_page()
    import dash_app.api_client as api_client

    monkeypatch.setattr(
        api_client,
        "analysis_state_curves",
        lambda _p, _t, _k: {"temperature": [1.0], "dtg": [], "has_dtg": False},
    )

    panel = mod._build_derivative_panel("proj", "ds", "light", "en", locale_data="en")
    assert isinstance(panel, html.Div)
    assert not panel.children


def test_toggle_preset_action_buttons_requires_selection():
    mod = _import_dsc_page()

    assert mod.toggle_dsc_preset_action_buttons(None) == (True, True)
    assert mod.toggle_dsc_preset_action_buttons("  ") == (True, True)
    assert mod.toggle_dsc_preset_action_buttons("polymer-default") == (False, False)


def test_build_event_cards_compacts_secondary_events():
    mod = _import_dsc_page()

    rows = [
        {
            "peak_type": "exotherm" if idx % 2 == 0 else "endotherm",
            "peak_temperature": 120.0 + idx * 14.0,
            "onset_temperature": 116.0 + idx * 14.0,
            "endset_temperature": 124.0 + idx * 14.0,
            "area": float(10 - idx),
            "height": float(4 - idx * 0.2),
        }
        for idx in range(6)
    ]

    cards = mod._build_event_cards({"glass_transition_count": 0}, rows, "en")
    cards_html = str(cards)
    assert cards_html.count("Peak ") == 4
    assert "Show 2 additional event(s)" in cards_html


def test_build_figure_returns_result_shell_without_debug(monkeypatch):
    mod = _import_dsc_page()
    import dash_app.api_client as api_client

    monkeypatch.setattr(
        api_client,
        "analysis_state_curves",
        lambda _project_id, _analysis_type, _dataset_key: {
            "temperature": [100.0, 130.0, 160.0, 190.0],
            "raw_signal": [0.0, 0.8, -0.25, 0.4],
            "smoothed": [0.1, 0.7, -0.2, 0.35],
            "baseline": [0.05, 0.05, 0.05, 0.05],
            "corrected": [0.05, 0.65, -0.25, 0.3],
        },
    )

    panel = mod._build_figure(
        "proj-1",
        "dataset-1",
        {
            "glass_transition_count": 1,
            "tg_midpoint": 150.0,
            "tg_onset": 140.0,
            "tg_endset": 160.0,
        },
        [{"peak_type": "exotherm", "peak_temperature": 130.0, "onset_temperature": 124.0, "endset_temperature": 138.0}],
        "light",
        "en",
        locale_data="en",
    )

    assert isinstance(panel, html.Div)
    assert "dsc-result-figure-shell" in str(getattr(panel, "className", "") or "")
    graph = panel.children
    assert isinstance(graph, dcc.Graph)
    assert "dsc-result-graph" in str(getattr(graph, "className", "") or "")
    assert graph.figure.layout.height == 600


def test_dsc_graph_config_exposes_png_export_options():
    mod = _import_dsc_page()
    cfg = mod._dsc_graph_config()

    assert cfg["displaylogo"] is False
    assert cfg["responsive"] is True
    assert cfg["toImageButtonOptions"]["format"] == "png"
    assert cfg["toImageButtonOptions"]["scale"] == 2


def test_run_dsc_analysis_forwards_draft_overrides_and_refreshes(monkeypatch):
    mod = _import_dsc_page()
    import dash_app.api_client as api_client

    captured: dict = {}

    def _fake_run(**kwargs):
        captured.update(kwargs)
        return {"execution_status": "saved", "result_id": "dsc_r_1"}

    monkeypatch.setattr(api_client, "analysis_run", _fake_run)
    monkeypatch.setattr(mod, "interpret_run_result", lambda *_a, **_k: (html.Div("ok"), True, "dsc_r_1"))

    draft = {
        "smoothing": {"method": "savgol", "window_length": 21, "polyorder": 3},
        "baseline": {"method": "asls", "lam": 1e5, "p": 0.02},
        "peak_detection": {"direction": "both", "prominence": 0.01, "distance": 2},
        "glass_transition": {"mode": "auto", "region": [90.0, 190.0]},
    }

    alert, refresh, latest_result_id, workspace_refresh = mod.run_dsc_analysis(
        1,
        "proj-1",
        "dataset-1",
        "dsc.general",
        4,
        7,
        "en",
        draft,
    )

    assert isinstance(alert, html.Div)
    assert refresh == 5
    assert latest_result_id == "dsc_r_1"
    assert workspace_refresh == 8

    assert captured["project_id"] == "proj-1"
    assert captured["dataset_key"] == "dataset-1"
    assert captured["analysis_type"] == "DSC"
    assert captured["workflow_template_id"] == "dsc.general"
    assert captured["processing_overrides"] == mod._overrides_from_draft(draft)


def test_run_dsc_analysis_returns_danger_alert_on_backend_error(monkeypatch):
    mod = _import_dsc_page()
    import dash_app.api_client as api_client

    monkeypatch.setattr(api_client, "analysis_run", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("backend down")))

    status, refresh, latest_result_id, workspace_refresh = mod.run_dsc_analysis(
        1,
        "proj-1",
        "dataset-1",
        "dsc.general",
        0,
        0,
        "en",
        mod._default_processing_draft(),
    )

    assert isinstance(status, dbc.Alert)
    assert status.color == "danger"
    assert "backend down" in str(status)
    assert refresh is dash.no_update
    assert latest_result_id is dash.no_update
    assert workspace_refresh is dash.no_update


def test_capture_dsc_figure_delegates_to_shared_helper(monkeypatch):
    mod = _import_dsc_page()
    captured_kwargs: dict = {}

    def _fake_capture(**kwargs):
        captured_kwargs.update(kwargs)
        return {"dsc_r_2": {"status": "ok"}}

    monkeypatch.setattr(mod, "capture_result_figure_from_layout", _fake_capture)

    result = mod.capture_dsc_figure("dsc_r_2", "proj-1", {"graph": True}, {"old": "state"})

    assert result == {"dsc_r_2": {"status": "ok"}}
    assert captured_kwargs == {
        "result_id": "dsc_r_2",
        "project_id": "proj-1",
        "figure_children": {"graph": True},
        "captured": {"old": "state"},
        "analysis_type": "DSC",
    }


def test_display_result_returns_new_surface_sections(monkeypatch):
    mod = _import_dsc_page()
    import dash_app.api_client as api_client

    monkeypatch.setattr(
        api_client,
        "workspace_result_detail",
        lambda _project_id, _result_id: {
            "summary": {
                "peak_count": 2,
                "glass_transition_count": 1,
                "tg_midpoint": 152.0,
                "tg_onset": 145.0,
                "tg_endset": 160.0,
                "delta_cp": 0.12,
                "sample_name": "Polymer A",
                "sample_mass": 12.5,
                "heating_rate": 10,
            },
            "result": {"dataset_key": "polymer_a.csv", "validation_status": "ok"},
            "processing": {
                "workflow_template_label": "General DSC",
                "workflow_template_version": 1,
                "signal_pipeline": {
                    "smoothing": {"method": "savgol", "window_length": 11, "polyorder": 3},
                    "baseline": {"method": "asls", "lam": 1e6, "p": 0.01},
                },
                "analysis_steps": {
                    "peak_detection": {"direction": "both", "prominence": 0.0, "distance": 1},
                    "glass_transition": {"mode": "auto", "region": None},
                },
                "method_context": {"sign_convention_label": "Endo down"},
            },
            "rows": [
                {
                    "peak_type": "endotherm",
                    "peak_temperature": 130.0,
                    "onset_temperature": 124.0,
                    "endset_temperature": 138.0,
                    "area": 1.2,
                    "fwhm": 9.0,
                    "height": 0.4,
                }
            ],
            "validation": {"status": "ok", "warning_count": 0, "issue_count": 0, "warnings": [], "issues": []},
        },
    )
    monkeypatch.setattr(
        api_client,
        "workspace_dataset_detail",
        lambda _project_id, _dataset_key: {
            "dataset": {"display_name": "Polymer A Dataset"},
            "metadata": {"file_name": "polymer_a.csv", "sample_mass": 12.5, "heating_rate": 10},
        },
    )
    monkeypatch.setattr(
        api_client,
        "analysis_state_curves",
        lambda _project_id, _analysis_type, _dataset_key: {
            "temperature": [100.0, 130.0, 160.0, 190.0],
            "raw_signal": [0.0, 0.8, -0.25, 0.4],
            "smoothed": [0.1, 0.7, -0.2, 0.35],
            "baseline": [0.05, 0.05, 0.05, 0.05],
            "corrected": [0.05, 0.65, -0.25, 0.3],
            "dtg": [0.0, 0.01, -0.02, 0.0],
            "has_dtg": True,
        },
    )

    outputs = mod.display_result("dsc_polymer_a", 1, "light", "en", "proj-1")

    assert len(outputs) == 9
    for item in outputs:
        assert item is not None


def test_layout_places_figure_before_raw_metadata():
    mod = _import_dsc_page()
    layout_str = str(mod.layout)
    assert layout_str.index("dsc-result-figure") < layout_str.index("dsc-result-raw-metadata")


def test_build_dsc_raw_metadata_panel_splits_user_and_technical_keys():
    mod = _import_dsc_page()
    metadata = {
        "sample_name": "Polymer A",
        "sample_mass": 12.5,
        "heating_rate": 10,
        "import_method": "auto",
        "import_confidence": "medium",
        "source_data_hash": "abc123",
        "inferred_analysis_type": "DSC",
    }
    panel = mod._build_dsc_raw_metadata_panel(metadata, "en")
    panel_html = str(panel)

    assert "sample_name" in panel_html
    assert "sample_mass" in panel_html
    assert "import_method" in panel_html
    assert "inferred_analysis_type" in panel_html
    assert panel_html.count("Details(") >= 2


def test_build_dsc_raw_metadata_panel_empty_metadata():
    mod = _import_dsc_page()
    panel = mod._build_dsc_raw_metadata_panel(None, "en")
    panel_html = str(panel)
    assert "dsc-raw-metadata" not in panel_html.lower() or "empty" in panel_html.lower() or "text-muted" in panel_html


def test_normalize_peak_detection_values_maps_explicit_zero_to_none():
    mod = _import_dsc_page()
    normalized = mod._normalize_peak_detection_values("both", prominence=0.0, distance=1)
    assert normalized["prominence"] is None
    assert normalized["distance"] is None

    explicit = mod._normalize_peak_detection_values("both", prominence=0.12, distance=8)
    assert explicit["prominence"] == 0.12
    assert explicit["distance"] == 8


def test_literature_diagnostics_show_search_mode_and_trust():
    from dash_app.components.literature_compare_ui import render_literature_output

    payload = {
        "literature_claims": [],
        "literature_comparisons": [],
        "citations": [],
        "literature_context": {
            "provider_query_status": "no_results",
            "no_results_reason": "no_real_results",
            "source_count": 0,
            "citation_count": 0,
            "query_text": "DSC thermal event calorimetry",
            "search_mode": "behavior_first",
            "subject_trust": "low_trust",
        },
    }
    output = render_literature_output(payload, "en", i18n_prefix="dash.analysis.dsc.literature")
    output_html = str(output)

    assert "behavior_first" in output_html
    assert "low_trust" in output_html


def test_literature_diagnostics_show_fallback_queries():
    from dash_app.components.literature_compare_ui import render_literature_output

    payload = {
        "literature_claims": [],
        "literature_comparisons": [],
        "citations": [],
        "literature_context": {
            "provider_query_status": "no_results",
            "no_results_reason": "query_too_narrow",
            "source_count": 0,
            "citation_count": 0,
            "query_text": "DSC glass transition calorimetry",
            "search_mode": "behavior_first",
            "subject_trust": "low_trust",
            "executed_queries": [
                "DSC glass transition calorimetry",
                "thermal analysis glass transition polymer",
                "differential scanning calorimetry glass transition",
            ],
        },
    }
    output = render_literature_output(payload, "en", i18n_prefix="dash.analysis.dsc.literature")
    output_html = str(output)

    assert "thermal analysis glass transition polymer" in output_html
    assert "differential scanning calorimetry glass transition" in output_html


def test_raw_metadata_technical_details_label_does_not_leak_i18n_key():
    mod = _import_dsc_page()
    metadata = {
        "sample_name": "Polymer A",
        "import_method": "auto",
    }
    panel = mod._build_dsc_raw_metadata_panel(metadata, "en")
    panel_html = str(panel)
    assert "Technical details" in panel_html
    assert "dash.analysis.dsc.raw_metadata.technical_details" not in panel_html


def test_raw_metadata_technical_details_label_turkish():
    mod = _import_dsc_page()
    metadata = {
        "sample_name": "Polimer A",
        "import_method": "auto",
    }
    panel = mod._build_dsc_raw_metadata_panel(metadata, "tr")
    panel_html = str(panel)
    assert "Teknik detaylar" in panel_html
    assert "dash.analysis.dsc.raw_metadata.technical_details" not in panel_html
