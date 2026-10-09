"""Provider boundary for OpenAI-compatible and Ollama-compatible chat APIs."""
from __future__ import annotations

import os
from typing import Any

import httpx


class ModelUnavailable(RuntimeError):
    """Raised when a configured model cannot be reached or returns invalid output."""


class OllamaAdapter:
    def __init__(self) -> None:
        self.provider = os.getenv("MODEL_PROVIDER", "openai").strip().lower()
        self.base_url = os.getenv("MODEL_BASE_URL", "").strip().rstrip("/")
        self.model_name = os.getenv("MODEL_NAME", "").strip()
        self.api_key = os.getenv("MODEL_API_KEY", "").strip()
        self.timeout_seconds = float(os.getenv("MODEL_TIMEOUT_SECONDS", "60"))

    def status(self) -> dict[str, Any]:
        provider_ready = self.provider == "ollama" or (self.provider in {"openai", "openai-compatible"} and bool(self.api_key))
        configured = bool(self.base_url and self.model_name and provider_ready)
        return {
            "provider": self.provider or "unconfigured",
            "configured": configured,
            "base_url_configured": bool(self.base_url),
            "model_configured": bool(self.model_name),
        }

    async def chat(self, messages: list[dict[str, str]], model_name: str | None = None) -> str:
        if not self.base_url or not self.model_name:
            raise ModelUnavailable("No AI model is configured. Set MODEL_PROVIDER, MODEL_BASE_URL, and MODEL_NAME on the server.")
        model = (model_name or self.model_name).strip() or self.model_name
        if self.provider == "ollama":
            url = f"{self.base_url}/api/chat"
            payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False}
            headers: dict[str, str] = {}
        elif self.provider in {"openai", "openai-compatible"}:
            if not self.api_key:
                raise ModelUnavailable("The model provider is not configured: set MODEL_API_KEY on the server.")
            url = f"{self.base_url}/chat/completions"
            payload = {"model": model, "messages": messages, "stream": False}
            headers = {"Authorization": f"Bearer {self.api_key}"}
        else:
            raise ModelUnavailable("Unsupported model provider. Use 'openai' or 'ollama'.")
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ModelUnavailable("The configured model endpoint is unavailable; no live answer was generated.") from exc
        if self.provider == "ollama":
            answer = data.get("message", {}).get("content") if isinstance(data, dict) else None
        else:
            choices = data.get("choices", []) if isinstance(data, dict) else []
            answer = choices[0].get("message", {}).get("content") if choices else None
        if not isinstance(answer, str) or not answer.strip():
            raise ModelUnavailable("The configured model returned no answer.")
        return answer.strip()
