# ThermoAnalyzer

ThermoAnalyzer is an all-in-one desktop analysis application for thermal and materials characterization data. It combines DSC, TGA, DTA, FTIR, Raman, and XRD workflows with managed cloud library access, reproducible processing, report generation, and project archives inside a single product.

The product is built as a thin client desktop app with a Python analysis/backend layer. End users work inside ThermoAnalyzer rather than switching between vendor tools, library viewers, and separate reporting software.

---

## Product Shape

- Thin client desktop application with bundled/backend-assisted runtime
- Managed cloud-first library access for FTIR, Raman, and XRD
- Limited local fallback cache for degraded operation
- No full provider libraries delivered permanently to the client
- Project-based workflow with reproducible processing context and report outputs

---

## Current Product Surface

### Primary workflows
- Home / data import
- DSC analysis
- TGA analysis
- DTA analysis
- FTIR analysis
- Raman analysis
- XRD analysis
- Compare workspace
- Export and reporting
- Library management
- Project save/load (`.thermozip`)

### Preview workflows
- Kinetics
- Peak deconvolution

---

## Managed Library Architecture

ThermoAnalyzer uses a managed cloud-library model:

- Full library search comes from ThermoAnalyzer cloud endpoints
- Local sync is reserved for small fallback packages only
- `full_provider` local sync remains blocked by default
- Fallback mode is explicitly reduced-capability, not equivalent to cloud full access

### Current provider direction
- FTIR: OpenSpecy
- Raman: OpenSpecy + ROD
- XRD: COD + Materials Project

This keeps the desktop app small while allowing broader qualitative search coverage without distributing raw provider-scale assets to clients.

---

## Key Capabilities

### Import and preprocessing
- CSV, TXT, TSV, XLSX/XLS import
- Automatic delimiter, decimal, header-row, and column-role inference
- Ambiguity-aware import confidence and review prompts
- Manual metadata and column correction when needed
- XRD import contract fields such as axis role, unit, and wavelength handling

### Analysis workflows
- DSC: baseline, peak detection, Tg, enthalpy, sign-aware interpretation
- TGA: DTG, step detection, residue/mass-loss interpretation, class-aware reasoning
- DTA: integrated into the main product surface
- FTIR / Raman: cloud-backed qualitative library search with provider provenance
- XRD: cloud-backed candidate ranking with caution-safe no-match behavior and wavelength-aware matching

### Reporting and traceability
- Compare workspace and batch-oriented evaluation flows
- DOCX, PDF, XLSX, and CSV outputs
- Processing payloads and method context persisted with results
- Validation issues/warnings preserved in exported artifacts
- Provenance fields for timestamps, context, and access-mode/library metadata

### Runtime behavior
- `cloud_full_access`: primary/full library mode
- `limited_cached_fallback`: reduced fallback-only mode
- `not_configured`: no usable cloud or fallback library path

---

## Installation

### Prerequisites
- Python 3.8+
- `pip`

### Setup

```bash
git clone https://github.com/utkuvibing/thermoanalyzer.git
cd thermoanalyzer

python -m venv venv
source venv/bin/activate    # Linux/macOS
venv\Scripts\activate       # Windows

pip install -r requirements.txt
```

---

## Running

### Streamlit UI

```bash
streamlit run app.py
```

Default URL: `http://localhost:8501`

### Backend API

```bash
python -m backend.main
```

Default URL: `http://localhost:8000`

### Local cloud-library dev config

Use the same repo-root `.env` for both Streamlit (`app.py`) and backend (`backend/app.py`).

```dotenv
THERMOANALYZER_LIBRARY_CLOUD_URL=http://127.0.0.1:8000
THERMOANALYZER_LIBRARY_CLOUD_ENABLED=true
THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH=true
THERMOANALYZER_LIBRARY_MIRROR_ROOT=C:\thermoanalyzer\build\reference_library_mirror_live
THERMOANALYZER_LIBRARY_HOSTED_ROOT=C:\thermoanalyzer\build\reference_library_hosted
THERMOANALYZER_LIBRARY_ALLOW_FULL_PROVIDER_SYNC=false
```

`THERMOANALYZER_LIBRARY_ALLOW_FULL_PROVIDER_SYNC=false` preserves the limited-fallback policy and blocks local full-provider sync by default.
`THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH=true` is a dev-only override. It lets the runtime cloud client generate a temporary local trial-style payload when no stored trial or activation exists; production entitlement checks remain strict by default.

### Publishing hosted library data locally

After provider ingest normalization, publish hosted datasets with:

```bash
python tools/publish_hosted_library.py --normalized-root build/reference_library_ingest --output-root build/reference_library_hosted
```

### Local cloud smoke helper

```bash
python tools/library_cloud_smoke.py --base-url http://127.0.0.1:8000
```

Expected local/dev result after `auth/token`, `providers`, and `coverage` succeed:

- `Library Mode = Cloud Full Access`
- `Cloud Access = Enabled`

---

## Recommended Usage Flow

1. Import one or more datasets from Home / Import.
2. Review inferred modality, metadata, and validation prompts.
3. Run the relevant analysis workflow: DSC, TGA, DTA, FTIR, Raman, or XRD.
4. Use Compare Workspace for cross-run review when needed.
5. Export results or generate a report.
6. Save the session as a `.thermozip` project archive.

---

## Project Structure

```text
thermoanalyzer/
├── app.py
├── core/                    # analysis engine, runtime logic, hosted/fallback library handling
├── ui/                      # Streamlit pages/components
├── backend/                 # FastAPI backend and managed cloud-library routes
├── desktop/                 # Electron wrapper and backend bundling assets
├── tools/                   # ingest, mirror, publish, smoke, packaging helpers
├── tests/                   # pytest suite
├── sample_data/             # sample datasets and fallback fixtures
├── packaging/windows/       # local release prep scripts/docs
└── requirements.txt
```

Local Windows release notes:
- [Local Windows Release Prep](packaging/windows/RELEASE_PREP_LOCAL.md)

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
