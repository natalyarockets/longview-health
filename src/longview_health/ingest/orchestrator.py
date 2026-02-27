"""Ingestion orchestrator -- coordinate the full pipeline for a vault.

    enumerate files → hash → deduplicate → parse → extract → validate → store

Each step has a single responsibility. The orchestrator connects them
and reports what happened. Failed documents go to the review queue
rather than being silently skipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from longview_health.core.config import AppConfig
from longview_health.core.paths import vault_documents_dir
from longview_health.domain.enums import DocumentType
from longview_health.domain.identifiers import content_hash
from longview_health.domain.models import Document, MedicalResult, ParsedDocument
from longview_health.ingest.enumerator import enumerate_documents, suffix_to_document_type
from longview_health.storage import document_store, results_store


@dataclass(frozen=True)
class IngestResult:
    """Summary of what happened during ingestion."""

    files_found: int
    files_new: int
    files_skipped: int  # already ingested, unchanged
    documents_parsed: int
    results_extracted: int
    results_stored: int
    errors: list[str] = field(default_factory=list)


def _build_document(
    vault_name: str, file_path: Path, file_hash: str
) -> Document:
    """Build a Document model from a file on disk."""
    doc_type = suffix_to_document_type(file_path.suffix) or DocumentType.UNKNOWN
    return Document(
        id=file_hash,
        vault_name=vault_name,
        filename=file_path.name,
        file_path=str(file_path.resolve()),
        document_type=doc_type,
        content_hash=file_hash,
        ingested_at=datetime.now(timezone.utc),
    )


def _parse_and_extract(
    file_path: Path, doc: Document
) -> tuple[ParsedDocument, list[MedicalResult]]:
    """Parse and extract results from a single document.

    Returns (parsed_document, results) so the caller can use the parsed
    content for FTS indexing.

    Uses the full pipeline: Docling parse → region grouping → extraction.
    """
    from longview_health.extract import parser_chain, llm_extractor, result_merger, table_parser
    from longview_health.extract.region_grouper import group_regions
    from longview_health.extract.table_parser import _detect_date

    conversion = parser_chain.parse_rich(file_path)
    parsed = conversion.parsed
    result_date = _detect_date(parsed.markdown) or date.today()

    all_lists: list[list[MedicalResult]] = []

    if conversion.docling_document:
        regions = group_regions(conversion.docling_document)

        # Table regions — deterministic, fast
        for region in regions:
            if region.table_item is None:
                continue
            table_results = table_parser.extract_from_table_item(
                table_item=region.table_item,
                doc_id=parsed.document_id,
                result_date=result_date,
                parser_used=parsed.parser_used,
            )
            all_lists.append(table_results)

        # Text regions — combined LLM call
        text_regions = [r for r in regions if r.table_item is None and r.text.strip()]
        if text_regions:
            combined = "\n\n---\n\n".join(r.text.strip() for r in text_regions)
            llm_results = llm_extractor.extract_region(
                region_text=combined,
                doc_id=parsed.document_id,
                parser_used=parsed.parser_used,
                fallback_date=result_date,
            )
            all_lists.append(llm_results)

        return parsed, result_merger.merge(*all_lists)
    else:
        # Fallback: use table parser on full document
        return parsed, table_parser.extract(parsed=parsed, fallback_date=result_date)


def _validate_and_triage(
    config: AppConfig,
    vault_name: str,
    results: list[MedicalResult],
) -> list[MedicalResult]:
    """Run validation. Store-worthy results are returned; rejected go to review queue."""
    from longview_health.domain.enums import ValidationStatus
    from longview_health.storage import review_store
    from longview_health.validate.engine import validate_one

    accepted: list[MedicalResult] = []
    for result in results:
        updated, outcome = validate_one(result)
        if outcome.status == ValidationStatus.REJECTED:
            review_store.add_to_review(
                config,
                vault_name,
                result_id=result.id,
                document_id=result.document_id,
                test_name=result.test_name,
                reason="; ".join(outcome.issues),
            )
        else:
            accepted.append(updated)
            # Flagged results also go to review queue for human verification
            if outcome.status == ValidationStatus.FLAGGED:
                review_store.add_to_review(
                    config,
                    vault_name,
                    result_id=result.id,
                    document_id=result.document_id,
                    test_name=result.test_name,
                    reason="; ".join(outcome.issues),
                )
    return accepted


def ingest_vault(
    config: AppConfig,
    vault_name: str,
    *,
    reprocess: bool = False,
    on_file: callable | None = None,
) -> IngestResult:
    """Run the full ingestion pipeline for a vault.

    Args:
        config: App configuration.
        vault_name: Name of the vault to ingest.
        reprocess: If True, re-extract even for already-indexed documents.
        on_file: Optional callback(filename, status) for progress reporting.
    """
    doc_dir = vault_documents_dir(config, vault_name)
    files = enumerate_documents(doc_dir)

    files_new = 0
    files_skipped = 0
    documents_parsed = 0
    total_extracted = 0
    total_stored = 0
    errors: list[str] = []

    for file_path in files:
        file_hash = content_hash(file_path)

        # Deduplication: skip if content hash already indexed
        existing = document_store.get_document_by_hash(config, vault_name, file_hash)
        if existing and not reprocess:
            files_skipped += 1
            if on_file:
                on_file(file_path.name, "skipped (unchanged)")
            continue

        files_new += 1
        if on_file:
            on_file(file_path.name, "processing")

        # Build and store document record
        doc = _build_document(vault_name, file_path, file_hash)

        # Insert document record first (needed as FK target for results + review queue)
        document_store.insert_document(config, vault_name, doc)

        try:
            # Parse and extract results
            parsed, raw_results = _parse_and_extract(file_path, doc)
            documents_parsed += 1

            # Validate and triage (rejected/flagged → review queue)
            validated = _validate_and_triage(config, vault_name, raw_results)
            total_extracted += len(validated)

            # Index for full-text search
            from longview_health.search.indexer import index_parsed_document
            index_parsed_document(config, vault_name, parsed)

            # Store validated results
            if validated:
                stored = results_store.insert_results(config, vault_name, validated)
                total_stored += stored

            if on_file:
                on_file(file_path.name, f"done ({len(validated)} results)")

        except Exception as e:
            errors.append(f"{file_path.name}: {e}")
            if on_file:
                on_file(file_path.name, f"error: {e}")

    return IngestResult(
        files_found=len(files),
        files_new=files_new,
        files_skipped=files_skipped,
        documents_parsed=documents_parsed,
        results_extracted=total_extracted,
        results_stored=total_stored,
        errors=errors,
    )
