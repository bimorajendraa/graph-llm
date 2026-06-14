from __future__ import annotations

from typing import Any

from src.database import Neo4jConnection
from src.llm_client import OpenRouterClient, build_system_message, build_user_message
from src.text_to_cypher import TextToCypher


ANSWER_PROMPT = """
Anda adalah asisten AlumniGraph AI.
Jawab pertanyaan pengguna dalam bahasa Indonesia berdasarkan data retrieval graph.
Jika data tidak cukup, katakan keterbatasannya dengan jelas.
Tampilkan jawaban ringkas, faktual, dan tidak mengarang data di luar konteks.
"""


class GraphRAG:
    def __init__(self, db: Neo4jConnection, llm: OpenRouterClient | None = None) -> None:
        self.db = db
        self.llm = llm or OpenRouterClient()
        self.text_to_cypher = TextToCypher(llm=self.llm, db=db)

    def retrieve(self, question: str) -> dict[str, Any]:
        result = self.text_to_cypher.ask(question)
        return {
            "question": question,
            "cypher": result["cypher"],
            "rows": result["rows"],
        }

    def answer(self, question: str) -> dict[str, Any]:
        retrieval = self.retrieve(question)
        response = self.llm.chat(
            [
                build_system_message(ANSWER_PROMPT),
                build_user_message(
                    "Pertanyaan:\n"
                    f"{question}\n\n"
                    "Query Cypher:\n"
                    f"{retrieval['cypher']}\n\n"
                    "Data hasil retrieval:\n"
                    f"{retrieval['rows']}\n\n"
                    "Jawaban akhir:"
                ),
            ],
            temperature=0.2,
            max_tokens=900,
        )
        retrieval["answer"] = response
        return retrieval
