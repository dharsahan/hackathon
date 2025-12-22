"""
Configuration Management System
===============================

Provides dataclass-based configuration with YAML file loading support.
All settings are validated and have sensible defaults.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Any, Dict
import yaml
import logging

logger = logging.getLogger(__name__)


@dataclass
class WatcherConfig:
    """Filesystem watcher configuration.
    
    Attributes:
        watch_directories: List of directories to monitor for new files.
        ignore_patterns: Glob patterns for files to ignore.
        debounce_seconds: Wait time before processing a file event.
        recursive: Whether to watch subdirectories.
    """
    watch_directories: List[Path] = field(default_factory=lambda: [
        Path.home() / "Downloads",
        Path.home() / "Desktop"
    ])
    ignore_patterns: List[str] = field(default_factory=lambda: [
        "*.tmp", "*.crdownload", "~$*", ".DS_Store", "Thumbs.db", "*.part"
    ])
    debounce_seconds: float = 1.0
    recursive: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WatcherConfig":
        """Create WatcherConfig from dictionary."""
        if not data:
            return cls()
        
        watch_dirs = data.get("watch_directories", [])
        # Expand ~ in paths
        watch_dirs = [Path(d).expanduser() for d in watch_dirs]
        
        return cls(
            watch_directories=watch_dirs or cls().watch_directories,
            ignore_patterns=data.get("ignore_patterns", cls().ignore_patterns),
            debounce_seconds=float(data.get("debounce_seconds", 1.0)),
            recursive=bool(data.get("recursive", False))
        )


@dataclass
class ClassificationConfig:
    """Classification engine configuration.
    
    Attributes:
        llm_model: Name of the LLM model for semantic classification.
        llm_backend: Backend to use ("ollama" or "llama-cpp").
        fallback_to_zero_shot: Use zero-shot if LLM unavailable.
        zero_shot_model: HuggingFace model for zero-shot fallback.
        max_text_length: Maximum text length to send to LLM.
        ocr_enabled: Whether to use OCR for image-based documents.
        ocr_languages: Tesseract language codes.
    """
    llm_model: str = "llama3"
    llm_backend: str = "ollama"
    fallback_to_zero_shot: bool = True
    zero_shot_model: str = "facebook/bart-large-mnli"
    max_text_length: int = 2000
    ocr_enabled: bool = True
    ocr_languages: str = "eng"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClassificationConfig":
        """Create ClassificationConfig from dictionary."""
        if not data:
            return cls()
        return cls(
            llm_model=data.get("llm_model", cls.llm_model),
            llm_backend=data.get("llm_backend", cls.llm_backend),
            fallback_to_zero_shot=data.get("fallback_to_zero_shot", cls.fallback_to_zero_shot),
            zero_shot_model=data.get("zero_shot_model", cls.zero_shot_model),
            max_text_length=int(data.get("max_text_length", cls.max_text_length)),
            ocr_enabled=data.get("ocr_enabled", cls.ocr_enabled),
            ocr_languages=data.get("ocr_languages", cls.ocr_languages)
        )


@dataclass
class SecurityConfig:
    """Security and encryption configuration.
    
    Attributes:
        enable_encryption: Whether to encrypt sensitive files.
        encryption_algorithm: Encryption algorithm to use.
        key_derivation: Key derivation function.
        argon2_memory_cost: Argon2 memory cost in KB.
        argon2_time_cost: Argon2 iteration count.
        argon2_parallelism: Argon2 parallelism degree.
        secure_delete_passes: Number of overwrite passes for secure delete.
    """
    enable_encryption: bool = True
    encryption_algorithm: str = "AES-256-GCM"
    key_derivation: str = "argon2id"
    argon2_memory_cost: int = 65536  # 64MB
    argon2_time_cost: int = 3
    argon2_parallelism: int = 4
    secure_delete_passes: int = 3

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SecurityConfig":
        """Create SecurityConfig from dictionary."""
        if not data:
            return cls()
        return cls(
            enable_encryption=data.get("enable_encryption", cls.enable_encryption),
            encryption_algorithm=data.get("encryption_algorithm", cls.encryption_algorithm),
            key_derivation=data.get("key_derivation", cls.key_derivation),
            argon2_memory_cost=int(data.get("argon2_memory_cost", cls.argon2_memory_cost)),
            argon2_time_cost=int(data.get("argon2_time_cost", cls.argon2_time_cost)),
            argon2_parallelism=int(data.get("argon2_parallelism", cls.argon2_parallelism)),
            secure_delete_passes=int(data.get("secure_delete_passes", cls.secure_delete_passes))
        )


@dataclass
class DeduplicationConfig:
    """Deduplication settings.
    
    Attributes:
        enabled: Whether duplicate detection is enabled.
        use_partial_hash: Use partial hashing for faster comparison.
        partial_hash_size: Chunk size in bytes for partial hashing.
        perceptual_hash_threshold: Similarity threshold for images (0-64).
        duplicate_action: Action for duplicates (quarantine/delete/hardlink/skip).
    """
    enabled: bool = True
    use_partial_hash: bool = True
    partial_hash_size: int = 4096
    perceptual_hash_threshold: int = 5
    duplicate_action: str = "quarantine"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeduplicationConfig":
        """Create DeduplicationConfig from dictionary."""
        if not data:
            return cls()
        return cls(
            enabled=data.get("enabled", cls.enabled),
            use_partial_hash=data.get("use_partial_hash", cls.use_partial_hash),
            partial_hash_size=int(data.get("partial_hash_size", cls.partial_hash_size)),
            perceptual_hash_threshold=int(data.get("perceptual_hash_threshold", cls.perceptual_hash_threshold)),
            duplicate_action=data.get("duplicate_action", cls.duplicate_action)
        )


@dataclass
class OrganizationConfig:
    """File organization settings.
    
    Attributes:
        base_directory: Base directory for organized files.
        vault_directory: Directory for encrypted sensitive files.
        quarantine_directory: Directory for duplicate files.
        use_date_folders: Include date in destination path.
        date_format: strftime format for date folders.
    """
    base_directory: Path = field(default_factory=lambda: Path.home() / "Organized")
    vault_directory: Path = field(default_factory=lambda: Path.home() / "Organized" / "Vault")
    quarantine_directory: Path = field(default_factory=lambda: Path.home() / "Organized" / ".quarantine")
    use_date_folders: bool = True
    date_format: str = "%Y/%m"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrganizationConfig":
        """Create OrganizationConfig from dictionary."""
        if not data:
            return cls()
        
        base_dir = Path(data.get("base_directory", "~/Organized")).expanduser()
        vault_dir = Path(data.get("vault_directory", "~/Organized/Vault")).expanduser()
        quarantine_dir = Path(data.get("quarantine_directory", "~/Organized/.quarantine")).expanduser()
        
        return cls(
            base_directory=base_dir,
            vault_directory=vault_dir,
            quarantine_directory=quarantine_dir,
            use_date_folders=data.get("use_date_folders", cls.use_date_folders),
            date_format=data.get("date_format", cls.date_format)
        )


@dataclass
class Config:
    """Main configuration container.
    
    Aggregates all configuration sections and provides loading from YAML.
    """
    watcher: WatcherConfig = field(default_factory=WatcherConfig)
    classification: ClassificationConfig = field(default_factory=ClassificationConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    deduplication: DeduplicationConfig = field(default_factory=DeduplicationConfig)
    organization: OrganizationConfig = field(default_factory=OrganizationConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from YAML file.
        
        Args:
            config_path: Path to the configuration file. If None, looks for
                        config.yaml in the current directory.
        
        Returns:
            Config instance with loaded settings.
        
        Raises:
            FileNotFoundError: If specified config file doesn't exist.
            yaml.YAMLError: If config file is not valid YAML.
        """
        if config_path is None:
            config_path = Path("config.yaml")
        
        if not config_path.exists():
            logger.warning(f"Config file not found at {config_path}, using defaults")
            return cls()
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            logger.info(f"Loaded configuration from {config_path}")
            return cls._from_dict(data)
        
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse config file: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            raise

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create Config from dictionary."""
        return cls(
            watcher=WatcherConfig.from_dict(data.get("watcher", {})),
            classification=ClassificationConfig.from_dict(data.get("classification", {})),
            security=SecurityConfig.from_dict(data.get("security", {})),
            deduplication=DeduplicationConfig.from_dict(data.get("deduplication", {})),
            organization=OrganizationConfig.from_dict(data.get("organization", {}))
        )

    def save(self, config_path: Path) -> None:
        """Save configuration to YAML file.
        
        Args:
            config_path: Path where to save the configuration.
        """
        data = {
            "watcher": {
                "watch_directories": [str(d) for d in self.watcher.watch_directories],
                "ignore_patterns": self.watcher.ignore_patterns,
                "debounce_seconds": self.watcher.debounce_seconds,
                "recursive": self.watcher.recursive
            },
            "classification": {
                "llm_model": self.classification.llm_model,
                "llm_backend": self.classification.llm_backend,
                "fallback_to_zero_shot": self.classification.fallback_to_zero_shot,
                "zero_shot_model": self.classification.zero_shot_model,
                "max_text_length": self.classification.max_text_length,
                "ocr_enabled": self.classification.ocr_enabled,
                "ocr_languages": self.classification.ocr_languages
            },
            "security": {
                "enable_encryption": self.security.enable_encryption,
                "encryption_algorithm": self.security.encryption_algorithm,
                "key_derivation": self.security.key_derivation,
                "argon2_memory_cost": self.security.argon2_memory_cost,
                "argon2_time_cost": self.security.argon2_time_cost,
                "argon2_parallelism": self.security.argon2_parallelism,
                "secure_delete_passes": self.security.secure_delete_passes
            },
            "deduplication": {
                "enabled": self.deduplication.enabled,
                "use_partial_hash": self.deduplication.use_partial_hash,
                "partial_hash_size": self.deduplication.partial_hash_size,
                "perceptual_hash_threshold": self.deduplication.perceptual_hash_threshold,
                "duplicate_action": self.deduplication.duplicate_action
            },
            "organization": {
                "base_directory": str(self.organization.base_directory),
                "vault_directory": str(self.organization.vault_directory),
                "quarantine_directory": str(self.organization.quarantine_directory),
                "use_date_folders": self.organization.use_date_folders,
                "date_format": self.organization.date_format
            }
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Saved configuration to {config_path}")
