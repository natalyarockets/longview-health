"""Trend analysis engine -- pure functions, no I/O.

Takes lists of MedicalResult and produces TrendSeries / TrendReport objects.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone

from longview_health.domain.enums import ResultCategory
from longview_health.domain.models import (
    MedicalResult,
    TrendPoint,
    TrendReport,
    TrendSeries,
)


def _try_parse_numeric(value: str) -> float | None:
    """Try to parse a string value as a number.

    Handles plain numbers ("145", "3.5"), comparators ("<0.01", ">200"),
    and strips whitespace. Returns None for narrative/non-numeric values.
    """
    cleaned = value.strip()
    # Strip leading comparison operators
    cleaned = re.sub(r"^[<>≤≥]=?\s*", "", cleaned)
    try:
        return float(cleaned)
    except (ValueError, OverflowError):
        return None


def build_trend_series(
    test_name: str, results: list[MedicalResult]
) -> TrendSeries:
    """Build a chronological TrendSeries for one test from its results.

    Results are sorted by date. Deltas are computed between consecutive
    numeric values.
    """
    sorted_results = sorted(results, key=lambda r: r.result_date)

    points: list[TrendPoint] = []
    prev_numeric: float | None = None

    for r in sorted_results:
        numeric = _try_parse_numeric(r.result_value.value)
        delta: float | None = None
        delta_percent: float | None = None

        if numeric is not None and prev_numeric is not None:
            delta = round(numeric - prev_numeric, 4)
            if prev_numeric != 0:
                delta_percent = round((delta / prev_numeric) * 100, 2)

        points.append(TrendPoint(result=r, delta=delta, delta_percent=delta_percent))

        if numeric is not None:
            prev_numeric = numeric

    # Determine if the series is numeric (majority of values parse as numbers)
    numeric_count = sum(
        1 for r in sorted_results if _try_parse_numeric(r.result_value.value) is not None
    )
    is_numeric = numeric_count > len(sorted_results) / 2

    # Unit from the most recent result that has one
    unit: str | None = None
    for r in reversed(sorted_results):
        if r.result_value.unit:
            unit = r.result_value.unit
            break

    latest_value = sorted_results[-1].result_value.value if sorted_results else ""

    return TrendSeries(
        test_name=test_name,
        category=sorted_results[0].category if sorted_results else ResultCategory.OTHER,
        unit=unit,
        points=points,
        latest_value=latest_value,
        is_numeric=is_numeric,
    )


def build_trend_report(
    vault_name: str, results: list[MedicalResult]
) -> TrendReport:
    """Build a full TrendReport from all results in a vault.

    Groups by category, then by test_name. Each group becomes a TrendSeries.
    """
    # Group results by (category, test_name)
    grouped: dict[ResultCategory, dict[str, list[MedicalResult]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in results:
        grouped[r.category][r.test_name].append(r)

    categories: dict[ResultCategory, list[TrendSeries]] = {}
    total_tests = 0
    for cat in sorted(grouped.keys(), key=lambda c: c.value):
        series_list: list[TrendSeries] = []
        for test_name in sorted(grouped[cat].keys()):
            series_list.append(build_trend_series(test_name, grouped[cat][test_name]))
            total_tests += 1
        categories[cat] = series_list

    dates = [r.result_date for r in results]

    return TrendReport(
        vault_name=vault_name,
        generated_at=datetime.now(timezone.utc),
        categories=categories,
        total_results=len(results),
        total_tests=total_tests,
        date_range_start=min(dates) if dates else None,
        date_range_end=max(dates) if dates else None,
    )
