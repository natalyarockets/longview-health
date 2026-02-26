"""Integration tests for vault lifecycle: create -> list -> verify -> delete -> verify gone."""

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from longview_health.cli.main import cli
from longview_health.core.config import AppConfig
from longview_health.core.paths import vault_db_path, vault_dir, vault_documents_dir
from longview_health.storage import vault_store
from longview_health.storage.migrations import _get_schema_version
from longview_health.storage.database import connect


@pytest.fixture
def config(tmp_path: Path) -> AppConfig:
    return AppConfig(vault_root=tmp_path / "vaults")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# -- vault_store unit tests --


class TestVaultStore:
    def test_create_vault(self, config: AppConfig) -> None:
        vault = vault_store.create_vault(config, "alice")
        assert vault.name == "alice"
        assert vault_dir(config, "alice").exists()
        assert vault_db_path(config, "alice").exists()
        assert vault_documents_dir(config, "alice").exists()

    def test_create_duplicate_raises(self, config: AppConfig) -> None:
        vault_store.create_vault(config, "alice")
        with pytest.raises(Exception, match="already exists"):
            vault_store.create_vault(config, "alice")

    def test_list_empty(self, config: AppConfig) -> None:
        assert vault_store.list_vaults(config) == []

    def test_list_vaults(self, config: AppConfig) -> None:
        vault_store.create_vault(config, "alice")
        vault_store.create_vault(config, "bob")
        vaults = vault_store.list_vaults(config)
        names = [v.name for v in vaults]
        assert "alice" in names
        assert "bob" in names

    def test_delete_vault(self, config: AppConfig) -> None:
        vault_store.create_vault(config, "alice")
        vault_store.delete_vault(config, "alice")
        assert not vault_dir(config, "alice").exists()

    def test_delete_nonexistent_raises(self, config: AppConfig) -> None:
        with pytest.raises(Exception, match="not found"):
            vault_store.delete_vault(config, "ghost")

    def test_schema_is_migrated(self, config: AppConfig) -> None:
        vault_store.create_vault(config, "alice")
        conn = connect(vault_db_path(config, "alice"))
        try:
            version = _get_schema_version(conn)
            assert version >= 1

            # Verify tables exist
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "documents" in tables
            assert "medical_results" in tables
            assert "review_queue" in tables
        finally:
            conn.close()


# -- CLI integration tests --


class TestVaultCLI:
    def test_list_via_cli(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["vault", "list"])
        assert result.exit_code == 0

    def test_vault_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["vault", "--help"])
        assert result.exit_code == 0
        assert "create" in result.output
        assert "list" in result.output
        assert "delete" in result.output
