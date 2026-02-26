"""Tests for document parsers.

Tests the Docling parser, pdfplumber parser, and parser chain
against generated PDF fixtures.
"""

from pathlib import Path

import pytest

from longview_health.core.errors import ParseError
from longview_health.domain.models import ParsedDocument
from longview_health.extract import parser_chain, pdf_parser


@pytest.fixture
def simple_lab_pdf(tmp_path: Path) -> Path:
    """Generate a simple lab report PDF for testing."""
    from tests.extract.generate_fixtures import create_simple_lab_pdf

    pdf_path = tmp_path / "simple_lab_report.pdf"
    create_simple_lab_pdf(pdf_path)
    return pdf_path


@pytest.fixture
def empty_file(tmp_path: Path) -> Path:
    """Create an empty file."""
    path = tmp_path / "empty.pdf"
    path.write_bytes(b"")
    return path


@pytest.fixture
def text_file(tmp_path: Path) -> Path:
    """Create a non-PDF file."""
    path = tmp_path / "notes.txt"
    path.write_text("not a pdf")
    return path


# -- pdfplumber parser tests --


class TestPdfParser:
    def test_parse_simple_pdf(self, simple_lab_pdf: Path) -> None:
        result = pdf_parser.parse(simple_lab_pdf)
        assert isinstance(result, ParsedDocument)
        assert result.parser_used == "pdfplumber"
        assert result.page_count == 1
        assert len(result.text_blocks) > 0

        # Verify lab content is in the text
        full_text = " ".join(result.text_blocks)
        assert "Jane Doe" in full_text
        assert "Hemoglobin" in full_text

    def test_parse_nonexistent_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ParseError, match="not found"):
            pdf_parser.parse(tmp_path / "ghost.pdf")

    def test_parse_non_pdf_raises(self, text_file: Path) -> None:
        with pytest.raises(ParseError, match="only handles PDFs"):
            pdf_parser.parse(text_file)

    def test_document_id_is_content_hash(self, simple_lab_pdf: Path) -> None:
        from longview_health.domain.identifiers import content_hash

        result = pdf_parser.parse(simple_lab_pdf)
        assert result.document_id == content_hash(simple_lab_pdf)


# -- parser chain tests --


class TestParserChain:
    def test_chain_parses_pdf(self, simple_lab_pdf: Path) -> None:
        result = parser_chain.parse(simple_lab_pdf)
        assert isinstance(result, ParsedDocument)
        assert result.parser_used in {"docling", "pdfplumber"}
        assert len(result.text_blocks) > 0

    def test_chain_rejects_unsupported_type(self, text_file: Path) -> None:
        with pytest.raises(ParseError, match="Unsupported file type"):
            parser_chain.parse(text_file)

    def test_chain_rejects_nonexistent(self, tmp_path: Path) -> None:
        with pytest.raises(ParseError, match="not found"):
            parser_chain.parse(tmp_path / "ghost.pdf")

    def test_parsed_document_has_document_id(self, simple_lab_pdf: Path) -> None:
        result = parser_chain.parse(simple_lab_pdf)
        assert len(result.document_id) == 64  # SHA-256 hex

    def test_parse_quality_check(self) -> None:
        """Verify the quality check logic."""
        good = ParsedDocument(
            document_id="x",
            text_blocks=["This is a real lab report with content"],
            tables=[],
            parser_used="test",
        )
        empty = ParsedDocument(
            document_id="x",
            text_blocks=["short"],
            tables=[],
            parser_used="test",
        )
        assert parser_chain._parse_quality_ok(good) is True
        assert parser_chain._parse_quality_ok(empty) is False
