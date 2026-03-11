"""Rule-based mechanism heuristics for scientific reasoning narratives."""

from __future__ import annotations

import re
from typing import Any


_ATOMIC_WEIGHTS: dict[str, float] = {
    "H": 1.00794,
    "Li": 6.941,
    "Be": 9.012182,
    "B": 10.811,
    "C": 12.0107,
    "N": 14.0067,
    "O": 15.9994,
    "F": 18.9984032,
    "Na": 22.98976928,
    "Mg": 24.3050,
    "Al": 26.9815386,
    "Si": 28.0855,
    "P": 30.973762,
    "S": 32.065,
    "Cl": 35.453,
    "K": 39.0983,
    "Ca": 40.078,
    "Sc": 44.955912,
    "Ti": 47.867,
    "V": 50.9415,
    "Cr": 51.9961,
    "Mn": 54.938045,
    "Fe": 55.845,
    "Co": 58.933195,
    "Ni": 58.6934,
    "Cu": 63.546,
    "Zn": 65.38,
    "Ga": 69.723,
    "Ge": 72.64,
    "As": 74.92160,
    "Se": 78.96,
    "Br": 79.904,
    "Rb": 85.4678,
    "Sr": 87.62,
    "Y": 88.90585,
    "Zr": 91.224,
    "Nb": 92.90638,
    "Mo": 95.96,
    "Ru": 101.07,
    "Rh": 102.9055,
    "Pd": 106.42,
    "Ag": 107.8682,
    "Cd": 112.411,
    "In": 114.818,
    "Sn": 118.710,
    "Sb": 121.760,
    "Te": 127.60,
    "I": 126.90447,
    "Cs": 132.9054519,
    "Ba": 137.327,
    "La": 138.90547,
    "Ce": 140.116,
    "Pr": 140.90765,
    "Nd": 144.242,
    "Sm": 150.36,
    "Eu": 151.964,
    "Gd": 157.25,
    "Tb": 158.92535,
    "Dy": 162.500,
    "Ho": 164.93032,
    "Er": 167.259,
    "Tm": 168.93421,
    "Yb": 173.054,
    "Lu": 174.9668,
    "Hf": 178.49,
    "Ta": 180.94788,
    "W": 183.84,
    "Re": 186.207,
    "Os": 190.23,
    "Ir": 192.217,
    "Pt": 195.084,
    "Au": 196.966569,
    "Hg": 200.59,
    "Tl": 204.3833,
    "Pb": 207.2,
    "Bi": 208.98040,
    "Th": 232.03806,
    "U": 238.02891,
}

_POLYMER_HINTS = (
    "poly",
    "pmma",
    "pvc",
    "pet",
    "polyethylene",
    "polypropylene",
    "polystyrene",
    "epoxy",
    "resin",
    "cellulose",
    "lignin",
    "biomass",
    "organic",
)
_INORGANIC_HINTS = (
    "salt",
    "mineral",
    "oxide",
    "sulfate",
    "sulphate",
    "chloride",
    "nitrate",
    "phosphate",
    "alumina",
    "ceramic",
)
_TGA_MASS_BALANCE_TOLERANCE = {
    "hydrate_salt": 2.0,
    "carbonate_inorganic": 2.5,
    "hydroxide_to_oxide": 3.0,
    "oxalate_multistage_inorganic": 3.0,
    "generic_inorganic_salt_or_mineral": 3.5,
}
_TGA_CLASS_LABELS = {
    "hydrate_salt": "hydrate / dehydration-prone salt",
    "carbonate_inorganic": "carbonate / decarbonation-prone inorganic",
    "hydroxide_to_oxide": "hydroxide / dehydration-to-oxide",
    "oxalate_multistage_inorganic": "oxalate / multistage gas-loss inorganic",
    "generic_inorganic_salt_or_mineral": "generic inorganic salt / mineral",
    "polymer_or_organic": "polymer / organic material",
    "unknown_unconstrained": "unknown / unconstrained",
}


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _flatten_context_text(
    *,
    summary: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
    dataset_key: str | None,
) -> str:
    summary = summary or {}
    metadata = metadata or {}
    parts = [
        dataset_key or "",
        metadata.get("sample_name") or "",
        metadata.get("display_name") or "",
        metadata.get("file_name") or "",
        summary.get("sample_name") or "",
    ]
    return " ".join(str(item) for item in parts if item not in (None, ""))


def _extract_formula_candidates(text: str) -> list[str]:
    if not text:
        return []
    normalized = text.replace("·", ".")
    tokens = [token for token in re.split(r"[^A-Za-z0-9().]+", normalized) if token]
    candidates: list[str] = []
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        upper_token = any(ch.isupper() for ch in token)
        has_digit = any(ch.isdigit() for ch in token)
        if not upper_token or not has_digit:
            idx += 1
            continue
        candidate = token
        if idx + 1 < len(tokens) and re.fullmatch(r"\d*H2O", tokens[idx + 1], flags=re.IGNORECASE):
            candidate = f"{token}.{tokens[idx + 1]}"
            idx += 1
        cleaned = candidate.strip("._- ")
        if cleaned:
            candidates.append(cleaned)
        idx += 1
    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _parse_number(formula: str, index: int) -> tuple[float, int]:
    start = index
    while index < len(formula) and formula[index].isdigit():
        index += 1
    if start == index:
        return 1.0, index
    return float(formula[start:index]), index


def _parse_formula_segment(formula: str, index: int = 0, end_char: str | None = None) -> tuple[dict[str, float], int]:
    counts: dict[str, float] = {}
    while index < len(formula):
        char = formula[index]
        if end_char and char == end_char:
            return counts, index + 1
        if char == "(":
            sub_counts, index = _parse_formula_segment(formula, index + 1, end_char=")")
            multiplier, index = _parse_number(formula, index)
            for key, value in sub_counts.items():
                counts[key] = counts.get(key, 0.0) + (value * multiplier)
            continue
        if not char.isalpha() or not char.isupper():
            index += 1
            continue
        symbol = char
        if index + 1 < len(formula) and formula[index + 1].islower():
            symbol += formula[index + 1]
            index += 1
        index += 1
        multiplier, index = _parse_number(formula, index)
        counts[symbol] = counts.get(symbol, 0.0) + multiplier
    return counts, index


def _parse_formula(formula: str | None) -> dict[str, float] | None:
    if not formula:
        return None
    normalized = str(formula).replace("·", ".").replace(" ", "")
    if not normalized:
        return None
    parts = [part for part in normalized.split(".") if part]
    total_counts: dict[str, float] = {}
    for part in parts:
        if part in {"+", "-"}:
            continue
        multiplier = 1.0
        if re.match(r"^\d+", part):
            digits = re.match(r"^\d+", part)
            if digits:
                multiplier = float(digits.group(0))
                part = part[len(digits.group(0)) :]
        counts, _ = _parse_formula_segment(part)
        if not counts:
            continue
        for element, value in counts.items():
            total_counts[element] = total_counts.get(element, 0.0) + (value * multiplier)
    if not total_counts:
        return None
    return total_counts


def _formula_mass(formula_counts: dict[str, float] | None) -> float | None:
    if not formula_counts:
        return None
    total = 0.0
    for element, count in formula_counts.items():
        mass = _ATOMIC_WEIGHTS.get(element)
        if mass is None:
            return None
        total += mass * count
    return total


def _formula_element_order(formula: str | None) -> list[str]:
    order: list[str] = []
    for symbol in re.findall(r"[A-Z][a-z]?", str(formula or "")):
        if symbol not in order:
            order.append(symbol)
    return order


def _counts_to_formula_string(formula_counts: dict[str, float] | None, *, order_hint: list[str] | None = None) -> str | None:
    if not formula_counts:
        return None
    order: list[str] = []
    for symbol in order_hint or []:
        if symbol in formula_counts and symbol not in order:
            order.append(symbol)
    for symbol in sorted(formula_counts.keys()):
        if symbol not in order:
            order.append(symbol)

    parts: list[str] = []
    for symbol in order:
        count = float(formula_counts.get(symbol) or 0.0)
        if count <= 1e-9:
            continue
        nearest = round(count)
        if abs(count - nearest) > 1e-6:
            return None
        parts.append(symbol if nearest == 1 else f"{symbol}{int(nearest)}")
    output = "".join(parts).strip()
    return output or None


def _derive_anhydrous_formula(formula: str | None) -> str | None:
    if not formula:
        return None
    raw = str(formula).strip()
    if not raw:
        return None
    stripped = re.sub(r"(?:[·\.])\d*H2O", "", raw, flags=re.IGNORECASE).strip(" .·")
    if not stripped or stripped == raw:
        return None
    parsed = _parse_formula(stripped)
    rendered = _counts_to_formula_string(parsed, order_hint=_formula_element_order(stripped))
    return rendered or stripped


def _derive_carbonate_oxide_formula(formula: str | None, formula_counts: dict[str, float] | None) -> str | None:
    formula_counts = dict(formula_counts or {})
    carbonate_groups = _group_count(formula or "", "CO3")
    if carbonate_groups <= 0 or not formula_counts:
        return None

    formula_counts["C"] = formula_counts.get("C", 0.0) - carbonate_groups
    formula_counts["O"] = formula_counts.get("O", 0.0) - (2.0 * carbonate_groups)
    if formula_counts.get("C", 0.0) > 1e-6 or formula_counts.get("O", 0.0) < -1e-6:
        return None
    if formula_counts.get("H", 0.0) > 1e-6:
        return None

    cleaned: dict[str, float] = {}
    for symbol, count in formula_counts.items():
        if count <= 1e-9:
            continue
        cleaned[symbol] = count
    if not cleaned:
        return None
    return _counts_to_formula_string(cleaned, order_hint=_formula_element_order(formula))


def _group_count(formula: str, group_token: str) -> float:
    if not formula:
        return 0.0
    normalized = str(formula).replace("·", ".").replace(" ", "")
    total = 0.0
    for value in re.findall(rf"\({re.escape(group_token)}\)(\d*)", normalized, flags=re.IGNORECASE):
        total += float(value) if value else 1.0
    for value in re.findall(rf"(?<!\(){re.escape(group_token)}(\d*)", normalized, flags=re.IGNORECASE):
        total += float(value) if value else 1.0
    return total


def _hydrate_water_units(formula: str) -> float:
    if not formula:
        return 0.0
    total = 0.0
    normalized = str(formula).replace("·", ".")
    for match in re.findall(r"(?:^|\.)(\d*)H2O", normalized, flags=re.IGNORECASE):
        total += float(match) if match else 1.0
    return total


def infer_tga_material_class(
    *,
    summary: dict[str, Any] | None,
    rows: list[dict[str, Any]] | None,
    metadata: dict[str, Any] | None,
    dataset_key: str | None = None,
) -> dict[str, Any]:
    """Infer broad material/reaction family for TGA interpretation."""
    summary = summary or {}
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    metadata = metadata or {}
    context_text = _flatten_context_text(summary=summary, metadata=metadata, dataset_key=dataset_key)
    lower_text = context_text.lower()

    scores = {
        "hydrate_salt": 0.0,
        "carbonate_inorganic": 0.0,
        "hydroxide_to_oxide": 0.0,
        "oxalate_multistage_inorganic": 0.0,
        "generic_inorganic_salt_or_mineral": 0.0,
        "polymer_or_organic": 0.0,
        "unknown_unconstrained": 0.0,
    }
    clues: list[str] = []

    formula_candidates = _extract_formula_candidates(context_text)
    parsed_formula: dict[str, float] | None = None
    formula_used: str | None = None
    for candidate in formula_candidates:
        parsed = _parse_formula(candidate)
        if parsed:
            parsed_formula = parsed
            formula_used = candidate
            break

    if "hydrate" in lower_text or "h2o" in lower_text:
        scores["hydrate_salt"] += 2.5
        clues.append("hydrate-style naming tokens detected")
    if "carbonate" in lower_text or "co3" in lower_text:
        scores["carbonate_inorganic"] += 2.0
        clues.append("carbonate-style naming tokens detected")
    if "hydroxide" in lower_text or "(oh" in lower_text:
        scores["hydroxide_to_oxide"] += 2.0
        clues.append("hydroxide-style naming tokens detected")
    if "oxalate" in lower_text or "c2o4" in lower_text:
        scores["oxalate_multistage_inorganic"] += 2.0
        clues.append("oxalate-style naming tokens detected")
    if any(token in lower_text for token in _POLYMER_HINTS):
        scores["polymer_or_organic"] += 2.5
        clues.append("polymer/organic naming tokens detected")
    if any(token in lower_text for token in _INORGANIC_HINTS):
        scores["generic_inorganic_salt_or_mineral"] += 1.8
        clues.append("inorganic/mineral naming tokens detected")

    total_loss = _safe_float(summary.get("total_mass_loss_percent"))
    residue = _safe_float(summary.get("residue_percent"))
    if total_loss is not None and residue is not None:
        if total_loss >= 85.0 and residue <= 15.0:
            scores["polymer_or_organic"] += 1.2
        if residue >= 40.0 and total_loss <= 65.0:
            scores["generic_inorganic_salt_or_mineral"] += 1.5
            scores["carbonate_inorganic"] += 0.8
            scores["hydrate_salt"] += 0.6

    event_temperatures = [
        _safe_float(row.get("midpoint_temperature"))
        for row in rows
        if _safe_float(row.get("midpoint_temperature")) is not None
    ]
    if event_temperatures:
        low_temp_events = sum(1 for value in event_temperatures if value <= 250.0)
        high_temp_events = sum(1 for value in event_temperatures if value >= 550.0)
        if low_temp_events >= 2:
            scores["hydrate_salt"] += 0.8
            scores["hydroxide_to_oxide"] += 0.5
        if high_temp_events >= 1:
            scores["carbonate_inorganic"] += 0.8
            scores["generic_inorganic_salt_or_mineral"] += 0.5

    if formula_used:
        hydrate_units = _hydrate_water_units(formula_used)
        carbonate_groups = _group_count(formula_used, "CO3")
        hydroxide_groups = _group_count(formula_used, "OH")
        oxalate_groups = _group_count(formula_used, "C2O4")
        if hydrate_units > 0:
            scores["hydrate_salt"] += 3.0
            clues.append(f"formula includes hydrate units ({hydrate_units:g} H2O)")
        if carbonate_groups > 0:
            scores["carbonate_inorganic"] += 3.0
            clues.append(f"formula includes carbonate groups ({carbonate_groups:g} CO3)")
        if hydroxide_groups > 0:
            scores["hydroxide_to_oxide"] += 2.5
            clues.append(f"formula includes hydroxide groups ({hydroxide_groups:g} OH)")
        if oxalate_groups > 0:
            scores["oxalate_multistage_inorganic"] += 3.0
            clues.append(f"formula includes oxalate groups ({oxalate_groups:g} C2O4)")
        if parsed_formula and "C" not in parsed_formula and "H" not in parsed_formula:
            scores["generic_inorganic_salt_or_mineral"] += 1.0

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_class, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    if top_score < 1.0:
        top_class = "unknown_unconstrained"
        confidence = "low"
    elif top_score >= 4.0 and (top_score - second_score) >= 1.5:
        confidence = "high"
    elif top_score >= 2.0:
        confidence = "moderate"
    else:
        confidence = "low"

    return {
        "material_class": top_class,
        "material_class_label": _TGA_CLASS_LABELS.get(top_class, _TGA_CLASS_LABELS["unknown_unconstrained"]),
        "confidence": confidence,
        "score": round(top_score, 2),
        "runner_up_score": round(second_score, 2),
        "formula_candidate": formula_used,
        "formula_counts": parsed_formula or {},
        "scores": {key: round(value, 2) for key, value in ranked},
        "clues": clues[:6],
    }


def evaluate_tga_mass_balance(
    *,
    summary: dict[str, Any] | None,
    class_inference: dict[str, Any] | None,
) -> dict[str, Any]:
    """Evaluate whether observed mass balance fits a plausible stable-solid pathway."""
    summary = summary or {}
    class_inference = class_inference or {}
    total_loss = _safe_float(summary.get("total_mass_loss_percent"))
    residue = _safe_float(summary.get("residue_percent"))
    if total_loss is None or residue is None:
        return {
            "status": "not_assessed",
            "reason": "Required summary metrics were incomplete.",
            "pathway": None,
            "formula_candidate": class_inference.get("formula_candidate"),
        }

    material_class = class_inference.get("material_class") or "unknown_unconstrained"
    formula = class_inference.get("formula_candidate")
    formula_counts = class_inference.get("formula_counts") or _parse_formula(formula) or {}
    formula_mass = _formula_mass(formula_counts)
    expected_solid_formula: str | None = None
    tolerance = _TGA_MASS_BALANCE_TOLERANCE.get(material_class, 3.5)
    if formula_mass is None and material_class in {
        "hydrate_salt",
        "carbonate_inorganic",
        "hydroxide_to_oxide",
        "oxalate_multistage_inorganic",
    }:
        return {
            "status": "not_assessed",
            "reason": "Class was inferred, but formula parsing was insufficient for stoichiometric matching.",
            "pathway": None,
            "formula_candidate": formula,
            "reactant_formula": formula,
            "expected_solid_formula": None,
            "class_label": class_inference.get("material_class_label"),
        }

    expected_loss: float | None = None
    expected_residue: float | None = None
    expected_loss_range: tuple[float, float] | None = None
    pathway: str | None = None

    if material_class == "hydrate_salt":
        hydrate_units = _hydrate_water_units(formula or "")
        if hydrate_units > 0 and formula_mass:
            expected_loss = (hydrate_units * 18.01528 / formula_mass) * 100.0
            expected_residue = 100.0 - expected_loss
            expected_solid_formula = _derive_anhydrous_formula(formula)
            if expected_solid_formula and formula:
                pathway = f"dehydration of {formula} to anhydrous {expected_solid_formula}"
            else:
                pathway = "dehydration to anhydrous solid residue"
    elif material_class == "carbonate_inorganic":
        carbonate_groups = _group_count(formula or "", "CO3")
        if carbonate_groups > 0 and formula_mass:
            expected_loss = (carbonate_groups * 44.0095 / formula_mass) * 100.0
            expected_residue = 100.0 - expected_loss
            expected_solid_formula = _derive_carbonate_oxide_formula(formula, formula_counts)
            if expected_solid_formula and formula:
                pathway = f"decarbonation of {formula} to {expected_solid_formula}"
            else:
                pathway = "decarbonation with stable oxide-rich residue"
    elif material_class == "hydroxide_to_oxide":
        hydroxide_groups = _group_count(formula or "", "OH")
        if hydroxide_groups > 0 and formula_mass:
            expected_loss = ((hydroxide_groups / 2.0) * 18.01528 / formula_mass) * 100.0
            expected_residue = 100.0 - expected_loss
            pathway = "dehydroxylation toward oxide residue"
    elif material_class == "oxalate_multistage_inorganic":
        oxalate_groups = _group_count(formula or "", "C2O4")
        if oxalate_groups > 0 and formula_mass:
            low_loss = (oxalate_groups * 44.0095 / formula_mass) * 100.0
            high_loss = (oxalate_groups * (44.0095 + 28.0101) / formula_mass) * 100.0
            expected_loss_range = (min(low_loss, high_loss), max(low_loss, high_loss))
            pathway = "multistage oxalate gas-loss pathway to stable residue"

    if expected_loss_range is not None:
        min_expected, max_expected = expected_loss_range
        if (min_expected - tolerance) <= total_loss <= (max_expected + tolerance):
            status = "strong_match"
        elif (min_expected - (1.8 * tolerance)) <= total_loss <= (max_expected + (1.8 * tolerance)):
            status = "plausible_match"
        else:
            status = "mismatch"
        range_mid = (min_expected + max_expected) / 2.0
        delta_loss = total_loss - range_mid
        return {
            "status": status,
            "reason": "Observed loss was compared against a plausible oxalate gas-loss range.",
            "pathway": pathway,
            "formula_candidate": formula,
            "reactant_formula": formula,
            "expected_solid_formula": expected_solid_formula,
            "expected_loss_percent": range_mid,
            "expected_loss_range_percent": [round(min_expected, 2), round(max_expected, 2)],
            "expected_residue_percent": 100.0 - range_mid,
            "delta_loss_percent": round(delta_loss, 2),
            "delta_residue_percent": round(residue - (100.0 - range_mid), 2),
            "tolerance_percent": tolerance,
            "class_label": class_inference.get("material_class_label"),
        }

    if expected_loss is None or expected_residue is None:
        return {
            "status": "not_assessed",
            "reason": "No class-specific stoichiometric pathway could be evaluated from available formula clues.",
            "pathway": None,
            "formula_candidate": formula,
            "reactant_formula": formula,
            "expected_solid_formula": None,
            "class_label": class_inference.get("material_class_label"),
        }

    delta_loss = total_loss - expected_loss
    delta_residue = residue - expected_residue
    abs_delta = max(abs(delta_loss), abs(delta_residue))
    if abs_delta <= tolerance:
        status = "strong_match"
    elif abs_delta <= (1.8 * tolerance):
        status = "plausible_match"
    else:
        status = "mismatch"
    return {
        "status": status,
        "reason": "Observed mass balance was compared against a class-specific stoichiometric pathway.",
        "pathway": pathway,
        "formula_candidate": formula,
        "reactant_formula": formula,
        "expected_solid_formula": expected_solid_formula,
        "expected_loss_percent": round(expected_loss, 2),
        "expected_residue_percent": round(expected_residue, 2),
        "delta_loss_percent": round(delta_loss, 2),
        "delta_residue_percent": round(delta_residue, 2),
        "tolerance_percent": tolerance,
        "class_label": class_inference.get("material_class_label"),
    }


def _derive_tga_profile(
    *,
    total_loss: float | None,
    residue: float | None,
    class_inference: dict[str, Any],
    mass_balance: dict[str, Any],
) -> str:
    if (
        mass_balance.get("status") in {"strong_match", "plausible_match"}
        and class_inference.get("material_class")
        in {
            "hydrate_salt",
            "carbonate_inorganic",
            "hydroxide_to_oxide",
            "oxalate_multistage_inorganic",
            "generic_inorganic_salt_or_mineral",
        }
    ):
        return "expected_stable_residue_conversion"
    if total_loss is None or residue is None:
        return "inconclusive"
    if total_loss >= 90 and residue <= 10:
        return "near_complete_decomposition"
    if total_loss >= 70 and residue <= 30:
        return "substantial_partial_decomposition"
    if residue >= 40 and total_loss <= 65:
        return "high_residue_mass_balance_unresolved"
    return "limited_partial_decomposition"


def tga_mechanism_signals(
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    metadata: dict[str, Any] | None = None,
    dataset_key: str | None = None,
) -> dict[str, Any]:
    """Infer high-level TGA behavior with class-aware mass-balance and DTG caution logic."""
    total_loss = _safe_float((summary or {}).get("total_mass_loss_percent"))
    residue = _safe_float((summary or {}).get("residue_percent"))
    step_count = _safe_int((summary or {}).get("step_count"))

    valid_rows = [row for row in (rows or []) if isinstance(row, dict)]
    ranked = sorted(
        valid_rows,
        key=lambda row: _safe_float(row.get("mass_loss_percent")) or float("-inf"),
        reverse=True,
    )
    ordered_by_temp = sorted(
        valid_rows,
        key=lambda row: _safe_float(row.get("midpoint_temperature")) if _safe_float(row.get("midpoint_temperature")) is not None else float("inf"),
    )
    lead_loss = _safe_float((ranked[0] if ranked else {}).get("mass_loss_percent"))
    second_loss = _safe_float((ranked[1] if len(ranked) > 1 else {}).get("mass_loss_percent"))
    lead_midpoint = _safe_float((ranked[0] if ranked else {}).get("midpoint_temperature"))

    if step_count is None and ranked:
        step_count = len(ranked)
    dominant = bool(
        lead_loss is not None
        and second_loss is not None
        and second_loss > 0
        and lead_loss >= 1.5 * second_loss
        and (total_loss is None or lead_loss >= (0.45 * total_loss))
    )
    if step_count is not None and step_count <= 1:
        dominant = True

    minor_threshold = max(2.0, (0.12 * total_loss) if total_loss is not None else 2.0)
    minor_event_count = 0
    event_losses: list[float] = []
    for row in ranked:
        loss = _safe_float(row.get("mass_loss_percent"))
        if loss is None:
            continue
        event_losses.append(loss)
    if event_losses:
        max_loss = max(event_losses)
        for loss in event_losses:
            if loss <= minor_threshold and loss < (0.5 * max_loss):
                minor_event_count += 1

    adjacent_pair_count = 0
    previous_temp = None
    for row in ordered_by_temp:
        midpoint = _safe_float(row.get("midpoint_temperature"))
        if midpoint is None:
            continue
        if previous_temp is not None and abs(midpoint - previous_temp) <= 35.0:
            adjacent_pair_count += 1
        previous_temp = midpoint
    possible_subdivision = minor_event_count > 0 or adjacent_pair_count > 0

    class_inference = infer_tga_material_class(
        summary=summary,
        rows=rows,
        metadata=metadata,
        dataset_key=dataset_key,
    )
    mass_balance = evaluate_tga_mass_balance(summary=summary, class_inference=class_inference)
    profile = _derive_tga_profile(
        total_loss=total_loss,
        residue=residue,
        class_inference=class_inference,
        mass_balance=mass_balance,
    )

    return {
        "profile": profile,
        "dominant_step": dominant,
        "step_count": step_count,
        "dtg_resolved_event_count": step_count,
        "lead_mass_loss_percent": lead_loss,
        "second_mass_loss_percent": second_loss,
        "lead_midpoint_temperature": lead_midpoint,
        "minor_event_count": minor_event_count,
        "adjacent_event_pair_count": adjacent_pair_count,
        "possible_subdivision": possible_subdivision,
        "minor_event_threshold_percent": round(minor_threshold, 2),
        "material_class_inference": class_inference,
        "mass_balance_assessment": mass_balance,
    }


def dsc_mechanism_signals(summary: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Infer high-level DSC event behavior."""
    summary = summary or {}
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    peak_count = summary.get("peak_count")
    peak_count = int(peak_count) if isinstance(peak_count, (int, float)) else len(rows)

    has_tg = _safe_float(summary.get("tg_midpoint")) is not None
    peak_types = [str(row.get("peak_type") or "").lower() for row in rows]
    endotherm_count = sum(1 for value in peak_types if "endo" in value)
    exotherm_count = sum(1 for value in peak_types if "exo" in value)

    complexity = "simple" if peak_count <= 1 else "multistage"
    if peak_count >= 3:
        complexity = "complex"

    return {
        "peak_count": peak_count,
        "has_tg": has_tg,
        "complexity": complexity,
        "endotherm_count": endotherm_count,
        "exotherm_count": exotherm_count,
    }


def dta_mechanism_signals(summary: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Infer qualitative DTA event behavior."""
    summary = summary or {}
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    peak_count = summary.get("peak_count")
    peak_count = int(peak_count) if isinstance(peak_count, (int, float)) else len(rows)
    return {
        "peak_count": peak_count,
        "event_richness": "multi-event" if peak_count >= 2 else "single-event",
    }


def kinetics_mechanism_signals(
    analysis_type: str,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Infer kinetics behavior with trend and complexity hints."""
    normalized = (analysis_type or "").upper()
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    ea_values = []
    alpha_values = []
    for row in rows:
        ea = _safe_float(row.get("activation_energy_kj_mol"))
        alpha = _safe_float(row.get("alpha"))
        if ea is not None:
            ea_values.append(ea)
        if alpha is not None:
            alpha_values.append(alpha)

    trend = "not_assessed"
    if len(ea_values) >= 2:
        delta = ea_values[-1] - ea_values[0]
        if abs(delta) <= 5:
            trend = "approximately_constant"
        elif delta > 5:
            trend = "increasing_with_conversion"
        else:
            trend = "decreasing_with_conversion"

    complexity = "single_step_like" if trend in {"approximately_constant", "not_assessed"} else "conversion_dependent"
    return {
        "method": normalized,
        "ea_count": len(ea_values),
        "ea_trend": trend,
        "complexity_hint": complexity,
        "has_conversion_profile": bool(alpha_values),
        "summary_activation_energy": _safe_float((summary or {}).get("activation_energy_kj_mol")),
    }


def deconvolution_mechanism_signals(summary: dict[str, Any], fit_quality: dict[str, Any]) -> dict[str, Any]:
    """Infer overlap/fit risk behavior for peak deconvolution."""
    peak_count = summary.get("peak_count")
    peak_count = int(peak_count) if isinstance(peak_count, (int, float)) else None
    r2 = _safe_float((fit_quality or {}).get("r_squared"))
    rmse = _safe_float((fit_quality or {}).get("rmse"))

    if peak_count is None:
        overlap = "unknown"
    elif peak_count >= 3:
        overlap = "high_overlap_likelihood"
    elif peak_count == 2:
        overlap = "moderate_overlap_likelihood"
    else:
        overlap = "low_overlap_likelihood"

    return {
        "peak_count": peak_count,
        "r_squared": r2,
        "rmse": rmse,
        "overlap_hint": overlap,
    }
