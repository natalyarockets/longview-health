"""Extraction orchestration.

Runs table and text extractors against a parsed document, merges results,
and deduplicates. Table results take priority over text results when both
find the same test on the same date.
"""

from __future__ import annotations

from datetime import date

from longview_health.domain.enums import ResultCategory
from longview_health.domain.models import MedicalResult, ParsedDocument
from longview_health.extract import table_extractor, text_extractor


def extract(
    parsed: ParsedDocument,
    result_date: date,
    category: ResultCategory = ResultCategory.LAB,
) -> list[MedicalResult]:
    """Run all extractors and return merged, deduplicated results.

    Priority:
    1. Table extractor (higher confidence, structured data)
    2. Text extractor (fills gaps from narrative content)

    When both extractors find the same result (same test name + date),
    the table-extracted version wins because it has higher confidence.

    Args:
        parsed: Output of the document parsing stage.
        result_date: Date to assign to extracted results.
        category: Default result category.

    Returns:
        Deduplicated list of MedicalResult objects.
    """
    # Run table extractor first (higher confidence)
    table_results = table_extractor.extract(parsed, result_date, category)

    # Track IDs from table extraction for dedup
    seen_ids: set[str] = {r.id for r in table_results}

    # Run text extractor, only keep results not already found in tables
    text_results = text_extractor.extract(parsed, result_date, category)
    unique_text_results = [r for r in text_results if r.id not in seen_ids]

    return table_results + unique_text_results
