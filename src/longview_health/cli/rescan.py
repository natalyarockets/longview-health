"""Rescan command -- re-ingest and reprocess documents in a vault."""

import click


@click.command()
@click.argument("vault")
def rescan(vault: str) -> None:
    """Scan/rescan all documents in a vault."""
    click.echo(f"Rescanning vault: {vault}")
