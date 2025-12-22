"""
Tier 1 - Metadata Classification
================================

Fast classification based on file extension and MIME type.
This is the first tier in the classification pipeline.
"""

from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from src.config.categories import FileCategory, CATEGORY_MAPPING
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Lazy import for python-magic
magic = None


def _import_magic():
    """Lazy import python-magic."""
    global magic
    if magic is None:
        try:
            import magic as _magic
            magic = _magic
        except ImportError:
            magic = False
    return magic


@dataclass
class ClassificationResult:
    """Result of file classification.
    
    Attributes:
        category: Main file category.
        subcategory: More specific subcategory.
        confidence: Confidence score (0.0 to 1.0).
        classification_tier: Which tier produced this result (1, 2, or 3).
        is_sensitive: Whether file may contain sensitive data.
        needs_deeper_analysis: If true, should proceed to higher tiers.
        metadata: Additional classification metadata.
        suggested_folder: Suggested destination folder name.
    """
    category: FileCategory
    subcategory: Optional[str] = None
    confidence: float = 1.0
    classification_tier: int = 1
    is_sensitive: bool = False
    needs_deeper_analysis: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    suggested_folder: Optional[str] = None
    
    def __post_init__(self):
        """Set suggested folder based on category."""
        if self.suggested_folder is None:
            if self.subcategory:
                self.suggested_folder = f"{self.category.value}/{self.subcategory}"
            else:
                self.suggested_folder = self.category.value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "subcategory": self.subcategory,
            "confidence": self.confidence,
            "tier": self.classification_tier,
            "is_sensitive": self.is_sensitive,
            "needs_deeper_analysis": self.needs_deeper_analysis,
            "suggested_folder": self.suggested_folder,
            "metadata": self.metadata,
        }


class Tier1Classifier:
    """Tier 1 - Extension and MIME type based classifier.
    
    Fast classification using file extension mapping and MIME type detection.
    This is always the first step in the classification pipeline.
    """
    
    # Extensions that should trigger content analysis
    NEEDS_CONTENT_ANALYSIS = {
        '.pdf', '.docx', '.doc', '.txt', '.md', '.rtf'
    }
    
    # Potentially sensitive file types
    POTENTIALLY_SENSITIVE = {
        '.pdf', '.docx', '.doc', '.xlsx', '.xls', '.csv',
        '.pptx', '.ppt', '.odt', '.ods'
    }
    
    def __init__(self, category_mapping=None):
        """Initialize Tier 1 classifier.
        
        Args:
            category_mapping: Custom category mapping. Uses default if None.
        """
        self.category_mapping = category_mapping or CATEGORY_MAPPING
        self._magic = None
    
    def _get_magic(self):
        """Get magic instance for MIME detection."""
        if self._magic is None:
            magic = _import_magic()
            if magic and magic is not False:
                try:
                    self._magic = magic.Magic(mime=True)
                except Exception as e:
                    logger.warning(f"Failed to initialize python-magic: {e}")
                    self._magic = False
            else:
                self._magic = False
        return self._magic if self._magic is not False else None
    
    def classify(self, file_path: Path) -> ClassificationResult:
        """Classify a file based on extension and MIME type.
        
        Args:
            file_path: Path to the file.
        
        Returns:
            ClassificationResult with category and metadata.
        """
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        # Get category from extension mapping
        category, subcategory = self.category_mapping.get_category(extension)
        
        # Get MIME type for validation
        mime_type = self._detect_mime_type(file_path)
        
        # Validate MIME type matches extension category
        if mime_type:
            validated = self._validate_mime(mime_type, category)
            if not validated:
                logger.warning(
                    f"MIME/extension mismatch: {file_path.name} - "
                    f"extension suggests {category.value}, MIME is {mime_type}"
                )
        
        # Determine if deeper analysis needed
        needs_deeper = self._needs_deeper_analysis(extension, category)
        
        # Check if potentially sensitive
        is_sensitive = extension in self.POTENTIALLY_SENSITIVE
        
        result = ClassificationResult(
            category=category,
            subcategory=subcategory,
            confidence=1.0 if category != FileCategory.UNKNOWN else 0.5,
            classification_tier=1,
            is_sensitive=is_sensitive,
            needs_deeper_analysis=needs_deeper,
            metadata={
                "extension": extension,
                "mime_type": mime_type,
                "file_size": file_path.stat().st_size if file_path.exists() else 0,
            }
        )
        
        logger.debug(
            f"Tier 1 classification: {file_path.name} -> "
            f"{category.value}/{subcategory or 'N/A'}"
        )
        
        return result
    
    def _detect_mime_type(self, file_path: Path) -> Optional[str]:
        """Detect MIME type using python-magic.
        
        Args:
            file_path: Path to the file.
        
        Returns:
            MIME type string or None.
        """
        magic_instance = self._get_magic()
        if magic_instance and file_path.exists():
            try:
                return magic_instance.from_file(str(file_path))
            except Exception as e:
                logger.debug(f"MIME detection failed: {e}")
        return None
    
    def _validate_mime(self, mime_type: str, category: FileCategory) -> bool:
        """Validate that MIME type matches the expected category.
        
        Args:
            mime_type: Detected MIME type.
            category: Expected category from extension.
        
        Returns:
            True if they match.
        """
        mime_category_map = {
            'image/': FileCategory.IMAGES,
            'audio/': FileCategory.AUDIO,
            'video/': FileCategory.VIDEO,
            'text/': FileCategory.DOCUMENTS,
            'application/pdf': FileCategory.DOCUMENTS,
            'application/msword': FileCategory.DOCUMENTS,
            'application/vnd.': FileCategory.DOCUMENTS,
            'application/zip': FileCategory.ARCHIVES,
            'application/x-rar': FileCategory.ARCHIVES,
            'application/x-7z': FileCategory.ARCHIVES,
            'application/x-executable': FileCategory.INSTALLERS,
        }
        
        for prefix, expected_category in mime_category_map.items():
            if mime_type.startswith(prefix):
                return category == expected_category
        
        return True  # Unknown MIME types pass validation
    
    def _needs_deeper_analysis(
        self,
        extension: str,
        category: FileCategory
    ) -> bool:
        """Determine if file should be analyzed by higher tiers.
        
        Args:
            extension: File extension.
            category: Detected category.
        
        Returns:
            True if deeper analysis recommended.
        """
        # Unknown files always need deeper analysis
        if category == FileCategory.UNKNOWN:
            return True
        
        # Documents may need content analysis
        if extension in self.NEEDS_CONTENT_ANALYSIS:
            return True
        
        return False
    
    def is_document(self, file_path: Path) -> bool:
        """Check if file is a document type.
        
        Args:
            file_path: Path to check.
        
        Returns:
            True if file is a document.
        """
        result = self.classify(file_path)
        return result.category == FileCategory.DOCUMENTS
    
    def is_image(self, file_path: Path) -> bool:
        """Check if file is an image.
        
        Args:
            file_path: Path to check.
        
        Returns:
            True if file is an image.
        """
        result = self.classify(file_path)
        return result.category == FileCategory.IMAGES
