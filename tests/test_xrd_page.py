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
