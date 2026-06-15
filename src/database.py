from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from neo4j import GraphDatabase

from src.config import settings

_driver = None


def get_driver():
    """Get or create the global Neo4j driver."""
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
    return _driver


class Neo4jConnection:
    def __init__(
        self,
        uri: str = settings.neo4j_uri,
        username: str = settings.neo4j_username,
        password: str = settings.neo4j_password,
        database: str = settings.neo4j_database,
    ) -> None:
        self.database = database
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def verify(self) -> None:
        self.driver.verify_connectivity()

    def close(self) -> None:
        self.driver.close()

    def run_query(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def execute_write(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        def _tx_run(tx: Any) -> list[dict[str, Any]]:
            result = tx.run(query, parameters or {})
            return [record.data() for record in result]

        with self.driver.session(database=self.database) as session:
            return session.execute_write(_tx_run)


def chunked(rows: list[dict[str, Any]], batch_size: int = 500) -> Iterable[list[dict[str, Any]]]:
    for index in range(0, len(rows), batch_size):
        yield rows[index : index + batch_size]
