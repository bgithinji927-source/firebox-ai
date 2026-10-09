"""Local FIREBOX model adapter; no external model provider is used."""
from __future__ import annotations

from typing import Any

from .firebox_model import LocalModelRuntime, LocalModelUnavailable


class ModelUnavailable(RuntimeError):
    """Raised when a trained local FIREBOX checkpoint is not available."""


class FireboxModelAdapter:
    def __init__(self) -> None:
        self.runtime = LocalModelRuntime()

    @property
    def model_name(self) -> str:
        return "FIREBOX local model"

    def status(self) -> dict[str, Any]:
        return self.runtime.status()

    async def chat(self, messages: list[dict[str, str]], model_name: str | None = None) -> str:
        prompt = "\n".join(f"{item['role'].title()}: {item['content']}" for item in messages[-12:])
        try:
            return self.runtime.generate(prompt)
        except LocalModelUnavailable as exc:
            raise ModelUnavailable(str(exc)) from exc
