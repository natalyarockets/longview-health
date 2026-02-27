#!/usr/bin/env python3
"""Test the full extraction pipeline on a real document.

Run from project root:
    uv run python scripts/test_extraction.py /path/to/document.pdf

Uses the smart extraction pipeline: Docling element tree → section router
→ table/form/LLM extractors → merged results.
"""

import sys
import time
from datetime import date
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/test_extraction.py <pdf_path>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        sys.exit(1)

    use_llm = "--llm" in sys.argv

    # Step 1: Parse with rich conversion (preserves Docling element tree)
    from longview_health.extract import parser_chain

    print(f"Step 1: Parsing {pdf_path.name} with Docling...")
    t0 = time.perf_counter()
    conversion = parser_chain.parse_rich(pdf_path)
    parse_ms = (time.perf_counter() - t0) * 1000

    parsed = conversion.parsed
    print(f"  Parser: {parsed.parser_used}")
    print(f"  Pages: {parsed.page_count}")
    print(f"  Markdown: {len(parsed.markdown)} chars")
    print(f"  Tables (structured): {len(parsed.tables)}")
    print(f"  Docling element tree: {'yes' if conversion.docling_document else 'no'}")
    print(f"  Parse time: {parse_ms:.0f}ms")

    # Save raw markdown for inspection
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "dev_output" / pdf_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_md_path = out_dir / "raw_markdown.md"
    raw_md_path.write_text(parsed.markdown)
    print(f"  Raw markdown saved to: {raw_md_path}")
    print()

    # Step 2: Classify sections
    if conversion.docling_document:
        from longview_health.extract.section_router import classify

        sections = classify(conversion.docling_document)
        print(f"Step 2: Section classification ({len(sections)} sections)")
        for i, s in enumerate(sections):
            detail = ""
            if s.table_item is not None:
                data = getattr(s.table_item, "data", None)
                if data:
                    detail = f" ({data.num_rows}x{data.num_cols} grid)"
            elif s.texts:
                detail = f" ({len(s.texts)} text items)"
            print(f"  [{i}] {s.section_type.value}{detail}")
        print()
    else:
        print("Step 2: No Docling element tree -- using legacy markdown parsing")
        print()

    # Step 3: Smart extraction
    from longview_health.extract.extraction_chain import extract_smart

    print(f"Step 3: Smart extraction (use_llm={use_llm})...")
    t0 = time.perf_counter()
    results = extract_smart(conversion, fallback_date=date(2025, 2, 21), use_llm=use_llm)
    extract_ms = (time.perf_counter() - t0) * 1000
    print(f"  Extracted {len(results)} results in {extract_ms:.0f}ms")
    print()

    # Step 4: Display results
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    for r in results:
        flag = " [ABNORMAL]" if r.result_value.is_abnormal else ""
        unit = r.result_value.unit or ""
        ref = ""
        if r.result_value.reference_low or r.result_value.reference_high:
            lo = r.result_value.reference_low or ""
            hi = r.result_value.reference_high or ""
            ref = f"  (ref: {lo}-{hi})"
        print(f"  {r.test_name}: {r.result_value.value} {unit}{ref}{flag}")
        print(f"    extractor={r.extractor_version}  confidence={r.confidence.value}")

    print()
    print(f"Total: {len(results)} results extracted")
    print(f"Timing: parse={parse_ms:.0f}ms  extract={extract_ms:.0f}ms  total={parse_ms + extract_ms:.0f}ms")


if __name__ == "__main__":
    main()
