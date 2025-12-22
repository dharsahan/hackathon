"""
Smart File Organizer - Main Application
=======================================

Main entry point and orchestration for the autonomous file organizer.
Coordinates all modules for intelligent file management.
"""

import signal
import sys
import time
from pathlib import Path
from queue import Queue
from typing import Optional
from dataclasses import dataclass

from src.config import Config
from src.monitoring import FileWatcherService, ProcessingQueueManager
from src.extraction import TextExtractionService, OCREngine
from src.classification import (
    Tier1Classifier,
    Tier2ContentClassifier,
    Tier3LLMClassifier,
    ZeroShotClassifier,
    ClassificationResult,
)
from src.deduplication import DeduplicationEngine, PerceptualHashEngine
from src.security import AESEncryptor, SecureArchiver, KeyDerivationService
from src.actions import FileOperations, ConflictResolver, ConflictStrategy
from src.utils.logging_config import setup_logging, get_logger, LoggingConfig

logger = get_logger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing a single file."""
    file_path: str
    success: bool
    category: str
    subcategory: Optional[str] = None
    destination: Optional[str] = None
    is_duplicate: bool = False
    is_sensitive: bool = False
    error: Optional[str] = None


class SmartFileOrganizer:
    """Main orchestrator for the Smart File Organizer.
    
    Coordinates filesystem monitoring, classification, deduplication,
    encryption, and file organization.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the Smart File Organizer.
        
        Args:
            config_path: Path to configuration file.
        """
        # Load configuration
        self.config = Config.load(config_path)
        
        # Setup logging
        setup_logging(LoggingConfig(level="INFO"))
        
        # Initialize processing queue
        self.processing_queue = Queue()
        
        # Initialize components
        self._init_components()
        
        # Statistics
        self._stats = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'duplicates': 0,
            'sensitive': 0,
        }
    
    def _init_components(self) -> None:
        """Initialize all processing components."""
        # Monitoring
        self.watcher = FileWatcherService(
            self.config.watcher,
            self.processing_queue
        )
        
        self.queue_manager = ProcessingQueueManager(
            processor_callback=self.process_file,
            max_workers=4,
            completion_callback=self._on_file_complete
        )
        
        # Extraction
        self.text_extractor = TextExtractionService()
        self.ocr_engine = OCREngine() if self.config.classification.ocr_enabled else None
        
        # Classification
        self.tier1_classifier = Tier1Classifier()
        self.tier2_classifier = Tier2ContentClassifier()
        self.tier3_classifier = Tier3LLMClassifier(
            model=self.config.classification.llm_model
        )
        self.zero_shot_classifier = ZeroShotClassifier() if self.config.classification.fallback_to_zero_shot else None
        
        # Deduplication
        self.dedup_engine = DeduplicationEngine()
        self.perceptual_hasher = PerceptualHashEngine(
            threshold=self.config.deduplication.perceptual_hash_threshold
        )
        
        # Security
        self.encryptor = AESEncryptor()
        self.archiver = SecureArchiver()
        self.key_service = KeyDerivationService()
        
        # File operations
        self.file_ops = FileOperations(
            base_directory=self.config.organization.base_directory
        )
        self.conflict_resolver = ConflictResolver(
            strategy=ConflictStrategy.RENAME,
            quarantine_dir=self.config.organization.quarantine_directory
        )
        
        logger.info("All components initialized")
    
    def process_file(self, file_path: str) -> bool:
        """Process a single file through the pipeline.
        
        Args:
            file_path: Path to the file to process.
        
        Returns:
            True if processing was successful.
        """
        path = Path(file_path)
        logger.info(f"Processing: {path.name}")
        
        try:
            # Step 1: Check if file still exists
            if not path.exists():
                logger.warning(f"File no longer exists: {path}")
                return True  # Not an error
            
            # Step 2: Check for duplicates
            if self.config.deduplication.enabled:
                hash_result = self.dedup_engine.check_duplicate(path)
                if hash_result.status.value == "exact_duplicate":
                    self._handle_duplicate(path, hash_result)
                    self._stats['duplicates'] += 1
                    return True
            
            # Step 3: Tier 1 classification (fast)
            tier1_result = self.tier1_classifier.classify(path)
            
            # Step 4: Check for image duplicates
            if tier1_result.category.value == "Images" and self.config.deduplication.enabled:
                if self.perceptual_hasher.is_supported(path):
                    perceptual_result = self.perceptual_hasher.find_similar(path)
                    if perceptual_result.is_duplicate:
                        self._handle_duplicate(path, perceptual_result)
                        self._stats['duplicates'] += 1
                        return True
            
            # Step 5: Deeper analysis for documents
            final_result = tier1_result
            if tier1_result.needs_deeper_analysis:
                final_result = self._deep_classify(path, tier1_result)
            
            # Step 6: Handle sensitive files
            if final_result.is_sensitive and self.config.security.enable_encryption:
                self._encrypt_and_vault(path, final_result)
                self._stats['sensitive'] += 1
                return True
            
            # Step 7: Move to organized location
            dest = self._get_destination(final_result)
            self.file_ops.move_file(path, dest)
            
            self._stats['successful'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error processing {path.name}: {e}")
            self._stats['failed'] += 1
            return False
        finally:
            self._stats['processed'] += 1
    
    def _deep_classify(
        self,
        file_path: Path,
        tier1_result: ClassificationResult
    ) -> ClassificationResult:
        """Perform deep classification using content analysis.
        
        Args:
            file_path: Path to file.
            tier1_result: Initial classification result.
        
        Returns:
            Enhanced classification result.
        """
        # Extract text
        extraction_result = self.text_extractor.extract(file_path)
        
        if not extraction_result or not extraction_result.text:
            return tier1_result
        
        text = extraction_result.text
        
        # Tier 2: Pattern matching
        tier2_result = self.tier2_classifier.classify(text, tier1_result)
        
        if not tier2_result.needs_deeper_analysis:
            return tier2_result
        
        # Tier 3: LLM classification (if available)
        if self.tier3_classifier.is_available():
            return self.tier3_classifier.classify_with_result(text, tier2_result)
        
        # Fallback to zero-shot
        if self.zero_shot_classifier and self.zero_shot_classifier.is_available():
            return self.zero_shot_classifier.classify_with_result(text, tier2_result)
        
        return tier2_result
    
    def _get_destination(self, result: ClassificationResult) -> Path:
        """Get destination directory for classified file.
        
        Args:
            result: Classification result.
        
        Returns:
            Destination directory path.
        """
        return self.file_ops.get_destination_path(
            category=result.category.value,
            subcategory=result.subcategory,
            use_date=self.config.organization.use_date_folders
        )
    
    def _handle_duplicate(self, file_path: Path, result) -> None:
        """Handle duplicate file based on configuration.
        
        Args:
            file_path: Path to duplicate file.
            result: Deduplication result.
        """
        action = self.config.deduplication.duplicate_action
        
        if action == "quarantine":
            self.file_ops.quarantine_file(file_path, reason="duplicate")
        elif action == "delete":
            from src.security import SecureDeleter
            deleter = SecureDeleter(passes=1)
            deleter.secure_delete(file_path)
        elif action == "skip":
            logger.info(f"Skipping duplicate: {file_path.name}")
        
        logger.info(f"Duplicate handled ({action}): {file_path.name}")
    
    def _encrypt_and_vault(
        self,
        file_path: Path,
        result: ClassificationResult
    ) -> None:
        """Encrypt sensitive file and move to vault.
        
        Args:
            file_path: Path to sensitive file.
            result: Classification result.
        """
        vault_dir = self.config.organization.vault_directory
        vault_dir.mkdir(parents=True, exist_ok=True)
        
        # Note: In production, password should come from secure storage
        # This is a placeholder - implement proper key management
        logger.info(f"Sensitive file detected: {file_path.name}")
        logger.info("Moving to vault (encryption requires password setup)")
        
        # For now, just move to vault without encryption
        # TODO: Implement password prompt/storage
        vault_dest = vault_dir / result.category.value
        vault_dest.mkdir(parents=True, exist_ok=True)
        self.file_ops.move_file(file_path, vault_dest)
    
    def _on_file_complete(self, file_path: str) -> None:
        """Callback when file processing completes.
        
        Args:
            file_path: Path to completed file.
        """
        # Notify watcher that file is done
        self.watcher.handler.mark_complete(file_path)
    
    def start(self) -> None:
        """Start the Smart File Organizer."""
        logger.info("Starting Smart File Organizer...")
        logger.info(f"Watching: {[str(d) for d in self.config.watcher.watch_directories]}")
        logger.info(f"Organizing to: {self.config.organization.base_directory}")
        
        try:
            self.watcher.start()
            self.queue_manager.start()
            logger.info("Smart File Organizer is running. Press Ctrl+C to stop.")
        except RuntimeError as e:
            logger.error(f"Failed to start: {e}")
            raise
    
    def stop(self) -> None:
        """Stop the Smart File Organizer."""
        logger.info("Stopping Smart File Organizer...")
        self.watcher.stop()
        self.queue_manager.stop()
        logger.info("Smart File Organizer stopped.")
        self._print_stats()
    
    def _print_stats(self) -> None:
        """Print processing statistics."""
        logger.info(f"Statistics:")
        logger.info(f"  Processed: {self._stats['processed']}")
        logger.info(f"  Successful: {self._stats['successful']}")
        logger.info(f"  Failed: {self._stats['failed']}")
        logger.info(f"  Duplicates: {self._stats['duplicates']}")
        logger.info(f"  Sensitive: {self._stats['sensitive']}")
    
    def process_directory(self, directory: Path) -> dict:
        """Process all files in a directory (batch mode).
        
        Args:
            directory: Directory to process.
        
        Returns:
            Processing statistics.
        """
        directory = Path(directory)
        
        if not directory.is_dir():
            raise ValueError(f"Not a directory: {directory}")
        
        logger.info(f"Processing directory: {directory}")
        
        for file_path in directory.iterdir():
            if file_path.is_file():
                self.process_file(str(file_path))
        
        return self._stats.copy()


def main():
    """Main entry point."""
    organizer = SmartFileOrganizer()
    
    def signal_handler(sig, frame):
        organizer.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    organizer.start()
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        organizer.stop()


if __name__ == "__main__":
    main()
