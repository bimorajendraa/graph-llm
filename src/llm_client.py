from __future__ import annotations

import json
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

try:
    import requests
except ModuleNotFoundError:
    requests = None

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

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "AlumniGraph AI",
        }
        request_body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if requests is not None:
            response = requests.post(
                url,
                headers=headers,
                json=request_body,
                timeout=60,
            )
            if not response.ok:
                raise RuntimeError(self._format_error(response.status_code, response.text))
            payload: dict[str, Any] = response.json()
        else:
            request = urllib_request.Request(
                url,
                data=json.dumps(request_body).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urllib_request.urlopen(request, timeout=60) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except urllib_error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(self._format_error(exc.code, detail)) from exc

        return payload["choices"][0]["message"]["content"].strip()

    def _format_error(self, status_code: int, response_text: str) -> str:
        try:
            payload = json.loads(response_text)
        except ValueError:
            payload = response_text

        detail = payload
        if isinstance(payload, dict):
            detail = payload.get("error", payload)

        message = (
            f"OpenRouter error {status_code} untuk model `{self.model}`. "
            f"Detail: {detail}"
        )
        if status_code == 404:
            message += (
                "\nKemungkinan besar nilai OPENROUTER_MODEL tidak tersedia. "
                "Coba ganti model di .env, misalnya `nex-agi/nex-n2-pro:free`."
            )
        if status_code == 401:
            message += "\nAPI key tidak valid atau belum terbaca dari .env."
        return message


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
