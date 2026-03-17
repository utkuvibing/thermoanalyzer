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
