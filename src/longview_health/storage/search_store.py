"""FTS5 search storage operations.

Manages the documents_fts virtual table for full-text search.
The FTS table was created in migration 1 with columns: document_id, content.
"""

from __future__ import annotations

from dataclasses import dataclass

from longview_health.core.config import AppConfig
from longview_health.storage.database import connect_vault


@dataclass(frozen=True)
class SearchHit:
    """A single search result with document ID and highlighted snippet."""

    document_id: str
    snippet: str
    rank: float


def index_document(
    config: AppConfig, vault_name: str, document_id: str, content: str
) -> None:
    """Index (or re-index) a document's text content for FTS search.

    Replaces any existing entry for this document_id.
    """
    conn = connect_vault(config, vault_name)
    try:
        # Remove old entry if exists
        conn.execute(
            "DELETE FROM documents_fts WHERE document_id = ?", (document_id,)
        )
        conn.execute(
            "INSERT INTO documents_fts (document_id, content) VALUES (?, ?)",
            (document_id, content),
        )
        conn.commit()
    finally:
        conn.close()


def search(
    config: AppConfig,
    vault_name: str,
    query: str,
    *,
    limit: int = 20,
) -> list[SearchHit]:
    """Search documents using FTS5. Returns ranked results with snippets.

    The query supports FTS5 syntax: AND, OR, NOT, "phrase", prefix*.
    """
    conn = connect_vault(config, vault_name)
    try:
        rows = conn.execute(
            """SELECT document_id,
                      snippet(documents_fts, 1, '>>>', '<<<', '...', 64) as snippet,
                      rank
               FROM documents_fts
               WHERE documents_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, limit),
        ).fetchall()
        return [
            SearchHit(
                document_id=row["document_id"],
                snippet=row["snippet"],
                rank=row["rank"],
            )
            for row in rows
        ]
    finally:
        conn.close()


def rebuild_index(config: AppConfig, vault_name: str) -> None:
    """Rebuild the FTS index (useful after bulk operations)."""
    conn = connect_vault(config, vault_name)
    try:
        conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
        conn.commit()
    finally:
        conn.close()


def document_indexed(
    config: AppConfig, vault_name: str, document_id: str
) -> bool:
    """Check if a document is already indexed."""
    conn = connect_vault(config, vault_name)
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM documents_fts WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        return row["cnt"] > 0
    finally:
        conn.close()
