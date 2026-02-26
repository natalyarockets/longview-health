"""Tests for table-based structured extraction."""

from datetime import date

from longview_health.domain.enums import Confidence, ResultCategory
from longview_health.domain.models import ParsedDocument, ParsedTable
from longview_health.extract import table_extractor
from longview_health.extract.table_extractor import (
    classify_headers,
    detect_abnormal,
    parse_reference_range,
)


# -- Reference range parsing --


class TestParseReferenceRange:
    def test_simple_range(self) -> None:
        assert parse_reference_range("4.5-11.0") == ("4.5", "11.0")

    def test_range_with_spaces(self) -> None:
        assert parse_reference_range("4.5 - 11.0") == ("4.5", "11.0")

    def test_range_with_en_dash(self) -> None:
        assert parse_reference_range("4.5\u201311.0") == ("4.5", "11.0")

    def test_less_than(self) -> None:
        assert parse_reference_range("< 200") == (None, "200")

    def test_greater_than(self) -> None:
        assert parse_reference_range("> 40") == ("40", None)

    def test_empty(self) -> None:
        assert parse_reference_range("") == (None, None)

    def test_nonsense(self) -> None:
        assert parse_reference_range("normal") == (None, None)


# -- Abnormality detection --


class TestDetectAbnormal:
    def test_flag_high(self) -> None:
        assert detect_abnormal("H", "200", "100", "199") is True

    def test_flag_low(self) -> None:
        assert detect_abnormal("L", "3.0", "4.5", "11.0") is True

    def test_flag_normal(self) -> None:
        assert detect_abnormal("N", "7.5", "4.5", "11.0") is False

    def test_no_flag_in_range(self) -> None:
        assert detect_abnormal(None, "7.5", "4.5", "11.0") is False

    def test_no_flag_above_range(self) -> None:
        assert detect_abnormal(None, "15.0", "4.5", "11.0") is True

    def test_no_flag_below_range(self) -> None:
        assert detect_abnormal(None, "2.0", "4.5", "11.0") is True

    def test_nonnumeric_value(self) -> None:
        assert detect_abnormal(None, "positive", None, None) is None


# -- Header classification --


class TestClassifyHeaders:
    def test_standard_lab_headers(self) -> None:
        col_map = classify_headers(["Test", "Result", "Unit", "Reference Range"])
        assert col_map.is_valid
        assert col_map.test_name == 0
        assert col_map.value == 1
        assert col_map.unit == 2
        assert col_map.reference_range == 3

    def test_alternate_headers(self) -> None:
        col_map = classify_headers(["Analyte", "Value", "Units", "Ref. Range", "Flag"])
        assert col_map.is_valid
        assert col_map.test_name == 0
        assert col_map.value == 1
        assert col_map.flag == 4

    def test_fallback_heuristic(self) -> None:
        """When headers don't match patterns, use positional fallback."""
        col_map = classify_headers(["Cholesterol Panel", "mg/dL", "K/uL", "Norm"])
        assert col_map.is_valid  # Falls back to first two columns

    def test_empty_headers(self) -> None:
        col_map = classify_headers([])
        assert not col_map.is_valid


# -- Full table extraction --


class TestTableExtraction:
    def test_extract_from_standard_table(self) -> None:
        table = ParsedTable(
            headers=["Test", "Result", "Unit", "Reference Range"],
            rows=[
                ["WBC", "7.5", "K/uL", "4.5-11.0"],
                ["RBC", "4.8", "M/uL", "4.0-5.5"],
                ["Hemoglobin", "14.2", "g/dL", "12.0-16.0"],
            ],
            page=1,
        )

        results = table_extractor.extract_from_table(
            table=table,
            document_id="doc123",
            result_date=date(2024, 3, 15),
            parser_used="docling",
        )

        assert len(results) == 3
        assert results[0].test_name == "WBC"
        assert results[0].result_value.value == "7.5"
        assert results[0].result_value.unit == "K/uL"
        assert results[0].result_value.reference_low == "4.5"
        assert results[0].result_value.reference_high == "11.0"
        assert results[0].result_value.is_abnormal is False
        assert results[0].parser_used == "docling"
        assert results[0].extractor_version == "table-v1"
        assert results[0].confidence == Confidence.MEDIUM

    def test_extract_with_flags(self) -> None:
        table = ParsedTable(
            headers=["Test", "Result", "Unit", "Reference Range", "Flag"],
            rows=[
                ["LDL", "180", "mg/dL", "< 130", "H"],
                ["HDL", "55", "mg/dL", "> 40", ""],
            ],
        )

        results = table_extractor.extract_from_table(
            table=table,
            document_id="doc456",
            result_date=date(2024, 3, 15),
            parser_used="docling",
        )

        assert len(results) == 2
        assert results[0].test_name == "LDL"
        assert results[0].result_value.is_abnormal is True
        assert results[1].test_name == "HDL"

    def test_skip_empty_rows(self) -> None:
        table = ParsedTable(
            headers=["Test", "Result"],
            rows=[
                ["WBC", "7.5"],
                ["", ""],
                ["RBC", "4.8"],
            ],
        )

        results = table_extractor.extract_from_table(
            table=table,
            document_id="doc789",
            result_date=date(2024, 3, 15),
            parser_used="docling",
        )

        assert len(results) == 2

    def test_extract_from_parsed_document(self) -> None:
        """Test the top-level extract function with a full ParsedDocument."""
        parsed = ParsedDocument(
            document_id="doc_abc",
            text_blocks=["Lab Report"],
            tables=[
                ParsedTable(
                    headers=["Component", "Value", "Units", "Range"],
                    rows=[
                        ["Glucose", "95", "mg/dL", "70-100"],
                        ["BUN", "15", "mg/dL", "7-20"],
                    ],
                ),
            ],
            parser_used="docling",
        )

        results = table_extractor.extract(
            parsed, result_date=date(2024, 6, 1)
        )

        assert len(results) == 2
        assert results[0].test_name == "Glucose"
        assert results[0].result_value.is_abnormal is False
        assert results[0].category == ResultCategory.LAB

    def test_unmappable_table_returns_empty(self) -> None:
        """A table with unrecognizable headers should return no results."""
        table = ParsedTable(
            headers=["A"],
            rows=[["foo"]],
        )

        results = table_extractor.extract_from_table(
            table=table,
            document_id="doc_x",
            result_date=date(2024, 1, 1),
            parser_used="docling",
        )

        assert results == []
