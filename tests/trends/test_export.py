"""Tests for trends/export -- PDF generation."""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from longview_health.domain.enums import (
    Confidence,
    ResultCategory,
)
from longview_health.domain.models import (
    MedicalResult,
    ResultValue,
    TrendPoint,
    TrendReport,
    TrendSeries,
)
from longview_health.trends.export import export_pdf


def _make_result(
    *,
    test_name: str = "HDL Cholesterol",
    value: str = "55",
    unit: str | None = "mg/dL",
    result_date: date = date(2024, 3, 15),
    category: ResultCategory = ResultCategory.LAB,
    is_abnormal: bool | None = False,
) -> MedicalResult:
    return MedicalResult(
        id=f"{test_name}-{result_date}",
        document_id="doc001",
        test_name=test_name,
        result_value=ResultValue(
            value=value,
            unit=unit,
            reference_low="40",
            reference_high="60",
            is_abnormal=is_abnormal,
        ),
        result_date=result_date,
        category=category,
        parser_used="docling",
        extractor_version="1.0.0",
        confidence=Confidence.HIGH,
    )


def _make_series(
    test_name: str = "HDL Cholesterol",
    results: list[MedicalResult] | None = None,
) -> TrendSeries:
    if results is None:
        results = [_make_result()]
    points = [TrendPoint(result=r) for r in results]
    return TrendSeries(
        test_name=test_name,
        category=results[0].category,
        unit=results[0].result_value.unit,
        points=points,
        latest_value=results[-1].result_value.value,
        is_numeric=True,
    )


def _make_report(
    series_list: list[TrendSeries] | None = None,
) -> TrendReport:
    if series_list is None:
        series_list = [_make_series()]
    categories: dict[ResultCategory, list[TrendSeries]] = {}
    total_results = 0
    for s in series_list:
        categories.setdefault(s.category, []).append(s)
        total_results += len(s.points)
    return TrendReport(
        vault_name="alice",
        generated_at=datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc),
        categories=categories,
        total_results=total_results,
        total_tests=len(series_list),
        date_range_start=date(2024, 1, 1),
        date_range_end=date(2024, 6, 1),
    )


class TestExportPdf:
    def test_creates_file(self, tmp_path: Path) -> None:
        report = _make_report()
        out = tmp_path / "test.pdf"
        result = export_pdf(report, out)
        assert result == out
        assert out.exists()
        assert out.stat().st_size > 0

    def test_valid_pdf_header(self, tmp_path: Path) -> None:
        report = _make_report()
        out = tmp_path / "test.pdf"
        export_pdf(report, out)
        with open(out, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"

    def test_empty_report(self, tmp_path: Path) -> None:
        report = TrendReport(
            vault_name="empty",
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            categories={},
            total_results=0,
            total_tests=0,
            date_range_start=None,
            date_range_end=None,
        )
        out = tmp_path / "empty.pdf"
        export_pdf(report, out)
        assert out.exists()
        with open(out, "rb") as f:
            assert f.read(5) == b"%PDF-"

    def test_abnormal_results(self, tmp_path: Path) -> None:
        """PDF with abnormal results should still generate successfully."""
        results = [
            _make_result(value="35", is_abnormal=True, result_date=date(2024, 1, 1)),
            _make_result(value="55", is_abnormal=False, result_date=date(2024, 6, 1)),
        ]
        series = _make_series(results=results)
        report = _make_report(series_list=[series])
        out = tmp_path / "abnormal.pdf"
        export_pdf(report, out)
        assert out.exists()

    def test_multiple_categories(self, tmp_path: Path) -> None:
        """PDF with multiple categories should create multi-section report."""
        lab_series = _make_series(
            test_name="HDL",
            results=[_make_result(test_name="HDL", category=ResultCategory.LAB)],
        )
        imaging_result = _make_result(
            test_name="MRI Brain",
            value="No acute findings",
            unit=None,
            category=ResultCategory.IMAGING,
        )
        imaging_series = TrendSeries(
            test_name="MRI Brain",
            category=ResultCategory.IMAGING,
            unit=None,
            points=[TrendPoint(result=imaging_result)],
            latest_value="No acute findings",
            is_numeric=False,
        )
        report = _make_report(series_list=[lab_series, imaging_series])
        out = tmp_path / "multi.pdf"
        export_pdf(report, out)
        assert out.exists()

    def test_with_doc_names(self, tmp_path: Path) -> None:
        """PDF should render document names when provided."""
        report = _make_report()
        out = tmp_path / "with_names.pdf"
        export_pdf(report, out, doc_names={"doc001": "labs-2024.pdf"})
        assert out.exists()
