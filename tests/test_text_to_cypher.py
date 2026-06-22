from __future__ import annotations

import pytest

from src.text_to_cypher import TextToCypher


class FailingLLM:
    def chat(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        raise AssertionError("LLM should not be called for deterministic similarity query")


def test_generic_similarity_question_uses_deterministic_query() -> None:
    agent = TextToCypher(llm=FailingLLM())  # type: ignore[arg-type]
    queries = agent.generate(
        "Mencari alumni dengan latar pendidikan, pekerjaan, employer, atau posisi yang mirip."
    )

    assert len(queries) == 1
    query = queries[0]
    assert "MIRIP_DENGAN" in query
    assert "similarity_score" in query
    assert "pendidikan_alumni_1" in query
    assert query.endswith("LIMIT 25")


def test_influential_similarity_question_uses_deterministic_query() -> None:
    agent = TextToCypher(llm=FailingLLM())  # type: ignore[arg-type]
    queries = agent.generate(
        "coba berikan nama salah satu alumni yang memiliki pengaruh besar dan dengan siapa dia paling mirip"
    )

    assert len(queries) == 1
    query = queries[0]
    assert "alumni_berpengaruh" in query
    assert "alumni_paling_mirip" in query
    assert "WITH a, count(rel) AS degree" in query
    assert query.endswith("LIMIT 25")


def test_non_similarity_question_still_uses_llm() -> None:
    agent = TextToCypher(llm=FailingLLM())  # type: ignore[arg-type]
    with pytest.raises(AssertionError, match="LLM should not be called"):
        agent.generate("Berapa alumni dari ITB?")
