"""Application configuration."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


def _default_vault_root() -> Path:
    return Path.home() / ".longview" / "vaults"


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration.

    Immutable after creation. Passed explicitly to all modules that need it.
    """

    vault_root: Path = field(default_factory=_default_vault_root)

    def ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        self.vault_root.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# LLM settings -- persisted in ~/.longview/settings.json
# ---------------------------------------------------------------------------

_SETTINGS_PATH = Path.home() / ".longview" / "settings.json"

_DEFAULTS: dict[str, str] = {
    "llm_backend": "mlx",
    "mlx_model": "mlx-community/Qwen2.5-3B-Instruct-4bit",
    "ollama_url": "http://localhost:11434",
    "ollama_model": "qwen2.5vl:latest",
}


def load_settings() -> dict[str, str]:
    """Load settings from disk, merging with defaults for any missing keys."""
    settings = dict(_DEFAULTS)
    if _SETTINGS_PATH.exists():
        try:
            with open(_SETTINGS_PATH) as f:
                stored = json.load(f)
            settings.update(stored)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read settings from %s: %s", _SETTINGS_PATH, e)
    return settings


def save_settings(settings: dict[str, str]) -> None:
    """Write settings to disk."""
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")


def get_setting(key: str) -> str:
    """Get a single setting value."""
    settings = load_settings()
    return settings.get(key, _DEFAULTS.get(key, ""))


def set_setting(key: str, value: str) -> None:
    """Set a single setting value and persist."""
    if key not in _DEFAULTS:
        raise ValueError(f"Unknown setting: {key}. Valid keys: {', '.join(sorted(_DEFAULTS))}")
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
