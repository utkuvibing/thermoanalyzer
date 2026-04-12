"""Plotly chart builders for thermal analysis data."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.session_state import get_ui_theme

THERMAL_COLORS = [
    "#0F766E",
    "#2563EB",
    "#DC2626",
    "#7C3AED",
    "#D97706",
    "#0891B2",
    "#65A30D",
    "#475569",
]

BASELINE_COLOR = "#64748B"
_PLOT_FONT_FAMILY = "Aptos, Segoe UI, Arial, sans-serif"
_PLOT_THEME = {
    "light": {
        "template": "plotly_white",
        "text": "#102033",
        "subtle_text": "#516072",
        "paper_bg": "#F7FAFC",
        "plot_bg": "#FFFFFF",
        "grid": "#D8E1EA",
        "axis": "#A8B6C7",
        "hover_border": "#C7D2DF",
        "legend_bg": "rgba(255,255,255,0.84)",
        "annotation_bg": "rgba(255,255,255,0.90)",
        "annotation_border": "rgba(120,138,160,0.24)",
    },
    "dark": {
        "template": "plotly_dark",
        "text": "#E5EEF8",
        "subtle_text": "#B8C6D8",
        "paper_bg": "#0F172A",
        "plot_bg": "#111C30",
        "grid": "#314055",
        "axis": "#6F829B",
        "hover_border": "#44566F",
        "legend_bg": "rgba(15,23,42,0.82)",
        "annotation_bg": "rgba(15,23,42,0.88)",
        "annotation_border": "rgba(122,150,182,0.28)",
    },
}
_DEFAULT_EXPORT_WIDTH = 1400
_DEFAULT_EXPORT_HEIGHT = 840
_DEFAULT_DISPLAY_SETTINGS = {
    "legend_mode": "auto",
    "compact": False,
    "show_grid": True,
    "show_spikes": True,
    "line_width_scale": 1.0,
    "marker_size_scale": 1.0,
    "export_scale": 2,
    "reverse_x_axis": False,
    "x_range_enabled": False,
    "x_min": None,
    "x_max": None,
    "y_range_enabled": False,
    "y_min": None,
    "y_max": None,
}

PLOTLY_CONFIG = dict(
    displayModeBar=True,
    scrollZoom=True,
    modeBarButtonsToAdd=["drawline", "drawopenpath", "eraseshape"],
    modeBarButtonsToRemove=["lasso2d"],
    displaylogo=False,
    responsive=True,
    toImageButtonOptions=dict(
        format="png",
        filename="thermoanalyzer_plot",
        width=_DEFAULT_EXPORT_WIDTH,
        height=_DEFAULT_EXPORT_HEIGHT,
        scale=2,
    ),
)

def _plot_tokens() -> dict[str, str]:
    return _PLOT_THEME[get_ui_theme()]


def _default_layout() -> dict:
    tokens = _plot_tokens()
    return dict(
        template=tokens["template"],
        colorway=THERMAL_COLORS,
        font=dict(family=_PLOT_FONT_FAMILY, size=12, color=tokens["text"]),
        hoverlabel=dict(
            bgcolor=tokens["plot_bg"],
            bordercolor=tokens["hover_border"],
            font_size=12,
            font_family=_PLOT_FONT_FAMILY,
            font_color=tokens["text"],
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.0,
            bgcolor=tokens["legend_bg"],
            bordercolor="rgba(0,0,0,0)",
            borderwidth=0,
            font=dict(size=10.5, color=tokens["subtle_text"]),
            title=dict(text=""),
            itemsizing="constant",
        ),
        title=dict(
            x=0.0,
            xanchor="left",
            y=0.98,
            yanchor="top",
            pad=dict(b=10),
            font=dict(size=18, color=tokens["text"]),
        ),
        margin=dict(l=76, r=44, t=88, b=68),
        paper_bgcolor=tokens["paper_bg"],
        plot_bgcolor=tokens["plot_bg"],
        autosize=True,
        xaxis=dict(
            gridcolor=tokens["grid"],
            gridwidth=1,
            ticks="outside",
            tickcolor=tokens["axis"],
            ticklen=5,
            showline=True,
            linecolor=tokens["axis"],
            linewidth=1.1,
            zeroline=False,
            mirror=False,
            automargin=True,
            title_standoff=12,
        ),
        yaxis=dict(
            gridcolor=tokens["grid"],
            gridwidth=1,
            ticks="outside",
            tickcolor=tokens["axis"],
            ticklen=5,
            showline=True,
            linecolor=tokens["axis"],
            linewidth=1.1,
            zeroline=False,
            mirror=False,
            automargin=True,
            title_standoff=12,
        ),
    )


def default_plot_display_settings(settings: dict | None = None, **overrides) -> dict:
    payload = dict(_DEFAULT_DISPLAY_SETTINGS)
    if isinstance(settings, dict):
        payload.update(settings)
    if overrides:
        payload.update(overrides)

    payload["legend_mode"] = str(payload.get("legend_mode") or "auto").lower()
    if payload["legend_mode"] not in {"auto", "external", "compact", "hidden"}:
        payload["legend_mode"] = "auto"
    payload["compact"] = bool(payload.get("compact"))
    payload["show_grid"] = bool(payload.get("show_grid", True))
    payload["show_spikes"] = bool(payload.get("show_spikes", True))
    payload["reverse_x_axis"] = bool(payload.get("reverse_x_axis"))
    payload["x_range_enabled"] = bool(payload.get("x_range_enabled"))
    payload["y_range_enabled"] = bool(payload.get("y_range_enabled"))

    try:
        payload["line_width_scale"] = float(payload.get("line_width_scale", 1.0))
    except (TypeError, ValueError):
        payload["line_width_scale"] = 1.0
    payload["line_width_scale"] = min(max(payload["line_width_scale"], 0.6), 1.8)

    try:
        payload["marker_size_scale"] = float(payload.get("marker_size_scale", 1.0))
    except (TypeError, ValueError):
        payload["marker_size_scale"] = 1.0
    payload["marker_size_scale"] = min(max(payload["marker_size_scale"], 0.6), 1.8)

    try:
        payload["export_scale"] = int(payload.get("export_scale", 2))
    except (TypeError, ValueError):
        payload["export_scale"] = 2
    payload["export_scale"] = min(max(payload["export_scale"], 1), 4)

    for key in ("x_min", "x_max", "y_min", "y_max"):
        value = payload.get(key)
        if value in (None, ""):
            payload[key] = None
            continue
        try:
            payload[key] = float(value)
        except (TypeError, ValueError):
            payload[key] = None

    if payload["x_range_enabled"] and payload["x_min"] is not None and payload["x_max"] is not None and payload["x_min"] > payload["x_max"]:
        payload["x_min"], payload["x_max"] = payload["x_max"], payload["x_min"]
    if payload["y_range_enabled"] and payload["y_min"] is not None and payload["y_max"] is not None and payload["y_min"] > payload["y_max"]:
        payload["y_min"], payload["y_max"] = payload["y_max"], payload["y_min"]
    return payload


def build_plotly_config(settings: dict | None = None, *, filename: str | None = None) -> dict:
    resolved = default_plot_display_settings(settings)
    export_options = dict(PLOTLY_CONFIG["toImageButtonOptions"])
    export_options["scale"] = resolved["export_scale"]
    if filename:
        export_options["filename"] = filename
    config = dict(PLOTLY_CONFIG)
    config["toImageButtonOptions"] = export_options
    return config

def _legend_layout(trace_count: int, *, legend_mode: str, compact: bool) -> tuple[bool, dict]:
    tokens = _plot_tokens()
    if legend_mode == "hidden":
        return False, {}
    font_size = 10 if compact else 10.5
    if legend_mode == "external" or legend_mode == "compact" or (legend_mode == "auto" and trace_count >= 5):
        return True, dict(
            orientation="v",
            yanchor="top",
            y=1.0,
            xanchor="left",
            x=1.02,
            bgcolor=tokens["legend_bg"],
            bordercolor="rgba(0,0,0,0)",
            borderwidth=0,
            tracegroupgap=4,
            font=dict(size=font_size, color=tokens["subtle_text"]),
            title=dict(text=""),
            itemsizing="constant",
        )
    return True, dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="left",
        x=0.0,
        bgcolor=tokens["legend_bg"],
        bordercolor="rgba(0,0,0,0)",
        borderwidth=0,
        font=dict(size=font_size, color=tokens["subtle_text"]),
        title=dict(text=""),
        itemsizing="constant",
    )


def _theme_margins(
    *,
    compact: bool,
    subtitle: str | None,
    legend_mode: str,
    trace_count: int,
    showlegend: bool,
) -> dict:
    top = 74 if compact else 90
    right = 34 if compact else 44
    left = 64 if compact else 76
    bottom = 54 if compact else 68
    needs_external_legend = showlegend and (
        legend_mode in {"external", "compact"} or (legend_mode == "auto" and trace_count >= 5)
    )
    if subtitle:
        top += 18
    if needs_external_legend:
        right += 118
    elif showlegend:
        top += 20
    return dict(l=left, r=right, t=top, b=bottom)


def _compose_title(title: str | None, subtitle: str | None, *, compact: bool) -> str:
    base = str(title or "").strip()
    sub = str(subtitle or "").strip()
    if not sub:
        return base
    sub_size = 11 if compact else 12
    return f"{base}<br><span style='font-size:{sub_size}px;color:{_plot_tokens()['subtle_text']}'>{sub}</span>"


def _style_trace_defaults(fig, *, compact: bool) -> None:
    for index, trace in enumerate(fig.data):
        mode = str(getattr(trace, "mode", "") or "")
        if "lines" in mode and hasattr(trace, "line"):
            current_width = getattr(trace.line, "width", None)
            if current_width in (None, 0):
                trace.line.width = 2.2 if index == 0 else 1.8
        if "markers" in mode and hasattr(trace, "marker"):
            current_size = getattr(trace.marker, "size", None)
            if current_size in (None, 0):
                trace.marker.size = 7 if compact else 8


def _scale_trace_styles(fig, *, line_width_scale: float, marker_size_scale: float) -> None:
    for trace in fig.data:
        if hasattr(trace, "line"):
            current_width = getattr(trace.line, "width", None)
            if isinstance(current_width, (int, float)):
                trace.line.width = max(0.6, float(current_width) * line_width_scale)
        if hasattr(trace, "marker"):
            current_size = getattr(trace.marker, "size", None)
            if isinstance(current_size, (int, float)):
                trace.marker.size = max(4.0, float(current_size) * marker_size_scale)


def apply_professional_plot_theme(
    fig,
    *,
    compact: bool = False,
    for_export: bool = False,
    legend_mode: str = "auto",
    title: str | None = None,
    subtitle: str | None = None,
):
    """Apply a shared publication-style theme across Plotly figures."""
    tokens = _plot_tokens()
    trace_count = sum(1 for trace in fig.data if getattr(trace, "showlegend", True) is not False)
    showlegend, legend = _legend_layout(trace_count, legend_mode=legend_mode, compact=compact)
    final_title = title if title is not None else getattr(fig.layout.title, "text", "")
    layout = _default_layout()
    layout.update(
        title=dict(
            text=_compose_title(final_title, subtitle, compact=compact),
            x=0.0,
            xanchor="left",
            y=0.98,
            yanchor="top",
            pad=dict(b=10),
            font=dict(size=16 if compact else 18, color=tokens["text"], family=_PLOT_FONT_FAMILY),
        ),
        showlegend=showlegend,
        legend=legend,
        margin=_theme_margins(
            compact=compact,
            subtitle=subtitle,
            legend_mode=legend_mode,
            trace_count=trace_count,
            showlegend=showlegend,
        ),
        hovermode="x unified",
        hoverdistance=80,
        spikedistance=1000,
        height=520 if compact else 620,
    )
    fig.update_layout(**layout)
    if for_export:
        fig.update_layout(width=_DEFAULT_EXPORT_WIDTH, height=_DEFAULT_EXPORT_HEIGHT)
    fig.update_xaxes(
        showspikes=True,
        spikecolor=tokens["axis"],
        spikethickness=1,
        spikedash="dot",
        spikemode="across",
        gridcolor=tokens["grid"],
        linecolor=tokens["axis"],
        tickfont=dict(size=11, color=tokens["text"]),
        title_font=dict(size=12, color=tokens["text"], family=_PLOT_FONT_FAMILY),
    )
    fig.update_yaxes(
        showspikes=True,
        spikecolor=tokens["axis"],
        spikethickness=1,
        spikedash="dot",
        spikemode="across",
        gridcolor=tokens["grid"],
        linecolor=tokens["axis"],
        tickfont=dict(size=11, color=tokens["text"]),
        title_font=dict(size=12, color=tokens["text"], family=_PLOT_FONT_FAMILY),
    )
    fig.update_annotations(
        font=dict(size=10.5 if compact else 11, color=tokens["subtle_text"], family=_PLOT_FONT_FAMILY),
        bgcolor=tokens["annotation_bg"],
        bordercolor=tokens["annotation_border"],
        borderwidth=0,
        borderpad=2,
    )
    _style_trace_defaults(fig, compact=compact)
    return fig


def apply_plot_display_settings(
    fig,
    settings: dict | None = None,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    for_export: bool = False,
    scale_traces: bool = True,
):
    resolved = default_plot_display_settings(settings)
    apply_professional_plot_theme(
        fig,
        compact=resolved["compact"] if not for_export else False,
        for_export=for_export,
        legend_mode=resolved["legend_mode"],
        title=title,
        subtitle=subtitle,
    )
    fig.update_xaxes(showgrid=resolved["show_grid"])
    fig.update_yaxes(showgrid=resolved["show_grid"])
    fig.update_xaxes(showspikes=resolved["show_spikes"])
    fig.update_yaxes(showspikes=resolved["show_spikes"])
    if resolved["x_range_enabled"] and resolved["x_min"] is not None and resolved["x_max"] is not None:
        x_range = [resolved["x_min"], resolved["x_max"]]
        if resolved["reverse_x_axis"]:
            x_range = list(reversed(x_range))
        fig.update_xaxes(range=x_range)
    elif resolved["reverse_x_axis"]:
        fig.update_xaxes(autorange="reversed")
    if resolved["y_range_enabled"] and resolved["y_min"] is not None and resolved["y_max"] is not None:
        fig.update_yaxes(range=[resolved["y_min"], resolved["y_max"]])
    if scale_traces:
        _scale_trace_styles(
            fig,
            line_width_scale=resolved["line_width_scale"],
            marker_size_scale=resolved["marker_size_scale"],
        )
    meta = getattr(fig.layout, "meta", None)
    if isinstance(meta, dict):
        next_meta = dict(meta)
    else:
        next_meta = {}
    next_meta["plot_display_settings"] = resolved
    fig.update_layout(meta=next_meta)
    return fig


def apply_plotly_config(fig):
    """Apply shared crosshair and hover behavior without overriding layout composition."""
    tokens = _plot_tokens()
    fig.update_layout(hovermode="x unified", hoverdistance=80, spikedistance=1000)
    fig.update_xaxes(
        showspikes=True,
        spikecolor=tokens["axis"],
        spikethickness=1,
        spikedash="dot",
        spikemode="across",
    )
    fig.update_yaxes(
        showspikes=True,
        spikecolor=tokens["axis"],
        spikethickness=1,
        spikedash="dot",
        spikemode="across",
    )
    return fig


def _add_exo_annotation(fig):
    """Add 'exo up' annotation to DSC/DTA plots (industry standard)."""
    tokens = _plot_tokens()
    fig.add_annotation(
        text="exo \u2191",
        xref="paper", yref="paper",
        x=0.01, y=1.0,
        xanchor="left",
        yanchor="bottom",
        showarrow=False,
        font=dict(size=11, color=tokens["subtle_text"], family=_PLOT_FONT_FAMILY),
    )


def create_thermal_plot(
    x, y, title="", x_label="Temperature (°C)", y_label="Signal",
    name="Signal", color=None, mode="lines", display_settings: dict | None = None,
):
    """Create a basic thermal analysis plot."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y, mode=mode, name=name,
        line=dict(color=color or THERMAL_COLORS[0], width=2.6),
    ))
    fig.update_layout(xaxis_title=x_label, yaxis_title=y_label)
    apply_plot_display_settings(fig, display_settings, title=title)
    apply_plotly_config(fig)
    return fig


def create_dsc_plot(temperature, heat_flow, title="DSC Curve",
                    y_label="Heat Flow (mW/mg)", baseline=None,
                    peaks=None, smoothed=None, display_settings: dict | None = None):
    """Create a DSC plot with optional baseline and peak markers."""
    tokens = _plot_tokens()
    fig = go.Figure()

    if smoothed is not None:
        fig.add_trace(go.Scatter(
            x=temperature, y=heat_flow, mode="lines", name="Raw",
            line=dict(color=tokens["axis"], width=1),
            opacity=0.5,
        ))
        fig.add_trace(go.Scatter(
            x=temperature, y=smoothed, mode="lines", name="Smoothed",
            line=dict(color=THERMAL_COLORS[0], width=2.6),
        ))
    else:
        fig.add_trace(go.Scatter(
            x=temperature, y=heat_flow, mode="lines", name="Heat Flow",
            line=dict(color=THERMAL_COLORS[0], width=2.6),
        ))

    if baseline is not None:
        fig.add_trace(go.Scatter(
            x=temperature, y=baseline, mode="lines", name="Baseline",
            line=dict(color=BASELINE_COLOR, width=1.4, dash="dash"),
        ))

    if peaks:
        peak_temps = [p.peak_temperature for p in peaks]
        peak_signals = [p.peak_signal for p in peaks]
        hover_texts = []
        for p in peaks:
            text = f"T={p.peak_temperature:.1f}°C"
            if p.onset_temperature is not None:
                text += f"<br>Onset={p.onset_temperature:.1f}°C"
            if p.area is not None:
                text += f"<br>Area={p.area:.2f} J/g"
            hover_texts.append(text)

        fig.add_trace(go.Scatter(
            x=peak_temps, y=peak_signals, mode="markers+text",
            name="Peaks",
            marker=dict(color=THERMAL_COLORS[3], size=9, symbol="diamond"),
            text=[f"{t:.1f}°C" for t in peak_temps],
            textposition="top center",
            textfont=dict(size=10.5, color=tokens["subtle_text"]),
            hovertext=hover_texts,
            hoverinfo="text",
        ))

        for p in peaks:
            if p.onset_temperature is not None:
                fig.add_vline(
                    x=p.onset_temperature, line_dash="dot",
                    line_color=tokens["axis"], opacity=0.55,
                    annotation_text=f"Onset {p.onset_temperature:.1f}°C",
                    annotation=dict(font=dict(size=10, color=tokens["subtle_text"], family=_PLOT_FONT_FAMILY)),
                )

    fig.update_layout(xaxis_title="Temperature (°C)", yaxis_title=y_label)
    _add_exo_annotation(fig)
    apply_plot_display_settings(fig, display_settings, title=title)
    apply_plotly_config(fig)
    return fig


def create_tga_plot(
    temperature,
    mass,
    title="TGA Curve",
    dtg=None,
    steps=None,
    x_label="Temperature (°C)",
    y_label="Mass (%)",
    mass_name="TGA (Mass %)",
    dtg_name="DTG",
    dtg_label="DTG (%/°C)",
    step_prefix="Step",
    display_settings: dict | None = None,
):
    """Create a TGA plot with optional DTG overlay and step markers."""
    tokens = _plot_tokens()
    if dtg is not None:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
    else:
        fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=temperature, y=mass, mode="lines", name=mass_name,
        line=dict(color=THERMAL_COLORS[0], width=2.6),
    ), secondary_y=False if dtg is not None else None)

    if dtg is not None:
        fig.add_trace(go.Scatter(
            x=temperature, y=dtg, mode="lines", name=dtg_name,
            line=dict(color=THERMAL_COLORS[1], width=1.8, dash="dash"),
        ), secondary_y=True)
        fig.update_yaxes(title_text=dtg_label, secondary_y=True)

    if steps:
        for i, step in enumerate(steps):
            fig.add_vrect(
                x0=step.onset_temperature, x1=step.endset_temperature,
                fillcolor=THERMAL_COLORS[i % len(THERMAL_COLORS)],
                opacity=0.08, line_width=0,
                annotation_text=f"{step_prefix} {i+1}: {step.mass_loss_percent:.1f}%",
                annotation_position="top left",
                annotation=dict(font=dict(size=10, color=tokens["subtle_text"], family=_PLOT_FONT_FAMILY)),
            )

    fig.update_layout(xaxis_title=x_label, yaxis_title=y_label)
    apply_plot_display_settings(fig, display_settings, title=title)
    apply_plotly_config(fig)
    return fig


def create_dta_plot(temperature, signal, title="DTA Curve",
                    baseline=None, peaks=None, smoothed=None, display_settings: dict | None = None):
    """Create a DTA plot."""
    fig = create_dsc_plot(
        temperature, signal, title=title,
        y_label="\u0394T (\u00b5V)", baseline=baseline,
        peaks=peaks, smoothed=smoothed,
        display_settings=display_settings,
    )
    # exo annotation is already added by create_dsc_plot
    return fig


def create_kissinger_plot(inv_tp, ln_beta_tp2, ea_kj, ln_a, r_squared, display_settings: dict | None = None):
    """Create Kissinger plot: ln(β/Tp²) vs 1000/Tp."""
    fig = go.Figure()

    x_fit = np.linspace(min(inv_tp) * 0.98, max(inv_tp) * 1.02, 100)
    slope = -ea_kj * 1000 / 8.314462
    y_fit = slope * x_fit + ln_a

    fig.add_trace(go.Scatter(
        x=inv_tp, y=ln_beta_tp2, mode="markers",
        name="Data Points",
        marker=dict(color=THERMAL_COLORS[0], size=9),
    ))
    fig.add_trace(go.Scatter(
        x=x_fit, y=y_fit, mode="lines",
        name=f"Fit (Ea={ea_kj:.1f} kJ/mol, R²={r_squared:.4f})",
        line=dict(color=THERMAL_COLORS[1], width=2.2),
    ))

    fig.update_layout(xaxis_title="1000/Tp (1/K)", yaxis_title="ln(β/Tp²)")
    apply_plot_display_settings(fig, display_settings, title="Kissinger Plot")
    apply_plotly_config(fig)
    return fig


def create_multirate_overlay(temperature_list, signal_list, rate_labels,
                              title="Multi-Rate Overlay", display_settings: dict | None = None):
    """Overlay multiple heating rate curves."""
    fig = go.Figure()
    for i, (temp, sig, label) in enumerate(zip(temperature_list, signal_list, rate_labels)):
        fig.add_trace(go.Scatter(
            x=temp, y=sig, mode="lines", name=label,
            line=dict(color=THERMAL_COLORS[i % len(THERMAL_COLORS)], width=2.3),
        ))
    fig.update_layout(xaxis_title="Temperature (°C)", yaxis_title="Signal")
    apply_plot_display_settings(fig, display_settings, title=title)
    apply_plotly_config(fig)
    return fig


def create_overlay_plot(series, title="Run Comparison", x_label="Temperature (°C)", y_label="Signal", display_settings: dict | None = None):
    """Overlay multiple thermal runs on the same axes."""
    fig = go.Figure()
    for i, item in enumerate(series):
        fig.add_trace(
            go.Scatter(
                x=item["x"],
                y=item["y"],
                mode=item.get("mode", "lines"),
                name=item.get("name", f"Run {i + 1}"),
                line=dict(
                    color=item.get("color", THERMAL_COLORS[i % len(THERMAL_COLORS)]),
                    width=item.get("width", 2.3),
                    dash=item.get("dash", "solid"),
                ),
                opacity=item.get("opacity", 1.0),
            )
        )
    fig.update_layout(xaxis_title=x_label, yaxis_title=y_label)
    apply_plot_display_settings(fig, display_settings, title=title)
    apply_plotly_config(fig)
    return fig


def create_deconvolution_plot(temperature, signal, fitted, components,
                               title="Peak Deconvolution", display_settings: dict | None = None):
    """Plot original signal with fitted sum and individual peak components."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=temperature, y=signal, mode="lines", name="Data",
        line=dict(color=THERMAL_COLORS[0], width=2.4),
    ))
    fig.add_trace(go.Scatter(
        x=temperature, y=fitted, mode="lines", name="Fit (Sum)",
        line=dict(color=THERMAL_COLORS[3], width=2.2, dash="dash"),
    ))
    for i, comp in enumerate(components):
        fig.add_trace(go.Scatter(
            x=temperature, y=comp, mode="lines",
            name=f"Peak {i+1}",
            line=dict(color=THERMAL_COLORS[(i+2) % len(THERMAL_COLORS)], width=1.4, dash="dot"),
            fill="tozeroy", opacity=0.18,
        ))
    fig.update_layout(xaxis_title="Temperature (°C)", yaxis_title="Signal")
    apply_plot_display_settings(fig, display_settings, title=title)
    apply_plotly_config(fig)
    return fig


def fig_to_bytes(fig, format="png", width=1000, height=600):
    """Export a Plotly figure to bytes (PNG or SVG)."""
    export_fig = go.Figure(fig)
    export_settings = {}
    meta = getattr(fig.layout, "meta", None)
    if isinstance(meta, dict):
        export_settings = meta.get("plot_display_settings") or {}
    apply_plot_display_settings(export_fig, export_settings, for_export=True, scale_traces=False)
    export_width = max(int(width), _DEFAULT_EXPORT_WIDTH)
    export_height = max(int(height), _DEFAULT_EXPORT_HEIGHT)
    return export_fig.to_image(format=format, width=export_width, height=export_height, engine="kaleido")
