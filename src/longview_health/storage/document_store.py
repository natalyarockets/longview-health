"""Document storage operations.

Insert, query, and check documents in a vault's SQLite database.
Follows the vault_store.py pattern: module-level functions, explicit config.
"""

from datetime import datetime, timezone

from longview_health.core.config import AppConfig
from longview_health.domain.enums import DocumentType
from longview_health.domain.models import Document
from longview_health.storage.database import connect_vault


def _row_to_document(row: dict) -> Document:
    """Convert a SQLite row to a Document."""
    return Document(
        id=row["id"],
        vault_name=row["vault_name"],
        filename=row["filename"],
        file_path=row["file_path"],
        document_type=DocumentType(row["document_type"]),
        content_hash=row["content_hash"],
        ingested_at=datetime.fromisoformat(row["ingested_at"]),
        page_count=row["page_count"],
    )


def insert_document(config: AppConfig, vault_name: str, doc: Document) -> None:
    """Insert or replace a document row."""
    conn = connect_vault(config, vault_name)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO documents
               (id, vault_name, filename, file_path, document_type,
                content_hash, ingested_at, page_count)
               VALUES (:id, :vault_name, :filename, :file_path, :document_type,
                       :content_hash, :ingested_at, :page_count)""",
            {
                "id": doc.id,
                "vault_name": doc.vault_name,
                "filename": doc.filename,
                "file_path": doc.file_path,
                "document_type": doc.document_type.value,
                "content_hash": doc.content_hash,
                "ingested_at": doc.ingested_at.isoformat(),
                "page_count": doc.page_count,
            },
        )
        conn.commit()
    finally:
        conn.close()


def get_document_by_hash(
    config: AppConfig, vault_name: str, content_hash: str
) -> Document | None:
    """Look up a document by its content hash. Returns None if not found."""
    conn = connect_vault(config, vault_name)
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return _row_to_document(dict(row)) if row else None
    finally:
        conn.close()


def get_document(
    config: AppConfig, vault_name: str, document_id: str
) -> Document | None:
    """Look up a document by ID."""
    conn = connect_vault(config, vault_name)
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        return _row_to_document(dict(row)) if row else None
    finally:
        conn.close()


def list_documents(config: AppConfig, vault_name: str) -> list[Document]:
    """List all documents in a vault, sorted by filename."""
    conn = connect_vault(config, vault_name)
    try:
        rows = conn.execute(
            "SELECT * FROM documents ORDER BY filename"
        ).fetchall()
        return [_row_to_document(dict(row)) for row in rows]
    finally:
        conn.close()


def delete_document(config: AppConfig, vault_name: str, document_id: str) -> None:
    """Delete a document and all its associated results, review items, and FTS entries."""
    conn = connect_vault(config, vault_name)
    try:
        conn.execute("DELETE FROM review_queue WHERE document_id = ?", (document_id,))
        conn.execute("DELETE FROM medical_results WHERE document_id = ?", (document_id,))
        conn.execute("DELETE FROM documents_fts WHERE document_id = ?", (document_id,))
        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        conn.commit()
    finally:
        conn.close()


def document_count(config: AppConfig, vault_name: str) -> int:
    """Return the number of documents in a vault."""
    conn = connect_vault(config, vault_name)
    try:
        row = conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()
        return row["cnt"]
    finally:
        conn.close()
