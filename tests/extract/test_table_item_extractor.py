"""Tests for extract_from_table_item (Docling TableItem direct extraction)."""

from datetime import date
from unittest.mock import MagicMock

from longview_health.domain.enums import Confidence, ResultCategory
from longview_health.extract.table_parser import extract_from_table_item


def _make_cell(
    text: str,
    row: int,
    col: int,
    column_header: bool = False,
) -> MagicMock:
    """Create a mock Docling TableCell."""
    cell = MagicMock()
    cell.text = text
    cell.start_row_offset_idx = row
    cell.start_col_offset_idx = col
    cell.column_header = column_header
    return cell


def _make_table_item(
    cells: list[MagicMock],
    num_rows: int,
    num_cols: int,
) -> MagicMock:
    """Create a mock Docling TableItem with a .data attribute."""
    data = MagicMock()
    data.table_cells = cells
    data.num_rows = num_rows
    data.num_cols = num_cols
    table = MagicMock()
    table.data = data
    return table


class TestExtractFromTableItem:
    def test_basic_lab_table(self) -> None:
        """Standard lab table with headers + data rows."""
        cells = [
            # Header row
            _make_cell("TESTS", 0, 0, column_header=True),
            _make_cell("RESULT", 0, 1, column_header=True),
            _make_cell("FLAG", 0, 2, column_header=True),
            _make_cell("UNITS", 0, 3, column_header=True),
            _make_cell("REFERENCE INTERVAL", 0, 4, column_header=True),
            # Data row 1
            _make_cell("WBC", 1, 0),
            _make_cell("7.5", 1, 1),
            _make_cell("", 1, 2),
            _make_cell("K/uL", 1, 3),
            _make_cell("4.5-11.0", 1, 4),
            # Data row 2
            _make_cell("RBC", 2, 0),
            _make_cell("4.80", 2, 1),
            _make_cell("", 2, 2),
            _make_cell("M/uL", 2, 3),
            _make_cell("4.00-5.50", 2, 4),
        ]
        table = _make_table_item(cells, num_rows=3, num_cols=5)

        results = extract_from_table_item(
            table_item=table,
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )

        assert len(results) == 2
        assert results[0].test_name == "WBC"
        assert results[0].result_value.value == "7.5"
        assert results[0].result_value.unit == "K/uL"
        assert results[0].result_value.reference_low == "4.5"
        assert results[0].result_value.reference_high == "11.0"
        assert results[0].confidence == Confidence.HIGH
        assert results[0].category == ResultCategory.LAB
        assert results[0].extractor_version == "table-v1"

    def test_abnormal_flag(self) -> None:
        cells = [
            _make_cell("TESTS", 0, 0, column_header=True),
            _make_cell("RESULT", 0, 1, column_header=True),
            _make_cell("FLAG", 0, 2, column_header=True),
            _make_cell("Glucose", 1, 0),
            _make_cell("250", 1, 1),
            _make_cell("High", 1, 2),
        ]
        table = _make_table_item(cells, num_rows=2, num_cols=3)

        results = extract_from_table_item(
            table_item=table,
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )

        assert len(results) == 1
        assert results[0].result_value.is_abnormal is True

    def test_no_data_attribute(self) -> None:
        table = MagicMock()
        table.data = None

        results = extract_from_table_item(
            table_item=table,
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )

        assert results == []

    def test_missing_required_columns(self) -> None:
        """Table without test/result columns returns empty."""
        cells = [
            _make_cell("Name", 0, 0, column_header=True),
            _make_cell("Age", 0, 1, column_header=True),
            _make_cell("John", 1, 0),
            _make_cell("30", 1, 1),
        ]
        table = _make_table_item(cells, num_rows=2, num_cols=2)

        results = extract_from_table_item(
            table_item=table,
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )

        assert results == []

    def test_skips_canceled_values(self) -> None:
        cells = [
            _make_cell("TESTS", 0, 0, column_header=True),
            _make_cell("RESULT", 0, 1, column_header=True),
            _make_cell("WBC", 1, 0),
            _make_cell("Canceled", 1, 1),
        ]
        table = _make_table_item(cells, num_rows=2, num_cols=2)

        results = extract_from_table_item(
            table_item=table,
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )

        assert results == []

    def test_skips_section_headers(self) -> None:
        cells = [
            _make_cell("TESTS", 0, 0, column_header=True),
            _make_cell("RESULT", 0, 1, column_header=True),
            # Section header (same value, rest empty)
            _make_cell("CBC", 1, 0),
            _make_cell("", 1, 1),
            # Actual data
            _make_cell("WBC", 2, 0),
            _make_cell("7.5", 2, 1),
        ]
        table = _make_table_item(cells, num_rows=3, num_cols=2)

        results = extract_from_table_item(
            table_item=table,
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )

        assert len(results) == 1
        assert results[0].test_name == "WBC"

    def test_no_header_row_uses_first_row(self) -> None:
        """When no cells are marked as column_header, treat first row as header."""
        cells = [
            _make_cell("TESTS", 0, 0),
            _make_cell("RESULT", 0, 1),
            _make_cell("WBC", 1, 0),
            _make_cell("7.5", 1, 1),
        ]
        table = _make_table_item(cells, num_rows=2, num_cols=2)

        results = extract_from_table_item(
            table_item=table,
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )

        assert len(results) == 1
        assert results[0].test_name == "WBC"
