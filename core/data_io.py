"""
data_io.py
==========
Data import/export engine for thermal analysis (DSC / TGA / DTA).

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
import io
import logging
import os
import re
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
        r"\u00b5[Vv]",      # µV
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
}

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


def guess_columns(df: pd.DataFrame) -> dict:
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
        'data_type'    str          - 'DSC', 'TGA', 'DTA', or 'unknown'
    """
    cols = list(df.columns)
    result: Dict[str, Optional[str]] = {
        "temperature": None,
        "time": None,
        "signal": None,
        "data_type": "unknown",
    }

    def _first_match(patterns: List[str]) -> Optional[str]:
        for col in cols:
            for pat in patterns:
                if re.search(pat, col):
                    return col
        return None

    result["temperature"] = _first_match(_PATTERNS["temperature"])
    result["time"] = _first_match(_PATTERNS["time"])

    # Signal: try specific types in priority order
    dsc_col = _first_match(_PATTERNS["signal_dsc"])
    tga_col = _first_match(_PATTERNS["signal_tga"])
    dta_col = _first_match(_PATTERNS["signal_dta"])

    if dsc_col:
        result["signal"] = dsc_col
        result["data_type"] = "DSC"
    elif tga_col:
        result["signal"] = tga_col
        result["data_type"] = "TGA"
    elif dta_col:
        result["signal"] = dta_col
        result["data_type"] = "DTA"
    else:
        # Fallback: use the first numeric column that is not already assigned
        assigned = {result["temperature"], result["time"]}
        for col in cols:
            if col not in assigned and _is_mostly_numeric(df[col]):
                result["signal"] = col
                break

    # If temperature not found, try heuristic: first numeric column not used as signal
    if result["temperature"] is None:
        assigned = {result["signal"], result["time"]}
        for col in cols:
            if col not in assigned and _is_mostly_numeric(df[col]):
                result["temperature"] = col
                break

    return result


# ---------------------------------------------------------------------------
# Internal: unit extraction from column name
# ---------------------------------------------------------------------------

_UNIT_RE = re.compile(
    r"\(?([°%a-zA-Z\u00b0\u00b5/]+(?:\.[a-zA-Z]+)?)\)?$"
)

_TEMP_UNIT_MAP = {
    "c": "°C", "°c": "°C", "celsius": "°C",
    "k": "K",  "°k": "K", "kelvin": "K",
    "f": "°F", "°f": "°F", "fahrenheit": "°F",
}

_SIGNAL_UNIT_KEYWORDS = {
    "mw/mg": "mW/mg", "mw": "mW",
    "µv": "µV", "uv": "µV",
    "%": "%", "mg": "mg",
    "w/g": "W/g",
}

_TIME_UNIT_MAP = {"min": "min", "s": "s", "sec": "s", "h": "h"}


def _extract_unit(col_name: str, role: str) -> str:
    """Try to extract a unit string from a column name like 'Temp/°C'."""
    m = _UNIT_RE.search(col_name)
    unit_str = m.group(1).strip() if m else ""
    unit_lower = unit_str.lower()

    if role == "temperature":
        return _TEMP_UNIT_MAP.get(unit_lower, "°C")
    if role == "signal":
        for key, val in _SIGNAL_UNIT_KEYWORDS.items():
            if key in unit_lower:
                return val
        return unit_str or "a.u."
    if role == "time":
        return _TIME_UNIT_MAP.get(unit_lower, "s")
    return unit_str


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
        Override automatic data-type detection.  One of 'DSC', 'TGA', 'DTA'.
    metadata : dict, optional
        Extra metadata to merge into the dataset's metadata dict.

    Returns
    -------
    ThermalDataset
    """
    metadata = metadata or {}
    source_name = ""

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
    if column_mapping is None:
        guessed = guess_columns(raw_df)
        col_map = {
            k: v
            for k, v in guessed.items()
            if k in ("temperature", "time", "signal") and v is not None
        }
        detected_type = guessed.get("data_type", "unknown")
    else:
        col_map = {k: v for k, v in column_mapping.items() if v is not None}
        detected_type = "unknown"

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
    if resolved_type not in ("DSC", "TGA", "DTA", "UNKNOWN"):
        logger.warning("Unrecognised data_type %r; falling back to 'unknown'.", resolved_type)
        resolved_type = "unknown"

    # ------------------------------------------------------------------
    # Final metadata
    # ------------------------------------------------------------------
    base_meta: dict = {
        "sample_name": metadata.get("sample_name", ""),
        "sample_mass": metadata.get("sample_mass", None),
        "heating_rate": metadata.get("heating_rate", None),
        "instrument": metadata.get("instrument", ""),
    }
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
