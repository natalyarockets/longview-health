"""MLX-based LLM inference for Apple Silicon.

Singleton wrapper around mlx-lm. Loads the model once on first call
and caches it in memory for the duration of the process.

Model files are cached by huggingface_hub in the standard location
(~/.cache/huggingface/) or a custom path if configured.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Module-level cache -- loaded once per process
_model = None
_tokenizer = None
_loaded_model_name: str | None = None

DEFAULT_MLX_MODEL = "mlx-community/Qwen2.5-3B-Instruct-4bit"


def _app_support_models_dir() -> Path:
    """Mac-appropriate model cache directory."""
    return Path.home() / "Library" / "Application Support" / "Longview Health" / "models"


def model_is_cached(model_name: str = DEFAULT_MLX_MODEL) -> bool:
    """Check whether the model files are already downloaded.

    Checks both the huggingface_hub default cache and the app-specific
    models directory. Returns True if the model is ready to use without
    any network access.
    """
    try:
        from huggingface_hub import try_to_load_from_cache
        # Check if the config.json is cached (lightweight probe)
        result = try_to_load_from_cache(model_name, "config.json")
        if result is not None:
            return True
    except Exception:
        pass

    # Check app-specific models directory
    app_dir = _app_support_models_dir()
    # huggingface_hub stores in models--org--name format
    safe_name = model_name.replace("/", "--")
    model_dir = app_dir / f"models--{safe_name}"
    if model_dir.exists() and any(model_dir.iterdir()):
        return True

    return False


def model_cache_path(model_name: str = DEFAULT_MLX_MODEL) -> str | None:
    """Return the local path where the model is cached, or None."""
    try:
        from huggingface_hub import try_to_load_from_cache
        result = try_to_load_from_cache(model_name, "config.json")
        if result is not None:
            return str(Path(result).parent)
    except Exception:
        pass
    return None


def download_model(model_name: str = DEFAULT_MLX_MODEL) -> str:
    """Download the model if not already cached. Returns the local path.

    Uses huggingface_hub.snapshot_download which is cache-aware --
    already-downloaded files are not re-fetched.
    """
    from huggingface_hub import snapshot_download

    logger.info("Downloading model %s (skips already-cached files)...", model_name)
    path = snapshot_download(model_name)
    logger.info("Model ready at %s", path)
    return path


def load_model(model_name: str = DEFAULT_MLX_MODEL) -> None:
    """Load the MLX model into memory. No-op if already loaded.

    Downloads the model if not cached (via huggingface_hub).
    """
    global _model, _tokenizer, _loaded_model_name

    if _model is not None and _loaded_model_name == model_name:
        return

    import warnings
    from mlx_lm import load

    logger.info("Loading MLX model: %s", model_name)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*deprecated.*")
        _model, _tokenizer = load(model_name)
    _loaded_model_name = model_name
    logger.info("MLX model loaded successfully")


def generate(
    prompt: str,
    model_name: str = DEFAULT_MLX_MODEL,
    max_tokens: int = 4096,
) -> str:
    """Generate text using the MLX model.

    Loads the model on first call. Applies chat template for instruct models.

    Args:
        prompt: The user prompt text.
        model_name: HuggingFace model identifier.
        max_tokens: Maximum tokens to generate.

    Returns:
        The generated text response.
    """
    from mlx_lm import generate as mlx_generate

    load_model(model_name)

    # Format as chat message for instruct model
    messages = [{"role": "user", "content": prompt}]
    chat_prompt = _tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    response = mlx_generate(
        _model,
        _tokenizer,
        prompt=chat_prompt,
        max_tokens=max_tokens,
        verbose=False,
    )

    return response
