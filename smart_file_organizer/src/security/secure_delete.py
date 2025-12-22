"""
Secure File Deletion
====================

Multi-pass secure file deletion to prevent data recovery.
Overwrites file contents before deletion.
"""

from pathlib import Path
from typing import Optional
import os
import secrets

from src.utils.logging_config import get_logger
from src.utils.exceptions import EncryptionError, ErrorCode

logger = get_logger(__name__)

# Try to import Send2Trash for safe deletion
send2trash = None


def _import_send2trash():
    """Lazy import send2trash."""
    global send2trash
    if send2trash is None:
        try:
            import send2trash as _send2trash
            send2trash = _send2trash
        except ImportError:
            send2trash = False
    return send2trash


class SecureDeleter:
    """Secure file deletion with multiple overwrite passes.
    
    Implements multi-pass overwriting before deletion to make
    data recovery more difficult.
    """
    
    # Buffer size for writing random data
    BUFFER_SIZE = 65536  # 64KB
    
    def __init__(self, passes: int = 3, use_trash: bool = False):
        """Initialize secure deleter.
        
        Args:
            passes: Number of overwrite passes (1-7).
            use_trash: Move to trash instead of permanent delete.
        """
        self.passes = min(max(passes, 1), 7)  # Clamp to 1-7
        self.use_trash = use_trash
    
    def secure_delete(self, file_path: Path) -> bool:
        """Securely delete a file.
        
        Overwrites the file with random data multiple times
        before deleting.
        
        Args:
            file_path: Path to file to delete.
        
        Returns:
            True if deletion successful.
        
        Raises:
            EncryptionError: If deletion fails.
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.warning(f"File does not exist: {file_path}")
            return False
        
        if not file_path.is_file():
            raise EncryptionError(
                "Path is not a file",
                file_path=str(file_path),
                operation="secure_delete",
                error_code=ErrorCode.SECURE_DELETE_FAILED
            )
        
        try:
            file_size = file_path.stat().st_size
            
            # Perform overwrite passes
            for pass_num in range(self.passes):
                self._overwrite_pass(file_path, file_size, pass_num)
            
            # Final deletion
            if self.use_trash:
                return self._move_to_trash(file_path)
            else:
                file_path.unlink()
            
            logger.info(
                f"Securely deleted: {file_path.name} "
                f"({self.passes} passes)"
            )
            return True
            
        except Exception as e:
            raise EncryptionError(
                f"Secure deletion failed: {e}",
                file_path=str(file_path),
                operation="secure_delete",
                error_code=ErrorCode.SECURE_DELETE_FAILED
            )
    
    def _overwrite_pass(
        self,
        file_path: Path,
        file_size: int,
        pass_num: int
    ) -> None:
        """Perform a single overwrite pass.
        
        Args:
            file_path: Path to file.
            file_size: Size of file in bytes.
            pass_num: Current pass number.
        """
        with open(file_path, 'r+b') as f:
            # Different patterns for different passes
            if pass_num % 3 == 0:
                # Random data
                bytes_written = 0
                while bytes_written < file_size:
                    chunk_size = min(self.BUFFER_SIZE, file_size - bytes_written)
                    f.write(secrets.token_bytes(chunk_size))
                    bytes_written += chunk_size
            elif pass_num % 3 == 1:
                # All zeros
                zeros = b'\x00' * self.BUFFER_SIZE
                bytes_written = 0
                while bytes_written < file_size:
                    chunk_size = min(self.BUFFER_SIZE, file_size - bytes_written)
                    f.write(zeros[:chunk_size])
                    bytes_written += chunk_size
            else:
                # All ones
                ones = b'\xFF' * self.BUFFER_SIZE
                bytes_written = 0
                while bytes_written < file_size:
                    chunk_size = min(self.BUFFER_SIZE, file_size - bytes_written)
                    f.write(ones[:chunk_size])
                    bytes_written += chunk_size
            
            # Flush to disk
            f.flush()
            os.fsync(f.fileno())
    
    def _move_to_trash(self, file_path: Path) -> bool:
        """Move file to system trash.
        
        Args:
            file_path: Path to file.
        
        Returns:
            True if successful.
        """
        trash_lib = _import_send2trash()
        
        if trash_lib and trash_lib is not False:
            trash_lib.send2trash(str(file_path))
            return True
        else:
            # Fallback to regular delete
            file_path.unlink()
            return True
    
    def secure_delete_directory(
        self,
        dir_path: Path,
        recursive: bool = True
    ) -> int:
        """Securely delete all files in a directory.
        
        Args:
            dir_path: Path to directory.
            recursive: Include subdirectories.
        
        Returns:
            Number of files deleted.
        """
        dir_path = Path(dir_path)
        
        if not dir_path.is_dir():
            raise EncryptionError(
                "Path is not a directory",
                file_path=str(dir_path),
                operation="secure_delete_directory",
                error_code=ErrorCode.SECURE_DELETE_FAILED
            )
        
        pattern = '**/*' if recursive else '*'
        deleted_count = 0
        
        for file_path in sorted(
            dir_path.glob(pattern),
            key=lambda p: len(str(p)),
            reverse=True
        ):
            if file_path.is_file():
                try:
                    self.secure_delete(file_path)
                    deleted_count += 1
                except EncryptionError as e:
                    logger.warning(f"Failed to delete {file_path}: {e}")
        
        # Remove empty directories
        for file_path in sorted(
            dir_path.glob(pattern),
            key=lambda p: len(str(p)),
            reverse=True
        ):
            if file_path.is_dir():
                try:
                    file_path.rmdir()
                except OSError:
                    pass  # Directory not empty
        
        # Remove the main directory if empty
        try:
            dir_path.rmdir()
        except OSError:
            pass
        
        logger.info(f"Securely deleted {deleted_count} files from {dir_path}")
        return deleted_count
    
    def quick_delete(self, file_path: Path) -> bool:
        """Quick delete with single overwrite pass.
        
        Faster than secure_delete but less thorough.
        
        Args:
            file_path: Path to file.
        
        Returns:
            True if successful.
        """
        original_passes = self.passes
        self.passes = 1
        try:
            return self.secure_delete(file_path)
        finally:
            self.passes = original_passes
