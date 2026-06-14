from __future__ import annotations

import re


WRITE_KEYWORDS = {
    "CREATE",
    "MERGE",
    "DELETE",
    "DETACH",
    "SET",
    "REMOVE",
    "DROP",
    "LOAD",
    "CALL DBMS",
    "CALL APOC",
}

ALLOWED_PREFIXES = ("MATCH", "WITH", "RETURN", "CALL DB.", "CALL GDS.")


def strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:cypher)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return cleaned


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", strip_code_fences(query)).strip()


def validate_read_only_cypher(query: str) -> str:
    normalized = normalize_query(query)
    upper = normalized.upper()

    if not normalized:
        raise ValueError("Query Cypher kosong.")

    if ";" in normalized[:-1]:
        raise ValueError("Hanya satu query Cypher yang diperbolehkan.")

    if not upper.startswith(ALLOWED_PREFIXES):
        raise ValueError("Query harus berupa query baca, misalnya MATCH ... RETURN ...")

    for keyword in WRITE_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", upper):
            raise ValueError(f"Query mengandung keyword yang tidak aman: {keyword}")

    if " LIMIT " not in f" {upper} ":
        normalized = f"{normalized.rstrip(';')} LIMIT 25"

    return normalized.rstrip(";")
