"""
Hash Engine
===========

Cryptographic hashing for file deduplication.
Implements efficient partial hashing for fast comparison.
"""

from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass
from enum import Enum
import hashlib
import os

from src.utils.logging_config import get_logger
from src.utils.exceptions import DeduplicationError

logger = get_logger(__name__)


class DuplicateStatus(Enum):
    """Status of duplicate detection."""
    UNIQUE = "unique"
    EXACT_DUPLICATE = "exact_duplicate"
    LIKELY_DUPLICATE = "likely_duplicate"
    SIZE_MATCH = "size_match"  # Size matches but hash differs


@dataclass
class HashResult:
    """Result of hash computation for a file.
    
    Attributes:
        file_path: Path to the file.
        file_size: File size in bytes.
        partial_hash: Hash of file chunks (fast comparison).
        full_hash: Complete file hash.
        status: Duplicate detection status.
        duplicate_of: Path to original file if duplicate.
    """
    file_path: Path
    file_size: int
    partial_hash: Optional[str] = None
    full_hash: Optional[str] = None
    status: DuplicateStatus = DuplicateStatus.UNIQUE
    duplicate_of: Optional[Path] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "file_path": str(self.file_path),
            "file_size": self.file_size,
            "partial_hash": self.partial_hash,
            "full_hash": self.full_hash,
            "status": self.status.value,
            "duplicate_of": str(self.duplicate_of) if self.duplicate_of else None,
        }


class PartialHasher:
    """Implements partial hashing for fast file comparison.
    
    Hashes only the beginning, middle, and end of large files
    for fast initial comparison.
    """

    def __init__(self, chunk_size: int = 4096):
        """Initialize partial hasher.
        
        Args:
            chunk_size: Size of chunks to hash in bytes.
        """
        self.chunk_size = chunk_size

    def compute(self, file_path: Path) -> str:
        """Compute partial hash of a file.
        
        For files smaller than 3 chunks, computes full hash.
        For larger files, hashes beginning, middle, and end.
        
        Args:
            file_path: Path to the file.
        
        Returns:
            Hexadecimal hash string.
        
        Raises:
            DeduplicationError: If file cannot be read.
        """
        try:
            file_size = file_path.stat().st_size
        except OSError as e:
            raise DeduplicationError(
                f"Cannot stat file: {e}",
                file_path=str(file_path),
                hash_type="partial"
            )

        # For small files, just compute full hash
        if file_size <= self.chunk_size * 3:
            return self._hash_full(file_path)

        hasher = hashlib.sha256()

        try:
            with open(file_path, 'rb') as f:
                # First chunk
                hasher.update(f.read(self.chunk_size))

                # Middle chunk
                middle_pos = file_size // 2
                f.seek(middle_pos)
                hasher.update(f.read(self.chunk_size))

                # Last chunk
                f.seek(-self.chunk_size, os.SEEK_END)
                hasher.update(f.read(self.chunk_size))

                # Include file size for additional uniqueness
                hasher.update(str(file_size).encode())

            return hasher.hexdigest()

        except OSError as e:
            raise DeduplicationError(
                f"Cannot read file: {e}",
                file_path=str(file_path),
                hash_type="partial"
            )

    def _hash_full(self, file_path: Path) -> str:
        """Compute full hash for small files.
        
        Args:
            file_path: Path to file.
        
        Returns:
            Hexadecimal hash string.
        """
        with open(file_path, 'rb') as f:
            if hasattr(hashlib, 'file_digest'):
                return hashlib.file_digest(f, "sha256").hexdigest()

            # Fallback for Python < 3.11
            hasher = hashlib.sha256()
            hasher.update(f.read())
            return hasher.hexdigest()


class FullHasher:
    """Computes full SHA-256 hash of files.
    
    Uses hashlib.file_digest for optimized hashing.
    """

    BUFFER_SIZE = 65536  # Kept for compatibility if needed elsewhere

    def compute(self, file_path: Path) -> str:
        """Compute full SHA-256 hash.
        
        Args:
            file_path: Path to the file.
        
        Returns:
            Hexadecimal hash string.
        
        Raises:
            DeduplicationError: If file cannot be read.
        """
        try:
            with open(file_path, 'rb') as f:
                if hasattr(hashlib, 'file_digest'):
                    return hashlib.file_digest(f, "sha256").hexdigest()

                # Fallback for Python < 3.11
                hasher = hashlib.sha256()
                while True:
                    data = f.read(self.BUFFER_SIZE)
                    if not data:
                        break
                    hasher.update(data)
                return hasher.hexdigest()

        except OSError as e:
            raise DeduplicationError(
                f"Cannot read file: {e}",
                file_path=str(file_path),
                hash_type="full"
            )

    def compute_md5(self, file_path: Path) -> str:
        """Compute MD5 hash (for compatibility).
        
        Args:
            file_path: Path to the file.
        
        Returns:
            Hexadecimal MD5 hash.
        """
        with open(file_path, 'rb') as f:
            if hasattr(hashlib, 'file_digest'):
                return hashlib.file_digest(f, "md5").hexdigest()

            # Fallback for Python < 3.11
            hasher = hashlib.md5()
            while True:
                data = f.read(self.BUFFER_SIZE)
                if not data:
                    break
                hasher.update(data)
            return hasher.hexdigest()


class DeduplicationEngine:
    """Main deduplication engine.
    
    Uses a multi-stage approach for efficient duplicate detection:
    1. Size comparison (fastest)
    2. Partial hash comparison
    3. Full hash comparison (for confirmation)
    """

    def __init__(self, chunk_size: int = 4096):
        """Initialize deduplication engine.
        
        Args:
            chunk_size: Chunk size for partial hashing.
        """
        self.partial_hasher = PartialHasher(chunk_size=chunk_size)
        self.full_hasher = FullHasher()

        # Indexes for fast lookup
        self._size_index: Dict[int, List[Path]] = {}  # size -> [paths]
        self._files_pending_partial: Dict[int, List[Path]] = {}  # size -> [paths pending partial hash]
        self._partial_hash_index: Dict[str, List[Path]] = {}  # partial -> [paths]
        self._full_hash_index: Dict[str, Path] = {}  # full -> first path
        self._path_to_partial_hash: Dict[Path, str] = {}  # path -> partial_hash
        self._path_to_full_hash: Dict[Path, str] = {}  # path -> full_hash

    def check_duplicate(self, file_path: Path) -> HashResult:
        """Check if a file is a duplicate.
        
        Uses multi-stage hashing for efficiency.
        
        Args:
            file_path: Path to check.
        
        Returns:
            HashResult with duplicate status.
        """
        file_path = Path(file_path)

        try:
            file_size = file_path.stat().st_size
        except OSError as e:
            raise DeduplicationError(
                f"Cannot access file: {e}",
                file_path=str(file_path)
            )

        result = HashResult(file_path=file_path, file_size=file_size)

        # Stage 1: Size comparison (fastest)
        if file_size not in self._size_index:
            # First file with this size - store for future comparison but defer hashing
            # Optimization: Don't compute partial/full hash yet.
            # Return immediately to avoid I/O overhead for unique sizes.
            self._size_index[file_size] = [file_path]
            self._files_pending_partial[file_size] = [file_path]

            # result.partial_hash remains None
            result.status = DuplicateStatus.UNIQUE
            logger.debug(f"Unique (first of size): {file_path.name}")
            return result

        # Stage 2: Partial hash comparison
        partial_hash = self.partial_hasher.compute(file_path)
        result.partial_hash = partial_hash
        self._path_to_partial_hash[file_path] = partial_hash

        # Hydrate partial hashes for candidates if missing (Lazy Hashing)
        # Optimization: Only iterate candidates that haven't been partial-hashed yet.
        # This reduces O(N^2) complexity to O(N) when adding many files of same size.
        candidates = self._files_pending_partial.get(file_size, [])
        if candidates:
            for candidate in candidates:
                # Candidates in _files_pending_partial definitely need hashing
                try:
                    c_partial_hash = self.partial_hasher.compute(candidate)
                    self._path_to_partial_hash[candidate] = c_partial_hash
                    if c_partial_hash not in self._partial_hash_index:
                        self._partial_hash_index[c_partial_hash] = []
                    self._partial_hash_index[c_partial_hash].append(candidate)
                except DeduplicationError:
                    # If we can't read the candidate anymore, ignore it
                    continue

            # Clear pending list as they are processed
            del self._files_pending_partial[file_size]

        if partial_hash not in self._partial_hash_index:
            # No partial hash match - likely unique
            self._size_index[file_size].append(file_path)
            # No need to add to pending because we just computed its partial hash

            if partial_hash not in self._partial_hash_index:
                self._partial_hash_index[partial_hash] = []
            self._partial_hash_index[partial_hash].append(file_path)
            result.status = DuplicateStatus.UNIQUE
            logger.debug(f"Unique (partial hash): {file_path.name}")
            return result

        # Stage 3: Full hash for confirmation
        # Potential duplicate found by partial hash. Now we need full hashes.
        full_hash = self.full_hasher.compute(file_path)
        result.full_hash = full_hash
        self._path_to_full_hash[file_path] = full_hash

        # Optimization: Check if we already have a valid match in the index
        # This avoids iterating through candidates if we already know it's a duplicate
        skip_candidates = False
        if full_hash in self._full_hash_index:
            original_path = self._full_hash_index[full_hash]
            if original_path.exists() and original_path != file_path:
                skip_candidates = True

        if not skip_candidates:
            # Ensure all candidates have their full hash computed
            candidates = self._partial_hash_index[partial_hash]
            for candidate in candidates:
                if candidate not in self._path_to_full_hash:
                    # Lazy computation of candidate's full hash
                    try:
                        candidate_hash = self.full_hasher.compute(candidate)
                        self._path_to_full_hash[candidate] = candidate_hash
                        if candidate_hash not in self._full_hash_index:
                            self._full_hash_index[candidate_hash] = candidate

                        # Optimization: If we found a match, we can stop hydrating other candidates
                        if candidate_hash == full_hash:
                            break
                    except DeduplicationError:
                        # If we can't read the candidate anymore, ignore it
                        continue

        if full_hash in self._full_hash_index:
            original_path = self._full_hash_index[full_hash]

            # Check if the "original" file still exists
            # If not, this is just a moved file, not a duplicate!
            if original_path.exists() and original_path != file_path:
                # True duplicate found
                result.status = DuplicateStatus.EXACT_DUPLICATE
                result.duplicate_of = original_path
                logger.info(
                    f"Duplicate found: {file_path.name} = "
                    f"{result.duplicate_of.name}"
                )
            else:
                # Original file was moved/deleted - update index with new location
                self._full_hash_index[full_hash] = file_path

                # Update size and partial hash indexes too
                if original_path in self._size_index.get(file_size, []):
                    self._size_index[file_size].remove(original_path)
                self._size_index[file_size].append(file_path)

                if original_path in self._partial_hash_index.get(partial_hash, []):
                    self._partial_hash_index[partial_hash].remove(original_path)
                self._partial_hash_index[partial_hash].append(file_path)

                result.status = DuplicateStatus.UNIQUE
                logger.debug(f"File moved, updating index: {file_path.name}")
        else:
            # Not a duplicate, add to indexes
            self._full_hash_index[full_hash] = file_path
            self._path_to_full_hash[file_path] = full_hash
            self._size_index[file_size].append(file_path)
            self._partial_hash_index[partial_hash].append(file_path)
            result.status = DuplicateStatus.UNIQUE
            logger.debug(f"Unique (full hash): {file_path.name}")

        return result

    def add_to_index(self, file_path: Path) -> HashResult:
        """Add a file to the index without checking for duplicates.
        
        Use this when indexing existing organized files.
        
        Args:
            file_path: Path to add.
        
        Returns:
            HashResult with computed hashes.
        """
        file_path = Path(file_path)
        file_size = file_path.stat().st_size

        partial_hash = self.partial_hasher.compute(file_path)
        full_hash = self.full_hasher.compute(file_path)

        # Add to indexes
        if file_size not in self._size_index:
            self._size_index[file_size] = []
        self._size_index[file_size].append(file_path)

        if partial_hash not in self._partial_hash_index:
            self._partial_hash_index[partial_hash] = []
        self._partial_hash_index[partial_hash].append(file_path)

        if full_hash not in self._full_hash_index:
            self._full_hash_index[full_hash] = file_path

        self._path_to_full_hash[file_path] = full_hash
        self._path_to_partial_hash[file_path] = partial_hash

        return HashResult(
            file_path=file_path,
            file_size=file_size,
            partial_hash=partial_hash,
            full_hash=full_hash,
            status=DuplicateStatus.UNIQUE
        )

    def find_duplicates_in_directory(self, directory: Path) -> Dict[str, List[Path]]:
        """Find all duplicates in a directory.
        
        Args:
            directory: Directory to scan.
        
        Returns:
            Dictionary mapping full hash to list of duplicate paths.
        """
        duplicates: Dict[str, List[Path]] = {}

        for file_path in directory.rglob('*'):
            if file_path.is_file():
                result = self.check_duplicate(file_path)

                if result.status == DuplicateStatus.EXACT_DUPLICATE:
                    hash_key = result.full_hash
                    if hash_key not in duplicates:
                        # Include the original file
                        duplicates[hash_key] = [result.duplicate_of]
                    duplicates[hash_key].append(file_path)

        return duplicates

    def get_stats(self) -> dict:
        """Get deduplication statistics.
        
        Returns:
            Dictionary with index statistics.
        """
        return {
            "unique_sizes": len(self._size_index),
            "unique_partial_hashes": len(self._partial_hash_index),
            "unique_full_hashes": len(self._full_hash_index),
            "total_files": sum(len(v) for v in self._size_index.values()),
        }

    def clear(self) -> None:
        """Clear all indexes."""
        self._size_index.clear()
        self._files_pending_partial.clear()
        self._partial_hash_index.clear()
        self._full_hash_index.clear()
        self._path_to_partial_hash.clear()
        self._path_to_full_hash.clear()
