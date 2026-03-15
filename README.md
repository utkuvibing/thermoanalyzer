# ThermoAnalyzer

ThermoAnalyzer is a vendor-independent thermal analysis workbench focused on reproducible DSC/TGA workflows, scientific reporting, and project-level traceability.

The application is built with Streamlit and a Python analysis core. It supports import from common lab export formats, structured processing pipelines, comparison workspaces, and publication-style reporting outputs.

---

## Current Scope

### Stable beta workflow
- DSC analysis (baseline, peaks, Tg, enthalpy)
- TGA analysis (DTG, step detection, mass-loss/residue, unit interpretation)
- Compare Workspace + Batch Template Runner for DSC/TGA
- Export and reporting (DOCX, PDF, XLSX, CSV summary)
- Project save/load (`.thermozip`)

### Preview workflow (exploratory)
- DTA
- Kinetics (Kissinger / OFW / Friedman)
- Peak deconvolution

Preview modules are available for exploration but are outside the stable beta promise.

---

## Key Features

### Data import and preprocessing
- CSV, TXT, TSV, XLSX/XLS import
- Automatic delimiter, decimal, header-row, and column role inference
- Ambiguity-aware import confidence and review prompts
- Manual column/metadata correction when needed

### Scientific analysis engine
- DSC: event extraction, Tg detection, sign-aware interpretation
- TGA: DTG-resolved event structure, dominant/minor event logic, residue-aware interpretation
- Class-aware TGA reasoning with stoichiometric mass-balance checks when formula clues are available
- Chemistry-specific interpretation paths when evidence is strong (for example hydrate dehydration or carbonate decarbonation product interpretation)
- Confidence gating with metadata/fit/validation constraints to avoid overclaiming

### Comparison and reporting
- Cross-run comparison tables and narrative synthesis
- Chemistry-aware comparison wording (residue is not treated as a naive "less decomposition" proxy)
- Record-level figure routing:
  - sample sections prefer sample-linked figures
  - comparison figures are isolated to comparison sections
- Scientific report sections:
  - methodology and equations
  - primary interpretation and evidence map
  - uncertainty and methodological limits
  - class-aware recommended follow-up experiments

### Traceability and reproducibility
- Processing payloads and method context persisted with results
- Validation status/issues/warnings included in outputs
- Provenance fields (timestamps, hashes, app/process context) included in technical appendix

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

### Optional backend API (if needed in your workflow)

```bash
python -m backend.main
```

Default URL: `http://localhost:8000`

### Local cloud-library dev config (M005)

Use the same repo-root `.env` for both Streamlit (`app.py`) and backend (`backend/app.py`).
Cloud is the primary library path; mirror/feed sync is only for limited fallback cache.

```dotenv
THERMOANALYZER_LIBRARY_CLOUD_URL=http://127.0.0.1:8000
THERMOANALYZER_LIBRARY_CLOUD_ENABLED=true
THERMOANALYZER_LIBRARY_MIRROR_ROOT=C:\thermoanalyzer\build\reference_library_mirror_live
THERMOANALYZER_LIBRARY_ALLOW_FULL_PROVIDER_SYNC=false
```

`THERMOANALYZER_LIBRARY_ALLOW_FULL_PROVIDER_SYNC=false` keeps full-provider local sync blocked by default.

Local dev smoke helper:

```bash
python tools/library_cloud_smoke.py --base-url http://127.0.0.1:8000
```

---

## Recommended Usage Flow (Stable Path)

1. Import dataset(s) from **Home / Import**.
2. Review auto-detected columns, inferred analysis type, and metadata.
3. Run **DSC** or **TGA** (stable modules).
4. Use **Compare Workspace** for cross-run evaluation.
5. (Optional) apply batch templates for repeatable multi-run processing.
6. Export results and generate reports from **Export & Report**.
7. Save the session as a project archive (`.thermozip`) for reproducibility.

---

## Reporting Outputs

- **DOCX**: full scientific narrative with figures and appendix
- **PDF**: publication-style narrative/table export (requires ReportLab)
- **XLSX**: results summary + detailed sheets
- **CSV summary**: normalized flat contract for downstream processing

Report narrative includes class-aware TGA claims, evidence-linked confidence context, and follow-up experiment recommendations tailored to inferred behavior.

---

## Standards and References

ThermoAnalyzer aligns with common thermal analysis conventions and reference workflows, including:
- ASTM E967 (DSC calibration context)
- ASTM E1131 (TGA compositional decomposition context)
- ASTM E1356 (DSC Tg assignment context)
- ICTAC kinetics guidance (preview kinetics workflows)

---

## Project Structure

```text
thermoanalyzer/
├── app.py
├── core/                    # analysis and scientific reasoning engine
├── ui/                      # Streamlit pages/components
├── backend/                 # optional FastAPI backend surface
├── desktop/                 # Electron wrapper and backend bundling assets
├── tests/                   # pytest suite
├── sample_data/             # sample datasets
├── packaging/windows/       # local release prep scripts/docs
└── requirements.txt
```

Local Windows release notes:
- [Local Windows Release Prep](packaging/windows/RELEASE_PREP_LOCAL.md)

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
