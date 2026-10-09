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
        # Keep inference aligned with training/train_firebox.py's JSONL format.
        # The model is small, so consistent prompt markers matter a lot.
        parts: list[str] = []
        for item in messages[-12:]:
            role = item["role"]
            if role == "system":
                parts.append(f"Context: {item['content']}")
            elif role == "user":
                parts.append(f"Instruction: {item['content']}")
            elif role == "assistant":
                parts.append(f"Response: {item['content']}")
        prompt = "\n".join(parts) + "\nResponse:"
        try:
            return self.runtime.generate(prompt)
        except LocalModelUnavailable as exc:
            raise ModelUnavailable(str(exc)) from exc
