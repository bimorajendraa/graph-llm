from __future__ import annotations

import json
from typing import Any

from src.answer_formatter import AnswerFormatter
from src.conversation_manager import ConversationManager
from src.database import Neo4jConnection
from src.llm_client import OpenRouterClient, build_system_message, build_user_message
from src.query_rewriter import QueryRewriter
from src.text_to_cypher import TextToCypher


ANSWER_PROMPT = """
Anda adalah asisten AlumniGraph AI.
Jawab pertanyaan pengguna dalam bahasa Indonesia berdasarkan data retrieval graph.
Jika data tidak cukup, katakan keterbatasannya dengan jelas.
Tampilkan jawaban ringkas, faktual, dan tidak mengarang data di luar konteks.
Jika ada lebih dari satu query, gabungkan hasilnya menjadi satu jawaban yang jelas.
"""


class GraphRAG:
    def __init__(self, db: Neo4jConnection, llm: OpenRouterClient | None = None) -> None:
        self.db = db
        self.llm = llm or OpenRouterClient()
        self.text_to_cypher = TextToCypher(llm=self.llm, db=db)
        self.query_rewriter = QueryRewriter(llm=self.llm)
        self.conversation_manager = ConversationManager()
        self.answer_formatter = AnswerFormatter()

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
        retrieval = self.retrieve(question)
        rows_payload = [
            {"query": item["query"], "rows": item["rows"]}
            for item in retrieval["queries"]
        ]

        response = self.llm.chat(
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
