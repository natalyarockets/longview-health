"""Validation engine -- run all rules against extracted results.

Every extraction must pass through this gate before entering trusted storage.
Results are either passed (stored), flagged (stored but marked for review),
or rejected (not stored, goes to review queue).

Rules that find issues:
- Required fields missing → REJECTED
- Future date → REJECTED
- Implausible value → FLAGGED
- Unrecognized unit → FLAGGED (not fatal, units list isn't exhaustive)
- Reference range inverted → FLAGGED
"""

from longview_health.domain.enums import Confidence, ValidationStatus
from longview_health.domain.models import MedicalResult, ValidationResult
from longview_health.validate.confidence import score_confidence
from longview_health.validate.rules import (
    ALL_RULES,
    check_date_plausible,
    check_required_fields,
)

# Rules whose issues cause rejection (not just flagging)
_REJECTION_RULES = {check_required_fields, check_date_plausible}


def validate_one(result: MedicalResult) -> tuple[MedicalResult, ValidationResult]:
    """Validate a single result. Returns (possibly-updated result, validation outcome)."""
    all_issues: list[str] = []
    has_rejection = False

    for rule in ALL_RULES:
        issues = rule(result)
        if issues:
            all_issues.extend(issues)
            if rule in _REJECTION_RULES:
                has_rejection = True

    if has_rejection:
        status = ValidationStatus.REJECTED
    elif all_issues:
        status = ValidationStatus.FLAGGED
    else:
        status = ValidationStatus.PASSED

    validation = ValidationResult(
        result_id=result.id,
        status=status,
        issues=all_issues,
    )

    # Adjust confidence based on validation outcome
    adjusted = score_confidence(result, validation)
    validation = ValidationResult(
        result_id=result.id,
        status=status,
        issues=all_issues,
        adjusted_confidence=adjusted if adjusted != result.confidence else None,
    )

    # Return updated result with validation status and adjusted confidence
    updated = MedicalResult(
        id=result.id,
        document_id=result.document_id,
        test_name=result.test_name,
        result_value=result.result_value,
        result_date=result.result_date,
        category=result.category,
        parser_used=result.parser_used,
        extractor_version=result.extractor_version,
        confidence=adjusted,
        validation_status=status,
        notes=result.notes,
    )

    return updated, validation


def validate_results(results: list[MedicalResult]) -> list[MedicalResult]:
    """Validate a batch of results. Returns only passed and flagged results.

    Rejected results are excluded from the return list (they should go
    to the review queue).
    """
    validated: list[MedicalResult] = []
    for result in results:
        updated, outcome = validate_one(result)
        if outcome.status != ValidationStatus.REJECTED:
            validated.append(updated)
    return validated
