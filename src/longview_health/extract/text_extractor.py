"""Text-based structured extractor.

Extracts medical results from narrative/inline text using regex patterns.
Handles formats like:
- "Hemoglobin: 14.2 g/dL (ref 12.0-16.0)"
- "WBC 7.5 K/uL"
- "TSH: 2.1 mIU/L (0.4 - 4.0)"
- "Glucose 95 mg/dL [70-100]"

This extractor supplements the table extractor for documents where
results are embedded in text rather than structured tables.
"""

from __future__ import annotations

import re
from datetime import date

from longview_health.domain.enums import Confidence, ResultCategory
from longview_health.domain.identifiers import result_key
from longview_health.domain.models import MedicalResult, ParsedDocument, ResultValue
from longview_health.extract.table_extractor import detect_abnormal, parse_reference_range

EXTRACTOR_VERSION = "text-v1"

# Pattern for inline lab results:
# "Test Name: 14.2 g/dL (ref 12.0-16.0)"
# "Test Name  14.2 g/dL [12.0 - 16.0]"
# "Test Name: 14.2 g/dL"
# Captures: test_name, value, unit (optional), reference range (optional)
_INLINE_RESULT_PATTERN = re.compile(
    r"(?P<test_name>[A-Za-z][A-Za-z\s\-/().]{2,40}?)"  # Test name (letters, spaces, hyphens)
    r"\s*[:=]\s*"                                         # Separator (colon or equals)
    r"(?P<value>[<>]?\s*\d+\.?\d*)"                       # Numeric value
    r"(?:\s+(?P<unit>[A-Za-z/%][A-Za-z/%\d.]*(?:/[A-Za-z]+)?))?"  # Optional unit (e.g. g/dL, K/uL, mIU/L)
    r"(?:\s*[\(\[]\s*"                                     # Optional reference range in parens/brackets
    r"(?:ref\.?\s*(?:range\s*)?[:=]?\s*)?"                 # Optional "ref range:" prefix
    r"(?P<ref_range>[<>]?\s*\d+\.?\d*\s*[-–—]\s*[<>]?\s*\d+\.?\d*)"
    r"\s*[\)\]])?"                                         # Close paren/bracket
)

# Simpler pattern for space-separated results (common in lab printouts):
# "WBC       7.5    K/uL    4.5-11.0"
_SPACED_RESULT_PATTERN = re.compile(
    r"^(?P<test_name>[A-Za-z][A-Za-z\s\-/().]{2,40}?)"   # Test name
    r"\s{2,}"                                              # Multiple spaces as separator
    r"(?P<value>[<>]?\s*\d+\.?\d*)"                        # Value
    r"(?:\s+(?P<unit>[A-Za-z/%][A-Za-z/%\d.]{0,15}))?"    # Optional unit
    r"(?:\s+(?P<ref_range>\d+\.?\d*\s*[-–—]\s*\d+\.?\d*))?" # Optional reference range
    r"\s*$"
)


def _extract_from_line(
    line: str,
    document_id: str,
    result_date: date,
    parser_used: str,
    category: ResultCategory,
) -> MedicalResult | None:
    """Try to extract a result from a single line of text."""

    # Try inline pattern first (colon-separated)
    m = _INLINE_RESULT_PATTERN.search(line)
    if not m:
        # Try space-separated pattern
        m = _SPACED_RESULT_PATTERN.match(line.strip())
    if not m:
        return None

    test_name = m.group("test_name").strip()
    value = m.group("value").strip()

    if not test_name or not value:
        return None

    # Skip if test_name looks like a section header or non-result text
    if len(test_name) < 2 or test_name.lower() in {
        "date", "time", "patient", "name", "doctor", "physician",
        "page", "report", "laboratory", "specimen", "collected",
    }:
        return None

    unit = None
    try:
        unit_match = m.group("unit")
        if unit_match:
            unit = unit_match.strip()
    except IndexError:
        pass

    ref_low: str | None = None
    ref_high: str | None = None
    try:
        ref_range = m.group("ref_range")
        if ref_range:
            ref_low, ref_high = parse_reference_range(ref_range)
    except IndexError:
        pass

    is_abnormal = detect_abnormal(None, value, ref_low, ref_high)
    result_id = result_key(document_id, test_name, result_date)

    return MedicalResult(
        id=result_id,
        document_id=document_id,
        test_name=test_name,
        result_value=ResultValue(
            value=value,
            unit=unit,
            reference_low=ref_low,
            reference_high=ref_high,
            is_abnormal=is_abnormal,
        ),
        result_date=result_date,
        category=category,
        parser_used=parser_used,
        extractor_version=EXTRACTOR_VERSION,
        confidence=Confidence.LOW,  # Text extraction is less reliable than table
    )


def extract(
    parsed: ParsedDocument,
    result_date: date,
    category: ResultCategory = ResultCategory.LAB,
) -> list[MedicalResult]:
    """Extract results from text blocks in a parsed document.

    Args:
        parsed: Output of the document parsing stage.
        result_date: Date to assign to extracted results.
        category: Default result category.

    Returns:
        MedicalResult objects found in text blocks.
    """
    results: list[MedicalResult] = []
    seen_keys: set[str] = set()

    for block in parsed.text_blocks:
        for line in block.split("\n"):
            line = line.strip()
            if not line or len(line) < 5:
                continue

            result = _extract_from_line(
                line=line,
                document_id=parsed.document_id,
                result_date=result_date,
                parser_used=parsed.parser_used,
                category=category,
            )

            if result and result.id not in seen_keys:
                seen_keys.add(result.id)
                results.append(result)

    return results
