"""
Perceptual Hashing
==================

Image similarity detection using perceptual hashing.
Finds visually similar images even with slight modifications.
"""

from pathlib import Path
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass, field
from enum import Enum

from src.utils.logging_config import get_logger
from src.utils.exceptions import DeduplicationError

logger = get_logger(__name__)

# Lazy imports for heavy libraries
imagehash = None
Image = None


def _import_imagehash():
    """Lazy import imagehash."""
    global imagehash, Image
    if imagehash is None:
        try:
            import imagehash as _imagehash
            from PIL import Image as _Image
            imagehash = _imagehash
            Image = _Image
        except ImportError:
            imagehash = False
            Image = False
    return imagehash, Image


class HashType(Enum):
    """Types of perceptual hashes."""
    PHASH = "phash"  # Perceptual hash (DCT-based)
    DHASH = "dhash"  # Difference hash
    AHASH = "ahash"  # Average hash
    WHASH = "whash"  # Wavelet hash


@dataclass
class PerceptualHashResult:
    """Result of perceptual hash computation.
    
    Attributes:
        file_path: Path to the image.
        hash_value: Computed hash as hex string.
        hash_type: Type of hash used.
        similar_files: List of (path, distance) for similar images.
        is_duplicate: Whether this is a near-duplicate.
    """
    file_path: Path
    hash_value: str
    hash_type: HashType = HashType.PHASH
    similar_files: List[Tuple[Path, int]] = field(default_factory=list)
    is_duplicate: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "file_path": str(self.file_path),
            "hash_value": self.hash_value,
            "hash_type": self.hash_type.value,
            "similar_files": [
                {"path": str(p), "distance": d}
                for p, d in self.similar_files
            ],
            "is_duplicate": self.is_duplicate,
        }


class PerceptualHashEngine:
    """Perceptual hashing engine for image similarity.
    
    Uses perceptual hashes to find visually similar images,
    even if they have been resized, compressed, or slightly modified.
    """
    
    # Supported image extensions
    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp',
        '.webp', '.tiff', '.tif'
    }
    
    def __init__(
        self,
        threshold: int = 5,
        hash_size: int = 8,
        hash_type: HashType = HashType.PHASH
    ):
        """Initialize perceptual hash engine.
        
        Args:
            threshold: Maximum Hamming distance for similarity (0-64).
                       Lower = stricter matching.
            hash_size: Size of hash (default 8 produces 64-bit hash).
            hash_type: Type of perceptual hash to use.
        """
        self.threshold = threshold
        self.hash_size = hash_size
        self.hash_type = hash_type
        
        # Index for quick similarity lookup
        self._hash_index: Dict[Path, str] = {}
    
    def is_supported(self, file_path: Path) -> bool:
        """Check if file is a supported image format.
        
        Args:
            file_path: Path to check.
        
        Returns:
            True if file is a supported image.
        """
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
    
    def compute_hash(self, image_path: Path) -> str:
        """Compute perceptual hash of an image.
        
        Args:
            image_path: Path to the image.
        
        Returns:
            Hash as hexadecimal string.
        
        Raises:
            DeduplicationError: If image cannot be processed.
        """
        imagehash_lib, PIL_Image = _import_imagehash()
        
        if not imagehash_lib or imagehash_lib is False:
            raise DeduplicationError(
                "imagehash library not available",
                file_path=str(image_path),
                hash_type="perceptual"
            )
        
        try:
            img = PIL_Image.open(image_path)
            
            # Compute hash based on type
            if self.hash_type == HashType.PHASH:
                hash_value = imagehash_lib.phash(img, hash_size=self.hash_size)
            elif self.hash_type == HashType.DHASH:
                hash_value = imagehash_lib.dhash(img, hash_size=self.hash_size)
            elif self.hash_type == HashType.AHASH:
                hash_value = imagehash_lib.average_hash(img, hash_size=self.hash_size)
            elif self.hash_type == HashType.WHASH:
                hash_value = imagehash_lib.whash(img, hash_size=self.hash_size)
            else:
                hash_value = imagehash_lib.phash(img, hash_size=self.hash_size)
            
            img.close()
            return str(hash_value)
            
        except Exception as e:
            raise DeduplicationError(
                f"Failed to compute perceptual hash: {e}",
                file_path=str(image_path),
                hash_type="perceptual"
            )
    
    def find_similar(self, image_path: Path) -> PerceptualHashResult:
        """Find similar images in the index.
        
        Args:
            image_path: Path to the image to check.
        
        Returns:
            PerceptualHashResult with similar images.
        """
        imagehash_lib, _ = _import_imagehash()
        
        if not imagehash_lib or imagehash_lib is False:
            logger.warning("imagehash not available, skipping perceptual hashing")
            return PerceptualHashResult(
                file_path=image_path,
                hash_value="",
                is_duplicate=False
            )
        
        # Compute hash for input image
        current_hash_str = self.compute_hash(image_path)
        current_hash = imagehash_lib.hex_to_hash(current_hash_str)
        
        similar = []
        
        # Compare against all indexed images
        for stored_path, stored_hash_str in self._hash_index.items():
            stored_hash = imagehash_lib.hex_to_hash(stored_hash_str)
            distance = current_hash - stored_hash  # Hamming distance
            
            if distance <= self.threshold:
                similar.append((stored_path, distance))
        
        # Sort by distance (most similar first)
        similar.sort(key=lambda x: x[1])
        
        # Add to index
        self._hash_index[image_path] = current_hash_str
        
        is_duplicate = len(similar) > 0 and similar[0][1] <= 2
        
        result = PerceptualHashResult(
            file_path=image_path,
            hash_value=current_hash_str,
            hash_type=self.hash_type,
            similar_files=similar,
            is_duplicate=is_duplicate
        )
        
        if similar:
            logger.info(
                f"Found {len(similar)} similar image(s) for {image_path.name}, "
                f"closest distance: {similar[0][1]}"
            )
        
        return result
    
    def add_to_index(self, image_path: Path) -> str:
        """Add image to index without checking for duplicates.
        
        Args:
            image_path: Path to image.
        
        Returns:
            Computed hash.
        """
        hash_value = self.compute_hash(image_path)
        self._hash_index[image_path] = hash_value
        return hash_value
    
    def compare_images(
        self,
        image1: Path,
        image2: Path
    ) -> Tuple[int, bool]:
        """Compare two images for similarity.
        
        Args:
            image1: First image path.
            image2: Second image path.
        
        Returns:
            Tuple of (distance, is_similar).
        """
        imagehash_lib, _ = _import_imagehash()
        
        if not imagehash_lib or imagehash_lib is False:
            return -1, False
        
        hash1 = imagehash_lib.hex_to_hash(self.compute_hash(image1))
        hash2 = imagehash_lib.hex_to_hash(self.compute_hash(image2))
        
        distance = hash1 - hash2
        is_similar = distance <= self.threshold
        
        return distance, is_similar
    
    def find_duplicates_in_directory(
        self,
        directory: Path
    ) -> Dict[str, List[Path]]:
        """Find all similar images in a directory.
        
        Args:
            directory: Directory to scan.
        
        Returns:
            Dictionary mapping hash to list of similar image paths.
        """
        duplicates: Dict[str, List[Path]] = {}
        
        for file_path in directory.rglob('*'):
            if file_path.is_file() and self.is_supported(file_path):
                try:
                    result = self.find_similar(file_path)
                    
                    if result.is_duplicate and result.similar_files:
                        # Group by closest match
                        key = self._hash_index.get(result.similar_files[0][0], "")
                        if key:
                            if key not in duplicates:
                                duplicates[key] = [result.similar_files[0][0]]
                            duplicates[key].append(file_path)
                            
                except Exception as e:
                    logger.warning(f"Error processing {file_path}: {e}")
        
        return duplicates
    
    def get_stats(self) -> dict:
        """Get engine statistics.
        
        Returns:
            Dictionary with index statistics.
        """
        return {
            "indexed_images": len(self._hash_index),
            "hash_type": self.hash_type.value,
            "threshold": self.threshold,
        }
    
    def clear(self) -> None:
        """Clear the hash index."""
        self._hash_index.clear()
