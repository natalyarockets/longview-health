"""Tests for extraction chain orchestration."""

from datetime import date

from longview_health.domain.enums import Confidence, ResultCategory
from longview_health.domain.models import ParsedDocument, ParsedTable
from longview_health.extract import extraction_chain


class TestExtractionChain:
    def test_table_results_preferred_over_text(self) -> None:
        """When table and text extract the same result, table wins."""
        parsed = ParsedDocument(
            document_id="doc1",
            text_blocks=["WBC: 7.5 K/uL (4.5-11.0)"],
            tables=[
                ParsedTable(
                    headers=["Test", "Result", "Unit", "Reference Range"],
                    rows=[["WBC", "7.5", "K/uL", "4.5-11.0"]],
                )
            ],
            parser_used="docling",
        )

        results = extraction_chain.extract(parsed, result_date=date(2024, 3, 15))

        # Should have exactly 1 result (deduplicated), from table extractor
        wbc_results = [r for r in results if r.test_name == "WBC"]
        assert len(wbc_results) == 1
        assert wbc_results[0].extractor_version == "table-v1"
        assert wbc_results[0].confidence == Confidence.MEDIUM

    def test_text_fills_gaps(self) -> None:
        """Text extractor adds results not found in tables."""
        parsed = ParsedDocument(
            document_id="doc2",
            text_blocks=["TSH: 2.1 mIU/L (0.4-4.0)"],
            tables=[
                ParsedTable(
                    headers=["Test", "Result", "Unit", "Reference Range"],
                    rows=[["WBC", "7.5", "K/uL", "4.5-11.0"]],
                )
            ],
            parser_used="docling",
        )

        results = extraction_chain.extract(parsed, result_date=date(2024, 3, 15))

        names = {r.test_name for r in results}
        assert "WBC" in names
        assert "TSH" in names

    def test_tables_only(self) -> None:
        parsed = ParsedDocument(
            document_id="doc3",
            text_blocks=[],
            tables=[
                ParsedTable(
                    headers=["Test", "Result"],
                    rows=[["Glucose", "95"]],
                )
            ],
            parser_used="docling",
        )

        results = extraction_chain.extract(parsed, result_date=date(2024, 3, 15))
        assert len(results) == 1
        assert results[0].test_name == "Glucose"

    def test_text_only(self) -> None:
        parsed = ParsedDocument(
            document_id="doc4",
            text_blocks=["Hemoglobin: 14.2 g/dL"],
            tables=[],
            parser_used="pdfplumber",
        )

        results = extraction_chain.extract(parsed, result_date=date(2024, 3, 15))
        assert len(results) == 1
        assert results[0].test_name == "Hemoglobin"

    def test_empty_document(self) -> None:
        parsed = ParsedDocument(
            document_id="doc5",
            text_blocks=[],
            tables=[],
            parser_used="docling",
        )

        results = extraction_chain.extract(parsed, result_date=date(2024, 3, 15))
        assert results == []

    def test_category_propagates(self) -> None:
        parsed = ParsedDocument(
            document_id="doc6",
            text_blocks=["Hemoglobin: 14.2 g/dL"],
            tables=[],
            parser_used="docling",
        )

        results = extraction_chain.extract(
            parsed,
            result_date=date(2024, 3, 15),
            category=ResultCategory.IMAGING,
        )

        assert all(r.category == ResultCategory.IMAGING for r in results)

    def test_provenance_tracked(self) -> None:
        """Verify parser_used flows through to results."""
        parsed = ParsedDocument(
            document_id="doc7",
            text_blocks=[],
            tables=[
                ParsedTable(
                    headers=["Test", "Result"],
                    rows=[["WBC", "7.5"]],
                )
            ],
            parser_used="docling",
        )

        results = extraction_chain.extract(parsed, result_date=date(2024, 3, 15))
        assert results[0].parser_used == "docling"
