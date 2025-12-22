"""
Unit tests for configuration module.
"""

import pytest
from pathlib import Path
import tempfile
import yaml

from src.config.settings import (
    Config,
    WatcherConfig,
    ClassificationConfig,
    SecurityConfig,
    DeduplicationConfig,
    OrganizationConfig,
)
from src.config.categories import FileCategory, CategoryMapping, CATEGORY_MAPPING


class TestWatcherConfig:
    """Tests for WatcherConfig."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = WatcherConfig()
        
        assert len(config.watch_directories) == 2
        assert config.debounce_seconds == 1.0
        assert config.recursive is False
        assert "*.tmp" in config.ignore_patterns
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "watch_directories": ["~/Documents"],
            "debounce_seconds": 2.0,
            "recursive": True
        }
        config = WatcherConfig.from_dict(data)
        
        assert config.debounce_seconds == 2.0
        assert config.recursive is True


class TestClassificationConfig:
    """Tests for ClassificationConfig."""
    
    def test_default_values(self):
        """Test default classification settings."""
        config = ClassificationConfig()
        
        assert config.llm_model == "llama3"
        assert config.ocr_enabled is True
        assert config.max_text_length == 2000
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "llm_model": "mistral",
            "ocr_enabled": False
        }
        config = ClassificationConfig.from_dict(data)
        
        assert config.llm_model == "mistral"
        assert config.ocr_enabled is False


class TestSecurityConfig:
    """Tests for SecurityConfig."""
    
    def test_default_values(self):
        """Test default security settings."""
        config = SecurityConfig()
        
        assert config.enable_encryption is True
        assert config.encryption_algorithm == "AES-256-GCM"
        assert config.argon2_memory_cost == 65536


class TestDeduplicationConfig:
    """Tests for DeduplicationConfig."""
    
    def test_default_values(self):
        """Test default deduplication settings."""
        config = DeduplicationConfig()
        
        assert config.enabled is True
        assert config.use_partial_hash is True
        assert config.duplicate_action == "quarantine"


class TestConfig:
    """Tests for main Config class."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = Config()
        
        assert isinstance(config.watcher, WatcherConfig)
        assert isinstance(config.classification, ClassificationConfig)
        assert isinstance(config.security, SecurityConfig)
    
    def test_load_from_file(self):
        """Test loading configuration from YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                "watcher": {"debounce_seconds": 3.0},
                "classification": {"llm_model": "codellama"}
            }, f)
            f.flush()
            
            config = Config.load(Path(f.name))
            
            assert config.watcher.debounce_seconds == 3.0
            assert config.classification.llm_model == "codellama"
    
    def test_load_missing_file(self):
        """Test loading from non-existent file returns defaults."""
        config = Config.load(Path("/nonexistent/config.yaml"))
        
        # Should return default config
        assert config.watcher.debounce_seconds == 1.0


class TestCategoryMapping:
    """Tests for CategoryMapping."""
    
    def test_document_extensions(self):
        """Test document extensions are mapped correctly."""
        category, subcategory = CATEGORY_MAPPING.get_category(".pdf")
        
        assert category == FileCategory.DOCUMENTS
        assert subcategory == "PDF"
    
    def test_image_extensions(self):
        """Test image extensions are mapped correctly."""
        category, subcategory = CATEGORY_MAPPING.get_category(".jpg")
        
        assert category == FileCategory.IMAGES
        assert subcategory == "Photo"
    
    def test_unknown_extension(self):
        """Test unknown extensions return UNKNOWN category."""
        category, subcategory = CATEGORY_MAPPING.get_category(".xyz")
        
        assert category == FileCategory.UNKNOWN
        assert subcategory is None
    
    def test_case_insensitive(self):
        """Test extension matching is case-insensitive."""
        category1, _ = CATEGORY_MAPPING.get_category(".PDF")
        category2, _ = CATEGORY_MAPPING.get_category(".pdf")
        
        assert category1 == category2
    
    def test_is_document(self):
        """Test is_document helper."""
        assert CATEGORY_MAPPING.is_document(".pdf") is True
        assert CATEGORY_MAPPING.is_document(".jpg") is False
    
    def test_is_image(self):
        """Test is_image helper."""
        assert CATEGORY_MAPPING.is_image(".png") is True
        assert CATEGORY_MAPPING.is_image(".pdf") is False
