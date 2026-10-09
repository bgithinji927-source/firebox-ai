"""Tiny CPU-compatible recurrent language model; intentionally not a ChatGPT-scale model."""
from __future__ import annotations

try:
    import torch
    from torch import nn
except ImportError:  # pragma: no cover - exercised on installations without torch
    torch = None
    nn = None


if nn is not None:
    class TinyFireboxModel(nn.Module):
        def __init__(self, vocab_size: int, embedding_size: int = 128, hidden_size: int = 256, layers: int = 2):
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, embedding_size, padding_idx=0)
            self.gru = nn.GRU(embedding_size, hidden_size, num_layers=layers, batch_first=True)
            self.output = nn.Linear(hidden_size, vocab_size)

        def forward(self, tokens, hidden=None):
            embedded = self.embedding(tokens)
            output, hidden = self.gru(embedded, hidden)
            return self.output(output), hidden
else:
    class TinyFireboxModel:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            raise RuntimeError("PyTorch is not installed; install requirements.txt to train FIREBOX AI")
