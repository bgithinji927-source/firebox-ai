#!/usr/bin/env python3
"""Train the small local FIREBOX model without any external model or API."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.firebox_model.training import train_model
parser = argparse.ArgumentParser()
parser.add_argument("--data", default="training_data/starter.jsonl")
parser.add_argument("--checkpoint", default="storage/checkpoints/latest.pt")
parser.add_argument("--epochs", type=int, default=8)
args = parser.parse_args()
metrics = train_model(Path(args.data), Path(args.checkpoint), epochs=max(1, args.epochs), callback=lambda item: print(item, flush=True))
print(f"Saved local FIREBOX checkpoint: {args.checkpoint}")
print(metrics)
