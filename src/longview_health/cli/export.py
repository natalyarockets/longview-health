"""Export command -- export trends to portable formats."""

from datetime import date

import click

from longview_health.core.config import AppConfig
from longview_health.core.errors import VaultNotFoundError
from longview_health.domain.enums import ResultCategory
from longview_health.storage import results_store, vault_store
from longview_health.trends.engine import build_trend_report
from longview_health.trends.export import export_pdf


def _config() -> AppConfig:
    config = AppConfig()
    config.ensure_dirs()
    return config


@click.command()
@click.argument("vault")
@click.option(
    "--format", "fmt", default="pdf", type=click.Choice(["pdf"]), help="Export format."
)
@click.option("--output", "output_path", default=None, help="Output file path.")
@click.option("--category", default=None, help="Filter by result category.")
@click.option("--test", default=None, help="Filter by test name.")
def export(
    vault: str,
    fmt: str,
    output_path: str | None,
    category: str | None,
    test: str | None,
) -> None:
    """Export vault trends to a PDF report."""
    config = _config()

    if not vault_store.vault_exists(config, vault):
        raise click.ClickException(f"Vault '{vault}' not found.")

    cat = ResultCategory(category) if category else None
    all_results = results_store.query_results(
        config, vault, test_name=test, category=cat
    )

    if not all_results:
        click.echo("No results found. Nothing to export.")
        return

    report = build_trend_report(vault, all_results)

    # Resolve document names for provenance
    doc_ids = list({r.document_id for r in all_results})
    doc_names = results_store.get_document_names(config, vault, doc_ids)

    if output_path is None:
        from longview_health.core.paths import vault_documents_dir
        doc_dir = vault_documents_dir(config, vault)
        output_path = str(doc_dir / f"{vault}-trends-{date.today().isoformat()}.pdf")

    path = export_pdf(report, output_path, doc_names=doc_names)
    click.echo(f"Exported {report.total_results} results to {path}")
