"""Actions module for file operations."""

from .file_operations import FileOperations
from .conflict_resolver import ConflictResolver, ConflictStrategy
from .history_tracker import HistoryTracker, HistoryEntry
from .rules_engine import RulesEngine, CustomRule, MatchType

__all__ = [
    "FileOperations",
    "ConflictResolver",
    "ConflictStrategy",
    "HistoryTracker",
    "HistoryEntry",
    "RulesEngine",
    "CustomRule",
    "MatchType",
]
