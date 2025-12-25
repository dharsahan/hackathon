"""
Unit tests for classification module.
"""

import pytest
from pathlib import Path
import tempfile
import os

from src.classification.tier1_metadata import (
    Tier1Classifier,
)
from src.classification.tier2_content import (
    Tier2ContentClassifier,
    PatternMatcher,
)
from src.config.categories import FileCategory


class TestTier1Classifier:
    """Tests for Tier1 Metadata Classifier."""
    
    @pytest.fixture
    def classifier(self):
        """Create classifier instance."""
        return Tier1Classifier()
    
    def test_classify_pdf(self, classifier):
        """Test PDF classification."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'%PDF-1.4 test')
            f.flush()
            
            result = classifier.classify(Path(f.name))
            
            assert result.category == FileCategory.DOCUMENTS
            assert result.subcategory == "PDF"
            assert result.classification_tier == 1
            
            os.unlink(f.name)
    
    def test_classify_image(self, classifier):
        """Test image classification."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            f.write(b'\xFF\xD8\xFF test jpg')
            f.flush()
            
            result = classifier.classify(Path(f.name))
            
            assert result.category == FileCategory.IMAGES
            assert result.subcategory == "Photo"
            
            os.unlink(f.name)
    
    def test_classify_unknown(self, classifier):
        """Test unknown file classification."""
        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as f:
            f.write(b'unknown content')
            f.flush()
            
            result = classifier.classify(Path(f.name))
            
            assert result.category == FileCategory.UNKNOWN
            assert result.needs_deeper_analysis is True
            
            os.unlink(f.name)
    
    def test_needs_deeper_analysis(self, classifier):
        """Test documents need deeper analysis."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'%PDF-1.4')
            f.flush()
            
            result = classifier.classify(Path(f.name))
            
            assert result.needs_deeper_analysis is True
            
            os.unlink(f.name)
    
    def test_is_document(self, classifier):
        """Test is_document helper."""
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
            f.write(b'PK\x03\x04')  # ZIP magic (docx is a zip)
            f.flush()
            
            assert classifier.is_document(Path(f.name)) is True
            
            os.unlink(f.name)


class TestPatternMatcher:
    """Tests for PatternMatcher."""
    
    @pytest.fixture
    def matcher(self):
        """Create matcher instance."""
        return PatternMatcher()
    
    def test_financial_patterns(self, matcher):
        """Test financial document patterns."""
        text = "This invoice shows a total of $1,234.56 for your bank account."
        
        matches = matcher.match(text)
        
        assert len(matches) > 0
        # Financial should be matched
        categories = [m[0].category for m in matches]
        assert "Finance" in categories
    
    def test_medical_patterns(self, matcher):
        """Test medical document patterns."""
        text = "Patient diagnosis shows symptoms requiring prescription medication."
        
        matches = matcher.match(text)
        
        categories = [m[0].category for m in matches]
        assert "Medical" in categories
    
    def test_legal_patterns(self, matcher):
        """Test legal document patterns."""
        text = "This contract agreement between the parties whereas hereby agreed."
        
        matches = matcher.match(text)
        
        categories = [m[0].category for m in matches]
        assert "Legal" in categories
    
    def test_no_matches(self, matcher):
        """Test text with no pattern matches."""
        text = "Random unrelated text with no special keywords."
        
        matches = matcher.match(text)
        
        # Should have no or few matches
        total_matches = sum(m[1] for m in matches)
        assert total_matches < 3


class TestTier2ContentClassifier:
    """Tests for Tier2 Content Classifier."""
    
    @pytest.fixture
    def classifier(self):
        """Create classifier instance."""
        return Tier2ContentClassifier()
    
    def test_classify_financial(self, classifier):
        """Test financial document classification."""
        text = """
        INVOICE #12345
        Amount Due: $1,500.00
        Bank Transfer Payment
        Account: XXXX-1234
        Tax ID: 12-3456789
        """
        
        result = classifier.classify(text)
        
        assert "Finance" in result.subcategory
        assert result.classification_tier == 2
    
    def test_classify_empty_text(self, classifier):
        """Test classification of empty text."""
        result = classifier.classify("")
        
        assert result.category == FileCategory.UNKNOWN
        assert result.needs_deeper_analysis is True
    
    def test_detect_sensitivity(self, classifier):
        """Test sensitivity detection."""
        sensitive_text = "Social Security Number: 123-45-6789"
        
        is_sensitive, score, types = classifier.detect_sensitivity(sensitive_text)
        
        assert is_sensitive is True
        assert score > 0.5
