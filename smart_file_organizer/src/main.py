"""
Smart File Organizer - Main Application
=======================================

Main entry point and orchestration for the autonomous file organizer.
Coordinates all modules for intelligent file management.
"""

import signal
import sys
import time
import threading
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
from src.actions import FileOperations, ConflictResolver, ConflictStrategy, HistoryTracker, RulesEngine
from src.utils.logging_config import setup_logging, get_logger, LoggingConfig
from src.utils.notifications import DesktopNotifier, NotificationConfig
from src.dashboard import DashboardServer

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

        # History tracking (NEW)
        self.history = HistoryTracker(
            base_directory=self.config.organization.base_directory
        )

        # Custom rules engine (NEW)
        self.rules_engine = RulesEngine(
            base_directory=self.config.organization.base_directory
        )

        # Desktop notifications (NEW)
        self.notifier = DesktopNotifier(NotificationConfig())

        # Web dashboard (NEW)
        self.dashboard = DashboardServer(self, port=3000)

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
            # Step 1: Check if file still exists and is actually a file
            if not path.exists():
                logger.warning(f"File no longer exists: {path}")
                return True  # Not an error

            if path.is_dir():
                logger.debug(f"Skipping directory: {path}")
                return True  # Not an error, just skip

            # Step 2: Check for duplicates
            if self.config.deduplication.enabled:
                hash_result = self.dedup_engine.check_duplicate(path)
                if hash_result.status.value == "exact_duplicate":
                    self._handle_duplicate(path, hash_result)
                    self._stats['duplicates'] += 1
                    return True

            # Step 3: Check custom rules first (NEW - before AI classification)
            rule_result = self.rules_engine.evaluate(path)
            if rule_result:
                dest = self._get_destination(rule_result, source_path=path)
                actual_dest = self.file_ops.move_file(path, dest)
                # Record to history
                self.history.record_move(
                    source=path,
                    destination=actual_dest,
                    category=rule_result.category.value if hasattr(rule_result.category, 'value') else str(rule_result.category),
                    subcategory=rule_result.subcategory or ""
                )
                self._stats['successful'] += 1
                logger.info(f"Rule matched: {path.name} -> {dest}")
                return True

            # Step 4: Tier 1 classification (fast)
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

            # Step 8: Move to organized location
            dest = self._get_destination(final_result, source_path=path)
            actual_dest = self.file_ops.move_file(path, dest)

            # Record to history (NEW)
            self.history.record_move(
                source=path,
                destination=actual_dest,
                category=final_result.category.value,
                subcategory=final_result.subcategory or ""
            )

            # Send desktop notification (NEW)
            self.notifier.notify_organized(
                filename=path.name,
                category=final_result.category.value,
                destination=str(actual_dest)
            )

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

    def _get_destination(self, result: ClassificationResult, source_path: Path = None) -> Path:
        """Get destination directory for classified file.
        
        Args:
            result: Classification result.
            source_path: Optional source file path for in-place organization.
        
        Returns:
            Destination directory path.
        """
        # If organizing in-place, use source directory as base
        if self.config.organization.organize_in_place and source_path:
            base_dir = source_path.parent
        else:
            base_dir = self.config.organization.base_directory

        # Build destination path
        category = result.category.value if hasattr(result.category, 'value') else str(result.category)
        subcategory = result.subcategory or ""

        dest = base_dir / category
        if subcategory:
            dest = dest / subcategory

        if self.config.organization.use_date_folders:
            from datetime import datetime
            date_folder = datetime.now().strftime(self.config.organization.date_format)
            dest = dest / date_folder

        return dest

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

            # Start queue bridge thread
            self._bridge_running = True
            self._bridge_thread = threading.Thread(
                target=self._queue_bridge,
                daemon=True,
                name="QueueBridge"
            )
            self._bridge_thread.start()

            # Start web dashboard (NEW)
            self.dashboard.start()

            # Send startup notification (NEW)
            self.notifier.notify_started()

            logger.info("Smart File Organizer is running. Press Ctrl+C to stop.")
            logger.info(f"Dashboard: {self.dashboard.url}")
        except RuntimeError as e:
            logger.error(f"Failed to start: {e}")
            raise

    def _queue_bridge(self) -> None:
        """Bridge between watcher queue and processor queue."""
        from queue import Empty
        while self._bridge_running:
            try:
                file_path = self.processing_queue.get(timeout=0.5)
                self.queue_manager.put(file_path)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Queue bridge error: {e}")

    def stop(self) -> None:
        """Stop the Smart File Organizer."""
        logger.info("Stopping Smart File Organizer...")
        self._bridge_running = False
        self.dashboard.stop()
        self.watcher.stop()
        self.queue_manager.stop()
        self.notifier.notify_stopped(self._stats)
        logger.info("Smart File Organizer stopped.")
        self._print_stats()

    def _print_stats(self) -> None:
        """Print processing statistics."""
        logger.info("Statistics:")
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

    # =====================
    # Undo/History Methods (NEW)
    # =====================

    def undo_last(self) -> bool:
        """Undo the last file organization.
        
        Returns:
            True if undo was successful.
        """
        entry = self.history.undo_last()
        if entry:
            logger.info(f"Undone: {Path(entry.dest_path).name} -> {entry.source_path}")
            return True
        return False

    def get_history(self, count: int = 10) -> list:
        """Get recent organization history.
        
        Args:
            count: Number of entries to return.
        
        Returns:
            List of history entries.
        """
        return self.history.get_recent(count)

    def get_rules(self) -> list:
        """Get all custom rules.
        
        Returns:
            List of custom rules.
        """
        return self.rules_engine.get_rules()

    def add_rule(
        self,
        name: str,
        pattern: str,
        category: str,
        subcategory: str = ""
    ) -> None:
        """Add a custom organization rule.
        
        Args:
            name: Rule name.
            pattern: Pattern to match.
            category: Target category.
            subcategory: Target subcategory.
        """
        from src.actions.rules_engine import MatchType
        self.rules_engine.add_rule(
            name=name,
            pattern=pattern,
            category=category,
            subcategory=subcategory,
            match_type=MatchType.CONTAINS
        )
        logger.info(f"Added rule: {name}")


def main():
    """Main entry point with CLI support."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Smart File Organizer - Intelligent file management"
    )
    parser.add_argument(
        '--undo', '-u',
        action='store_true',
        help='Undo the last file organization'
    )
    parser.add_argument(
        '--history', '-H',
        type=int,
        nargs='?',
        const=10,
        help='Show recent history (default: 10 entries)'
    )
    parser.add_argument(
        '--rules', '-r',
        action='store_true',
        help='List all custom rules'
    )
    parser.add_argument(
        '--add-rule',
        nargs=4,
        metavar=('NAME', 'PATTERN', 'CATEGORY', 'SUBCATEGORY'),
        help='Add a custom rule'
    )
    parser.add_argument(
        '--stats', '-s',
        action='store_true',
        help='Show organization statistics'
    )

    args = parser.parse_args()

    # Handle CLI commands
    if args.undo:
        organizer = SmartFileOrganizer()
        if organizer.undo_last():
            print("✓ Undo successful")
        else:
            print("✗ Nothing to undo")
        return

    if args.history is not None:
        organizer = SmartFileOrganizer()
        entries = organizer.get_history(args.history)
        if entries:
            print(f"\n📋 Recent History ({len(entries)} entries):\n")
            for entry in entries:
                status = "✓" if not entry.can_undo else "↩"
                print(f"  {status} [{entry.timestamp[:16]}] {Path(entry.source_path).name}")
                print(f"      → {entry.dest_path}")
        else:
            print("No history yet.")
        return

    if args.rules:
        organizer = SmartFileOrganizer()
        rules = organizer.get_rules()
        if rules:
            print(f"\n📜 Custom Rules ({len(rules)}):\n")
            for rule in rules:
                status = "✓" if rule.enabled else "✗"
                print(f"  {status} [{rule.priority}] {rule.name}")
                print(f"      Pattern: '{rule.pattern}' ({rule.match_type.value})")
                print(f"      → {rule.category}/{rule.subcategory}")
        else:
            print("No custom rules defined.")
        return

    if args.add_rule:
        name, pattern, category, subcategory = args.add_rule
        organizer = SmartFileOrganizer()
        organizer.add_rule(name, pattern, category, subcategory)
        print(f"✓ Added rule: {name}")
        return

    if args.stats:
        organizer = SmartFileOrganizer()
        stats = organizer.history.get_stats()
        print("\n📊 Organization Statistics:\n")
        print(f"  Total operations: {stats['total_operations']}")
        print(f"  Undoable: {stats['undoable']}")
        print(f"  Total size: {stats['total_size_bytes'] / 1024 / 1024:.2f} MB")
        print("\n  By category:")
        for cat, count in stats.get('by_category', {}).items():
            print(f"    {cat}: {count}")
        return

    # Default: Run the organizer
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

