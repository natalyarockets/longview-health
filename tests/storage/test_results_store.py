"""Tests for storage/results_store -- insert/query roundtrip, upsert, filters."""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from longview_health.core.config import AppConfig
from longview_health.domain.enums import (
    Confidence,
    DocumentType,
    ResultCategory,
    ValidationStatus,
)
from longview_health.domain.models import Document, MedicalResult, ResultValue
from longview_health.storage import results_store, vault_store


@pytest.fixture
def config(tmp_path: Path) -> AppConfig:
    return AppConfig(vault_root=tmp_path / "vaults")


@pytest.fixture
def vault_with_doc(config: AppConfig) -> tuple[AppConfig, str]:
    """Create a vault with one document inserted."""
    vault_store.create_vault(config, "alice")
    doc = Document(
        id="doc001",
        vault_name="alice",
        filename="labs-2024.pdf",
        file_path="/path/to/labs-2024.pdf",
        document_type=DocumentType.PDF,
        content_hash="abc123hash",
        ingested_at=datetime(2024, 3, 15, tzinfo=timezone.utc),
        page_count=2,
    )
    results_store.insert_document(config, "alice", doc)
    return config, "alice"


def _make_result(
    *,
    id: str = "r001",
    document_id: str = "doc001",
    test_name: str = "HDL Cholesterol",
    value: str = "55",
    unit: str | None = "mg/dL",
    reference_low: str | None = "40",
    reference_high: str | None = "60",
    is_abnormal: bool | None = False,
    result_date: date = date(2024, 3, 15),
    category: ResultCategory = ResultCategory.LAB,
    confidence: Confidence = Confidence.HIGH,
    notes: str | None = None,
) -> MedicalResult:
    return MedicalResult(
        id=id,
        document_id=document_id,
        test_name=test_name,
        result_value=ResultValue(
            value=value,
            unit=unit,
            reference_low=reference_low,
            reference_high=reference_high,
            is_abnormal=is_abnormal,
        ),
        result_date=result_date,
        category=category,
        parser_used="docling",
        extractor_version="1.0.0",
        confidence=confidence,
    )


class TestInsertAndQuery:
    def test_insert_and_roundtrip(self, vault_with_doc: tuple) -> None:
        config, vault = vault_with_doc
        r = _make_result()
        count = results_store.insert_results(config, vault, [r])
        assert count == 1

        rows = results_store.query_results(config, vault)
        assert len(rows) == 1
        got = rows[0]
        assert got.id == "r001"
        assert got.test_name == "HDL Cholesterol"
        assert got.result_value.value == "55"
        assert got.result_value.unit == "mg/dL"
        assert got.result_value.reference_low == "40"
        assert got.result_value.reference_high == "60"
        assert got.result_value.is_abnormal is False
        assert got.result_date == date(2024, 3, 15)
        assert got.category == ResultCategory.LAB
        assert got.confidence == Confidence.HIGH
        assert got.validation_status == ValidationStatus.PENDING

    def test_insert_empty_list(self, vault_with_doc: tuple) -> None:
        config, vault = vault_with_doc
        assert results_store.insert_results(config, vault, []) == 0

    def test_upsert_replaces(self, vault_with_doc: tuple) -> None:
        config, vault = vault_with_doc
        r1 = _make_result(value="55")
        results_store.insert_results(config, vault, [r1])

        r2 = _make_result(value="60")
        results_store.insert_results(config, vault, [r2])

        rows = results_store.query_results(config, vault)
        assert len(rows) == 1
        assert rows[0].result_value.value == "60"

    def test_null_handling(self, vault_with_doc: tuple) -> None:
        config, vault = vault_with_doc
        r = _make_result(
            unit=None,
            reference_low=None,
            reference_high=None,
            is_abnormal=None,
        )
        results_store.insert_results(config, vault, [r])
        got = results_store.query_results(config, vault)[0]
        assert got.result_value.unit is None
        assert got.result_value.reference_low is None
        assert got.result_value.reference_high is None
        assert got.result_value.is_abnormal is None


class TestFilters:
    def test_filter_by_test_name(self, vault_with_doc: tuple) -> None:
        config, vault = vault_with_doc
        results_store.insert_results(
            config,
            vault,
            [
                _make_result(id="r1", test_name="HDL"),
                _make_result(id="r2", test_name="LDL"),
            ],
        )
        rows = results_store.query_results(config, vault, test_name="HDL")
        assert len(rows) == 1
        assert rows[0].test_name == "HDL"

    def test_filter_by_category(self, vault_with_doc: tuple) -> None:
        config, vault = vault_with_doc
        results_store.insert_results(
            config,
            vault,
            [
                _make_result(id="r1", category=ResultCategory.LAB),
                _make_result(id="r2", category=ResultCategory.IMAGING, test_name="MRI Brain"),
            ],
        )
        rows = results_store.query_results(config, vault, category=ResultCategory.IMAGING)
        assert len(rows) == 1
        assert rows[0].category == ResultCategory.IMAGING

    def test_filter_by_date_range(self, vault_with_doc: tuple) -> None:
        config, vault = vault_with_doc
        results_store.insert_results(
            config,
            vault,
            [
                _make_result(id="r1", result_date=date(2024, 1, 1)),
                _make_result(id="r2", result_date=date(2024, 6, 15)),
                _make_result(id="r3", result_date=date(2024, 12, 31)),
            ],
        )
        rows = results_store.query_results(
            config,
            vault,
            date_from=date(2024, 3, 1),
            date_to=date(2024, 9, 1),
        )
        assert len(rows) == 1
        assert rows[0].id == "r2"

    def test_results_sorted_by_date(self, vault_with_doc: tuple) -> None:
        config, vault = vault_with_doc
        results_store.insert_results(
            config,
            vault,
            [
                _make_result(id="r3", result_date=date(2024, 12, 1)),
                _make_result(id="r1", result_date=date(2024, 1, 1)),
                _make_result(id="r2", result_date=date(2024, 6, 1)),
            ],
        )
        rows = results_store.query_results(config, vault)
        assert [r.id for r in rows] == ["r1", "r2", "r3"]


class TestAggregations:
    def test_distinct_tests(self, vault_with_doc: tuple) -> None:
        config, vault = vault_with_doc
        results_store.insert_results(
            config,
            vault,
            [
                _make_result(id="r1", test_name="HDL"),
                _make_result(id="r2", test_name="LDL"),
                _make_result(id="r3", test_name="HDL", result_date=date(2024, 6, 1)),
            ],
        )
        tests = results_store.get_distinct_tests(config, vault)
        assert tests == ["HDL", "LDL"]

    def test_distinct_tests_by_category(self, vault_with_doc: tuple) -> None:
        config, vault = vault_with_doc
        results_store.insert_results(
            config,
            vault,
            [
                _make_result(id="r1", test_name="HDL", category=ResultCategory.LAB),
                _make_result(id="r2", test_name="MRI Brain", category=ResultCategory.IMAGING),
            ],
        )
        tests = results_store.get_distinct_tests(config, vault, category=ResultCategory.LAB)
        assert tests == ["HDL"]

    def test_counts_by_category(self, vault_with_doc: tuple) -> None:
        config, vault = vault_with_doc
        results_store.insert_results(
            config,
            vault,
            [
                _make_result(id="r1", category=ResultCategory.LAB),
                _make_result(id="r2", category=ResultCategory.LAB, test_name="LDL"),
                _make_result(id="r3", category=ResultCategory.IMAGING, test_name="MRI"),
            ],
        )
        counts = results_store.get_result_counts_by_category(config, vault)
        assert counts[ResultCategory.LAB] == 2
        assert counts[ResultCategory.IMAGING] == 1

    def test_document_names(self, vault_with_doc: tuple) -> None:
        config, vault = vault_with_doc
        names = results_store.get_document_names(config, vault, ["doc001"])
        assert names == {"doc001": "labs-2024.pdf"}

    def test_document_names_empty(self, vault_with_doc: tuple) -> None:
        config, vault = vault_with_doc
        assert results_store.get_document_names(config, vault, []) == {}
