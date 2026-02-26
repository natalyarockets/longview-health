"""Shared Protocol definitions for module contracts.

Each protocol defines the input/output contract for a pipeline stage.
Implementations live in their respective modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from longview_health.domain.models import (
    Document,
    MedicalResult,
    ParsedDocument,
    ValidationResult,
)


class DocumentParser(Protocol):
    """Contract: file on disk -> parsed document structure."""

    def parse(self, file_path: Path) -> ParsedDocument: ...


class StructuredExtractor(Protocol):
    """Contract: parsed document -> extracted medical results."""

    def extract(self, parsed: ParsedDocument) -> Sequence[MedicalResult]: ...


class ResultValidator(Protocol):
    """Contract: extracted result -> validation outcome."""

    def validate(self, result: MedicalResult) -> ValidationResult: ...
