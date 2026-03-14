# Phase 1 Research: Foundation Contracts and Execution Path

## Standard Stack
- Keep the current runtime stack for Phase 1: `FastAPI` + `Pydantic` in `backend/`, `numpy/pandas/scipy` in `core/`, `Streamlit` in `ui/`, Electron shell in `desktop/`.
- Add no new external dependencies for Phase 1. Use standard library typing (`Protocol`, `TypedDict`, `dataclass`) for contracts and registry.
- Reuse existing core building blocks instead of replacing them:
  - Processing payload normalization: `core/processing_schema.py`.
  - Validation: `core/validation.py`.
  - Result record format: `core/result_serialization.py`.
  - Provenance: `core/provenance.py`.
  - Existing DSC/TGA execution kernel: `core/batch_runner.py`.

Practical dependency risks:
- `backend/app.py` hard-codes `DSC/TGA` checks in `/analysis/run` and `/workspace/{id}/batch/run`; generic handling must move to registry lookups without breaking API response shape.
- `backend/detail.py` and workspace defaults still assume `comparison_workspace.analysis_type` is `DSC` or `TGA`.
- `core/project_io.py` persists `dsc_state_*` and `tga_state_*`; changing this too early will break archive compatibility.
- `core/report_generator.py` has explicit `DSC/TGA` branches for comparison and context sections; Phase 1 should not rewrite reporting logic, only prepare extension hooks.

ARCH coverage in this stack choice:
- `ARCH-01`: contract + registry are implementable without changing math kernels.
- `ARCH-02`: DSC/TGA behavior can stay byte-level compatible by wrapping existing runners.
- `ARCH-04`: run/batch API generic handling can be driven by registry metadata instead of hard-coded type checks.

## Architecture Patterns
1. Registry-first, explicit modality catalog.
- Create a central registry module (for example `core/modalities/registry.py`) with explicit entries.
- Do not use dynamic plugin discovery in Phase 1.
- Registry entry must include:
  - `analysis_type`
  - `stability` (`stable` or `experimental`)
  - `default_workflow_template_id`
  - dataset eligibility function
  - execution adapter
  - serializer/report capability flags

2. Thin contract layer over existing processors.
- Define a strict modality execution contract with the lifecycle required by ARCH-01:
  - `import` (already fulfilled for thermal types by `read_thermal_data`)
  - `preprocess`
  - `analyze`
  - `serialize`
  - `report_context`
- For Phase 1, implement DSC/TGA adapters that internally call existing `execute_batch_template` path so behavior is preserved.

3. Generic backend execution service.
- Introduce an execution service (`core/execution_engine.py`) that accepts `analysis_type` and dispatches via registry.
- Replace direct `if analysis_type in {"DSC", "TGA"}` checks in backend endpoints with:
  - `modality = registry.require_stable(analysis_type)`
  - `eligibility = modality.is_dataset_eligible(dataset)`
  - `outcome = modality.run(...)`
- Keep existing response DTOs unchanged.

4. Compatibility-preserving state strategy.
- Keep current state keys (`dsc_state_*`, `tga_state_*`) in Phase 1.
- Add a helper mapping: `state_key_for(analysis_type, dataset_key)`.
- This allows new modalities later without archive-breaking changes now.

5. Single-source execution logic.
- Streamlit compare-page batch and backend API batch currently share `execute_batch_template` but still duplicate orchestration logic.
- Move orchestration into reusable service function first, then call it from both UI and backend.

ARCH mapping:
- `ARCH-01`: achieved by contract + registry + standardized lifecycle hooks.
- `ARCH-02`: achieved by adapter pattern that preserves existing DSC/TGA kernels.
- `ARCH-04`: achieved by backend service dispatch based on analysis type registry metadata.

## Don't Hand-Roll
- Do not hand-roll a new processing schema system. Extend `ensure_processing_payload` and `get_workflow_templates`.
- Do not rewrite DSC/TGA processor math (`DSCProcessor`, `TGAProcessor`). Wrap them.
- Do not create a second result-record format. Use `make_result_record` and existing serializers.
- Do not implement dynamic plugin loading from filesystem in Phase 1.
- Do not fork validation logic by endpoint. Keep `validate_thermal_dataset` as the shared path and add modality-specific validators behind the contract when needed.
- Do not change project archive layout in Phase 1; keep current `analysis_states` compatibility.

## Common Pitfalls
- Behavior regression by changing default templates:
  - current defaults are hard-coded (`dsc.general` / `tga.general`) in backend and batch paths.
- Hidden eligibility regressions:
  - DSC currently accepts dataset types `DSC`, `DTA`, `UNKNOWN`; TGA accepts `TGA`, `UNKNOWN`.
- Archive incompatibility:
  - changing `dsc_state_*` / `tga_state_*` storage without migration logic will break load/save roundtrip.
- UI/backend drift:
  - Electron and Streamlit still present DSC/TGA-centric controls; backend generic support alone will not expose new stable modalities.
- Report coupling:
  - report comparison helpers include TGA/DSC-specific sections and assumptions.
- False confidence from passing tests:
  - current tests are strong for DSC/TGA paths but do not yet enforce a registry contract API.
- Runtime warning noise:
  - `DSCProcessor.normalize()` warns when sample mass is missing; this can pollute batch/test logs if not handled.

## Validation Architecture
Use a layered strategy with requirement gates.

1. Contract-level tests (new).
- Verify every stable registry entry implements the same hook surface.
- Verify `analysis_type` lookup, default template, and state-key mapping.
- Gate: ARCH-01.

2. DSC/TGA parity tests (must-have).
- Golden parity for single run and batch run before/after refactor:
  - `execution_status`
  - `result_id`
  - `processing.workflow_template_id`
  - `summary` and `rows`
  - `validation.status`
- Gate: ARCH-02.

3. Backend API generic-dispatch tests.
- `/analysis/run` and `/workspace/{id}/batch/run` must dispatch from registry.
- Stable modality accepted, unsupported modality rejected with explicit validation error (not fallthrough).
- Compare workspace update should validate against registry stable set, not fixed DSC/TGA literal.
- Gate: ARCH-04.

4. Persistence compatibility tests.
- Save/load roundtrip for old and new project state still restores:
  - `comparison_workspace`
  - existing DSC/TGA analysis states
  - result summaries and report/export preparation.
- Gate: ARCH-02.

5. Smoke integration tests.
- Existing focused suite baseline command:
  - `pytest -q tests/test_backend_api.py tests/test_backend_batch.py tests/test_batch_runner.py tests/test_processing_schema.py`
  - Current baseline in this repo: pass (19 passed), with known DSC normalize warning.

Definition of done for Phase 1 testing:
- ARCH-01/02/04 each has at least one explicit automated gate.
- Existing DSC/TGA snapshot outputs remain stable.
- Backend run/batch no longer contains DSC/TGA-only dispatch branches.

## Code Examples
```python
# core/modalities/contracts.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol

class ModalityAdapter(Protocol):
    analysis_type: str
    stable: bool
    default_workflow_template_id: str

    def is_dataset_eligible(self, dataset_type: str) -> bool: ...

    def run(
        self,
        *,
        dataset_key: str,
        dataset: Any,
        workflow_template_id: str,
        existing_processing: dict[str, Any] | None,
        analysis_history: list[dict[str, Any]] | None,
        analyst_name: str | None,
        app_version: str | None,
        batch_run_id: str | None,
    ) -> dict[str, Any]: ...

@dataclass(frozen=True)
class ModalitySpec:
    analysis_type: str
    stable: bool
    default_workflow_template_id: str
    adapter: ModalityAdapter
```

```python
# core/modalities/registry.py
from core.modalities.adapters import DSCAdapter, TGAAdapter

REGISTRY = {
    "DSC": DSCAdapter(),
    "TGA": TGAAdapter(),
}

def require_stable_modality(analysis_type: str):
    token = str(analysis_type or "").upper()
    modality = REGISTRY.get(token)
    if modality is None or not modality.stable:
        raise ValueError(f"Unsupported stable analysis_type: {token}")
    return modality
```

```python
# backend/app.py (target shape)
analysis_type = request.analysis_type.upper()
modality = require_stable_modality(analysis_type)

if not modality.is_dataset_eligible(dataset_type):
    raise HTTPException(status_code=400, detail=f"Dataset '{request.dataset_key}' is not eligible for {analysis_type} analysis.")

workflow_template_id = request.workflow_template_id or modality.default_workflow_template_id
outcome = modality.run(
    dataset_key=request.dataset_key,
    dataset=dataset,
    workflow_template_id=workflow_template_id,
    existing_processing=existing_state.get("processing"),
    analysis_history=state.get("analysis_history", []),
    analyst_name=((state.get("branding") or {}).get("analyst_name") or ""),
    app_version=APP_VERSION,
    batch_run_id=f"desktop_single_{uuid.uuid4().hex[:8]}",
)
```

## Recommendation
Implement Phase 1 in four controlled passes.

1. Pass A: Introduce modality contract + static registry + DSC/TGA adapters only.
- No endpoint behavior changes yet.
- Add contract tests.

2. Pass B: Switch backend `/analysis/run` and `/batch/run` dispatch to registry.
- Keep response payloads and saved state keys unchanged.
- Add explicit unsupported-modality validation errors.

3. Pass C: Replace DSC/TGA literals in compare workspace validation with registry-stable set.
- Preserve default behavior (`DSC`) when legacy state has no value.

4. Pass D: Lock regression and compatibility.
- Add DSC/TGA parity tests and archive roundtrip checks.
- Run focused backend/core suite as a release gate.

This sequence satisfies ARCH-01 first (contract), preserves ARCH-02 continuously (adapter parity), and delivers ARCH-04 safely (generic backend execution path) without destabilizing current production DSC/TGA behavior.
