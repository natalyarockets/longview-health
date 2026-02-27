# Longview Health

CLI-first, local-first health document indexing and medical result trend extraction.

Longview ingests your medical documents (lab reports, imaging results, pathology, diagnostics, and more), extracts structured data from them, validates the extractions, and lets you search and trend your health data over time. Each family member gets an isolated vault.

## Status

**Active development.** Core parsing and extraction pipeline working.

## Extraction Pipeline

```
Document (PDF/image)
  -> Docling        (layout analysis: bounding boxes, element classification, OCR)
  -> Region Grouper (spatial clustering of elements into logical regions)
  -> Per-region LLM (focused Ollama calls per region -> MedicalResult JSON)
  -> Validation     (gate before trusted storage)
  -> SQLite         (per-vault relational storage)
```

Docling handles spatial layout (where things are on the page, element types, bounding boxes). A local LLM (via Ollama) handles meaning -- each document region gets its own focused extraction call with a small, targeted prompt. No regex, no brittle column-counting heuristics. All processing runs locally -- no data leaves your machine.

## Features (MVP)

- **Vault management** -- isolated per-person data stores backed by SQLite
- **Document ingestion** -- PDF, PNG, JPG, TIFF with content-hash deduplication
- **Smart parsing** -- Docling layout analysis with bounding boxes and element classification
- **Region-based LLM extraction** -- focused per-region Ollama calls for accurate extraction
- **Full provenance** -- every result tracks which parser and extractor produced it
- **Validation gate** -- every extraction is validated before entering trusted storage
- **Full-text search** -- FTS5-powered search across all documents in a vault
- **Result trends** -- query and chart test/finding values over time, export to PDF with source document links
- **Review queue** -- flag and manually correct uncertain extractions

## CLI Usage

```
longview vault create|list|delete
longview rescan <vault>
longview search <vault> <query>
longview results <vault> [--test <name>]
longview trend <vault> <test>
longview export <vault> [--format pdf]
longview review <vault>
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| CLI | Click |
| Document parsing | Docling (required) |
| Structured extraction | Local LLM via Ollama (per-region focused calls) |
| Storage | SQLite (one DB per vault) |
| Search | FTS5 |
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
  extract/      # Docling parsing, region grouping, LLM extraction
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
uv run python -m pytest

# start Ollama for LLM extraction
ollama serve
ollama pull qwen2.5-vl:7b
```

## Design Principles

See [`CLAUDE.md`](CLAUDE.md) for the full set of architectural principles and systems-level thinking guidelines that govern this project. Key highlights:

- **Data flows downhill** -- linear pipeline, no sideways dependencies
- **Contracts over conventions** -- typed interfaces at every module boundary
- **Accuracy over automation** -- validation gate, review queue, manual override
- **Best tools first** -- Docling for spatial layout, LLM for meaning, all local
- **Design for reprocessing** -- content-hashed, versioned, idempotent
- **Isolation by default** -- fully independent vaults, zero shared state
