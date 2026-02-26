# Longview Health -- Project Intelligence

> This file is loaded automatically at the start of every Claude Code session.
> It contains the architectural principles, design contracts, and systems-level
> thinking guidelines that govern all work on this project.

## Project Overview

Longview Health is a CLI-first, local-first tool for indexing personal/family health
documents and extracting structured, trendable data from them. Covers all medical
result types: lab panels, imaging (MRI, CT, X-ray), pathology, diagnostics (EKG, EEG),
vitals, and any other test/finding with a reportable value. Each family member gets
an isolated vault backed by SQLite.

**Current phase:** Pre-implementation. Scaffolding and architecture only.

---

## Systems-Level Thinking Principles

These are the foundational mental models for every design decision.

### 1. Data Flows Downhill -- Never Sideways

Every piece of data in the system has a single, linear path from ingestion to storage.
No module reaches sideways into another module's internals. If module A needs something
from module B, it goes through an explicit contract (function signature, protocol, or
shared domain type). Draw the data flow before writing the code.

```
Document on disk
  -> FileEnumerator (discovers, hashes, deduplicates)
  -> DocumentParser (extracts text + layout structure)
  -> StructuredExtractor (maps structure to domain types)
  -> ValidationEngine (rejects or flags bad extractions)
  -> StorageLayer (persists validated results)
  -> SearchIndex (indexes for retrieval)
```

### 2. Contracts Over Conventions

Every boundary between modules is defined by a Python Protocol or typed dataclass --
never by implicit dict shapes, magic strings, or "just pass the whole object." When
you define a new module, define its input type and output type first, then implement.

### 3. Single Responsibility Is Real

Each module does exactly one thing. If you're writing a function that parses AND
validates, split it. If a class manages files AND talks to SQLite, split it. The cost
of an extra file is near zero; the cost of tangled responsibilities is compounding.

### 4. Accuracy Over Automation

Health data must be correct. Every extraction goes through a validation gate before
it's considered trusted. The system should make it easy to flag, review, and manually
correct results. An unreviewed result is not a trusted result.

### 5. Best Tools First, ML As Tiebreaker

The parsing pipeline uses the best available tool at each stage. Docling is a required
dependency because it produces the most accurate layout/table extraction -- making it
optional would undermine the accuracy-first principle. The pipeline order:

1. Docling (layout-aware parsing, table extraction) -- primary parser
2. Native PDF text extraction -- supplement/fallback for text-heavy documents
3. OCR -- fallback for image-only documents or when Docling can't extract text
4. LLM/VLM -- last resort for ambiguity resolution only, never the primary parser

When an LLM is used, its output is schema-constrained and validation-gated. All tools
run locally -- no data leaves the machine.

### 6. Design for Reprocessing

Documents will be re-ingested as extraction logic improves. Every document is content-
hashed. Extraction results are versioned by extractor version. Re-running `rescan`
on a vault re-processes everything idempotently. No "run once and pray" pipelines.

### 7. Isolation by Default

Vaults are fully isolated. No shared state between vaults. Each vault is its own
SQLite database, its own file index, its own search index. This makes the system
simple to reason about, trivial to back up, and safe for multi-user (family) use.

---

## Architectural Rules

### Module Boundaries

| Module      | Responsibility                             | Depends On         |
|-------------|--------------------------------------------|--------------------|
| `cli/`      | Parse commands, call core services         | core, all engines  |
| `core/`     | Config, paths, shared types, protocols     | nothing            |
| `domain/`   | Typed data models and schemas              | nothing            |
| `ingest/`   | File discovery, hashing, dedup, orchestration | core, domain    |
| `extract/`  | Document parsing + structured extraction   | core, domain       |
| `validate/` | Validation rules, confidence scoring       | core, domain       |
| `storage/`  | SQLite read/write, migrations              | core, domain       |
| `search/`   | FTS5 indexing and query                    | core, domain, storage |
| `trends/`   | Chronological aggregation and output       | core, domain, storage |
| `review/`   | Manual review queue and correction flow    | core, domain, storage |

**Dependency direction:** `cli -> engines -> core/domain`. Never reverse.

### Data Model Principles

- All domain types live in `domain/` and are immutable dataclasses or Pydantic models.
- IDs are deterministic where possible (content hash for documents, composite keys for results).
- Timestamps are always UTC ISO-8601.
- Every extracted result carries: source document ID, result category (lab, imaging, pathology, etc.), extractor version, confidence score, validation status.

### Storage Principles

- One SQLite database per vault. No shared databases.
- Schema migrations are explicit and versioned (not auto-generated).
- All writes go through the storage layer -- no raw SQL outside `storage/`.
- FTS5 virtual tables for search. Kept in sync via triggers or explicit rebuild.

### Error Handling

- Fail loudly at module boundaries. Don't swallow errors inside a pipeline stage.
- Use typed result objects (`Result[T, Error]` pattern) for operations that can fail expectedly.
- Unexpected errors propagate up and are caught at the CLI layer with clear messages.
- Never silently skip a document. If parsing fails, it goes into the review queue.

### Testing Strategy

- Unit tests per module against its contract (input type -> output type).
- Integration tests for the full pipeline (document -> stored result).
- Fixture-based: real sample documents (anonymized) as test inputs.
- No mocking of domain types. Mock only external I/O (filesystem, LLM calls).

---

## Code Style and Conventions

- **Python 3.11+** with full type annotations on all public functions.
- **Pydantic v2** for domain models that need validation/serialization.
- **dataclasses** for simple internal types that don't need Pydantic overhead.
- **Protocol classes** for module contracts (dependency inversion).
- **Click** for CLI framework.
- **No classes where functions suffice.** Don't wrap a single function in a class.
- **Imports:** absolute imports only (`from longview_health.domain.models import ...`).
- **Naming:** snake_case everywhere. No abbreviations except universally understood ones (id, db, fts).
- **No global mutable state.** Config is loaded once and passed explicitly.

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.11+ | Iteration speed, Docling/ML ecosystem |
| CLI framework | Click | Mature, composable, good testing support |
| Storage | SQLite (one per vault) | Local-first, zero-config, portable |
| Search | FTS5 | Built into SQLite, no external dependency |
| Document parsing | Docling (required) | Best layout/table preservation, accuracy-first principle |
| Domain models | Pydantic v2 | Validation, serialization, schema export |
| Testing | pytest | Standard, fixture-friendly |
| Package management | uv | Fast, reliable, lockfile support |

---

## What NOT To Do

- Do not add a web server, REST API, or GUI in V1.
- Do not add background services, watchers, or daemons.
- Do not use an ORM. Raw SQL through the storage layer is fine for SQLite.
- Do not add "plugin" or "extension" systems. Keep it monolithic and simple.
- Do not reach for async. The CLI is synchronous. Docling and SQLite are synchronous.
- Do not store extracted data as JSON blobs in SQLite. Use proper relational tables.
- Do not skip the validation gate for any extraction path.

---

## File References

- PRD: `docs/prd-mvp.md`
- Implementation Plan: `docs/PLAN.md`
