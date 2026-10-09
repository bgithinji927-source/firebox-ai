"""Configurable local model adapter for Ollama-compatible inference backends."""

from __future__ import annotations

import os
from typing import Any

import httpx


class ModelUnavailable(RuntimeError):
    """Raised when a configured model cannot be reached or returns an invalid response."""


class OllamaAdapter:
    def __init__(self) -> None:
        self.base_url = os.getenv("MODEL_BASE_URL", "http://localhost:11434").rstrip("/")
        self.model_name = os.getenv("MODEL_NAME", "llama3.2")
        self.timeout_seconds = float(os.getenv("MODEL_TIMEOUT_SECONDS", "60"))

    def status(self) -> dict[str, Any]:
        return {"provider": "ollama-compatible", "base_url_configured": bool(self.base_url), "model": self.model_name}

    async def chat(self, messages: list[dict[str, str]], model_name: str | None = None) -> str:
        model = (model_name or self.model_name).strip() or self.model_name
        payload = {"model": model, "messages": messages, "stream": False}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ModelUnavailable("The configured model endpoint is unavailable; no live answer was generated") from exc

        answer = data.get("message", {}).get("content") if isinstance(data, dict) else None
        if not isinstance(answer, str) or not answer.strip():
            raise ModelUnavailable("The configured model returned no answer")
        return answer.strip()
