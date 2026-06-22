from __future__ import annotations

from typing import Any

from src.database import Neo4jConnection


class GraphMachineLearning:
    def __init__(self, db: Neo4jConnection) -> None:
        self.db = db

    def write_louvain_clusters(self, graph_name: str = "alumniGraph") -> list[dict[str, Any]]:
        return self.db.run_query(
            """
            CALL gds.louvain.write($graphName, {writeProperty: 'clusterId'})
            YIELD communityCount, modularity, nodePropertiesWritten
            RETURN communityCount, modularity, nodePropertiesWritten
            """,
            {"graphName": graph_name},
        )

    def write_fast_rp_embeddings(self, graph_name: str = "alumniGraph", dimensions: int = 64) -> list[dict[str, Any]]:
        return self.db.run_query(
            """
            CALL gds.fastRP.write($graphName, {
              embeddingDimension: $dimensions,
              writeProperty: 'embedding'
            })
            YIELD nodePropertiesWritten
            RETURN nodePropertiesWritten
            """,
            {"graphName": graph_name, "dimensions": dimensions},
        )

    def write_knn_similarity(self, graph_name: str = "alumniGraph", top_k: int = 5) -> list[dict[str, Any]]:
        return self.db.run_query(
            """
            CALL gds.nodeSimilarity.write($graphName, {
              nodeLabels: ['Alumni'],
              writeRelationshipType: 'MIRIP_DENGAN',
              writeProperty: 'score',
              topK: $topK,
              similarityCutoff: 0.0001
            })
            YIELD nodesCompared, relationshipsWritten
            RETURN nodesCompared, relationshipsWritten
            """,
            {"graphName": graph_name, "topK": top_k},
        )

    def similar_alumni(self, alumni_name: str, limit: int = 10) -> list[dict[str, Any]]:
        return self.db.run_query(
            """
            MATCH (a:Alumni)-[r:MIRIP_DENGAN]-(other:Alumni)
            WHERE toLower(a.name) CONTAINS toLower($name)
            RETURN a.name AS alumni, other.name AS similarAlumni, r.score AS score
            ORDER BY score DESC
            LIMIT $limit
            """,
            {"name": alumni_name, "limit": limit},
        )
