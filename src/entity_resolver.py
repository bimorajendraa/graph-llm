from __future__ import annotations

import re


MISSING_TOKENS = {"", "-", "--", "na", "n/a", "nan", "none", "null"}


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return "" if text.casefold() in MISSING_TOKENS else text


def normalize_name(value: object) -> str:
    return normalize_text(value).casefold()


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
