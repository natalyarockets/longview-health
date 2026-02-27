"""Domain models -- the typed core of the system.

All domain types are immutable. They flow through the pipeline but are never
mutated in place. New instances are created at each stage boundary.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from longview_health.domain.enums import (
    Confidence,
    DocumentType,
    ResultCategory,
    ValidationStatus,
)


# ---------------------------------------------------------------------------
# Vault
# ---------------------------------------------------------------------------


class Vault(BaseModel, frozen=True):
    """A vault represents one person's medical document collection."""

    name: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class Document(BaseModel, frozen=True):
    """A source document ingested into a vault."""

    id: str = Field(description="Content hash (SHA-256) of the file.")
    vault_name: str
    filename: str
    file_path: str
    document_type: DocumentType
    content_hash: str
    ingested_at: datetime
    page_count: int | None = None


# ---------------------------------------------------------------------------
# Parsed document (output of parsing stage)
# ---------------------------------------------------------------------------


class ParsedTable(BaseModel, frozen=True):
    """A table extracted from a document."""

    headers: list[str]
    rows: list[list[str]]
    page: int | None = None


class ParsedDocument(BaseModel, frozen=True):
    """Output of the document parsing stage.

    Contains the full markdown representation of the document (primary),
    plus structured text blocks and tables for direct access.
    The markdown is what gets fed to the LLM for structured extraction.
    """

    document_id: str
    markdown: str = Field(description="Full document as markdown (Docling export). Primary input for LLM extraction.")
    text_blocks: list[str]
    tables: list[ParsedTable]
    parser_used: str
    page_count: int | None = None
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Rich conversion (preserves Docling element tree)
# ---------------------------------------------------------------------------


class DoclingConversion(BaseModel, frozen=True):
    """Pairs a ParsedDocument with the raw Docling document object.

    The docling_document preserves Docling's element tree (tables, groups,
    form areas) for smart routing. Uses Any to avoid coupling domain to
    docling_core types. None when parsed by a non-Docling parser (e.g.
    pdfplumber fallback).
    """

    parsed: ParsedDocument
    docling_document: Any | None = None


# ---------------------------------------------------------------------------
# Medical results (output of extraction stage)
# ---------------------------------------------------------------------------


class ResultValue(BaseModel, frozen=True):
    """A single value within a medical result.

    Examples:
    - Lab: value=145, unit="mg/dL", reference_low=100, reference_high=199
    - Imaging: value="No acute findings", unit=None (narrative)
    - Vitals: value=120, unit="mmHg"
    """

    value: str = Field(description="The extracted value, always stored as string for uniformity.")
    unit: str | None = None
    reference_low: str | None = None
    reference_high: str | None = None
    is_abnormal: bool | None = None


class MedicalResult(BaseModel, frozen=True):
    """A single extracted medical result/finding from a document.

    Covers labs, imaging findings, pathology, diagnostics, vitals, etc.
    """

    id: str = Field(description="Deterministic composite key.")
    document_id: str
    test_name: str
    result_value: ResultValue
    result_date: date
    category: ResultCategory
    parser_used: str = Field(description="Which parser produced the source data (e.g. docling, pdfplumber).")
    extractor_version: str
    confidence: Confidence
    validation_status: ValidationStatus = ValidationStatus.PENDING
    notes: str | None = None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class ValidationResult(BaseModel, frozen=True):
    """Output of the validation engine for a single result."""

    result_id: str
    status: ValidationStatus
    issues: list[str] = Field(default_factory=list)
    adjusted_confidence: Confidence | None = None


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------


class ReviewItem(BaseModel, frozen=True):
    """An item in the review queue for manual correction."""

    id: str
    result: MedicalResult
    reason: str
    created_at: datetime
    resolved: bool = False
    resolved_at: datetime | None = None


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------


class TrendPoint(BaseModel, frozen=True):
    """A single point in a trend series, wrapping a MedicalResult with deltas."""

    result: MedicalResult
    delta: float | None = None
    delta_percent: float | None = None


class TrendSeries(BaseModel, frozen=True):
    """Chronological series for one test/finding."""

    test_name: str
    category: ResultCategory
    unit: str | None
    points: list[TrendPoint]
    latest_value: str
    is_numeric: bool


class TrendReport(BaseModel, frozen=True):
    """Full trend report for a vault."""

    vault_name: str
    generated_at: datetime
    categories: dict[ResultCategory, list[TrendSeries]]
    total_results: int
    total_tests: int
    date_range_start: date | None
    date_range_end: date | None
