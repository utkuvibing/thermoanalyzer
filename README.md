# MaterialScope

MaterialScope is a desktop analysis platform for thermal and broader materials characterization workflows. It brings DSC, TGA, DTA, FTIR, Raman, and XRD into one product with reproducible processing, managed cloud-backed library search, publication-grade reporting, and project archives.

The product is designed so users stay inside MaterialScope instead of switching between vendor software, spreadsheet cleanup, library viewers, and separate reporting tools.

---

## What MaterialScope Covers

### Stable workflows
- DSC
- TGA
- DTA
- FTIR
- Raman
- XRD
- Compare workspace
- Report/export center
- Project save/load with `.thermozip`

### Preview workflows
- Kinetics
- Peak deconvolution

---

## Product Direction

- Thin-client desktop application with a Python analysis and backend layer
- Cloud-first library access for FTIR, Raman, and XRD
- Limited local fallback cache for degraded operation
- No full provider-scale libraries shipped permanently to the client
- Reproducible result records with processing, validation, provenance, and report context preserved

---

## Core Capabilities

### Import and preprocessing
- CSV, TXT, TSV, XLSX, and XLS import
- Automatic delimiter, decimal, header-row, and column-role inference
- Ambiguity-aware import confidence and review prompts
- Manual correction for metadata and column mapping when needed
- XRD-specific import handling for axis role, unit, and wavelength provenance

### Analysis workflows
- DSC: baseline correction, peak detection, Tg handling, enthalpy, sign-aware interpretation
- TGA: DTG, step detection, residue and mass-loss interpretation, class-aware reasoning
- DTA: stable report/export path aligned with the main product surface
- FTIR and Raman: cloud-backed qualitative library search with provider provenance
- XRD: qualitative phase screening with cloud-backed candidate ranking, scientific naming, reference dossiers, and caution-safe no-match handling

### Reporting and traceability
- DOCX, PDF, XLSX, and CSV outputs
- Compact report-style main body with appendix-level technical evidence
- Scientific reasoning sections by modality
- Publication-grade figures for UI and export
- Figure snapshots and report-primary figure selection
- Preserved validation warnings, processing context, and provenance metadata

### Project workflow
- Compare workspace for cross-run review
- Batch-oriented stable analysis flows
- Session persistence plus `.thermozip` project archives

---

## Managed Library Model

MaterialScope uses a managed cloud-library architecture:

- full library search comes from MaterialScope cloud endpoints
- local sync is reserved for small fallback packages only
- `full_provider` local sync is blocked by default
- fallback mode is explicitly reduced-capability and not equivalent to cloud full access

### Current provider direction
- FTIR: OpenSpecy
- Raman: OpenSpecy + ROD
- XRD: COD + Materials Project

This keeps the desktop footprint small while still allowing broader qualitative search coverage and provider-backed provenance.

---

## XRD Notes

XRD is handled as qualitative phase screening, not definitive phase confirmation.

- cloud-backed ranked candidates
- scientific display naming and formula rendering
- reference-dossier appendix support in reports
- explicit caution-safe `no_match` and low-confidence behavior
- wavelength and provenance gaps surfaced in summaries and reports

`cloud_full_access` means the cloud path is active. It does not suppress coverage-quality warnings when hosted XRD coverage is still limited.

---

## Runtime Modes

- `cloud_full_access`: primary managed-library mode
- `limited_cached_fallback`: reduced fallback-only mode
- `not_configured`: no usable cloud or fallback path

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

For local development, start the backend before using library-backed workflows if you expect `cloud_full_access`.

### Docker / Coolify deployment

This repo includes a production `Dockerfile` for Coolify-style deployments.

The container starts:
- the FastAPI backend on `127.0.0.1:8000`
- the Streamlit UI on `0.0.0.0:8501`

For web deployment:
- deploy with `Dockerfile`
- expose port `8501`
- set runtime secrets in Coolify instead of committing `.env`

Recommended runtime environment variables:

```dotenv
THERMOANALYZER_LIBRARY_CLOUD_URL=http://127.0.0.1:8000
THERMOANALYZER_LIBRARY_CLOUD_ENABLED=true
THERMOANALYZER_LIBRARY_ALLOW_FULL_PROVIDER_SYNC=false
MATERIALSCOPE_OPENALEX_EMAIL=
MATERIALSCOPE_OPENALEX_API_KEY=
```

---

## Local Cloud-Library Development

Use the same repo-root `.env` for both Streamlit (`app.py`) and the backend (`backend/app.py`).

```dotenv
THERMOANALYZER_LIBRARY_CLOUD_URL=http://127.0.0.1:8000
THERMOANALYZER_LIBRARY_CLOUD_ENABLED=true
THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH=true
THERMOANALYZER_LIBRARY_MIRROR_ROOT=C:\thermoanalyzer\build\reference_library_mirror_live
THERMOANALYZER_LIBRARY_HOSTED_ROOT=C:\thermoanalyzer\build\reference_library_hosted
THERMOANALYZER_LIBRARY_ALLOW_FULL_PROVIDER_SYNC=false
```

Notes:
- `THERMOANALYZER_LIBRARY_ALLOW_FULL_PROVIDER_SYNC=false` preserves the limited-fallback policy.
- `THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH=true` is a dev-only shortcut for local cloud testing.
- hosted XRD coverage warnings remain visible even when the cloud path is healthy.

### Publish hosted library data locally

```bash
python tools/publish_hosted_library.py --output-root build/reference_library_hosted
```

### Local cloud smoke test

```bash
python tools/library_cloud_smoke.py --base-url http://127.0.0.1:8000
```

Expected local/dev result:
- `Library Mode = Cloud Full Access`
- `Cloud Access = Enabled`

---

## Recommended Usage Flow

1. Import one or more datasets from Home / Import.
2. Review inferred modality, metadata, and validation prompts.
3. Run the relevant workflow: DSC, TGA, DTA, FTIR, Raman, or XRD.
4. Use Compare Workspace for cross-run review when needed.
5. Export results or generate a report.
6. Save the session as a `.thermozip` project archive.

---

## Repository Layout

```text
thermoanalyzer/
├── app.py
├── core/                    # analysis engine, scientific/report logic, library handling
├── ui/                      # Streamlit pages and shared UI components
├── backend/                 # FastAPI backend and managed cloud-library routes
├── desktop/                 # desktop wrapper and bundling assets
├── tools/                   # ingest, publish, smoke, packaging helpers
├── tests/                   # pytest suite
├── sample_data/             # sample datasets and library fixtures
├── packaging/windows/       # local Windows release prep scripts/docs
└── requirements.txt
```

Local Windows release notes:
- [Local Windows Release Prep](packaging/windows/RELEASE_PREP_LOCAL.md)

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
