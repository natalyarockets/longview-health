"""Search command -- full-text search across documents in a vault."""

import click


@click.command()
@click.argument("vault")
@click.argument("query")
def search(vault: str, query: str) -> None:
    """Search documents in a vault."""
    click.echo(f"Searching vault '{vault}' for: {query}")
