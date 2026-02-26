"""Application configuration."""

from dataclasses import dataclass, field
from pathlib import Path


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
