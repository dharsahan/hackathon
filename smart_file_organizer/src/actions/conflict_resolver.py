"""
Conflict Resolver
=================

Strategies for resolving file conflicts (duplicates, naming, etc.).
"""

from pathlib import Path
from typing import Optional, List
from enum import Enum
from dataclasses import dataclass

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ConflictStrategy(Enum):
    """Strategy for handling conflicts."""

    RENAME = "rename"  # Add counter suffix
    SKIP = "skip"  # Skip the file
    OVERWRITE = "overwrite"  # Overwrite existing
    QUARANTINE = "quarantine"  # Move to quarantine
    KEEP_NEWER = "keep_newer"  # Keep the newer file
    KEEP_LARGER = "keep_larger"  # Keep the larger file
    ASK = "ask"  # Prompt (not implemented in auto mode)


@dataclass
class ConflictInfo:
    """Information about a file conflict.

    Attributes:
        source: Source file path.
        existing: Existing file at destination.
        conflict_type: Type of conflict.
        resolution: How conflict was resolved.
        result_path: Final file path after resolution.
    """

    source: Path
    existing: Path
    conflict_type: str
    resolution: Optional[ConflictStrategy] = None
    result_path: Optional[Path] = None


class ConflictResolver:
    """Resolves file conflicts based on configured strategy.

    Supports multiple resolution strategies including renaming,
    skipping, overwriting, and smart comparisons.
    """

    def __init__(
        self,
        strategy: ConflictStrategy = ConflictStrategy.RENAME,
        quarantine_dir: Optional[Path] = None,
    ):
        """Initialize conflict resolver.

        Args:
            strategy: Default conflict resolution strategy.
            quarantine_dir: Directory for quarantined files.
        """
        self.strategy = strategy
        self.quarantine_dir = (
            quarantine_dir or Path.home() / "Organized" / ".quarantine"
        )

        # History of resolved conflicts
        self._conflicts: List[ConflictInfo] = []

    def resolve(
        self, source: Path, dest_path: Path, strategy: Optional[ConflictStrategy] = None
    ) -> tuple:
        """Resolve a file conflict.

        Args:
            source: Source file to move/copy.
            dest_path: Intended destination path.
            strategy: Override default strategy.

        Returns:
            Tuple of (action, final_path) where action is
            'proceed', 'skip', 'overwrite', or 'quarantine'.
        """
        strategy = strategy or self.strategy

        # No conflict if destination doesn't exist
        if not dest_path.exists():
            return "proceed", dest_path

        conflict = ConflictInfo(
            source=source, existing=dest_path, conflict_type="name_collision"
        )

        if strategy == ConflictStrategy.RENAME:
            new_path = self._generate_unique_name(dest_path)
            conflict.resolution = strategy
            conflict.result_path = new_path
            self._conflicts.append(conflict)
            return "proceed", new_path

        elif strategy == ConflictStrategy.SKIP:
            conflict.resolution = strategy
            self._conflicts.append(conflict)
            logger.info(f"Skipping (exists): {source.name}")
            return "skip", None

        elif strategy == ConflictStrategy.OVERWRITE:
            conflict.resolution = strategy
            conflict.result_path = dest_path
            self._conflicts.append(conflict)
            logger.info(f"Overwriting: {dest_path.name}")
            return "overwrite", dest_path

        elif strategy == ConflictStrategy.QUARANTINE:
            quarantine_path = self._quarantine(source)
            conflict.resolution = strategy
            conflict.result_path = quarantine_path
            self._conflicts.append(conflict)
            return "quarantine", quarantine_path

        elif strategy == ConflictStrategy.KEEP_NEWER:
            action, path = self._resolve_by_date(source, dest_path)
            conflict.resolution = strategy
            conflict.result_path = path
            self._conflicts.append(conflict)
            return action, path

        elif strategy == ConflictStrategy.KEEP_LARGER:
            action, path = self._resolve_by_size(source, dest_path)
            conflict.resolution = strategy
            conflict.result_path = path
            self._conflicts.append(conflict)
            return action, path

        else:
            # Default to rename
            new_path = self._generate_unique_name(dest_path)
            return "proceed", new_path

    def _generate_unique_name(self, path: Path) -> Path:
        """Generate unique filename by appending counter.

        Args:
            path: Original path.

        Returns:
            Available path with counter suffix.
        """
        stem = path.stem
        suffix = path.suffix
        parent = path.parent

        counter = 1
        while True:
            new_name = f"{stem}_{counter}{suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1
            if counter > 9999:
                # Fallback to timestamp
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                return parent / f"{stem}_{timestamp}{suffix}"

    def _quarantine(self, file_path: Path) -> Path:
        """Move file to quarantine directory.

        Args:
            file_path: File to quarantine.

        Returns:
            Path in quarantine.
        """
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        dest = self.quarantine_dir / file_path.name
        dest = self._generate_unique_name(dest)
        return dest

    def _resolve_by_date(self, source: Path, existing: Path) -> tuple:
        """Resolve by keeping newer file.

        Args:
            source: Source file.
            existing: Existing file.

        Returns:
            Tuple of (action, path).
        """
        source_mtime = source.stat().st_mtime
        existing_mtime = existing.stat().st_mtime

        if source_mtime > existing_mtime:
            # Source is newer, overwrite
            logger.info(f"Overwriting (source newer): {existing.name}")
            return "overwrite", existing
        else:
            # Existing is newer, skip
            logger.info(f"Skipping (existing newer): {source.name}")
            return "skip", None

    def _resolve_by_size(self, source: Path, existing: Path) -> tuple:
        """Resolve by keeping larger file.

        Args:
            source: Source file.
            existing: Existing file.

        Returns:
            Tuple of (action, path).
        """
        source_size = source.stat().st_size
        existing_size = existing.stat().st_size

        if source_size > existing_size:
            # Source is larger, overwrite
            logger.info(f"Overwriting (source larger): {existing.name}")
            return "overwrite", existing
        else:
            # Existing is larger or same, skip
            logger.info(f"Skipping (existing larger/equal): {source.name}")
            return "skip", None

    def get_conflict_history(self) -> List[ConflictInfo]:
        """Get history of resolved conflicts.

        Returns:
            List of ConflictInfo objects.
        """
        return self._conflicts.copy()

    def clear_history(self) -> None:
        """Clear conflict history."""
        self._conflicts.clear()

    def get_stats(self) -> dict:
        """Get conflict resolution statistics.

        Returns:
            Dictionary with statistics.
        """
        stats = {
            "total": len(self._conflicts),
            "by_strategy": {},
        }

        for conflict in self._conflicts:
            strategy = conflict.resolution.value if conflict.resolution else "unknown"
            stats["by_strategy"][strategy] = stats["by_strategy"].get(strategy, 0) + 1

        return stats
