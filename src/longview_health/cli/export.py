"""Export command -- export trends to portable formats."""

import click


@click.command()
@click.argument("vault")
@click.option("--format", "fmt", default="md", type=click.Choice(["md"]), help="Export format.")
def export(vault: str, fmt: str) -> None:
    """Export vault trends to a file."""
    click.echo(f"Exporting vault '{vault}' as {fmt}")
