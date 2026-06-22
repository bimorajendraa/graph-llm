from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

try:
    import requests
except ModuleNotFoundError:
    requests = None

from src.cache_manager import JsonCache
from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)


class OpenRouterClient:
    def __init__(
        self,
        api_key: str = settings.openrouter_api_key,
        model: str = settings.openrouter_model,
        base_url: str = settings.openrouter_base_url,
        use_cache: bool = settings.llm_cache_enabled,
        cache_dir: str = str(settings.llm_cache_dir),
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.use_cache = use_cache
        self.cache = JsonCache(cache_dir) if use_cache else None

    def _cache_key(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
        # Kunci cache deterministik: model + temperature + max_tokens + isi
        # messages persis. Pertanyaan yang identik (termasuk system prompt dan
        # history yang menyertainya) akan menghasilkan key yang sama, jadi
        # tidak perlu memanggil API lagi.
        payload = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1200,
        use_cache: bool | None = None,
    ) -> str:
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY belum diisi di file .env")

        should_use_cache = self.use_cache if use_cache is None else use_cache
        cache_key = None
        if should_use_cache and self.cache is not None:
            cache_key = self._cache_key(messages, temperature, max_tokens)
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug("Cache hit untuk request LLM (key=%s)", cache_key[:12])
                return cached["content"]

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

        content = self._extract_content(payload)

        if should_use_cache and self.cache is not None and cache_key is not None:
            self.cache.set(cache_key, {"content": content})
            logger.debug("Cache disimpan untuk request LLM (key=%s)", cache_key[:12])

        return content

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1200,
    ) -> str:
        """Kirim request dengan stream=True, cetak token ke stdout saat
        diterima, dan kembalikan teks lengkap di akhir.
        Tidak menggunakan cache karena streaming by nature tidak bisa
        disimpan sebelum selesai -- tapi hasil akhir bisa di-cache
        oleh caller jika diinginkan.
        Membutuhkan library `requests` (sudah ada di requirements.txt).
        """
        if requests is None:
            logger.warning("Library 'requests' tidak tersedia, fallback ke chat() non-streaming.")
            return self.chat(messages, temperature=temperature, max_tokens=max_tokens)

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
            "stream": True,
        }

        accumulated = []
        try:
            with requests.post(
                url,
                headers=headers,
                json=request_body,
                timeout=120,
                stream=True,
            ) as response:
                if not response.ok:
                    raise RuntimeError(self._format_error(response.status_code, response.text))

                for raw_line in response.iter_lines():
                    if not raw_line:
                        continue
                    line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                    if not line.startswith("data: "):
                        continue
                    data_str = line[len("data: "):]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        token = delta.get("content", "")
                        if token:
                            print(token, end="", flush=True)
                            accumulated.append(token)
                    except (json.JSONDecodeError, IndexError, KeyError):
                        continue
        except Exception as exc:
            raise RuntimeError(f"Streaming request gagal: {exc}") from exc

        print()  # newline setelah streaming selesai
        return "".join(accumulated)

    def _extract_content(self, payload: dict[str, Any]) -> str:
        # OpenRouter, terutama untuk model gratis, kadang mengembalikan HTTP 200
        # tapi body berisi {"error": {...}} alih-alih {"choices": [...]} saat
        # provider upstream sedang bermasalah. Tangani ini secara eksplisit
        # supaya tidak crash dengan KeyError('choices') yang membingungkan.
        if "error" in payload:
            detail = payload["error"]
            raise RuntimeError(
                f"OpenRouter mengembalikan error untuk model `{self.model}` "
                f"meskipun HTTP status sukses. Detail: {detail}\n"
                "Provider upstream model ini kemungkinan sedang overload atau "
                "tidak tersedia. Coba lagi, atau ganti OPENROUTER_MODEL di .env."
            )

        choices = payload.get("choices")
        if not choices:
            raise RuntimeError(
                f"Response OpenRouter untuk model `{self.model}` tidak memiliki "
                f"field 'choices' yang diharapkan. Payload mentah: {payload}"
            )

        message = choices[0].get("message") or {}
        content = message.get("content")
        if not content:
            raise RuntimeError(
                f"Response OpenRouter untuk model `{self.model}` tidak memiliki "
                f"konten teks (kemungkinan dipotong/finish_reason bukan 'stop'). "
                f"Payload mentah: {payload}"
            )

        return content.strip()

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
        if status_code == 429:
            message += (
                "\nKuota harian model gratis kemungkinan habis. Tunggu reset "
                "harian, tambahkan kredit di OpenRouter, atau ganti "
                "OPENROUTER_MODEL ke model lain di .env."
            )
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