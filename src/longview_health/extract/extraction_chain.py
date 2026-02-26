"""Extraction orchestration.

Pipeline: Docling markdown -> LLM -> structured MedicalResult objects.

The LLM is the sole extractor. It receives the clean markdown that Docling
produces and maps it to our schema. No regex, no header guessing.
"""

from __future__ import annotations

from datetime import date

from longview_health.domain.models import MedicalResult, ParsedDocument
from longview_health.extract import llm_extractor


def extract(
    parsed: ParsedDocument,
    fallback_date: date,
    model: str = llm_extractor.DEFAULT_MODEL,
    base_url: str = llm_extractor.DEFAULT_OLLAMA_URL,
) -> list[MedicalResult]:
    """Extract structured medical results from a parsed document.

    Uses Docling's markdown output + LLM for robust extraction
    across all document types (labs, imaging, pathology, etc.).

    Args:
        parsed: Output of the document parsing stage.
        fallback_date: Date to use if the LLM can't find a date in the document.
        model: Ollama model name.
        base_url: Ollama API base URL.

    Returns:
        List of MedicalResult objects with full provenance.
    """
    return llm_extractor.extract(
        parsed=parsed,
        fallback_date=fallback_date,
        model=model,
        base_url=base_url,
    )
