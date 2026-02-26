"""Table-based structured extractor.

Takes ParsedTable objects and maps rows to MedicalResult objects by
identifying which columns contain test names, values, units, and
reference ranges based on header text matching.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Sequence

from longview_health.domain.enums import Confidence, ResultCategory
from longview_health.domain.identifiers import result_key
from longview_health.domain.models import (
    MedicalResult,
    ParsedDocument,
    ParsedTable,
    ResultValue,
)

EXTRACTOR_VERSION = "table-v1"

# ---------------------------------------------------------------------------
# Header classification
# ---------------------------------------------------------------------------

# Patterns for identifying column roles from header text (case-insensitive).
_TEST_NAME_PATTERNS = re.compile(
    r"(?i)^(test|analyte|component|panel|parameter|exam|finding|marker|item|name|description)s?$"
)
_VALUE_PATTERNS = re.compile(
    r"(?i)^(result|value|observed|measured|level|reading|score|outcome|finding)s?$"
)
_UNIT_PATTERNS = re.compile(
    r"(?i)^(unit|units|uom|measure)s?$"
)
_REFERENCE_PATTERNS = re.compile(
    r"(?i)^(ref\.?\s*range|reference\s*range|reference|range|normal\s*range|"
    r"normal|expected|standard\s*range|ref\.?\s*interval|biological\s*ref)s?$"
)
_REF_LOW_PATTERNS = re.compile(
    r"(?i)^(low|min|lower|ref\.?\s*low|lower\s*limit)$"
)
_REF_HIGH_PATTERNS = re.compile(
    r"(?i)^(high|max|upper|ref\.?\s*high|upper\s*limit)$"
)
_FLAG_PATTERNS = re.compile(
    r"(?i)^(flag|flags|status|abnormal|interpretation|ind\.?|indicator)s?$"
)


class ColumnMap:
    """Mapping of column indices to their roles in a result table."""

    def __init__(self) -> None:
        self.test_name: int | None = None
        self.value: int | None = None
        self.unit: int | None = None
        self.reference_range: int | None = None
        self.reference_low: int | None = None
        self.reference_high: int | None = None
        self.flag: int | None = None

    @property
    def is_valid(self) -> bool:
        """A table mapping is useful if we can identify at least test name and value."""
        return self.test_name is not None and self.value is not None


def classify_headers(headers: list[str]) -> ColumnMap:
    """Map table column headers to result roles."""
    col_map = ColumnMap()

    for i, header in enumerate(headers):
        h = header.strip()
        if not h:
            continue

        if _TEST_NAME_PATTERNS.match(h):
            col_map.test_name = i
        elif _VALUE_PATTERNS.match(h):
            col_map.value = i
        elif _UNIT_PATTERNS.match(h):
            col_map.unit = i
        elif _REFERENCE_PATTERNS.match(h):
            col_map.reference_range = i
        elif _REF_LOW_PATTERNS.match(h):
            col_map.reference_low = i
        elif _REF_HIGH_PATTERNS.match(h):
            col_map.reference_high = i
        elif _FLAG_PATTERNS.match(h):
            col_map.flag = i

    # Fallback heuristic: if no exact match, try the first two non-empty
    # columns as test_name and value (common in simple lab tables).
    if not col_map.is_valid and len(headers) >= 2:
        non_empty = [(i, h) for i, h in enumerate(headers) if h.strip()]
        if len(non_empty) >= 2:
            col_map.test_name = non_empty[0][0]
            col_map.value = non_empty[1][0]
            # If there's a third column, try it as unit
            if len(non_empty) >= 3:
                col_map.unit = non_empty[2][0]
            # If there's a fourth, try as reference range
            if len(non_empty) >= 4:
                col_map.reference_range = non_empty[3][0]

    return col_map


# ---------------------------------------------------------------------------
# Reference range parsing
# ---------------------------------------------------------------------------

_RANGE_PATTERN = re.compile(
    r"^\s*([<>]?\s*[\d.]+)\s*[-–—]\s*([<>]?\s*[\d.]+)\s*$"
)
_LESS_THAN_PATTERN = re.compile(r"^\s*[<≤]\s*([\d.]+)\s*$")
_GREATER_THAN_PATTERN = re.compile(r"^\s*[>≥]\s*([\d.]+)\s*$")


def parse_reference_range(text: str) -> tuple[str | None, str | None]:
    """Parse a reference range string into (low, high).

    Handles formats like:
    - "4.5-11.0" -> ("4.5", "11.0")
    - "< 200"   -> (None, "200")
    - "> 40"    -> ("40", None)
    - "4.5 - 11.0" -> ("4.5", "11.0")
    """
    text = text.strip()
    if not text:
        return None, None

    m = _RANGE_PATTERN.match(text)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    m = _LESS_THAN_PATTERN.match(text)
    if m:
        return None, m.group(1).strip()

    m = _GREATER_THAN_PATTERN.match(text)
    if m:
        return m.group(1).strip(), None

    return None, None


# ---------------------------------------------------------------------------
# Abnormality detection
# ---------------------------------------------------------------------------

_ABNORMAL_FLAGS = re.compile(r"(?i)^(H|L|HH|LL|A|ABN|HIGH|LOW|ABNORMAL|CRIT|\*+)$")
_NORMAL_FLAGS = re.compile(r"(?i)^(N|NL|NORMAL|WNL|NEG|NEGATIVE)?$")


def detect_abnormal(
    flag_text: str | None,
    value_text: str,
    ref_low: str | None,
    ref_high: str | None,
) -> bool | None:
    """Determine if a result is abnormal.

    Uses flag column first, then compares numeric value against reference range.
    Returns None if indeterminate.
    """
    if flag_text:
        flag = flag_text.strip()
        if _ABNORMAL_FLAGS.match(flag):
            return True
        if _NORMAL_FLAGS.match(flag):
            return False

    # Try numeric comparison against reference range
    try:
        val = float(value_text.strip())
    except (ValueError, TypeError):
        return None

    if ref_low is not None:
        try:
            if val < float(ref_low):
                return True
        except ValueError:
            pass

    if ref_high is not None:
        try:
            if val > float(ref_high):
                return True
        except ValueError:
            pass

    if ref_low is not None and ref_high is not None:
        try:
            if float(ref_low) <= val <= float(ref_high):
                return False
        except ValueError:
            pass

    return None


# ---------------------------------------------------------------------------
# Table extraction
# ---------------------------------------------------------------------------


def _get_cell(row: list[str], idx: int | None) -> str:
    """Safely get a cell value by index."""
    if idx is None or idx >= len(row):
        return ""
    return row[idx].strip()


def extract_from_table(
    table: ParsedTable,
    document_id: str,
    result_date: date,
    parser_used: str,
    category: ResultCategory = ResultCategory.LAB,
) -> list[MedicalResult]:
    """Extract MedicalResult objects from a single parsed table.

    Args:
        table: Parsed table with headers and rows.
        document_id: ID of the source document.
        result_date: Date of the results.
        parser_used: Which parser produced the source data.
        category: Result category (defaults to LAB).

    Returns:
        List of extracted MedicalResult objects.
    """
    col_map = classify_headers(table.headers)
    if not col_map.is_valid:
        return []

    results: list[MedicalResult] = []

    for row in table.rows:
        test_name = _get_cell(row, col_map.test_name)
        value = _get_cell(row, col_map.value)

        if not test_name or not value:
            continue

        unit = _get_cell(row, col_map.unit) or None

        # Parse reference range
        ref_low: str | None = None
        ref_high: str | None = None
        if col_map.reference_range is not None:
            ref_low, ref_high = parse_reference_range(
                _get_cell(row, col_map.reference_range)
            )
        if col_map.reference_low is not None:
            ref_low = _get_cell(row, col_map.reference_low) or None
        if col_map.reference_high is not None:
            ref_high = _get_cell(row, col_map.reference_high) or None

        # Detect abnormality
        flag_text = _get_cell(row, col_map.flag) or None
        is_abnormal = detect_abnormal(flag_text, value, ref_low, ref_high)

        result_id = result_key(document_id, test_name, result_date)

        results.append(
            MedicalResult(
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
                confidence=Confidence.MEDIUM,
            )
        )

    return results


def extract(
    parsed: ParsedDocument,
    result_date: date,
    category: ResultCategory = ResultCategory.LAB,
) -> list[MedicalResult]:
    """Extract all results from tables in a parsed document.

    Args:
        parsed: Output of the document parsing stage.
        result_date: Date to assign to extracted results.
        category: Default result category.

    Returns:
        All MedicalResult objects found across all tables.
    """
    all_results: list[MedicalResult] = []

    for table in parsed.tables:
        results = extract_from_table(
            table=table,
            document_id=parsed.document_id,
            result_date=result_date,
            parser_used=parsed.parser_used,
            category=category,
        )
        all_results.extend(results)

    return all_results
