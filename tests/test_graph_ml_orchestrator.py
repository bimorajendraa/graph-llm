from __future__ import annotations

from typing import Any

import pytest

from src.graph_ml_orchestrator import GraphMLOrchestrator


class FakeDb:
    def __init__(self) -> None:
        self.alumni_count = 10
        self.embedding_count = 0
        self.cluster_count = 0
        self.rel_count = 0
        self.queries: list[str] = []

    def run_query(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self.queries.append(query)
        if "count(a) AS total" in query:
            return [{"total": self.alumni_count}]
        if "embeddingCount" in query:
            return [
                {
                    "alumniCount": self.alumni_count,
                    "embeddingCount": self.embedding_count,
                    "clusterCount": self.cluster_count,
                }
            ]
        if "relCount" in query:
            return [{"relCount": self.rel_count}]
        return []


class FakeAnalytics:
    def __init__(self) -> None:
        self.called = False
        self.calls: list[dict[str, Any]] = []

    def create_gds_projection(
        self,
        graph_name: str,
        include_embeddings: bool = False,
        include_similarity: bool = False,
    ) -> list[dict[str, Any]]:
        self.called = True
        self.calls.append(
            {
                "graph_name": graph_name,
                "include_embeddings": include_embeddings,
                "include_similarity": include_similarity,
            }
        )
        return [{"graphName": graph_name}]


class FakeML:
    def __init__(self) -> None:
        self.louvain_called = False
        self.embedding_called = False
        self.knn_called = False

    def write_louvain_clusters(self, graph_name: str) -> list[dict[str, Any]]:
        self.louvain_called = True
        return [{"communityCount": 1}]

    def write_fast_rp_embeddings(self, graph_name: str, dimensions: int = 64) -> list[dict[str, Any]]:
        self.embedding_called = True
        return [{"nodePropertiesWritten": 10, "dimensions": dimensions}]

    def write_knn_similarity(self, graph_name: str, top_k: int = 5) -> list[dict[str, Any]]:
        self.knn_called = True
        return [{"relationshipsWritten": 20, "topK": top_k}]


def _orchestrator_with_fakes(db: FakeDb) -> tuple[GraphMLOrchestrator, FakeAnalytics, FakeML]:
    orchestrator = GraphMLOrchestrator(db)  # type: ignore[arg-type]
    analytics = FakeAnalytics()
    ml = FakeML()
    orchestrator.analytics = analytics  # type: ignore[assignment]
    orchestrator.ml = ml  # type: ignore[assignment]
    return orchestrator, analytics, ml


def test_needs_ml_detects_similarity_question() -> None:
    orchestrator = GraphMLOrchestrator(FakeDb())  # type: ignore[arg-type]
    assert orchestrator.needs_ml("Siapa alumni yang paling mirip?")
    assert orchestrator.needs_ml("Alumni berpengaruh itu masuk cluster apa?")
    assert not orchestrator.needs_ml("Berapa alumni dari ITB?")


def test_non_ml_question_does_not_query_status() -> None:
    db = FakeDb()
    orchestrator = GraphMLOrchestrator(db)  # type: ignore[arg-type]
    result = orchestrator.ensure_ml_ready("Berapa alumni dari ITB?")
    assert result["needed"] is False
    assert db.queries == []


def test_empty_graph_raises_clear_error() -> None:
    db = FakeDb()
    db.alumni_count = 0
    orchestrator = GraphMLOrchestrator(db)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="belum berisi node Alumni"):
        orchestrator.ensure_ml_ready("alumni yang mirip")


def test_ready_ml_skips_pipeline() -> None:
    db = FakeDb()
    db.embedding_count = 10
    db.cluster_count = 10
    db.rel_count = 20
    orchestrator, analytics, ml = _orchestrator_with_fakes(db)
    result = orchestrator.ensure_ml_ready("alumni yang mirip")
    assert result["ran"] is False
    assert analytics.called is False
    assert ml.knn_called is False


def test_incomplete_ml_runs_pipeline() -> None:
    db = FakeDb()
    orchestrator, analytics, ml = _orchestrator_with_fakes(db)
    result = orchestrator.ensure_ml_ready("rekomendasi alumni serupa")
    assert result["ran"] is True
    assert analytics.called is True
    assert analytics.calls[0]["include_embeddings"] is False
    assert analytics.calls[1]["include_embeddings"] is True
    assert ml.louvain_called is True
    assert ml.embedding_called is True
    assert ml.knn_called is True
