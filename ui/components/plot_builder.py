"""Plotly chart builders for thermal analysis data."""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


THERMAL_COLORS = [
    "#1F3B5B",
    "#C45A5A",
    "#4E7A64",
    "#7A5C9E",
    "#D08B45",
    "#2C7DA0",
    "#A44A3F",
    "#667085",
]

BASELINE_COLOR = "#697586"
_PLOT_FONT_FAMILY = "Aptos, Segoe UI, Arial, sans-serif"
_PLOT_TEXT_COLOR = "#1F2937"
_PLOT_SUBTLE_TEXT = "#64748B"
_PLOT_PAPER_BG = "#FCFCF8"
_PLOT_AREA_BG = "#FFFFFF"
_PLOT_GRID_COLOR = "#E7ECF3"
_PLOT_AXIS_COLOR = "#AAB4C3"
_PLOT_HOVER_BORDER = "#CBD5E1"
_DEFAULT_EXPORT_WIDTH = 1400
_DEFAULT_EXPORT_HEIGHT = 840

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

DEFAULT_LAYOUT = dict(
    template="plotly_white",
    colorway=THERMAL_COLORS,
    font=dict(family=_PLOT_FONT_FAMILY, size=12, color=_PLOT_TEXT_COLOR),
    hoverlabel=dict(
        bgcolor="#FFFFFF",
        bordercolor=_PLOT_HOVER_BORDER,
        font_size=12,
        font_family=_PLOT_FONT_FAMILY,
        font_color=_PLOT_TEXT_COLOR,
    ),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="left",
        x=0.0,
        bgcolor="rgba(255,255,255,0.68)",
        bordercolor="rgba(0,0,0,0)",
        borderwidth=0,
        font=dict(size=10.5, color=_PLOT_SUBTLE_TEXT),
        title=dict(text=""),
        itemsizing="constant",
    ),
    title=dict(
        x=0.0,
        xanchor="left",
        y=0.98,
        yanchor="top",
        pad=dict(b=10),
        font=dict(size=18, color=_PLOT_TEXT_COLOR),
    ),
    margin=dict(l=76, r=44, t=88, b=68),
    paper_bgcolor=_PLOT_PAPER_BG,
    plot_bgcolor=_PLOT_AREA_BG,
    autosize=True,
    xaxis=dict(
        gridcolor=_PLOT_GRID_COLOR,
        gridwidth=1,
        ticks="outside",
        tickcolor=_PLOT_AXIS_COLOR,
        ticklen=5,
        showline=True,
        linecolor=_PLOT_AXIS_COLOR,
        linewidth=1.1,
        zeroline=False,
        mirror=False,
        automargin=True,
        title_standoff=12,
    ),
    yaxis=dict(
        gridcolor=_PLOT_GRID_COLOR,
        gridwidth=1,
        ticks="outside",
        tickcolor=_PLOT_AXIS_COLOR,
        ticklen=5,
        showline=True,
        linecolor=_PLOT_AXIS_COLOR,
        linewidth=1.1,
        zeroline=False,
        mirror=False,
        automargin=True,
        title_standoff=12,
    ),
)

def _legend_layout(trace_count: int, *, legend_mode: str, compact: bool) -> tuple[bool, dict]:
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
            bgcolor="rgba(255,255,255,0.72)",
            bordercolor="rgba(0,0,0,0)",
            borderwidth=0,
            tracegroupgap=4,
            font=dict(size=font_size, color=_PLOT_SUBTLE_TEXT),
            title=dict(text=""),
            itemsizing="constant",
        )
    return True, dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="left",
        x=0.0,
        bgcolor="rgba(255,255,255,0.60)",
        bordercolor="rgba(0,0,0,0)",
        borderwidth=0,
        font=dict(size=font_size, color=_PLOT_SUBTLE_TEXT),
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
    return f"{base}<br><span style='font-size:{sub_size}px;color:{_PLOT_SUBTLE_TEXT}'>{sub}</span>"


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
    trace_count = sum(1 for trace in fig.data if getattr(trace, "showlegend", True) is not False)
    showlegend, legend = _legend_layout(trace_count, legend_mode=legend_mode, compact=compact)
    final_title = title if title is not None else getattr(fig.layout.title, "text", "")
    layout = dict(DEFAULT_LAYOUT)
    layout.update(
        title=dict(
            text=_compose_title(final_title, subtitle, compact=compact),
            x=0.0,
            xanchor="left",
            y=0.98,
            yanchor="top",
            pad=dict(b=10),
            font=dict(size=16 if compact else 18, color=_PLOT_TEXT_COLOR, family=_PLOT_FONT_FAMILY),
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
        spikecolor=_PLOT_AXIS_COLOR,
        spikethickness=1,
        spikedash="dot",
        spikemode="across",
        gridcolor=_PLOT_GRID_COLOR,
        linecolor=_PLOT_AXIS_COLOR,
        tickfont=dict(size=11, color=_PLOT_TEXT_COLOR),
        title_font=dict(size=12, color=_PLOT_TEXT_COLOR, family=_PLOT_FONT_FAMILY),
    )
    fig.update_yaxes(
        showspikes=True,
        spikecolor=_PLOT_AXIS_COLOR,
        spikethickness=1,
        spikedash="dot",
        spikemode="across",
        gridcolor=_PLOT_GRID_COLOR,
        linecolor=_PLOT_AXIS_COLOR,
        tickfont=dict(size=11, color=_PLOT_TEXT_COLOR),
        title_font=dict(size=12, color=_PLOT_TEXT_COLOR, family=_PLOT_FONT_FAMILY),
    )
    fig.update_annotations(
        font=dict(size=10.5 if compact else 11, color=_PLOT_SUBTLE_TEXT, family=_PLOT_FONT_FAMILY),
        bgcolor="rgba(255,255,255,0.78)",
        bordercolor="rgba(148,163,184,0.24)",
        borderwidth=0,
        borderpad=2,
    )
    _style_trace_defaults(fig, compact=compact)
    return fig


def apply_plotly_config(fig):
    """Apply shared crosshair and hover behavior without overriding layout composition."""
    fig.update_layout(hovermode="x unified", hoverdistance=80, spikedistance=1000)
    fig.update_xaxes(
        showspikes=True,
        spikecolor=_PLOT_AXIS_COLOR,
        spikethickness=1,
        spikedash="dot",
        spikemode="across",
    )
    fig.update_yaxes(
        showspikes=True,
        spikecolor=_PLOT_AXIS_COLOR,
        spikethickness=1,
        spikedash="dot",
        spikemode="across",
    )
    return fig


def _add_exo_annotation(fig):
    """Add 'exo up' annotation to DSC/DTA plots (industry standard)."""
    fig.add_annotation(
        text="exo \u2191",
        xref="paper", yref="paper",
        x=0.01, y=1.0,
        xanchor="left",
        yanchor="bottom",
        showarrow=False,
        font=dict(size=11, color=_PLOT_SUBTLE_TEXT, family=_PLOT_FONT_FAMILY),
    )


def create_thermal_plot(
    x, y, title="", x_label="Temperature (°C)", y_label="Signal",
    name="Signal", color=None, mode="lines",
):
    """Create a basic thermal analysis plot."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y, mode=mode, name=name,
        line=dict(color=color or THERMAL_COLORS[0], width=2.6),
    ))
    fig.update_layout(xaxis_title=x_label, yaxis_title=y_label)
    apply_professional_plot_theme(fig, title=title)
    apply_plotly_config(fig)
    return fig


def create_dsc_plot(temperature, heat_flow, title="DSC Curve",
                    y_label="Heat Flow (mW/mg)", baseline=None,
                    peaks=None, smoothed=None):
    """Create a DSC plot with optional baseline and peak markers."""
    fig = go.Figure()

    if smoothed is not None:
        fig.add_trace(go.Scatter(
            x=temperature, y=heat_flow, mode="lines", name="Raw",
            line=dict(color="#CCCCCC", width=1),
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
            textfont=dict(size=10.5, color=_PLOT_SUBTLE_TEXT),
            hovertext=hover_texts,
            hoverinfo="text",
        ))

        for p in peaks:
            if p.onset_temperature is not None:
                fig.add_vline(
                    x=p.onset_temperature, line_dash="dot",
                    line_color=_PLOT_AXIS_COLOR, opacity=0.55,
                    annotation_text=f"Onset {p.onset_temperature:.1f}°C",
                    annotation=dict(font=dict(size=10, color=_PLOT_SUBTLE_TEXT, family=_PLOT_FONT_FAMILY)),
                )

    fig.update_layout(xaxis_title="Temperature (°C)", yaxis_title=y_label)
    _add_exo_annotation(fig)
    apply_professional_plot_theme(fig, title=title)
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
):
    """Create a TGA plot with optional DTG overlay and step markers."""
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
                annotation=dict(font=dict(size=10, color=_PLOT_SUBTLE_TEXT, family=_PLOT_FONT_FAMILY)),
            )

    fig.update_layout(xaxis_title=x_label, yaxis_title=y_label)
    apply_professional_plot_theme(fig, title=title, legend_mode="auto")
    apply_plotly_config(fig)
    return fig


def create_dta_plot(temperature, signal, title="DTA Curve",
                    baseline=None, peaks=None, smoothed=None):
    """Create a DTA plot."""
    fig = create_dsc_plot(
        temperature, signal, title=title,
        y_label="\u0394T (\u00b5V)", baseline=baseline,
        peaks=peaks, smoothed=smoothed,
    )
    # exo annotation is already added by create_dsc_plot
    return fig


def create_kissinger_plot(inv_tp, ln_beta_tp2, ea_kj, ln_a, r_squared):
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
    apply_professional_plot_theme(fig, title="Kissinger Plot")
    apply_plotly_config(fig)
    return fig


def create_multirate_overlay(temperature_list, signal_list, rate_labels,
                              title="Multi-Rate Overlay"):
    """Overlay multiple heating rate curves."""
    fig = go.Figure()
    for i, (temp, sig, label) in enumerate(zip(temperature_list, signal_list, rate_labels)):
        fig.add_trace(go.Scatter(
            x=temp, y=sig, mode="lines", name=label,
            line=dict(color=THERMAL_COLORS[i % len(THERMAL_COLORS)], width=2.3),
        ))
    fig.update_layout(xaxis_title="Temperature (°C)", yaxis_title="Signal")
    apply_professional_plot_theme(fig, title=title, legend_mode="auto")
    apply_plotly_config(fig)
    return fig


def create_overlay_plot(series, title="Run Comparison", x_label="Temperature (°C)", y_label="Signal"):
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
    apply_professional_plot_theme(fig, title=title, legend_mode="auto")
    apply_plotly_config(fig)
    return fig


def create_deconvolution_plot(temperature, signal, fitted, components,
                               title="Peak Deconvolution"):
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
    apply_professional_plot_theme(fig, title=title, legend_mode="auto")
    apply_plotly_config(fig)
    return fig


def fig_to_bytes(fig, format="png", width=1000, height=600):
    """Export a Plotly figure to bytes (PNG or SVG)."""
    export_fig = go.Figure(fig)
    apply_professional_plot_theme(export_fig, for_export=True, compact=False, legend_mode="auto")
    export_width = max(int(width), _DEFAULT_EXPORT_WIDTH)
    export_height = max(int(height), _DEFAULT_EXPORT_HEIGHT)
    return export_fig.to_image(format=format, width=export_width, height=export_height, engine="kaleido")
