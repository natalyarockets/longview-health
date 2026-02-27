"""Model management commands -- download, status, and info."""

import click

from longview_health.core.config import load_settings


@click.group()
def model() -> None:
    """Manage the local extraction model."""


@model.command()
def status() -> None:
    """Show whether the extraction model is downloaded and ready."""
    settings = load_settings()
    backend = settings["llm_backend"]

    if backend == "ollama":
        click.echo(f"Backend: ollama")
        click.echo(f"Model:   {settings['ollama_model']}")
        click.echo(f"URL:     {settings['ollama_url']}")
        click.echo()
        click.echo("Ollama manages its own models. Run 'ollama list' to check.")
        return

    model_name = settings["mlx_model"]
    click.echo(f"Backend: mlx")
    click.echo(f"Model:   {model_name}")

    from longview_health.extract.mlx_extractor import model_is_cached, model_cache_path

    if model_is_cached(model_name):
        path = model_cache_path(model_name)
        click.echo(f"Status:  downloaded")
        if path:
            click.echo(f"Path:    {path}")
    else:
        click.echo(f"Status:  not downloaded")
        click.echo()
        click.echo("Run 'longview model download' to fetch the model (~2GB).")


@model.command()
def download() -> None:
    """Download the configured MLX model.

    Uses huggingface_hub, which caches files permanently.
    Already-downloaded files are not re-fetched.
    """
    settings = load_settings()

    if settings["llm_backend"] == "ollama":
        click.echo("Backend is set to 'ollama'. Ollama manages its own models.")
        click.echo("To switch to MLX: longview settings set llm_backend mlx")
        return

    model_name = settings["mlx_model"]

    from longview_health.extract.mlx_extractor import model_is_cached

    if model_is_cached(model_name):
        click.echo(f"Model '{model_name}' is already downloaded.")
        return

    click.echo(f"Downloading model: {model_name}")
    click.echo("This may take a few minutes (~2GB)...")

    from longview_health.extract.mlx_extractor import download_model

    path = download_model(model_name)
    click.echo(f"Model downloaded to: {path}")
