"""Native PDF text extraction -- supplement/fallback parser.

Uses pdfplumber for direct text extraction from PDFs with embedded text layers.
Faster than Docling but doesn't preserve table structure as well.
Used when Docling fails or as a supplementary text source.
"""

from pathlib import Path

from longview_health.core.errors import ParseError
from longview_health.domain.identifiers import content_hash
from longview_health.domain.models import ParsedDocument


def parse(file_path: Path) -> ParsedDocument:
    """Parse a PDF using native text extraction.

    Args:
        file_path: Path to a PDF file.

    Returns:
        ParsedDocument with extracted text blocks (no table structure).

    Raises:
        ParseError: If the file cannot be read or has no extractable text.
    """
    if not file_path.exists():
        raise ParseError(f"File not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix != ".pdf":
        raise ParseError(f"pdf_parser only handles PDFs, got: {suffix}")

    try:
        import pdfplumber
    except ImportError:
        raise ParseError("pdfplumber is not installed -- cannot use native PDF parser")

    text_blocks: list[str] = []
    page_count = 0
    warnings: list[str] = []

    try:
        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    text_blocks.append(text.strip())
    except Exception as e:
        raise ParseError(f"Failed to extract text from {file_path.name}: {e}")

    if not text_blocks:
        warnings.append("No extractable text found -- document may be image-only")

    doc_id = content_hash(file_path)

    # Combine text blocks into markdown (plain text, no table structure)
    markdown = "\n\n".join(text_blocks)

    return ParsedDocument(
        document_id=doc_id,
        markdown=markdown,
        text_blocks=text_blocks,
        tables=[],
        parser_used="pdfplumber",
        page_count=page_count,
        warnings=warnings,
    )
