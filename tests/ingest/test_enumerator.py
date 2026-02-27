"""Tests for ingest/enumerator -- file discovery."""

from pathlib import Path

from longview_health.domain.enums import DocumentType
from longview_health.ingest.enumerator import enumerate_documents, suffix_to_document_type


class TestSuffixToDocumentType:
    def test_pdf(self) -> None:
        assert suffix_to_document_type(".pdf") == DocumentType.PDF

    def test_png(self) -> None:
        assert suffix_to_document_type(".png") == DocumentType.PNG

    def test_jpg(self) -> None:
        assert suffix_to_document_type(".jpg") == DocumentType.JPG

    def test_jpeg(self) -> None:
        assert suffix_to_document_type(".jpeg") == DocumentType.JPG

    def test_tiff(self) -> None:
        assert suffix_to_document_type(".tiff") == DocumentType.TIFF

    def test_case_insensitive(self) -> None:
        assert suffix_to_document_type(".PDF") == DocumentType.PDF

    def test_unsupported_returns_none(self) -> None:
        assert suffix_to_document_type(".docx") is None


class TestEnumerateDocuments:
    def test_finds_supported_files(self, tmp_path: Path) -> None:
        (tmp_path / "report.pdf").write_bytes(b"fake pdf")
        (tmp_path / "scan.png").write_bytes(b"fake png")
        (tmp_path / "notes.txt").write_text("not supported")

        results = enumerate_documents(tmp_path)
        names = [p.name for p in results]
        assert "report.pdf" in names
        assert "scan.png" in names
        assert "notes.txt" not in names

    def test_empty_directory(self, tmp_path: Path) -> None:
        assert enumerate_documents(tmp_path) == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        assert enumerate_documents(tmp_path / "nope") == []

    def test_sorted_deterministically(self, tmp_path: Path) -> None:
        (tmp_path / "c.pdf").write_bytes(b"c")
        (tmp_path / "a.pdf").write_bytes(b"a")
        (tmp_path / "b.pdf").write_bytes(b"b")

        results = enumerate_documents(tmp_path)
        names = [p.name for p in results]
        assert names == ["a.pdf", "b.pdf", "c.pdf"]

    def test_ignores_directories(self, tmp_path: Path) -> None:
        (tmp_path / "subdir.pdf").mkdir()
        (tmp_path / "real.pdf").write_bytes(b"pdf")

        results = enumerate_documents(tmp_path)
        assert len(results) == 1
        assert results[0].name == "real.pdf"
