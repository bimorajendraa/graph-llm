from __future__ import annotations

import pytest

from src.entity_resolver import (
    ALIASES,
    normalize_name,
    normalize_text,
    resolve_entity,
    resolve_label,
    split_multi_value,
)


class TestNormalizeText:
    def test_strips_surrounding_whitespace(self) -> None:
        assert normalize_text("  Ari Lasso  ") == "Ari Lasso"

    def test_collapses_internal_whitespace(self) -> None:
        assert normalize_text("Ari   Lasso") == "Ari Lasso"

    def test_none_returns_empty_string(self) -> None:
        assert normalize_text(None) == ""

    @pytest.mark.parametrize("token", ["", "-", "--", "na", "N/A", "nan", "None", "null"])
    def test_missing_tokens_become_empty_string(self, token: str) -> None:
        assert normalize_text(token) == ""

    def test_non_string_input_is_stringified(self) -> None:
        assert normalize_text(123) == "123"


class TestNormalizeName:
    def test_casefolds_the_result(self) -> None:
        assert normalize_name("Institut Teknologi Bandung") == "institut teknologi bandung"

    def test_missing_token_returns_empty_string(self) -> None:
        assert normalize_name("-") == ""


class TestResolveEntity:
    def test_known_alias_is_expanded(self) -> None:
        assert resolve_entity("itb") == ALIASES["itb"]
        assert resolve_entity("UGM") == ALIASES["ugm"]

    def test_alias_lookup_is_case_insensitive(self) -> None:
        assert resolve_entity("Itb") == ALIASES["itb"]

    def test_exact_candidate_match(self) -> None:
        candidates = ["Universitas Indonesia", "Institut Teknologi Bandung"]
        assert resolve_entity("Universitas Indonesia", candidates=candidates) == "Universitas Indonesia"

    def test_close_typo_resolves_via_fuzzy_match(self) -> None:
        candidates = ["Institut Teknologi Bandung", "Universitas Gadjah Mada"]
        result = resolve_entity("Institut Tekhnologi Bandung", candidates=candidates)
        assert result == "Institut Teknologi Bandung"

    def test_unrelated_name_falls_back_to_original(self) -> None:
        candidates = ["Institut Teknologi Bandung", "Universitas Gadjah Mada"]
        result = resolve_entity("Sekolah Tinggi Hukum Z", candidates=candidates)
        assert result == "Sekolah Tinggi Hukum Z"


class TestSplitMultiValue:
    def test_splits_on_semicolon_and_pipe(self) -> None:
        assert split_multi_value("Dokter; Pengusaha|Politisi") == ["Dokter", "Pengusaha", "Politisi"]

    def test_does_not_split_on_comma_by_default(self) -> None:
        assert split_multi_value("Dokter, Pengusaha") == ["Dokter, Pengusaha"]

    def test_splits_on_comma_when_requested(self) -> None:
        assert split_multi_value("Dokter, Pengusaha", split_commas=True) == ["Dokter", "Pengusaha"]

    def test_missing_value_returns_empty_list(self) -> None:
        assert split_multi_value("-") == []
        assert split_multi_value(None) == []

    def test_empty_segments_are_dropped(self) -> None:
        assert split_multi_value("Dokter;;Pengusaha") == ["Dokter", "Pengusaha"]


class TestResolveLabel:
    def test_exact_match(self) -> None:
        allowed = {"Universitas Indonesia", "Institut Teknologi Bandung"}
        assert resolve_label("Universitas Indonesia", allowed) == "Universitas Indonesia"

    def test_case_insensitive_match(self) -> None:
        allowed = {"Universitas Indonesia", "Institut Teknologi Bandung"}
        assert resolve_label("universitas indonesia", allowed) == "Universitas Indonesia"

    def test_no_match_returns_none(self) -> None:
        allowed = {"Universitas Indonesia"}
        assert resolve_label("Institut Teknologi Bandung", allowed) is None