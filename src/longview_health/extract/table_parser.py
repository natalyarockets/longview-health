"""Markdown table parser for structured extraction.

Parses the clean markdown tables that Docling produces directly into
MedicalResult objects. No LLM needed -- the tables already have clear
column headers (TESTS, RESULTS, FLAG, UNITS, REFERENCE INTERVAL).

This is fast and deterministic. The LLM path remains available for
unstructured or ambiguous content.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from longview_health.domain.enums import Confidence, ResultCategory, ValidationStatus
from longview_health.domain.identifiers import result_key
from longview_health.domain.models import MedicalResult, ParsedDocument, ResultValue

logger = logging.getLogger(__name__)

EXTRACTOR_VERSION = "table-v1"

# Column header patterns (case-insensitive matching)
_HEADER_PATTERNS = {
    "test": re.compile(r"test", re.IGNORECASE),
    "result": re.compile(r"result", re.IGNORECASE),
    "flag": re.compile(r"flag", re.IGNORECASE),
    "unit": re.compile(r"unit", re.IGNORECASE),
    "reference": re.compile(r"ref|range|interval", re.IGNORECASE),
    "lab": re.compile(r"^lab$", re.IGNORECASE),
}

# Values that indicate a result was canceled/not performed
_SKIP_VALUES = {"canceled", "cancelled", "tnp", "not performed", "see note", "see below"}

# Abnormal flag patterns
_ABNORMAL_FLAGS = {"high", "low", "h", "l", "hh", "ll", "abnormal", "critical", "*"}


def _parse_reference_range(ref: str) -> tuple[str | None, str | None]:
    """Parse a reference range string into (low, high).

    Handles formats like:
        "70-99"       -> ("70", "99")
        "0.57-1.00"   -> ("0.57", "1.00")
        ">59"         -> ("59", None)
        "<200"        -> (None, "200")
        "3.4-10.8"    -> ("3.4", "10.8")
        "0.450-4.500" -> ("0.450", "4.500")
    """
    ref = ref.strip()
    if not ref:
        return None, None

    # ">X" pattern -- lower bound only
    m = re.match(r"^[>≥]\s*(\d+\.?\d*)$", ref)
    if m:
        return m.group(1), None

    # "<X" pattern -- upper bound only
    m = re.match(r"^[<≤]\s*(\d+\.?\d*)$", ref)
    if m:
        return None, m.group(1)

    # "X-Y" pattern -- range
    m = re.match(r"^(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)$", ref)
    if m:
        return m.group(1), m.group(2)

    return None, None


def _detect_date(markdown: str) -> date | None:
    """Try to find a document/collection date in the markdown text."""
    # Look for "Date/Time Collected" followed by a date
    m = re.search(r"(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}", markdown)
    if m:
        try:
            return date.fromisoformat(m.group(1))
        except ValueError:
            pass

    # Look for any YYYY-MM-DD date
    m = re.search(r"(\d{4}-\d{2}-\d{2})", markdown)
    if m:
        try:
            return date.fromisoformat(m.group(1))
        except ValueError:
            pass

    return None


def _identify_columns(header_cells: list[str]) -> dict[str, int]:
    """Map column roles to their indices based on header text."""
    mapping: dict[str, int] = {}

    for i, cell in enumerate(header_cells):
        cell_clean = cell.strip()
        if not cell_clean:
            continue

        for role, pattern in _HEADER_PATTERNS.items():
            if pattern.search(cell_clean) and role not in mapping:
                mapping[role] = i
                break

    return mapping


def _is_section_header(cells: list[str]) -> bool:
    """Check if a row is a section header (e.g., 'Comp. Metabolic Panel (14)').

    Section headers typically have the same value in all non-empty cells,
    or have content only in the first cell.
    """
    non_empty = [c.strip() for c in cells if c.strip()]
    if len(non_empty) <= 1:
        return True
    # All non-empty cells have the same value
    if len(set(non_empty)) == 1:
        return True
    return False


def _parse_table_block(
    lines: list[str],
    doc_id: str,
    result_date: date,
    parser_used: str,
) -> list[MedicalResult]:
    """Parse a single markdown table block into MedicalResult objects."""
    results: list[MedicalResult] = []

    # Find header row and separator
    header_idx = None
    data_start = None
    for i, line in enumerate(lines):
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            col_map = _identify_columns(cells)
            if "test" in col_map and "result" in col_map:
                header_idx = i
                # Next line should be separator (|---|---|...)
                if i + 1 < len(lines) and re.match(r"^\|[\s\-|]+\|$", lines[i + 1]):
                    data_start = i + 2
                else:
                    data_start = i + 1
                break

    if header_idx is None or data_start is None:
        return results

    # Parse data rows
    for line in lines[data_start:]:
        if not (line.startswith("|") and line.endswith("|")):
            continue

        cells = [c.strip() for c in line.split("|")[1:-1]]

        if _is_section_header(cells):
            continue

        # Pad short rows to match header column count
        expected_cols = max(col_map.values()) + 1 if col_map else len(cells)
        while len(cells) < expected_cols:
            cells.append("")

        # Extract values by column mapping
        test_name = cells[col_map["test"]] if "test" in col_map and col_map["test"] < len(cells) else ""
        value = cells[col_map["result"]] if "result" in col_map and col_map["result"] < len(cells) else ""
        flag = cells[col_map["flag"]] if "flag" in col_map and col_map["flag"] < len(cells) else ""
        unit = cells[col_map["unit"]] if "unit" in col_map and col_map["unit"] < len(cells) else ""
        ref_str = cells[col_map["reference"]] if "reference" in col_map and col_map["reference"] < len(cells) else ""

        test_name = test_name.strip()
        value = value.strip()

        # Skip empty, canceled, or non-result rows
        if not test_name or not value:
            continue
        if value.lower() in _SKIP_VALUES:
            continue
        # Skip rows that look like footnotes or metadata
        if test_name.startswith(".") or test_name.startswith("01"):
            continue

        # Parse reference range
        ref_low, ref_high = _parse_reference_range(ref_str.strip())

        # Determine abnormality
        is_abnormal = flag.strip().lower() in _ABNORMAL_FLAGS if flag.strip() else None

        rid = result_key(doc_id, test_name, result_date)

        results.append(
            MedicalResult(
                id=rid,
                document_id=doc_id,
                test_name=test_name,
                result_value=ResultValue(
                    value=value,
                    unit=unit.strip() or None,
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

    return results


def extract_from_table_item(
    table_item: object,
    doc_id: str,
    result_date: date,
    parser_used: str,
) -> list[MedicalResult]:
    """Extract MedicalResult objects directly from a Docling TableItem.

    Works with Docling's structured table data (grid, cells, column_header
    flags) instead of re-parsing markdown. Faster and more reliable than
    the markdown-based extract() path.

    Args:
        table_item: A Docling TableItem with a .data attribute.
        doc_id: Document content hash.
        result_date: Date for the results.
        parser_used: Which parser produced the source data.

    Returns:
        List of extracted MedicalResult objects.
    """
    data = getattr(table_item, "data", None)
    if data is None:
        return []

    # Build 2D grid from table cells
    grid: list[list[str]] = [
        [""] * data.num_cols for _ in range(data.num_rows)
    ]
    header_rows: set[int] = set()

    for cell in data.table_cells:
        row = cell.start_row_offset_idx
        col = cell.start_col_offset_idx
        if 0 <= row < data.num_rows and 0 <= col < data.num_cols:
            grid[row][col] = cell.text.strip()
            if cell.column_header:
                header_rows.add(row)

    # Separate headers from data rows
    if header_rows:
        max_header_row = max(header_rows)
        headers = grid[max_header_row]
        data_rows = grid[max_header_row + 1:]
    elif grid:
        headers = grid[0]
        data_rows = grid[1:]
    else:
        return []

    # Map column roles
    col_map = _identify_columns(headers)
    if "test" not in col_map or "result" not in col_map:
        return []

    results: list[MedicalResult] = []

    for cells in data_rows:
        if _is_section_header(cells):
            continue

        # Pad short rows
        while len(cells) < len(headers):
            cells.append("")

        test_name = cells[col_map["test"]] if col_map["test"] < len(cells) else ""
        value = cells[col_map["result"]] if col_map["result"] < len(cells) else ""
        flag = cells[col_map["flag"]] if "flag" in col_map and col_map["flag"] < len(cells) else ""
        unit = cells[col_map["unit"]] if "unit" in col_map and col_map["unit"] < len(cells) else ""
        ref_str = cells[col_map["reference"]] if "reference" in col_map and col_map["reference"] < len(cells) else ""

        test_name = test_name.strip()
        value = value.strip()

        if not test_name or not value:
            continue
        if value.lower() in _SKIP_VALUES:
            continue
        if test_name.startswith(".") or test_name.startswith("01"):
            continue

        ref_low, ref_high = _parse_reference_range(ref_str.strip())
        is_abnormal = flag.strip().lower() in _ABNORMAL_FLAGS if flag.strip() else None

        rid = result_key(doc_id, test_name, result_date)

        results.append(
            MedicalResult(
                id=rid,
                document_id=doc_id,
                test_name=test_name,
                result_value=ResultValue(
                    value=value,
                    unit=unit.strip() or None,
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

    return results


def _dedup_table_columns(markdown: str) -> str:
    """Remove duplicate columns from markdown tables.

    Docling sometimes produces tables where the same content is repeated across
    multiple columns. This cleans them up for reliable parsing.
    """
    lines = markdown.split("\n")
    cleaned = []
    for line in lines:
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.split("|")]
            cells = cells[1:-1]
            if len(cells) > 2:
                seen: set[str] = set()
                unique = []
                for cell in cells:
                    normalized = cell.strip().strip("-")
                    if normalized not in seen:
                        seen.add(normalized)
                        unique.append(cell)
                if len(unique) < len(cells):
                    line = "| " + " | ".join(unique) + " |"
        cleaned.append(line)
    return "\n".join(cleaned)


def extract(
    parsed: ParsedDocument,
    fallback_date: date,
) -> list[MedicalResult]:
    """Extract structured medical results by parsing markdown tables directly.

    Fast, deterministic extraction for documents with structured tables.
    No LLM required.

    Args:
        parsed: Output of the document parsing stage (must have markdown).
        fallback_date: Date to use if no date found in the document.

    Returns:
        List of extracted MedicalResult objects.
    """
    if not parsed.markdown.strip():
        logger.warning("Empty markdown for document %s", parsed.document_id)
        return []

    # Clean up duplicated columns
    cleaned = _dedup_table_columns(parsed.markdown)

    # Try to find a date in the document
    doc_date = _detect_date(cleaned) or fallback_date

    # Split markdown into table blocks (consecutive lines starting with |)
    lines = cleaned.split("\n")
    table_blocks: list[list[str]] = []
    current_block: list[str] = []

    for line in lines:
        if line.startswith("|"):
            current_block.append(line)
        else:
            if current_block:
                table_blocks.append(current_block)
                current_block = []
    if current_block:
        table_blocks.append(current_block)

    # Parse each table block
    all_results: list[MedicalResult] = []
    for block in table_blocks:
        results = _parse_table_block(
            block,
            doc_id=parsed.document_id,
            result_date=doc_date,
            parser_used=parsed.parser_used,
        )
        all_results.extend(results)

    logger.info(
        "Extracted %d results from %d table blocks in document %s",
        len(all_results), len(table_blocks), parsed.document_id,
    )

    return all_results
