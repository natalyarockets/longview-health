"""Vault CRUD operations.

Manages vault creation, listing, and deletion at the filesystem + database level.
"""

import shutil
from datetime import datetime, timezone
from pathlib import Path

from longview_health.core.config import AppConfig
from longview_health.core.errors import VaultExistsError, VaultNotFoundError
from longview_health.core.paths import vault_db_path, vault_dir, vault_documents_dir
from longview_health.domain.models import Vault
from longview_health.storage.database import connect
from longview_health.storage.migrations import run_migrations


def create_vault(config: AppConfig, name: str) -> Vault:
    """Create a new vault with its directory structure and database."""
    vdir = vault_dir(config, name)
    if vdir.exists():
        raise VaultExistsError(name)

    # Create directory structure
    vdir.mkdir(parents=True)
    vault_documents_dir(config, name).mkdir()

    # Initialize database with schema
    db_path = vault_db_path(config, name)
    conn = connect(db_path)
    try:
        run_migrations(conn)
    finally:
        conn.close()

    return Vault(name=name, created_at=datetime.now(timezone.utc))


def list_vaults(config: AppConfig) -> list[Vault]:
    """List all existing vaults."""
    if not config.vault_root.exists():
        return []

    vaults = []
    for entry in sorted(config.vault_root.iterdir()):
        if entry.is_dir() and (entry / "vault.db").exists():
            stat = entry.stat()
            created = datetime.fromtimestamp(stat.st_birthtime, tz=timezone.utc)
            vaults.append(Vault(name=entry.name, created_at=created))
    return vaults


def delete_vault(config: AppConfig, name: str) -> None:
    """Delete a vault and all its data."""
    vdir = vault_dir(config, name)
    if not vdir.exists():
        raise VaultNotFoundError(name)
    shutil.rmtree(vdir)


def vault_exists(config: AppConfig, name: str) -> bool:
    """Check if a vault exists."""
    return vault_dir(config, name).exists()
