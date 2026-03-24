"""
data_io.py
==========
Data import/export engine for thermal and spectral analysis datasets.

Pure Python + NumPy + pandas -- no Streamlit dependency.

Public API
----------
ThermalDataset          - standardised container for one measurement run
detect_file_format()    - auto-detect delimiter, encoding, header row, etc.
guess_columns()         - regex-based column-role assignment
read_thermal_data()     - main entry point: file / buffer -> ThermalDataset
export_results_csv()    - write analysis results dict to CSV
export_data_xlsx()      - write one or more datasets to an Excel workbook
"""

from __future__ import annotations

import copy
import csv
import hashlib
import io
import logging
import os
import re
import shlex
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, IO, List, Optional, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum number of lines to inspect when sniffing file format
_SNIFF_LINES = 50

# Candidate encodings tried in order
_ENCODINGS = ("utf-8", "utf-8-sig", "latin-1", "cp1252")

# Candidate delimiters passed to csv.Sniffer (space handled separately)
_DELIMITERS = ",\t; "

# Regex patterns for column-role detection
_PATTERNS: Dict[str, List[str]] = {
    "temperature": [
        r"[Tt]emp",
        r"[Ss]\u0131cak",   # Turkish: sıcak(lık)
        r"\u00b0[CcKk]",    # °C / °K
        r"[Cc]elsius",
        r"[Kk]elvin",
        r"[Ww]avenumber",
        r"[Rr]aman\s*[Ss]hift",
        r"2\s*theta",
        r"2\u03b8",
        r"[Tt]wo\s*theta",
        r"[Aa]ngle",
        r"\bcm[-\^]?\s*1\b",
        r"\b1/cm\b",
        r"^T\b",
        r"^T_",
    ],
    "time": [
        r"[Tt]ime",
        r"[Zz]aman",        # Turkish
        r"\bmin\b",
        r"\bsec\b",
        r"\bs\b",
        r"^t\b",
        r"^t_",
    ],
    "signal_dsc": [
        r"[Hh]eat\s*[Ff]low",
        r"\bDSC\b",
        r"[Mm][Ww]",
        r"[Ee]ndo",
        r"[Ee]xo",
        r"[Hh]eat\s*[Cc]ap",
        r"Cp\b",
    ],
    "signal_tga": [
        r"[Mm]ass",
        r"[Ww]eight",
        r"\bTG(?!A)\b",
        r"mg$",
        r"%$",
        r"\bTGA\b",
        r"[Ww]t\.?\s*%",
    ],
    "signal_dta": [
        r"\bDTA\b",
        r"[Dd]elta\s*T",
        r"\u00b5[Vv]",      # µV
        r"\u0394T",         # ΔT
    ],
    "signal_ftir": [
        r"\bFTIR\b",
        r"[Aa]bsorb",
        r"[Tt]ransmitt",
        r"[Rr]eflect",
        r"%\s*T\b",
    ],
    "signal_raman": [
        r"\bRAMAN\b",
        r"[Ii]ntensity",
        r"\bCPS\b",
        r"[Cc]ounts?",
        r"[Rr]aman",
    ],
    "signal_xrd": [
        r"\bXRD\b",
        r"[Dd]iffract",
        r"2\s*theta",
        r"2\u03b8",
        r"[Aa]ngle",
    ],
}

_IMPORT_CONFIDENCE_ORDER = {"high": 3, "medium": 2, "review": 1}
_ANALYSIS_TYPE_KEYS = ("DSC", "TGA", "DTA", "FTIR", "RAMAN", "XRD")
_TYPE_PATTERN_KEYS = {
    "DSC": "signal_dsc",
    "TGA": "signal_tga",
    "DTA": "signal_dta",
    "FTIR": "signal_ftir",
    "RAMAN": "signal_raman",
    "XRD": "signal_xrd",
}
_SPECTRAL_ANALYSIS_TYPES = {"FTIR", "RAMAN"}
_XRD_SOURCE_HINTS = ("xrd", "diffract", "2theta", "2_theta", "zenodo_xrd")
_VENDOR_TOKEN_SETS = {
    "NETZSCH": (
        "netzsch",
        "proteus",
        "sta 449",
        "sta449",
        "sta 2500",
        "temp./°c",
        "dsc/(mw",
        "tg/%",
        "dtg/(%/",
    ),
    "TA": (
        "ta instruments",
        "trios",
        "q20",
        "q200",
        "q50",
        "q500",
        "temperature (°c)",
        "heat flow (",
        "weight (%)",
        "derivative weight",
    ),
    "METTLER": (
        "mettler",
        "star e",
        "stare",
        "toledo",
    ),
}
_JCAMP_EXTENSIONS = (".jdx", ".dx", ".jcamp", ".dxj")
_JCAMP_UNSUPPORTED_TAGS = {"NTUPLES", "VAR_NAME", "SYMBOL", "CLASS", "XYPOINTS", "PEAK TABLE"}
_JCAMP_XUNIT_MAP = {
    "1/CM": "cm^-1",
    "CM-1": "cm^-1",
    "CM^-1": "cm^-1",
    "CM**-1": "cm^-1",
    "1/CM ": "cm^-1",
}
_XRD_MEASURED_EXTENSIONS = (".xy", ".dat")
_XRD_CIF_EXTENSIONS = (".cif",)
_XRD_SUPPORTED_AXIS_TAGS = ("_pd_meas_2theta_scan", "_pd_proc_2theta_corrected")
_XRD_SUPPORTED_INTENSITY_TAGS = (
    "_pd_meas_intensity_total",
    "_pd_proc_intensity_total",
    "_pd_meas_counts_total",
)
_XRD_WAVELENGTH_TAGS = ("_diffrn_radiation_wavelength", "_pd_meas_wavelength")
_XRD_UNSUPPORTED_CIF_HINTS = ("_atom_site_", "_symmetry_space_group", "_cell_length_")

# ---------------------------------------------------------------------------
# ThermalDataset
# ---------------------------------------------------------------------------


@dataclass
class ThermalDataset:
    """Container for one thermal analysis measurement run.

    Attributes
    ----------
    data : pd.DataFrame
        Standardised DataFrame with columns:
        - 'temperature'  (always present, numeric, in °C or K)
        - 'signal'       (always present, numeric)
        - 'time'         (optional, numeric)
        Additional original columns are preserved with their original names.
    metadata : dict
        Arbitrary key/value pairs such as sample_name, sample_mass,
        heating_rate, instrument, date, etc.
    data_type : str
        One of 'DSC', 'TGA', 'DTA', or 'unknown'.
    units : dict
        Expected keys: 'temperature', 'signal', 'time' (optional).
        Example: {'temperature': '°C', 'signal': 'mW/mg', 'time': 'min'}
    original_columns : dict
        Mapping from standard role names to the original column names found
        in the source file, e.g. {'temperature': 'Temp/°C', 'signal': 'DSC/(mW/mg)'}.
    file_path : str
        Path to the source file (empty string when loaded from a buffer).
    """

    data: pd.DataFrame
    metadata: dict
    data_type: str
    units: dict
    original_columns: dict
    file_path: str = ""

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def copy(self) -> "ThermalDataset":
        """Return a deep copy of this dataset."""
        return ThermalDataset(
            data=self.data.copy(deep=True),
            metadata=copy.deepcopy(self.metadata),
            data_type=self.data_type,
            units=copy.deepcopy(self.units),
            original_columns=copy.deepcopy(self.original_columns),
            file_path=self.file_path,
        )

    def __repr__(self) -> str:  # pragma: no cover
        n = len(self.data)
        name = self.metadata.get("sample_name", "unnamed")
        return (
            f"ThermalDataset(type={self.data_type!r}, sample={name!r}, "
            f"rows={n}, file={os.path.basename(self.file_path)!r})"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_readable_buffer(
    source: Union[str, Path, IO, object],
) -> tuple[io.StringIO, str]:
    """Return a (StringIO, source_name) pair from any supported source type.

    Accepted source types
    ---------------------
    - str / pathlib.Path  : opened from the filesystem
    - io.BytesIO          : decoded using _try_encodings
    - io.StringIO         : used directly
    - UploadedFile-like   : objects with a .read() method (Streamlit, etc.)
    """
    source_name = ""

    # --- filesystem path ---
    if isinstance(source, (str, Path)):
        source_name = str(source)
        raw = Path(source).read_bytes()
        text, _ = _try_encodings(raw)
        return io.StringIO(text), source_name

    # --- already a StringIO ---
    if isinstance(source, io.StringIO):
        source_name = getattr(source, "name", "")
        source.seek(0)
        return source, source_name

    # --- BytesIO or file-like with .read() ---
    if hasattr(source, "read"):
        # Preserve the name attribute if present (UploadedFile has .name)
        source_name = getattr(source, "name", "")
        if hasattr(source, "seek"):
            source.seek(0)
        raw = source.read()
        if isinstance(raw, str):
            return io.StringIO(raw), source_name
        text, _ = _try_encodings(raw)
        return io.StringIO(text), source_name

    raise TypeError(
        f"Unsupported source type: {type(source)}. "
        "Expected a file path, io.StringIO, io.BytesIO, or file-like object."
    )


def _try_encodings(raw_bytes: bytes) -> tuple[str, str]:
    """Try to decode *raw_bytes* using the candidate encodings.

    Returns (decoded_text, encoding_used).
    Raises UnicodeDecodeError if none succeed.
    """
    for enc in _ENCODINGS:
        try:
            return raw_bytes.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    # Last resort: replace unmappable characters
    text = raw_bytes.decode("utf-8", errors="replace")
    logger.warning("Could not cleanly decode file; unknown characters replaced.")
    return text, "utf-8 (with replacements)"


def _read_first_n_lines(buffer: io.StringIO, n: int = _SNIFF_LINES) -> str:
    """Read up to *n* lines from *buffer* and rewind it."""
    lines = []
    for _ in range(n):
        line = buffer.readline()
        if not line:
            break
        lines.append(line)
    buffer.seek(0)
    return "".join(lines)


def _is_mostly_numeric(series: pd.Series, threshold: float = 0.6) -> bool:
    """Return True if >= threshold fraction of non-null values are numeric."""
    if series.empty:
        return False
    coerced = pd.to_numeric(series, errors="coerce")
    valid = coerced.notna().sum()
    total = series.notna().sum()
    return bool(total > 0 and (valid / total) >= threshold)


def _detect_decimal_sep(sample: str) -> str:
    """Guess whether decimal separator is '.' or ',' from a text sample."""
    # Count occurrences of patterns like "3,14" vs "3.14"
    comma_decimal = len(re.findall(r"\d,\d", sample))
    dot_decimal = len(re.findall(r"\d\.\d", sample))
    return "," if comma_decimal > dot_decimal else "."


def _count_pattern_hits(text: str, patterns: List[str]) -> int:
    return sum(1 for pat in patterns if re.search(pat, text))


def _is_mostly_monotonic_increasing(series: pd.Series, threshold: float = 0.9) -> bool:
    """Return True when numeric values are predominantly monotonic increasing."""
    coerced = pd.to_numeric(series, errors="coerce").dropna()
    if len(coerced) < 3:
        return False
    diffs = np.diff(coerced.to_numpy(dtype=float))
    positive = float(np.mean(diffs > 0))
    return positive >= threshold


def _raw_unit_token(col_name: str) -> str:
    match = _UNIT_RE.search(str(col_name))
    return match.group(1).strip() if match else ""


def _classify_import_confidence(*levels: str) -> str:
    if not levels:
        return "review"
    if any(level == "review" for level in levels):
        return "review"
    if any(level == "medium" for level in levels):
        return "medium"
    return "high"


def _is_spectral_axis_hint(column_name: str | None) -> bool:
    token = str(column_name or "").strip().lower()
    if not token:
        return False
    return any(
        hint in token
        for hint in (
            "wavenumber",
            "wave number",
            "raman shift",
            "shift (cm",
            "cm-1",
            "cm^-1",
            "1/cm",
        )
    )


def _is_xrd_axis_hint(column_name: str | None) -> bool:
    token = str(column_name or "").strip().lower()
    if not token:
        return False
    return any(
        hint in token
        for hint in (
            "2theta",
            "2 theta",
            "2θ",
            "theta",
            "two theta",
            "angle",
            "diffract",
            "xrd",
        )
    )


def _xrd_source_hint_score(source_name: str | None) -> int:
    token = str(source_name or "").strip().lower()
    if not token:
        return 0
    score = 0
    if "xrd" in token:
        score += 10
    for hint in _XRD_SOURCE_HINTS:
        if hint in token and hint != "xrd":
            score += 4
    if token.endswith((".xy", ".dat", ".cif")):
        score += 4
    return score


def _looks_like_jcamp(source_name: str, text: str) -> bool:
    source_lower = str(source_name or "").lower()
    if source_lower.endswith(_JCAMP_EXTENSIONS):
        return True
    sample = (text or "")[:3000].upper()
    return "##TITLE=" in sample and ("##XYDATA=" in sample or "##PEAK TABLE=" in sample)


def _parse_jcamp_numeric_tokens(line: str) -> list[float]:
    raw = re.findall(r"[-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?", line)
    values: list[float] = []
    for token in raw:
        try:
            values.append(float(token))
        except ValueError:
            continue
    return values


def _parse_jcamp_dataset(
    text: str,
    *,
    source_name: str,
    data_type: str | None = None,
    metadata: dict | None = None,
) -> ThermalDataset:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        raise ValueError("JCAMP-DX source is empty.")

    tags: dict[str, str] = {}
    xydata_seen = 0
    tag_pattern = re.compile(r"^##([^=]+)=(.*)$")
    for line in lines:
        match = tag_pattern.match(line)
        if not match:
            continue
        key = match.group(1).strip().upper()
        value = match.group(2).strip()
        tags.setdefault(key, value)
        if key == "XYDATA":
            xydata_seen += 1

    blocks_value = str(tags.get("BLOCKS") or "").strip()
    if blocks_value and blocks_value not in {"", "1"}:
        raise ValueError(
            "JCAMP-DX MVP supports single-spectrum files only; linked/multi-block JCAMP variants are unsupported."
        )

    unsupported = [key for key in tags if key in _JCAMP_UNSUPPORTED_TAGS and key != "PEAK TABLE"]
    if unsupported:
        raise ValueError(
            "JCAMP-DX MVP supports only single-spectrum ##XYDATA core files; advanced constructs "
            f"({', '.join(sorted(set(unsupported)))}) are unsupported."
        )
    if "PEAK TABLE" in tags:
        raise ValueError("JCAMP-DX peak-table imports are outside MVP scope; provide single-spectrum ##XYDATA data.")
    if xydata_seen != 1:
        raise ValueError(
            "JCAMP-DX MVP supports exactly one ##XYDATA block per file; linked or multi-spectrum files are unsupported."
        )

    xydata_index = next((idx for idx, line in enumerate(lines) if line.upper().startswith("##XYDATA=")), -1)
    if xydata_index < 0:
        raise ValueError("JCAMP-DX import requires a ##XYDATA section for MVP support.")

    data_lines: list[str] = []
    for line in lines[xydata_index + 1 :]:
        if line.upper().startswith("##"):
            break
        data_lines.append(line)
    if not data_lines:
        raise ValueError("JCAMP-DX ##XYDATA section did not contain numeric data.")

    delta_x: float | None = None
    try:
        if tags.get("DELTAX") not in (None, ""):
            delta_x = float(str(tags.get("DELTAX")))
    except ValueError:
        delta_x = None

    x_values: list[float] = []
    y_values: list[float] = []
    for line in data_lines:
        values = _parse_jcamp_numeric_tokens(line)
        if len(values) < 2:
            continue
        if len(values) == 2:
            x_values.append(values[0])
            y_values.append(values[1])
            continue

        if len(values) % 2 == 0 and delta_x is None:
            for index in range(0, len(values), 2):
                x_values.append(values[index])
                y_values.append(values[index + 1])
            continue

        if delta_x is None:
            raise ValueError(
                "JCAMP-DX compressed XYDATA without DELTAX is unsupported in MVP; provide pairwise XY rows."
            )
        start_x = values[0]
        for index, y_value in enumerate(values[1:]):
            x_values.append(start_x + (delta_x * index))
            y_values.append(y_value)

    if len(x_values) < 2 or len(y_values) < 2:
        raise ValueError("JCAMP-DX import could not extract a usable single spectrum.")

    out_df = pd.DataFrame({"temperature": x_values, "signal": y_values})
    out_df.dropna(subset=["temperature", "signal"], inplace=True)
    out_df.reset_index(drop=True, inplace=True)
    if out_df.empty:
        raise ValueError("JCAMP-DX spectrum contains no valid numeric points.")

    resolved_type = str(data_type or "").upper().strip()
    inferred_type = "RAMAN" if "RAMAN" in (str(tags.get("TITLE") or "") + " " + str(tags.get("DATATYPE") or "")).upper() else "FTIR"
    if resolved_type not in {"FTIR", "RAMAN"}:
        resolved_type = inferred_type

    x_unit_raw = str(tags.get("XUNITS") or "1/CM").strip().upper()
    x_unit = _JCAMP_XUNIT_MAP.get(x_unit_raw, "cm^-1")
    y_unit_raw = str(tags.get("YUNITS") or "").strip().lower()
    if "abs" in y_unit_raw:
        y_unit = "absorbance"
    elif "trans" in y_unit_raw:
        y_unit = "transmittance"
    elif "count" in y_unit_raw or "cps" in y_unit_raw:
        y_unit = "counts"
    else:
        y_unit = "a.u."

    import_warnings: list[str] = []
    if "RAMAN" not in resolved_type and "RAMAN" in inferred_type:
        import_warnings.append("JCAMP title metadata suggested RAMAN while FTIR was selected; review modality selection.")

    metadata = metadata or {}
    display_name = metadata.get("display_name") or os.path.basename(source_name) or metadata.get("sample_name", "")
    payload_meta = {
        "sample_name": metadata.get("sample_name", ""),
        "sample_mass": metadata.get("sample_mass", None),
        "heating_rate": metadata.get("heating_rate", None),
        "instrument": metadata.get("instrument", ""),
        "vendor": metadata.get("vendor", "Generic"),
        "display_name": display_name,
        "source_data_hash": _hash_dataframe(out_df),
        "import_method": "auto",
        "import_confidence": "medium",
        "import_review_required": bool(import_warnings),
        "import_warnings": import_warnings,
        "inferred_analysis_type": inferred_type,
        "inferred_signal_unit": y_unit,
        "inferred_vendor": "Generic",
        "vendor_detection_confidence": "review",
        "modality_confirmation_required": inferred_type != resolved_type,
        "modality_confirmation_applied": bool(data_type and inferred_type != resolved_type),
        "import_format": "jcamp_dx",
        "import_delimiter": "jcamp",
        "import_decimal_sep": ".",
        "import_header_row": 0,
        "import_data_start_row": max(xydata_index + 1, 0),
        "spectral_axis_role": "wavenumber",
        "spectral_axis_column": "JCAMP_X",
        "jcamp_title": str(tags.get("TITLE") or ""),
        "jcamp_xunits": x_unit_raw or "1/CM",
        "jcamp_yunits": str(tags.get("YUNITS") or ""),
    }
    payload_meta.update(metadata)

    return ThermalDataset(
        data=out_df,
        metadata=payload_meta,
        data_type=resolved_type,
        units={"temperature": x_unit, "signal": y_unit},
        original_columns={"temperature": "JCAMP_X", "signal": "JCAMP_Y"},
        file_path=source_name,
    )


# ---------------------------------------------------------------------------
# 2. detect_file_format
# ---------------------------------------------------------------------------


def detect_file_format(
    file_path_or_buffer: Union[str, Path, IO, object],
) -> dict:
    """Auto-detect format parameters from the first *_SNIFF_LINES* lines.

    Parameters
    ----------
    file_path_or_buffer : str, Path, BytesIO, StringIO, or file-like object

    Returns
    -------
    dict with keys:
        delimiter       str   e.g. ',', '\\t', ';', ' '
        header_row      int   0-based row index of the column-name row
        data_start_row  int   0-based row index where numeric data begins
        encoding        str   detected or assumed encoding
        decimal_sep     str   '.' or ','
        is_xlsx         bool  True when source appears to be an Excel file
    """
    # --- XLSX fast-path ---
    is_xlsx = False
    source_name = ""
    if isinstance(source := file_path_or_buffer, (str, Path)):
        source_name = str(source)
        if source_name.lower().endswith((".xlsx", ".xls")):
            return {
                "delimiter": None,
                "header_row": 0,
                "data_start_row": 1,
                "encoding": None,
                "decimal_sep": ".",
                "is_xlsx": True,
            }

    # Check for Excel-like bytes magic number
    raw_peek = b""
    if hasattr(file_path_or_buffer, "read"):
        raw_peek = file_path_or_buffer.read(8)
        file_path_or_buffer.seek(0)
        # XLSX: PK\x03\x04 (ZIP); XLS: \xd0\xcf\x11\xe0
        if raw_peek[:4] in (b"PK\x03\x04", b"\xd0\xcf\x11\xe0"):
            is_xlsx = True
            return {
                "delimiter": None,
                "header_row": 0,
                "data_start_row": 1,
                "encoding": None,
                "decimal_sep": ".",
                "is_xlsx": True,
            }

    # --- text-based detection ---
    try:
        string_buf, source_name = _to_readable_buffer(file_path_or_buffer)
    except Exception as exc:
        raise ValueError(f"Cannot read source for format detection: {exc}") from exc

    sample_text = _read_first_n_lines(string_buf, _SNIFF_LINES)
    if not sample_text.strip():
        raise ValueError("Source appears to be empty.")

    # Encoding (already resolved inside _to_readable_buffer; report best guess)
    encoding = "utf-8"
    if isinstance(file_path_or_buffer, (str, Path)):
        raw_bytes = Path(file_path_or_buffer).read_bytes()
        _, encoding = _try_encodings(raw_bytes)

    # Decimal separator
    decimal_sep = _detect_decimal_sep(sample_text)

    # Delimiter via csv.Sniffer
    delimiter = _sniff_delimiter(sample_text)

    # Header row and data_start_row
    header_row, data_start_row = _find_header_and_data_rows(
        sample_text, delimiter, decimal_sep
    )

    return {
        "delimiter": delimiter,
        "header_row": header_row,
        "data_start_row": data_start_row,
        "encoding": encoding,
        "decimal_sep": decimal_sep,
        "is_xlsx": False,
    }


def _sniff_delimiter(sample_text: str) -> str:
    """Use csv.Sniffer to determine the field delimiter."""
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample_text, delimiters=_DELIMITERS)
        return dialect.delimiter
    except csv.Error:
        pass

    # Manual fallback: count occurrences per line and pick the most consistent
    lines = [ln for ln in sample_text.splitlines() if ln.strip()][:20]
    counts: Dict[str, List[int]] = {d: [] for d in (",", "\t", ";", " ")}
    for line in lines:
        for d in counts:
            counts[d].append(line.count(d))

    best_delim = ","
    best_score = -1.0
    for d, cnts in counts.items():
        if not cnts or max(cnts) == 0:
            continue
        mean = float(np.mean(cnts))
        std = float(np.std(cnts))
        # Prefer delimiter with high mean and low variance
        score = mean - std
        if score > best_score:
            best_score = score
            best_delim = d

    return best_delim


def _find_header_and_data_rows(
    sample_text: str, delimiter: str, decimal_sep: str
) -> tuple[int, int]:
    """Return (header_row, data_start_row) as 0-based indices."""
    lines = sample_text.splitlines()
    header_row = 0
    data_start_row = 1

    # Normalise decimal separators for numeric tests
    def _parse_numeric(val: str) -> bool:
        v = val.strip()
        if decimal_sep == ",":
            v = v.replace(",", ".", 1)
        try:
            float(v)
            return True
        except ValueError:
            return False

    for i, line in enumerate(lines):
        if not line.strip():
            continue
        parts = line.split(delimiter) if delimiter != " " else line.split()
        if not parts:
            continue

        numeric_count = sum(_parse_numeric(p) for p in parts)
        total = len(parts)

        # If less than half the fields are numeric, treat as a header row
        if total > 0 and numeric_count / total < 0.5:
            header_row = i
        else:
            # First predominantly numeric row is where data starts
            data_start_row = i
            break
    else:
        # All lines appear non-numeric — keep defaults
        pass

    # Ensure data_start_row > header_row
    if data_start_row <= header_row:
        data_start_row = header_row + 1

    return header_row, data_start_row


# ---------------------------------------------------------------------------
# 3. guess_columns
# ---------------------------------------------------------------------------


def guess_columns(df: pd.DataFrame, source_name: str | None = None) -> dict:
    """Guess the role of each column using regex pattern matching.

    Parameters
    ----------
    df : pd.DataFrame
        Raw DataFrame whose column names have been stripped of whitespace.

    Returns
    -------
    dict with keys:
        'temperature'  str or None  - column name
        'time'         str or None  - column name
        'signal'       str or None  - column name
        'data_type'    str          - 'DSC', 'TGA', 'DTA', 'FTIR', 'RAMAN', 'XRD', or 'unknown'
    """
    cols = list(df.columns)
    numeric_cols = {col for col in cols if _is_mostly_numeric(df[col])}
    result: Dict[str, Optional[str] | dict | list] = {
        "temperature": None,
        "time": None,
        "signal": None,
        "data_type": "unknown",
        "warnings": [],
        "confidence": {},
        "candidates": {},
        "inferred_signal_unit": "unknown",
        "inferred_analysis_type": "unknown",
    }
    warnings_list: list[str] = []
    confidence: dict[str, str] = {}

    def _rank_role(pattern_key: str, *, prefer_monotonic: bool = False) -> list[dict[str, object]]:
        ranked: list[dict[str, object]] = []
        for col in cols:
            score = 0
            pattern_hits = _count_pattern_hits(col, _PATTERNS[pattern_key])
            if pattern_hits:
                score += 10 + pattern_hits * 2
            header_lower = str(col).lower()
            if pattern_key == "temperature" and any(token in header_lower for token in ("°c", "degc", "celsius", "kelvin", "°k")):
                score += 8
            if pattern_key == "time" and any(token in header_lower for token in ("time", "min", "sec", "hour", "hours")):
                score += 8
            if col in numeric_cols:
                score += 2
            if prefer_monotonic and col in numeric_cols and _is_mostly_monotonic_increasing(df[col]):
                score += 4
            ranked.append({"column": col, "score": score, "pattern_hits": pattern_hits})
        ranked.sort(key=lambda item: (int(item["score"]), str(item["column"])), reverse=True)
        return ranked

    xrd_source_bonus = _xrd_source_hint_score(source_name)

    temp_ranked = _rank_role("temperature", prefer_monotonic=True)
    time_ranked = _rank_role("time", prefer_monotonic=True)
    result["candidates"]["temperature"] = temp_ranked[:3]
    result["candidates"]["time"] = time_ranked[:3]

    if temp_ranked and (int(temp_ranked[0]["pattern_hits"]) > 0 or int(temp_ranked[0]["score"]) >= 10):
        result["temperature"] = str(temp_ranked[0]["column"])
        confidence["temperature"] = "high"
        if len(temp_ranked) > 1 and int(temp_ranked[1]["score"]) >= int(temp_ranked[0]["score"]) - 1 and int(temp_ranked[1]["score"]) > 0:
            confidence["temperature"] = "medium"
            warnings_list.append(
                f"Temperature-column inference is close between '{temp_ranked[0]['column']}' and '{temp_ranked[1]['column']}'."
            )
    else:
        for col in cols:
            signal_like = any(
                _count_pattern_hits(col, _PATTERNS[key]) > 0
                for key in ("signal_dsc", "signal_tga", "signal_dta", "signal_ftir", "signal_raman", "signal_xrd")
            )
            signal_like = signal_like or bool(
                re.search(
                    r"signal|heat|weight|mass|dsc|tga|dta|ftir|raman|xrd|diffract|intensity|absorb|transmitt",
                    str(col),
                    flags=re.IGNORECASE,
                )
            )
            if col in numeric_cols and not signal_like:
                result["temperature"] = col
                confidence["temperature"] = "review"
                warnings_list.append(
                    f"Temperature column was inferred by numeric fallback as '{col}'; verify the column mapping."
                )
                break
        else:
            confidence["temperature"] = "review"

    if time_ranked and (int(time_ranked[0]["pattern_hits"]) > 0 or int(time_ranked[0]["score"]) >= 10) and str(time_ranked[0]["column"]) != result["temperature"]:
        result["time"] = str(time_ranked[0]["column"])
        confidence["time"] = "high"
        if len(time_ranked) > 1 and int(time_ranked[1]["score"]) >= int(time_ranked[0]["score"]) - 1 and int(time_ranked[1]["score"]) > 0:
            confidence["time"] = "medium"
    else:
        confidence["time"] = "review" if any(int(item["score"]) > 0 for item in time_ranked) else "medium"

    assigned = {result["temperature"], result["time"]}
    signal_candidates: dict[str, list[dict[str, object]]] = {analysis_type: [] for analysis_type in _ANALYSIS_TYPE_KEYS}
    for analysis_type in _ANALYSIS_TYPE_KEYS:
        pattern_key = _TYPE_PATTERN_KEYS[analysis_type]
        for col in cols:
            if col in assigned:
                continue
            score = 0
            pattern_hits = _count_pattern_hits(col, _PATTERNS[pattern_key])
            if pattern_hits:
                score += 10 + pattern_hits * 2
            signal_unit = _extract_unit(col, "signal")
            if analysis_type == "DSC" and signal_unit in {"mW", "mW/mg", "W/g"}:
                score += 4
            if analysis_type == "TGA" and signal_unit in {"%", "mg"}:
                score += 4
            if analysis_type == "DTA" and signal_unit in {"µV", "mV"}:
                score += 4
            if analysis_type == "FTIR" and signal_unit in {"absorbance", "transmittance", "%T", "a.u."}:
                score += 4
            if analysis_type == "RAMAN" and signal_unit in {"counts", "cps", "a.u."}:
                score += 4
            if analysis_type == "XRD":
                if signal_unit in {"counts", "cps", "intensity"}:
                    score += 2
                elif signal_unit == "a.u.":
                    score += 1
            col_token = str(col).lower()
            if analysis_type == "FTIR" and any(token in col_token for token in ("ftir", "absorb", "transmitt", "reflect")):
                score += 3
            if analysis_type == "RAMAN" and any(token in col_token for token in ("raman", "intensity", "counts", "cps")):
                score += 3
            if analysis_type == "RAMAN" and _is_xrd_axis_hint(str(result.get("temperature") or "")):
                score -= 6
            if analysis_type == "XRD":
                if any(token in col_token for token in ("xrd", "diffract", "2theta", "2θ", "angle")):
                    score += 4
                if any(token in col_token for token in ("intensity", "counts", "cps")):
                    score += 1
                if "raman" in col_token:
                    score -= 4
                if _is_xrd_axis_hint(str(result.get("temperature") or "")):
                    score += 2
            if col in numeric_cols and score > 0:
                score += 2
            signal_candidates[analysis_type].append(
                {
                    "column": col,
                    "score": score,
                    "pattern_hits": pattern_hits,
                    "signal_unit": signal_unit,
                }
            )
        signal_candidates[analysis_type].sort(
            key=lambda item: (int(item["score"]), str(item["column"])),
            reverse=True,
        )
        result["candidates"][analysis_type.lower()] = signal_candidates[analysis_type][:3]

    type_scores = []
    for analysis_type, ranked in signal_candidates.items():
        if ranked:
            top = ranked[0]
            score = int(top["score"])
            if analysis_type == "XRD":
                score += xrd_source_bonus
                if _is_xrd_axis_hint(str(result.get("temperature") or "")):
                    score += 12
            type_scores.append((analysis_type, score, str(top["column"]), str(top["signal_unit"])))
    type_scores.sort(key=lambda item: (item[1], item[0]), reverse=True)

    if type_scores and type_scores[0][1] > 0:
        best_type, best_score, best_col, best_unit = type_scores[0]
        ambiguous_type = False
        ambiguity_margin = 4
        if best_type == "XRD" and (
            _is_xrd_axis_hint(str(result.get("temperature") or "")) or xrd_source_bonus >= 8
        ):
            ambiguity_margin = 1
        if len(type_scores) > 1 and (type_scores[1][1] >= best_score - ambiguity_margin and type_scores[1][1] > 0):
            ambiguous_type = True
            warnings_list.append(
                f"Analysis-type inference is ambiguous between {best_type} and {type_scores[1][0]}; review the selected signal column."
            )
            if {best_type, type_scores[1][0]} == _SPECTRAL_ANALYSIS_TYPES:
                warnings_list.append(
                    "Spectral modality inference is low-confidence between FTIR and RAMAN; confirm modality before stable analysis."
                )
        result["signal"] = best_col
        result["inferred_signal_unit"] = best_unit or "unknown"
        result["inferred_analysis_type"] = "unknown" if ambiguous_type else best_type
        result["data_type"] = result["inferred_analysis_type"]
        confidence["signal"] = "medium" if ambiguous_type else "high"
        confidence["data_type"] = "review" if ambiguous_type else "high"
        if ambiguous_type:
            warnings_list.append("Analysis type remains unknown after import heuristics; review the selected signal column.")
    else:
        fallback_signal = None
        for col in cols:
            if col not in assigned and col in numeric_cols:
                fallback_signal = col
                break
        result["signal"] = fallback_signal
        result["data_type"] = "unknown"
        result["inferred_analysis_type"] = "unknown"
        result["inferred_signal_unit"] = _extract_unit(fallback_signal, "signal") if fallback_signal else "unknown"
        confidence["signal"] = "review"
        confidence["data_type"] = "review"
        if fallback_signal is not None:
            warnings_list.append(
                f"Signal column was inferred by numeric fallback as '{fallback_signal}'; analysis type remains unknown."
            )

    if result["signal"]:
        signal_unit = _extract_unit(str(result["signal"]), "signal")
        result["inferred_signal_unit"] = signal_unit or "unknown"
        inferred_type = str(result["data_type"]).upper()
        if inferred_type == "TGA" and signal_unit not in {"%", "mg"}:
            warnings_list.append(
                f"TGA signal unit could not be confirmed from column '{result['signal']}'; review whether the signal is % or absolute mass."
            )
            confidence["signal"] = "review"
        elif inferred_type == "DSC" and signal_unit in {"a.u.", "unknown"}:
            warnings_list.append(
                f"DSC signal unit could not be confirmed from column '{result['signal']}'; verify whether the signal is mW, mW/mg, or W/g."
            )
            confidence["signal"] = "medium"
        elif inferred_type == "FTIR" and signal_unit not in {"absorbance", "transmittance", "%T", "a.u."}:
            warnings_list.append(
                f"FTIR signal unit could not be confirmed from column '{result['signal']}'; review whether the signal is absorbance or transmittance."
            )
            confidence["signal"] = "review"
        elif inferred_type == "RAMAN" and signal_unit not in {"counts", "cps", "a.u."}:
            warnings_list.append(
                f"Raman signal unit could not be confirmed from column '{result['signal']}'; review whether the signal represents counts/intensity."
            )
            confidence["signal"] = "review"
        elif inferred_type == "XRD" and signal_unit not in {"counts", "cps", "a.u.", "intensity"}:
            warnings_list.append(
                f"XRD signal unit could not be confirmed from column '{result['signal']}'; review whether the signal represents counts/intensity."
            )
            confidence["signal"] = "review"
        elif inferred_type == "unknown":
            warnings_list.append("Analysis type remains unresolved after import heuristics; review the file before stable analysis.")

    inferred_type = str(result["data_type"]).upper()
    if inferred_type in _SPECTRAL_ANALYSIS_TYPES and not _is_spectral_axis_hint(str(result.get("temperature") or "")):
        warnings_list.append(
            f"Spectral axis column '{result.get('temperature')}' is not explicitly labeled as wavenumber/shift; default to wavenumber-first and review mapping."
        )
        confidence["temperature"] = "review"
    if inferred_type == "XRD" and not _is_xrd_axis_hint(str(result.get("temperature") or "")):
        warnings_list.append(
            f"XRD axis column '{result.get('temperature')}' is not explicitly labeled as 2theta/angle; review mapping before stable analysis."
        )
        confidence["temperature"] = "review"

    result["warnings"] = warnings_list
    result["confidence"] = {
        "temperature": confidence.get("temperature", "review"),
        "time": confidence.get("time", "review"),
        "signal": confidence.get("signal", "review"),
        "data_type": confidence.get("data_type", "review"),
        "overall": _classify_import_confidence(
            confidence.get("temperature", "review"),
            confidence.get("signal", "review"),
            confidence.get("data_type", "review"),
        ),
    }
    return result


# ---------------------------------------------------------------------------
# Internal: unit extraction from column name
# ---------------------------------------------------------------------------

_UNIT_RE = re.compile(
    r"\(?([°%a-zA-Z0-9\u00b0\u00b5/\^\-]+(?:\.[a-zA-Z]+)?)\)?$"
)

_TEMP_UNIT_MAP = {
    "c": "°C", "°c": "°C", "celsius": "°C",
    "k": "K",  "°k": "K", "kelvin": "K",
    "f": "°F", "°f": "°F", "fahrenheit": "°F",
    "cm-1": "cm^-1", "cm^-1": "cm^-1", "1/cm": "cm^-1", "cm−1": "cm^-1",
}

_SIGNAL_UNIT_KEYWORDS = {
    "mw/mg": "mW/mg", "mw": "mW",
    "µv": "µV", "uv": "µV",
    "%": "%", "mg": "mg",
    "w/g": "W/g",
    "absorbance": "absorbance",
    "transmittance": "transmittance",
    "%t": "%T",
    "counts": "counts",
    "cps": "cps",
    "intensity": "a.u.",
}

_TIME_UNIT_MAP = {"min": "min", "s": "s", "sec": "s", "h": "h"}


def detect_vendor_info(source_name: str = "", columns: list[str] | None = None) -> dict[str, object]:
    """Return vendor inference details for common thermal-analysis exports."""
    source_name = (source_name or "").lower()
    column_text = " ".join(str(col).lower() for col in (columns or []))
    combined = f"{source_name} {column_text}"

    scores: dict[str, tuple[int, list[str]]] = {}
    for vendor, tokens in _VENDOR_TOKEN_SETS.items():
        matched = [token for token in tokens if token in combined]
        score = 0
        for token in matched:
            score += 3 if token in source_name else 2
        scores[vendor] = (score, matched)

    ranked = sorted(scores.items(), key=lambda item: (item[1][0], item[0]), reverse=True)
    warnings_list: list[str] = []
    if not ranked or ranked[0][1][0] <= 0:
        warnings_list.append("Vendor detection remained generic; confirm the export source if vendor-specific conventions matter.")
        return {
            "vendor": "Generic",
            "confidence": "review",
            "warnings": warnings_list,
            "matched_tokens": [],
        }

    best_vendor, (best_score, matched_tokens) = ranked[0]
    confidence = "high" if best_score >= 4 else "medium"
    if len(ranked) > 1 and ranked[1][1][0] >= best_score - 1 and ranked[1][1][0] > 0:
        warnings_list.append(
            f"Vendor inference is close between {best_vendor} and {ranked[1][0]}; review the source file naming and column headers."
        )
        confidence = "review"
    elif confidence == "medium":
        warnings_list.append(
            f"Vendor '{best_vendor}' was inferred from limited header/file-name evidence; review before relying on vendor conventions."
        )

    return {
        "vendor": best_vendor,
        "confidence": confidence,
        "warnings": warnings_list,
        "matched_tokens": matched_tokens,
    }


def detect_vendor(source_name: str = "", columns: list[str] | None = None) -> str:
    """Heuristically classify common vendor exports."""
    return str(detect_vendor_info(source_name=source_name, columns=columns).get("vendor", "Generic"))


def _extract_unit(col_name: str, role: str) -> str:
    """Try to extract a unit string from a column name like 'Temp/°C'."""
    col_name = str(col_name)
    m = _UNIT_RE.search(col_name)
    unit_str = m.group(1).strip() if m else ""
    unit_lower = unit_str.lower()

    if role == "temperature":
        return _TEMP_UNIT_MAP.get(unit_lower, "°C")
    if role == "signal":
        for key, val in _SIGNAL_UNIT_KEYWORDS.items():
            if key in unit_lower:
                return val
        normalized_col = col_name.strip().lower()
        if unit_lower == normalized_col or re.fullmatch(r"[a-zA-Z\s]+", unit_str or ""):
            return "a.u."
        return unit_str or "a.u."
    if role == "time":
        return _TIME_UNIT_MAP.get(unit_lower, "s")
    return unit_str


def _hash_dataframe(df: pd.DataFrame) -> str:
    """Return a stable content hash for a standardized dataset DataFrame."""
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


# ---------------------------------------------------------------------------
# 4. read_thermal_data
# ---------------------------------------------------------------------------


def read_thermal_data(
    source: Union[str, Path, IO, object],
    column_mapping: Optional[Dict[str, str]] = None,
    data_type: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> ThermalDataset:
    """Load a thermal analysis file and return a standardised ThermalDataset.

    Parameters
    ----------
    source : str, Path, BytesIO, StringIO, or file-like
        The data source.  For Streamlit UploadedFile objects, just pass the
        object directly -- it exposes a .read() / .seek() interface.
    column_mapping : dict, optional
        Override automatic column detection.  Keys are standard role names
        ('temperature', 'signal', 'time') and values are the actual column
        names in the source file.
        Example: {'temperature': 'Temp/°C', 'signal': 'DSC/(mW/mg)'}
    data_type : str, optional
        Override automatic data-type detection. One of
        'DSC', 'TGA', 'DTA', 'FTIR', 'RAMAN', 'XRD'.
    metadata : dict, optional
        Extra metadata to merge into the dataset's metadata dict.

    Returns
    -------
    ThermalDataset
    """
    metadata = metadata or {}
    source_name = ""

    # ------------------------------------------------------------------
    # JCAMP-DX fast path (single-spectrum MVP only)
    # ------------------------------------------------------------------
    readable_buf, source_name = _to_readable_buffer(source)
    source_text = readable_buf.getvalue()
    if _looks_like_jcamp(source_name, source_text):
        return _parse_jcamp_dataset(
            source_text,
            source_name=source_name,
            data_type=data_type,
            metadata=metadata,
        )

    if _looks_like_xrd_cif(source_name, source_text, data_type=data_type):
        return _parse_xrd_cif_dataset(
            source_text,
            source_name=source_name,
            data_type=data_type,
            metadata=metadata,
        )

    if _looks_like_xrd_measured_pattern(source_name, source_text, data_type=data_type):
        return _parse_xrd_measured_dataset(
            source_text,
            source_name=source_name,
            data_type=data_type,
            metadata=metadata,
        )

    if hasattr(source, "seek"):
        source.seek(0)

    # ------------------------------------------------------------------
    # Detect format
    # ------------------------------------------------------------------
    try:
        fmt = detect_file_format(source)
    except Exception as exc:
        raise ValueError(f"Format detection failed: {exc}") from exc

    # Reset buffer position after format detection consumed it
    if hasattr(source, "seek"):
        source.seek(0)

    # ------------------------------------------------------------------
    # Load into a raw DataFrame
    # ------------------------------------------------------------------
    if fmt["is_xlsx"]:
        raw_df, source_name = _load_xlsx(source)
    else:
        raw_df, source_name = _load_text(source, fmt)

    if raw_df.empty:
        raise ValueError("No data could be read from the source.")

    # Strip whitespace from column names
    raw_df.columns = [str(c).strip() for c in raw_df.columns]

    # Drop completely empty rows
    raw_df.dropna(how="all", inplace=True)
    raw_df.reset_index(drop=True, inplace=True)

    # ------------------------------------------------------------------
    # Column mapping
    # ------------------------------------------------------------------
    import_warnings: list[str] = []
    import_confidence = "high"
    inferred_analysis_type = "unknown"
    if column_mapping is None:
        guessed = guess_columns(raw_df, source_name=source_name)
        col_map = {
            k: v
            for k, v in guessed.items()
            if k in ("temperature", "time", "signal") and v is not None
        }
        detected_type = str(guessed.get("data_type", "unknown"))
        inferred_analysis_type = str(guessed.get("inferred_analysis_type", detected_type or "unknown"))
        import_warnings.extend(str(item) for item in guessed.get("warnings", []))
        import_confidence = str((guessed.get("confidence") or {}).get("overall", "review"))
    else:
        col_map = {k: v for k, v in column_mapping.items() if v is not None}
        detected_type = "unknown"
        inferred_analysis_type = "unknown"
        import_confidence = "medium"
        import_warnings.append("Column mapping was supplied manually; verify the selected data type and units.")

    # Validate required columns
    if "temperature" not in col_map:
        raise ValueError(
            "Could not identify a temperature column.  "
            "Please supply a column_mapping with 'temperature' set."
        )
    if "signal" not in col_map:
        raise ValueError(
            "Could not identify a signal column.  "
            "Please supply a column_mapping with 'signal' set."
        )

    # ------------------------------------------------------------------
    # Build standardised DataFrame
    # ------------------------------------------------------------------
    keep_cols: Dict[str, str] = {}  # standard_name -> original_col

    keep_cols["temperature"] = col_map["temperature"]
    keep_cols["signal"] = col_map["signal"]
    if "time" in col_map:
        keep_cols["time"] = col_map["time"]

    # Build output DataFrame preserving all original columns
    out_df = raw_df.copy()

    # Rename to standard names (only for mapped roles)
    rename_map = {v: k for k, v in keep_cols.items() if v != k}
    out_df.rename(columns=rename_map, inplace=True)

    # Coerce standard columns to numeric
    for std_col in ("temperature", "signal", "time"):
        if std_col in out_df.columns:
            out_df[std_col] = pd.to_numeric(out_df[std_col], errors="coerce")

    # Drop rows where temperature or signal is NaN
    out_df.dropna(subset=["temperature", "signal"], inplace=True)
    out_df.reset_index(drop=True, inplace=True)

    if out_df.empty:
        raise ValueError(
            "After coercing to numeric, no valid (temperature, signal) rows remain."
        )

    # ------------------------------------------------------------------
    # Units
    # ------------------------------------------------------------------
    units: Dict[str, str] = {
        "temperature": _extract_unit(col_map["temperature"], "temperature"),
        "signal": _extract_unit(col_map["signal"], "signal"),
    }
    if "time" in col_map:
        units["time"] = _extract_unit(col_map["time"], "time")

    # ------------------------------------------------------------------
    # Data type
    # ------------------------------------------------------------------
    resolved_type = (data_type or detected_type or "unknown").upper()
    if resolved_type not in ("DSC", "TGA", "DTA", "FTIR", "RAMAN", "XRD", "UNKNOWN"):
        logger.warning("Unrecognised data_type %r; falling back to 'unknown'.", resolved_type)
        resolved_type = "unknown"
    if data_type and inferred_analysis_type not in ("unknown", resolved_type):
        import_warnings.append(
            f"Manual data type override '{resolved_type}' differs from the inferred analysis type '{inferred_analysis_type}'."
        )
        import_confidence = _classify_import_confidence(import_confidence, "medium")

    # ------------------------------------------------------------------
    # Final metadata
    # ------------------------------------------------------------------
    vendor_info = detect_vendor_info(source_name=source_name, columns=list(raw_df.columns))
    vendor = str(vendor_info["vendor"])
    import_warnings.extend(str(item) for item in vendor_info.get("warnings", []))
    import_confidence = _classify_import_confidence(import_confidence, str(vendor_info.get("confidence", "review")))
    display_name = metadata.get("display_name") or os.path.basename(source_name) or metadata.get("sample_name", "")
    inferred_signal_unit = _extract_unit(col_map["signal"], "signal") if "signal" in col_map else "unknown"
    spectral_confirmation_required = (
        resolved_type in _SPECTRAL_ANALYSIS_TYPES
        and inferred_analysis_type.upper() not in {resolved_type, "UNKNOWN"}
    ) or (
        resolved_type in _SPECTRAL_ANALYSIS_TYPES
        and inferred_analysis_type.upper() == "UNKNOWN"
    )
    spectral_confirmation_applied = bool(
        data_type
        and resolved_type in _SPECTRAL_ANALYSIS_TYPES
        and inferred_analysis_type.upper() != resolved_type
    )
    if spectral_confirmation_applied:
        import_warnings.append(
            f"Spectral modality '{resolved_type}' was user-confirmed after low-confidence inference ({inferred_analysis_type})."
        )
        import_confidence = _classify_import_confidence(import_confidence, "medium")

    if resolved_type in _SPECTRAL_ANALYSIS_TYPES:
        axis_column = str(col_map.get("temperature") or "")
        if not _is_spectral_axis_hint(axis_column):
            import_warnings.append(
                f"Spectral axis column '{axis_column}' was inferred without an explicit wavenumber/shift label; defaulting to wavenumber-first interpretation."
            )
            import_confidence = _classify_import_confidence(import_confidence, "review")
        if units.get("temperature") in {"°C", "K", "°F"}:
            units["temperature"] = "cm^-1"
        if inferred_signal_unit in {"a.u.", "unknown"}:
            import_warnings.append(
                f"{resolved_type} signal unit could not be confirmed from column '{col_map['signal']}'; review signal scaling before stable interpretation."
            )
            import_confidence = _classify_import_confidence(import_confidence, "medium")

    if resolved_type == "TGA" and inferred_signal_unit not in {"%", "mg"}:
        import_warnings.append(
            f"TGA signal unit could not be confirmed from column '{col_map['signal']}'; review whether the signal is % or absolute mass."
        )
        import_confidence = _classify_import_confidence(import_confidence, "review")
    elif resolved_type == "DSC" and inferred_signal_unit in {"a.u.", ""}:
        import_warnings.append(
            f"DSC signal unit could not be confirmed from column '{col_map['signal']}'; review whether the signal is mW, mW/mg, or W/g."
        )
        import_confidence = _classify_import_confidence(import_confidence, "medium")

    if resolved_type == "XRD":
        axis_column = str(col_map.get("temperature") or "")
        xrd_axis_mapping_confirmed = bool(metadata.get("xrd_axis_mapping_confirmed"))
        xrd_axis_mapping_review_required = (not xrd_axis_mapping_confirmed) and (not _is_xrd_axis_hint(axis_column))
        if xrd_axis_mapping_review_required:
            import_warnings.append(
                f"XRD axis column '{axis_column}' is not explicitly labeled as 2theta/angle; review mapping before stable analysis."
            )
            import_confidence = _classify_import_confidence(import_confidence, "review")
        if units.get("temperature") in {"°C", "K", "°F", "", "unknown"}:
            units["temperature"] = "degree_2theta"
        signal_unit_token = str(units.get("signal") or "").strip().lower()
        if signal_unit_token not in {"counts", "cps", "intensity"}:
            units["signal"] = "counts"
        if metadata.get("xrd_wavelength_angstrom") in (None, ""):
            import_warnings.append(
                "XRD wavelength was not provided; set xrd_wavelength_angstrom for deterministic phase-matching provenance."
            )
            import_confidence = _classify_import_confidence(import_confidence, "medium")
        xrd_provenance_state, xrd_provenance_warning = _xrd_provenance_state(
            wavelength_angstrom=metadata.get("xrd_wavelength_angstrom")
        )
    else:
        xrd_axis_mapping_review_required = False
        xrd_provenance_state, xrd_provenance_warning = ("complete", "")

    import_warnings = list(dict.fromkeys(warning for warning in import_warnings if warning))

    base_meta: dict = {
        "sample_name": metadata.get("sample_name", ""),
        "sample_mass": metadata.get("sample_mass", None),
        "heating_rate": metadata.get("heating_rate", None),
        "instrument": metadata.get("instrument", ""),
        "vendor": metadata.get("vendor", vendor),
        "display_name": display_name,
        "source_data_hash": _hash_dataframe(out_df),
        "import_method": "manual_mapping" if column_mapping else "auto",
        "import_confidence": import_confidence,
        "import_review_required": bool(import_warnings or import_confidence == "review"),
        "import_warnings": import_warnings,
        "inferred_analysis_type": inferred_analysis_type,
        "inferred_signal_unit": inferred_signal_unit,
        "inferred_vendor": vendor,
        "vendor_detection_confidence": vendor_info.get("confidence", "review"),
        "modality_confirmation_required": spectral_confirmation_required,
        "modality_confirmation_applied": spectral_confirmation_applied,
        "import_format": "xlsx" if fmt["is_xlsx"] else "delimited_text",
        "import_delimiter": fmt.get("delimiter") or ("xlsx" if fmt["is_xlsx"] else ""),
        "import_decimal_sep": fmt.get("decimal_sep", "."),
        "import_header_row": fmt.get("header_row", 0),
        "import_data_start_row": fmt.get("data_start_row", 1),
    }
    if resolved_type in _SPECTRAL_ANALYSIS_TYPES:
        base_meta["spectral_axis_role"] = "wavenumber"
        base_meta["spectral_axis_column"] = col_map.get("temperature", "")
    if resolved_type == "XRD":
        base_meta["xrd_axis_role"] = "two_theta"
        base_meta["xrd_axis_column"] = col_map.get("temperature", "")
        base_meta["xrd_axis_unit"] = units.get("temperature", "degree_2theta")
        base_meta["xrd_wavelength_angstrom"] = metadata.get("xrd_wavelength_angstrom")
        base_meta["xrd_axis_mapping_confirmed"] = bool(metadata.get("xrd_axis_mapping_confirmed"))
        base_meta["xrd_axis_mapping_review_required"] = bool(xrd_axis_mapping_review_required)
        base_meta["xrd_stable_matching_blocked"] = bool(xrd_axis_mapping_review_required)
        base_meta["xrd_provenance_state"] = xrd_provenance_state
        base_meta["xrd_provenance_warning"] = xrd_provenance_warning
    for optional_key in ("atmosphere", "operator", "calibration_id", "method_template_id"):
        if metadata.get(optional_key) not in (None, ""):
            base_meta[optional_key] = metadata[optional_key]
    base_meta.update(metadata)  # let caller override defaults

    return ThermalDataset(
        data=out_df,
        metadata=base_meta,
        data_type=resolved_type,
        units=units,
        original_columns=keep_cols,
        file_path=source_name,
    )


# ------------------------------------------------------------------
# Internal loaders
# ------------------------------------------------------------------


def _load_text(
    source: Union[str, Path, IO, object],
    fmt: dict,
) -> tuple[pd.DataFrame, str]:
    """Load a delimited text file into a raw DataFrame."""
    string_buf, source_name = _to_readable_buffer(source)

    delimiter = fmt["delimiter"] or ","
    header_row = fmt.get("header_row", 0)
    decimal_sep = fmt.get("decimal_sep", ".")

    # pandas read_csv from StringIO
    try:
        # Try with detected header row
        df = pd.read_csv(
            string_buf,
            sep=delimiter,
            header=header_row,
            decimal=decimal_sep,
            engine="python",
            skip_blank_lines=True,
            on_bad_lines="warn",
        )

        # If we get a single column the delimiter may be wrong; retry
        if len(df.columns) == 1 and delimiter != "\t":
            string_buf.seek(0)
            df_alt = pd.read_csv(
                string_buf,
                sep=r"\s+",
                header=header_row,
                decimal=decimal_sep,
                engine="python",
                skip_blank_lines=True,
                on_bad_lines="warn",
            )
            if len(df_alt.columns) > len(df.columns):
                df = df_alt

    except Exception as exc:
        raise ValueError(f"Failed to parse text file: {exc}") from exc

    return df, source_name


def _load_xlsx(
    source: Union[str, Path, IO, object],
) -> tuple[pd.DataFrame, str]:
    """Load the first sheet of an Excel workbook."""
    source_name = ""

    if isinstance(source, (str, Path)):
        source_name = str(source)
        wb_source: Union[str, io.BytesIO] = str(source)
    elif hasattr(source, "read"):
        source_name = getattr(source, "name", "")
        raw = source.read()
        wb_source = io.BytesIO(raw) if isinstance(raw, bytes) else io.BytesIO(raw.encode())
    elif isinstance(source, io.BytesIO):
        source.seek(0)
        wb_source = source
    else:
        raise TypeError(f"Cannot load Excel from source of type {type(source)}.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = pd.read_excel(
                wb_source,
                sheet_name=0,
                header=0,
                engine="openpyxl",
            )
    except ImportError:
        # Fallback to xlrd for older .xls
        try:
            if not isinstance(wb_source, str):
                wb_source.seek(0)  # type: ignore[union-attr]
            df = pd.read_excel(
                wb_source,
                sheet_name=0,
                header=0,
                engine="xlrd",
            )
        except Exception as exc:
            raise ImportError(
                "Reading Excel files requires 'openpyxl' (or 'xlrd' for .xls). "
                "Install with: pip install openpyxl"
            ) from exc
    except Exception as exc:
        raise ValueError(f"Failed to parse Excel file: {exc}") from exc

    return df, source_name


# ---------------------------------------------------------------------------
# 5. export_results_csv
# ---------------------------------------------------------------------------


def export_results_csv(
    results_dict: dict,
    file_path_or_buffer: Union[str, Path, IO],
) -> None:
    """Write analysis results to a CSV file or buffer.

    The *results_dict* may have arbitrary structure.  It is flattened into
    two columns: 'parameter' and 'value'.  Nested dicts and lists are
    serialised as JSON-like strings.

    Parameters
    ----------
    results_dict : dict
        Analysis results, e.g. peak temperatures, onset points, etc.
    file_path_or_buffer : str, Path, or writable file-like
        Destination for the CSV data.
    """
    if not isinstance(results_dict, dict):
        raise TypeError(f"results_dict must be a dict, got {type(results_dict)}.")

    rows = _flatten_dict(results_dict)
    df = pd.DataFrame(rows, columns=["parameter", "value"])

    try:
        if isinstance(file_path_or_buffer, (str, Path)):
            df.to_csv(str(file_path_or_buffer), index=False, encoding="utf-8-sig")
        else:
            # Write to buffer
            df.to_csv(file_path_or_buffer, index=False, encoding="utf-8-sig")
    except Exception as exc:
        raise IOError(f"Failed to write results CSV: {exc}") from exc


def _flatten_dict(d: dict, prefix: str = "") -> list:
    """Recursively flatten a nested dict into (parameter, value) pairs."""
    rows = []
    for key, val in d.items():
        full_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(val, dict):
            rows.extend(_flatten_dict(val, prefix=full_key))
        elif isinstance(val, (list, tuple, np.ndarray)):
            rows.append((full_key, str(list(val))))
        else:
            rows.append((full_key, val))
    return rows


# ---------------------------------------------------------------------------
# 6. export_data_xlsx
# ---------------------------------------------------------------------------


def export_data_xlsx(
    datasets: List[ThermalDataset],
    file_path_or_buffer: Union[str, Path, IO],
) -> None:
    """Export one or more ThermalDataset objects to an Excel workbook.

    Each dataset is written to a separate sheet.  A 'Metadata' sheet is
    prepended that summarises key information about every dataset.

    Parameters
    ----------
    datasets : list of ThermalDataset
        The datasets to export.
    file_path_or_buffer : str, Path, or writable binary file-like (BytesIO)
        Destination Excel file.
    """
    if not datasets:
        raise ValueError("datasets list is empty; nothing to export.")

    try:
        import openpyxl  # noqa: F401 -- presence check
    except ImportError as exc:
        raise ImportError(
            "Exporting to Excel requires 'openpyxl'. "
            "Install with: pip install openpyxl"
        ) from exc

    # Determine output target
    if isinstance(file_path_or_buffer, (str, Path)):
        output: Union[str, io.BytesIO] = str(file_path_or_buffer)
    else:
        output = file_path_or_buffer  # type: ignore[assignment]

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # --- Metadata summary sheet ---
        meta_rows = []
        for i, ds in enumerate(datasets):
            sheet_name = _make_sheet_name(ds, i)
            row: dict = {"sheet": sheet_name, "data_type": ds.data_type}
            row.update(ds.metadata)
            row["n_points"] = len(ds.data)
            row["temp_unit"] = ds.units.get("temperature", "")
            row["signal_unit"] = ds.units.get("signal", "")
            row["file_path"] = ds.file_path
            meta_rows.append(row)

        pd.DataFrame(meta_rows).to_excel(
            writer, sheet_name="Metadata", index=False
        )

        # --- Data sheets ---
        for i, ds in enumerate(datasets):
            sheet_name = _make_sheet_name(ds, i)

            # Build an export DataFrame with descriptive column headers
            temp_unit = ds.units.get("temperature", "°C")
            sig_unit = ds.units.get("signal", "a.u.")
            time_unit = ds.units.get("time", "")

            export_df = ds.data.copy()

            rename = {
                "temperature": f"Temperature ({temp_unit})",
                "signal": f"Signal ({sig_unit})",
            }
            if "time" in export_df.columns and time_unit:
                rename["time"] = f"Time ({time_unit})"

            export_df.rename(columns=rename, inplace=True)
            export_df.to_excel(writer, sheet_name=sheet_name, index=False)

    logger.info("Exported %d dataset(s) to Excel.", len(datasets))


def _make_sheet_name(ds: ThermalDataset, index: int) -> str:
    """Create a valid Excel sheet name (<=31 chars) from dataset attributes."""
    name = ds.metadata.get("sample_name") or os.path.splitext(
        os.path.basename(ds.file_path)
    )[0]
    if not name:
        name = f"Dataset_{index + 1}"

    # Sanitise: Excel forbids  / \ ? * [ ] :
    name = re.sub(r'[/\\?*\[\]:]', "_", name)
    prefix = f"{ds.data_type}_" if ds.data_type != "unknown" else ""
    full = f"{prefix}{name}"
    # Truncate to 31 characters
    return full[:31]

def _extract_first_float(text: str | None) -> float | None:
    if text in (None, ""):
        return None
    match = re.search(r"[-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?", str(text))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _parse_xrd_numeric_pairs(lines: list[str]) -> tuple[list[float], list[float]]:
    axis_values: list[float] = []
    signal_values: list[float] = []
    for raw_line in lines:
        line = str(raw_line or "").strip()
        if not line or line.startswith(("#", ";", "!", "//")):
            continue
        numbers = _parse_jcamp_numeric_tokens(line)
        if len(numbers) < 2:
            continue
        axis_values.append(float(numbers[0]))
        signal_values.append(float(numbers[1]))
    return axis_values, signal_values


def _normalize_xrd_dataset(
    *,
    axis_values: list[float],
    signal_values: list[float],
    source_name: str,
    metadata: dict | None,
    import_format: str,
    import_confidence: str,
    import_warnings: list[str] | None = None,
    wavelength_angstrom: float | None = None,
    data_type: str | None = None,
) -> ThermalDataset:
    if len(axis_values) < 2 or len(signal_values) < 2:
        raise ValueError("XRD import requires at least two numeric (axis, intensity) rows.")

    out_df = pd.DataFrame({"temperature": axis_values, "signal": signal_values})
    out_df.dropna(subset=["temperature", "signal"], inplace=True)
    out_df.sort_values("temperature", inplace=True)
    out_df.reset_index(drop=True, inplace=True)
    if out_df.empty:
        raise ValueError("XRD import could not extract usable numeric points.")

    metadata = metadata or {}
    warnings_list = list(import_warnings or [])
    resolved_type = str(data_type or "XRD").upper().strip()
    if resolved_type != "XRD":
        warnings_list.append(f"XRD parser normalized requested data type '{resolved_type or 'UNKNOWN'}' to 'XRD'.")
        resolved_type = "XRD"
    xrd_provenance_state, xrd_provenance_warning = _xrd_provenance_state(wavelength_angstrom=wavelength_angstrom)

    signal_unit = "counts"
    display_name = metadata.get("display_name") or os.path.basename(source_name) or metadata.get("sample_name", "")
    payload_meta = {
        "sample_name": metadata.get("sample_name", ""),
        "sample_mass": metadata.get("sample_mass", None),
        "heating_rate": metadata.get("heating_rate", None),
        "instrument": metadata.get("instrument", ""),
        "vendor": metadata.get("vendor", "Generic"),
        "display_name": display_name,
        "source_data_hash": _hash_dataframe(out_df),
        "import_method": "auto",
        "import_confidence": import_confidence,
        "import_review_required": bool(warnings_list),
        "import_warnings": warnings_list,
        "inferred_analysis_type": "XRD",
        "inferred_signal_unit": signal_unit,
        "inferred_vendor": "Generic",
        "vendor_detection_confidence": "review",
        "modality_confirmation_required": False,
        "modality_confirmation_applied": False,
        "import_format": import_format,
        "import_delimiter": "whitespace" if import_format == "xrd_xy_dat" else "cif",
        "import_decimal_sep": ".",
        "import_header_row": 0,
        "import_data_start_row": 1,
        "xrd_axis_role": "two_theta",
        "xrd_axis_column": "XRD_AXIS",
        "xrd_axis_unit": "degree_2theta",
        "xrd_wavelength_angstrom": wavelength_angstrom,
        "xrd_axis_mapping_review_required": False,
        "xrd_stable_matching_blocked": False,
        "xrd_provenance_state": xrd_provenance_state,
        "xrd_provenance_warning": xrd_provenance_warning,
    }
    payload_meta.update(metadata)

    return ThermalDataset(
        data=out_df,
        metadata=payload_meta,
        data_type=resolved_type,
        units={"temperature": "degree_2theta", "signal": signal_unit},
        original_columns={"temperature": "XRD_AXIS", "signal": "XRD_INTENSITY"},
        file_path=source_name,
    )


def _looks_like_xrd_cif(source_name: str, text: str, *, data_type: str | None = None) -> bool:
    if str(data_type or "").upper().strip() == "XRD" and str(source_name or "").lower().endswith(_XRD_CIF_EXTENSIONS):
        return True
    if str(source_name or "").lower().endswith(_XRD_CIF_EXTENSIONS):
        return True
    sample = str(text or "")[:5000].lower()
    return "data_" in sample and ("_pd_meas_2theta" in sample or "_pd_proc_2theta" in sample)


def _looks_like_xrd_measured_pattern(source_name: str, text: str, *, data_type: str | None = None) -> bool:
    suffix = str(Path(str(source_name or "")).suffix).lower()
    sample = str(text or "")[:5000].lower()
    has_hint = any(token in sample for token in ("2theta", "two theta", "xrd", "diffract", "intensity", "counts"))
    declared_xrd = str(data_type or "").upper().strip() == "XRD"
    source_name_lower = str(source_name or "").lower()
    axis_values, signal_values = _parse_xrd_numeric_pairs(str(text or "").splitlines()[:200])
    has_numeric_pair_shape = len(axis_values) >= 10 and len(signal_values) == len(axis_values)

    if suffix in {".xlsx", ".xls"} or sample.startswith("pk\x03\x04"):
        return False

    if suffix == ".xy":
        return True
    if suffix == ".dat":
        return bool(has_hint or declared_xrd or has_numeric_pair_shape)
    if suffix in {".txt", ".csv", ".tsv"} and has_numeric_pair_shape:
        if declared_xrd:
            return True
        if "xrd" in source_name_lower or "diffract" in source_name_lower:
            return True
        return bool(has_hint)
    if declared_xrd:
        return has_hint and any(token in sample for token in ("2theta", "two theta", "xrd", "diffract"))
    return has_hint and ("2theta" in sample or "two theta" in sample)


def _xrd_provenance_state(*, wavelength_angstrom: float | None) -> tuple[str, str]:
    if wavelength_angstrom in (None, ""):
        return (
            "incomplete",
            "XRD wavelength is not recorded; qualitative phase matching provenance remains incomplete.",
        )
    return ("complete", "")


def _parse_xrd_measured_dataset(
    text: str,
    *,
    source_name: str,
    data_type: str | None = None,
    metadata: dict | None = None,
) -> ThermalDataset:
    lines = str(text or "").splitlines()
    axis_values, signal_values = _parse_xrd_numeric_pairs(lines)

    wavelength = None
    for line in lines[:40]:
        lower = str(line).lower()
        if "wave" in lower or "lambda" in lower:
            wavelength = _extract_first_float(line)
            if wavelength is not None:
                break

    warnings_list: list[str] = []
    if wavelength is None:
        warnings_list.append("XRD wavelength metadata was not found in the source; set xrd_wavelength_angstrom before phase matching.")

    suffix = str(Path(str(source_name or "")).suffix).lower()
    confidence = "high" if suffix in _XRD_MEASURED_EXTENSIONS else "medium"
    if warnings_list:
        confidence = _classify_import_confidence(confidence, "medium")

    return _normalize_xrd_dataset(
        axis_values=axis_values,
        signal_values=signal_values,
        source_name=source_name,
        metadata=metadata,
        import_format="xrd_xy_dat",
        import_confidence=confidence,
        import_warnings=warnings_list,
        wavelength_angstrom=wavelength,
        data_type=data_type,
    )


def _parse_xrd_cif_dataset(
    text: str,
    *,
    source_name: str,
    data_type: str | None = None,
    metadata: dict | None = None,
) -> ThermalDataset:
    lines = [line.rstrip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        raise ValueError("CIF source is empty.")

    block_count = sum(1 for line in lines if line.strip().lower().startswith("data_"))
    if block_count > 1:
        raise ValueError("CIF MVP supports exactly one data_ block; multi-block CIF files are unsupported.")

    lowered = "\n".join(line.lower() for line in lines)
    if "_pd_meas_d_spacing" in lowered or "_pd_proc_d_spacing" in lowered:
        raise ValueError("CIF MVP supports two-theta powder patterns only; d-spacing-only CIF variants are unsupported.")

    wavelength = None
    for line in lines:
        token = line.strip()
        lower = token.lower()
        for tag in _XRD_WAVELENGTH_TAGS:
            if lower.startswith(tag):
                value = token[len(tag):].strip()
                wavelength = _extract_first_float(value)
                break
        if wavelength is not None:
            break

    axis_values: list[float] = []
    signal_values: list[float] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].strip()
        lower = line.lower()
        if lower != "loop_":
            i += 1
            continue

        i += 1
        tags: list[str] = []
        while i < n and lines[i].strip().startswith("_"):
            tags.append(lines[i].strip().lower())
            i += 1

        if not tags:
            continue

        axis_idx = next((idx for idx, tag in enumerate(tags) if tag in _XRD_SUPPORTED_AXIS_TAGS), None)
        intensity_idx = next((idx for idx, tag in enumerate(tags) if tag in _XRD_SUPPORTED_INTENSITY_TAGS), None)

        rows: list[str] = []
        while i < n:
            row_line = lines[i].strip()
            row_lower = row_line.lower()
            if not row_line:
                i += 1
                continue
            if row_lower == "loop_" or row_line.startswith("_") or row_lower.startswith("data_"):
                break
            rows.append(row_line)
            i += 1

        if axis_idx is None or intensity_idx is None:
            continue

        for row in rows:
            try:
                parts = shlex.split(row)
            except ValueError:
                parts = row.split()
            if len(parts) < len(tags):
                continue
            axis_raw = parts[axis_idx]
            intensity_raw = parts[intensity_idx]
            if axis_raw in {"?", "."} or intensity_raw in {"?", "."}:
                continue
            axis = _extract_first_float(axis_raw)
            intensity = _extract_first_float(intensity_raw)
            if axis is None or intensity is None:
                continue
            axis_values.append(axis)
            signal_values.append(intensity)

        if len(axis_values) >= 2:
            break

    if len(axis_values) < 2:
        if any(hint in lowered for hint in _XRD_UNSUPPORTED_CIF_HINTS):
            raise ValueError(
                "CIF MVP supports measured powder-pattern loops with _pd_meas_2theta_scan and intensity fields; structural-only CIF files are outside MVP scope."
            )
        raise ValueError(
            "CIF MVP supports measured powder-pattern loops containing _pd_meas_2theta_scan and intensity columns; provided CIF is unsupported."
        )

    warnings_list: list[str] = []
    if wavelength is None:
        warnings_list.append("CIF did not declare radiation wavelength; set xrd_wavelength_angstrom before qualitative matching.")

    confidence = "medium"
    if warnings_list:
        confidence = _classify_import_confidence(confidence, "medium")

    return _normalize_xrd_dataset(
        axis_values=axis_values,
        signal_values=signal_values,
        source_name=source_name,
        metadata=metadata,
        import_format="xrd_cif",
        import_confidence=confidence,
        import_warnings=warnings_list,
        wavelength_angstrom=wavelength,
        data_type=data_type,
    )




