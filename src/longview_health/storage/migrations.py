"""Versioned schema migrations for vault databases.

Each migration is a function that takes a connection and applies DDL.
Migrations are tracked in a _schema_version table and run in order.
"""

import sqlite3

MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "Initial schema",
        """
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            vault_name TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            document_type TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            ingested_at TEXT NOT NULL,
            page_count INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_documents_content_hash
            ON documents(content_hash);

        CREATE TABLE IF NOT EXISTS medical_results (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(id),
            test_name TEXT NOT NULL,
            value TEXT NOT NULL,
            unit TEXT,
            reference_low TEXT,
            reference_high TEXT,
            is_abnormal INTEGER,
            result_date TEXT NOT NULL,
            category TEXT NOT NULL,
            extractor_version TEXT NOT NULL,
            confidence TEXT NOT NULL,
            validation_status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );

        CREATE INDEX IF NOT EXISTS idx_results_test_name
            ON medical_results(test_name);
        CREATE INDEX IF NOT EXISTS idx_results_date
            ON medical_results(result_date);
        CREATE INDEX IF NOT EXISTS idx_results_category
            ON medical_results(category);
        CREATE INDEX IF NOT EXISTS idx_results_document
            ON medical_results(document_id);

        CREATE TABLE IF NOT EXISTS review_queue (
            id TEXT PRIMARY KEY,
            result_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            test_name TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            resolved INTEGER NOT NULL DEFAULT 0,
            resolved_at TEXT,
            FOREIGN KEY (result_id) REFERENCES medical_results(id),
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );

        CREATE INDEX IF NOT EXISTS idx_review_unresolved
            ON review_queue(resolved) WHERE resolved = 0;

        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
            USING fts5(document_id, content, tokenize='porter');
        """,
    ),
]


def _get_schema_version(conn: sqlite3.Connection) -> int:
    """Get the current schema version, or 0 if uninitialized."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _schema_version (version INTEGER NOT NULL)"
    )
    row = conn.execute("SELECT MAX(version) FROM _schema_version").fetchone()
    return row[0] or 0


def run_migrations(conn: sqlite3.Connection) -> int:
    """Run all pending migrations. Returns the final schema version."""
    current = _get_schema_version(conn)

    for version, description, sql in MIGRATIONS:
        if version <= current:
            continue
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO _schema_version (version) VALUES (?)", (version,)
        )
        conn.commit()

    return _get_schema_version(conn)
