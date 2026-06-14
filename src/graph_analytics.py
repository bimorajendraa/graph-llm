from __future__ import annotations

from typing import Any

from src.database import Neo4jConnection


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

    def create_gds_projection(self, graph_name: str = "alumniGraph") -> list[dict[str, Any]]:
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
              ['Alumni', 'University', 'Occupation', 'Employer', 'Position'],
              {
                LULUSAN_DARI: {orientation: 'UNDIRECTED'},
                BEKERJA_SEBAGAI: {orientation: 'UNDIRECTED'},
                BEKERJA_DI: {orientation: 'UNDIRECTED'},
                MENJABAT_SEBAGAI: {orientation: 'UNDIRECTED'},
                MIRIP_DENGAN: {orientation: 'UNDIRECTED'}
              }
            )
            YIELD graphName, nodeCount, relationshipCount
            RETURN graphName, nodeCount, relationshipCount
            """,
            {"graphName": graph_name},
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
