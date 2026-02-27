"""Deterministic path resolution for vaults and their contents."""

from pathlib import Path

from longview_health.core.config import AppConfig


def vault_dir(config: AppConfig, vault_name: str) -> Path:
    """Root directory for a vault."""
    return config.vault_root / vault_name


def vault_db_path(config: AppConfig, vault_name: str) -> Path:
    """SQLite database file for a vault."""
    return vault_dir(config, vault_name) / "vault.db"


def _source_path_file(config: AppConfig, vault_name: str) -> Path:
    """Path to the file that stores the external document source directory."""
    return vault_dir(config, vault_name) / "source_path"


def vault_documents_dir(config: AppConfig, vault_name: str) -> Path:
    """Directory where source documents live.

    If the vault was created with --path, returns that external directory.
    Otherwise returns the default <vault>/documents/ subdirectory.
    """
    source_file = _source_path_file(config, vault_name)
    if source_file.exists():
        return Path(source_file.read_text().strip())
    return vault_dir(config, vault_name) / "documents"
