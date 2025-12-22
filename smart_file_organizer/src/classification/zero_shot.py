"""
Zero-Shot Classification
========================

Fallback classifier using HuggingFace transformers for zero-shot classification.
Used when LLM is not available.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from src.classification.tier1_metadata import ClassificationResult
from src.config.categories import FileCategory
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Lazy imports for heavy ML libraries
pipeline = None
transformers = None


def _import_transformers():
    """Lazy import transformers."""
    global pipeline
    if pipeline is None:
        try:
            from transformers import pipeline as _pipeline
            pipeline = _pipeline
        except ImportError:
            pipeline = False
    return pipeline


@dataclass
class ZeroShotResult:
    """Result from zero-shot classification.
    
    Attributes:
        labels: List of predicted labels.
        scores: List of corresponding scores.
        best_label: Highest scoring label.
        best_score: Highest score.
    """
    labels: List[str]
    scores: List[float]
    best_label: str
    best_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "labels": self.labels,
            "scores": self.scores,
            "best_label": self.best_label,
            "best_score": self.best_score,
        }


class ZeroShotClassifier:
    """Zero-shot classifier using transformers.
    
    Uses pretrained NLI models for classification without task-specific training.
    """
    
    # Default candidate labels for document classification
    DEFAULT_LABELS = [
        "financial document",
        "medical record",
        "legal document",
        "personal correspondence",
        "work document",
        "educational material",
        "receipt or invoice",
        "insurance document",
        "technical documentation",
        "other document",
    ]
    
    # Label to category mapping
    LABEL_TO_CATEGORY = {
        "financial document": ("Finance", "Financial"),
        "medical record": ("Medical", "Medical Record"),
        "legal document": ("Legal", "Legal"),
        "personal correspondence": ("Personal", "Correspondence"),
        "work document": ("Work", "Business"),
        "educational material": ("Education", "Academic"),
        "receipt or invoice": ("Finance", "Receipts"),
        "insurance document": ("Insurance", "Insurance"),
        "technical documentation": ("Work", "Technical"),
        "other document": ("Other", "General"),
    }
    
    # Sensitivity labels
    SENSITIVE_LABELS = {
        "medical record",
        "financial document",
        "legal document",
        "insurance document",
    }
    
    def __init__(
        self,
        model: str = "facebook/bart-large-mnli",
        device: int = -1,  # -1 for CPU, 0 for GPU
        max_length: int = 512
    ):
        """Initialize zero-shot classifier.
        
        Args:
            model: HuggingFace model name.
            device: Device to use (-1 for CPU).
            max_length: Maximum sequence length.
        """
        self.model_name = model
        self.device = device
        self.max_length = max_length
        self._classifier = None
        self._is_loaded = False
    
    def _load_model(self) -> bool:
        """Load the classification model.
        
        Returns:
            True if model loaded successfully.
        """
        if self._is_loaded:
            return self._classifier is not None
        
        pipeline = _import_transformers()
        if not pipeline or pipeline is False:
            logger.warning("Transformers library not available")
            self._is_loaded = True
            return False
        
        try:
            logger.info(f"Loading zero-shot model: {self.model_name}")
            self._classifier = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                device=self.device
            )
            self._is_loaded = True
            logger.info("Zero-shot model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load zero-shot model: {e}")
            self._is_loaded = True
            return False
    
    def is_available(self) -> bool:
        """Check if classifier is available.
        
        Returns:
            True if model can be loaded.
        """
        return self._load_model()
    
    def classify(
        self,
        text: str,
        candidate_labels: Optional[List[str]] = None,
        multi_label: bool = False
    ) -> Optional[ZeroShotResult]:
        """Classify text using zero-shot classification.
        
        Args:
            text: Text to classify.
            candidate_labels: Labels to classify against.
            multi_label: Allow multiple labels.
        
        Returns:
            ZeroShotResult if successful.
        """
        if not self._load_model():
            return None
        
        if not text or not text.strip():
            return None
        
        labels = candidate_labels or self.DEFAULT_LABELS
        
        # Truncate text if needed
        if len(text) > self.max_length * 4:  # Rough character limit
            text = text[:self.max_length * 4]
        
        try:
            result = self._classifier(
                text,
                candidate_labels=labels,
                multi_label=multi_label
            )
            
            return ZeroShotResult(
                labels=result['labels'],
                scores=result['scores'],
                best_label=result['labels'][0],
                best_score=result['scores'][0]
            )
        except Exception as e:
            logger.error(f"Zero-shot classification failed: {e}")
            return None
    
    def classify_with_result(
        self,
        text: str,
        tier1_result: Optional[ClassificationResult] = None
    ) -> ClassificationResult:
        """Classify and return as ClassificationResult.
        
        Args:
            text: Document text.
            tier1_result: Optional previous tier result.
        
        Returns:
            ClassificationResult with zero-shot classification.
        """
        zs_result = self.classify(text)
        
        if not zs_result:
            if tier1_result:
                tier1_result.metadata['zero_shot_failed'] = True
                return tier1_result
            return ClassificationResult(
                category=FileCategory.DOCUMENTS,
                subcategory="Unknown",
                confidence=0.5,
                classification_tier=3,
                metadata={'zero_shot_failed': True}
            )
        
        # Map best label to category
        category_info = self.LABEL_TO_CATEGORY.get(
            zs_result.best_label,
            ("Other", "General")
        )
        
        is_sensitive = zs_result.best_label in self.SENSITIVE_LABELS
        
        return ClassificationResult(
            category=FileCategory.DOCUMENTS,
            subcategory=f"{category_info[0]}/{category_info[1]}",
            confidence=zs_result.best_score,
            classification_tier=3,
            is_sensitive=is_sensitive,
            needs_deeper_analysis=False,
            metadata={
                'zero_shot_label': zs_result.best_label,
                'all_labels': dict(zip(zs_result.labels[:5], zs_result.scores[:5])),
            },
            suggested_folder=f"Documents/{category_info[0]}/{category_info[1]}"
        )
    
    def classify_sensitivity(self, text: str) -> tuple:
        """Classify document sensitivity level.
        
        Args:
            text: Document text.
        
        Returns:
            Tuple of (is_sensitive, sensitivity_score, sensitivity_type).
        """
        sensitivity_labels = [
            "contains personal identifiable information",
            "contains financial information",
            "contains medical information",
            "contains legal information",
            "contains confidential business information",
            "contains public or general information",
        ]
        
        result = self.classify(text, sensitivity_labels)
        
        if not result:
            return False, 0.0, None
        
        # "public or general information" is not sensitive
        if result.best_label == "contains public or general information":
            return False, 1.0 - result.best_score, None
        
        is_sensitive = result.best_score > 0.5
        return is_sensitive, result.best_score, result.best_label
