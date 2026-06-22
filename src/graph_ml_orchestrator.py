from __future__ import annotations

import re
from typing import Any

from src.database import Neo4jConnection
from src.graph_analytics import GraphAnalytics
from src.graph_ml import GraphMachineLearning
from src.logger import get_logger


logger = get_logger(__name__)

ML_HINT_PATTERN = re.compile(
    r"\b("
    r"mirip|serupa|similar|similarity|rekomen|rekomendasi|"
    r"cluster|komunitas|kelompok|"
    r"pengaruh besar|berpengaruh|paling berpengaruh"
    r")\b",
    re.IGNORECASE,
)


class GraphMLOrchestrator:
    def __init__(self, db: Neo4jConnection, graph_name: str = "alumniGraph") -> None:
        self.db = db
        self.graph_name = graph_name
        self.analytics = GraphAnalytics(db)
        self.ml = GraphMachineLearning(db)

    def needs_ml(self, question: str) -> bool:
        return bool(ML_HINT_PATTERN.search(question or ""))

    def graph_has_alumni(self) -> bool:
        rows = self.db.run_query("MATCH (a:Alumni) RETURN count(a) AS total")
        return bool(rows and rows[0].get("total", 0) > 0)

    def ml_status(self) -> dict[str, int]:
        rows = self.db.run_query(
            """
            MATCH (a:Alumni)
            RETURN
              count(a) AS alumniCount,
              count(CASE WHEN a.embedding IS NOT NULL THEN 1 END) AS embeddingCount,
              count(CASE WHEN a.clusterId IS NOT NULL THEN 1 END) AS clusterCount
            """
        )
        rel_rows = self.db.run_query(
            "MATCH (:Alumni)-[r:MIRIP_DENGAN]-(:Alumni) RETURN count(r) AS relCount"
        )

        row = rows[0] if rows else {}
        rel_row = rel_rows[0] if rel_rows else {}

        return {
            "alumniCount": int(row.get("alumniCount", 0) or 0),
            "embeddingCount": int(row.get("embeddingCount", 0) or 0),
            "clusterCount": int(row.get("clusterCount", 0) or 0),
            "similarityRelCount": int(rel_row.get("relCount", 0) or 0),
        }

    def is_ml_ready(self) -> bool:
        status = self.ml_status()
        alumni_count = status["alumniCount"]
        if alumni_count == 0:
            return False
        return (
            status["embeddingCount"] > 0
            and status["clusterCount"] > 0
            and status["similarityRelCount"] > 0
        )

    def ensure_ml_ready(self, question: str | None = None, force: bool = False) -> dict[str, Any]:
        if question is not None and not self.needs_ml(question) and not force:
            return {
                "needed": False,
                "ran": False,
                "message": "Pertanyaan tidak membutuhkan Graph ML.",
            }

        if not self.graph_has_alumni():
            raise RuntimeError(
                "Graph Neo4j belum berisi node Alumni. Jalankan import terlebih dahulu: "
                "python -m src.graph_builder --processed-dir data/processed"
            )

        before = self.ml_status()
        if self.is_ml_ready() and not force:
            logger.info("Graph ML sudah tersedia, melewati proses ML.")
            return {
                "needed": True,
                "ran": False,
                "status": before,
                "message": "Graph ML sudah tersedia.",
            }

        logger.info("Graph ML belum tersedia/lengkap, menjalankan pipeline...")

        try:
            projection = self.analytics.create_gds_projection(self.graph_name)
            louvain = self.ml.write_louvain_clusters(self.graph_name)
            embedding = self.ml.write_fast_rp_embeddings(self.graph_name, dimensions=64)
            embedding_projection = self.analytics.create_gds_projection(
                self.graph_name,
                include_embeddings=True,
            )
            knn = self.ml.write_knn_similarity(self.graph_name, top_k=5)
        except Exception as exc:
            raise RuntimeError(self._format_pipeline_error(exc)) from exc

        after = self.ml_status()
        logger.info("Graph ML selesai: embeddings, clusterId, dan MIRIP_DENGAN tersedia.")

        return {
            "needed": True,
            "ran": True,
            "before": before,
            "after": after,
            "projection": projection,
            "embedding_projection": embedding_projection,
            "louvain": louvain,
            "embedding": embedding,
            "knn": knn,
            "message": "Graph ML pipeline selesai dijalankan.",
        }

    def _format_pipeline_error(self, exc: Exception) -> str:
        message = str(exc)
        lowered = message.casefold()

        if "relationship projection" in lowered or "relationship types not found" in lowered:
            return (
                "GDS projection gagal karena relationship graph belum lengkap. "
                "Jalankan ulang import graph terlebih dahulu: "
                "python -m src.graph_builder --processed-dir data/processed. "
                f"Detail: {message}"
            )

        if "empty" in lowered or "node" in lowered or "relationship" in lowered:
            return (
                "GDS projection gagal. Pastikan graph Neo4j sudah berisi node dan relationship "
                "hasil import. Detail: "
                f"{message}"
            )

        if "gds" in lowered or "procedure" in lowered:
            return (
                "Graph ML gagal dijalankan. Pastikan Neo4j Graph Data Science plugin aktif. "
                f"Detail: {message}"
            )

        return f"Graph ML pipeline gagal dijalankan. Detail: {message}"
