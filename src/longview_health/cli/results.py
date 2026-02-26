"""Results command -- query extracted medical results."""

import click


@click.command()
@click.argument("vault")
@click.option("--test", default=None, help="Filter by test/finding name.")
@click.option("--category", default=None, help="Filter by result category (lab, imaging, pathology, etc.).")
def results(vault: str, test: str | None, category: str | None) -> None:
    """View extracted medical results in a vault."""
    click.echo(f"Results for vault: {vault}")
    if test:
        click.echo(f"  filter test: {test}")
    if category:
        click.echo(f"  filter category: {category}")
