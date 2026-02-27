"""Longview Health CLI entry point."""

import click

from longview_health.cli.vault import vault
from longview_health.cli.rescan import rescan
from longview_health.cli.search import search
from longview_health.cli.results import results
from longview_health.cli.trend import trend
from longview_health.cli.export import export
from longview_health.cli.review import review
from longview_health.cli.model import model
from longview_health.cli.settings import settings_group


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Longview Health -- medical document indexing and result trend extraction."""


cli.add_command(vault)
cli.add_command(rescan)
cli.add_command(search)
cli.add_command(results)
cli.add_command(trend)
cli.add_command(export)
cli.add_command(review)
cli.add_command(model)
cli.add_command(settings_group, name="settings")

if __name__ == "__main__":
    cli()
