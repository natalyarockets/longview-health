"""Review command -- review flagged/uncertain extractions."""

import click

from longview_health.core.config import AppConfig
from longview_health.review import queue as review_queue
from longview_health.storage import results_store, review_store, vault_store


def _config() -> AppConfig:
    config = AppConfig()
    config.ensure_dirs()
    return config


@click.group()
def review() -> None:
    """Review and correct flagged extractions."""


@review.command("list")
@click.argument("vault")
@click.option("--all", "show_all", is_flag=True, help="Show resolved items too.")
def list_items(vault: str, show_all: bool) -> None:
    """List items in the review queue."""
    config = _config()

    if not vault_store.vault_exists(config, vault):
        raise click.ClickException(f"Vault '{vault}' not found.")

    items = (
        review_store.list_all(config, vault)
        if show_all
        else review_store.list_pending(config, vault)
    )

    if not items:
        click.echo("No items to review.")
        return

    for item in items:
        status = "RESOLVED" if item.resolved else "PENDING"
        click.echo(f"  [{status}] {item.id[:8]}  {item.test_name}")
        click.echo(f"           Reason: {item.reason}")
        click.echo(f"           Result: {item.result_id[:12]}  Doc: {item.document_id[:12]}")
        click.echo()

    pending = sum(1 for i in items if not i.resolved)
    click.echo(f"{len(items)} item(s), {pending} pending")


@review.command()
@click.argument("vault")
@click.argument("review_id")
def accept(vault: str, review_id: str) -> None:
    """Accept a flagged result as correct."""
    config = _config()

    if not vault_store.vault_exists(config, vault):
        raise click.ClickException(f"Vault '{vault}' not found.")

    # Allow matching by prefix
    items = review_store.list_pending(config, vault)
    match = _find_by_prefix(items, review_id)
    if not match:
        raise click.ClickException(f"No pending review item matching '{review_id}'.")

    if review_queue.accept_item(config, vault, match.id):
        click.echo(f"Accepted: {match.test_name} ({match.id[:8]})")
    else:
        click.echo("Failed to accept item.", err=True)


@review.command()
@click.argument("vault")
@click.argument("review_id")
def reject(vault: str, review_id: str) -> None:
    """Reject a result and remove it from stored results."""
    config = _config()

    if not vault_store.vault_exists(config, vault):
        raise click.ClickException(f"Vault '{vault}' not found.")

    items = review_store.list_pending(config, vault)
    match = _find_by_prefix(items, review_id)
    if not match:
        raise click.ClickException(f"No pending review item matching '{review_id}'.")

    if review_queue.reject_item(config, vault, match.id, match.result_id):
        click.echo(f"Rejected and removed: {match.test_name} ({match.id[:8]})")
    else:
        click.echo("Failed to reject item.", err=True)


@review.command()
@click.argument("vault")
@click.argument("review_id")
@click.option("--value", default=None, help="Corrected value.")
@click.option("--unit", default=None, help="Corrected unit.")
@click.option("--test-name", default=None, help="Corrected test name.")
def edit(
    vault: str,
    review_id: str,
    value: str | None,
    unit: str | None,
    test_name: str | None,
) -> None:
    """Edit a result's value, unit, or test name and mark as manually verified."""
    config = _config()

    if not vault_store.vault_exists(config, vault):
        raise click.ClickException(f"Vault '{vault}' not found.")

    if value is None and unit is None and test_name is None:
        raise click.ClickException("Provide at least one of --value, --unit, or --test-name.")

    items = review_store.list_pending(config, vault)
    match = _find_by_prefix(items, review_id)
    if not match:
        raise click.ClickException(f"No pending review item matching '{review_id}'.")

    if review_queue.edit_result(
        config, vault, match.id, match.result_id,
        value=value, unit=unit, test_name=test_name,
    ):
        click.echo(f"Edited and verified: {match.test_name} ({match.id[:8]})")
    else:
        click.echo("Failed to edit item.", err=True)


def _find_by_prefix(
    items: list[review_store.ReviewRow], prefix: str
) -> review_store.ReviewRow | None:
    """Find a review item by ID prefix match."""
    for item in items:
        if item.id.startswith(prefix):
            return item
    return None
