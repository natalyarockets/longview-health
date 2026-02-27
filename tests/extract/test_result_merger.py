"""Tests for result merger."""

from datetime import date

from longview_health.domain.enums import Confidence, ResultCategory, ValidationStatus
from longview_health.domain.identifiers import result_key
from longview_health.domain.models import MedicalResult, ResultValue
from longview_health.extract.result_merger import merge


def _make_result(
    test_name: str = "WBC",
    extractor_version: str = "table-v1",
    value: str = "7.5",
    doc_id: str = "doc123",
    result_date: date = date(2025, 2, 21),
) -> MedicalResult:
    rid = result_key(doc_id, test_name, result_date)
    return MedicalResult(
        id=rid,
        document_id=doc_id,
        test_name=test_name,
        result_value=ResultValue(value=value, unit="K/uL"),
        result_date=result_date,
        category=ResultCategory.LAB,
        parser_used="docling",
        extractor_version=extractor_version,
        confidence=Confidence.HIGH,
        validation_status=ValidationStatus.PENDING,
    )


class TestMerge:
    def test_no_duplicates_keeps_all(self) -> None:
        a = _make_result(test_name="WBC")
        b = _make_result(test_name="RBC")

        merged = merge([a], [b])

        assert len(merged) == 2

    def test_duplicate_keeps_higher_priority(self) -> None:
        table_result = _make_result(extractor_version="table-v1")
        llm_result = _make_result(extractor_version="llm-v1")

        merged = merge([table_result], [llm_result])

        assert len(merged) == 1
        assert merged[0].extractor_version == "table-v1"

    def test_form_beats_llm(self) -> None:
        form_result = _make_result(extractor_version="form-v1")
        llm_result = _make_result(extractor_version="llm-v1")

        merged = merge([form_result], [llm_result])

        assert len(merged) == 1
        assert merged[0].extractor_version == "form-v1"

    def test_table_beats_form(self) -> None:
        table_result = _make_result(extractor_version="table-v1")
        form_result = _make_result(extractor_version="form-v1")

        merged = merge([table_result], [form_result])

        assert len(merged) == 1
        assert merged[0].extractor_version == "table-v1"

    def test_empty_inputs(self) -> None:
        assert merge([], []) == []

    def test_single_list(self) -> None:
        a = _make_result(test_name="WBC")
        assert len(merge([a])) == 1

    def test_multiple_lists(self) -> None:
        a = _make_result(test_name="WBC", extractor_version="table-v1")
        b = _make_result(test_name="RBC", extractor_version="form-v1")
        c = _make_result(test_name="HGB", extractor_version="llm-v1")

        merged = merge([a], [b], [c])

        assert len(merged) == 3

    def test_unknown_extractor_lowest_priority(self) -> None:
        known = _make_result(extractor_version="llm-v1")
        unknown = _make_result(extractor_version="experimental-v0")

        merged = merge([known], [unknown])

        assert len(merged) == 1
        assert merged[0].extractor_version == "llm-v1"

    def test_order_of_input_does_not_matter(self) -> None:
        """Priority is by extractor version, not by input order."""
        llm_result = _make_result(extractor_version="llm-v1")
        table_result = _make_result(extractor_version="table-v1")

        # LLM first, table second -- table should still win
        merged = merge([llm_result], [table_result])

        assert len(merged) == 1
        assert merged[0].extractor_version == "table-v1"
