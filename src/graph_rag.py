from __future__ import annotations

import json
from typing import Any

from src.answer_formatter import AnswerFormatter
from src.conversation_manager import ConversationManager
from src.database import Neo4jConnection
from src.intent_router import classify_intent
from src.llm_client import OpenRouterClient, build_system_message, build_user_message
from src.logger import get_logger
from src.query_rewriter import QueryRewriter
from src.text_to_cypher import TextToCypher

logger = get_logger(__name__)


ANSWER_PROMPT = """
Anda adalah asisten AlumniGraph AI.
Jawab pertanyaan pengguna dalam bahasa Indonesia berdasarkan data retrieval graph.
Jika data tidak cukup, katakan keterbatasannya dengan jelas.
Tampilkan jawaban ringkas, faktual, dan tidak mengarang data di luar konteks.
Jika ada lebih dari satu query, gabungkan hasilnya menjadi satu jawaban yang jelas.
Jangan tampilkan proses berpikir, analisis internal, atau reasoning langkah demi langkah.
Langsung berikan jawaban akhir berbasis data.
"""

# Catatan: prompt ini TIDAK berisi daftar kapabilitas yang di-hardcode.
# Jumlah node, label yang tersedia, dan contoh pertanyaan dibangun secara
# dinamis dari kondisi graph saat ini (lihat _graph_context_summary), lalu
# LLM yang merangkai jawabannya. Jika graph berubah (mis. setelah import
# ulang dengan data berbeda), jawaban yang dihasilkan ikut berubah tanpa
# perlu mengubah kode.
META_PROMPT_TEMPLATE = """
Anda adalah asisten AlumniGraph AI yang ramah.
Pengguna mengajukan pertanyaan umum/meta (sapaan, bertanya kapabilitas
sistem, atau pertanyaan yang tidak bisa dijawab dengan query data spesifik)
-- bukan pertanyaan data yang konkret.

Jawab dalam bahasa Indonesia, ramah, dan jelas. Jelaskan apa yang bisa
dilakukan pengguna di sistem ini HANYA berdasarkan kondisi graph aktual di
bawah ini. Jangan mengarang jumlah data atau fitur yang tidak ada.

Kondisi graph saat ini:
{graph_context}

Format query yang didukung sistem ini (untuk referensi gaya bertanya):
- Pertanyaan tentang jumlah/daftar alumni dari universitas tertentu
- Pertanyaan tentang pekerjaan, perusahaan (employer), atau posisi/jabatan alumni
- Follow-up question dalam satu sesi chat (mis. "Kalau dari universitas lain?")

Jika graph kosong, katakan dengan jelas bahwa belum ada data yang diimport
dan sarankan menjalankan `python -m src.graph_builder --processed-dir data/processed`.
"""


class GraphRAG:
    def __init__(self, db: Neo4jConnection, llm: OpenRouterClient | None = None, stream: bool = False) -> None:
        self.db = db
        self.llm = llm or OpenRouterClient()
        self.stream = stream
        self.text_to_cypher = TextToCypher(llm=self.llm, db=db)
        self.query_rewriter = QueryRewriter(llm=self.llm)
        self.conversation_manager = ConversationManager()
        self.answer_formatter = AnswerFormatter()

    def _graph_context_summary(self) -> str:
        # Ringkasan kondisi graph yang SELALU diambil langsung dari Neo4j,
        # bukan teks statis. Ini yang membuat jawaban meta tetap akurat
        # walau isi graph berubah dari waktu ke waktu.
        try:
            rows = self.db.run_query(
                """
                MATCH (n)
                WITH labels(n)[0] AS label, count(*) AS total
                RETURN label, total
                ORDER BY label
                """
            )
        except Exception as exc:
            logger.warning("Gagal mengambil ringkasan graph: %s", exc)
            return "Tidak dapat mengambil ringkasan graph saat ini (koneksi database bermasalah)."

        if not rows:
            return "Graph saat ini KOSONG, belum ada data yang diimport."

        lines = [f"- {row['label']}: {row['total']} node" for row in rows if row.get("label")]
        return "\n".join(lines) if lines else "Graph saat ini KOSONG, belum ada data yang diimport."

    def _answer_meta(self, question: str) -> dict[str, Any]:
        graph_context = self._graph_context_summary()
        prompt = META_PROMPT_TEMPLATE.format(graph_context=graph_context)

        try:
            response = self.llm.chat(
                [
                    build_system_message(prompt),
                    build_user_message(question),
                ],
                temperature=0.4,
                max_tokens=400,
            )
        except Exception as exc:
            logger.warning("Gagal generate jawaban meta, pakai fallback statis: %s", exc)
            response = (
                "Saya asisten AlumniGraph AI. Coba tanyakan sesuatu tentang data "
                "alumni, universitas, pekerjaan, atau posisi yang ada di graph ini."
            )

        return {
            "question": question,
            "rewritten_question": None,
            "queries": [],
            "cypher": "",
            "answer": response,
        }

    def retrieve(self, question: str) -> dict[str, Any]:
        rewritten_question = self.query_rewriter.rewrite(
            question, self.conversation_manager.get_context_for_rewrite()
        )

        result = self.text_to_cypher.ask(rewritten_question, history=self.conversation_manager.get_history())
        query_text = "\n---\n".join(item["query"] for item in result["queries"])

        return {
            "question": question,
            "rewritten_question": rewritten_question if rewritten_question != question else None,
            "queries": result["queries"],
            "cypher": query_text,
        }

    def answer(self, question: str) -> dict[str, Any]:
        intent = classify_intent(question)
        if intent == "meta":
            logger.debug("Pertanyaan diklasifikasikan sebagai meta/chit-chat: %s", question)
            return self._answer_meta(question)

        try:
            retrieval = self.retrieve(question)
        except ValueError:
            # Pertanyaan lolos heuristik sebagai data_query tapi ternyata
            # LLM tetap gagal menghasilkan Cypher yang valid. Gunakan jalur
            # jawaban dinamis yang sama, bukan string statis.
            logger.debug("Gagal generate Cypher, fallback ke jawaban meta dinamis: %s", question)
            return self._answer_meta(question)

        rows_payload = [
            {"query": item["query"], "rows": item["rows"]}
            for item in retrieval["queries"]
        ]

        llm_call = self.llm.stream_chat if self.stream else self.llm.chat
        if self.stream:
            print("\nJawaban: ", flush=True)

        response = llm_call(
            [
                build_system_message(ANSWER_PROMPT),
                build_user_message(
                    "Pertanyaan:\n"
                    f"{question}\n\n"
                    "Query Cypher:\n"
                    f"{retrieval['cypher']}\n\n"
                    "Data hasil retrieval:\n"
                    f"{json.dumps(rows_payload, ensure_ascii=False, indent=2)}\n\n"
                    "Jawaban akhir:"
                ),
            ],
            temperature=0.2,
            max_tokens=900,
        )

        self.conversation_manager.add_turn(
            user_question=question,
            queries=retrieval["queries"],
            answer=response,
            rewritten_question=retrieval.get("rewritten_question"),
        )

        retrieval["answer"] = response
        return retrieval
