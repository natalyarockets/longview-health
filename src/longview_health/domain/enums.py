"""Enumerations for domain types."""

from enum import Enum


class DocumentType(str, Enum):
    """Type of source document based on file format."""

    PDF = "pdf"
    PNG = "png"
    JPG = "jpg"
    TIFF = "tiff"
    UNKNOWN = "unknown"


class ResultCategory(str, Enum):
    """Category of medical result.

    Broad classification of what kind of test/finding this is.
    """

    LAB = "lab"
    IMAGING = "imaging"
    PATHOLOGY = "pathology"
    DIAGNOSTIC = "diagnostic"
    VITALS = "vitals"
    OTHER = "other"


class ValidationStatus(str, Enum):
    """Outcome of validation for an extracted result."""

    PASSED = "passed"
    FLAGGED = "flagged"
    REJECTED = "rejected"
    PENDING = "pending"


class Confidence(str, Enum):
    """Confidence level in an extracted result.

    Based on extraction method and validation outcome.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MANUAL = "manual"  # Manually verified by user -- highest trust
