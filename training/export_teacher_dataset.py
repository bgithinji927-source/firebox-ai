#!/usr/bin/env python3
"""Export owner-approved Groq teacher examples for FIREBOX retraining."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.db import MongoStore
from backend.repositories import Repositories

parser = argparse.ArgumentParser()
parser.add_argument("--output", default="training_data/teacher_approved.jsonl")
parser.add_argument("--owner", default=None)
args = parser.parse_args()

store = MongoStore.from_environment()
store.connect()
try:
    owner = (args.owner or "").strip() or __import__("os").getenv("FIREBOX_OWNER_ID", "local-owner")
    items = Repositories(store).approved_teacher_dataset(owner)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"Exported {len(items)} approved teacher examples to {output}")
finally:
    store.close()
