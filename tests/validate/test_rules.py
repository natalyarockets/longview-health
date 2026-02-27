"""Tests for validate/rules -- individual validation rules."""

from datetime import date

import pytest

from longview_health.domain.enums import Confidence, ResultCategory
from longview_health.domain.models import MedicalResult, ResultValue
from longview_health.validate.rules import (
    check_date_plausible,
    check_reference_range_consistent,
    check_required_fields,
    check_unit_recognized,
    check_value_plausible,
)


def _make_result(
    *,
    test_name: str = "HDL Cholesterol",
    value: str = "55",
    unit: str | None = "mg/dL",
    result_date: date = date(2024, 3, 15),
    reference_low: str | None = "40",
    reference_high: str | None = "60",
    is_abnormal: bool | None = False,
) -> MedicalResult:
    return MedicalResult(
        id="r001",
        document_id="doc001",
        test_name=test_name,
        result_value=ResultValue(
            value=value,
            unit=unit,
            reference_low=reference_low,
            reference_high=reference_high,
            is_abnormal=is_abnormal,
        ),
        result_date=result_date,
        category=ResultCategory.LAB,
        parser_used="docling",
        extractor_version="1.0.0",
        confidence=Confidence.HIGH,
    )


class TestCheckRequiredFields:
    def test_all_present(self) -> None:
        assert check_required_fields(_make_result()) == []

    def test_missing_test_name(self) -> None:
        issues = check_required_fields(_make_result(test_name=""))
        assert any("test name" in i.lower() for i in issues)

    def test_whitespace_test_name(self) -> None:
        issues = check_required_fields(_make_result(test_name="   "))
        assert any("test name" in i.lower() for i in issues)

    def test_missing_value(self) -> None:
        issues = check_required_fields(_make_result(value=""))
        assert any("value" in i.lower() for i in issues)


class TestCheckDatePlausible:
    def test_normal_date(self) -> None:
        assert check_date_plausible(_make_result()) == []

    def test_future_date(self) -> None:
        future = date(2099, 1, 1)
        issues = check_date_plausible(_make_result(result_date=future))
        assert any("future" in i.lower() for i in issues)

    def test_ancient_date(self) -> None:
        issues = check_date_plausible(_make_result(result_date=date(1800, 1, 1)))
        assert any("old" in i.lower() for i in issues)


class TestCheckUnitRecognized:
    def test_known_unit(self) -> None:
        assert check_unit_recognized(_make_result(unit="mg/dL")) == []

    def test_no_unit(self) -> None:
        assert check_unit_recognized(_make_result(unit=None)) == []

    def test_unknown_unit(self) -> None:
        issues = check_unit_recognized(_make_result(unit="zorbles"))
        assert any("unrecognized" in i.lower() for i in issues)

    def test_case_insensitive(self) -> None:
        assert check_unit_recognized(_make_result(unit="MG/DL")) == []


class TestCheckValuePlausible:
    def test_normal_value(self) -> None:
        assert check_value_plausible(_make_result(test_name="HDL", value="55")) == []

    def test_impossibly_high(self) -> None:
        issues = check_value_plausible(_make_result(test_name="HDL", value="9999"))
        assert any("plausible" in i.lower() for i in issues)

    def test_narrative_skipped(self) -> None:
        assert check_value_plausible(_make_result(value="No acute findings")) == []

    def test_unknown_test_skipped(self) -> None:
        assert check_value_plausible(_make_result(test_name="Obscure Test XYZ", value="99999")) == []


class TestCheckReferenceRange:
    def test_normal_range(self) -> None:
        assert check_reference_range_consistent(
            _make_result(reference_low="40", reference_high="60")
        ) == []

    def test_inverted_range(self) -> None:
        issues = check_reference_range_consistent(
            _make_result(reference_low="60", reference_high="40")
        )
        assert any("inverted" in i.lower() for i in issues)

    def test_no_range(self) -> None:
        assert check_reference_range_consistent(
            _make_result(reference_low=None, reference_high=None)
        ) == []

    def test_partial_range(self) -> None:
        assert check_reference_range_consistent(
            _make_result(reference_low="40", reference_high=None)
        ) == []
