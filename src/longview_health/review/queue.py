"""Review queue logic -- surface flagged extractions for correction.

Provides functions to list, accept, reject, and edit review items.
The CLI layer calls these functions for the interactive review flow.
"""

from __future__ import annotations

from longview_health.core.config import AppConfig
from longview_health.domain.enums import Confidence, ValidationStatus
from longview_health.domain.models import MedicalResult, ResultValue
from longview_health.storage import results_store, review_store
from longview_health.storage.review_store import ReviewRow


def get_pending_items(
    config: AppConfig, vault_name: str
) -> list[ReviewRow]:
    """Get all pending review items."""
    return review_store.list_pending(config, vault_name)


def accept_item(config: AppConfig, vault_name: str, review_id: str) -> bool:
    """Accept a flagged result as-is. Marks the review item resolved."""
    return review_store.resolve_item(config, vault_name, review_id)


def reject_item(
    config: AppConfig, vault_name: str, review_id: str, result_id: str
) -> bool:
    """Reject a result -- remove it from results and resolve the review item."""
    # Delete the result from medical_results
    conn = results_store.connect_vault(config, vault_name)
    try:
        conn.execute("DELETE FROM medical_results WHERE id = ?", (result_id,))
        conn.commit()
    finally:
        conn.close()
    return review_store.resolve_item(config, vault_name, review_id)


def edit_result(
    config: AppConfig,
    vault_name: str,
    review_id: str,
    result_id: str,
    *,
    value: str | None = None,
    unit: str | None = None,
    test_name: str | None = None,
) -> bool:
    """Edit a result's value/unit/test_name and mark as manually verified.

    Returns True if the edit was applied successfully.
    """
    # Fetch current result
    rows = results_store.query_results(config, vault_name)
    current = None
    for r in rows:
        if r.id == result_id:
            current = r
            break

    if current is None:
        return False

    # Build updated result
    updated = MedicalResult(
        id=current.id,
        document_id=current.document_id,
        test_name=test_name if test_name is not None else current.test_name,
        result_value=ResultValue(
            value=value if value is not None else current.result_value.value,
            unit=unit if unit is not None else current.result_value.unit,
            reference_low=current.result_value.reference_low,
            reference_high=current.result_value.reference_high,
            is_abnormal=current.result_value.is_abnormal,
        ),
        result_date=current.result_date,
        category=current.category,
        parser_used=current.parser_used,
        extractor_version=current.extractor_version,
        confidence=Confidence.MANUAL,
        validation_status=ValidationStatus.PASSED,
        notes=current.notes,
    )

    results_store.insert_results(config, vault_name, [updated])
    review_store.resolve_item(config, vault_name, review_id)
    return True
