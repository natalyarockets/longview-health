"""Extraction orchestration.

Two extraction paths:

1. extract() -- Legacy. Parses markdown tables only. Fast but misses
   non-tabular content.

2. extract_smart() -- Region-based extraction using Docling's element tree.
   Groups elements into spatial regions, then dispatches:
   - Docling TableItem regions → table extractor (instant, HIGH confidence)
   - All non-table text regions → combined into ONE LLM call (MEDIUM confidence)
   Results are merged with dedup by composite key.

Architecture: Docling handles WHERE (spatial layout, bounding boxes).
The LLM handles WHAT (semantic understanding of non-table content).
"""

from __future__ import annotations

import logging
from datetime import date

from longview_health.domain.models import DoclingConversion, MedicalResult, ParsedDocument
from longview_health.extract import llm_extractor, result_merger, table_parser
from longview_health.extract.region_grouper import group_regions
from longview_health.extract.table_parser import _detect_date

logger = logging.getLogger(__name__)

_REGION_SEPARATOR = "\n\n---\n\n"


def extract(
    parsed: ParsedDocument,
    fallback_date: date,
) -> list[MedicalResult]:
    """Extract structured medical results from a parsed document.

    Legacy path: uses direct markdown table parsing. Fast and deterministic
    but only handles documents with proper markdown tables.

    Args:
        parsed: Output of the document parsing stage.
        fallback_date: Date to use if no date found in the document.

    Returns:
        List of MedicalResult objects with full provenance.
    """
    return table_parser.extract(parsed=parsed, fallback_date=fallback_date)


def extract_smart(
    conversion: DoclingConversion,
    fallback_date: date,
) -> list[MedicalResult]:
    """Extract structured medical results using region-based routing.

    Groups Docling elements into spatial regions, then dispatches:
    - Docling TableItem regions → deterministic table extractor (fast path)
    - All non-table text → combined into a single LLM call

    Every non-table region is checked by the LLM regardless of whether
    tables produced results, because results can appear outside tables.

    Falls back to legacy markdown table parser when no Docling element tree
    is available.

    Args:
        conversion: DoclingConversion with ParsedDocument and optional DoclingDocument.
        fallback_date: Date to use if no date found in the document.

    Returns:
        List of MedicalResult objects with full provenance.
    """
    parsed = conversion.parsed
    docling_doc = conversion.docling_document

    # No element tree available -- fall back to legacy markdown parsing
    if docling_doc is None:
        logger.info("No Docling element tree, falling back to markdown table parser")
        return table_parser.extract(parsed=parsed, fallback_date=fallback_date)

    # Detect date from the markdown content
    result_date = _detect_date(parsed.markdown) or fallback_date

    # Group elements into spatial regions
    regions = group_regions(docling_doc)

    if not regions:
        logger.info("No regions found, falling back to markdown table parser")
        return table_parser.extract(parsed=parsed, fallback_date=fallback_date)

    # 1. Run table extractor on table regions (instant)
    all_result_lists: list[list[MedicalResult]] = []

    for region in regions:
        if region.table_item is not None:
            results = table_parser.extract_from_table_item(
                table_item=region.table_item,
                doc_id=parsed.document_id,
                result_date=result_date,
                parser_used=parsed.parser_used,
            )
            logger.info(
                "Table region (page %d): %d results via table extractor",
                region.page_no, len(results),
            )
            all_result_lists.append(results)

    # 2. Combine all non-table text into a single LLM call
    text_chunks = []
    for region in regions:
        if region.table_item is None and region.text.strip():
            text_chunks.append(region.text.strip())

    if text_chunks:
        combined_text = _REGION_SEPARATOR.join(text_chunks)
        logger.info(
            "Sending %d non-table regions to LLM (%d chars combined)",
            len(text_chunks), len(combined_text),
        )
        llm_results = llm_extractor.extract_region(
            region_text=combined_text,
            doc_id=parsed.document_id,
            parser_used=parsed.parser_used,
            fallback_date=result_date,
        )
        logger.info("LLM extraction: %d results", len(llm_results))
        all_result_lists.append(llm_results)

    # Merge and deduplicate
    merged = result_merger.merge(*all_result_lists)

    logger.info(
        "Smart extraction: %d regions (%d table, %d text) → %d results (from %d pre-merge)",
        len(regions),
        sum(1 for r in regions if r.table_item is not None),
        len(text_chunks),
        len(merged),
        sum(len(r) for r in all_result_lists),
    )

    return merged
