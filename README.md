# Longview Health

CLI-first, local-first health document indexing and medical result trend extraction.

Longview ingests your medical documents (lab reports, imaging results, pathology, diagnostics, and more), extracts structured data from them, validates the extractions, and lets you search and trend your health data over time. Each family member gets an isolated vault.

## Status

**Pre-implementation.** Architecture and planning phase.

## Features (MVP)

- **Vault management** -- isolated per-person data stores backed by SQLite
- **Document ingestion** -- PDF, PNG, JPG, TIFF with content-hash deduplication
- **Smart parsing** -- Docling-powered layout/table extraction (required), with OCR and LLM fallbacks
- **Structured extraction** -- typed medical results (labs, imaging, pathology, diagnostics) with units, reference ranges, dates
- **Validation gate** -- every extraction is validated before entering trusted storage
- **Full-text search** -- FTS5-powered search across all documents in a vault
- **Result trends** -- query and chart test/finding values over time, export to markdown
- **Review queue** -- flag and manually correct uncertain extractions

## CLI Usage

```
longview vault create|list|delete
longview rescan <vault>
longview search <vault> <query>
longview results <vault> [--test <name>]
longview trend <vault> <test>
longview export <vault> [--format md]
longview review <vault>
```

## Architecture

```
CLI (Click)
  -> VaultManager         (create/list/delete isolated vaults)
  -> IngestionEngine      (discover, hash, deduplicate files)
     -> DocumentParser    (Docling-first layout + table extraction)
     -> StructuredExtractor (map parsed content to typed results)
     -> ValidationEngine  (reject or flag bad extractions)
  -> StorageLayer         (SQLite per vault, relational tables)
  -> SearchIndex          (FTS5 full-text search)
  -> TrendEngine          (chronological result/finding aggregation)
  -> ReviewQueue          (manual correction for flagged items)
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| CLI | Click |
| Storage | SQLite (one DB per vault) |
| Search | FTS5 |
| Document parsing | Docling, pdfplumber, Tesseract |
| Domain models | Pydantic v2 |
| Testing | pytest |
| Package management | uv |

## Project Structure

```
src/longview_health/
  cli/          # command interface
  core/         # config, paths, contracts
  domain/       # typed models and schemas
  ingest/       # file discovery, hashing, orchestration
  extract/      # document parsing + structured extraction
  validate/     # validation gate
  storage/      # SQLite persistence
  search/       # FTS5 indexing and query
  trends/       # chronological trend outputs
  review/       # manual correction queue

docs/
  prd-mvp.md   # product requirements
  PLAN.md       # phased implementation plan

CLAUDE.md       # architecture principles (auto-loaded per session)
```

## Development

```bash
# install dependencies
uv sync

# run CLI
uv run longview --help

# run tests
uv run pytest
```

## Design Principles

See [`CLAUDE.md`](CLAUDE.md) for the full set of architectural principles and systems-level thinking guidelines that govern this project. Key highlights:

- **Data flows downhill** -- linear pipeline, no sideways dependencies
- **Contracts over conventions** -- typed interfaces at every module boundary
- **Accuracy over automation** -- validation gate, review queue, manual override
- **Determinism first** -- LLM/VLM only as a last resort for ambiguity
- **Design for reprocessing** -- content-hashed, versioned, idempotent
- **Isolation by default** -- fully independent vaults, zero shared state
