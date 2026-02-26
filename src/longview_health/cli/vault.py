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
def create(name: str) -> None:
    """Create a new vault for a family member."""
    try:
        v = vault_store.create_vault(_config(), name)
        click.echo(f"Created vault: {v.name}")
    except VaultExistsError:
        click.echo(f"Error: vault '{name}' already exists.", err=True)
        raise SystemExit(1)


@vault.command("list")
def list_vaults() -> None:
    """List all vaults."""
    vaults = vault_store.list_vaults(_config())
    if not vaults:
        click.echo("No vaults found.")
        return
    for v in vaults:
        click.echo(f"  {v.name}  (created {v.created_at:%Y-%m-%d %H:%M})")


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
