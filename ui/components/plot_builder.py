"""Plotly chart builders for thermal analysis data."""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np


THERMAL_COLORS = [
    "#1F77B4", "#D62728", "#2CA02C", "#E71D36",
    "#8338EC", "#FF9F1C", "#3A86FF", "#06D6A0",
]

BASELINE_COLOR = "#555555"

PLOTLY_CONFIG = dict(
    displayModeBar=True,
    scrollZoom=True,
    modeBarButtonsToAdd=["drawline", "drawopenpath", "eraseshape"],
    modeBarButtonsToRemove=["lasso2d"],
    displaylogo=False,
    toImageButtonOptions=dict(
        format="png",
        filename="thermoanalyzer_plot",
        width=1200,
        height=700,
        scale=2,
    ),
)

DEFAULT_LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, Arial, sans-serif", size=12),
    hoverlabel=dict(bgcolor="white", font_size=12, font_family="Consolas, monospace"),
    legend=dict(
        orientation="v", yanchor="top", y=0.98, xanchor="right", x=0.99,
        bgcolor="rgba(255,255,255,0.9)", bordercolor="#D1D5DB", borderwidth=1,
        font=dict(size=11),
    ),
    margin=dict(l=60, r=30, t=50, b=60),
    paper_bgcolor="#FAFBFC",
    xaxis=dict(
        gridcolor="#E5E7EB", gridwidth=1, mirror=True, ticks="outside",
        showline=True, linecolor="#9CA3AF", linewidth=1,
    ),
    yaxis=dict(
        gridcolor="#E5E7EB", gridwidth=1, mirror=True, ticks="outside",
        showline=True, linecolor="#9CA3AF", linewidth=1,
    ),
)


def apply_plotly_config(fig):
    """Apply crosshair hover and spike lines to a Plotly figure."""
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(
        showspikes=True, spikecolor="#9CA3AF", spikethickness=1,
        spikedash="dot", spikemode="across",
    )
    fig.update_yaxes(
        showspikes=True, spikecolor="#9CA3AF", spikethickness=1,
        spikedash="dot", spikemode="across",
    )
    return fig


def _style_title(fig):
    """Center the title and apply professional font sizing."""
    fig.update_layout(title_x=0.5, title_xanchor="center", title_font_size=14)


def _add_exo_annotation(fig):
    """Add 'exo up' annotation to DSC/DTA plots (industry standard)."""
    fig.add_annotation(
        text="exo \u2191",
        xref="paper", yref="paper",
        x=0.02, y=0.98,
        showarrow=False,
        font=dict(size=11, color="#6B7280", family="Inter, Arial, sans-serif"),
        bgcolor="rgba(255,255,255,0.7)",
        bordercolor="#D1D5DB",
        borderwidth=1,
        borderpad=3,
    )


def create_thermal_plot(
    x, y, title="", x_label="Temperature (°C)", y_label="Signal",
    name="Signal", color=None, mode="lines",
):
    """Create a basic thermal analysis plot."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y, mode=mode, name=name,
        line=dict(color=color or THERMAL_COLORS[0], width=2),
    ))
    fig.update_layout(
        title=title, xaxis_title=x_label, yaxis_title=y_label,
        **DEFAULT_LAYOUT,
    )
    _style_title(fig)
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
            line=dict(color=THERMAL_COLORS[0], width=2),
        ))
    else:
        fig.add_trace(go.Scatter(
            x=temperature, y=heat_flow, mode="lines", name="Heat Flow",
            line=dict(color=THERMAL_COLORS[0], width=2),
        ))

    if baseline is not None:
        fig.add_trace(go.Scatter(
            x=temperature, y=baseline, mode="lines", name="Baseline",
            line=dict(color=BASELINE_COLOR, width=1.5, dash="dash"),
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
            marker=dict(color=THERMAL_COLORS[3], size=10, symbol="diamond"),
            text=[f"{t:.1f}°C" for t in peak_temps],
            textposition="top center",
            hovertext=hover_texts,
            hoverinfo="text",
        ))

        for p in peaks:
            if p.onset_temperature is not None:
                fig.add_vline(
                    x=p.onset_temperature, line_dash="dot",
                    line_color="gray", opacity=0.5,
                    annotation_text=f"Onset {p.onset_temperature:.1f}°C",
                )

    fig.update_layout(
        title=title, xaxis_title="Temperature (°C)", yaxis_title=y_label,
        **DEFAULT_LAYOUT,
    )
    _style_title(fig)
    _add_exo_annotation(fig)
    apply_plotly_config(fig)
    return fig


def create_tga_plot(temperature, mass, title="TGA Curve",
                    dtg=None, steps=None):
    """Create a TGA plot with optional DTG overlay and step markers."""
    if dtg is not None:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
    else:
        fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=temperature, y=mass, mode="lines", name="TGA (Mass %)",
        line=dict(color=THERMAL_COLORS[0], width=2),
    ), secondary_y=False if dtg is not None else None)

    if dtg is not None:
        fig.add_trace(go.Scatter(
            x=temperature, y=dtg, mode="lines", name="DTG",
            line=dict(color=THERMAL_COLORS[1], width=1.5, dash="dash"),
        ), secondary_y=True)
        fig.update_yaxes(title_text="DTG (%/°C)", secondary_y=True)

    if steps:
        for i, step in enumerate(steps):
            fig.add_vrect(
                x0=step.onset_temperature, x1=step.endset_temperature,
                fillcolor=THERMAL_COLORS[i % len(THERMAL_COLORS)],
                opacity=0.1, line_width=0,
                annotation_text=f"Step {i+1}: {step.mass_loss_percent:.1f}%",
                annotation_position="top left",
            )

    fig.update_layout(
        title=title,
        xaxis_title="Temperature (°C)",
        yaxis_title="Mass (%)",
        **DEFAULT_LAYOUT,
    )
    _style_title(fig)
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
        marker=dict(color=THERMAL_COLORS[0], size=10),
    ))
    fig.add_trace(go.Scatter(
        x=x_fit, y=y_fit, mode="lines",
        name=f"Fit (Ea={ea_kj:.1f} kJ/mol, R²={r_squared:.4f})",
        line=dict(color=THERMAL_COLORS[1], width=2),
    ))

    fig.update_layout(
        title="Kissinger Plot",
        xaxis_title="1000/Tp (1/K)",
        yaxis_title="ln(β/Tp²)",
        **DEFAULT_LAYOUT,
    )
    _style_title(fig)
    apply_plotly_config(fig)
    return fig


def create_multirate_overlay(temperature_list, signal_list, rate_labels,
                              title="Multi-Rate Overlay"):
    """Overlay multiple heating rate curves."""
    fig = go.Figure()
    for i, (temp, sig, label) in enumerate(zip(temperature_list, signal_list, rate_labels)):
        fig.add_trace(go.Scatter(
            x=temp, y=sig, mode="lines", name=label,
            line=dict(color=THERMAL_COLORS[i % len(THERMAL_COLORS)], width=2),
        ))
    fig.update_layout(
        title=title,
        xaxis_title="Temperature (°C)",
        yaxis_title="Signal",
        **DEFAULT_LAYOUT,
    )
    _style_title(fig)
    apply_plotly_config(fig)
    return fig


def create_deconvolution_plot(temperature, signal, fitted, components,
                               title="Peak Deconvolution"):
    """Plot original signal with fitted sum and individual peak components."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=temperature, y=signal, mode="lines", name="Data",
        line=dict(color=THERMAL_COLORS[0], width=2),
    ))
    fig.add_trace(go.Scatter(
        x=temperature, y=fitted, mode="lines", name="Fit (Sum)",
        line=dict(color=THERMAL_COLORS[3], width=2, dash="dash"),
    ))
    for i, comp in enumerate(components):
        fig.add_trace(go.Scatter(
            x=temperature, y=comp, mode="lines",
            name=f"Peak {i+1}",
            line=dict(color=THERMAL_COLORS[(i+2) % len(THERMAL_COLORS)], width=1.5, dash="dot"),
            fill="tozeroy", opacity=0.3,
        ))
    fig.update_layout(
        title=title,
        xaxis_title="Temperature (°C)",
        yaxis_title="Signal",
        **DEFAULT_LAYOUT,
    )
    _style_title(fig)
    apply_plotly_config(fig)
    return fig


def fig_to_bytes(fig, format="png", width=1000, height=600):
    """Export a Plotly figure to bytes (PNG or SVG)."""
    return fig.to_image(format=format, width=width, height=height, engine="kaleido")
