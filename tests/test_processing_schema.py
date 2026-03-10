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
