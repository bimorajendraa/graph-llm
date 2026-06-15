from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConversationTurn:
    """Represents a single turn in the conversation."""
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


class ConversationManager:
    """Manages conversation state and history."""

    def __init__(self, max_history: int = 20) -> None:
        self.turns: list[ConversationTurn] = []
        self.max_history = max_history

    def add_turn(
        self,
        user_question: str,
        queries: list[dict[str, Any]] | None = None,
        answer: str | None = None,
        rewritten_question: str | None = None,
    ) -> None:
        """Add a new turn to the conversation."""
        turn = ConversationTurn(
            user_question=user_question,
            rewritten_question=rewritten_question,
            queries=queries or [],
            answer=answer,
        )
        self.turns.append(turn)
        logger.debug(f"Added turn: {user_question}")

        if len(self.turns) > self.max_history:
            self.turns.pop(0)

    def get_history(self) -> list[dict[str, str]]:
        """Get conversation history in chat format."""
        history = []
        for turn in self.turns:
            history.append({"role": "user", "content": turn.user_question})
            if turn.answer:
                history.append({"role": "assistant", "content": turn.answer})
        return history

    def get_last_n_turns(self, n: int = 5) -> list[ConversationTurn]:
        """Get the last n turns."""
        return self.turns[-n:] if self.turns else []

    def get_context_for_rewrite(self) -> list[dict[str, str]]:
        """Get conversation context for query rewriting."""
        context = []
        for turn in self.turns[-3:]:
            context.append({"role": "user", "content": turn.user_question})
            if turn.answer:
                context.append({"role": "assistant", "content": turn.answer[:200]})
        return context

    def clear(self) -> None:
        """Clear conversation history."""
        self.turns = []
        logger.debug("Conversation history cleared")

    def summary(self) -> dict[str, Any]:
        """Get a summary of the conversation."""
        return {
            "total_turns": len(self.turns),
            "turns": [turn.to_dict() for turn in self.turns],
        }
