"""
Category Definitions
====================

Defines file categories, subcategories, and extension mappings for classification.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Set


class FileCategory(Enum):
    """Main file categories for organization."""
    DOCUMENTS = "Documents"
    IMAGES = "Images"
    AUDIO = "Audio"
    VIDEO = "Video"
    ARCHIVES = "Archives"
    INSTALLERS = "Installers"
    CODE = "Code"
    DATA = "Data"
    EBOOKS = "Ebooks"
    FONTS = "Fonts"
    UNKNOWN = "Unknown"


class DocumentSubcategory(Enum):
    """Document subcategories for deeper classification."""
    PDF = "PDF"
    WORD = "Word"
    EXCEL = "Excel"
    POWERPOINT = "PowerPoint"
    TEXT = "Text"
    SCANNED = "Scanned"
    FINANCIAL = "Financial"
    MEDICAL = "Medical"
    LEGAL = "Legal"
    RECEIPTS = "Receipts"
    INVOICES = "Invoices"
    CONTRACTS = "Contracts"
    PERSONAL = "Personal"
    WORK = "Work"


class ImageSubcategory(Enum):
    """Image subcategories."""
    PHOTO = "Photos"
    SCREENSHOT = "Screenshots"
    ARTWORK = "Artwork"
    ICON = "Icons"
    DIAGRAM = "Diagrams"
    RAW = "RAW"


class AudioSubcategory(Enum):
    """Audio subcategories."""
    MUSIC = "Music"
    PODCAST = "Podcasts"
    AUDIOBOOK = "Audiobooks"
    VOICE_MEMO = "Voice Memos"
    SOUND_EFFECT = "Sound Effects"


class VideoSubcategory(Enum):
    """Video subcategories."""
    MOVIE = "Movies"
    TV_SHOW = "TV Shows"
    SCREEN_RECORDING = "Screen Recordings"
    CLIP = "Clips"


@dataclass
class CategoryMapping:
    """Mapping of file extensions to categories and subcategories.
    
    Provides comprehensive mapping for quick Tier 1 classification.
    """
    
    # Document extensions
    DOCUMENT_EXTENSIONS: Dict[str, str] = None
    
    # Image extensions
    IMAGE_EXTENSIONS: Dict[str, str] = None
    
    # Audio extensions
    AUDIO_EXTENSIONS: Dict[str, str] = None
    
    # Video extensions
    VIDEO_EXTENSIONS: Dict[str, str] = None
    
    # Archive extensions
    ARCHIVE_EXTENSIONS: Set[str] = None
    
    # Installer extensions
    INSTALLER_EXTENSIONS: Set[str] = None
    
    # Code extensions
    CODE_EXTENSIONS: Dict[str, str] = None
    
    # Data extensions
    DATA_EXTENSIONS: Dict[str, str] = None
    
    # Ebook extensions
    EBOOK_EXTENSIONS: Set[str] = None
    
    # Font extensions
    FONT_EXTENSIONS: Set[str] = None
    
    def __post_init__(self):
        """Initialize all extension mappings."""
        self.DOCUMENT_EXTENSIONS = {
            ".pdf": "PDF",
            ".doc": "Word",
            ".docx": "Word",
            ".odt": "Word",
            ".rtf": "Word",
            ".txt": "Text",
            ".md": "Text",
            ".tex": "Text",
            ".xls": "Excel",
            ".xlsx": "Excel",
            ".ods": "Excel",
            ".csv": "Excel",
            ".ppt": "PowerPoint",
            ".pptx": "PowerPoint",
            ".odp": "PowerPoint",
            ".pages": "Word",
            ".numbers": "Excel",
            ".keynote": "PowerPoint",
        }
        
        self.IMAGE_EXTENSIONS = {
            ".jpg": "Photo",
            ".jpeg": "Photo",
            ".png": "Image",
            ".gif": "Image",
            ".bmp": "Image",
            ".webp": "Image",
            ".svg": "Diagram",
            ".ico": "Icon",
            ".tiff": "Photo",
            ".tif": "Photo",
            ".heic": "Photo",
            ".heif": "Photo",
            ".raw": "RAW",
            ".cr2": "RAW",
            ".nef": "RAW",
            ".arw": "RAW",
            ".dng": "RAW",
            ".psd": "Artwork",
            ".ai": "Artwork",
            ".xcf": "Artwork",
        }
        
        self.AUDIO_EXTENSIONS = {
            ".mp3": "Music",
            ".m4a": "Music",
            ".aac": "Music",
            ".flac": "Music",
            ".wav": "Music",
            ".ogg": "Music",
            ".wma": "Music",
            ".aiff": "Music",
            ".opus": "Podcast",
            ".m4b": "Audiobook",
        }
        
        self.VIDEO_EXTENSIONS = {
            ".mp4": "Video",
            ".mov": "Video",
            ".avi": "Video",
            ".mkv": "Video",
            ".wmv": "Video",
            ".flv": "Video",
            ".webm": "Video",
            ".m4v": "Video",
            ".mpeg": "Video",
            ".mpg": "Video",
            ".3gp": "Video",
        }
        
        self.ARCHIVE_EXTENSIONS = {
            ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
            ".xz", ".tgz", ".tbz2", ".lz", ".lzma",
        }
        
        self.INSTALLER_EXTENSIONS = {
            ".exe", ".msi", ".dmg", ".pkg", ".deb",
            ".rpm", ".appimage", ".snap", ".flatpak",
        }
        
        self.CODE_EXTENSIONS = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".jsx": "JavaScript",
            ".tsx": "TypeScript",
            ".java": "Java",
            ".c": "C",
            ".cpp": "C++",
            ".h": "C",
            ".hpp": "C++",
            ".cs": "C#",
            ".go": "Go",
            ".rs": "Rust",
            ".rb": "Ruby",
            ".php": "PHP",
            ".swift": "Swift",
            ".kt": "Kotlin",
            ".scala": "Scala",
            ".r": "R",
            ".sql": "SQL",
            ".sh": "Shell",
            ".bash": "Shell",
            ".zsh": "Shell",
            ".ps1": "PowerShell",
            ".html": "Web",
            ".css": "Web",
            ".scss": "Web",
            ".sass": "Web",
            ".less": "Web",
            ".vue": "Web",
            ".svelte": "Web",
        }
        
        self.DATA_EXTENSIONS = {
            ".json": "JSON",
            ".xml": "XML",
            ".yaml": "YAML",
            ".yml": "YAML",
            ".toml": "TOML",
            ".ini": "Config",
            ".conf": "Config",
            ".cfg": "Config",
            ".env": "Config",
            ".db": "Database",
            ".sqlite": "Database",
            ".sqlite3": "Database",
            ".sql": "Database",
            ".parquet": "Data",
            ".feather": "Data",
            ".pickle": "Data",
            ".pkl": "Data",
        }
        
        self.EBOOK_EXTENSIONS = {
            ".epub", ".mobi", ".azw", ".azw3", ".fb2", ".djvu",
        }
        
        self.FONT_EXTENSIONS = {
            ".ttf", ".otf", ".woff", ".woff2", ".eot",
        }
    
    def get_category(self, extension: str) -> Tuple[FileCategory, Optional[str]]:
        """Get category and subcategory for a file extension.
        
        Args:
            extension: File extension including the dot (e.g., ".pdf").
        
        Returns:
            Tuple of (FileCategory, subcategory_string or None).
        """
        ext_lower = extension.lower()
        
        if ext_lower in self.DOCUMENT_EXTENSIONS:
            return FileCategory.DOCUMENTS, self.DOCUMENT_EXTENSIONS[ext_lower]
        
        if ext_lower in self.IMAGE_EXTENSIONS:
            return FileCategory.IMAGES, self.IMAGE_EXTENSIONS[ext_lower]
        
        if ext_lower in self.AUDIO_EXTENSIONS:
            return FileCategory.AUDIO, self.AUDIO_EXTENSIONS[ext_lower]
        
        if ext_lower in self.VIDEO_EXTENSIONS:
            return FileCategory.VIDEO, self.VIDEO_EXTENSIONS[ext_lower]
        
        if ext_lower in self.ARCHIVE_EXTENSIONS:
            return FileCategory.ARCHIVES, None
        
        if ext_lower in self.INSTALLER_EXTENSIONS:
            return FileCategory.INSTALLERS, None
        
        if ext_lower in self.CODE_EXTENSIONS:
            return FileCategory.CODE, self.CODE_EXTENSIONS[ext_lower]
        
        if ext_lower in self.DATA_EXTENSIONS:
            return FileCategory.DATA, self.DATA_EXTENSIONS[ext_lower]
        
        if ext_lower in self.EBOOK_EXTENSIONS:
            return FileCategory.EBOOKS, None
        
        if ext_lower in self.FONT_EXTENSIONS:
            return FileCategory.FONTS, None
        
        return FileCategory.UNKNOWN, None
    
    def is_document(self, extension: str) -> bool:
        """Check if extension is a document type."""
        return extension.lower() in self.DOCUMENT_EXTENSIONS
    
    def is_image(self, extension: str) -> bool:
        """Check if extension is an image type."""
        return extension.lower() in self.IMAGE_EXTENSIONS
    
    def needs_ocr(self, extension: str) -> bool:
        """Check if file type might need OCR for text extraction."""
        ext_lower = extension.lower()
        # Scanned PDFs and images might need OCR
        return ext_lower in {".pdf", ".tiff", ".tif", ".png", ".jpg", ".jpeg"}


# Global category mapping instance
CATEGORY_MAPPING = CategoryMapping()
