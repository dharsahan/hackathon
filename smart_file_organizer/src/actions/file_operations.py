"""
File Operations
===============

Safe file operations for organizing files.
Handles moving, copying, renaming with atomic operations.
"""

from pathlib import Path
from typing import Optional
import shutil
from datetime import datetime

from src.utils.logging_config import get_logger
from src.utils.exceptions import FileProcessingError, ErrorCode

logger = get_logger(__name__)


class FileOperations:
    """Safe file operations with conflict handling.
    
    Provides atomic move/copy operations with automatic
    conflict resolution.
    """

    def __init__(self, base_directory: Optional[Path] = None):
        """Initialize file operations.
        
        Args:
            base_directory: Base directory for organized files.
        """
        self.base_directory = Path(base_directory) if base_directory else Path.home() / "Organized"

    def move_file(
        self,
        source: Path,
        dest_dir: Path,
        new_name: Optional[str] = None
    ) -> Path:
        """Move a file to destination directory.
        
        Args:
            source: Source file path.
            dest_dir: Destination directory.
            new_name: Optional new filename.
        
        Returns:
            Final path of moved file.
        
        Raises:
            FileProcessingError: If move fails.
        """
        source = Path(source)
        dest_dir = Path(dest_dir)

        if not source.exists():
            raise FileProcessingError(
                "Source file does not exist",
                file_path=str(source),
                error_code=ErrorCode.FILE_NOT_FOUND
            )

        # Create destination directory
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Determine filename
        filename = new_name if new_name else source.name
        dest_path = dest_dir / filename

        # Handle conflicts
        dest_path = self._resolve_conflict(dest_path)

        try:
            shutil.move(str(source), str(dest_path))
            logger.info(f"Moved: {source.name} -> {dest_path}")
            return dest_path

        except Exception as e:
            raise FileProcessingError(
                f"Failed to move file: {e}",
                file_path=str(source),
                error_code=ErrorCode.PROCESSING_FAILED
            )

    def copy_file(
        self,
        source: Path,
        dest_dir: Path,
        new_name: Optional[str] = None
    ) -> Path:
        """Copy a file to destination directory.
        
        Args:
            source: Source file path.
            dest_dir: Destination directory.
            new_name: Optional new filename.
        
        Returns:
            Path of copied file.
        """
        source = Path(source)
        dest_dir = Path(dest_dir)

        if not source.exists():
            raise FileProcessingError(
                "Source file does not exist",
                file_path=str(source),
                error_code=ErrorCode.FILE_NOT_FOUND
            )

        dest_dir.mkdir(parents=True, exist_ok=True)

        filename = new_name if new_name else source.name
        dest_path = dest_dir / filename
        dest_path = self._resolve_conflict(dest_path)

        try:
            shutil.copy2(str(source), str(dest_path))
            logger.info(f"Copied: {source.name} -> {dest_path}")
            return dest_path

        except Exception as e:
            raise FileProcessingError(
                f"Failed to copy file: {e}",
                file_path=str(source),
                error_code=ErrorCode.PROCESSING_FAILED
            )

    def rename_file(
        self,
        file_path: Path,
        new_name: str
    ) -> Path:
        """Rename a file.
        
        Args:
            file_path: Path to file.
            new_name: New filename.
        
        Returns:
            New file path.
        """
        file_path = Path(file_path)
        new_path = file_path.parent / new_name

        new_path = self._resolve_conflict(new_path)

        try:
            file_path.rename(new_path)
            logger.info(f"Renamed: {file_path.name} -> {new_path.name}")
            return new_path

        except Exception as e:
            raise FileProcessingError(
                f"Failed to rename file: {e}",
                file_path=str(file_path),
                error_code=ErrorCode.PROCESSING_FAILED
            )

    def _resolve_conflict(self, dest_path: Path) -> Path:
        """Resolve filename conflict by appending counter.
        
        Args:
            dest_path: Desired destination path.
        
        Returns:
            Available path (may have counter suffix).
        """
        if not dest_path.exists():
            return dest_path

        stem = dest_path.stem
        suffix = dest_path.suffix
        parent = dest_path.parent

        counter = 1
        while True:
            new_name = f"{stem}_{counter}{suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1
            if counter > 1000:
                raise FileProcessingError(
                    "Too many files with same name",
                    file_path=str(dest_path),
                    error_code=ErrorCode.PROCESSING_FAILED
                )

    def create_date_path(
        self,
        base_dir: Path,
        date: Optional[datetime] = None,
        format_str: str = "%Y/%m"
    ) -> Path:
        """Create date-based subdirectory structure.
        
        Args:
            base_dir: Base directory.
            date: Date to use (default: now).
            format_str: strftime format for path.
        
        Returns:
            Path with date subdirectories.
        """
        if date is None:
            date = datetime.now()

        date_path = date.strftime(format_str)
        full_path = base_dir / date_path
        full_path.mkdir(parents=True, exist_ok=True)

        return full_path

    def get_destination_path(
        self,
        category: str,
        subcategory: Optional[str] = None,
        use_date: bool = True
    ) -> Path:
        """Get organized destination path.
        
        Args:
            category: Main category name.
            subcategory: Optional subcategory.
            use_date: Include date folders.
        
        Returns:
            Full destination path.
        """
        dest = self.base_directory / category

        if subcategory:
            dest = dest / subcategory

        if use_date:
            dest = self.create_date_path(dest)
        else:
            dest.mkdir(parents=True, exist_ok=True)

        return dest

    def quarantine_file(
        self,
        file_path: Path,
        reason: str = "duplicate"
    ) -> Path:
        """Move file to quarantine directory.
        
        Args:
            file_path: File to quarantine.
            reason: Reason for quarantine.
        
        Returns:
            Path in quarantine.
        """
        quarantine_dir = self.base_directory / ".quarantine" / reason
        return self.move_file(file_path, quarantine_dir)

    def is_safe_path(self, file_path: Path) -> bool:
        """Check if path is safe to operate on.
        
        Args:
            file_path: Path to check.
        
        Returns:
            True if path is safe.
        """
        file_path = Path(file_path).absolute()

        # Check not operating on system directories
        unsafe_dirs = [
            Path("/"),
            Path("/bin"),
            Path("/boot"),
            Path("/etc"),
            Path("/lib"),
            Path("/sbin"),
            Path("/usr"),
            Path("/var"),
            Path.home() / ".config",
            Path.home() / ".local",
        ]

        for unsafe in unsafe_dirs:
            if file_path == unsafe:
                return False

        return True
