"""Results command -- query extracted medical results."""

import click

from longview_health.core.config import AppConfig
from longview_health.domain.enums import ResultCategory
from longview_health.storage import results_store, vault_store


def _config() -> AppConfig:
    config = AppConfig()
    config.ensure_dirs()
    return config


@click.command()
@click.argument("vault")
@click.option("--test", default=None, help="Filter by test/finding name.")
@click.option(
    "--category",
    default=None,
    help="Filter by result category (lab, imaging, pathology, etc.).",
)
def results(vault: str, test: str | None, category: str | None) -> None:
    """View extracted medical results in a vault."""
    config = _config()

    if not vault_store.vault_exists(config, vault):
        raise click.ClickException(f"Vault '{vault}' not found.")

    cat = ResultCategory(category) if category else None
    rows = results_store.query_results(config, vault, test_name=test, category=cat)

    if not rows:
        click.echo("No results found.")
        return

    # Print aligned columns: Date | Test | Value | Unit | Ref Range | Flag | Category
    header = f"{'Date':<12} {'Test':<25} {'Value':<12} {'Unit':<10} {'Ref Range':<15} {'Flag':<10} {'Category':<10}"
    click.echo(header)
    click.echo("-" * len(header))

    for r in rows:
        rv = r.result_value
        ref = ""
        if rv.reference_low and rv.reference_high:
            ref = f"{rv.reference_low}-{rv.reference_high}"
        elif rv.reference_low:
            ref = f">={rv.reference_low}"
        elif rv.reference_high:
            ref = f"<={rv.reference_high}"

        flag = ""
        if rv.is_abnormal is True:
            flag = "ABNORMAL"
        elif rv.is_abnormal is False:
            flag = "normal"

        click.echo(
            f"{str(r.result_date):<12} "
            f"{r.test_name:<25} "
            f"{rv.value:<12} "
            f"{(rv.unit or ''):<10} "
            f"{ref:<15} "
            f"{flag:<10} "
            f"{r.category.value:<10}"
        )

    click.echo(f"\n{len(rows)} result(s)")
