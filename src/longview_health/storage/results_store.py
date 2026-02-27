"""Medical results storage operations.

Insert, query, and aggregate extracted MedicalResult rows in a vault's
SQLite database. Follows the vault_store.py pattern: module-level functions,
explicit config, connect_vault(), try/finally.
"""

from datetime import date

from longview_health.core.config import AppConfig
from longview_health.domain.enums import (
    Confidence,
    ResultCategory,
    ValidationStatus,
)
from longview_health.domain.models import Document, MedicalResult, ResultValue
from longview_health.storage.database import connect_vault


def _row_to_result(row: dict) -> MedicalResult:
    """Re-nest flat SQLite columns into a MedicalResult."""
    return MedicalResult(
        id=row["id"],
        document_id=row["document_id"],
        test_name=row["test_name"],
        result_value=ResultValue(
            value=row["value"],
            unit=row["unit"],
            reference_low=row["reference_low"],
            reference_high=row["reference_high"],
            is_abnormal=bool(row["is_abnormal"]) if row["is_abnormal"] is not None else None,
        ),
        result_date=date.fromisoformat(row["result_date"]),
        category=ResultCategory(row["category"]),
        parser_used=row["parser_used"],
        extractor_version=row["extractor_version"],
        confidence=Confidence(row["confidence"]),
        validation_status=ValidationStatus(row["validation_status"]),
        notes=row["notes"],
    )


def _result_to_params(result: MedicalResult) -> dict:
    """Flatten a MedicalResult for INSERT."""
    return {
        "id": result.id,
        "document_id": result.document_id,
        "test_name": result.test_name,
        "value": result.result_value.value,
        "unit": result.result_value.unit,
        "reference_low": result.result_value.reference_low,
        "reference_high": result.result_value.reference_high,
        "is_abnormal": (
            int(result.result_value.is_abnormal)
            if result.result_value.is_abnormal is not None
            else None
        ),
        "result_date": result.result_date.isoformat(),
        "category": result.category.value,
        "parser_used": result.parser_used,
        "extractor_version": result.extractor_version,
        "confidence": result.confidence.value,
        "validation_status": result.validation_status.value,
        "notes": result.notes,
    }


def insert_document(config: AppConfig, vault_name: str, doc: Document) -> None:
    """Insert a Document row (needed as FK target for medical_results)."""
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


def insert_results(
    config: AppConfig, vault_name: str, results: list[MedicalResult]
) -> int:
    """INSERT OR REPLACE results in a single transaction. Returns count inserted."""
    if not results:
        return 0
    conn = connect_vault(config, vault_name)
    try:
        for r in results:
            conn.execute(
                """INSERT OR REPLACE INTO medical_results
                   (id, document_id, test_name, value, unit,
                    reference_low, reference_high, is_abnormal,
                    result_date, category, parser_used,
                    extractor_version, confidence, validation_status, notes)
                   VALUES (:id, :document_id, :test_name, :value, :unit,
                           :reference_low, :reference_high, :is_abnormal,
                           :result_date, :category, :parser_used,
                           :extractor_version, :confidence, :validation_status, :notes)""",
                _result_to_params(r),
            )
        conn.commit()
        return len(results)
    finally:
        conn.close()


def query_results(
    config: AppConfig,
    vault_name: str,
    *,
    test_name: str | None = None,
    category: ResultCategory | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[MedicalResult]:
    """Query results with optional filters. Returns list sorted by result_date."""
    clauses: list[str] = []
    params: dict = {}

    if test_name is not None:
        clauses.append("test_name = :test_name")
        params["test_name"] = test_name
    if category is not None:
        clauses.append("category = :category")
        params["category"] = category.value
    if date_from is not None:
        clauses.append("result_date >= :date_from")
        params["date_from"] = date_from.isoformat()
    if date_to is not None:
        clauses.append("result_date <= :date_to")
        params["date_to"] = date_to.isoformat()

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM medical_results{where} ORDER BY result_date, test_name"

    conn = connect_vault(config, vault_name)
    try:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_result(dict(row)) for row in rows]
    finally:
        conn.close()


def get_distinct_tests(
    config: AppConfig,
    vault_name: str,
    *,
    category: ResultCategory | None = None,
) -> list[str]:
    """Return distinct test names, optionally filtered by category."""
    params: dict = {}
    where = ""
    if category is not None:
        where = " WHERE category = :category"
        params["category"] = category.value

    sql = f"SELECT DISTINCT test_name FROM medical_results{where} ORDER BY test_name"

    conn = connect_vault(config, vault_name)
    try:
        rows = conn.execute(sql, params).fetchall()
        return [row["test_name"] for row in rows]
    finally:
        conn.close()


def get_result_counts_by_category(
    config: AppConfig, vault_name: str
) -> dict[ResultCategory, int]:
    """Return count of results per category."""
    conn = connect_vault(config, vault_name)
    try:
        rows = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM medical_results GROUP BY category"
        ).fetchall()
        return {ResultCategory(row["category"]): row["cnt"] for row in rows}
    finally:
        conn.close()


def get_document_names(
    config: AppConfig, vault_name: str, document_ids: list[str]
) -> dict[str, str]:
    """Map document IDs to filenames."""
    if not document_ids:
        return {}
    conn = connect_vault(config, vault_name)
    try:
        placeholders = ",".join("?" for _ in document_ids)
        rows = conn.execute(
            f"SELECT id, filename FROM documents WHERE id IN ({placeholders})",
            document_ids,
        ).fetchall()
        return {row["id"]: row["filename"] for row in rows}
    finally:
        conn.close()
