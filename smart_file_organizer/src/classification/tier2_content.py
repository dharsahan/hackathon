"""
Tier 2 - Content-Based Classification
======================================

Analyzes file content using pattern matching and heuristics.
Second tier in the classification pipeline.
"""

from pathlib import Path
from typing import Optional, Dict, List, Tuple
import re
from dataclasses import dataclass

from src.classification.tier1_metadata import ClassificationResult
from src.config.categories import FileCategory
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ContentPattern:
    """Pattern for content-based classification.
    
    Attributes:
        patterns: List of regex patterns to match.
        category: Category to assign if matched.
        subcategory: Subcategory to assign.
        sensitivity_boost: Extra sensitivity score if matched.
        confidence: Confidence score for this pattern.
    """
    patterns: List[str]
    category: str
    subcategory: str
    sensitivity_boost: float = 0.0
    confidence: float = 0.8


class PatternMatcher:
    """Matches content against predefined patterns."""
    
    # Financial document patterns
    FINANCIAL_PATTERNS = [
        r'\b(?:invoice|bill|receipt|payment|transaction)\b',
        r'\$[\d,]+\.?\d*',
        r'\b(?:bank|account|balance|credit|debit)\b',
        r'\b(?:tax|IRS|W-2|1099|salary|income)\b',
        r'\b(?:mortgage|loan|interest rate|principal)\b',
    ]
    
    # Medical document patterns
    MEDICAL_PATTERNS = [
        r'\b(?:patient|diagnosis|prescription|medication)\b',
        r'\b(?:doctor|physician|hospital|clinic|medical)\b',
        r'\b(?:treatment|therapy|symptoms|health)\b',
        r'\b(?:insurance claim|copay|deductible)\b',
        r'\b(?:blood pressure|heart rate|BMI|cholesterol)\b',
    ]
    
    # Legal document patterns
    LEGAL_PATTERNS = [
        r'\b(?:contract|agreement|terms|conditions)\b',
        r'\b(?:party|parties|herein|whereas|hereby)\b',
        r'\b(?:court|legal|attorney|lawyer|law firm)\b',
        r'\b(?:plaintiff|defendant|lawsuit|litigation)\b',
        r'\b(?:notarized|affidavit|deposition)\b',
    ]
    
    # Receipt patterns
    RECEIPT_PATTERNS = [
        r'\b(?:receipt|order|purchase|item|qty|quantity)\b',
        r'\b(?:subtotal|total|tax|tip|gratuity)\b',
        r'\b(?:visa|mastercard|amex|payment method)\b',
        r'\b(?:thank you for your purchase)\b',
        r'\bitem\s+\d+\b',
    ]
    
    # Invoice patterns
    INVOICE_PATTERNS = [
        r'\b(?:invoice|inv|bill to|ship to)\b',
        r'\binvoice\s*(?:#|number|no\.?)\s*\d+',
        r'\b(?:due date|payment due|net 30|net 60)\b',
        r'\b(?:amount due|balance due|please pay)\b',
    ]
    
    # Personal ID patterns
    PERSONAL_ID_PATTERNS = [
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN format
        r'\b(?:social security|SSN)\b',
        r'\b(?:passport|driver.?s? license|ID card)\b',
        r'\b(?:date of birth|DOB)\b',
    ]
    
    def __init__(self):
        """Initialize pattern matcher with compiled patterns."""
        self.pattern_sets = [
            ContentPattern(
                patterns=self.FINANCIAL_PATTERNS,
                category="Finance",
                subcategory="Financial",
                sensitivity_boost=0.3,
            ),
            ContentPattern(
                patterns=self.MEDICAL_PATTERNS,
                category="Medical",
                subcategory="Medical",
                sensitivity_boost=0.5,  # High sensitivity
            ),
            ContentPattern(
                patterns=self.LEGAL_PATTERNS,
                category="Legal",
                subcategory="Legal",
                sensitivity_boost=0.3,
            ),
            ContentPattern(
                patterns=self.RECEIPT_PATTERNS,
                category="Finance",
                subcategory="Receipts",
                sensitivity_boost=0.1,
            ),
            ContentPattern(
                patterns=self.INVOICE_PATTERNS,
                category="Finance",
                subcategory="Invoices",
                sensitivity_boost=0.2,
            ),
            ContentPattern(
                patterns=self.PERSONAL_ID_PATTERNS,
                category="Personal",
                subcategory="Identity",
                sensitivity_boost=0.8,  # Very high sensitivity
            ),
        ]
        
        # Compile all patterns
        self._compiled_patterns = {}
        for pattern_set in self.pattern_sets:
            compiled = [
                re.compile(p, re.IGNORECASE) 
                for p in pattern_set.patterns
            ]
            self._compiled_patterns[pattern_set.category] = compiled
    
    def match(self, text: str) -> List[Tuple[ContentPattern, int]]:
        """Match text against all pattern sets.
        
        Args:
            text: Text content to analyze.
        
        Returns:
            List of (ContentPattern, match_count) tuples, sorted by match count.
        """
        results = []
        
        for pattern_set in self.pattern_sets:
            match_count = 0
            for pattern in pattern_set.patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    match_count += 1
            
            if match_count > 0:
                results.append((pattern_set, match_count))
        
        # Sort by match count descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results


class Tier2ContentClassifier:
    """Tier 2 - Content-based classifier using pattern matching.
    
    Analyzes document content to determine category and sensitivity.
    """
    
    # Minimum match threshold for classification
    MIN_MATCHES = 2
    
    def __init__(self):
        """Initialize the content classifier."""
        self.pattern_matcher = PatternMatcher()
    
    def classify(
        self,
        text: str,
        tier1_result: Optional[ClassificationResult] = None
    ) -> ClassificationResult:
        """Classify based on text content.
        
        Args:
            text: Text content to analyze.
            tier1_result: Optional Tier 1 result to enhance.
        
        Returns:
            Enhanced ClassificationResult.
        """
        if not text or not text.strip():
            if tier1_result:
                return tier1_result
            return ClassificationResult(
                category=FileCategory.UNKNOWN,
                classification_tier=2,
                needs_deeper_analysis=True,
            )
        
        # Normalize text
        text = text.lower()
        
        # Match patterns
        matches = self.pattern_matcher.match(text)
        
        if not matches or matches[0][1] < self.MIN_MATCHES:
            # No strong matches, return tier 1 result or unknown
            if tier1_result:
                tier1_result.classification_tier = 2
                tier1_result.needs_deeper_analysis = True
                return tier1_result
            return ClassificationResult(
                category=FileCategory.DOCUMENTS,
                subcategory="General",
                classification_tier=2,
                confidence=0.5,
                needs_deeper_analysis=True,
            )
        
        # Get best match
        best_pattern, match_count = matches[0]
        
        # Calculate confidence based on match count
        confidence = min(0.5 + (match_count * 0.1), 0.9)
        
        # Calculate sensitivity
        is_sensitive = best_pattern.sensitivity_boost > 0.3
        
        result = ClassificationResult(
            category=FileCategory.DOCUMENTS,
            subcategory=f"{best_pattern.category}/{best_pattern.subcategory}",
            confidence=confidence,
            classification_tier=2,
            is_sensitive=is_sensitive,
            needs_deeper_analysis=confidence < 0.7,
            metadata={
                "content_category": best_pattern.category,
                "pattern_matches": match_count,
                "sensitivity_score": best_pattern.sensitivity_boost,
                "all_matches": [
                    {
                        "category": p.category,
                        "subcategory": p.subcategory,
                        "matches": c
                    }
                    for p, c in matches[:3]
                ]
            }
        )
        
        logger.debug(
            f"Tier 2 classification: {best_pattern.category}/"
            f"{best_pattern.subcategory} (matches: {match_count})"
        )
        
        return result
    
    def detect_sensitivity(self, text: str) -> Tuple[bool, float, List[str]]:
        """Detect if text contains sensitive information.
        
        Args:
            text: Text to analyze.
        
        Returns:
            Tuple of (is_sensitive, sensitivity_score, detected_types).
        """
        matches = self.pattern_matcher.match(text)
        
        detected_types = []
        max_sensitivity = 0.0
        
        for pattern, count in matches:
            if pattern.sensitivity_boost > 0:
                detected_types.append(pattern.subcategory)
                max_sensitivity = max(max_sensitivity, pattern.sensitivity_boost)
        
        is_sensitive = max_sensitivity > 0.3
        
        return is_sensitive, max_sensitivity, detected_types
