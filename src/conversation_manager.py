from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.logger import get_logger

logger = get_logger(__name__)

DEFAULT_HISTORY_PATH = Path(".cache") / "conversation_history.json"


@dataclass
class ConversationTurn:
    user_question: str
    rewritten_question: str | None = None
    queries: list[dict[str, Any]] = field(default_factory=list)
    answer: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_question": self.user_question,
            "rewritten_question": self.rewritten_question,
            "queries": self.queries,
            "answer": self.answer,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationTurn":
        ts = data.get("timestamp")
        return cls(
            user_question=data.get("user_question", ""),
            rewritten_question=data.get("rewritten_question"),
            queries=data.get("queries", []),
            answer=data.get("answer"),
            timestamp=datetime.fromisoformat(ts) if ts else datetime.now(),
        )


class ConversationManager:
    def __init__(
        self,
        max_history: int = 20,
        persist_path: Path | str | None = DEFAULT_HISTORY_PATH,
    ) -> None:
        self.turns: list[ConversationTurn] = []
        self.max_history = max_history
        self.persist_path = Path(persist_path) if persist_path else None
        self._load()

    def _load(self) -> None:
        if self.persist_path is None or not self.persist_path.exists():
            return
        try:
            raw = json.loads(self.persist_path.read_text(encoding="utf-8"))
            self.turns = [ConversationTurn.from_dict(t) for t in raw.get("turns", [])]
            if self.turns:
                logger.debug("Loaded %d turns from %s", len(self.turns), self.persist_path)
        except Exception as exc:
            logger.warning("Gagal memuat history percakapan: %s — mulai sesi baru.", exc)
            self.turns = []

    def _save(self) -> None:
        if self.persist_path is None:
            return
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = {"turns": [t.to_dict() for t in self.turns]}
            self.persist_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning("Gagal menyimpan history percakapan: %s", exc)

    def add_turn(
        self,
        user_question: str,
        queries: list[dict[str, Any]] | None = None,
        answer: str | None = None,
        rewritten_question: str | None = None,
    ) -> None:
        turn = ConversationTurn(
            user_question=user_question,
            rewritten_question=rewritten_question,
            queries=queries or [],
            answer=answer,
        )
        self.turns.append(turn)
        logger.debug("Added turn: %s", user_question)
        if len(self.turns) > self.max_history:
            self.turns.pop(0)
        self._save()

    def get_history(self) -> list[dict[str, str]]:
        history = []
        for turn in self.turns:
            history.append({"role": "user", "content": turn.user_question})
            if turn.answer:
                history.append({"role": "assistant", "content": turn.answer})
        return history

    def get_last_n_turns(self, n: int = 5) -> list[ConversationTurn]:
        return self.turns[-n:] if self.turns else []

    def get_context_for_rewrite(self) -> list[dict[str, str]]:
        context = []
        for turn in self.turns[-3:]:
            context.append({"role": "user", "content": turn.user_question})
            if turn.answer:
                context.append({"role": "assistant", "content": turn.answer[:200]})
        return context

    def clear(self, delete_file: bool = True) -> None:
        self.turns = []
        if delete_file and self.persist_path and self.persist_path.exists():
            try:
                self.persist_path.unlink()
            except Exception as exc:
                logger.warning("Gagal menghapus file history: %s", exc)
        logger.debug("Conversation history cleared")

    def summary(self) -> dict[str, Any]:
        return {
            "total_turns": len(self.turns),
            "turns": [turn.to_dict() for turn in self.turns],
        }