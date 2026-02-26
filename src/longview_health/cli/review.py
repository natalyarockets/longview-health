"""Review command -- review flagged/uncertain extractions."""

import click


@click.command()
@click.argument("vault")
def review(vault: str) -> None:
    """Review and correct flagged extractions in a vault."""
    click.echo(f"Reviewing flagged items in vault: {vault}")
