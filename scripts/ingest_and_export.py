#!/usr/bin/env python3
"""End-to-end: parse PDF → extract → store in vault → export trend PDF.

Usage:
    uv run python scripts/ingest_and_export.py <vault_name> <pdf_path> [<pdf_path> ...]

Example:
    uv run python scripts/ingest_and_export.py alice ~/labs/bloodwork-jan.pdf ~/labs/bloodwork-jun.pdf
    # -> alice-trends-2026-02-27.pdf in current directory
"""

import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from longview_health.core.config import AppConfig
from longview_health.domain.enums import DocumentType
from longview_health.domain.models import Document
from longview_health.extract import parser_chain, llm_extractor, result_merger, table_parser
from longview_health.extract.region_grouper import group_regions
from longview_health.extract.table_parser import _detect_date
from longview_health.search.indexer import index_parsed_document
from longview_health.storage import document_store, results_store, vault_store
from longview_health.trends.engine import build_trend_report
from longview_health.trends.export import export_pdf
from longview_health.validate.engine import validate_results


def _suffix_to_doctype(suffix: str) -> DocumentType:
    return {
        ".pdf": DocumentType.PDF,
        ".png": DocumentType.PNG,
        ".jpg": DocumentType.JPG,
        ".jpeg": DocumentType.JPG,
        ".tiff": DocumentType.TIFF,
        ".tif": DocumentType.TIFF,
    }.get(suffix.lower(), DocumentType.UNKNOWN)


def ingest_one(config: AppConfig, vault_name: str, pdf_path: Path) -> int:
    """Parse, extract, and store results from one document. Returns result count."""
    print(f"\n{'='*60}")
    print(f"  {pdf_path.name}")
    print(f"{'='*60}")

    # Parse
    t0 = time.perf_counter()
    conversion = parser_chain.parse_rich(pdf_path)
    parsed = conversion.parsed
    parse_ms = (time.perf_counter() - t0) * 1000
    print(f"  Parsed in {parse_ms:.0f}ms ({parsed.parser_used}, {parsed.page_count} pages)")

    # Insert document row
    from longview_health.domain.identifiers import content_hash
    doc_hash = content_hash(pdf_path)
    doc = Document(
        id=doc_hash,
        vault_name=vault_name,
        filename=pdf_path.name,
        file_path=str(pdf_path.resolve()),
        document_type=_suffix_to_doctype(pdf_path.suffix),
        content_hash=doc_hash,
        ingested_at=datetime.now(timezone.utc),
        page_count=parsed.page_count,
    )
    document_store.insert_document(config, vault_name, doc)

    # Extract
    t0 = time.perf_counter()
    result_date = _detect_date(parsed.markdown) or date.today()
    all_result_lists: list[list] = []

    if conversion.docling_document:
        regions = group_regions(conversion.docling_document)
        print(f"  {len(regions)} regions")

        # Table regions
        for r in regions:
            if r.table_item is None:
                continue
            table_results = table_parser.extract_from_table_item(
                table_item=r.table_item,
                doc_id=parsed.document_id,
                result_date=result_date,
                parser_used=parsed.parser_used,
            )
            all_result_lists.append(table_results)

        # Text regions → combined LLM call
        text_regions = [r for r in regions if r.table_item is None and r.text.strip()]
        if text_regions:
            combined = "\n\n---\n\n".join(r.text.strip() for r in text_regions)
            llm_results = llm_extractor.extract_region(
                region_text=combined,
                doc_id=parsed.document_id,
                parser_used=parsed.parser_used,
                fallback_date=result_date,
            )
            all_result_lists.append(llm_results)

        results = result_merger.merge(*all_result_lists)
    else:
        results = table_parser.extract(parsed=parsed, fallback_date=result_date)

    extract_ms = (time.perf_counter() - t0) * 1000
    print(f"  Extracted {len(results)} results in {extract_ms:.0f}ms")

    # Validate
    validated = validate_results(results)
    rejected = len(results) - len(validated)
    if rejected:
        print(f"  Validated: {len(validated)} passed, {rejected} rejected")

    for r in validated:
        flag = " [!]" if r.result_value.is_abnormal else ""
        print(f"    {r.test_name}: {r.result_value.value} {r.result_value.unit or ''}{flag}")

    # Index for search
    index_parsed_document(config, vault_name, parsed)

    # Store
    results_store.insert_results(config, vault_name, validated)
    print(f"  Stored {len(validated)} results")

    return len(validated)


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: uv run python scripts/ingest_and_export.py <vault> <pdf> [<pdf> ...]")
        sys.exit(1)

    vault_name = sys.argv[1]
    pdf_paths = [Path(p) for p in sys.argv[2:]]

    for p in pdf_paths:
        if not p.exists():
            print(f"File not found: {p}")
            sys.exit(1)

    config = AppConfig()
    config.ensure_dirs()

    # Create vault if needed
    if not vault_store.vault_exists(config, vault_name):
        vault_store.create_vault(config, vault_name)
        print(f"Created vault: {vault_name}")
    else:
        print(f"Using existing vault: {vault_name}")

    # Ingest each PDF
    total = 0
    for pdf_path in pdf_paths:
        total += ingest_one(config, vault_name, pdf_path)

    # Export PDF
    all_results = results_store.query_results(config, vault_name)
    if not all_results:
        print("\nNo results to export.")
        return

    report = build_trend_report(vault_name, all_results)
    doc_ids = list({r.document_id for r in all_results})
    doc_names = results_store.get_document_names(config, vault_name, doc_ids)

    out_path = f"{vault_name}-trends-{date.today().isoformat()}.pdf"
    export_pdf(report, out_path, doc_names=doc_names)

    print(f"\n{'='*60}")
    print(f"Done. {total} results from {len(pdf_paths)} document(s).")
    print(f"PDF: {out_path}")
    print(f"\nYou can also run:")
    print(f"  longview results {vault_name}")
    print(f"  longview trend {vault_name} '<test name>'")
    print(f"  longview export {vault_name}")


if __name__ == "__main__":
    main()
