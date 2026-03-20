"""Presentation-only helpers for chemical formula typography."""

from __future__ import annotations

import re
from typing import Any


_SUBSCRIPT_MAP = str.maketrans({
    "0": "₀",
    "1": "₁",
    "2": "₂",
    "3": "₃",
    "4": "₄",
    "5": "₅",
    "6": "₆",
    "7": "₇",
    "8": "₈",
    "9": "₉",
    "+": "₊",
    "-": "₋",
})
_HTML_SUB_PATTERN = re.compile(r"(?is)<sub>\s*([^<]+?)\s*</sub>")
_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_URL_PATTERN = re.compile(r"(https?://[^\s)]+)")
_DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s)]+", re.IGNORECASE)
_FORMULA_TOKEN_PATTERN = re.compile(r"(?<![A-Za-z0-9/])([A-Z][A-Za-z0-9()\[\]·\-–]*(?:\d+[A-Za-z0-9()\[\]·\-–]*)+)(?![A-Za-z0-9/])")
_FORMULA_SEGMENT_PATTERN = re.compile(r"^\d*(?:(?:[A-Z][a-z]?\d*)|\((?:[A-Z][a-z]?\d*)+\)\d*)+$")


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _subscript_fragment(text: str) -> str:
    return str(text or "").translate(_SUBSCRIPT_MAP)


def _normalize_html_subscripts(text: str) -> str:
    return _HTML_SUB_PATTERN.sub(lambda match: _subscript_fragment(_clean_text(match.group(1))), text)


def _looks_like_formula(token: str) -> bool:
    cleaned = _clean_text(token)
    if len(cleaned) <= 2 or "_" in cleaned or "/" in cleaned or ":" in cleaned or "#" in cleaned or "%" in cleaned or "=" in cleaned:
        return False
    if not any(char.isdigit() for char in cleaned):
        return False
    segments = re.split(r"[·\-–]", cleaned)
    return all(segment and _FORMULA_SEGMENT_PATTERN.fullmatch(segment) for segment in segments)


def _format_formula_token(token: str) -> str:
    output: list[str] = []
    subscript_run = False
    for char in token:
        if char.isdigit():
            if subscript_run:
                output.append(_subscript_fragment(char))
            else:
                output.append(char)
            continue
        output.append(char)
        subscript_run = char.isalpha() or char in {")", "]"}
        if char in {"·", "-", "–"}:
            subscript_run = False
    return "".join(output)


def _format_plain_segment(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if not _looks_like_formula(token):
            return token
        return _format_formula_token(token)

    cursor = 0
    protected_ranges: list[tuple[int, int]] = []
    for pattern in (_URL_PATTERN, _DOI_PATTERN):
        for match in pattern.finditer(text):
            protected_ranges.append((match.start(), match.end()))
    protected_ranges.sort()

    chunks: list[str] = []
    for start, end in protected_ranges:
        if start < cursor:
            continue
        if start > cursor:
            chunks.append(_FORMULA_TOKEN_PATTERN.sub(replace, text[cursor:start]))
        chunks.append(text[start:end])
        cursor = end
    if cursor < len(text):
        chunks.append(_FORMULA_TOKEN_PATTERN.sub(replace, text[cursor:]))
    return "".join(chunks)


def format_chemical_formula_text(value: Any) -> str:
    text = _normalize_html_subscripts(str(value or ""))
    if not text:
        return ""

    result: list[str] = []
    cursor = 0
    for match in _MARKDOWN_LINK_PATTERN.finditer(text):
        if match.start() > cursor:
            result.append(_format_plain_segment(text[cursor:match.start()]))
        label, url = match.group(1), match.group(2)
        result.append(f"[{_format_plain_segment(label)}]({url})")
        cursor = match.end()
    if cursor < len(text):
        result.append(_format_plain_segment(text[cursor:]))
    return "".join(result)
