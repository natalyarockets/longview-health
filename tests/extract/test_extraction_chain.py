"""Tests for extraction chain (extract_smart)."""

from datetime import date
from unittest.mock import MagicMock

from longview_health.domain.enums import Confidence, ResultCategory
from longview_health.domain.models import DoclingConversion, ParsedDocument
from longview_health.extract.extraction_chain import extract, extract_smart


def _make_parsed(markdown: str = "# Lab Report", tables: list | None = None) -> ParsedDocument:
    return ParsedDocument(
        document_id="doc123",
        markdown=markdown,
        text_blocks=["Lab Report"],
        tables=tables or [],
        parser_used="docling",
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

    def test_routes_form_sections(self) -> None:
        """Mock a Docling doc with a form area containing lab headers."""
        # Build mock Docling document
        text_items = []
        for i, text in enumerate([
            "TESTS", "RESULTS", "FLAG", "UNITS", "REFERENCE INTERVAL", "LAB",
            "hCG", "<1", "", "mIU/mL", "<5", "BN",
        ]):
            item = MagicMock()
            item.text = text
            item.self_ref = f"#/texts/{i}"
            text_items.append(item)

        group = MagicMock()
        group.self_ref = "#/groups/0"
        group.label = MagicMock()
        group.label.value = "form_area"
        # Set up children refs that resolve to text items
        children = []
        for ti in text_items:
            ref = MagicMock()
            ref.resolve = MagicMock(return_value=ti)
            ref.cref = ti.self_ref
            children.append(ref)
        group.children = children

        doc = MagicMock()
        doc.tables = []
        doc.groups = [group]
        doc.texts = []

        parsed = _make_parsed("2025-02-21\nhCG report content")
        conversion = DoclingConversion(parsed=parsed, docling_document=doc)

        results = extract_smart(conversion, fallback_date=date(2025, 2, 21))

        assert len(results) == 1
        assert results[0].test_name == "hCG"
        assert results[0].result_value.value == "<1"
        assert results[0].extractor_version == "form-v1"
        assert results[0].confidence == Confidence.HIGH

    def test_empty_sections_falls_back(self) -> None:
        """If section classification finds nothing, fall back to markdown parser."""
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
