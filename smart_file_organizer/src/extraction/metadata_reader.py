"""
Metadata Reader
===============

Extracts metadata from files including EXIF data, file system info,
and format-specific metadata.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
import stat

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Lazy imports
PIL_Image = None
magic = None


def _import_pil():
    """Lazy import PIL."""
    global PIL_Image
    if PIL_Image is None:
        from PIL import Image
        PIL_Image = Image
    return PIL_Image


def _import_magic():
    """Lazy import python-magic."""
    global magic
    if magic is None:
        import magic as _magic
        magic = _magic
    return magic


@dataclass
class FileMetadata:
    """Container for file metadata.
    
    Attributes:
        file_path: Path to the file.
        file_name: Name of the file.
        extension: File extension.
        size_bytes: File size in bytes.
        created_at: Creation timestamp.
        modified_at: Last modification timestamp.
        accessed_at: Last access timestamp.
        mime_type: MIME type of the file.
        permissions: File permissions string.
        is_hidden: Whether file is hidden.
        extra: Additional format-specific metadata.
    """
    file_path: str
    file_name: str
    extension: str
    size_bytes: int
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    accessed_at: Optional[datetime] = None
    mime_type: Optional[str] = None
    permissions: Optional[str] = None
    is_hidden: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def size_human(self) -> str:
        """Get human-readable file size."""
        size = self.size_bytes
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "size_human": self.size_human,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "accessed_at": self.accessed_at.isoformat() if self.accessed_at else None,
            "mime_type": self.mime_type,
            "permissions": self.permissions,
            "is_hidden": self.is_hidden,
            "extra": self.extra,
        }


class MetadataReader:
    """Reads metadata from various file types.
    
    Extracts file system metadata, MIME types, and format-specific
    information like EXIF data for images.
    """

    def __init__(self, extract_exif: bool = True):
        """Initialize metadata reader.
        
        Args:
            extract_exif: Whether to extract EXIF data from images.
        """
        self.extract_exif = extract_exif
        self._magic = None

    def _get_magic(self):
        """Get magic instance for MIME detection."""
        if self._magic is None:
            try:
                magic = _import_magic()
                self._magic = magic.Magic(mime=True)
            except Exception as e:
                logger.warning(f"python-magic not available: {e}")
                self._magic = False
        return self._magic

    def read(self, file_path: Path) -> FileMetadata:
        """Read metadata from a file.
        
        Args:
            file_path: Path to the file.
        
        Returns:
            FileMetadata object with extracted information.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        stat_info = file_path.stat()

        # Basic file info
        metadata = FileMetadata(
            file_path=str(file_path.absolute()),
            file_name=file_path.name,
            extension=file_path.suffix.lower(),
            size_bytes=stat_info.st_size,
            is_hidden=file_path.name.startswith('.'),
        )

        # Timestamps
        try:
            metadata.created_at = datetime.fromtimestamp(stat_info.st_ctime)
            metadata.modified_at = datetime.fromtimestamp(stat_info.st_mtime)
            metadata.accessed_at = datetime.fromtimestamp(stat_info.st_atime)
        except (OSError, ValueError) as e:
            logger.debug(f"Could not read timestamps: {e}")

        # Permissions
        try:
            mode = stat_info.st_mode
            metadata.permissions = stat.filemode(mode)
        except Exception:
            pass

        # MIME type
        try:
            magic_instance = self._get_magic()
            if magic_instance:
                metadata.mime_type = magic_instance.from_file(str(file_path))
        except Exception as e:
            logger.debug(f"Could not detect MIME type: {e}")

        # Format-specific metadata
        if self.extract_exif and metadata.extension in {
            '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.heic'
        }:
            exif = self._extract_exif(file_path)
            if exif:
                metadata.extra['exif'] = exif

        return metadata

    def _extract_exif(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Extract EXIF data from an image.
        
        Args:
            file_path: Path to image file.
        
        Returns:
            Dictionary of EXIF data, or None.
        """
        try:
            Image = _import_pil()
            img = Image.open(file_path)

            # Get basic image info
            exif_data = {
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'mode': img.mode,
            }

            # Try to get EXIF data
            if hasattr(img, '_getexif') and img._getexif():
                from PIL.ExifTags import TAGS
                raw_exif = img._getexif()

                # Extract useful EXIF tags
                useful_tags = {
                    'Make', 'Model', 'DateTime', 'DateTimeOriginal',
                    'ExposureTime', 'FNumber', 'ISOSpeedRatings',
                    'FocalLength', 'GPSInfo', 'Software', 'Orientation'
                }

                for tag_id, value in raw_exif.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    if tag_name in useful_tags:
                        # Convert to string for JSON serialization
                        if hasattr(value, 'denominator'):  # Rational number
                            value = float(value)
                        elif isinstance(value, bytes):
                            try:
                                value = value.decode('utf-8', errors='replace')
                            except (UnicodeDecodeError, AttributeError):
                                value = str(value)
                        exif_data[tag_name] = value

            img.close()
            return exif_data

        except Exception as e:
            logger.debug(f"Could not extract EXIF data: {e}")
            return None

    def get_checksum(self, file_path: Path, algorithm: str = 'sha256') -> str:
        """Calculate file checksum.
        
        Args:
            file_path: Path to file.
            algorithm: Hash algorithm ('sha256', 'md5', 'sha1').
        
        Returns:
            Hexadecimal checksum string.
        """
        import hashlib

        hasher = hashlib.new(algorithm)

        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)

        return hasher.hexdigest()
