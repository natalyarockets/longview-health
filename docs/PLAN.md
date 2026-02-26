# Longview Health -- Implementation Plan

> Phased build plan for the MVP. Each phase produces working, testable code.
> Phases are sequential -- each builds on the previous.

---

## Phase 0: Project Scaffolding

**Goal:** Runnable project skeleton with `longview --help` working.

- [ ] Initialize Python project with `uv` (pyproject.toml, lockfile)
- [ ] Create package structure: `src/longview_health/` with all subpackages
- [ ] Set up Click CLI entry point with stub commands
- [ ] Configure pytest with `tests/` directory mirroring `src/` structure
- [ ] Add `.gitignore`, `py.typed` marker
- [ ] Verify: `longview --help` prints command list, `pytest` runs with 0 tests

**Deliverable:** `longview --help` works. All subpackages importable.

---

## Phase 1: Core + Domain + Vault Management

**Goal:** Create and manage isolated vaults. Define all domain types.

### 1a: Core infrastructure
- [ ] `core/config.py` -- app-level config (vault root path, defaults)
- [ ] `core/paths.py` -- deterministic path resolution for vaults
- [ ] `core/protocols.py` -- shared Protocol definitions for module contracts
- [ ] `core/errors.py` -- base error types

### 1b: Domain models
- [ ] `domain/models.py` -- `Vault`, `Document`, `MedicalResult`, `ResultValue`, `ReviewItem`
- [ ] `domain/enums.py` -- `ValidationStatus`, `DocumentType`, `ResultCategory`, `Confidence`
- [ ] `domain/identifiers.py` -- content hash functions, composite key builders

### 1c: Storage layer (schema only)
- [ ] `storage/database.py` -- SQLite connection management per vault
- [ ] `storage/migrations.py` -- versioned schema creation (tables, FTS5, indexes)
- [ ] `storage/vault_store.py` -- CRUD for vault metadata

### 1d: Vault CLI commands
- [ ] `cli/vault.py` -- `longview vault create|list|delete`
- [ ] Integration test: create vault -> list -> verify SQLite exists -> delete -> verify gone

**Deliverable:** Can create, list, and delete vaults from the CLI. Each vault has its own SQLite database with the full schema.

---

## Phase 2: File Ingestion Pipeline

**Goal:** Discover files in a vault's document directory, hash them, track them.

### 2a: File enumeration
- [ ] `ingest/enumerator.py` -- walk directory, filter supported types (PDF, PNG, JPG, TIFF)
- [ ] `ingest/hasher.py` -- SHA-256 content hashing for deduplication
- [ ] `domain/models.py` -- extend `Document` with file metadata fields

### 2b: Document storage
- [ ] `storage/document_store.py` -- insert/query/update documents
- [ ] Deduplication logic: skip files with unchanged content hash

### 2c: Rescan orchestration
- [ ] `ingest/orchestrator.py` -- coordinate enumerate -> hash -> store -> (extract placeholder)
- [ ] `cli/rescan.py` -- `longview rescan <vault>`
- [ ] Integration test: add files to vault dir -> rescan -> verify documents in DB

**Deliverable:** `longview rescan <vault>` discovers and indexes files. Re-running is idempotent.

---

## Phase 3: Document Parsing

**Goal:** Extract text and structural layout from documents.

### 3a: Parser abstraction
- [ ] `extract/protocols.py` -- `DocumentParser` protocol (input: file path, output: `ParsedDocument`)
- [ ] `domain/models.py` -- `ParsedDocument` type (text blocks, tables, metadata)

### 3b: Docling parser (primary)
- [ ] `extract/docling_parser.py` -- Docling-based layout + table extraction
- [ ] Map Docling output to `ParsedDocument` domain type
- [ ] Docling is a required dependency -- accuracy-first means using the best tool

### 3c: Native PDF parser (supplement/fallback)
- [ ] `extract/pdf_parser.py` -- direct text extraction via `pdfplumber` or `pymupdf`
- [ ] Used when Docling fails or as supplementary text source

### 3d: OCR fallback
- [ ] `extract/ocr_parser.py` -- Tesseract or similar for image-only documents
- [ ] Integrate into parser chain as fallback

### 3e: Parser orchestration
- [ ] `extract/parser_chain.py` -- Docling first, then native PDF, then OCR
- [ ] Record which parser succeeded per document
- [ ] Parse quality scoring to decide if fallback is needed

**Deliverable:** Any supported document produces a structured `ParsedDocument`.

---

## Phase 4: Structured Extraction

**Goal:** Map parsed document content to typed medical results (labs, imaging, pathology, diagnostics).

### 4a: Extraction framework
- [ ] `extract/protocols.py` -- `StructuredExtractor` protocol
- [ ] `domain/models.py` -- refine `MedicalResult`, `ResultValue` with units, reference ranges, result categories

### 4b: Table-based extractor
- [ ] `extract/table_extractor.py` -- extract results from tabular data (lab panels, structured reports)
- [ ] Pattern matching for common report formats (CBC, CMP, lipid panel, imaging findings, etc.)

### 4c: Text-based extractor
- [ ] `extract/text_extractor.py` -- regex/pattern extraction for narrative-format results (radiology reports, pathology notes)

### 4d: LLM/VLM extractor (last resort)
- [ ] `extract/llm_extractor.py` -- schema-constrained LLM/VLM call for ambiguous documents
- [ ] Strict output schema, confidence scoring, never auto-trusted

### 4e: Extraction orchestration
- [ ] `extract/extraction_chain.py` -- try extractors, merge results, tag source method and result category
- [ ] Wire into rescan pipeline after parsing stage

**Deliverable:** Parsed documents produce typed `MedicalResult`/`ResultValue` objects with provenance and category.

---

## Phase 5: Validation Engine

**Goal:** Gate all extracted data through validation before it enters trusted storage.

- [ ] `validate/rules.py` -- validation rule definitions:
  - Value in physiologically plausible range
  - Units are recognized and consistent
  - Date is parseable and not in the future
  - Required fields present (test name, value, date)
- [ ] `validate/engine.py` -- run rules, produce `ValidationResult` (pass/flag/reject)
- [ ] `validate/confidence.py` -- confidence scoring based on extraction method + rule results
- [ ] Wire into pipeline: extraction -> validation -> storage (if passed) or review queue (if flagged)

**Deliverable:** No extraction result enters trusted storage without passing validation.

---

## Phase 6: Search

**Goal:** Full-text search across documents in a vault.

- [ ] `search/indexer.py` -- populate FTS5 virtual table from parsed document text
- [ ] `search/query.py` -- search query parsing and execution
- [ ] `storage/search_store.py` -- FTS5 table management
- [ ] `cli/search.py` -- `longview search <vault> <query>`
- [ ] Integration test: ingest documents -> search -> verify results

**Deliverable:** `longview search <vault> "cholesterol"` returns matching documents with snippets.

---

## Phase 7: Results + Trends

**Goal:** Query and trend medical results (labs, imaging findings, any quantifiable value) over time.

- [ ] `storage/results_store.py` -- query results by test/finding name, category, date range
- [ ] `trends/engine.py` -- chronological aggregation, delta calculation
- [ ] `trends/formatters.py` -- table and ASCII chart output for terminal
- [ ] `trends/export.py` -- export trends to PDF with:
  - Each result hyperlinked to its source document
  - Parser provenance shown per result (which parser + extractor produced it)
  - Grouped by category (lab, imaging, pathology, etc.)
- [ ] `cli/results.py` -- `longview results <vault> [--test <name>] [--category <cat>]`
- [ ] `cli/trend.py` -- `longview trend <vault> <test>`
- [ ] `cli/export.py` -- `longview export <vault> [--format pdf]`
- [ ] Integration test: multiple documents -> extract -> trend output + export

**Deliverable:** `longview results <vault>` shows all results across categories. `longview trend <vault> "HDL"` shows history. `longview export <vault>` produces a PDF trends report where each result links to its source document.

---

## Phase 8: Review Queue

**Goal:** Surface flagged/failed extractions for manual correction.

- [ ] `review/queue.py` -- list items needing review, accept/reject/edit
- [ ] `storage/review_store.py` -- review queue persistence
- [ ] `cli/review.py` -- `longview review <vault>` -- interactive review flow
- [ ] Edited results re-enter storage as manually verified (highest confidence)

**Deliverable:** `longview review <vault>` shows flagged items, allows correction.

---

## Phase Dependency Graph

```
Phase 0 (scaffold)
  |
Phase 1 (core + domain + vaults)
  |
Phase 2 (file ingestion)
  |
Phase 3 (document parsing)
  |
Phase 4 (structured extraction)
  |
Phase 5 (validation)
  / \
Phase 6    Phase 7      Phase 8
(search)   (results/    (review)
            trends)
```

Phases 6, 7, and 8 can be developed in parallel once Phase 5 is complete.

---

## Definition of Done (Per Phase)

1. All new code has type annotations.
2. Unit tests pass for all new modules.
3. Integration test demonstrates the phase's deliverable.
4. No regressions in previous phase tests.
5. CLI commands work end-to-end for the new functionality.
