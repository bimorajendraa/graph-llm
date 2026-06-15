from __future__ import annotations

from typing import Any

from src.llm_client import OpenRouterClient, build_system_message, build_user_message
from src.logger import get_logger

logger = get_logger(__name__)

REWRITE_PROMPT = """
Anda adalah asisten untuk mengubah pertanyaan follow-up menjadi pertanyaan lengkap yang jelas.

Diberikan pertanyaan saat ini dan riwayat percakapan, ubah pertanyaan menjadi pernyataan yang jelas dan eksplisit tanpa menghilang esensinya.

Contoh:
History:
User: Berapa banyak alumni dari ITB?

Follow-up: Kalau dari universitas lain?
Rewritten: Berapa banyak alumni dari universitas lain selain ITB?

---

History:
User: Siapa nama alumni dari ITS?
Assistant: [hasil query]

Follow-up: Lainnya?
Rewritten: Berapa banyak alumni lain dari ITS yang belum ditampilkan?

---

Aturan:
1. Jika pertanyaan sudah jelas, kembalikan apa adanya.
2. Jika pertanyaan adalah follow-up vague (seperti "lainnya?", "kalau yang lain?"), ubah menjadi pertanyaan eksplisit dengan konteks.
3. Gunakan konteks dari history untuk membuat pertanyaan yang lebih spesifik.
4. Jawab HANYA dengan pertanyaan yang telah ditulis ulang, tanpa penjelasan.
"""


class QueryRewriter:
    def __init__(self, llm: OpenRouterClient | None = None) -> None:
        self.llm = llm or OpenRouterClient()

    def _build_history_context(self, history: list[dict[str, str]]) -> str:
        if not history:
            return ""
        lines = []
        for message in history[-4:]:
            prefix = "User:" if message["role"] == "user" else "Assistant:"
            lines.append(f"{prefix} {message['content']}")
        return "History:\n" + "\n".join(lines)

    def rewrite(self, question: str, history: list[dict[str, str]] | None = None) -> str:
        if not history or len(history) < 2:
            logger.debug(f"No history, returning question as-is: {question}")
            return question

        history_text = self._build_history_context(history)
        prompt = f"{history_text}\n\nFollow-up: {question}\nRewritten:"

        try:
            response = self.llm.chat(
                [
                    build_system_message(REWRITE_PROMPT),
                    build_user_message(prompt),
                ],
                temperature=0.3,
                max_tokens=200,
            )
            rewritten = response.strip()
            logger.debug(f"Rewritten '{question}' → '{rewritten}'")
            return rewritten if rewritten else question
        except Exception as exc:
            logger.warning(f"Query rewrite failed: {exc}")
            return question
