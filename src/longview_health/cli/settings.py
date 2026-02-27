"""Settings management commands."""

import click

from longview_health.core.config import _DEFAULTS, load_settings, set_setting


@click.group("settings")
def settings_group() -> None:
    """View and change Longview settings."""


@settings_group.command("show")
def show() -> None:
    """Show all current settings."""
    current = load_settings()
    for key in sorted(_DEFAULTS):
        value = current.get(key, _DEFAULTS[key])
        default_marker = " (default)" if value == _DEFAULTS.get(key) else ""
        click.echo(f"  {key}: {value}{default_marker}")


@settings_group.command("set")
@click.argument("key")
@click.argument("value")
def set_value(key: str, value: str) -> None:
    """Set a configuration value.

    Valid keys: llm_backend, mlx_model, ollama_url, ollama_model
    """
    try:
        set_setting(key, value)
    except ValueError as e:
        raise click.ClickException(str(e))
    click.echo(f"Set {key} = {value}")


@settings_group.command("get")
@click.argument("key")
def get_value(key: str) -> None:
    """Get a single setting value."""
    settings = load_settings()
    if key not in _DEFAULTS:
        raise click.ClickException(
            f"Unknown setting: {key}. Valid keys: {', '.join(sorted(_DEFAULTS))}"
        )
    click.echo(settings.get(key, _DEFAULTS.get(key, "")))
