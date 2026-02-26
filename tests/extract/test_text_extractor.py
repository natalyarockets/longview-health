"""Tests for text-based structured extraction."""

from datetime import date

from longview_health.domain.enums import Confidence, ResultCategory
from longview_health.domain.models import ParsedDocument
from longview_health.extract import text_extractor


class TestTextExtraction:
    def test_colon_separated_with_ref_range(self) -> None:
        parsed = ParsedDocument(
            document_id="doc1",
            text_blocks=["Hemoglobin: 14.2 g/dL (ref 12.0-16.0)"],
            tables=[],
            parser_used="pdfplumber",
        )

        results = text_extractor.extract(parsed, result_date=date(2024, 3, 15))

        assert len(results) == 1
        r = results[0]
        assert r.test_name == "Hemoglobin"
        assert r.result_value.value == "14.2"
        assert r.result_value.reference_low == "12.0"
        assert r.result_value.reference_high == "16.0"
        assert r.confidence == Confidence.LOW
        assert r.parser_used == "pdfplumber"
        assert r.extractor_version == "text-v1"

    def test_colon_separated_no_ref(self) -> None:
        parsed = ParsedDocument(
            document_id="doc2",
            text_blocks=["TSH: 2.1 mIU/L"],
            tables=[],
            parser_used="pdfplumber",
        )

        results = text_extractor.extract(parsed, result_date=date(2024, 3, 15))

        assert len(results) == 1
        assert results[0].test_name == "TSH"
        assert results[0].result_value.value == "2.1"

    def test_multiple_results_in_block(self) -> None:
        parsed = ParsedDocument(
            document_id="doc3",
            text_blocks=[
                "Glucose: 95 mg/dL (70-100)\n"
                "BUN: 15 mg/dL (7-20)\n"
                "Creatinine: 1.0 mg/dL (0.7-1.3)"
            ],
            tables=[],
            parser_used="pdfplumber",
        )

        results = text_extractor.extract(parsed, result_date=date(2024, 3, 15))

        assert len(results) == 3
        names = {r.test_name for r in results}
        assert "Glucose" in names
        assert "BUN" in names
        assert "Creatinine" in names

    def test_skips_non_result_lines(self) -> None:
        parsed = ParsedDocument(
            document_id="doc4",
            text_blocks=[
                "Patient: John Smith\n"
                "Date: 2024-03-15\n"
                "Lab Report\n"
                "WBC: 7.5 K/uL"
            ],
            tables=[],
            parser_used="pdfplumber",
        )

        results = text_extractor.extract(parsed, result_date=date(2024, 3, 15))

        # Should only find WBC, not "Patient" or "Date"
        names = {r.test_name for r in results}
        assert "Patient" not in names
        assert "Date" not in names

    def test_deduplicates(self) -> None:
        parsed = ParsedDocument(
            document_id="doc5",
            text_blocks=[
                "WBC: 7.5 K/uL",
                "WBC: 7.5 K/uL",  # Duplicate in separate block
            ],
            tables=[],
            parser_used="pdfplumber",
        )

        results = text_extractor.extract(parsed, result_date=date(2024, 3, 15))
        assert len(results) == 1

    def test_empty_document(self) -> None:
        parsed = ParsedDocument(
            document_id="doc6",
            text_blocks=[],
            tables=[],
            parser_used="pdfplumber",
        )

        results = text_extractor.extract(parsed, result_date=date(2024, 3, 15))
        assert results == []
