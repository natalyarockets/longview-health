"""Vault management commands."""

import click

from longview_health.core.config import AppConfig
from longview_health.core.errors import VaultExistsError, VaultNotFoundError
from longview_health.storage import vault_store


def _config() -> AppConfig:
    config = AppConfig()
    config.ensure_dirs()
    return config


@click.group()
def vault() -> None:
    """Create, list, and delete vaults."""


@vault.command()
@click.argument("name")
@click.option(
    "--path",
    "source_path",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    default=None,
    help="Path to an existing folder of medical documents.",
)
def create(name: str, source_path: str | None) -> None:
    """Create a new vault for a family member.

    Optionally point it at an existing folder of medical documents with --path.
    """
    from pathlib import Path

    try:
        sp = Path(source_path) if source_path else None
        v = vault_store.create_vault(_config(), name, source_path=sp)
        click.echo(f"Created vault: {v.name}")
        if sp:
            click.echo(f"  Documents: {sp}")
        click.echo(f"\nNext: longview rescan {v.name}")
    except VaultExistsError:
        click.echo(f"Error: vault '{name}' already exists.", err=True)
        raise SystemExit(1)


@vault.command("list")
def list_vaults() -> None:
    """List all vaults."""
    config = _config()
    vaults = vault_store.list_vaults(config)
    if not vaults:
        click.echo("No vaults found.")
        return
    from longview_health.core.paths import vault_documents_dir
    for v in vaults:
        doc_dir = vault_documents_dir(config, v.name)
        click.echo(f"  {v.name}  (created {v.created_at:%Y-%m-%d %H:%M})")
        click.echo(f"    documents: {doc_dir}")


@vault.command()
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to delete this vault?")
def delete(name: str) -> None:
    """Delete a vault and all its data."""
    try:
        vault_store.delete_vault(_config(), name)
        click.echo(f"Deleted vault: {name}")
    except VaultNotFoundError:
        click.echo(f"Error: vault '{name}' not found.", err=True)
        raise SystemExit(1)
