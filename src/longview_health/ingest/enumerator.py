"""File enumeration -- discover supported documents in a vault's directory.

Walks the vault's documents directory, filters by supported file type,
and yields paths. Does not modify anything.
"""

from pathlib import Path

from longview_health.domain.enums import DocumentType

# Supported file extensions, mapped to document type
_SUPPORTED_EXTENSIONS: dict[str, DocumentType] = {
    ".pdf": DocumentType.PDF,
    ".png": DocumentType.PNG,
    ".jpg": DocumentType.JPG,
    ".jpeg": DocumentType.JPG,
    ".tiff": DocumentType.TIFF,
    ".tif": DocumentType.TIFF,
}


def suffix_to_document_type(suffix: str) -> DocumentType | None:
    """Map a file suffix to DocumentType, or None if unsupported."""
    return _SUPPORTED_EXTENSIONS.get(suffix.lower())


def enumerate_documents(directory: Path) -> list[Path]:
    """Walk a directory and return paths to all supported document files.

    Non-recursive by design -- vault documents sit in a flat directory.
    Returns sorted list for deterministic ordering.
    """
    if not directory.is_dir():
        return []

    results: list[Path] = []
    for entry in sorted(directory.iterdir()):
        if entry.is_file() and entry.suffix.lower() in _SUPPORTED_EXTENSIONS:
            results.append(entry)
    return results
