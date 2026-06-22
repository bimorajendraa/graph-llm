from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz, process

from src.cypher_guard import split_cypher_queries, validate_read_only_cypher
from src.database import Neo4jConnection
from src.entity_resolver import ALIASES
from src.llm_client import OpenRouterClient, build_system_message, build_user_message
from src.logger import get_logger

logger = get_logger(__name__)

# Pola untuk menangkap nama universitas setelah kata depan umum dalam
# pertanyaan, mis. "alumni dari Institut Tekhnologi Bandung" atau
# "lulusan Universitas Gajah Mada". Dibatasi panjang agar tidak menangkap
# seluruh sisa kalimat.
UNIVERSITY_MENTION_PATTERN = re.compile(
    r"\b(?:dari|di|lulusan(?:\s+dari)?)\s+([A-Za-z][A-Za-z .'-]{2,60})",
    re.IGNORECASE,
)
FUZZY_MATCH_THRESHOLD = 85
GENERIC_SIMILARITY_PATTERN = re.compile(
    r"\b(mencari|cari|tampilkan|lihat|daftar|rekomendasi|rekomendasikan)\b"
    r".*\b(mirip|serupa|similar|similarity)\b",
    re.IGNORECASE,
)

GENERIC_SIMILARITY_QUERY = """
MATCH (a:Alumni)-[r:MIRIP_DENGAN]-(other:Alumni)
OPTIONAL MATCH (a)-[:LULUSAN_DARI]->(u1:University)
OPTIONAL MATCH (other)-[:LULUSAN_DARI]->(u2:University)
OPTIONAL MATCH (a)-[:BEKERJA_SEBAGAI]->(o1:Occupation)
OPTIONAL MATCH (other)-[:BEKERJA_SEBAGAI]->(o2:Occupation)
OPTIONAL MATCH (a)-[:BEKERJA_DI]->(e1:Employer)
OPTIONAL MATCH (other)-[:BEKERJA_DI]->(e2:Employer)
OPTIONAL MATCH (a)-[:MENJABAT_SEBAGAI]->(p1:Position)
OPTIONAL MATCH (other)-[:MENJABAT_SEBAGAI]->(p2:Position)
RETURN a.name AS alumni_1,
       other.name AS alumni_2,
       r.score AS similarity_score,
       collect(DISTINCT u1.name) AS pendidikan_alumni_1,
       collect(DISTINCT u2.name) AS pendidikan_alumni_2,
       collect(DISTINCT o1.name) AS pekerjaan_alumni_1,
       collect(DISTINCT o2.name) AS pekerjaan_alumni_2,
       collect(DISTINCT e1.name) AS employer_alumni_1,
       collect(DISTINCT e2.name) AS employer_alumni_2,
       collect(DISTINCT p1.name) AS posisi_alumni_1,
       collect(DISTINCT p2.name) AS posisi_alumni_2
ORDER BY similarity_score DESC
LIMIT 25
"""

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
- (:Alumni)-[:MIRIP_DENGAN {score: float}]->(:Alumni)   ← hasil Graph ML (KNN similarity)

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
7. Untuk pertanyaan "pengaruh besar", gunakan degree graph: alumni dengan koneksi paling banyak.
8. Untuk similarity/rekomendasi/cluster, gunakan hasil Graph ML:
   - `MIRIP_DENGAN.score` untuk similarity.
   - `Alumni.clusterId` untuk cluster/komunitas.

CONTOH:
Q: Berapa banyak alumni dari ITB?
A: MATCH (a:Alumni)-[:LULUSAN_DARI]->(u:University {normalizedName: toLower('Institut Teknologi Bandung')}) RETURN count(a) AS jumlah LIMIT 25

Q: Siapa nama alumni dari ITS?
A: MATCH (a:Alumni)-[:LULUSAN_DARI]->(u:University {normalizedName: toLower('Institut Teknologi Sepuluh Nopember')}) RETURN a.name LIMIT 25

Q: Berapa alumni dari ITB dan siapa saja?
A: MATCH (a:Alumni)-[:LULUSAN_DARI]->(u:University {normalizedName: toLower('Institut Teknologi Bandung')}) RETURN count(a) AS total LIMIT 25

MATCH (a:Alumni)-[:LULUSAN_DARI]->(u:University {normalizedName: toLower('Institut Teknologi Bandung')}) RETURN a.name LIMIT 25

Q: Siapa alumni yang mirip dengan Budi Santoso?
A: MATCH (a:Alumni {normalizedName: toLower('Budi Santoso')})-[:MIRIP_DENGAN]->(other:Alumni) RETURN other.name AS nama_mirip LIMIT 25

Q: Rekomendasikan alumni yang serupa dengan alumni ITB yang bekerja sebagai politisi
A: MATCH (a:Alumni)-[:LULUSAN_DARI]->(u:University {normalizedName: toLower('Institut Teknologi Bandung')}), (a)-[:MIRIP_DENGAN]->(other:Alumni) RETURN DISTINCT other.name AS rekomendasi LIMIT 25

Q: Berikan salah satu alumni yang memiliki pengaruh besar dan siapa alumni yang paling mirip dengannya
A: MATCH (a:Alumni)-[rel]-()
WITH a, count(rel) AS degree
ORDER BY degree DESC
LIMIT 1
MATCH (a)-[r:MIRIP_DENGAN]-(other:Alumni)
RETURN a.name AS alumni_berpengaruh,
       degree,
       other.name AS alumni_paling_mirip,
       r.score AS similarity_score
ORDER BY similarity_score DESC
LIMIT 25

Q: Alumni berpengaruh itu masuk cluster apa dan mirip dengan siapa?
A: MATCH (a:Alumni)-[rel]-()
WITH a, count(rel) AS degree
ORDER BY degree DESC
LIMIT 1
MATCH (a)-[r:MIRIP_DENGAN]-(other:Alumni)
RETURN a.name AS alumni_berpengaruh,
       a.clusterId AS cluster,
       other.name AS alumni_paling_mirip,
       r.score AS similarity_score
ORDER BY similarity_score DESC
LIMIT 25
"""


class TextToCypher:
    def __init__(self, llm: OpenRouterClient | None = None, db: Neo4jConnection | None = None) -> None:
        self.llm = llm or OpenRouterClient()
        self.db = db
        self._university_names_cache: list[str] | None = None

    def _rewrite_aliases(self, question: str) -> str:
        rewritten = question
        for alias, full_name in ALIASES.items():
            rewritten = re.sub(rf"\b{re.escape(alias)}\b", full_name, rewritten, flags=re.IGNORECASE)
        return rewritten

    def _known_universities(self) -> list[str]:
        # Cache di instance supaya tidak query Neo4j berulang kali untuk
        # setiap pertanyaan dalam satu sesi chat.
        if self._university_names_cache is not None:
            return self._university_names_cache

        if self.db is None:
            self._university_names_cache = []
            return self._university_names_cache

        try:
            rows = self.db.run_query("MATCH (u:University) RETURN u.name AS name")
            self._university_names_cache = [row["name"] for row in rows if row.get("name")]
        except Exception as exc:  # pragma: no cover - jaringan/DB tidak tersedia
            logger.warning("Gagal mengambil daftar universitas untuk fuzzy matching: %s", exc)
            self._university_names_cache = []

        return self._university_names_cache

    def _fuzzy_correct_universities(self, question: str) -> str:
        known = self._known_universities()
        if not known:
            return question

        def _replace(match: re.Match[str]) -> str:
            candidate = match.group(1).strip().rstrip("?.!,")
            if not candidate:
                return match.group(0)

            result = process.extractOne(candidate, known, scorer=fuzz.WRatio)
            if not result:
                return match.group(0)

            best_match, score, _ = result
            if score >= FUZZY_MATCH_THRESHOLD and best_match.lower() != candidate.lower():
                logger.debug(
                    "Koreksi fuzzy nama universitas: '%s' -> '%s' (score=%.1f)",
                    candidate, best_match, score,
                )
                return match.group(0).replace(candidate, best_match)

            return match.group(0)

        return UNIVERSITY_MENTION_PATTERN.sub(_replace, question)

    def _build_history_text(self, history: list[dict[str, str]] | None) -> str:
        if not history:
            return ""
        lines = []
        for message in history:
            prefix = "User:" if message["role"] == "user" else "Assistant:"
            lines.append(f"{prefix} {message['content']}")
        return "History:\n" + "\n".join(lines) + "\n\n"

    def _deterministic_queries(self, question: str) -> list[str]:
        if GENERIC_SIMILARITY_PATTERN.search(question):
            return split_cypher_queries(GENERIC_SIMILARITY_QUERY)
        return []

    def generate(self, question: str, history: list[dict[str, str]] | None = None) -> list[str]:
        question_text = self._rewrite_aliases(question)
        question_text = self._fuzzy_correct_universities(question_text)
        deterministic_queries = self._deterministic_queries(question_text)
        if deterministic_queries:
            return deterministic_queries

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
        from src.graph_ml_orchestrator import GraphMLOrchestrator

        GraphMLOrchestrator(self.db).ensure_ml_ready(question)
        queries = self.generate(question, history=history)
        results: list[dict[str, Any]] = []
        for query in queries:
            rows = self.db.run_query(query)
            results.append({"query": query, "rows": rows})
        return {"question": question, "queries": results}
