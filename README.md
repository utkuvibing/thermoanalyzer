# MaterialScope

MaterialScope is a desktop analysis platform for thermal and broader materials characterization workflows. It brings DSC, TGA, DTA, FTIR, Raman, and XRD into one product with reproducible processing, managed cloud-backed library search, publication-grade reporting, and project archives.

The product is designed so users stay inside MaterialScope instead of switching between vendor software, spreadsheet cleanup, library viewers, and separate reporting tools.

The current primary application surface is a Dash + Plotly UI mounted into FastAPI (`python -m dash_app.server`). The Streamlit entrypoint remains available as a legacy/transition path during migration.

### Version (current release line)

| Item | Value |
|------|--------|
| **MaterialScope application version** | `2.0` (see `utils/license_manager.APP_VERSION`) |
| **Bundled FastAPI / backend API version** | `0.1.0` (see `backend.BACKEND_API_VERSION`; exposed on `/version` and health endpoints) |
| **Active development branch** | `web-dash-plotly-migration` (Dash + Plotly migration and backend integration) |

Use these when reporting bugs, support tickets, or export diagnostics. The API version tracks the HTTP surface; the application version tracks the product build users see in licensing and support workflows.

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
- Project save/load with `.scopezip` (legacy `.thermozip` still imports)

### Preview workflows

- Kinetics
- Peak deconvolution

---

## Product Direction

- Dash + Plotly frontend mounted on FastAPI as the primary app stack
- Thin-client desktop application with an Electron wrapper and Python backend
- Streamlit retained as a legacy/transition surface while modality migration completes
- Cloud-first library access for FTIR, Raman, and XRD
- Limited local fallback cache for degraded operation
- No full provider-scale libraries shipped permanently to the client
- Reproducible result records with processing, validation, provenance, and report context preserved

---

## Dash migration status (latest)

- Dash + Plotly is the **default** surface for stable modalities; migration continues modality-by-modality to keep verification explicit.
- **DTA** — Phase 4 polish: quality and raw-metadata cards, expandable processing summary, preset flow, keyboard shortcuts.
- **DSC** — Full Dash analysis surface aligned with DTA patterns: literature compare, figure capture for reports, export-oriented figure registration with diagnostics (`report_figure_status` / export warnings when figures are missing).
- Streamlit remains supported for legacy flows until remaining surfaces reach parity.

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
- DTA: Dash Phase 4 polish shipped (quality + raw metadata cards, expandable processing summary, keyboard shortcuts, and preset-to-run tab flow)
- FTIR and Raman: cloud-backed qualitative library search with provider provenance
- XRD: qualitative phase screening with cloud-backed candidate ranking, scientific naming, reference dossiers, and caution-safe no-match handling

### Reporting and traceability

- DOCX, PDF, XLSX, and CSV outputs
- Compact report-style main body with appendix-level technical evidence
- Scientific reasoning sections by modality
- Publication-grade figures for UI and export; server-side snapshot figures aligned with processed thermal axes
- Report-primary figure keys, optional **Figure export notes** when PNGs are missing, and per-result capture status for troubleshooting
- Preserved validation warnings, processing context, and provenance metadata

### Project workflow

- Compare workspace for cross-run review
- Batch-oriented stable analysis flows
- Session persistence plus `.scopezip` project archives (legacy `.thermozip` import supported)

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
git clone https://github.com/utkuvibing/MaterialScope-web-dash-plotly-migration.git
cd MaterialScope-web-dash-plotly-migration

python -m venv venv
source venv/bin/activate    # Linux/macOS
venv\Scripts\activate       # Windows

pip install -r requirements.txt
```

---

## Running

### Dash + FastAPI (Primary)

```bash
python -m dash_app.server
```

Default URL: `http://127.0.0.1:8050`

Optional run flags:

```bash
python -m dash_app.server --host 0.0.0.0 --port 8050 --token <api-token>
```

This starts a combined FastAPI app with Dash mounted at `/` and backend routes served from the same process.

### Backend API (standalone)

```bash
python -m backend.main
```

Default URL: `http://localhost:8000`

### Streamlit UI (Legacy / Transition)

```bash
streamlit run app.py
```

Default URL: `http://localhost:8501`

For local development, start the backend before using Streamlit workflows that require `cloud_full_access`.

### Docker / Coolify deployment

This repo includes a production `Dockerfile` for Coolify-style deployments.

The current container profile starts:

- the FastAPI backend on `127.0.0.1:8000`
- the Streamlit UI (legacy path) on `0.0.0.0:8501`
- Streamlit waits for backend health before the UI process starts

Dash-first container startup is a forward-looking follow-up as migration hardens.

For web deployment:

- deploy with `Dockerfile`
- expose port `8501`
- set runtime secrets in Coolify instead of committing `.env`

Recommended runtime environment variables:

```dotenv
MATERIALSCOPE_LIBRARY_CLOUD_URL=http://127.0.0.1:8000
MATERIALSCOPE_LIBRARY_CLOUD_ENABLED=true
MATERIALSCOPE_LIBRARY_ALLOW_FULL_PROVIDER_SYNC=false
MATERIALSCOPE_ENABLE_PREVIEW_MODULES=false
MATERIALSCOPE_OPENALEX_EMAIL=
MATERIALSCOPE_OPENALEX_API_KEY=
# Optional: when live OpenAlex is not configured, also search bundled demo fixtures (dev/demo only).
# MATERIALSCOPE_LITERATURE_FIXTURE_FALLBACK=1
```

Live literature compare (DSC, DTA, TGA, FTIR, XRD) uses the OpenAlex-backed provider by default. Set at least `MATERIALSCOPE_OPENALEX_EMAIL` (OpenAlex polite-pool `mailto`) or `MATERIALSCOPE_OPENALEX_API_KEY` so the backend can run real metadata queries. Without that, the API reports `provider_query_status=not_configured` unless `MATERIALSCOPE_LITERATURE_FIXTURE_FALLBACK=1` is enabled to merge the local fixture catalog.

Set `MATERIALSCOPE_ENABLE_PREVIEW_MODULES=true` only in builds where kinetics and deconvolution should be exposed.

Optional runtime tuning:

```dotenv
BACKEND_STARTUP_TIMEOUT_SECONDS=30
```

---

## Local Cloud-Library Development

Use the same repo-root `.env` for Dash (`dash_app/server.py`), Streamlit (`app.py`), and backend (`backend/app.py`).

```dotenv
MATERIALSCOPE_LIBRARY_CLOUD_URL=http://127.0.0.1:8000
MATERIALSCOPE_LIBRARY_CLOUD_ENABLED=true
MATERIALSCOPE_LIBRARY_DEV_CLOUD_AUTH=true
MATERIALSCOPE_LIBRARY_MIRROR_ROOT=C:\materialscope\build\reference_library_mirror_live
MATERIALSCOPE_LIBRARY_HOSTED_ROOT=C:\materialscope\build\reference_library_hosted
MATERIALSCOPE_LIBRARY_ALLOW_FULL_PROVIDER_SYNC=false
```

Notes:

- `MATERIALSCOPE_LIBRARY_ALLOW_FULL_PROVIDER_SYNC=false` preserves the limited-fallback policy.
- `MATERIALSCOPE_LIBRARY_DEV_CLOUD_AUTH=true` is a dev-only shortcut for local cloud testing.
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
6. Save the session as a `.scopezip` project archive.

---

## Repository Layout

```text
MaterialScope/
├── app.py                    # Streamlit legacy entrypoint
├── dash_app/                 # primary Dash + Plotly frontend and combined server
├── core/                    # analysis engine, scientific/report logic, library handling
├── ui/                      # Streamlit pages/components kept during migration
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

## Forward-looking work (Dash-first)

- Continue modality parity and polish (remaining surfaces and deployment defaults where Dash is not yet primary).
- Reuse the shared Dash result-surface patterns (quality cards, raw metadata, processing summaries, literature compare, figure capture) across modalities.
- Converge desktop and container runtimes toward Dash-first defaults; Streamlit remains until parity is complete.
- Expand managed cloud-library provider coverage and provenance quality.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.