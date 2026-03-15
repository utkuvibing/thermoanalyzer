from pathlib import Path

import pandas as pd

from core.data_io import ThermalDataset
from ui import xrd_page


def _xrd_dataset():
    return ThermalDataset(
        data=pd.DataFrame(
            {
                "temperature": [18.2, 27.5, 36.1, 44.8],
                "signal": [130.0, 290.0, 175.0, 120.0],
            }
        ),
        metadata={
            "sample_name": "SyntheticXRD",
            "display_name": "Synthetic XRD Pattern",
            "xrd_axis_role": "two_theta",
            "xrd_axis_unit": "degree_2theta",
            "xrd_wavelength_angstrom": 1.5406,
        },
        data_type="XRD",
        units={"temperature": "degree_2theta", "signal": "counts"},
        original_columns={"temperature": "two_theta", "signal": "intensity"},
        file_path="",
    )


def test_attach_xrd_report_figure_stores_png_and_links_record(monkeypatch):
    dataset = _xrd_dataset()
    record = {"id": "xrd_synthetic_xrd", "artifacts": {}}
    figures_store = {}

    monkeypatch.setattr(xrd_page, "_build_processed_plot", lambda *args, **kwargs: object())
    monkeypatch.setattr(xrd_page, "fig_to_bytes", lambda fig: b"xrd-figure")

    updated_record, figure_key = xrd_page._attach_xrd_report_figure(
        record,
        dataset_key="synthetic_xrd",
        dataset=dataset,
        state={"peaks": [{"position": 27.5, "intensity": 290.0}]},
        lang="tr",
        figures_store=figures_store,
    )

    assert figure_key == "XRD Analysis - synthetic_xrd"
    assert figures_store[figure_key] == b"xrd-figure"
    assert updated_record["artifacts"]["figure_keys"] == [figure_key]
    assert updated_record["artifacts"]["report_figure_key"] == figure_key
    assert updated_record["artifacts"]["figure_snapshots"][0]["figure_key"] == figure_key


def test_attach_xrd_report_figure_deduplicates_existing_figure_key(monkeypatch):
    dataset = _xrd_dataset()
    figure_key = "XRD Analysis - synthetic_xrd"
    record = {"id": "xrd_synthetic_xrd", "artifacts": {"figure_keys": ["Aux Figure", figure_key]}}
    figures_store = {}

    monkeypatch.setattr(xrd_page, "_build_processed_plot", lambda *args, **kwargs: object())
    monkeypatch.setattr(xrd_page, "fig_to_bytes", lambda fig: b"xrd-figure")

    updated_record, _ = xrd_page._attach_xrd_report_figure(
        record,
        dataset_key="synthetic_xrd",
        dataset=dataset,
        state={"peaks": [{"position": 27.5, "intensity": 290.0}]},
        lang="tr",
        figures_store=figures_store,
    )

    assert updated_record["artifacts"]["figure_keys"] == ["Aux Figure", figure_key]
    assert updated_record["artifacts"]["report_figure_key"] == figure_key


def test_xrd_page_uses_pending_workflow_seed_for_preset_application():
    source = Path(xrd_page.__file__).read_text(encoding="utf-8")

    assert 'seed_pending_workflow_template(f"xrd_template_{selected_key}")' in source


def test_xrd_control_key_tracks_render_revision():
    assert xrd_page._xrd_control_key("sample", "smooth_method", {}) == "xrd_smooth_method_sample_0"
    assert xrd_page._xrd_control_key("sample", "smooth_method", {"_render_revision": 4}) == "xrd_smooth_method_sample_4"


def test_sync_xrd_processing_from_controls_prefers_widget_state(monkeypatch):
    dataset = _xrd_dataset()
    processing = xrd_page._seed_xrd_processing_defaults({}, "xrd.general", dataset)
    state = {"_render_revision": 2}
    widget_state = {
        "xrd_restrict_synthetic_xrd_2": True,
        "xrd_axis_min_synthetic_xrd_2": 11.5,
        "xrd_axis_max_synthetic_xrd_2": 76.0,
        "xrd_smooth_method_synthetic_xrd_2": "moving_average",
        "xrd_smooth_window_synthetic_xrd_2": 21,
        "xrd_smooth_poly_synthetic_xrd_2": 5,
        "xrd_baseline_method_synthetic_xrd_2": "linear",
        "xrd_baseline_window_synthetic_xrd_2": 55,
        "xrd_baseline_smooth_synthetic_xrd_2": 13,
        "xrd_peak_prom_synthetic_xrd_2": 0.22,
        "xrd_peak_dist_synthetic_xrd_2": 9,
        "xrd_peak_width_synthetic_xrd_2": 4,
        "xrd_peak_max_synthetic_xrd_2": 18,
        "xrd_match_tol_synthetic_xrd_2": 0.19,
        "xrd_match_min_synthetic_xrd_2": 0.61,
        "xrd_match_topn_synthetic_xrd_2": 8,
        "xrd_match_iw_synthetic_xrd_2": 0.47,
        "xrd_match_major_synthetic_xrd_2": 0.58,
        "xrd_plot_peak_labels_synthetic_xrd_2": True,
        "xrd_plot_label_density_synthetic_xrd_2": "all",
        "xrd_plot_max_labels_synthetic_xrd_2": 14,
        "xrd_plot_label_min_ratio_synthetic_xrd_2": 0.2,
        "xrd_plot_marker_size_synthetic_xrd_2": 12,
        "xrd_plot_pos_precision_synthetic_xrd_2": 3,
        "xrd_plot_int_precision_synthetic_xrd_2": 1,
        "xrd_plot_show_matched_synthetic_xrd_2": True,
        "xrd_plot_show_match_labels_synthetic_xrd_2": True,
        "xrd_plot_show_unmatched_obs_synthetic_xrd_2": False,
        "xrd_plot_show_unmatched_ref_synthetic_xrd_2": True,
        "xrd_plot_show_connectors_synthetic_xrd_2": False,
        "xrd_plot_style_synthetic_xrd_2": "shape_only",
        "xrd_plot_x_range_synthetic_xrd_2": True,
        "xrd_plot_x_min_synthetic_xrd_2": 9.5,
        "xrd_plot_x_max_synthetic_xrd_2": 66.2,
        "xrd_plot_y_range_synthetic_xrd_2": True,
        "xrd_plot_y_min_synthetic_xrd_2": 5.0,
        "xrd_plot_y_max_synthetic_xrd_2": 9000.0,
        "xrd_plot_log_y_synthetic_xrd_2": True,
        "xrd_plot_line_width_synthetic_xrd_2": 2.8,
    }
    monkeypatch.setattr(xrd_page.st, "session_state", widget_state)

    synced = xrd_page._sync_xrd_processing_from_controls(
        processing,
        dataset_key="synthetic_xrd",
        dataset=dataset,
        state=state,
    )

    axis_norm = synced["signal_pipeline"]["axis_normalization"]
    smoothing = synced["signal_pipeline"]["smoothing"]
    baseline = synced["signal_pipeline"]["baseline"]
    peaks = synced["analysis_steps"]["peak_detection"]
    context = synced["method_context"]

    assert axis_norm["axis_min"] == 11.5
    assert axis_norm["axis_max"] == 76.0
    assert smoothing["method"] == "moving_average"
    assert smoothing["window_length"] == 21
    assert baseline["method"] == "linear"
    assert peaks["prominence"] == 0.22
    assert context["xrd_match_tolerance_deg"] == 0.19
    assert context["xrd_match_top_n"] == 8
    assert context["xrd_plot_settings"]["label_density_mode"] == "all"
    assert context["xrd_plot_settings"]["marker_size"] == 12
    assert context["xrd_plot_settings"]["show_unmatched_observed"] is False
    assert context["xrd_plot_settings"]["style_preset"] == "shape_only"
    assert context["xrd_plot_settings"]["x_range_enabled"] is True
    assert context["xrd_plot_settings"]["x_min"] == 9.5
    assert context["xrd_plot_settings"]["y_range_enabled"] is True
    assert context["xrd_plot_settings"]["log_y"] is True
    assert context["xrd_plot_settings"]["line_width"] == 2.8


def test_pick_peak_label_indices_uses_smart_filter():
    peaks = [
        {"position": 10.0, "intensity": 10.0},
        {"position": 20.0, "intensity": 120.0},
        {"position": 30.0, "intensity": 90.0},
        {"position": 40.0, "intensity": 5.0},
    ]
    settings = {
        "show_peak_labels": True,
        "label_density_mode": "smart",
        "max_labels": 2,
        "min_label_intensity_ratio": 0.2,
    }

    selected = xrd_page._pick_peak_label_indices(peaks, settings)

    assert selected == {1, 2}


def test_build_processed_plot_adds_match_overlay_traces():
    dataset = _xrd_dataset()
    state = {
        "peaks": [
            {"position": 18.2, "intensity": 130.0},
            {"position": 27.5, "intensity": 290.0},
            {"position": 36.1, "intensity": 175.0},
        ]
    }
    selected_match = {
        "rank": 1,
        "candidate_name": "Phase Alpha",
        "evidence": {
            "matched_peak_pairs": [
                {
                    "observed_position": 27.5,
                    "observed_intensity": 290.0,
                    "reference_position": 27.62,
                    "reference_intensity": 1.0,
                }
            ],
            "unmatched_observed_peaks": [{"position": 18.2, "intensity": 130.0}],
            "unmatched_reference_peaks": [{"position": 36.4, "intensity": 0.8, "is_major": True}],
        },
    }
    settings = xrd_page._normalize_xrd_plot_settings(
        {
            "show_peak_labels": True,
            "show_match_connectors": True,
            "show_matched_peaks": True,
            "show_unmatched_observed": True,
            "show_unmatched_reference": True,
        }
    )

    fig = xrd_page._build_processed_plot(
        "synthetic_xrd",
        dataset,
        state,
        "tr",
        plot_settings=settings,
        selected_match=selected_match,
    )
    trace_names = [trace.name for trace in fig.data]

    assert "Pikler" in trace_names
    assert "Eşleşen Pikler" in trace_names
    assert "Eşleşen Referans Pik" in trace_names
    assert "Eşleşmeyen Gözlenen Pik" in trace_names
    assert "Eşleşmeyen Referans Pik" in trace_names


def test_save_xrd_graph_snapshot_to_session_sets_primary_and_prunes(monkeypatch):
    dataset = _xrd_dataset()
    record = {
        "id": "xrd_synthetic_xrd",
        "artifacts": {
            "figure_snapshots": [
                {"figure_key": f"XRD Snapshot - synthetic_xrd - old_{idx}"}
                for idx in range(10)
            ],
            "figure_keys": [f"XRD Snapshot - synthetic_xrd - old_{idx}" for idx in range(10)],
            "report_figure_key": "XRD Snapshot - synthetic_xrd - old_9",
        },
    }
    state = {"processing": {"method_context": {"xrd_plot_settings": {}}}, "peaks": [{"position": 27.5, "intensity": 290.0}]}
    selected_match = {"rank": 1, "candidate_id": "phase_alpha", "candidate_name": "Phase Alpha", "evidence": {}}

    monkeypatch.setattr(xrd_page, "_build_processed_plot", lambda *args, **kwargs: object())

    def _fake_fig_to_bytes(fig, format="png", width=1000, height=600):
        return f"{format}-bytes".encode("utf-8")

    monkeypatch.setattr(xrd_page, "fig_to_bytes", _fake_fig_to_bytes)
    monkeypatch.setattr(
        xrd_page,
        "_xrd_snapshot_figure_key",
        lambda dataset_key, selected_match: "XRD Snapshot - synthetic_xrd - new_primary",
    )
    monkeypatch.setattr(
        xrd_page.st,
        "session_state",
        {
            "figures": {f"XRD Snapshot - synthetic_xrd - old_{idx}": b"old" for idx in range(10)},
            "figure_outputs": {f"XRD Snapshot - synthetic_xrd - old_{idx}": {"png": b"old"} for idx in range(10)},
            "results": {},
        },
    )

    updated_record, snapshot_key = xrd_page._save_xrd_graph_snapshot_to_session(
        record=record,
        dataset_key="synthetic_xrd",
        dataset=dataset,
        state=state,
        lang="tr",
        selected_match=selected_match,
        plot_settings={"show_matched_peaks": True},
        set_primary=True,
    )

    assert snapshot_key == "XRD Snapshot - synthetic_xrd - new_primary"
    assert updated_record["artifacts"]["report_figure_key"] == snapshot_key
    assert len(updated_record["artifacts"]["figure_snapshots"]) == 10
    assert "XRD Snapshot - synthetic_xrd - old_0" not in xrd_page.st.session_state["figures"]
    assert xrd_page.st.session_state["figures"][snapshot_key] == b"png-bytes"
