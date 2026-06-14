from __future__ import annotations

from typing import Any

from src.cypher_guard import validate_read_only_cypher
from src.database import Neo4jConnection
from src.llm_client import OpenRouterClient, build_system_message, build_user_message


SCHEMA_PROMPT = """
Anda adalah asisten Text-to-Cypher untuk AlumniGraph AI.
Gunakan hanya schema aktual berikut:

Node:
- Alumni(alumniId, name, normalizedName, description, source, clusterId, embedding)
- University(name, normalizedName, source)
- Occupation(name, normalizedName, source)
- Employer(name, normalizedName, source)
- Position(name, normalizedName, source)

Relationship:
- (:Alumni)-[:LULUSAN_DARI]->(:University)
- (:Alumni)-[:BEKERJA_SEBAGAI]->(:Occupation)
- (:Alumni)-[:BEKERJA_DI]->(:Employer)
- (:Alumni)-[:MENJABAT_SEBAGAI]->(:Position)
- (:Alumni)-[:MIRIP_DENGAN]->(:Alumni)

Aturan:
- Jawab hanya dengan satu query Cypher.
- Query harus read-only.
- Selalu beri LIMIT maksimal 25 jika query mengembalikan banyak data.
- Jangan memakai properti yang tidak ada di schema.
"""


class TextToCypher:
    def __init__(self, llm: OpenRouterClient | None = None, db: Neo4jConnection | None = None) -> None:
        self.llm = llm or OpenRouterClient()
        self.db = db

    def generate(self, question: str) -> str:
        response = self.llm.chat(
            [
                build_system_message(SCHEMA_PROMPT),
                build_user_message(f"Pertanyaan: {question}\n\nCypher:"),
            ],
            temperature=0.0,
            max_tokens=600,
        )
        return validate_read_only_cypher(response)

    def ask(self, question: str) -> dict[str, Any]:
        if self.db is None:
            raise ValueError("Neo4jConnection belum diberikan.")
        cypher = self.generate(question)
        rows = self.db.run_query(cypher)
        return {"question": question, "cypher": cypher, "rows": rows}
