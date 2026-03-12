from __future__ import annotations

from core.processing_schema import ensure_processing_payload, get_workflow_templates


def test_get_workflow_templates_includes_dta_kinetics_and_deconvolution():
    dta_ids = {entry["id"] for entry in get_workflow_templates("DTA")}
    kissinger_ids = {entry["id"] for entry in get_workflow_templates("Kissinger")}
    ofw_ids = {entry["id"] for entry in get_workflow_templates("Ozawa-Flynn-Wall")}
    friedman_ids = {entry["id"] for entry in get_workflow_templates("Friedman")}
    deconv_ids = {entry["id"] for entry in get_workflow_templates("Peak Deconvolution")}

    assert "dta.general" in dta_ids
    assert "kinetics.kissinger_general" in kissinger_ids
    assert "kinetics.ofw_general" in ofw_ids
    assert "kinetics.friedman_general" in friedman_ids
    assert "deconvolution.general" in deconv_ids


def test_get_workflow_templates_includes_ftir_and_raman_catalogs():
    ftir_ids = {entry["id"] for entry in get_workflow_templates("FTIR")}
    raman_ids = {entry["id"] for entry in get_workflow_templates("raman")}

    assert "ftir.general" in ftir_ids
    assert "ftir.functional_groups" in ftir_ids
    assert "raman.general" in raman_ids
    assert "raman.polymorph_screening" in raman_ids


def test_ensure_processing_payload_populates_ftir_template_sections_and_method_defaults():
    payload = ensure_processing_payload(
        {
            "smoothing": {"method": "savgol", "window_length": 9},
            "baseline": {"method": "asls"},
            "normalization": {"method": "vector"},
            "peak_detection": {"prominence": 0.02},
            "similarity_matching": {"top_n": 5, "metric": "cosine"},
        },
        analysis_type="FTIR",
        workflow_template="ftir.general",
    )

    assert payload["analysis_type"] == "FTIR"
    assert payload["workflow_template_id"] == "ftir.general"
    assert list(payload["signal_pipeline"].keys()) == ["smoothing", "baseline", "normalization"]
    assert payload["analysis_steps"]["peak_detection"]["prominence"] == 0.02
    assert payload["analysis_steps"]["similarity_matching"]["metric"] == "cosine"
    assert payload["method_context"]["default_pipeline_order"] == ["smoothing", "baseline", "normalization"]


def test_ensure_processing_payload_populates_raman_template_sections_and_method_defaults():
    payload = ensure_processing_payload(
        {
            "signal_pipeline": {
                "smoothing": {"method": "savgol"},
                "baseline": {"method": "rubberband"},
                "normalization": {"method": "snv"},
            },
            "analysis_steps": {
                "peak_detection": {"prominence": 0.01},
                "similarity_matching": {"top_n": 3, "metric": "pearson"},
            },
        },
        analysis_type="raman",
        workflow_template="raman.general",
    )

    assert payload["analysis_type"] == "RAMAN"
    assert payload["workflow_template_id"] == "raman.general"
    assert list(payload["signal_pipeline"].keys()) == ["smoothing", "baseline", "normalization"]
    assert payload["signal_pipeline"]["normalization"]["method"] == "snv"
    assert payload["analysis_steps"]["similarity_matching"]["top_n"] == 3
    assert payload["method_context"]["spectral_domain"] == "raman_shift"


def test_ensure_processing_payload_populates_kissinger_defaults():
    payload = ensure_processing_payload(
        analysis_type="Kissinger",
        workflow_template="kinetics.kissinger_general",
    )

    assert payload["analysis_type"] == "KISSINGER"
    assert payload["workflow_template_id"] == "kinetics.kissinger_general"
    assert payload["method_context"]["kinetic_family"] == "model_fitting"
    assert payload["method_context"]["formulation"] == "kissinger"


def test_ensure_processing_payload_populates_deconvolution_defaults():
    payload = ensure_processing_payload(
        analysis_type="Peak Deconvolution",
        workflow_template="deconvolution.general",
    )

    assert payload["analysis_type"] == "PEAK DECONVOLUTION"
    assert payload["workflow_template_id"] == "deconvolution.general"
    assert payload["method_context"]["fit_engine"] == "lmfit"
    assert payload["method_context"]["objective_function"] == "least_squares"
