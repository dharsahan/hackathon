"""Configuration module for Smart File Organizer."""

from .settings import (
    Config,
    WatcherConfig,
    ClassificationConfig,
    SecurityConfig,
    DeduplicationConfig,
    OrganizationConfig,
)
from .categories import FileCategory, CategoryMapping

__all__ = [
    "Config",
    "WatcherConfig",
    "ClassificationConfig",
    "SecurityConfig",
    "DeduplicationConfig",
    "OrganizationConfig",
    "FileCategory",
    "CategoryMapping",
]
