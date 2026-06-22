from __future__ import annotations

import re
from typing import Literal

Intent = Literal["data_query", "meta"]

# Penanda pertanyaan meta/chit-chat: sapaan, pertanyaan tentang kapabilitas
# sistem, atau permintaan bantuan umum -- bukan pertanyaan tentang data
# alumni/universitas/pekerjaan/posisi yang spesifik.
META_HINT_PATTERN = re.compile(
    r"\b(halo|hai|hi+|hello|apa kabar|siapa kamu|kamu siapa|kamu bisa apa|"
    r"apa yang bisa|apa saja yang bisa|bisa apa|fitur apa|cara pakai|"
    r"cara menggunakan|cara memakai|tolong jelaskan|jelaskan tentang|"
    r"bagaimana cara|bantuan|^help$|menu|panduan|what (can|do) (you|we)|"
    r"what (is|are) this)\b",
    re.IGNORECASE,
)

# Penanda pertanyaan data: menyebut entitas/relationship yang ada di schema
# graph atau kata tanya kuantitatif khas pertanyaan data.
DATA_HINT_PATTERN = re.compile(
    r"\b(alumni|universitas|kampus|university|pekerjaan|jabatan|posisi|"
    r"employer|perusahaan|lulusan|berapa|siapa (saja|nama)|daftar|list|"
    r"mirip|serupa|sejenis|similar|rekomen|rekomendasi)\b",
    re.IGNORECASE,
)


def classify_intent(question: str) -> Intent:
    """Heuristik murah (tanpa panggilan LLM) untuk membedakan pertanyaan
    data vs meta/chit-chat.

    Hanya diklasifikasikan sebagai "meta" jika ada penanda meta yang jelas
    DAN tidak ada penanda data sama sekali -- supaya pertanyaan campuran
    seperti "Bisa kasih tau alumni dari ITB?" tetap dianggap data_query.
    Kasus ambigu lain tetap dicoba sebagai data_query lebih dulu; GraphRAG
    punya fallback dinamis jika ternyata gagal menghasilkan Cypher.
    """
    normalized = question.strip().lower()
    if not normalized:
        return "meta"

    has_meta_hint = bool(META_HINT_PATTERN.search(normalized))
    has_data_hint = bool(DATA_HINT_PATTERN.search(normalized))

    if has_meta_hint and not has_data_hint:
        return "meta"
    return "data_query"