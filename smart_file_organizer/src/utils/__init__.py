"""Utilities module for Smart File Organizer."""

from .logging_config import setup_logging, get_logger
from .exceptions import (
    SmartOrganizerError,
    ConfigurationError,
    FileProcessingError,
    ClassificationError,
    EncryptionError,
    DeduplicationError,
    ExtractionError,
)

__all__ = [
    "setup_logging",
    "get_logger",
    "SmartOrganizerError",
    "ConfigurationError",
    "FileProcessingError",
    "ClassificationError",
    "EncryptionError",
    "DeduplicationError",
    "ExtractionError",
]
