"""About page -- static product info."""

import dash
from dash import html
import dash_bootstrap_components as dbc

from dash_app.components.chrome import page_header

dash.register_page(__name__, path="/about", title="About - MaterialScope")


layout = html.Div([
    page_header("About MaterialScope", "Product information and capabilities.", badge="Product Info"),

    dbc.Card([
        dbc.CardBody([
            html.H4("Overview", className="mb-3"),
            html.P(
                "MaterialScope is a vendor-independent, multimodal characterization "
                "workbench for QC and R&D laboratories."
            ),
            html.P(
                "It supports DSC, TGA, DTA, FTIR, Raman, and XRD data import, "
                "analysis, comparison, and reporting -- all within a single unified workspace."
            ),
            html.Hr(),
            html.H5("Supported Modalities"),
            dbc.ListGroup([
                dbc.ListGroupItem("DSC -- Differential Scanning Calorimetry"),
                dbc.ListGroupItem("TGA -- Thermogravimetric Analysis"),
                dbc.ListGroupItem("DTA -- Differential Thermal Analysis"),
                dbc.ListGroupItem("FTIR -- Fourier-Transform Infrared Spectroscopy"),
                dbc.ListGroupItem("RAMAN -- Raman Spectroscopy"),
                dbc.ListGroupItem("XRD -- X-Ray Diffraction"),
            ], flush=True, className="mb-3"),
            html.Hr(),
            html.H5("Architecture"),
            html.P(
                "This application uses a Dash + Plotly frontend with a FastAPI backend "
                "and a pure-Python scientific core engine."
            ),
        ])
    ], className="mb-4"),
])
