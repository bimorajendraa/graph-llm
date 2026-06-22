from __future__ import annotations

import pytest

from src.cypher_guard import (
    normalize_query,
    split_cypher_queries,
    strip_code_fences,
    validate_read_only_cypher,
)


class TestStripCodeFences:
    def test_removes_plain_fence(self) -> None:
        text = "```\nMATCH (a) RETURN a\n```"
        assert strip_code_fences(text) == "MATCH (a) RETURN a"

    def test_removes_cypher_language_fence(self) -> None:
        text = "```cypher\nMATCH (a) RETURN a\n```"
        assert strip_code_fences(text) == "MATCH (a) RETURN a"

    def test_text_without_fence_is_unchanged(self) -> None:
        text = "MATCH (a) RETURN a"
        assert strip_code_fences(text) == text


class TestNormalizeQuery:
    def test_collapses_whitespace(self) -> None:
        text = "MATCH (a)\n   RETURN   a"
        assert normalize_query(text) == "MATCH (a) RETURN a"


class TestValidateReadOnlyCypher:
    def test_valid_query_with_limit_passes_unchanged(self) -> None:
        query = "MATCH (a:Alumni) RETURN a.name LIMIT 10"
        assert validate_read_only_cypher(query) == query

    def test_limit_is_appended_when_missing(self) -> None:
        query = "MATCH (a:Alumni) RETURN a.name"
        result = validate_read_only_cypher(query)
        assert result.upper().endswith("LIMIT 25")

    def test_empty_query_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_read_only_cypher("")

    def test_none_query_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_read_only_cypher(None)  # type: ignore[arg-type]

    def test_missing_return_clause_raises(self) -> None:
        with pytest.raises(ValueError, match="RETURN"):
            validate_read_only_cypher("MATCH (a:Alumni)")

    def test_query_not_starting_with_allowed_prefix_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_read_only_cypher("EXPLAIN MATCH (a:Alumni) RETURN a")

    @pytest.mark.parametrize(
        "keyword",
        ["CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP", "LOAD"],
    )
    def test_write_keywords_are_rejected(self, keyword: str) -> None:
        query = f"MATCH (a:Alumni) {keyword} a.flag = true RETURN a"
        with pytest.raises(ValueError, match="tidak aman"):
            validate_read_only_cypher(query)

    def test_multiple_statements_with_semicolon_raises(self) -> None:
        query = "MATCH (a:Alumni) RETURN a.name; MATCH (b) RETURN b"
        with pytest.raises(ValueError, match="satu query"):
            validate_read_only_cypher(query)

    def test_trailing_semicolon_alone_is_allowed(self) -> None:
        query = "MATCH (a:Alumni) RETURN a.name LIMIT 5;"
        result = validate_read_only_cypher(query)
        assert not result.endswith(";")

    def test_limit_before_return_raises(self) -> None:
        # Pathological case where LIMIT keyword appears (e.g. inside an
        # earlier clause) before the RETURN clause itself.
        query = "MATCH (a:Alumni) WITH a LIMIT 5 RETURN a.name"
        with pytest.raises(ValueError, match="SETELAH"):
            validate_read_only_cypher(query)

    def test_call_db_prefix_is_allowed(self) -> None:
        query = "CALL db.labels() YIELD label RETURN label LIMIT 25"
        assert validate_read_only_cypher(query) == query

    def test_call_gds_prefix_is_allowed(self) -> None:
        query = "CALL gds.louvain.stream('alumniGraph') YIELD nodeId RETURN nodeId LIMIT 25"
        assert validate_read_only_cypher(query) == query

    def test_code_fence_is_stripped_before_validation(self) -> None:
        query = "```cypher\nMATCH (a:Alumni) RETURN a.name LIMIT 5\n```"
        result = validate_read_only_cypher(query)
        assert "```" not in result


class TestSplitCypherQueries:
    def test_empty_text_returns_empty_list(self) -> None:
        assert split_cypher_queries("") == []
        assert split_cypher_queries(None) == []  # type: ignore[arg-type]

    def test_single_query_returns_single_item(self) -> None:
        text = "MATCH (a:Alumni) RETURN a.name LIMIT 25"
        result = split_cypher_queries(text)
        assert len(result) == 1
        assert result[0] == text

    def test_multiple_queries_split_on_triple_dash(self) -> None:
        text = (
            "MATCH (a:Alumni) RETURN count(a) AS total LIMIT 25\n"
            "---\n"
            "MATCH (a:Alumni) RETURN a.name LIMIT 25"
        )
        result = split_cypher_queries(text)
        assert len(result) == 2

    def test_non_cypher_text_yields_no_queries(self) -> None:
        text = "Maaf, saya tidak bisa membantu dengan itu."
        assert split_cypher_queries(text) == []

    def test_invalid_query_among_valid_ones_raises(self) -> None:
        # split_cypher_queries delegates validation to validate_read_only_cypher,
        # so a write query slipped in should still raise.
        text = (
            "MATCH (a:Alumni) RETURN a.name LIMIT 25\n"
            "---\n"
            "MATCH (a:Alumni) DELETE a RETURN a"
        )
        with pytest.raises(ValueError):
            split_cypher_queries(text)