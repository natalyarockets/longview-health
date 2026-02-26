"""Base error types for Longview Health."""


class LongviewError(Exception):
    """Base exception for all Longview errors."""


class VaultNotFoundError(LongviewError):
    """Raised when a vault does not exist."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Vault not found: {name}")


class VaultExistsError(LongviewError):
    """Raised when creating a vault that already exists."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Vault already exists: {name}")


class StorageError(LongviewError):
    """Raised for storage/database errors."""


class ValidationError(LongviewError):
    """Raised when extracted data fails validation."""


class ParseError(LongviewError):
    """Raised when document parsing fails."""
