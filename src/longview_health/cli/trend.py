"""Trend command -- show longitudinal trends for a test/finding."""

import click


@click.command()
@click.argument("vault")
@click.argument("test")
def trend(vault: str, test: str) -> None:
    """Show trend for a specific test/finding over time."""
    click.echo(f"Trending '{test}' in vault: {vault}")
