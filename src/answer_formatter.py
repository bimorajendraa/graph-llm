from __future__ import annotations

from typing import Any

from src.logger import get_logger

logger = get_logger(__name__)


class AnswerFormatter:
    """Formats graph retrieval results into natural Indonesian answers."""

    @staticmethod
    def format_results(queries: list[dict[str, Any]]) -> str:
        """Convert raw query results into a formatted answer."""
        if not queries:
            return "Tidak ada hasil retrieval."

        if len(queries) == 1:
            return AnswerFormatter._format_single_result(queries[0])

        return AnswerFormatter._format_multiple_results(queries)

    @staticmethod
    def _format_single_result(query_result: dict[str, Any]) -> str:
        """Format a single query result."""
        rows = query_result.get("rows", [])
        if not rows:
            return "Tidak ditemukan data untuk query ini."

        formatted_parts = []

        for row in rows:
            if not row:
                continue

            formatted_row = AnswerFormatter._format_row(row)
            if formatted_row:
                formatted_parts.append(formatted_row)

        if not formatted_parts:
            return f"Ditemukan {len(rows)} result(s) tanpa data detail."

        return "\n".join(formatted_parts)

    @staticmethod
    def _format_multiple_results(queries: list[dict[str, Any]]) -> str:
        """Format multiple query results."""
        parts = []
        for idx, query_result in enumerate(queries, 1):
            rows = query_result.get("rows", [])
            if rows:
                formatted = AnswerFormatter._format_single_result(query_result)
                parts.append(f"**Hasil Query {idx}:**\n{formatted}")

        return "\n\n".join(parts) if parts else "Tidak ada data ditemukan."

    @staticmethod
    def _format_row(row: dict[str, Any]) -> str:
        """Format a single row from query results."""
        if not row:
            return ""

        parts = []
        for key, value in row.items():
            if value is None or value == "":
                continue

            formatted_value = AnswerFormatter._format_value(value)
            key_display = AnswerFormatter._humanize_key(key)
            parts.append(f"• {key_display}: {formatted_value}")

        return "\n".join(parts) if parts else ""

    @staticmethod
    def _format_value(value: Any) -> str:
        """Format a single value."""
        if isinstance(value, (list, tuple)):
            if not value:
                return "(kosong)"
            return ", ".join(str(v) for v in value[:10])
        if isinstance(value, bool):
            return "Ya" if value else "Tidak"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value.strip()
        return str(value)

    @staticmethod
    def _humanize_key(key: str) -> str:
        """Convert key to human-readable format."""
        key = key.replace("_", " ").replace(".", " ")
        words = key.split()

        humanized_words = {
            "a.name": "Nama Alumni",
            "count": "Jumlah",
            "total": "Total",
            "jumlah": "Jumlah",
            "u.name": "Nama Universitas",
            "o.name": "Nama Pekerjaan",
            "e.name": "Nama Perusahaan",
            "p.name": "Nama Posisi",
        }

        full_key = key.lower()
        if full_key in humanized_words:
            return humanized_words[full_key]

        result = " ".join(word.capitalize() for word in words)
        return result

    @staticmethod
    def format_as_answer(question: str, queries: list[dict[str, Any]]) -> str:
        """Format results as a complete answer to a question."""
        formatted = AnswerFormatter.format_results(queries)
        return f"{formatted}"

    @staticmethod
    def is_count_query(rows: list[dict[str, Any]]) -> bool:
        """Check if a query is a count/aggregate query."""
        if not rows:
            return False
        first_row = rows[0]
        count_keys = {"count", "total", "jumlah", "count(a)"}
        return any(key.lower() in count_keys for key in first_row.keys())

    @staticmethod
    def extract_count(rows: list[dict[str, Any]]) -> int | None:
        """Extract count/total from query results."""
        if not rows:
            return None
        first_row = rows[0]
        for key in ["count", "total", "jumlah", "count(a)"]:
            if key in first_row:
                return int(first_row[key])
        return None
