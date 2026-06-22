from __future__ import annotations

from typing import Any

from src.database import Neo4jConnection


BASE_RELATIONSHIP_TYPES = [
    "LULUSAN_DARI",
    "BEKERJA_SEBAGAI",
    "BEKERJA_DI",
    "MENJABAT_SEBAGAI",
]
SIMILARITY_RELATIONSHIP_TYPES = [
    "MIRIP_DENGAN",
]
NODE_LABELS = ["Alumni", "University", "Occupation", "Employer", "Position"]


class GraphAnalytics:
    def __init__(self, db: Neo4jConnection) -> None:
        self.db = db

    def top_connected_alumni(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.db.run_query(
            """
            MATCH (a:Alumni)-[r]-()
            RETURN a.alumniId AS alumniId, a.name AS name, count(r) AS degree
            ORDER BY degree DESC, name
            LIMIT $limit
            """,
            {"limit": limit},
        )

    def university_alumni_counts(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.db.run_query(
            """
            MATCH (a:Alumni)-[:LULUSAN_DARI]->(u:University)
            RETURN u.name AS university, count(DISTINCT a) AS alumniCount
            ORDER BY alumniCount DESC, university
            LIMIT $limit
            """,
            {"limit": limit},
        )

    def occupation_counts(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.db.run_query(
            """
            MATCH (a:Alumni)-[:BEKERJA_SEBAGAI]->(o:Occupation)
            RETURN o.name AS occupation, count(DISTINCT a) AS alumniCount
            ORDER BY alumniCount DESC, occupation
            LIMIT $limit
            """,
            {"limit": limit},
        )

    def available_relationship_types(self) -> set[str]:
        rows = self.db.run_query(
            """
            MATCH ()-[r]->()
            RETURN collect(DISTINCT type(r)) AS relationshipTypes
            """
        )
        if not rows:
            return set()
        return set(rows[0].get("relationshipTypes") or [])

    def create_gds_projection(
        self,
        graph_name: str = "alumniGraph",
        include_embeddings: bool = False,
        include_similarity: bool = False,
    ) -> list[dict[str, Any]]:
        existing_relationships = self.available_relationship_types()
        base_relationships = [
            relationship for relationship in BASE_RELATIONSHIP_TYPES if relationship in existing_relationships
        ]

        if not base_relationships:
            raise RuntimeError(
                "Graph Neo4j belum memiliki relationship hasil import. "
                "Jalankan ulang import graph terlebih dahulu: "
                "python -m src.graph_builder --processed-dir data/processed"
            )

        relationship_types = [
            *base_relationships,
            *[
                relationship
                for relationship in SIMILARITY_RELATIONSHIP_TYPES
                if include_similarity and relationship in existing_relationships
            ],
        ]
        relationship_projection = {
            relationship: {"orientation": "UNDIRECTED"}
            for relationship in relationship_types
        }
        node_projection: list[str] | dict[str, dict[str, Any]]
        if include_embeddings:
            node_projection = {label: {} for label in NODE_LABELS}
            node_projection["Alumni"] = {"properties": ["embedding"]}
        else:
            node_projection = NODE_LABELS

        self.db.run_query(
            """
            CALL gds.graph.drop($graphName, false)
            YIELD graphName
            RETURN graphName
            """,
            {"graphName": graph_name},
        )
        return self.db.run_query(
            """
            CALL gds.graph.project(
              $graphName,
              $nodeProjection,
              $relationshipProjection
            )
            YIELD graphName, nodeCount, relationshipCount
            RETURN graphName, nodeCount, relationshipCount, $relationshipTypes AS relationshipTypes
            """,
            {
                "graphName": graph_name,
                "nodeProjection": node_projection,
                "relationshipProjection": relationship_projection,
                "relationshipTypes": relationship_types,
            },
        )

    def page_rank(self, graph_name: str = "alumniGraph", limit: int = 20) -> list[dict[str, Any]]:
        return self.db.run_query(
            """
            CALL gds.pageRank.stream($graphName)
            YIELD nodeId, score
            WITH gds.util.asNode(nodeId) AS node, score
            WHERE node:Alumni
            RETURN node.alumniId AS alumniId, node.name AS name, score
            ORDER BY score DESC
            LIMIT $limit
            """,
            {"graphName": graph_name, "limit": limit},
        )
