"""Search command -- full-text search across documents in a vault."""

import click

from longview_health.core.config import AppConfig
from longview_health.storage import document_store, search_store, vault_store


def _config() -> AppConfig:
    config = AppConfig()
    config.ensure_dirs()
    return config


@click.command()
@click.argument("vault")
@click.argument("query")
@click.option("--limit", default=20, help="Maximum number of results.")
def search(vault: str, query: str, limit: int) -> None:
    """Search documents in a vault using full-text search.

    Supports FTS5 syntax: AND, OR, NOT, "phrase", prefix*.
    """
    config = _config()

    if not vault_store.vault_exists(config, vault):
        raise click.ClickException(f"Vault '{vault}' not found.")

    hits = search_store.search(config, vault, query, limit=limit)

    if not hits:
        click.echo("No results found.")
        return

    # Resolve document filenames
    doc_ids = [h.document_id for h in hits]
    docs = {
        d.id: d
        for d in [document_store.get_document(config, vault, did) for did in doc_ids]
        if d is not None
    }

    for i, hit in enumerate(hits, 1):
        doc = docs.get(hit.document_id)
        filename = doc.filename if doc else hit.document_id[:12]
        click.echo(f"{i}. {filename}")
        click.echo(f"   {hit.snippet}")
        click.echo()

    click.echo(f"{len(hits)} result(s)")
