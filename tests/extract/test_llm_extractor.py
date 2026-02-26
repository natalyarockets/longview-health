"""Tests for LLM-based structured extraction.

Mocks the Ollama API call so tests run without a live server.
Tests the full pipeline: markdown -> LLM response -> MedicalResult objects.
"""

import json
from datetime import date
from unittest.mock import patch

import pytest

from longview_health.domain.enums import Confidence, ResultCategory, ValidationStatus
from longview_health.domain.models import ParsedDocument, ParsedTable
from longview_health.extract import llm_extractor
from longview_health.extract.llm_extractor import (
    ExtractionResponse,
    ExtractedResult,
    _parse_llm_response,
)


# -- Fixtures --


def _make_parsed_doc(markdown: str = "# Lab Report\n\n| Test | Result |\n|---|---|\n| WBC | 7.5 |") -> ParsedDocument:
    return ParsedDocument(
        document_id="doc123",
        markdown=markdown,
        text_blocks=["Lab Report"],
        tables=[],
        parser_used="docling",
    )


def _make_ollama_response(results: list[dict], doc_date: str | None = "2024-03-15") -> str:
    """Build a JSON response string matching our ExtractionResponse schema."""
    return json.dumps({
        "results": results,
        "document_date": doc_date,
        "document_type": "lab report",
    })


# -- Response parsing tests --


class TestParseLLMResponse:
    def test_valid_json(self) -> None:
        raw = _make_ollama_response([
            {"test_name": "WBC", "value": "7.5", "unit": "K/uL", "category": "lab"},
        ])
        resp = _parse_llm_response(raw)
        assert len(resp.results) == 1
        assert resp.results[0].test_name == "WBC"

    def test_json_in_code_fences(self) -> None:
        raw = "```json\n" + _make_ollama_response([
            {"test_name": "WBC", "value": "7.5", "category": "lab"},
        ]) + "\n```"
        resp = _parse_llm_response(raw)
        assert len(resp.results) == 1

    def test_empty_results(self) -> None:
        raw = _make_ollama_response([])
        resp = _parse_llm_response(raw)
        assert resp.results == []

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(Exception):
            _parse_llm_response("this is not json")

    def test_full_result_fields(self) -> None:
        raw = _make_ollama_response([{
            "test_name": "HDL Cholesterol",
            "value": "55",
            "unit": "mg/dL",
            "reference_low": "40",
            "reference_high": "60",
            "is_abnormal": False,
            "category": "lab",
            "result_date": "2024-03-15",
        }])
        resp = _parse_llm_response(raw)
        r = resp.results[0]
        assert r.test_name == "HDL Cholesterol"
        assert r.reference_low == "40"
        assert r.reference_high == "60"
        assert r.is_abnormal is False


# -- Full extraction tests (mocked Ollama) --


class TestLLMExtraction:
    @patch("longview_health.extract.llm_extractor._call_ollama")
    def test_basic_extraction(self, mock_ollama: object) -> None:
        mock_ollama.return_value = _make_ollama_response([  # type: ignore[attr-defined]
            {"test_name": "WBC", "value": "7.5", "unit": "K/uL",
             "reference_low": "4.5", "reference_high": "11.0",
             "is_abnormal": False, "category": "lab"},
            {"test_name": "Hemoglobin", "value": "14.2", "unit": "g/dL",
             "reference_low": "12.0", "reference_high": "16.0",
             "is_abnormal": False, "category": "lab"},
        ])

        parsed = _make_parsed_doc()
        results = llm_extractor.extract(parsed, fallback_date=date(2024, 3, 15))

        assert len(results) == 2
        assert results[0].test_name == "WBC"
        assert results[0].result_value.value == "7.5"
        assert results[0].result_value.unit == "K/uL"
        assert results[0].result_value.reference_low == "4.5"
        assert results[0].result_value.reference_high == "11.0"
        assert results[0].result_value.is_abnormal is False
        assert results[0].category == ResultCategory.LAB
        assert results[0].parser_used == "docling"
        assert results[0].extractor_version == "llm-v1"
        assert results[0].confidence == Confidence.MEDIUM
        assert results[0].validation_status == ValidationStatus.PENDING

    @patch("longview_health.extract.llm_extractor._call_ollama")
    def test_imaging_results(self, mock_ollama: object) -> None:
        mock_ollama.return_value = _make_ollama_response([  # type: ignore[attr-defined]
            {"test_name": "Lumbar spine alignment", "value": "Normal lordosis",
             "category": "imaging"},
            {"test_name": "Disc herniation", "value": "L4-L5 mild protrusion",
             "is_abnormal": True, "category": "imaging"},
        ])

        parsed = _make_parsed_doc("# MRI Report\n\nLumbar Spine MRI findings...")
        results = llm_extractor.extract(parsed, fallback_date=date(2024, 6, 1))

        assert len(results) == 2
        assert results[0].category == ResultCategory.IMAGING
        assert results[1].result_value.is_abnormal is True

    @patch("longview_health.extract.llm_extractor._call_ollama")
    def test_date_from_document(self, mock_ollama: object) -> None:
        """LLM-found date should be used over fallback."""
        mock_ollama.return_value = _make_ollama_response(  # type: ignore[attr-defined]
            [{"test_name": "WBC", "value": "7.5", "category": "lab",
              "result_date": "2024-01-10"}],
            doc_date="2024-01-10",
        )

        parsed = _make_parsed_doc()
        results = llm_extractor.extract(parsed, fallback_date=date(2099, 1, 1))

        assert results[0].result_date == date(2024, 1, 10)

    @patch("longview_health.extract.llm_extractor._call_ollama")
    def test_fallback_date_used_when_no_date_found(self, mock_ollama: object) -> None:
        mock_ollama.return_value = _make_ollama_response(  # type: ignore[attr-defined]
            [{"test_name": "WBC", "value": "7.5", "category": "lab"}],
            doc_date=None,
        )

        parsed = _make_parsed_doc()
        fallback = date(2024, 3, 15)
        results = llm_extractor.extract(parsed, fallback_date=fallback)

        assert results[0].result_date == fallback

    @patch("longview_health.extract.llm_extractor._call_ollama")
    def test_empty_markdown_returns_empty(self, mock_ollama: object) -> None:
        parsed = ParsedDocument(
            document_id="empty",
            markdown="",
            text_blocks=[],
            tables=[],
            parser_used="docling",
        )

        results = llm_extractor.extract(parsed, fallback_date=date(2024, 1, 1))
        assert results == []
        mock_ollama.assert_not_called()  # type: ignore[attr-defined]

    @patch("longview_health.extract.llm_extractor._call_ollama")
    def test_bad_json_returns_empty(self, mock_ollama: object) -> None:
        mock_ollama.return_value = "not valid json at all"  # type: ignore[attr-defined]

        parsed = _make_parsed_doc()
        results = llm_extractor.extract(parsed, fallback_date=date(2024, 1, 1))

        assert results == []

    @patch("longview_health.extract.llm_extractor._call_ollama")
    def test_provenance_tracked(self, mock_ollama: object) -> None:
        mock_ollama.return_value = _make_ollama_response([  # type: ignore[attr-defined]
            {"test_name": "WBC", "value": "7.5", "category": "lab"},
        ])

        parsed = ParsedDocument(
            document_id="doc_pdfplumber",
            markdown="WBC: 7.5 K/uL",
            text_blocks=["WBC: 7.5 K/uL"],
            tables=[],
            parser_used="pdfplumber",
        )

        results = llm_extractor.extract(parsed, fallback_date=date(2024, 1, 1))
        assert results[0].parser_used == "pdfplumber"
        assert results[0].extractor_version == "llm-v1"

    @patch("longview_health.extract.llm_extractor._call_ollama")
    def test_multiple_categories(self, mock_ollama: object) -> None:
        mock_ollama.return_value = _make_ollama_response([  # type: ignore[attr-defined]
            {"test_name": "WBC", "value": "7.5", "category": "lab"},
            {"test_name": "Blood Pressure", "value": "120/80", "unit": "mmHg", "category": "vitals"},
            {"test_name": "Tumor size", "value": "2.3", "unit": "cm", "category": "pathology"},
        ])

        parsed = _make_parsed_doc()
        results = llm_extractor.extract(parsed, fallback_date=date(2024, 1, 1))

        categories = {r.category for r in results}
        assert ResultCategory.LAB in categories
        assert ResultCategory.VITALS in categories
        assert ResultCategory.PATHOLOGY in categories
