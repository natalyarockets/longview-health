"""Tests for extraction chain (extract_smart)."""

from datetime import date
from unittest.mock import MagicMock, patch

from longview_health.domain.enums import Confidence, ResultCategory, ValidationStatus
from longview_health.domain.models import (
    DoclingConversion,
    MedicalResult,
    ParsedDocument,
    ResultValue,
)
from longview_health.extract.extraction_chain import extract, extract_smart


def _make_parsed(markdown: str = "# Lab Report", tables: list | None = None) -> ParsedDocument:
    return ParsedDocument(
        document_id="doc123",
        markdown=markdown,
        text_blocks=["Lab Report"],
        tables=tables or [],
        parser_used="docling",
    )


def _make_result(test_name: str, value: str, extractor: str = "llm-v1") -> MedicalResult:
    return MedicalResult(
        id=f"doc123_{test_name}_2025-02-21",
        document_id="doc123",
        test_name=test_name,
        result_value=ResultValue(value=value),
        result_date=date(2025, 2, 21),
        category=ResultCategory.LAB,
        parser_used="docling",
        extractor_version=extractor,
        confidence=Confidence.MEDIUM,
        validation_status=ValidationStatus.PENDING,
    )


class TestExtractLegacy:
    def test_returns_list(self) -> None:
        parsed = _make_parsed("| TESTS | RESULT |\n|---|---|\n| WBC | 7.5 |")
        results = extract(parsed, fallback_date=date(2025, 2, 21))
        assert isinstance(results, list)


class TestExtractSmart:
    def test_fallback_to_markdown_when_no_docling_doc(self) -> None:
        """When docling_document is None, falls back to legacy table parser."""
        parsed = _make_parsed("| TESTS | RESULT |\n|---|---|\n| WBC | 7.5 |")
        conversion = DoclingConversion(parsed=parsed, docling_document=None)

        results = extract_smart(conversion, fallback_date=date(2025, 2, 21))

        assert len(results) == 1
        assert results[0].test_name == "WBC"
        assert results[0].extractor_version == "table-v1"

    def test_empty_regions_falls_back(self) -> None:
        """If region grouping finds nothing, fall back to markdown parser."""
        doc = MagicMock()
        doc.tables = []
        doc.groups = []
        doc.texts = []

        parsed = _make_parsed("| TESTS | RESULT |\n|---|---|\n| WBC | 7.5 |")
        conversion = DoclingConversion(parsed=parsed, docling_document=doc)

        results = extract_smart(conversion, fallback_date=date(2025, 2, 21))

        # Falls back to markdown table parser
        assert len(results) == 1
        assert results[0].test_name == "WBC"

    @patch("longview_health.extract.extraction_chain.llm_extractor")
    def test_dispatches_text_regions_to_llm(self, mock_llm) -> None:
        """Text regions (non-table) are sent to the LLM extractor."""
        mock_llm.extract_region.return_value = [_make_result("hCG", "<1")]

        # Build a mock Docling doc with text items but no tables
        text_item = MagicMock()
        text_item.text = "hCG Beta Subunit: <1 mIU/mL"
        text_item.label = MagicMock()
        text_item.label.value = "text"
        prov = MagicMock()
        prov.page_no = 1
        prov.bbox.l = 50
        prov.bbox.t = 500
        prov.bbox.r = 400
        prov.bbox.b = 480
        prov.bbox.coord_origin = MagicMock()
        prov.bbox.coord_origin.value = "BOTTOMLEFT"
        text_item.prov = [prov]

        doc = MagicMock()
        doc.tables = []
        doc.texts = [text_item]

        parsed = _make_parsed("2025-02-21\nhCG Beta Subunit: <1 mIU/mL")
        conversion = DoclingConversion(parsed=parsed, docling_document=doc)

        results = extract_smart(conversion, fallback_date=date(2025, 2, 21))

        assert len(results) == 1
        assert results[0].test_name == "hCG"
        mock_llm.extract_region.assert_called_once()

    def test_dispatches_table_regions_to_table_extractor(self) -> None:
        """Table regions use the deterministic table extractor."""
        # Build a mock table with grid data
        cell1 = MagicMock()
        cell1.text = "WBC"
        cell1.start_row_offset_idx = 1
        cell1.start_col_offset_idx = 0
        cell1.column_header = False

        cell2 = MagicMock()
        cell2.text = "7.5"
        cell2.start_row_offset_idx = 1
        cell2.start_col_offset_idx = 1
        cell2.column_header = False

        header1 = MagicMock()
        header1.text = "TESTS"
        header1.start_row_offset_idx = 0
        header1.start_col_offset_idx = 0
        header1.column_header = True

        header2 = MagicMock()
        header2.text = "RESULT"
        header2.start_row_offset_idx = 0
        header2.start_col_offset_idx = 1
        header2.column_header = True

        data = MagicMock()
        data.num_rows = 2
        data.num_cols = 2
        data.table_cells = [header1, header2, cell1, cell2]

        table_item = MagicMock()
        table_item.data = data
        prov = MagicMock()
        prov.page_no = 1
        prov.bbox.l = 50
        prov.bbox.t = 700
        prov.bbox.r = 500
        prov.bbox.b = 400
        table_item.prov = [prov]

        doc = MagicMock()
        doc.tables = [table_item]
        doc.texts = []

        parsed = _make_parsed("2025-02-21\n| TESTS | RESULT |\n|---|---|\n| WBC | 7.5 |")
        conversion = DoclingConversion(parsed=parsed, docling_document=doc)

        results = extract_smart(conversion, fallback_date=date(2025, 2, 21))

        # Table extractor should handle this
        assert any(r.test_name == "WBC" for r in results)
        table_results = [r for r in results if r.extractor_version == "table-v1"]
        assert len(table_results) >= 1
