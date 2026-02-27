"""Rescan command -- ingest and process documents in a vault."""

import click

from longview_health.core.config import AppConfig, load_settings
from longview_health.storage import vault_store


def _config() -> AppConfig:
    config = AppConfig()
    config.ensure_dirs()
    return config


@click.command()
@click.argument("vault")
@click.option("--reprocess", is_flag=True, help="Re-extract even for already-indexed documents.")
@click.option("--no-export", is_flag=True, help="Skip PDF export after scanning.")
@click.option("--mlx", "force_backend", flag_value="mlx", help="Force MLX backend for extraction.")
@click.option("--ollama", "force_backend", flag_value="ollama", help="Force Ollama backend for extraction.")
def rescan(vault: str, reprocess: bool, no_export: bool, force_backend: str | None) -> None:
    """Scan/rescan all documents in a vault.

    Point a vault at your documents folder with:
        longview vault create <name> --path /path/to/documents

    Then run this command to process them. A PDF trend report is
    automatically generated after scanning.
    """
    config = _config()

    if not vault_store.vault_exists(config, vault):
        raise click.ClickException(f"Vault '{vault}' not found.")

    # Resolve LLM backend from flag or settings
    settings = load_settings()
    backend = force_backend or settings["llm_backend"]
    model = settings["mlx_model"] if backend == "mlx" else settings["ollama_model"]
    base_url = settings["ollama_url"]

    click.echo(f"Scanning vault '{vault}' (backend: {backend})...")

    from longview_health.ingest.orchestrator import ingest_vault

    def on_file(filename: str, status: str) -> None:
        click.echo(f"  {filename}: {status}")

    result = ingest_vault(
        config, vault,
        reprocess=reprocess,
        on_file=on_file,
        backend=backend,
        model=model,
        base_url=base_url,
    )

    click.echo()
    click.echo(f"Files found:     {result.files_found}")
    click.echo(f"New/changed:     {result.files_new}")
    click.echo(f"Skipped:         {result.files_skipped}")
    if result.files_removed:
        click.echo(f"Removed:         {result.files_removed}")
    click.echo(f"Parsed:          {result.documents_parsed}")
    click.echo(f"Results stored:  {result.results_stored}")

    if result.errors:
        click.echo()
        click.echo(f"Errors ({len(result.errors)}):")
        for err in result.errors:
            click.echo(f"  {err}", err=True)

    # Auto-export PDF trend report (regenerate if anything changed)
    has_changes = result.results_stored > 0 or result.files_removed > 0
    if not no_export and has_changes:
        from longview_health.core.paths import vault_trends_pdf
        from longview_health.storage import results_store
        from longview_health.trends.engine import build_trend_report
        from longview_health.trends.export import export_pdf

        all_results = results_store.query_results(config, vault)
        if all_results:
            report = build_trend_report(vault, all_results)
            doc_ids = list({r.document_id for r in all_results})
            doc_names = results_store.get_document_names(config, vault, doc_ids)

            out_path = vault_trends_pdf(config, vault)
            export_pdf(report, out_path, doc_names=doc_names)

            click.echo()
            click.echo(f"PDF report: {out_path}")
