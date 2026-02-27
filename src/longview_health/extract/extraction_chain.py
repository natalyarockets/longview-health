"""Extraction orchestration.

Two extraction paths:

1. extract() -- Legacy. Parses markdown tables only. Fast but misses
   form-area and unstructured content.

2. extract_smart() -- Uses Docling's element tree for smart routing.
   Dispatches each document section to the most appropriate extractor:
   - TableItem → table extractor (instant, HIGH confidence)
   - form_area with lab headers → form extractor (instant, HIGH confidence)
   - unstructured text → LLM extractor (slow, MEDIUM confidence, opt-in)
   Results are merged with dedup by composite key.
"""

from __future__ import annotations

import logging
from datetime import date

from longview_health.domain.models import DoclingConversion, MedicalResult, ParsedDocument
from longview_health.extract import form_extractor, result_merger, table_parser
from longview_health.extract.section_router import SectionType, classify
from longview_health.extract.table_parser import _detect_date

logger = logging.getLogger(__name__)


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
    use_llm: bool = False,
) -> list[MedicalResult]:
    """Extract structured medical results using smart section routing.

    Uses Docling's element tree to classify each document section and
    dispatch to the most appropriate extractor. Falls back to the legacy
    markdown table parser when no Docling element tree is available.

    Args:
        conversion: DoclingConversion with ParsedDocument and optional DoclingDocument.
        fallback_date: Date to use if no date found in the document.
        use_llm: Whether to use LLM extraction for unstructured sections.

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

    # Classify document sections
    sections = classify(docling_doc)

    if not sections:
        logger.info("No sections classified, falling back to markdown table parser")
        return table_parser.extract(parsed=parsed, fallback_date=fallback_date)

    # Dispatch each section to its extractor
    all_result_lists: list[list[MedicalResult]] = []

    for section in sections:
        if section.section_type == SectionType.TABLE:
            results = table_parser.extract_from_table_item(
                table_item=section.table_item,
                doc_id=parsed.document_id,
                result_date=result_date,
                parser_used=parsed.parser_used,
            )
            all_result_lists.append(results)

        elif section.section_type == SectionType.FORM:
            results = form_extractor.extract_from_form_group(
                group_texts=section.texts,
                doc_id=parsed.document_id,
                result_date=result_date,
                parser_used=parsed.parser_used,
            )
            all_result_lists.append(results)

        elif section.section_type == SectionType.UNSTRUCTURED and use_llm:
            from longview_health.extract import llm_extractor

            results = llm_extractor.extract(
                parsed=parsed,
                fallback_date=fallback_date,
            )
            all_result_lists.append(results)

    # Merge and deduplicate
    merged = result_merger.merge(*all_result_lists)

    logger.info(
        "Smart extraction: %d sections → %d results (from %d pre-merge)",
        len(sections),
        len(merged),
        sum(len(r) for r in all_result_lists),
    )

    return merged
