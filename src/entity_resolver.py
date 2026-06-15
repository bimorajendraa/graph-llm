from __future__ import annotations
from rapidfuzz import process, fuzz
from src.database import get_driver

import re


MISSING_TOKENS = {"", "-", "--", "na", "n/a", "nan", "none", "null"}
ALIASES = {"ugm": "Universitas Gadjah Mada", "itb": "Institut Teknologi Bandung",
           "ui": "Universitas Indonesia", "its": "Institut Teknologi Sepuluh Nopember",
           "unair": "Universitas Airlangga", "ipb": "Institut Pertanian Bogor",
           "undip": "Universitas Diponegoro", "uns": "Universitas Sebelas Maret",
           "unpad": "Universitas Padjadjaran"}


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return "" if text.casefold() in MISSING_TOKENS else text

def normalize_name(value: object) -> str:
    return normalize_text(value).casefold()

def get_known_universities():
    with get_driver().session() as s:
        return [r["name"] for r in s.run("MATCH (u:University) RETURN u.name AS name")]

def resolve_entity(name: str, candidates=None) -> str:
    key = name.strip().lower()
    if key in ALIASES:
        return ALIASES[key]
    candidates = candidates or get_known_universities()
    match, score, _ = process.extractOne(name, candidates, scorer=fuzz.WRatio)
    return match if score >= 80 else name


def split_multi_value(value: object, split_commas: bool = False) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []

    separators = r"[;|/]+"
    if split_commas:
        separators = r"[,;|/]+"

    return [part for part in (normalize_text(item) for item in re.split(separators, text)) if part]


def resolve_label(label: str, allowed_labels: set[str]) -> str | None:
    normalized_label = normalize_name(label)
    for candidate in allowed_labels:
        if normalize_name(candidate) == normalized_label:
            return candidate
    return None
