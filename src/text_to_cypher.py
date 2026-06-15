from __future__ import annotations

import re
from typing import Any

from src.cypher_guard import split_cypher_queries, validate_read_only_cypher
from src.database import Neo4jConnection
from src.entity_resolver import ALIASES
from src.llm_client import OpenRouterClient, build_system_message, build_user_message
from src.logger import get_logger

logger = get_logger(__name__)

SCHEMA_PROMPT = """
Anda adalah asisten Text-to-Cypher untuk AlumniGraph AI yang sangat pintar dan detail.

SCHEMA NODE DAN RELATIONSHIP:
- Alumni(alumniId, name, normalizedName, description, source, clusterId, embedding)
- University(name, normalizedName, source)
- Occupation(name, normalizedName, source)
- Employer(name, normalizedName, source)
- Position(name, normalizedName, source)
- (:Alumni)-[:LULUSAN_DARI]->(:University)
- (:Alumni)-[:BEKERJA_SEBAGAI]->(:Occupation)
- (:Alumni)-[:BEKERJA_DI]->(:Employer)
- (:Alumni)-[:MENJABAT_SEBAGAI]->(:Position)

UNIVERSITAS ALIASES:
UGM=Universitas Gadjah Mada, ITB=Institut Teknologi Bandung, UI=Universitas Indonesia,
ITS=Institut Teknologi Sepuluh Nopember, UNAIR=Universitas Airlangga, IPB=Institut Pertanian Bogor,
UNDIP=Universitas Diponegoro, UNS=Universitas Sebelas Maret, UNPAD=Universitas Padjadjaran

CONTEKS PERCAPAKAPAN:
Gunakan konteks percakapan sebelumnya jika pertanyaan adalah follow-up seperti "Kalau dari universitas lain?" atau "Lainnya?".

INSTRUKSI WAJIB:
1. Setiap query HARUS diakhiri dengan RETURN statement.
2. LIMIT maksimal 25 harus ada dalam RETURN clause: "RETURN ... LIMIT 25".
3. Gunakan count(), collect(), atau aggregate functions bila perlu.
4. Jika pertanyaan memerlukan multiple queries, pisahkan dengan "---" (tiga dash).
5. Jawab HANYA dengan query Cypher, tanpa penjelasan atau markdown.
6. Konversi alias universitas ke nama lengkap.

CONTOH:
Q: Berapa banyak alumni dari ITB?
A: MATCH (a:Alumni)-[:LULUSAN_DARI]->(u:University {normalizedName: toLower('Institut Teknologi Bandung')}) RETURN count(a) AS jumlah LIMIT 25

Q: Siapa nama alumni dari ITS?
A: MATCH (a:Alumni)-[:LULUSAN_DARI]->(u:University {normalizedName: toLower('Institut Teknologi Sepuluh Nopember')}) RETURN a.name LIMIT 25

Q: Berapa alumni dari ITB dan siapa saja?
A: MATCH (a:Alumni)-[:LULUSAN_DARI]->(u:University {normalizedName: toLower('Institut Teknologi Bandung')}) RETURN count(a) AS total LIMIT 25
---
MATCH (a:Alumni)-[:LULUSAN_DARI]->(u:University {normalizedName: toLower('Institut Teknologi Bandung')}) RETURN a.name LIMIT 25
"""


class TextToCypher:
    def __init__(self, llm: OpenRouterClient | None = None, db: Neo4jConnection | None = None) -> None:
        self.llm = llm or OpenRouterClient()
        self.db = db

    def _rewrite_aliases(self, question: str) -> str:
        rewritten = question
        for alias, full_name in ALIASES.items():
            rewritten = re.sub(rf"\b{re.escape(alias)}\b", full_name, rewritten, flags=re.IGNORECASE)
        return rewritten

    def _build_history_text(self, history: list[dict[str, str]] | None) -> str:
        if not history:
            return ""
        lines = []
        for message in history:
            prefix = "User:" if message["role"] == "user" else "Assistant:"
            lines.append(f"{prefix} {message['content']}")
        return "History:\n" + "\n".join(lines) + "\n\n"

    def generate(self, question: str, history: list[dict[str, str]] | None = None) -> list[str]:
        question_text = self._rewrite_aliases(question)
        prompt = self._build_history_text(history) + f"Pertanyaan: {question_text}"
        response = self.llm.chat(
            [
                build_system_message(SCHEMA_PROMPT),
                build_user_message(prompt),
            ],
            temperature=0.0,
            max_tokens=900,
        )

        if not response:
            raise ValueError("LLM tidak mengembalikan response yang valid.")

        logger.debug(f"LLM response untuk '{question}': {response}")
        queries = split_cypher_queries(response)
        if not queries:
            raise ValueError("Tidak ditemukan query Cypher yang valid dalam respons LLM.")

        return queries

    def ask(self, question: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        if self.db is None:
            raise ValueError("Neo4jConnection belum diberikan.")
        queries = self.generate(question, history=history)
        results: list[dict[str, Any]] = []
        for query in queries:
            rows = self.db.run_query(query)
            results.append({"query": query, "rows": rows})
        return {"question": question, "queries": results}
