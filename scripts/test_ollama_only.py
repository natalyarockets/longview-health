#!/usr/bin/env python3
"""Test just the LLM extraction step using a cached Docling parse.

Run from project root:
    uv run python scripts/test_ollama_only.py
"""

import pickle
from datetime import date

from longview_health.extract import llm_extractor

print("Loading cached Docling parse from /tmp/longview_parsed.pkl...")
with open("/tmp/longview_parsed.pkl", "rb") as f:
    parsed = pickle.load(f)
print(f"  Markdown: {len(parsed.markdown)} chars")
print()

print("Calling Ollama (this will take 1-2 minutes)...")
results = llm_extractor.extract(parsed, fallback_date=date(2025, 2, 21))
print(f"Extracted {len(results)} results:")
print()

for r in results:
    flag = " [ABNORMAL]" if r.result_value.is_abnormal else ""
    unit = r.result_value.unit or ""
    ref = ""
    if r.result_value.reference_low or r.result_value.reference_high:
        lo = r.result_value.reference_low or ""
        hi = r.result_value.reference_high or ""
        ref = f"  (ref: {lo}-{hi})"
    print(f"  {r.test_name}: {r.result_value.value} {unit}{ref}{flag}")

print(f"\nTotal: {len(results)} results extracted")
