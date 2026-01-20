"""
History Tracker
================

Tracks file movement history and provides undo functionality.
Stores history in a JSON file for persistence across sessions.
"""

import json
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict
from datetime import datetime
import shutil

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class HistoryEntry:
    """Record of a single file operation.

    Attributes:
        id: Unique identifier for this entry.
        timestamp: When the operation occurred.
        operation: Type of operation (move, copy, delete).
        source_path: Original file location.
        dest_path: New file location.
        category: Classification category.
        subcategory: Classification subcategory.
        file_size: Size of file in bytes.
        can_undo: Whether this operation can be undone.
    """

    id: int
    timestamp: str
    operation: str
    source_path: str
    dest_path: str
    category: str = ""
    subcategory: str = ""
    file_size: int = 0
    can_undo: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        """Create from dictionary."""
        return cls(**data)


class HistoryTracker:
    """Tracks file operations and provides undo functionality.

    Persists history to a JSON file for durability across sessions.
    """

    DEFAULT_HISTORY_FILE = "organization_history.json"
    MAX_HISTORY_SIZE = 1000  # Maximum entries to keep

    def __init__(
        self, history_file: Optional[Path] = None, base_directory: Optional[Path] = None
    ):
        """Initialize history tracker.

        Args:
            history_file: Path to history JSON file.
            base_directory: Base directory for organized files.
        """
        self.base_directory = base_directory or Path.home() / "Organized"
        self.history_file = (
            history_file or self.base_directory / self.DEFAULT_HISTORY_FILE
        )
        self._history: List[HistoryEntry] = []
        self._next_id = 1
        self._load_history()

    def _load_history(self) -> None:
        """Load history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r") as f:
                    data = json.load(f)
                    self._history = [
                        HistoryEntry.from_dict(entry)
                        for entry in data.get("entries", [])
                    ]
                    self._next_id = data.get("next_id", 1)
                logger.debug(f"Loaded {len(self._history)} history entries")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Error loading history: {e}")
                self._history = []

    def _save_history(self) -> None:
        """Save history to file."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        # Trim history if too large
        if len(self._history) > self.MAX_HISTORY_SIZE:
            self._history = self._history[-self.MAX_HISTORY_SIZE :]

        data = {
            "next_id": self._next_id,
            "entries": [entry.to_dict() for entry in self._history],
        }

        with open(self.history_file, "w") as f:
            json.dump(data, f, indent=2)

    def record_move(
        self, source: Path, destination: Path, category: str = "", subcategory: str = ""
    ) -> HistoryEntry:
        """Record a file move operation.

        Args:
            source: Original file path.
            destination: New file path.
            category: Classification category.
            subcategory: Classification subcategory.

        Returns:
            The created history entry.
        """
        try:
            file_size = destination.stat().st_size if destination.exists() else 0
        except OSError:
            file_size = 0

        entry = HistoryEntry(
            id=self._next_id,
            timestamp=datetime.now().isoformat(),
            operation="move",
            source_path=str(source),
            dest_path=str(destination),
            category=category,
            subcategory=subcategory,
            file_size=file_size,
            can_undo=True,
        )

        self._next_id += 1
        self._history.append(entry)
        self._save_history()

        logger.debug(f"Recorded move: {source.name} -> {destination}")
        return entry

    def undo_last(self) -> Optional[HistoryEntry]:
        """Undo the most recent undoable operation.

        Returns:
            The undone entry, or None if nothing to undo.
        """
        # Find last undoable entry
        for i in range(len(self._history) - 1, -1, -1):
            entry = self._history[i]
            if entry.can_undo and entry.operation == "move":
                return self._undo_entry(entry, i)

        logger.info("Nothing to undo")
        return None

    def undo_by_id(self, entry_id: int) -> Optional[HistoryEntry]:
        """Undo a specific operation by ID.

        Args:
            entry_id: ID of the entry to undo.

        Returns:
            The undone entry, or None if not found.
        """
        for i, entry in enumerate(self._history):
            if entry.id == entry_id and entry.can_undo:
                return self._undo_entry(entry, i)

        logger.warning(f"Entry {entry_id} not found or cannot be undone")
        return None

    def _undo_entry(self, entry: HistoryEntry, index: int) -> HistoryEntry:
        """Perform the undo operation.

        Args:
            entry: The entry to undo.
            index: Index in history list.

        Returns:
            The undone entry.
        """
        dest = Path(entry.dest_path)
        source = Path(entry.source_path)

        if not dest.exists():
            logger.warning(f"Cannot undo: destination file not found: {dest}")
            entry.can_undo = False
            self._save_history()
            return entry

        # Move file back to original location
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dest), str(source))

        # Mark as undone
        entry.can_undo = False
        self._save_history()

        logger.info(f"Undone: {dest.name} -> {source}")
        return entry

    def get_recent(self, count: int = 10) -> List[HistoryEntry]:
        """Get recent history entries.

        Args:
            count: Number of entries to return.

        Returns:
            List of recent entries (newest first).
        """
        return list(reversed(self._history[-count:]))

    def get_by_date(self, date: datetime) -> List[HistoryEntry]:
        """Get history entries for a specific date.

        Args:
            date: Date to filter by.

        Returns:
            List of entries from that date.
        """
        date_str = date.strftime("%Y-%m-%d")
        return [
            entry for entry in self._history if entry.timestamp.startswith(date_str)
        ]

    def get_stats(self) -> Dict:
        """Get history statistics.

        Returns:
            Dictionary with stats.
        """
        categories = {}
        for entry in self._history:
            cat = entry.category or "Unknown"
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_operations": len(self._history),
            "undoable": sum(1 for e in self._history if e.can_undo),
            "by_category": categories,
            "total_size_bytes": sum(e.file_size for e in self._history),
        }

    def clear_history(self) -> None:
        """Clear all history."""
        self._history.clear()
        self._next_id = 1
        self._save_history()
        logger.info("History cleared")

    def search(self, query: str) -> List[HistoryEntry]:
        """Search history by filename.

        Args:
            query: Search term.

        Returns:
            Matching entries.
        """
        query_lower = query.lower()
        return [
            entry
            for entry in self._history
            if query_lower in Path(entry.source_path).name.lower()
            or query_lower in Path(entry.dest_path).name.lower()
        ]
