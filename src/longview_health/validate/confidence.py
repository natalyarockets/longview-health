"""Confidence scoring for validated results.

Adjusts the extraction-assigned confidence based on validation outcome
and extraction method characteristics.
"""

from longview_health.domain.enums import Confidence, ValidationStatus
from longview_health.domain.models import MedicalResult, ValidationResult


def score_confidence(
    result: MedicalResult, validation: ValidationResult
) -> Confidence:
    """Determine final confidence based on extraction method + validation.

    - MANUAL confidence is never downgraded (user verified).
    - Rejected results keep whatever confidence they had (they won't be stored).
    - Flagged results are downgraded one level.
    - Passed results keep or upgrade their confidence.
    """
    if result.confidence == Confidence.MANUAL:
        return Confidence.MANUAL

    if validation.status == ValidationStatus.REJECTED:
        return result.confidence

    if validation.status == ValidationStatus.FLAGGED:
        # Downgrade one level
        if result.confidence == Confidence.HIGH:
            return Confidence.MEDIUM
        return Confidence.LOW

    # Passed validation -- deterministic extractors get HIGH
    if "table" in result.extractor_version:
        return Confidence.HIGH

    return result.confidence
