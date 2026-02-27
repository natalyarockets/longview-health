#!/usr/bin/env python3
"""Test extraction using MLX (Apple Silicon optimized).

Run from project root:
    uv run python scripts/test_mlx_extraction.py

First run downloads ~4GB model from HuggingFace.
"""

import json
import pickle
import time
from pathlib import Path

from mlx_lm import generate, load

from longview_health.extract.llm_extractor import (
    EXTRACTION_PROMPT,
    ExtractionResponse,
    _dedup_table_columns,
)

# Load cached Docling parse
print("Loading cached Docling parse...")
with open("/tmp/longview_parsed.pkl", "rb") as f:
    parsed = pickle.load(f)

cleaned = _dedup_table_columns(parsed.markdown)
print(f"Markdown: {len(parsed.markdown)} -> {len(cleaned)} chars after dedup")
print()

# Build prompt
schema_json = ExtractionResponse.model_json_schema()
prompt_text = EXTRACTION_PROMPT.format(
    schema=json.dumps(schema_json, indent=2),
    document=cleaned,
)

# Load model (downloads ~4GB on first run)
model_name = "mlx-community/Qwen2.5-3B-Instruct-4bit"
print(f"Loading model: {model_name}")
print("(first run downloads ~4GB, subsequent loads take seconds)")
model, tokenizer = load(model_name)
print("Model loaded!")
print()

# Format as chat message for instruct model
messages = [
    {"role": "user", "content": prompt_text},
]
chat_prompt = tokenizer.apply_chat_template(
    messages, tokenize=False, add_generation_prompt=True
)

# Generate
print("Generating extraction (watch for speed)...")
start = time.time()
response = generate(
    model,
    tokenizer,
    prompt=chat_prompt,
    max_tokens=4096,
    verbose=True,
)
elapsed = time.time() - start
print(f"\nCompleted in {elapsed:.1f}s")
print()

# Parse and display
try:
    # Strip markdown fences if present
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    data = json.loads(text)
    extraction = ExtractionResponse.model_validate(data)

    print("=" * 70)
    print(f"RESULTS ({len(extraction.results)} extracted)")
    print(f"Document date: {extraction.document_date}")
    print(f"Document type: {extraction.document_type}")
    print("=" * 70)
    for r in extraction.results:
        flag = " [ABNORMAL]" if r.is_abnormal else ""
        unit = r.unit or ""
        ref = ""
        if r.reference_low or r.reference_high:
            lo = r.reference_low or ""
            hi = r.reference_high or ""
            ref = f"  (ref: {lo}-{hi})"
        print(f"  {r.test_name}: {r.value} {unit}{ref}{flag}")

except (json.JSONDecodeError, Exception) as e:
    print(f"Parse error: {e}")
    print("Raw response (first 2000 chars):")
    print(response[:2000])
