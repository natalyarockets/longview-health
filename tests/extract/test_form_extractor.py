"""Tests for form-area extractor."""

from datetime import date

from longview_health.domain.enums import Confidence, ResultCategory, ValidationStatus
from longview_health.extract.form_extractor import (
    _find_header_span,
    _parse_reference_range,
    extract_from_form_group,
)


class TestParseReferenceRange:
    def test_standard_range(self) -> None:
        assert _parse_reference_range("70-99") == ("70", "99")

    def test_decimal_range(self) -> None:
        assert _parse_reference_range("0.57-1.00") == ("0.57", "1.00")

    def test_greater_than(self) -> None:
        assert _parse_reference_range(">59") == ("59", None)

    def test_less_than(self) -> None:
        assert _parse_reference_range("<200") == (None, "200")

    def test_less_than_with_equals(self) -> None:
        assert _parse_reference_range("≤5") == (None, "5")

    def test_empty(self) -> None:
        assert _parse_reference_range("") == (None, None)


class TestFindHeaderSpan:
    def test_standard_lab_headers(self) -> None:
        texts = ["TESTS", "RESULTS", "FLAG", "UNITS", "REFERENCE INTERVAL", "LAB", "hCG", "<1"]
        roles, start, count = _find_header_span(texts)
        assert count == 6
        assert start == 0
        assert roles == ["test", "result", "flag", "unit", "reference", "lab"]

    def test_minimal_headers(self) -> None:
        texts = ["TEST", "RESULT", "WBC", "7.5"]
        roles, start, count = _find_header_span(texts)
        assert count == 2
        assert start == 0
        assert roles == ["test", "result"]

    def test_no_headers(self) -> None:
        texts = ["John Doe", "2024-01-15", "Normal"]
        roles, start, count = _find_header_span(texts)
        assert count == 0
        assert roles == []

    def test_headers_after_metadata(self) -> None:
        """Real-world case: patient info before lab headers."""
        texts = [
            "Specimen Number", "Patient ID", "15022905670", "110964687",
            "Patient Last Name", "BAILEY", "Date of Birth", "1986-09-26",
            "TESTS", "RESULTS", "FLAG", "UNITS", "REFERENCE INTERVAL", "LAB",
            "hCG", "468", "", "mIU/mL", "0-5", "01",
        ]
        roles, start, count = _find_header_span(texts)
        assert count == 6
        assert start == 8
        assert roles == ["test", "result", "flag", "unit", "reference", "lab"]


class TestExtractFromFormGroup:
    def test_hcg_report(self) -> None:
        """Simulate the hCG form area: 6 headers + 6 data items = 1 result."""
        texts = [
            "TESTS", "RESULTS", "FLAG", "UNITS", "REFERENCE INTERVAL", "LAB",
            "hCG, Total, Qualitative", "<1", "", "mIU/mL", "<5", "BN",
        ]

        results = extract_from_form_group(
            group_texts=texts,
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )

        assert len(results) == 1
        r = results[0]
        assert r.test_name == "hCG, Total, Qualitative"
        assert r.result_value.value == "<1"
        assert r.result_value.unit == "mIU/mL"
        assert r.result_value.reference_low is None
        assert r.result_value.reference_high == "5"
        assert r.result_value.is_abnormal is None  # No flag
        assert r.category == ResultCategory.LAB
        assert r.extractor_version == "form-v1"
        assert r.confidence == Confidence.HIGH

    def test_multiple_results(self) -> None:
        """Two data rows after headers."""
        texts = [
            "TEST", "RESULT", "UNITS",
            "WBC", "7.5", "K/uL",
            "RBC", "4.8", "M/uL",
        ]

        results = extract_from_form_group(
            group_texts=texts,
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )

        assert len(results) == 2
        assert results[0].test_name == "WBC"
        assert results[0].result_value.value == "7.5"
        assert results[0].result_value.unit == "K/uL"
        assert results[1].test_name == "RBC"
        assert results[1].result_value.value == "4.8"

    def test_with_abnormal_flag(self) -> None:
        texts = [
            "TEST", "RESULT", "FLAG",
            "Glucose", "250", "High",
        ]

        results = extract_from_form_group(
            group_texts=texts,
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )

        assert len(results) == 1
        assert results[0].result_value.is_abnormal is True

    def test_missing_required_headers(self) -> None:
        """Should return empty if no test+result headers found."""
        texts = ["FLAG", "UNITS", "High", "mg/dL"]

        results = extract_from_form_group(
            group_texts=texts,
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )

        assert results == []

    def test_empty_input(self) -> None:
        results = extract_from_form_group(
            group_texts=[],
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )
        assert results == []

    def test_skips_empty_test_name(self) -> None:
        texts = [
            "TEST", "RESULT",
            "", "7.5",
        ]

        results = extract_from_form_group(
            group_texts=texts,
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )

        assert results == []

    def test_validation_status_pending(self) -> None:
        texts = ["TEST", "RESULT", "WBC", "7.5"]

        results = extract_from_form_group(
            group_texts=texts,
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )

        assert results[0].validation_status == ValidationStatus.PENDING

    def test_headers_buried_after_metadata(self) -> None:
        """Real-world: patient metadata precedes the header row."""
        texts = [
            "Specimen Number", "Patient ID", "15022905670", "110964687",
            "Patient Last Name", "BAILEY",
            "TESTS", "RESULTS", "FLAG", "UNITS", "REFERENCE INTERVAL", "LAB",
            "hCG,Beta Subunit,Qnt,Serum", "468", "", "mIU/mL", "0-5", "01",
        ]

        results = extract_from_form_group(
            group_texts=texts,
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )

        assert len(results) == 1
        assert results[0].test_name == "hCG,Beta Subunit,Qnt,Serum"
        assert results[0].result_value.value == "468"
        assert results[0].result_value.unit == "mIU/mL"
        assert results[0].result_value.reference_low == "0"
        assert results[0].result_value.reference_high == "5"

    def test_partial_row_ignored(self) -> None:
        """If data items don't fill a complete row, the partial row is skipped."""
        texts = [
            "TEST", "RESULT", "UNITS",
            "WBC", "7.5", "K/uL",
            "RBC",  # Incomplete row
        ]

        results = extract_from_form_group(
            group_texts=texts,
            doc_id="abc123",
            result_date=date(2025, 2, 21),
            parser_used="docling",
        )

        assert len(results) == 1
        assert results[0].test_name == "WBC"
