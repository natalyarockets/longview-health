"""Tests for domain models -- verify immutability and serialization."""

from datetime import date, datetime, timezone

import pytest

from longview_health.domain.enums import (
    Confidence,
    DocumentType,
    ResultCategory,
    ValidationStatus,
)
from longview_health.domain.models import (
    Document,
    MedicalResult,
    ParsedDocument,
    ParsedTable,
    ResultValue,
    Vault,
)


def test_vault_is_immutable() -> None:
    v = Vault(name="alice", created_at=datetime.now(timezone.utc))
    with pytest.raises(Exception):
        v.name = "bob"  # type: ignore[misc]


def test_document_roundtrip() -> None:
    doc = Document(
        id="abc123",
        vault_name="alice",
        filename="labs.pdf",
        file_path="/path/to/labs.pdf",
        document_type=DocumentType.PDF,
        content_hash="sha256hex",
        ingested_at=datetime.now(timezone.utc),
    )
    data = doc.model_dump()
    restored = Document.model_validate(data)
    assert restored == doc


def test_medical_result_roundtrip() -> None:
    result = MedicalResult(
        id="r123",
        document_id="doc456",
        test_name="HDL Cholesterol",
        result_value=ResultValue(
            value="55",
            unit="mg/dL",
            reference_low="40",
            reference_high="60",
            is_abnormal=False,
        ),
        result_date=date(2024, 3, 15),
        category=ResultCategory.LAB,
        parser_used="docling",
        extractor_version="1.0.0",
        confidence=Confidence.HIGH,
    )
    data = result.model_dump()
    restored = MedicalResult.model_validate(data)
    assert restored == result
    assert restored.validation_status == ValidationStatus.PENDING


def test_parsed_document_with_tables() -> None:
    table = ParsedTable(
        headers=["Test", "Result", "Unit", "Reference"],
        rows=[["HDL", "55", "mg/dL", "40-60"]],
        page=1,
    )
    parsed = ParsedDocument(
        document_id="doc1",
        text_blocks=["Lab Results Report"],
        tables=[table],
        parser_used="docling",
    )
    assert len(parsed.tables) == 1
    assert parsed.tables[0].rows[0][0] == "HDL"
