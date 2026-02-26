"""SQLite connection management.

One database per vault. Connections are created on demand and
configured with WAL mode and foreign keys.
"""

import sqlite3
from pathlib import Path

from longview_health.core.config import AppConfig
from longview_health.core.paths import vault_db_path


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a configured SQLite connection."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def connect_vault(config: AppConfig, vault_name: str) -> sqlite3.Connection:
    """Open a connection to a vault's database."""
    path = vault_db_path(config, vault_name)
    if not path.exists():
        raise FileNotFoundError(f"Vault database not found: {path}")
    return connect(path)
