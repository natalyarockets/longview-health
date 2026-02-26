"""Docling-based document parser -- primary parser.

Uses Docling's DocumentConverter to extract text and table structure
from PDFs and images. This is the accuracy-first parser that preserves
layout, table geometry, and header relationships.
"""

from pathlib import Path

from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.document import ConversionResult
from docling.document_converter import DocumentConverter, FormatOption, PdfFormatOption

from longview_health.core.errors import ParseError
from longview_health.domain.models import ParsedDocument, ParsedTable


def _build_converter() -> DocumentConverter:
    """Create a configured Docling DocumentConverter."""
    return DocumentConverter(
        allowed_formats=[
            InputFormat.PDF,
            InputFormat.IMAGE,
        ],
        format_options={
            InputFormat.PDF: PdfFormatOption(),
        },
    )


# Module-level converter -- reused across calls to avoid re-initialization cost.
_converter: DocumentConverter | None = None


def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        _converter = _build_converter()
    return _converter


def _extract_tables(result: ConversionResult) -> list[ParsedTable]:
    """Extract structured tables from a Docling ConversionResult."""
    tables: list[ParsedTable] = []

    for table_item in result.document.tables:
        data = table_item.data
        if data is None:
            continue

        # Build a 2D grid from table cells
        grid: list[list[str]] = [
            [""] * data.num_cols for _ in range(data.num_rows)
        ]
        header_rows: set[int] = set()

        for cell in data.table_cells:
            row = cell.start_row_offset_idx
            col = cell.start_col_offset_idx
            if 0 <= row < data.num_rows and 0 <= col < data.num_cols:
                grid[row][col] = cell.text.strip()
                if cell.column_header:
                    header_rows.add(row)

        # Separate headers from data rows
        if header_rows:
            max_header_row = max(header_rows)
            # Combine all header rows into a single header list
            # (use the last header row as the canonical headers)
            headers = grid[max_header_row]
            rows = grid[max_header_row + 1:]
        elif grid:
            # No explicit headers -- treat first row as headers
            headers = grid[0]
            rows = grid[1:]
        else:
            continue

        # Determine page from provenance if available
        page = None
        if table_item.prov:
            page = table_item.prov[0].page_no

        tables.append(ParsedTable(headers=headers, rows=rows, page=page))

    return tables


def _extract_text_blocks(result: ConversionResult) -> list[str]:
    """Extract text blocks from a Docling ConversionResult."""
    blocks: list[str] = []
    for text_item in result.document.texts:
        text = text_item.text.strip()
        if text:
            blocks.append(text)
    return blocks


def parse(file_path: Path) -> ParsedDocument:
    """Parse a document using Docling.

    Args:
        file_path: Path to a PDF or image file.

    Returns:
        ParsedDocument with extracted text blocks and tables.

    Raises:
        ParseError: If Docling fails to convert the document.
    """
    if not file_path.exists():
        raise ParseError(f"File not found: {file_path}")

    converter = _get_converter()
    result = converter.convert(file_path, raises_on_error=False)

    warnings: list[str] = []

    if result.status == ConversionStatus.FAILURE:
        error_msgs = [e.error_message for e in result.errors if e.error_message]
        raise ParseError(
            f"Docling failed to parse {file_path.name}: {'; '.join(error_msgs) or 'unknown error'}"
        )

    if result.status == ConversionStatus.PARTIAL_SUCCESS:
        warnings.append("Docling partial success -- some content may be missing")
        for e in result.errors:
            if e.error_message:
                warnings.append(f"Docling warning: {e.error_message}")

    text_blocks = _extract_text_blocks(result)
    tables = _extract_tables(result)
    page_count = result.document.num_pages()

    # Markdown export -- the primary representation for LLM extraction
    markdown = result.document.export_to_markdown()

    # Content hash of the source file serves as the document ID
    from longview_health.domain.identifiers import content_hash

    doc_id = content_hash(file_path)

    return ParsedDocument(
        document_id=doc_id,
        markdown=markdown,
        text_blocks=text_blocks,
        tables=tables,
        parser_used="docling",
        page_count=page_count,
        warnings=warnings,
    )
