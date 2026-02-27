"""Trend command -- show longitudinal trends for a test/finding."""

import click

from longview_health.core.config import AppConfig
from longview_health.storage import results_store, vault_store
from longview_health.trends.engine import build_trend_series


def _config() -> AppConfig:
    config = AppConfig()
    config.ensure_dirs()
    return config


@click.command()
@click.argument("vault")
@click.argument("test")
def trend(vault: str, test: str) -> None:
    """Show trend for a specific test/finding over time."""
    config = _config()

    if not vault_store.vault_exists(config, vault):
        raise click.ClickException(f"Vault '{vault}' not found.")

    rows = results_store.query_results(config, vault, test_name=test)

    if not rows:
        click.echo(f"No results found for '{test}'.")
        return

    series = build_trend_series(test, rows)

    unit_str = f" ({series.unit})" if series.unit else ""
    click.echo(f"Trend: {series.test_name}{unit_str}")
    click.echo(f"Category: {series.category.value}")
    click.echo(f"Points: {len(series.points)}")
    click.echo()

    header = f"{'Date':<12} {'Value':<12} {'Delta':<15} {'Flag':<10}"
    click.echo(header)
    click.echo("-" * len(header))

    for point in series.points:
        r = point.result
        rv = r.result_value

        delta_str = ""
        if point.delta is not None:
            sign = "+" if point.delta > 0 else ""
            delta_str = f"{sign}{point.delta}"
            if point.delta_percent is not None:
                delta_str += f" ({sign}{point.delta_percent}%)"

        flag = ""
        if rv.is_abnormal is True:
            flag = "ABNORMAL"
        elif rv.is_abnormal is False:
            flag = "normal"

        click.echo(
            f"{str(r.result_date):<12} "
            f"{rv.value:<12} "
            f"{delta_str:<15} "
            f"{flag:<10}"
        )
