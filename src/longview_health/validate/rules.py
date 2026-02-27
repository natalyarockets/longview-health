"""Validation rules for extracted medical results.

Each rule is a function: MedicalResult -> list[str] (issues found).
Empty list means the rule passed.
"""

from __future__ import annotations

import re
from datetime import date

from longview_health.domain.models import MedicalResult

# Known units (case-insensitive) -- not exhaustive, but covers common ones
_KNOWN_UNITS: set[str] = {
    # Lab
    "mg/dl", "g/dl", "mmol/l", "umol/l", "ng/ml", "pg/ml", "ng/dl",
    "ug/dl", "iu/l", "u/l", "miu/ml", "mu/l", "meq/l", "mmol/l",
    "cells/ul", "cells/mcl", "/ul", "/mcl", "x10e3/ul", "x10e6/ul",
    "x10^3/ul", "x10^6/ul", "10*3/ul", "10*6/ul",
    "%", "g/l", "mg/l", "ug/l", "fl", "pg", "sec", "seconds",
    "mm/hr", "ratio", "index", "titer",
    # Vitals
    "mmhg", "bpm", "breaths/min", "°f", "°c", "kg", "lbs", "cm", "in",
    "kg/m2", "kg/m²",
    # Imaging / misc
    "mm", "cm", "ml", "cc",
}

# Physiological sanity bounds by common test name patterns
# These are intentionally very wide -- just catching gross extraction errors
_PLAUSIBLE_RANGES: list[tuple[str, float, float]] = [
    # Hematology
    ("wbc", 0.1, 500),
    ("rbc", 0.1, 20),
    ("hemoglobin", 1, 30),
    ("hematocrit", 1, 80),
    ("platelet", 1, 2000),
    ("mcv", 20, 200),
    ("mch", 5, 100),
    ("mchc", 10, 50),
    # Chemistry
    ("glucose", 1, 1000),
    ("creatinine", 0.01, 50),
    ("bun", 0.1, 300),
    ("sodium", 50, 250),
    ("potassium", 0.5, 15),
    ("chloride", 50, 200),
    ("calcium", 1, 25),
    ("protein", 0.1, 20),
    ("albumin", 0.1, 10),
    ("bilirubin", 0.01, 50),
    ("ast", 0.1, 10000),
    ("alt", 0.1, 10000),
    ("alkaline phosphatase", 1, 5000),
    ("cholesterol", 10, 1000),
    ("hdl", 1, 200),
    ("ldl", 1, 500),
    ("triglyceride", 1, 5000),
    # Thyroid
    ("tsh", 0.001, 200),
    ("t3", 0.1, 1000),
    ("t4", 0.1, 50),
    # Vitals
    ("heart rate", 10, 300),
    ("pulse", 10, 300),
    ("systolic", 30, 300),
    ("diastolic", 10, 200),
    ("temperature", 85, 115),  # Fahrenheit range
    ("weight", 0.5, 700),
    ("height", 10, 300),
    ("bmi", 5, 100),
    ("respiratory rate", 1, 60),
    ("oxygen saturation", 30, 100),
    ("spo2", 30, 100),
]


def _try_float(value: str) -> float | None:
    """Try to parse a value as float, stripping comparators."""
    cleaned = re.sub(r"^[<>≤≥]=?\s*", "", value.strip())
    try:
        return float(cleaned)
    except (ValueError, OverflowError):
        return None


def check_required_fields(result: MedicalResult) -> list[str]:
    """Test name, value, and date must be present."""
    issues: list[str] = []
    if not result.test_name or not result.test_name.strip():
        issues.append("Missing test name")
    if not result.result_value.value or not result.result_value.value.strip():
        issues.append("Missing result value")
    return issues


def check_date_plausible(result: MedicalResult) -> list[str]:
    """Date must not be in the future and not before 1900."""
    issues: list[str] = []
    if result.result_date > date.today():
        issues.append(f"Result date is in the future: {result.result_date}")
    if result.result_date.year < 1900:
        issues.append(f"Result date is implausibly old: {result.result_date}")
    return issues


def check_unit_recognized(result: MedicalResult) -> list[str]:
    """If a unit is present, flag if it's not in our known-units set."""
    unit = result.result_value.unit
    if not unit:
        return []
    if unit.strip().lower() in _KNOWN_UNITS:
        return []
    return [f"Unrecognized unit: {unit}"]


def check_value_plausible(result: MedicalResult) -> list[str]:
    """If the value is numeric and the test name matches a known range, check bounds."""
    numeric = _try_float(result.result_value.value)
    if numeric is None:
        return []  # Non-numeric values (narrative) are fine

    test_lower = result.test_name.lower()
    for pattern, lo, hi in _PLAUSIBLE_RANGES:
        if pattern in test_lower:
            if numeric < lo or numeric > hi:
                return [
                    f"Value {numeric} outside plausible range "
                    f"[{lo}-{hi}] for {result.test_name}"
                ]
            break  # Found matching pattern, value is OK
    return []


def check_reference_range_consistent(result: MedicalResult) -> list[str]:
    """If both reference bounds are present, low should be <= high."""
    rv = result.result_value
    if not rv.reference_low or not rv.reference_high:
        return []
    lo = _try_float(rv.reference_low)
    hi = _try_float(rv.reference_high)
    if lo is not None and hi is not None and lo > hi:
        return [f"Reference range inverted: {rv.reference_low} > {rv.reference_high}"]
    return []


# All rules, in order of importance
ALL_RULES = [
    check_required_fields,
    check_date_plausible,
    check_unit_recognized,
    check_value_plausible,
    check_reference_range_consistent,
]
