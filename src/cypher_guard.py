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
    "MUTATE",
}

ALLOWED_PREFIXES = ("MATCH", "WITH", "RETURN", "CALL DB.", "CALL GDS.")

BLOCKED_CALL_PATTERNS = [
    re.compile(r"\bCALL\s+GDS\.[A-Z0-9_.]*\.(?:WRITE|MUTATE)\b", re.IGNORECASE),
    re.compile(r"\bCALL\s+GDS\.GRAPH\.(?:DROP|PROJECT|CREATE|DELETE|REMOVE)\b", re.IGNORECASE),
]


def strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:cypher)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return cleaned


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", strip_code_fences(query)).strip()


def validate_read_only_cypher(query: str) -> str:
    if query is None or not query:
        raise ValueError("Query Cypher kosong atau tidak valid.")

    normalized = normalize_query(query)
    upper = normalized.upper()

    if not normalized:
        raise ValueError("Query Cypher kosong.")

    if ";" in normalized[:-1]:
        raise ValueError("Hanya satu query Cypher yang diperbolehkan.")

    if not upper.startswith(ALLOWED_PREFIXES):
        raise ValueError("Query harus berupa query baca, misalnya MATCH ... RETURN ...")

    for pattern in BLOCKED_CALL_PATTERNS:
        if pattern.search(normalized):
            raise ValueError("Query Graph ML write/mutate/drop tidak boleh dijalankan dari LLM.")

    if " RETURN " not in upper and not upper.startswith("RETURN "):
        raise ValueError("Query harus memiliki RETURN clause.")

    return_pos = upper.find(" RETURN ")
    limit_pos = upper.find(" LIMIT ")
    if limit_pos > 0 and limit_pos < return_pos:
        raise ValueError("LIMIT harus datang SETELAH RETURN clause.")

    for keyword in WRITE_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", upper):
            raise ValueError(f"Query mengandung keyword yang tidak aman: {keyword}")

    if " LIMIT " not in f" {upper} ":
        normalized = f"{normalized.rstrip(';')} LIMIT 25"

    return normalized.rstrip(";")


def split_cypher_queries(text: str) -> list[str]:
    if not text:
        return []

    parts = re.split(r"\n-{3,}\n", text.strip())
    queries: list[str] = []

    for part in parts:
        cleaned = normalize_query(part)
        if not cleaned:
            continue

        if cleaned.upper().startswith("MATCH") or cleaned.upper().startswith("WITH") or cleaned.upper().startswith("RETURN"):
            queries.append(validate_read_only_cypher(cleaned))

    return queries
