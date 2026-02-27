"""Rescan command -- ingest and process documents in a vault."""

import click

from longview_health.core.config import AppConfig
from longview_health.storage import vault_store


def _config() -> AppConfig:
    config = AppConfig()
    config.ensure_dirs()
    return config


@click.command()
@click.argument("vault")
@click.option("--reprocess", is_flag=True, help="Re-extract even for already-indexed documents.")
def rescan(vault: str, reprocess: bool) -> None:
    """Scan/rescan all documents in a vault.

    Place documents in ~/.longview/vaults/<vault>/documents/ then run this command.
    """
    config = _config()

    if not vault_store.vault_exists(config, vault):
        raise click.ClickException(f"Vault '{vault}' not found.")

    from longview_health.ingest.orchestrator import ingest_vault

    def on_file(filename: str, status: str) -> None:
        click.echo(f"  {filename}: {status}")

    click.echo(f"Scanning vault '{vault}'...")
    result = ingest_vault(config, vault, reprocess=reprocess, on_file=on_file)

    click.echo()
    click.echo(f"Files found:     {result.files_found}")
    click.echo(f"New/changed:     {result.files_new}")
    click.echo(f"Skipped:         {result.files_skipped}")
    click.echo(f"Parsed:          {result.documents_parsed}")
    click.echo(f"Results stored:  {result.results_stored}")

    if result.errors:
        click.echo()
        click.echo(f"Errors ({len(result.errors)}):")
        for err in result.errors:
            click.echo(f"  {err}", err=True)
