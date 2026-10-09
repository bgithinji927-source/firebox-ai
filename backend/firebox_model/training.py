"""Training utilities for the small local FIREBOX model."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Callable

from .model import TinyFireboxModel, torch
from .tokenizer import FireboxTokenizer


def load_texts(path: Path) -> list[str]:
    texts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, str):
            texts.append(item)
        elif isinstance(item, dict):
            instruction = item.get("instruction", "")
            context = item.get("context", "")
            response = item.get("response", "")
            texts.append(f"Instruction: {instruction}\nContext: {context}\nResponse: {response}")
    if not texts:
        raise ValueError("Training dataset is empty")
    return texts


def train_model(dataset_path: Path, checkpoint_path: Path, epochs: int = 8, embedding_size: int = 128, hidden_size: int = 256, layers: int = 2, callback: Callable[[dict], None] | None = None) -> dict:
    if torch is None:
        raise RuntimeError("PyTorch is not installed; install requirements.txt to train FIREBOX AI")
    random.seed(7)
    torch.manual_seed(7)
    texts = load_texts(dataset_path)
    random.shuffle(texts)
    split = max(1, int(len(texts) * 0.8))
    train_texts, validation_texts = texts[:split], texts[split:] or texts[:1]
    tokenizer = FireboxTokenizer()
    tokenizer.train(texts)
    pad = tokenizer.vocab["<pad>"]
    model = TinyFireboxModel(len(tokenizer.vocab), embedding_size, hidden_size, layers)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.003)
    loss_fn = torch.nn.CrossEntropyLoss(ignore_index=pad)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    metrics = {"epochs": epochs, "vocabulary": len(tokenizer.vocab), "train_loss": None, "validation_loss": None}

    def loss_for(batch_texts):
        losses = []
        for text in batch_texts:
            ids = tokenizer.encode(text)
            if len(ids) < 3:
                continue
            x = torch.tensor([ids[:-1]], dtype=torch.long)
            y = torch.tensor([ids[1:]], dtype=torch.long)
            logits, _ = model(x)
            losses.append(loss_fn(logits.reshape(-1, logits.shape[-1]), y.reshape(-1)))
        return torch.stack(losses).mean() if losses else torch.tensor(0.0)

    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        train_loss = loss_for(train_texts)
        train_loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        model.eval()
        with torch.no_grad():
            validation_loss = loss_for(validation_texts)
        metrics.update({"epoch": epoch, "train_loss": round(float(train_loss.item()), 5), "validation_loss": round(float(validation_loss.item()), 5)})
        payload = {"vocab": tokenizer.vocab, "config": {"embedding_size": embedding_size, "hidden_size": hidden_size, "layers": layers}, "state_dict": model.state_dict(), **metrics}
        torch.save(payload, checkpoint_path)
        if callback:
            callback(metrics.copy())
    return metrics
