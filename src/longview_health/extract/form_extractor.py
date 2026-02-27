"""Form-area extractor for structured medical results.

Handles documents where Docling classifies content as form_area with
sequential text items rather than a proper table. Common in portal-style
lab reports (e.g., hCG reports) that use form layouts.

The extractor identifies header items (TESTS, RESULTS, FLAG, UNITS,
REFERENCE INTERVAL, LAB) and chunks subsequent text items by column
count to reconstruct rows.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from longview_health.domain.enums import Confidence, ResultCategory, ValidationStatus
from longview_health.domain.identifiers import result_key
from longview_health.domain.models import MedicalResult, ResultValue

logger = logging.getLogger(__name__)

EXTRACTOR_VERSION = "form-v1"

# Canonical header labels (lowercased for matching)
_HEADER_LABELS: dict[str, str] = {
    "tests": "test",
    "test": "test",
    "test name": "test",
    "results": "result",
    "result": "result",
    "flag": "flag",
    "units": "unit",
    "unit": "unit",
    "reference interval": "reference",
    "reference range": "reference",
    "lab": "lab",
}

# Abnormal flag patterns
_ABNORMAL_FLAGS = {"high", "low", "h", "l", "hh", "ll", "abnormal", "critical", "*"}


def _parse_reference_range(ref: str) -> tuple[str | None, str | None]:
    """Parse a reference range string into (low, high)."""
    ref = ref.strip()
    if not ref:
        return None, None

    m = re.match(r"^[>≥]\s*(\d+\.?\d*)$", ref)
    if m:
        return m.group(1), None

    m = re.match(r"^[<≤]\s*(\d+\.?\d*)$", ref)
    if m:
        return None, m.group(1)

    m = re.match(r"^(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)$", ref)
    if m:
        return m.group(1), m.group(2)

    return None, None


def _find_header_span(texts: list[str]) -> tuple[list[str], int, int]:
    """Find a consecutive run of header items anywhere in the text list.

    Scans the full list for the longest consecutive run of recognized
    header keywords (TESTS, RESULTS, FLAG, etc.). Real form areas often
    have patient metadata before the headers.

    Returns:
        Tuple of (ordered column roles, start index, header count).
        Returns ([], 0, 0) if no valid header span found.
    """
    best_roles: list[str] = []
    best_start = 0
    best_count = 0

    i = 0
    while i < len(texts):
        normalized = texts[i].lower().strip()
        if normalized in _HEADER_LABELS:
            # Start collecting a consecutive run
            run_start = i
            run_roles: list[str] = []
            while i < len(texts):
                n = texts[i].lower().strip()
                if n in _HEADER_LABELS:
                    run_roles.append(_HEADER_LABELS[n])
                    i += 1
                else:
                    break
            # Keep the longest run that has both test + result
            if len(run_roles) > best_count and "test" in run_roles and "result" in run_roles:
                best_roles = run_roles
                best_start = run_start
                best_count = len(run_roles)
        else:
            i += 1

    return best_roles, best_start, best_count


def extract_from_form_group(
    group_texts: list[str],
    doc_id: str,
    result_date: date,
    parser_used: str,
) -> list[MedicalResult]:
    """Extract MedicalResult objects from a form-area group's text items.

    The form area contains sequential text items: first a header row
    (TESTS, RESULTS, FLAG, UNITS, REFERENCE INTERVAL, LAB), then data
    items in the same column order.

    Args:
        group_texts: Ordered text items from the form group.
        doc_id: Document content hash.
        result_date: Date for the results.
        parser_used: Which parser produced the source data.

    Returns:
        List of extracted MedicalResult objects.
    """
    if not group_texts:
        return []

    # Find header span (may be buried after patient metadata)
    roles, header_start, header_count = _find_header_span(group_texts)
    if header_count < 2:
        logger.debug("Form group missing required headers (test, result), skipping")
        return []

    # Data items start after the header span
    data_items = group_texts[header_start + header_count:]
    cols = header_count

    if not data_items or len(data_items) < cols:
        logger.debug("Form group has no data rows")
        return []

    results: list[MedicalResult] = []

    for row_start in range(0, len(data_items) - cols + 1, cols):
        chunk = data_items[row_start:row_start + cols]

        # Map chunk items to roles
        row: dict[str, str] = {}
        for i, role in enumerate(roles):
            row[role] = chunk[i].strip() if i < len(chunk) else ""

        test_name = row.get("test", "").strip()
        value = row.get("result", "").strip()

        if not test_name or not value:
            continue

        unit = row.get("unit", "").strip() or None
        ref_str = row.get("reference", "").strip()
        flag = row.get("flag", "").strip()

        ref_low, ref_high = _parse_reference_range(ref_str)
        is_abnormal = flag.lower() in _ABNORMAL_FLAGS if flag else None

        rid = result_key(doc_id, test_name, result_date)

        results.append(
            MedicalResult(
                id=rid,
                document_id=doc_id,
                test_name=test_name,
                result_value=ResultValue(
                    value=value,
                    unit=unit,
                    reference_low=ref_low,
                    reference_high=ref_high,
                    is_abnormal=is_abnormal,
                ),
                result_date=result_date,
                category=ResultCategory.LAB,
                parser_used=parser_used,
                extractor_version=EXTRACTOR_VERSION,
                confidence=Confidence.HIGH,
                validation_status=ValidationStatus.PENDING,
            )
        )

    logger.info(
        "Extracted %d results from form group (%d headers, %d data items)",
        len(results), header_count, len(data_items),
    )

    return results
