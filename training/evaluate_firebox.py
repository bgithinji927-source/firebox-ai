#!/usr/bin/env python3
"""Evaluate a local FIREBOX checkpoint against keyword expectations."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.firebox_model.runtime import LocalModelRuntime

parser = argparse.ArgumentParser()
parser.add_argument("--data", default="training_data/starter.jsonl")
parser.add_argument("--checkpoint", default="storage/checkpoints/latest.pt")
parser.add_argument("--max-tokens", type=int, default=80)
args = parser.parse_args()
runtime = LocalModelRuntime()
passed = total = 0
for line in Path(args.data).read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    case = json.loads(line)
    total += 1
    answer = runtime.generate(f"Instruction: {case['instruction']}\nResponse:", max_tokens=args.max_tokens, temperature=0.2)
    expected = set(str(case.get("response", "")).lower().split())
    actual = set(answer.lower().split())
    overlap = len(expected & actual) / max(1, len(expected))
    passed += overlap >= 0.10
    print(json.dumps({"instruction": case["instruction"], "overlap": round(overlap, 3), "passed": overlap >= 0.10, "answer": answer}, ensure_ascii=False))
print(json.dumps({"passed": passed, "total": total, "score": round(passed / max(1, total), 3)}))
