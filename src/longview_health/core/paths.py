"""Deterministic path resolution for vaults and their contents."""

from pathlib import Path

from longview_health.core.config import AppConfig


def vault_dir(config: AppConfig, vault_name: str) -> Path:
    """Root directory for a vault."""
    return config.vault_root / vault_name


def vault_db_path(config: AppConfig, vault_name: str) -> Path:
    """SQLite database file for a vault."""
    return vault_dir(config, vault_name) / "vault.db"


def vault_documents_dir(config: AppConfig, vault_name: str) -> Path:
    """Directory where source documents are stored/linked for a vault."""
    return vault_dir(config, vault_name) / "documents"
