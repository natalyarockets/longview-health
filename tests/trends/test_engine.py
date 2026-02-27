"""Tests for trends/engine -- pure trend computation logic."""

from datetime import date

import pytest

from longview_health.domain.enums import (
    Confidence,
    ResultCategory,
    ValidationStatus,
)
from longview_health.domain.models import MedicalResult, ResultValue
from longview_health.trends.engine import (
    _try_parse_numeric,
    build_trend_report,
    build_trend_series,
)


def _make_result(
    *,
    test_name: str = "HDL Cholesterol",
    value: str = "55",
    unit: str | None = "mg/dL",
    result_date: date = date(2024, 3, 15),
    category: ResultCategory = ResultCategory.LAB,
    is_abnormal: bool | None = False,
    document_id: str = "doc001",
) -> MedicalResult:
    return MedicalResult(
        id=f"{test_name}-{result_date}",
        document_id=document_id,
        test_name=test_name,
        result_value=ResultValue(
            value=value,
            unit=unit,
            is_abnormal=is_abnormal,
        ),
        result_date=result_date,
        category=category,
        parser_used="docling",
        extractor_version="1.0.0",
        confidence=Confidence.HIGH,
    )


class TestTryParseNumeric:
    def test_integer(self) -> None:
        assert _try_parse_numeric("145") == 145.0

    def test_float(self) -> None:
        assert _try_parse_numeric("3.5") == 3.5

    def test_less_than(self) -> None:
        assert _try_parse_numeric("<0.01") == 0.01

    def test_greater_than(self) -> None:
        assert _try_parse_numeric(">200") == 200.0

    def test_less_equal(self) -> None:
        assert _try_parse_numeric("<=5.0") == 5.0

    def test_whitespace(self) -> None:
        assert _try_parse_numeric("  42  ") == 42.0

    def test_narrative_returns_none(self) -> None:
        assert _try_parse_numeric("No acute findings") is None

    def test_empty_returns_none(self) -> None:
        assert _try_parse_numeric("") is None


class TestBuildTrendSeries:
    def test_chronological_sorting(self) -> None:
        results = [
            _make_result(value="60", result_date=date(2024, 6, 1)),
            _make_result(value="50", result_date=date(2024, 1, 1)),
            _make_result(value="55", result_date=date(2024, 3, 1)),
        ]
        series = build_trend_series("HDL Cholesterol", results)
        dates = [p.result.result_date for p in series.points]
        assert dates == [date(2024, 1, 1), date(2024, 3, 1), date(2024, 6, 1)]

    def test_numeric_deltas(self) -> None:
        results = [
            _make_result(value="50", result_date=date(2024, 1, 1)),
            _make_result(value="55", result_date=date(2024, 3, 1)),
            _make_result(value="60", result_date=date(2024, 6, 1)),
        ]
        series = build_trend_series("HDL Cholesterol", results)
        assert series.points[0].delta is None  # first point, no previous
        assert series.points[1].delta == 5.0
        assert series.points[2].delta == 5.0

    def test_delta_percent(self) -> None:
        results = [
            _make_result(value="100", result_date=date(2024, 1, 1)),
            _make_result(value="110", result_date=date(2024, 3, 1)),
        ]
        series = build_trend_series("HDL Cholesterol", results)
        assert series.points[1].delta == 10.0
        assert series.points[1].delta_percent == 10.0

    def test_non_numeric_no_deltas(self) -> None:
        results = [
            _make_result(value="No acute findings", result_date=date(2024, 1, 1)),
            _make_result(value="Stable", result_date=date(2024, 6, 1)),
        ]
        series = build_trend_series("MRI Brain", results)
        assert all(p.delta is None for p in series.points)
        assert series.is_numeric is False

    def test_is_numeric_flag(self) -> None:
        results = [
            _make_result(value="55", result_date=date(2024, 1, 1)),
            _make_result(value="60", result_date=date(2024, 3, 1)),
        ]
        series = build_trend_series("HDL", results)
        assert series.is_numeric is True

    def test_latest_value(self) -> None:
        results = [
            _make_result(value="50", result_date=date(2024, 1, 1)),
            _make_result(value="65", result_date=date(2024, 6, 1)),
        ]
        series = build_trend_series("HDL", results)
        assert series.latest_value == "65"

    def test_unit_from_latest(self) -> None:
        results = [
            _make_result(value="50", unit="mg/dL", result_date=date(2024, 1, 1)),
            _make_result(value="55", unit="mg/dL", result_date=date(2024, 3, 1)),
        ]
        series = build_trend_series("HDL", results)
        assert series.unit == "mg/dL"

    def test_mixed_numeric_narrative(self) -> None:
        """Narrative value in the middle doesn't break delta chain."""
        results = [
            _make_result(value="50", result_date=date(2024, 1, 1)),
            _make_result(value="see note", result_date=date(2024, 3, 1)),
            _make_result(value="55", result_date=date(2024, 6, 1)),
        ]
        series = build_trend_series("HDL", results)
        # Delta from 50 to 55 (skips the narrative)
        assert series.points[2].delta == 5.0


class TestBuildTrendReport:
    def test_groups_by_category(self) -> None:
        results = [
            _make_result(test_name="HDL", category=ResultCategory.LAB),
            _make_result(test_name="MRI Brain", value="Normal", category=ResultCategory.IMAGING),
        ]
        report = build_trend_report("alice", results)
        assert ResultCategory.LAB in report.categories
        assert ResultCategory.IMAGING in report.categories
        assert len(report.categories[ResultCategory.LAB]) == 1
        assert len(report.categories[ResultCategory.IMAGING]) == 1

    def test_summary_stats(self) -> None:
        results = [
            _make_result(test_name="HDL", result_date=date(2024, 1, 1)),
            _make_result(test_name="HDL", result_date=date(2024, 6, 1), value="60"),
            _make_result(test_name="LDL", result_date=date(2024, 1, 1), value="120"),
        ]
        report = build_trend_report("alice", results)
        assert report.vault_name == "alice"
        assert report.total_results == 3
        assert report.total_tests == 2
        assert report.date_range_start == date(2024, 1, 1)
        assert report.date_range_end == date(2024, 6, 1)

    def test_empty_results(self) -> None:
        report = build_trend_report("alice", [])
        assert report.total_results == 0
        assert report.total_tests == 0
        assert report.date_range_start is None
        assert report.date_range_end is None
        assert report.categories == {}
