from __future__ import annotations

from typing import Any

import requests

from src.config import settings


class OpenRouterClient:
    def __init__(
        self,
        api_key: str = settings.openrouter_api_key,
        model: str = settings.openrouter_model,
        base_url: str = settings.openrouter_base_url,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1200,
    ) -> str:
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY belum diisi di file .env")

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "AlumniGraph AI",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        return payload["choices"][0]["message"]["content"].strip()


def build_system_message(role: str) -> dict[str, str]:
    return {
        "role": "system",
        "content": role.strip(),
    }


def build_user_message(content: str) -> dict[str, str]:
    return {
        "role": "user",
        "content": content.strip(),
    }
