"""Review queue storage operations.

Manages the review_queue table for flagged/rejected extractions that
need manual review.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from longview_health.core.config import AppConfig
from longview_health.domain.enums import ValidationStatus
from longview_health.domain.models import ValidationResult
from longview_health.storage.database import connect_vault


@dataclass(frozen=True)
class ReviewRow:
    """A row from the review queue table."""

    id: str
    result_id: str
    document_id: str
    test_name: str
    reason: str
    created_at: str
    resolved: bool
    resolved_at: str | None


def _row_to_review(row: dict) -> ReviewRow:
    return ReviewRow(
        id=row["id"],
        result_id=row["result_id"],
        document_id=row["document_id"],
        test_name=row["test_name"],
        reason=row["reason"],
        created_at=row["created_at"],
        resolved=bool(row["resolved"]),
        resolved_at=row["resolved_at"],
    )


def add_to_review(
    config: AppConfig,
    vault_name: str,
    *,
    result_id: str,
    document_id: str,
    test_name: str,
    reason: str,
) -> None:
    """Add an item to the review queue."""
    import hashlib

    review_id = hashlib.sha256(
        f"{result_id}:{reason}".encode()
    ).hexdigest()[:16]

    conn = connect_vault(config, vault_name)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO review_queue
               (id, result_id, document_id, test_name, reason, created_at, resolved)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (
                review_id,
                result_id,
                document_id,
                test_name,
                reason,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_pending(config: AppConfig, vault_name: str) -> list[ReviewRow]:
    """List unresolved review items, ordered by creation date."""
    conn = connect_vault(config, vault_name)
    try:
        rows = conn.execute(
            "SELECT * FROM review_queue WHERE resolved = 0 ORDER BY created_at"
        ).fetchall()
        return [_row_to_review(dict(row)) for row in rows]
    finally:
        conn.close()


def list_all(config: AppConfig, vault_name: str) -> list[ReviewRow]:
    """List all review items."""
    conn = connect_vault(config, vault_name)
    try:
        rows = conn.execute(
            "SELECT * FROM review_queue ORDER BY created_at"
        ).fetchall()
        return [_row_to_review(dict(row)) for row in rows]
    finally:
        conn.close()


def resolve_item(
    config: AppConfig, vault_name: str, review_id: str
) -> bool:
    """Mark a review item as resolved. Returns True if the item existed."""
    conn = connect_vault(config, vault_name)
    try:
        cursor = conn.execute(
            """UPDATE review_queue
               SET resolved = 1, resolved_at = ?
               WHERE id = ? AND resolved = 0""",
            (datetime.now(timezone.utc).isoformat(), review_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def pending_count(config: AppConfig, vault_name: str) -> int:
    """Return the number of unresolved review items."""
    conn = connect_vault(config, vault_name)
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM review_queue WHERE resolved = 0"
        ).fetchone()
        return row["cnt"]
    finally:
        conn.close()
