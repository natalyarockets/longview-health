# Longview Health -- MVP Product Requirements Document

> Archived from the original project brief. This is the source-of-truth requirements document for V1.

## Vision

CLI-first, local-first health document indexing and medical result/finding trend extraction.

Built to prioritize **correctness, traceability, and clean architecture** before UX. The MVP is a `longview` CLI that manages separate family member vaults, ingests medical documents, extracts structured results, validates them, and produces searchable/trendable outputs.

## Core Standards (Non-Negotiable)

- Build from thoughtful primitives with single responsibilities.
- No redundant layers, duplicated parsing logic, or overlapping data models.
- Keep code and data flow explicit end-to-end.
- Prefer simple modules with clear contracts over clever abstractions.
- Design for scale now (multi-vault, reprocessing, versioned extraction) without overbuilding V1.
- Accuracy beats automation: manual `rescan`, validation gate, review queue.
- Local-first and deterministic: models are helpers, not sources of truth.

## MVP Scope (CLI-First)

- `longview vault create|list|delete`
- `longview rescan <vault>`
- `longview search <vault> ...`
- `longview results <vault> [--test ...]`
- `longview trend <vault> <test>`
- `longview export <vault> [--format md]`
- `longview review <vault>`

No watcher, no daemon, no background service.

## Architecture (V1)

```text
CLI
  -> VaultManager
  -> IngestionEngine
     -> FileEnumerator
     -> DocumentParser (Docling-first layout/table extraction)
     -> StructuredExtractor
     -> ValidationEngine
     -> StorageLayer (SQLite)
     -> SearchIndex (FTS5)
  -> TrendEngine
  -> ReviewQueue
```

## Why Docling Is In The Flow

Docling is used in the document parsing stage to preserve layout and table structure from PDFs/images before structured result extraction. This improves accuracy for reports where table geometry and headers matter.

Planned parser priority:

1. Docling layout/table extraction (primary -- required dependency)
2. Native PDF text extraction (supplement/fallback)
3. OCR fallback when text/layer quality is insufficient
4. LLM/VLM only for ambiguity resolution (strict schema output)

## Repository Layout

```text
src/longview_health/
  cli/          # command interface
  core/         # config, paths, contracts
  domain/       # typed models / schemas
  ingest/       # scan + hash + orchestration
  extract/      # document parse + structured extraction (Docling hook)
  validate/     # hard validation gate
  storage/      # SQLite persistence
  search/       # FTS/search contracts
  trends/       # chronological trend outputs
  review/       # manual correction queue

docs/
  prd-mvp.md
```

## Technical Decisions

- Python for iteration speed in V1.
- SQLite is the source of truth per vault.
- FTS5 for local search.
- Docling integration is a first-class parser primitive, not a bolt-on script.
- Keep extraction output schema-stable and versioned.
