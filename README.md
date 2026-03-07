# ThermoAnalyzer

**Vendor-independent thermal analysis workbench with a stable DSC/TGA beta workflow and preview-only exploratory modules.**

ThermoAnalyzer is an open-source, browser-based application built with Streamlit that imports, processes, and reports thermal analysis data from exported lab files. The current stable beta scope is DSC, TGA, Compare Workspace, Batch Template Runner, report/export, and project archive workflows. DTA, kinetics, and deconvolution remain preview modules for exploratory evaluation only.

Professor-facing docs:
- [Profesor Kurulum ve Kullanim Kilavuzu](PROFESOR_KURULUM_VE_KULLANIM_KILAVUZU.md)
- [Professor Setup and Usage Guide](PROFESSOR_SETUP_AND_USAGE_GUIDE.md)
- [Professor Beta Guide](PROFESSOR_BETA_GUIDE.md)

---

## Features

### Data Import & Processing
- **Universal file support** -- CSV, TXT, TSV, and Excel files with automatic delimiter, encoding, and column detection
- **Vendor-independent** -- best current support is for generic delimited exports plus common TA / NETZSCH-style text exports
- **Review-aware import** -- ambiguous type, column, unit, and vendor guesses are flagged for review instead of being presented as fully trusted
- **Intelligent column mapping** -- regex- and score-based auto-detection with manual override for temperature, signal, and time columns

### Analysis Modules

| Module | Description |
|---|---|
| **DSC Analysis (Stable Beta)** | Smoothing, mass normalization, baseline correction, peak detection, enthalpy integration, and glass-transition detection inside the current reproducible export/project workflow |
| **TGA Analysis (Stable Beta)** | DTG curve computation, step detection, mass-loss quantification, residue calculation, and explicit unit-mode review context |
| **Compare Workspace + Batch Template Runner (Stable Beta)** | Multi-run overlays and repeatable DSC/TGA template application across compatible datasets |
| **DTA Analysis (Preview)** | Exploratory baseline correction and qualitative thermal-event characterization outside the stable beta promise |
| **Kinetic Analysis (Preview)** | Exploratory Kissinger / OFW / Friedman workflows, not part of the stable commercial beta surface |
| **Peak Deconvolution (Preview)** | Exploratory multi-peak fitting workflow, not part of the stable commercial beta surface |

### Export & Reporting
- **Excel export** -- multi-sheet XLSX workbooks with raw and processed data
- **Word reports** -- styled DOCX documents with formatted tables, embedded figures, and fit reports
- **CSV summaries** -- flat-file export of all numeric results for downstream analysis

### User Interface
- Multi-page navigation with a stable primary workflow and preview modules behind an explicit toggle
- Interactive Plotly charts with scientific axis labeling
- Analysis pipeline history tracker
- Professional dark sidebar theme with corporate styling

---

## Tech Stack

| Category | Technologies |
|---|---|
| **Framework** | Python 3.8+, Streamlit >= 1.39 |
| **Numerical** | NumPy >= 1.24, SciPy >= 1.11, pandas >= 2.0 |
| **Baseline Correction** | pybaselines >= 1.1 |
| **Peak Fitting** | lmfit >= 1.3 |
| **Visualization** | Plotly >= 5.18, Kaleido >= 0.2.1 |
| **Report Generation** | openpyxl >= 3.1, python-docx >= 1.0 |
| **Testing** | pytest >= 7.0 |

---

## Getting Started

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/utkuvibing/thermoanalyzer.git
cd thermoanalyzer

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate    # Linux/macOS
venv\Scripts\activate       # Windows

# Install dependencies
pip install -r requirements.txt
```

### Running the Application

```bash
streamlit run app.py
```

The application will open in your default browser at `http://localhost:8501`.

### Quick Start

1. Navigate to **Import Data** and upload a CSV/Excel file from your thermal analyzer
2. Verify the auto-detected column mapping (temperature, signal, time)
3. Review the import confidence, inferred data type, and signal unit before accepting the run
4. Use **Compare Workspace** and then **DSC** or **TGA** for the stable beta workflow
5. Export results as Excel, Word, or CSV from the **Export & Report** page, or save a `.thermozip` project archive

Sample datasets are included in the `sample_data/` directory for testing:
- `dsc_polymer_melting.csv` -- DSC polymer melting curve
- `dsc_multirate_kissinger.csv` -- Multi-rate DSC data for Kissinger kinetic analysis
- `tga_calcium_oxalate.csv` -- TGA decomposition of calcium oxalate monohydrate

---

## Standards Compliance

ThermoAnalyzer follows established thermal analysis standards and committee recommendations:

| Standard | Scope |
|---|---|
| **ASTM E967** | DSC temperature and enthalpy calibration using reference materials (In, Sn, Zn) |
| **ASTM E1131** | Compositional analysis by thermogravimetry (CaC2O4-H2O reference) |
| **ASTM E1356** | Assignment of glass transition temperatures by DSC |
| **ICTAC Kinetics Committee** | Recommendations for performing kinetic computations on thermal analysis data |

Built-in reference data includes DSC melting-point calibration standards and TGA decomposition standards for instrument validation.

---

## Project Structure

```
thermoanalyzer/
├── app.py                  # Streamlit entry point and navigation
├── core/                   # Analysis engine (no UI dependencies)
│   ├── baseline.py         # Baseline correction algorithms
│   ├── data_io.py          # File parsing and export
│   ├── dsc_processor.py    # DSC analysis pipeline
│   ├── tga_processor.py    # TGA analysis pipeline
│   ├── dta_processor.py    # DTA analysis pipeline
│   ├── kinetics.py         # Kissinger, OFW, Friedman methods
│   ├── peak_analysis.py    # Peak detection and characterization
│   ├── peak_deconvolution.py # Multi-peak fitting with lmfit
│   ├── preprocessing.py    # Smoothing, differentiation, normalization
│   └── report_generator.py # DOCX and CSV report generation
├── ui/                     # Streamlit UI pages and components
│   ├── home.py             # Data upload and column mapping
│   ├── dsc_page.py         # DSC analysis interface
│   ├── tga_page.py         # TGA analysis interface
│   ├── dta_page.py         # DTA analysis interface
│   ├── kinetics_page.py    # Kinetic analysis interface
│   ├── deconvolution_page.py # Peak deconvolution interface
│   ├── export_page.py      # Export and report generation
│   └── components/         # Reusable UI components
├── utils/                  # Constants, reference data, validators
├── tests/                  # pytest test suite
├── sample_data/            # Example thermal analysis datasets
└── requirements.txt        # Python dependencies
```

---

## Citation

If you use ThermoAnalyzer in your research, please cite:

```bibtex
@software{thermoanalyzer,
  title   = {ThermoAnalyzer},
  version = {1.0},
  year    = {2025},
  url     = {https://github.com/utkuvibing/thermoanalyzer},
  note    = {Open-source thermal analysis suite}
}
```

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
