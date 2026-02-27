"""LLM-based structured extractor.

Takes the markdown output from Docling and uses a local LLM (via Ollama)
to extract structured medical results. The LLM output is schema-constrained
to our Pydantic types and validation-gated before entering trusted storage.

This is the primary extraction method. Docling handles layout/structure,
the LLM handles semantic understanding of what the content means.
"""

from __future__ import annotations

import json
import logging
from datetime import date

import httpx
from pydantic import BaseModel, Field

from longview_health.domain.enums import Confidence, ResultCategory, ValidationStatus
from longview_health.domain.identifiers import result_key
from longview_health.domain.models import MedicalResult, ParsedDocument, ResultValue

logger = logging.getLogger(__name__)

EXTRACTOR_VERSION = "llm-v1"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5vl:latest"


# ---------------------------------------------------------------------------
# Schema for LLM output -- kept simple and flat for reliable extraction
# ---------------------------------------------------------------------------


class ExtractedResult(BaseModel):
    """Schema the LLM must produce for each result found."""

    test_name: str = Field(description="Name of the test, finding, or measurement.")
    value: str = Field(description="The result value (numeric or text).")
    unit: str | None = Field(default=None, description="Unit of measurement if applicable.")
    reference_low: str | None = Field(default=None, description="Lower bound of reference range.")
    reference_high: str | None = Field(default=None, description="Upper bound of reference range.")
    is_abnormal: bool | None = Field(default=None, description="Whether the result is outside the normal range.")
    category: str = Field(
        default="lab",
        description="Category: 'lab', 'imaging', 'pathology', 'diagnostic', 'vitals', or 'other'.",
    )
    result_date: str | None = Field(
        default=None,
        description="Date of the result in YYYY-MM-DD format, if found in the document.",
    )


class ExtractionResponse(BaseModel):
    """Top-level schema for LLM extraction output."""

    results: list[ExtractedResult] = Field(default_factory=list)
    document_date: str | None = Field(
        default=None,
        description="Overall document date in YYYY-MM-DD format, if found.",
    )
    document_type: str | None = Field(
        default=None,
        description="Type of document (e.g. 'lab report', 'radiology report', 'pathology report').",
    )


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """You are a medical document data extractor. Extract ALL test results, findings, and measurements from this document.

For each result found, provide:
- test_name: the name of the test or finding
- value: the result value
- unit: unit of measurement (null if not applicable)
- reference_low: lower bound of reference/normal range (null if not provided)
- reference_high: upper bound of reference/normal range (null if not provided)
- is_abnormal: true if flagged as abnormal/high/low, false if normal, null if unclear
- category: one of "lab", "imaging", "pathology", "diagnostic", "vitals", "other"
- result_date: date of this specific result in YYYY-MM-DD format (null if not found)

Also extract:
- document_date: the overall document date in YYYY-MM-DD format
- document_type: what kind of document this is

IMPORTANT:
- Extract EVERY result, finding, or measurement. Do not skip any.
- For reference ranges like "4.5-11.0", split into reference_low and reference_high.
- For ranges like "< 200", set reference_high=200 and reference_low=null.
- Keep values exactly as they appear (do not convert units or round).
- If a result is flagged as H, L, HH, LL, or abnormal, set is_abnormal=true.

Respond with ONLY valid JSON matching this schema, no other text:
{schema}

Document content:
{document}"""


# ---------------------------------------------------------------------------
# Ollama client
# ---------------------------------------------------------------------------


def _call_ollama(
    prompt: str,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_OLLAMA_URL,
    timeout: float = 300.0,
) -> str:
    """Send a prompt to Ollama and return the response text."""
    import subprocess
    import tempfile

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 4096,
            "num_ctx": 16384,
        },
        "format": "json",
    })

    # Use curl instead of httpx — httpx has buffering issues with large
    # payloads to Ollama that cause requests to hang until connection close.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(payload)
        payload_file = f.name

    try:
        result = subprocess.run(
            [
                "curl", "-s", "-S",
                "--max-time", str(int(timeout)),
                "-H", "Content-Type: application/json",
                "-d", f"@{payload_file}",
                f"{base_url}/api/generate",
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"curl failed: {result.stderr}")
        return json.loads(result.stdout)["response"]
    finally:
        import os
        os.unlink(payload_file)


def _parse_llm_response(raw: str) -> ExtractionResponse:
    """Parse the LLM's JSON response into our schema.

    Tolerant of minor formatting issues.
    """
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    data = json.loads(text)
    return ExtractionResponse.model_validate(data)


# ---------------------------------------------------------------------------
# Category mapping
# ---------------------------------------------------------------------------

_CATEGORY_MAP: dict[str, ResultCategory] = {
    "lab": ResultCategory.LAB,
    "imaging": ResultCategory.IMAGING,
    "pathology": ResultCategory.PATHOLOGY,
    "diagnostic": ResultCategory.DIAGNOSTIC,
    "vitals": ResultCategory.VITALS,
    "other": ResultCategory.OTHER,
}


def _map_category(raw: str) -> ResultCategory:
    return _CATEGORY_MAP.get(raw.lower().strip(), ResultCategory.OTHER)


def _parse_date(date_str: str | None, fallback: date) -> date:
    """Parse a date string, falling back to the provided default."""
    if not date_str:
        return fallback
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return fallback


# ---------------------------------------------------------------------------
# Markdown cleanup -- Docling sometimes produces tables with duplicated columns
# ---------------------------------------------------------------------------


def _dedup_table_columns(markdown: str) -> str:
    """Remove duplicate columns from markdown tables.

    Docling sometimes produces tables where the same content is repeated across
    multiple columns (e.g., an 8-column table where columns 2-8 are copies of
    column 1). This inflates the prompt by 10x and can cause Ollama to fail.
    """
    lines = markdown.split("\n")
    cleaned = []
    for line in lines:
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.split("|")]
            # cells[0] and cells[-1] are empty strings from leading/trailing |
            cells = cells[1:-1]
            if len(cells) > 2:
                # Keep only unique cells in order (preserves first occurrence)
                seen = set()
                unique = []
                for cell in cells:
                    normalized = cell.strip().strip("-")
                    if normalized not in seen:
                        seen.add(normalized)
                        unique.append(cell)
                if len(unique) < len(cells):
                    line = "| " + " | ".join(unique) + " |"
        cleaned.append(line)
    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# Region-focused prompt (smaller context = faster + more accurate)
# ---------------------------------------------------------------------------

REGION_EXTRACTION_PROMPT = """You are a medical document data extractor. This is ONE REGION from a medical document.

If this region contains test results with ACTUAL MEASURED VALUES, extract them.
If this region does NOT contain measured values, return an empty results list.

Return EMPTY results for regions that only contain:
- Patient demographics (name, DOB, address, phone)
- Column headers (TESTS, RESULTS, FLAG, UNITS, REFERENCE INTERVAL, LAB)
- Test order codes or requisition numbers (e.g. "004416")
- Administrative text (lab address, physician info, page numbers)
- Reference range tables without corresponding measured values

A measured value is an actual number or measurement from a test (e.g. "7.5", "468", "<1", "Negative", "Normal"). Order codes, test codes, and requisition numbers are NOT measured values.

For each result found, provide:
- test_name: the name of the test or finding
- value: the MEASURED value (a number or measurement, NOT an order code or test code)
- unit: unit of measurement (null if not applicable)
- reference_low: lower bound of reference/normal range (null if not provided)
- reference_high: upper bound of reference/normal range (null if not provided)
- is_abnormal: true if flagged as abnormal/high/low, false if normal, null if unclear
- category: one of "lab", "imaging", "pathology", "diagnostic", "vitals", "other"
- result_date: date of this specific result in YYYY-MM-DD format (null if not found)

IMPORTANT:
- For reference ranges like "4.5-11.0", split into reference_low and reference_high.
- Keep values exactly as they appear (do not convert units or round).
- If a result is flagged as H, L, HH, LL, or abnormal, set is_abnormal=true.

Respond with ONLY valid JSON matching this schema, no other text:
{schema}

Region content:
{region}"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract(
    parsed: ParsedDocument,
    fallback_date: date,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_OLLAMA_URL,
) -> list[MedicalResult]:
    """Extract structured medical results from a parsed document using an LLM.

    Args:
        parsed: Output of the document parsing stage (must have markdown).
        fallback_date: Date to use if the LLM can't find a date in the document.
        model: Ollama model to use.
        base_url: Ollama API base URL.

    Returns:
        List of extracted MedicalResult objects.
    """
    if not parsed.markdown.strip():
        logger.warning("Empty markdown for document %s, skipping LLM extraction", parsed.document_id)
        return []

    # Clean up duplicated table columns from Docling output
    cleaned_markdown = _dedup_table_columns(parsed.markdown)
    logger.info(
        "Markdown %d -> %d chars after dedup", len(parsed.markdown), len(cleaned_markdown)
    )

    schema_json = ExtractionResponse.model_json_schema()
    prompt = EXTRACTION_PROMPT.format(
        schema=json.dumps(schema_json, indent=2),
        document=cleaned_markdown,
    )

    try:
        raw_response = _call_ollama(prompt, model=model, base_url=base_url)
    except RuntimeError as e:
        logger.error("Ollama call failed: %s", e)
        raise
    except Exception as e:
        logger.error(
            "Cannot connect to Ollama at %s. Is it running? (ollama serve): %s",
            base_url, e,
        )
        raise

    try:
        extraction = _parse_llm_response(raw_response)
    except (json.JSONDecodeError, Exception) as e:
        logger.error(
            "Failed to parse LLM response for document %s: %s\nRaw: %s",
            parsed.document_id, e, raw_response[:500],
        )
        return []

    # Convert to domain MedicalResult objects
    doc_date = _parse_date(extraction.document_date, fallback_date)
    results: list[MedicalResult] = []

    for item in extraction.results:
        result_date = _parse_date(item.result_date, doc_date)
        rid = result_key(parsed.document_id, item.test_name, result_date)

        results.append(
            MedicalResult(
                id=rid,
                document_id=parsed.document_id,
                test_name=item.test_name,
                result_value=ResultValue(
                    value=item.value,
                    unit=item.unit,
                    reference_low=item.reference_low,
                    reference_high=item.reference_high,
                    is_abnormal=item.is_abnormal,
                ),
                result_date=result_date,
                category=_map_category(item.category),
                parser_used=parsed.parser_used,
                extractor_version=EXTRACTOR_VERSION,
                confidence=Confidence.MEDIUM,
                validation_status=ValidationStatus.PENDING,
            )
        )

    return results


def extract_region(
    region_text: str,
    doc_id: str,
    parser_used: str,
    fallback_date: date,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_OLLAMA_URL,
) -> list[MedicalResult]:
    """Extract structured medical results from a single document region.

    Sends a small, focused chunk of text to the LLM instead of the entire
    document. Faster and more accurate than whole-document extraction.

    Args:
        region_text: Text content of one document region.
        doc_id: Document content hash.
        parser_used: Which parser produced the source data.
        fallback_date: Date to use if no date found.
        model: Ollama model to use.
        base_url: Ollama API base URL.

    Returns:
        List of extracted MedicalResult objects.
    """
    if not region_text.strip():
        return []

    schema_json = ExtractionResponse.model_json_schema()
    prompt = REGION_EXTRACTION_PROMPT.format(
        schema=json.dumps(schema_json, indent=2),
        region=region_text,
    )

    try:
        raw_response = _call_ollama(prompt, model=model, base_url=base_url)
    except RuntimeError as e:
        logger.error("Ollama call failed for region: %s", e)
        return []
    except Exception as e:
        logger.error("Cannot connect to Ollama at %s: %s", base_url, e)
        return []

    try:
        extraction = _parse_llm_response(raw_response)
    except (json.JSONDecodeError, Exception) as e:
        logger.error("Failed to parse LLM response for region: %s\nRaw: %s", e, raw_response[:500])
        return []

    doc_date = _parse_date(extraction.document_date, fallback_date)
    results: list[MedicalResult] = []

    for item in extraction.results:
        result_date = _parse_date(item.result_date, doc_date)
        rid = result_key(doc_id, item.test_name, result_date)

        results.append(
            MedicalResult(
                id=rid,
                document_id=doc_id,
                test_name=item.test_name,
                result_value=ResultValue(
                    value=item.value,
                    unit=item.unit,
                    reference_low=item.reference_low,
                    reference_high=item.reference_high,
                    is_abnormal=item.is_abnormal,
                ),
                result_date=result_date,
                category=_map_category(item.category),
                parser_used=parser_used,
                extractor_version=EXTRACTOR_VERSION,
                confidence=Confidence.MEDIUM,
                validation_status=ValidationStatus.PENDING,
            )
        )

    return results
