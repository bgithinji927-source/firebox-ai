"""Load and run the locally trained FIREBOX checkpoint."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .model import TinyFireboxModel, torch
from .tokenizer import FireboxTokenizer


class LocalModelUnavailable(RuntimeError):
    pass


class LocalModelRuntime:
    def __init__(self) -> None:
        self.checkpoint = Path(os.getenv("FIREBOX_CHECKPOINT", "storage/checkpoints/latest.pt"))
        if not self.checkpoint.is_absolute():
            self.checkpoint = Path(__file__).resolve().parents[2] / self.checkpoint
        self.model: Any = None
        self.tokenizer: FireboxTokenizer | None = None
        self.metadata: dict[str, Any] = {}
        self._load_error: str | None = None
        self.load()

    def load(self) -> None:
        self.model = None
        self.tokenizer = None
        self._load_error = None
        if not self.checkpoint.exists():
            self._load_error = "No local FIREBOX checkpoint exists yet; run the training command first."
            return
        if torch is None:
            self._load_error = "PyTorch is not installed; install requirements.txt to load FIREBOX AI."
            return
        try:
            payload = torch.load(self.checkpoint, map_location="cpu", weights_only=False)
            self.tokenizer = FireboxTokenizer(payload["vocab"])
            config = payload["config"]
            self.model = TinyFireboxModel(len(self.tokenizer.vocab), config["embedding_size"], config["hidden_size"], config["layers"])
            self.model.load_state_dict(payload["state_dict"])
            self.model.eval()
            self.metadata = {key: payload.get(key) for key in ("step", "epoch", "train_loss", "validation_loss")}
        except Exception as exc:  # never expose checkpoint internals to HTTP clients
            self._load_error = f"Local FIREBOX checkpoint could not be loaded: {exc.__class__.__name__}"

    def status(self) -> dict[str, Any]:
        return {"provider": "local-firebox", "configured": self.model is not None, "checkpoint": str(self.checkpoint), "error": self._load_error, **self.metadata}

    @torch.no_grad() if torch is not None else (lambda function: function)
    def generate(self, prompt: str, max_tokens: int = 120, temperature: float = 0.75) -> str:
        if self.model is None or self.tokenizer is None or torch is None:
            raise LocalModelUnavailable(self._load_error or "Local FIREBOX model is unavailable")
        ids = self.tokenizer.encode(prompt)
        generated = list(ids)
        hidden = None
        for _ in range(max_tokens):
            input_ids = torch.tensor([generated[-128:]], dtype=torch.long)
            logits, hidden = self.model(input_ids, hidden)
            next_logits = logits[0, -1] / max(temperature, 0.05)
            next_id = int(torch.multinomial(torch.softmax(next_logits, dim=-1), 1).item())
            generated.append(next_id)
            if next_id == self.tokenizer.vocab["<eos>"]:
                break
        answer = self.tokenizer.decode(generated[len(ids):])
        if not answer:
            raise LocalModelUnavailable("The local FIREBOX model generated no text")
        return answer
