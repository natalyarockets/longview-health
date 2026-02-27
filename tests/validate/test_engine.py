"""Tests for validate/engine -- validation pipeline."""

from datetime import date

from longview_health.domain.enums import (
    Confidence,
    ResultCategory,
    ValidationStatus,
)
from longview_health.domain.models import MedicalResult, ResultValue
from longview_health.validate.engine import validate_one, validate_results


def _make_result(
    *,
    test_name: str = "HDL Cholesterol",
    value: str = "55",
    unit: str | None = "mg/dL",
    result_date: date = date(2024, 3, 15),
    confidence: Confidence = Confidence.HIGH,
) -> MedicalResult:
    return MedicalResult(
        id="r001",
        document_id="doc001",
        test_name=test_name,
        result_value=ResultValue(value=value, unit=unit),
        result_date=result_date,
        category=ResultCategory.LAB,
        parser_used="docling",
        extractor_version="1.0.0",
        confidence=confidence,
    )


class TestValidateOne:
    def test_valid_result_passes(self) -> None:
        updated, outcome = validate_one(_make_result())
        assert outcome.status == ValidationStatus.PASSED
        assert updated.validation_status == ValidationStatus.PASSED

    def test_missing_test_name_rejected(self) -> None:
        updated, outcome = validate_one(_make_result(test_name=""))
        assert outcome.status == ValidationStatus.REJECTED

    def test_future_date_rejected(self) -> None:
        updated, outcome = validate_one(_make_result(result_date=date(2099, 1, 1)))
        assert outcome.status == ValidationStatus.REJECTED

    def test_unknown_unit_flagged(self) -> None:
        updated, outcome = validate_one(_make_result(unit="zorbles"))
        assert outcome.status == ValidationStatus.FLAGGED
        assert updated.validation_status == ValidationStatus.FLAGGED

    def test_flagged_downgrades_confidence(self) -> None:
        updated, outcome = validate_one(
            _make_result(unit="zorbles", confidence=Confidence.HIGH)
        )
        assert updated.confidence == Confidence.MEDIUM

    def test_manual_confidence_preserved(self) -> None:
        r = MedicalResult(
            id="r001",
            document_id="doc001",
            test_name="HDL",
            result_value=ResultValue(value="55", unit="zorbles"),
            result_date=date(2024, 3, 15),
            category=ResultCategory.LAB,
            parser_used="docling",
            extractor_version="1.0.0",
            confidence=Confidence.MANUAL,
        )
        updated, _ = validate_one(r)
        assert updated.confidence == Confidence.MANUAL


class TestValidateResults:
    def test_filters_rejected(self) -> None:
        good = _make_result()
        bad = _make_result(test_name="")
        results = validate_results([good, bad])
        assert len(results) == 1
        assert results[0].test_name == "HDL Cholesterol"

    def test_keeps_flagged(self) -> None:
        flagged = _make_result(unit="zorbles")
        results = validate_results([flagged])
        assert len(results) == 1
        assert results[0].validation_status == ValidationStatus.FLAGGED

    def test_empty_input(self) -> None:
        assert validate_results([]) == []
