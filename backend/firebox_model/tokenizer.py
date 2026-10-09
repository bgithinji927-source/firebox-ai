"""A deliberately small, readable word-level tokenizer for the FIREBOX model."""
from __future__ import annotations

import json
import re
from pathlib import Path

SPECIAL = ["<pad>", "<unk>", "<bos>", "<eos>"]
TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class FireboxTokenizer:
    def __init__(self, vocab: dict[str, int] | None = None):
        self.vocab = vocab or {token: index for index, token in enumerate(SPECIAL)}
        self.inverse = {index: token for token, index in self.vocab.items()}

    def train(self, texts: list[str], max_vocab: int = 12000) -> None:
        counts: dict[str, int] = {}
        for text in texts:
            for token in TOKEN_RE.findall(text.lower()):
                counts[token] = counts.get(token, 0) + 1
        available = max(0, max_vocab - len(SPECIAL))
        for token, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:available]:
            if token not in self.vocab:
                self.vocab[token] = len(self.vocab)
        self.inverse = {index: token for token, index in self.vocab.items()}

    def encode(self, text: str, add_boundaries: bool = True) -> list[int]:
        values = [self.vocab.get(token, self.vocab["<unk>"]) for token in TOKEN_RE.findall(text.lower())]
        return ([self.vocab["<bos>"]] + values + [self.vocab["<eos>"]]) if add_boundaries else values

    def decode(self, ids: list[int]) -> str:
        tokens = [self.inverse.get(index, "<unk>") for index in ids]
        tokens = [token for token in tokens if token not in {"<pad>", "<bos>", "<eos>"}]
        text = " ".join(tokens)
        return re.sub(r"\s+([,.!?;:)\]}])", r"\1", re.sub(r"([(\[{])\s+", r"\1", text)).strip()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.vocab, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "FireboxTokenizer":
        return cls(json.loads(path.read_text(encoding="utf-8")))
