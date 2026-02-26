"""Deterministic identifier generation.

Content hashes for documents, composite keys for results.
"""

import hashlib
from datetime import date
from pathlib import Path


def content_hash(file_path: Path) -> str:
    """SHA-256 hash of file contents. Used for deduplication."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def result_key(
    document_id: str,
    test_name: str,
    result_date: date,
) -> str:
    """Composite key for a medical result.

    Deterministic: same document + test + date always produces the same key.
    """
    raw = f"{document_id}:{test_name}:{result_date.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
