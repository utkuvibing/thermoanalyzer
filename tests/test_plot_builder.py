import plotly.graph_objects as go

from ui.components import plot_builder


def test_apply_professional_plot_theme_adds_shared_title_legend_and_export_layout():
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[1, 2], mode="lines", name="Run 1"))
    fig.add_trace(go.Scatter(x=[0, 1], y=[2, 3], mode="lines", name="Run 2"))

    plot_builder.apply_professional_plot_theme(
        fig,
        title="Demo Figure",
        subtitle="Publication subtitle",
        legend_mode="compact",
    )

    assert fig.layout.paper_bgcolor == plot_builder.DEFAULT_LAYOUT["paper_bgcolor"]
    assert fig.layout.plot_bgcolor == plot_builder.DEFAULT_LAYOUT["plot_bgcolor"]
    assert fig.layout.hovermode == "x unified"
    assert "Demo Figure" in str(fig.layout.title.text)
    assert "Publication subtitle" in str(fig.layout.title.text)
    assert fig.layout.legend.orientation == "v"
    assert float(fig.layout.legend.x) >= 1.0


def test_main_plot_builders_use_shared_professional_theme():
    thermal = plot_builder.create_thermal_plot([25, 50, 75], [1.0, 1.4, 1.1], title="Thermal")
    overlay = plot_builder.create_overlay_plot(
        [
            {"x": [0, 1, 2], "y": [1.0, 1.2, 1.1], "name": "Run 1"},
            {"x": [0, 1, 2], "y": [0.9, 1.0, 1.3], "name": "Run 2"},
            {"x": [0, 1, 2], "y": [1.1, 1.1, 1.0], "name": "Run 3"},
            {"x": [0, 1, 2], "y": [0.8, 0.95, 1.05], "name": "Run 4"},
            {"x": [0, 1, 2], "y": [1.2, 1.15, 1.1], "name": "Run 5"},
            {"x": [0, 1, 2], "y": [1.0, 1.05, 0.98], "name": "Run 6"},
        ],
        title="Overlay",
    )
    deconvolution = plot_builder.create_deconvolution_plot(
        [30, 40, 50],
        [0.2, 0.6, 0.3],
        [0.18, 0.58, 0.28],
        [[0.1, 0.3, 0.1], [0.08, 0.28, 0.18]],
        title="Deconvolution",
    )
    kissinger = plot_builder.create_kissinger_plot(
        [1.10, 1.15, 1.20],
        [0.22, 0.31, 0.39],
        ea_kj=145.0,
        ln_a=8.4,
        r_squared=0.992,
    )

    for fig in (thermal, overlay, deconvolution, kissinger):
        assert fig.layout.paper_bgcolor == plot_builder.DEFAULT_LAYOUT["paper_bgcolor"]
        assert fig.layout.plot_bgcolor == plot_builder.DEFAULT_LAYOUT["plot_bgcolor"]
        assert fig.layout.hovermode == "x unified"
        assert fig.layout.font.family == plot_builder.DEFAULT_LAYOUT["font"]["family"]
        assert fig.layout.xaxis.showspikes is True
        assert fig.layout.yaxis.showspikes is True

    assert overlay.layout.legend.orientation == "v"
    assert float(overlay.layout.legend.x) >= 1.0


def test_fig_to_bytes_uses_report_safe_export_dimensions(monkeypatch):
    fig = plot_builder.create_overlay_plot(
        [
            {"x": [0, 1, 2], "y": [1.0, 1.2, 1.1], "name": "Run 1"},
            {"x": [0, 1, 2], "y": [0.9, 1.0, 1.3], "name": "Run 2"},
        ],
        title="Export Figure",
    )
    captured = {}

    def _fake_to_image(self, *, format, width, height, engine):
        captured["format"] = format
        captured["width"] = width
        captured["height"] = height
        captured["engine"] = engine
        captured["title"] = str(self.layout.title.text)
        return b"figure-bytes"

    monkeypatch.setattr(plot_builder.go.Figure, "to_image", _fake_to_image, raising=False)

    payload = plot_builder.fig_to_bytes(fig, format="png", width=900, height=500)

    assert payload == b"figure-bytes"
    assert captured["format"] == "png"
    assert captured["engine"] == "kaleido"
    assert captured["width"] >= plot_builder.PLOTLY_CONFIG["toImageButtonOptions"]["width"]
    assert captured["height"] >= plot_builder.PLOTLY_CONFIG["toImageButtonOptions"]["height"]
    assert "Export Figure" in captured["title"]


def test_apply_plot_display_settings_respects_user_layout_preferences():
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[4000, 3000, 2000], y=[0.1, 0.4, 0.2], mode="lines+markers", name="Spectrum"))

    plot_builder.apply_plot_display_settings(
        fig,
        {
            "legend_mode": "hidden",
            "compact": True,
            "show_grid": False,
            "show_spikes": False,
            "line_width_scale": 1.4,
            "marker_size_scale": 1.5,
            "reverse_x_axis": True,
        },
        title="Configured Spectrum",
    )

    assert fig.layout.showlegend is False
    assert fig.layout.height == 520
    assert fig.layout.xaxis.showgrid is False
    assert fig.layout.yaxis.showgrid is False
    assert fig.layout.xaxis.showspikes is False
    assert fig.layout.yaxis.showspikes is False
    assert fig.layout.xaxis.autorange == "reversed"
    assert float(fig.data[0].line.width) > 2.0
    assert float(fig.data[0].marker.size) >= 10.0


def test_apply_plot_display_settings_supports_locked_axis_ranges():
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[50, 500, 1500, 3000], y=[5.0, 15.0, 9.0, 3.0], mode="lines", name="Spectrum"))

    plot_builder.apply_plot_display_settings(
        fig,
        {
            "x_range_enabled": True,
            "x_min": 100.0,
            "x_max": 1800.0,
            "y_range_enabled": True,
            "y_min": 2.0,
            "y_max": 18.0,
        },
    )

    assert list(fig.layout.xaxis.range) == [100.0, 1800.0]
    assert list(fig.layout.yaxis.range) == [2.0, 18.0]


def test_build_plotly_config_applies_export_scale_and_filename():
    config = plot_builder.build_plotly_config(
        {"export_scale": 4},
        filename="materialscope_ftir_demo",
    )

    assert config["toImageButtonOptions"]["scale"] == 4
    assert config["toImageButtonOptions"]["filename"] == "materialscope_ftir_demo"


def test_create_thermal_plot_applies_display_settings_and_persists_them_for_export():
    fig = plot_builder.create_thermal_plot(
        [4000, 3000, 2000],
        [0.1, 0.4, 0.2],
        title="Configured Thermal",
        display_settings={
            "legend_mode": "hidden",
            "show_grid": False,
            "reverse_x_axis": True,
            "line_width_scale": 1.3,
        },
    )

    assert fig.layout.showlegend is False
    assert fig.layout.xaxis.showgrid is False
    assert fig.layout.xaxis.autorange == "reversed"
    assert float(fig.data[0].line.width) > 3.0
    assert fig.layout.meta["plot_display_settings"]["reverse_x_axis"] is True
