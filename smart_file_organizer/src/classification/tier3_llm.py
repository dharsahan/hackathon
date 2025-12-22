"""
Tier 3 - LLM Classification
===========================

Uses local LLM (Ollama) for semantic document classification.
Highest accuracy tier in the classification pipeline.
"""

from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
import json
import re

from src.classification.tier1_metadata import ClassificationResult
from src.config.categories import FileCategory
from src.utils.logging_config import get_logger
from src.utils.exceptions import ClassificationError

logger = get_logger(__name__)

# Lazy import for ollama
ollama = None


def _import_ollama():
    """Lazy import ollama."""
    global ollama
    if ollama is None:
        try:
            import ollama as _ollama
            ollama = _ollama
        except ImportError:
            ollama = False
    return ollama


@dataclass
class LLMResponse:
    """Response from LLM classification.
    
    Attributes:
        category: Classified category.
        subcategory: More specific subcategory.
        summary: Brief summary of document content.
        document_date: Detected document date.
        is_sensitive: Whether document contains sensitive data.
        confidence: Model's confidence in classification.
        keywords: Extracted keywords.
        suggested_name: Suggested descriptive filename.
    """
    category: str
    subcategory: Optional[str] = None
    summary: Optional[str] = None
    document_date: Optional[str] = None
    is_sensitive: bool = False
    confidence: float = 0.8
    keywords: List[str] = None
    suggested_name: Optional[str] = None
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category,
            "subcategory": self.subcategory,
            "summary": self.summary,
            "document_date": self.document_date,
            "is_sensitive": self.is_sensitive,
            "confidence": self.confidence,
            "keywords": self.keywords,
            "suggested_name": self.suggested_name,
        }


class PromptTemplates:
    """Prompt templates for LLM classification."""
    
    SYSTEM_PROMPT = """You are an expert file archivist and document classifier.
Your task is to analyze document content and classify it accurately.
You must respond with ONLY valid JSON - no other text, explanations, or formatting."""

    CLASSIFICATION_PROMPT = """Analyze this document excerpt and classify it accurately.

DOCUMENT TEXT:
\"\"\"
{text}
\"\"\"

AVAILABLE CATEGORIES:
- Finance: Tax documents, bank statements, invoices, receipts, financial reports
- Medical: Medical records, prescriptions, lab results, insurance claims
- Legal: Contracts, agreements, legal notices, court documents
- Personal: Personal correspondence, IDs, certificates, personal records
- Work: Work projects, reports, presentations, business documents
- Education: Academic papers, transcripts, certificates, coursework
- Receipts: Purchase receipts, order confirmations
- Insurance: Insurance policies, claims, coverage documents
- Other: Documents that don't fit other categories

Respond with ONLY this JSON structure (no other text):
{{
    "category": "category_name",
    "subcategory": "specific document type",
    "summary": "5-10 word summary of document content",
    "document_date": "YYYY-MM-DD or null if not found",
    "is_sensitive": true/false,
    "confidence": 0.0-1.0,
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "suggested_name": "descriptive_filename"
}}"""

    SIMPLE_PROMPT = """Classify this document excerpt into one of these categories:
Finance, Medical, Legal, Personal, Work, Education, Receipts, Insurance, Other

Document:
{text}

Respond with only JSON: {{"category": "category_name", "is_sensitive": true/false, "confidence": 0.0-1.0}}"""


class Tier3LLMClassifier:
    """Tier 3 - LLM-based semantic classifier.
    
    Uses local Ollama models for accurate document classification.
    Falls back gracefully if LLM is unavailable.
    """
    
    # Category mapping from LLM response to FileCategory
    LLM_TO_CATEGORY = {
        "finance": FileCategory.DOCUMENTS,
        "medical": FileCategory.DOCUMENTS,
        "legal": FileCategory.DOCUMENTS,
        "personal": FileCategory.DOCUMENTS,
        "work": FileCategory.DOCUMENTS,
        "education": FileCategory.DOCUMENTS,
        "receipts": FileCategory.DOCUMENTS,
        "insurance": FileCategory.DOCUMENTS,
        "other": FileCategory.DOCUMENTS,
    }
    
    def __init__(
        self,
        model: str = "llama3",
        max_text_length: int = 2000,
        temperature: float = 0.1,
        timeout: int = 30
    ):
        """Initialize LLM classifier.
        
        Args:
            model: Ollama model name.
            max_text_length: Maximum text length to send to LLM.
            temperature: LLM temperature (lower = more deterministic).
            timeout: Request timeout in seconds.
        """
        self.model = model
        self.max_text_length = max_text_length
        self.temperature = temperature
        self.timeout = timeout
        self.templates = PromptTemplates()
    
    def is_available(self) -> bool:
        """Check if LLM is available.
        
        Returns:
            True if Ollama is running and model is available.
        """
        ollama = _import_ollama()
        if not ollama or ollama is False:
            return False
        
        try:
            models = ollama.list()
            model_names = [m.get('name', '') for m in models.get('models', [])]
            # Check if our model or a variant is available
            return any(
                self.model in name or name.startswith(self.model)
                for name in model_names
            )
        except Exception as e:
            logger.debug(f"Ollama not available: {e}")
            return False
    
    def list_models(self) -> List[str]:
        """List available Ollama models.
        
        Returns:
            List of available model names.
        """
        ollama = _import_ollama()
        if not ollama or ollama is False:
            return []
        
        try:
            models = ollama.list()
            return [m.get('name', '') for m in models.get('models', [])]
        except:
            return []
    
    def classify(
        self,
        text: str,
        use_simple_prompt: bool = False
    ) -> Optional[LLMResponse]:
        """Classify document using LLM.
        
        Args:
            text: Document text to classify.
            use_simple_prompt: Use simpler prompt for faster classification.
        
        Returns:
            LLMResponse if successful, None if failed.
        """
        ollama = _import_ollama()
        if not ollama or ollama is False:
            logger.warning("Ollama not available for classification")
            return None
        
        # Truncate text to max length
        truncated = text[:self.max_text_length]
        if len(text) > self.max_text_length:
            truncated += "\n[...text truncated...]"
        
        # Select prompt
        if use_simple_prompt:
            prompt = self.templates.SIMPLE_PROMPT.format(text=truncated)
        else:
            prompt = self.templates.CLASSIFICATION_PROMPT.format(text=truncated)
        
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': self.templates.SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt}
                ],
                options={
                    'temperature': self.temperature,
                    'num_predict': 512,
                }
            )
            
            content = response['message']['content']
            return self._parse_response(content)
            
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return None
    
    def _parse_response(self, response_text: str) -> Optional[LLMResponse]:
        """Parse LLM response into structured format.
        
        Args:
            response_text: Raw LLM response.
        
        Returns:
            LLMResponse if parsing succeeded.
        """
        # Try to find JSON in response
        # First try to parse the whole response
        try:
            data = json.loads(response_text.strip())
            return self._create_response(data)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from response
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return self._create_response(data)
            except json.JSONDecodeError:
                pass
        
        # Try to extract nested JSON (handles escaped content)
        json_match = re.search(
            r'\{(?:[^{}]|\{[^{}]*\})*\}',
            response_text,
            re.DOTALL
        )
        if json_match:
            try:
                data = json.loads(json_match.group())
                return self._create_response(data)
            except json.JSONDecodeError:
                pass
        
        logger.warning(f"Could not parse LLM response: {response_text[:200]}")
        return None
    
    def _create_response(self, data: dict) -> LLMResponse:
        """Create LLMResponse from parsed data.
        
        Args:
            data: Parsed JSON data.
        
        Returns:
            LLMResponse object.
        """
        return LLMResponse(
            category=data.get('category', 'Other'),
            subcategory=data.get('subcategory'),
            summary=data.get('summary'),
            document_date=data.get('document_date'),
            is_sensitive=bool(data.get('is_sensitive', False)),
            confidence=float(data.get('confidence', 0.8)),
            keywords=data.get('keywords', []),
            suggested_name=data.get('suggested_name'),
        )
    
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
            ClassificationResult with LLM classification.
        """
        llm_response = self.classify(text)
        
        if not llm_response:
            if tier1_result:
                tier1_result.classification_tier = 3
                tier1_result.metadata['llm_failed'] = True
                return tier1_result
            return ClassificationResult(
                category=FileCategory.DOCUMENTS,
                subcategory="Unknown",
                classification_tier=3,
                confidence=0.5,
                metadata={'llm_failed': True}
            )
        
        # Map LLM category to FileCategory
        category = self.LLM_TO_CATEGORY.get(
            llm_response.category.lower(),
            FileCategory.DOCUMENTS
        )
        
        return ClassificationResult(
            category=category,
            subcategory=f"{llm_response.category}/{llm_response.subcategory or 'General'}",
            confidence=llm_response.confidence,
            classification_tier=3,
            is_sensitive=llm_response.is_sensitive,
            needs_deeper_analysis=False,
            metadata={
                'llm_summary': llm_response.summary,
                'document_date': llm_response.document_date,
                'keywords': llm_response.keywords,
                'suggested_name': llm_response.suggested_name,
            },
            suggested_folder=f"Documents/{llm_response.category}/{llm_response.subcategory or 'General'}"
        )
