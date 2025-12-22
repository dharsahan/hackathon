"""Actions module for file operations."""

from .file_operations import FileOperations
from .conflict_resolver import ConflictResolver, ConflictStrategy

__all__ = [
    "FileOperations",
    "ConflictResolver",
    "ConflictStrategy",
]
