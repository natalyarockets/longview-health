"""Parser orchestration -- try parsers in priority order.

Priority:
1. Docling (primary -- best layout/table extraction)
2. Native PDF text (fallback for when Docling fails)

Each parser produces a ParsedDocument. The chain returns the first
successful result and records which parser was used.
"""

from pathlib import Path

from longview_health.core.errors import ParseError
from longview_health.domain.models import DoclingConversion, ParsedDocument
from longview_health.extract import docling_parser, pdf_parser


def _is_pdf(file_path: Path) -> bool:
    return file_path.suffix.lower() == ".pdf"


def _is_image(file_path: Path) -> bool:
    return file_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tiff", ".tif"}


def _parse_quality_ok(result: ParsedDocument) -> bool:
    """Check if a parse result has enough content to be useful."""
    has_text = any(len(block) > 10 for block in result.text_blocks)
    has_tables = len(result.tables) > 0
    return has_text or has_tables


def parse(file_path: Path) -> ParsedDocument:
    """Parse a document using the best available parser.

    Tries Docling first, falls back to native PDF extraction.

    Args:
        file_path: Path to a PDF or image file.

    Returns:
        ParsedDocument from the first parser that produces good output.

    Raises:
        ParseError: If no parser can handle the document.
    """
    if not file_path.exists():
        raise ParseError(f"File not found: {file_path}")

    if not (_is_pdf(file_path) or _is_image(file_path)):
        raise ParseError(
            f"Unsupported file type: {file_path.suffix}. "
            f"Supported: .pdf, .png, .jpg, .jpeg, .tiff, .tif"
        )

    errors: list[str] = []

    # 1. Try Docling (primary)
    try:
        result = docling_parser.parse(file_path)
        if _parse_quality_ok(result):
            return result
        errors.append(f"Docling produced low-quality output for {file_path.name}")
    except ParseError as e:
        errors.append(f"Docling: {e}")
    except Exception as e:
        errors.append(f"Docling unexpected error: {e}")

    # 2. Try native PDF parser (fallback, PDFs only)
    if _is_pdf(file_path):
        try:
            result = pdf_parser.parse(file_path)
            if _parse_quality_ok(result):
                return result
            errors.append(f"pdfplumber produced low-quality output for {file_path.name}")
        except ParseError as e:
            errors.append(f"pdfplumber: {e}")
        except Exception as e:
            errors.append(f"pdfplumber unexpected error: {e}")

    raise ParseError(
        f"All parsers failed for {file_path.name}:\n" +
        "\n".join(f"  - {e}" for e in errors)
    )


def parse_rich(file_path: Path) -> DoclingConversion:
    """Parse a document, preserving the raw Docling element tree when available.

    Tries Docling first (returns full DoclingConversion with element tree).
    Falls back to pdfplumber (wraps in DoclingConversion with docling_document=None).

    Args:
        file_path: Path to a PDF or image file.

    Returns:
        DoclingConversion with ParsedDocument and optional DoclingDocument.

    Raises:
        ParseError: If no parser can handle the document.
    """
    if not file_path.exists():
        raise ParseError(f"File not found: {file_path}")

    if not (_is_pdf(file_path) or _is_image(file_path)):
        raise ParseError(
            f"Unsupported file type: {file_path.suffix}. "
            f"Supported: .pdf, .png, .jpg, .jpeg, .tiff, .tif"
        )

    errors: list[str] = []

    # 1. Try Docling (primary -- returns rich conversion with element tree)
    try:
        conversion = docling_parser.parse_rich(file_path)
        if _parse_quality_ok(conversion.parsed):
            return conversion
        errors.append(f"Docling produced low-quality output for {file_path.name}")
    except ParseError as e:
        errors.append(f"Docling: {e}")
    except Exception as e:
        errors.append(f"Docling unexpected error: {e}")

    # 2. Try native PDF parser (fallback, PDFs only -- no element tree)
    if _is_pdf(file_path):
        try:
            result = pdf_parser.parse(file_path)
            if _parse_quality_ok(result):
                return DoclingConversion(parsed=result, docling_document=None)
            errors.append(f"pdfplumber produced low-quality output for {file_path.name}")
        except ParseError as e:
            errors.append(f"pdfplumber: {e}")
        except Exception as e:
            errors.append(f"pdfplumber unexpected error: {e}")

    raise ParseError(
        f"All parsers failed for {file_path.name}:\n" +
        "\n".join(f"  - {e}" for e in errors)
    )
