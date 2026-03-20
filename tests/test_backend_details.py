from __future__ import annotations

import base64
import uuid

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.store import ProjectStore
from core.modalities import stable_analysis_types
from core.result_serialization import make_result_record
from backend.workspace import normalize_workspace_state


class _BackendStubProvider:
    provider_result_source = "stub_search"

    def __init__(self, provider_id: str, sources: list[dict]) -> None:
        self.provider_id = provider_id
        self.sources = list(sources)
        self.last_request_id = ""

    def search(self, query: str, filters: dict | None = None) -> list[dict]:
        del filters
        self.last_request_id = f"litreq_{self.provider_id}_{uuid.uuid4().hex[:8]}"
        rows: list[dict] = []
        for source in self.sources:
            provenance = dict(source.get("provenance") or {})
            rows.append(
                {
                    **dict(source),
                    "provenance": {
                        **provenance,
                        "provider_id": self.provider_id,
                        "request_id": self.last_request_id,
                        "result_source": self.provider_result_source,
                        "query": query,
                        "provider_scope": [self.provider_id],
                        "provider_request_ids": [self.last_request_id],
                    },
                }
            )
        return rows

    def fetch_accessible_text(self, candidate: dict) -> dict | None:
        access_class = str(candidate.get("access_class") or "").lower()
        if access_class == "restricted_external":
            return None
        text = str(candidate.get("oa_full_text") or candidate.get("abstract_text") or "").strip()
        if not text:
            return None
        field = "oa_full_text" if candidate.get("oa_full_text") else "abstract_text"
        return {
            "source_id": candidate.get("source_id"),
            "text": text,
            "field": field,
            "access_class": candidate.get("access_class"),
        }


def _lit_source(*, source_id: str, access_class: str, text: str, hint: str, doi: str | None = None, url: str | None = None) -> dict:
    return {
        "source_id": source_id,
        "title": f"{source_id} title",
        "authors": ["A. Author"],
        "journal": "Fixture Journal",
        "year": 2025,
        "doi": doi if doi is not None else f"10.1000/{source_id}",
        "url": url if url is not None else f"https://example.test/{source_id}",
        "access_class": access_class,
        "available_fields": ["metadata", "abstract"],
        "abstract_text": text if access_class != "restricted_external" else "",
        "oa_full_text": text if access_class == "open_access_full_text" else "",
        "source_license_note": "fixture",
        "citation_text": "",
        "provenance": {
            "modalities": ["XRD"],
            "keywords": ["phase alpha", "xrd"],
            "comparison_hint": hint,
        },
    }


def _seed_xrd_result_store() -> tuple[ProjectStore, str, str]:
    store = ProjectStore()
    record = make_result_record(
        result_id="xrd_demo",
        analysis_type="XRD",
        status="stable",
        dataset_key="xrd_demo",
        metadata={"sample_name": "Phase Alpha Sample"},
        summary={
            "top_candidate_name": "Phase Alpha",
            "top_candidate_display_name_unicode": "Phase Alpha",
            "top_candidate_formula": "Al2O3",
            "top_candidate_id": "phase_alpha_001",
            "top_candidate_score": 0.82,
            "top_candidate_shared_peak_count": 6,
            "top_candidate_coverage_ratio": 0.71,
            "top_candidate_weighted_overlap_score": 0.74,
            "top_candidate_provider": "COD",
            "library_result_source": "xrd_cloud_search",
            "library_provider_scope": ["cod"],
            "match_status": "matched",
            "confidence_band": "medium",
        },
        rows=[{"rank": 1, "candidate_name": "Phase Alpha", "normalized_score": 0.82}],
        scientific_context={
            "scientific_claims": [
                {
                    "id": "C1",
                    "strength": "mechanistic",
                    "claim": "Phase Alpha remains a qualitative XRD follow-up candidate rather than a confirmed phase call.",
                    "evidence": ["Shared peaks remain consistent with the retained candidate."],
                }
            ],
            "uncertainty_assessment": {"overall_confidence": "moderate", "items": ["Interpretation remains qualitative."]},
        },
        validation={"status": "pass", "warnings": [], "issues": []},
    )
    project_id = store.put(normalize_workspace_state({"results": {record["id"]: record}}))
    return store, project_id, record["id"]


def _seed_thermal_result_store(analysis_type: str) -> tuple[ProjectStore, str, str]:
    normalized = analysis_type.upper()
    if normalized == "DSC":
        record = make_result_record(
            result_id="dsc_demo",
            analysis_type="DSC",
            status="stable",
            dataset_key="dsc_demo",
            metadata={"sample_name": "Polymer A"},
            summary={"sample_name": "Polymer A", "peak_count": 1, "glass_transition_count": 1, "tg_midpoint": 118.4},
            rows=[{"peak_type": "endo", "peak_temperature": 121.2}],
            scientific_context={
                "scientific_claims": [{"id": "C1", "claim": "The DSC result indicates a glass-transition-related thermal feature that remains qualitative."}],
                "uncertainty_assessment": {"overall_confidence": "moderate", "items": ["Interpretation remains qualitative."]},
            },
            validation={"status": "pass", "warnings": [], "issues": []},
        )
    elif normalized == "DTA":
        record = make_result_record(
            result_id="dta_demo",
            analysis_type="DTA",
            status="stable",
            dataset_key="dta_demo",
            metadata={"sample_name": "Ore B"},
            summary={"sample_name": "Ore B", "peak_count": 1},
            rows=[{"peak_type": "exo", "peak_temperature": 642.8}],
            scientific_context={
                "scientific_claims": [{"id": "C1", "claim": "The DTA result indicates a leading exothermic event that remains qualitative."}],
                "uncertainty_assessment": {"overall_confidence": "moderate", "items": ["Interpretation remains qualitative."]},
            },
            validation={"status": "pass", "warnings": [], "issues": []},
        )
    else:
        record = make_result_record(
            result_id="tga_demo",
            analysis_type="TGA",
            status="stable",
            dataset_key="tga_demo",
            metadata={"sample_name": "Composite C"},
            summary={"sample_name": "Composite C", "step_count": 1, "total_mass_loss_percent": 32.4, "residue_percent": 67.6},
            rows=[{"midpoint_temperature": 411.0, "mass_loss_percent": 32.4}],
            scientific_context={
                "scientific_claims": [{"id": "C1", "claim": "The TGA result indicates a decomposition profile with a dominant mass-loss step that remains qualitative."}],
                "uncertainty_assessment": {"overall_confidence": "moderate", "items": ["Interpretation remains qualitative."]},
            },
            validation={"status": "pass", "warnings": [], "issues": []},
        )
    store = ProjectStore()
    project_id = store.put(normalize_workspace_state({"results": {record["id"]: record}}))
    return store, project_id, record["id"]


def _headers() -> dict[str, str]:
    return {"X-TA-Token": "details-token"}


def _as_b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _import_dataset(client: TestClient, project_id: str, thermal_dataset, *, file_name: str, data_type: str) -> str:
    csv_bytes = thermal_dataset.data.to_csv(index=False).encode("utf-8")
    imported = client.post(
        "/dataset/import",
        headers=_headers(),
        json={
            "project_id": project_id,
            "file_name": file_name,
            "file_base64": _as_b64(csv_bytes),
            "data_type": data_type,
        },
    )
    assert imported.status_code == 200
    return imported.json()["dataset"]["key"]


def _seed_workspace_with_dsc_result(client: TestClient, thermal_dataset) -> tuple[str, str, str]:
    created = client.post("/workspace/new", headers=_headers()).json()
    project_id = created["project_id"]
    dataset_key = _import_dataset(client, project_id, thermal_dataset, file_name="seed_dsc.csv", data_type="DSC")

    run = client.post(
        "/analysis/run",
        headers=_headers(),
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": "DSC",
            "workflow_template_id": "dsc.general",
        },
    )
    assert run.status_code == 200
    result_id = run.json()["result_id"]
    assert result_id
    return project_id, dataset_key, result_id


def test_dataset_and_result_detail_endpoints(thermal_dataset):
    app = create_app(api_token="details-token")
    client = TestClient(app)
    project_id, dataset_key, result_id = _seed_workspace_with_dsc_result(client, thermal_dataset)

    ds_detail = client.get(f"/workspace/{project_id}/datasets/{dataset_key}", headers=_headers())
    assert ds_detail.status_code == 200
    ds_body = ds_detail.json()
    assert ds_body["dataset"]["key"] == dataset_key
    assert "validation" in ds_body
    assert "metadata" in ds_body
    assert isinstance(ds_body["data_preview"], list)

    result_detail = client.get(f"/workspace/{project_id}/results/{result_id}", headers=_headers())
    assert result_detail.status_code == 200
    result_body = result_detail.json()
    assert result_body["result"]["id"] == result_id
    assert result_body["result"]["analysis_type"] == "DSC"
    assert "processing" in result_body
    assert "provenance" in result_body
    assert "validation" in result_body
    assert result_body["row_count"] >= 0


def test_compare_workspace_read_write(thermal_dataset):
    app = create_app(api_token="details-token")
    client = TestClient(app)
    project_id, dataset_key, _result_id = _seed_workspace_with_dsc_result(client, thermal_dataset)

    compare_get = client.get(f"/workspace/{project_id}/compare", headers=_headers())
    assert compare_get.status_code == 200
    assert compare_get.json()["compare_workspace"]["analysis_type"] in set(stable_analysis_types())

    compare_put = client.put(
        f"/workspace/{project_id}/compare",
        headers=_headers(),
        json={
            "analysis_type": "DSC",
            "selected_datasets": [dataset_key],
            "notes": "Desktop compare smoke",
        },
    )
    assert compare_put.status_code == 200
    payload = compare_put.json()["compare_workspace"]
    assert payload["analysis_type"] == "DSC"
    assert payload["selected_datasets"] == [dataset_key]
    assert payload["notes"] == "Desktop compare smoke"


def test_compare_workspace_accepts_spectral_analysis_types():
    app = create_app(api_token="details-token")
    client = TestClient(app)
    project_id = client.post("/workspace/new", headers=_headers()).json()["project_id"]

    for analysis_type in ("FTIR", "RAMAN"):
        compare_put = client.put(
            f"/workspace/{project_id}/compare",
            headers=_headers(),
            json={"analysis_type": analysis_type, "selected_datasets": [], "notes": f"{analysis_type} lane"},
        )
        assert compare_put.status_code == 200
        payload = compare_put.json()["compare_workspace"]
        assert payload["analysis_type"] == analysis_type
        assert payload["selected_datasets"] == []


def test_compare_workspace_accepts_xrd_analysis_type():
    app = create_app(api_token="details-token")
    client = TestClient(app)
    project_id = client.post("/workspace/new", headers=_headers()).json()["project_id"]

    compare_put = client.put(
        f"/workspace/{project_id}/compare",
        headers=_headers(),
        json={"analysis_type": "XRD", "selected_datasets": [], "notes": "XRD lane"},
    )
    assert compare_put.status_code == 200
    payload = compare_put.json()["compare_workspace"]
    assert payload["analysis_type"] == "XRD"
    assert payload["selected_datasets"] == []


def test_compare_workspace_xrd_lane_filters_incompatible_datasets(thermal_dataset):
    app = create_app(api_token="details-token")
    client = TestClient(app)
    project_id = client.post("/workspace/new", headers=_headers()).json()["project_id"]

    xrd_key = _import_dataset(client, project_id, thermal_dataset, file_name="xrd_lane.csv", data_type="XRD")
    ftir_key = _import_dataset(client, project_id, thermal_dataset, file_name="ftir_lane.csv", data_type="FTIR")

    compare_put = client.put(
        f"/workspace/{project_id}/compare",
        headers=_headers(),
        json={"analysis_type": "XRD", "selected_datasets": [xrd_key, ftir_key]},
    )
    assert compare_put.status_code == 200
    payload = compare_put.json()["compare_workspace"]
    assert payload["analysis_type"] == "XRD"
    assert payload["selected_datasets"] == [xrd_key]


def test_compare_workspace_rejects_invalid_analysis_type():
    app = create_app(api_token="details-token")
    client = TestClient(app)
    project_id = client.post("/workspace/new", headers=_headers()).json()["project_id"]

    response = client.put(
        f"/workspace/{project_id}/compare",
        headers=_headers(),
        json={"analysis_type": "INVALID"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "analysis_type must be one of:" in detail
    for token in stable_analysis_types():
        assert token in detail


def test_result_literature_compare_endpoint_persists_payload():
    store, project_id, result_id = _seed_xrd_result_store()
    client = TestClient(create_app(api_token="details-token", store=store))

    response = client.post(
        f"/workspace/{project_id}/results/{result_id}/literature/compare",
        headers=_headers(),
        json={
            "persist": True,
            "user_documents": [
                {
                    "document_id": "user_doc_alpha",
                    "title": "User doc alpha",
                    "text": "This user document supports the Phase Alpha qualitative interpretation.",
                    "authors": ["U. Analyst"],
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_id"] == result_id
    assert payload["literature_context"]["mode"] == "metadata_abstract_oa_only"
    assert payload["literature_context"]["provider_scope"] == ["openalex_like_provider"]
    assert payload["literature_context"]["provider_request_ids"]
    assert payload["literature_context"]["query_text"]
    assert payload["literature_context"]["candidate_name"] == "Phase Alpha"
    assert payload["literature_context"]["citation_count"] >= 1
    assert payload["literature_claims"]
    assert payload["literature_comparisons"][0]["candidate_name"] == "Phase Alpha"
    assert payload["literature_comparisons"][0]["validation_posture"] in {"non_validating", "contextual_only", "related_support", "alternative_interpretation"}
    assert payload["detail"]["project_id"] == project_id
    assert payload["detail"]["result"]["id"] == result_id
    assert payload["detail"]["literature_context"]["mode"] == "metadata_abstract_oa_only"
    assert payload["detail"]["citations"][0]["source_license_note"]

    detail = client.get(f"/workspace/{project_id}/results/{result_id}", headers=_headers())
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["literature_context"]["mode"] == "metadata_abstract_oa_only"
    assert detail_payload["literature_claims"]


def test_result_literature_compare_endpoint_persists_safe_context_when_no_real_results_exist(monkeypatch):
    for name in (
        "MATERIALSCOPE_OPENALEX_EMAIL",
        "THERMOANALYZER_OPENALEX_EMAIL",
        "MATERIALSCOPE_OPENALEX_API_KEY",
        "THERMOANALYZER_OPENALEX_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    store, project_id, result_id = _seed_xrd_result_store()
    client = TestClient(create_app(api_token="details-token", store=store))

    response = client.post(
        f"/workspace/{project_id}/results/{result_id}/literature/compare",
        headers=_headers(),
        json={"persist": True, "provider_ids": ["openalex_like_provider"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["detail"] is not None
    assert payload["literature_context"]["provider_scope"] == ["openalex_like_provider"]
    assert payload["literature_context"]["query_text"]
    assert payload["literature_context"]["real_literature_available"] is False
    assert payload["literature_context"]["provider_query_status"] == "not_configured"
    assert payload["literature_context"]["no_results_reason"] == "not_configured"


def test_result_literature_compare_endpoint_defaults_live_provider_for_thermal_results():
    store, project_id, result_id = _seed_thermal_result_store("DSC")
    client = TestClient(create_app(api_token="details-token", store=store))

    response = client.post(
        f"/workspace/{project_id}/results/{result_id}/literature/compare",
        headers=_headers(),
        json={"persist": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["literature_context"]["provider_scope"] == ["openalex_like_provider"]
    assert payload["literature_context"]["analysis_type"] == "DSC"
    assert payload["literature_context"]["query_text"]


def test_result_literature_compare_endpoint_validates_typed_user_documents():
    store, project_id, result_id = _seed_xrd_result_store()
    client = TestClient(create_app(api_token="details-token", store=store))

    response = client.post(
        f"/workspace/{project_id}/results/{result_id}/literature/compare",
        headers=_headers(),
        json={
            "persist": False,
            "user_documents": [
                {
                    "document_id": "bad_user_doc",
                    "title": "Bad user doc",
                    "text": "",
                }
            ],
        },
    )

    assert response.status_code == 422


def test_create_app_uses_injected_literature_provider_registry_for_compare_endpoint():
    store, project_id, result_id = _seed_xrd_result_store()
    registry = {
        "stub_provider": lambda: _BackendStubProvider(
            "stub_provider",
            [
                _lit_source(
                    source_id="stub_support",
                    access_class="open_access_full_text",
                    text="This source supports the Phase Alpha qualitative XRD interpretation.",
                    hint="supports",
                )
            ],
        )
    }
    client = TestClient(
        create_app(
            api_token="details-token",
            store=store,
            literature_provider_registry=registry,
        )
    )

    response = client.post(
        f"/workspace/{project_id}/results/{result_id}/literature/compare",
        headers=_headers(),
        json={"provider_ids": ["stub_provider"], "persist": False},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["literature_context"]["provider_scope"] == ["stub_provider"]
    assert payload["literature_context"]["provider_result_source"] == "stub_search"
    assert payload["literature_context"]["provider_request_ids"]
    assert payload["citations"][0]["provenance"]["provider_id"] == "stub_provider"


def test_result_literature_compare_endpoint_aggregates_multi_provider_results_and_dedupes_citations():
    store, project_id, result_id = _seed_xrd_result_store()
    shared_doi = "10.1000/shared-alpha"
    registry = {
        "stub_a": lambda: _BackendStubProvider(
            "stub_a",
            [
                _lit_source(
                    source_id="shared_alpha_a",
                    access_class="abstract_only",
                    text="This source supports the Phase Alpha qualitative XRD interpretation.",
                    hint="supports",
                    doi=shared_doi,
                    url="https://example.test/shared-a",
                )
            ],
        ),
        "stub_b": lambda: _BackendStubProvider(
            "stub_b",
            [
                _lit_source(
                    source_id="shared_alpha_b",
                    access_class="open_access_full_text",
                    text="This open-access source supports the Phase Alpha qualitative XRD interpretation.",
                    hint="supports",
                    doi=shared_doi,
                    url="https://example.test/shared-b",
                )
            ],
        ),
    }
    client = TestClient(
        create_app(
            api_token="details-token",
            store=store,
            literature_provider_registry=registry,
        )
    )

    response = client.post(
        f"/workspace/{project_id}/results/{result_id}/literature/compare",
        headers=_headers(),
        json={"provider_ids": ["stub_a", "stub_b"], "persist": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["detail"] is not None
    assert payload["detail"]["result"]["id"] == result_id
    assert payload["literature_context"]["provider_scope"] == ["stub_a", "stub_b"]
    assert payload["literature_context"]["provider_result_source"] == "multi_provider_search"
    assert set(payload["literature_context"]["provider_request_ids"]) == set(
        payload["detail"]["literature_context"]["provider_request_ids"]
    )
    assert payload["literature_context"]["source_count"] == 1
    assert payload["literature_context"]["citation_count"] == 1
    assert payload["literature_context"]["accessible_source_count"] == 1
    assert len(payload["citations"]) == 1
    assert set(payload["citations"][0]["provenance"]["provider_scope"]) == {"stub_a", "stub_b"}

    detail = client.get(f"/workspace/{project_id}/results/{result_id}", headers=_headers())
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["literature_context"]["provider_scope"] == ["stub_a", "stub_b"]
    assert detail_payload["literature_context"]["citation_count"] == 1
    assert len(detail_payload["citations"]) == 1
