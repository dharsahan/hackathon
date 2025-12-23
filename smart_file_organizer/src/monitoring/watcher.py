"""
Filesystem Watcher
==================

Monitors directories for new files and enqueues them for processing.
Implements debouncing and file settling detection to handle partial writes.
"""

import threading
import time
from pathlib import Path
from queue import Queue
from typing import Set, Dict, Optional, List
from fnmatch import fnmatch

from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    DirCreatedEvent,
    DirModifiedEvent,
)

from src.utils.logging_config import get_logger
from src.config.settings import WatcherConfig

logger = get_logger(__name__)


class DebounceTracker:
    """Tracks file events for debouncing.
    
    Prevents multiple rapid events for the same file from triggering
    multiple processing attempts.
    """

    def __init__(self, debounce_seconds: float = 1.0):
        """Initialize the debounce tracker.
        
        Args:
            debounce_seconds: Minimum time between events for the same file.
        """
        self.debounce_seconds = debounce_seconds
        self._pending: Dict[str, float] = {}
        self._lock = threading.Lock()

    def should_process(self, file_path: str) -> bool:
        """Check if enough time has passed since the last event.
        
        Args:
            file_path: Path to the file.
        
        Returns:
            True if the file should be processed, False to skip.
        """
        current_time = time.time()
        with self._lock:
            last_time = self._pending.get(file_path, 0)
            if current_time - last_time >= self.debounce_seconds:
                self._pending[file_path] = current_time
                return True
            return False

    def clear(self, file_path: str) -> None:
        """Remove a file from the pending tracker.
        
        Args:
            file_path: Path to the file to remove.
        """
        with self._lock:
            self._pending.pop(file_path, None)

    def clear_all(self) -> None:
        """Clear all pending entries."""
        with self._lock:
            self._pending.clear()


class FileSettlingChecker:
    """Ensures files are fully written before processing.
    
    Monitors file size stability to detect when a file has finished
    being written to disk.
    """

    @staticmethod
    def is_file_ready(
        file_path: Path,
        check_interval: float = 0.5,
        max_checks: int = 10,
        stability_checks: int = 2
    ) -> bool:
        """Check if file size is stable (file is fully written).
        
        Args:
            file_path: Path to the file to check.
            check_interval: Time between size checks in seconds.
            max_checks: Maximum number of checks before giving up.
            stability_checks: Number of consecutive stable readings required.
        
        Returns:
            True if file is ready for processing.
        """
        if not file_path.exists():
            return False

        previous_size = -1
        stable_count = 0

        for _ in range(max_checks):
            try:
                current_size = file_path.stat().st_size

                if current_size == previous_size and current_size > 0:
                    stable_count += 1
                    if stable_count >= stability_checks:
                        # Try to open the file to verify it's not locked
                        try:
                            with open(file_path, 'rb') as f:
                                f.read(1)
                            return True
                        except (OSError, IOError):
                            # File is still locked
                            stable_count = 0
                else:
                    stable_count = 0

                previous_size = current_size

            except (OSError, FileNotFoundError):
                return False

            time.sleep(check_interval)

        # Return True if we have a non-zero stable size
        return stable_count >= 1 and previous_size > 0

    @staticmethod
    def wait_for_file(
        file_path: Path,
        timeout: float = 30.0,
        check_interval: float = 0.5
    ) -> bool:
        """Wait for a file to become ready.
        
        Args:
            file_path: Path to the file.
            timeout: Maximum time to wait in seconds.
            check_interval: Time between checks.
        
        Returns:
            True if file is ready, False if timeout occurred.
        """
        max_checks = int(timeout / check_interval)
        return FileSettlingChecker.is_file_ready(
            file_path,
            check_interval=check_interval,
            max_checks=max_checks
        )


class OrganizerEventHandler(FileSystemEventHandler):
    """Custom event handler for file organization.
    
    Filters events based on ignore patterns and handles debouncing
    before enqueuing files for processing.
    """

    def __init__(
        self,
        processing_queue: Queue,
        config: WatcherConfig,
        settling_checker: Optional[FileSettlingChecker] = None
    ):
        """Initialize the event handler.
        
        Args:
            processing_queue: Queue to add files for processing.
            config: Watcher configuration.
            settling_checker: Optional custom settling checker.
        """
        super().__init__()
        self.queue = processing_queue
        self.config = config
        self.debouncer = DebounceTracker(config.debounce_seconds)
        self.settling_checker = settling_checker or FileSettlingChecker()
        self._processing_set: Set[str] = set()
        self._lock = threading.Lock()

    def _should_ignore(self, file_path: str) -> bool:
        """Check if file matches ignore patterns.
        
        Args:
            file_path: Path to check.
        
        Returns:
            True if file should be ignored.
        """
        name = Path(file_path).name
        return any(
            fnmatch(name, pattern)
            for pattern in self.config.ignore_patterns
        )

    def _is_already_processing(self, file_path: str) -> bool:
        """Check if file is already being processed.
        
        Args:
            file_path: Path to check.
        
        Returns:
            True if file is currently being processed.
        """
        with self._lock:
            return file_path in self._processing_set

    def _mark_processing(self, file_path: str) -> bool:
        """Mark a file as being processed.
        
        Args:
            file_path: Path to mark.
        
        Returns:
            True if successfully marked, False if already processing.
        """
        with self._lock:
            if file_path in self._processing_set:
                return False
            self._processing_set.add(file_path)
            return True

    def mark_complete(self, file_path: str) -> None:
        """Mark a file as complete (no longer processing).
        
        Args:
            file_path: Path to mark as complete.
        """
        with self._lock:
            self._processing_set.discard(file_path)
        self.debouncer.clear(file_path)

    def _handle_file_event(self, file_path: str) -> None:
        """Handle a file event after validation.
        
        Args:
            file_path: Path to the file.
        """
        # Skip directories - only process files
        path = Path(file_path)
        if path.is_dir():
            logger.debug(f"Skipping directory: {file_path}")
            return

        # Skip if should be ignored
        if self._should_ignore(file_path):
            logger.debug(f"Ignoring file (matches pattern): {file_path}")
            return

        # Skip if already processing
        if self._is_already_processing(file_path):
            logger.debug(f"Skipping file (already processing): {file_path}")
            return

        # Check debounce
        if not self.debouncer.should_process(file_path):
            logger.debug(f"Debouncing file event: {file_path}")
            return

        # Wait for file to settle in a separate thread
        def wait_and_enqueue():
            path = Path(file_path)
            if self.settling_checker.wait_for_file(path, timeout=30.0):
                if self._mark_processing(file_path):
                    logger.info(f"Enqueuing file for processing: {file_path}")
                    self.queue.put(file_path)
            else:
                logger.warning(f"File did not settle, skipping: {file_path}")
                self.debouncer.clear(file_path)

        thread = threading.Thread(target=wait_and_enqueue, daemon=True)
        thread.start()

    def on_created(self, event) -> None:
        """Handle file creation events.
        
        Args:
            event: Filesystem event.
        """
        if isinstance(event, DirCreatedEvent):
            return

        logger.debug(f"File created event: {event.src_path}")
        self._handle_file_event(event.src_path)

    def on_modified(self, event) -> None:
        """Handle file modification events.
        
        We only process modifications for files we haven't seen yet,
        to handle cases where the created event was missed.
        
        Args:
            event: Filesystem event.
        """
        # Skip directory events
        if isinstance(event, (DirCreatedEvent, DirModifiedEvent)):
            return

        # Only process if not already in the processing set
        if not self._is_already_processing(event.src_path):
            logger.debug(f"File modified event: {event.src_path}")
            self._handle_file_event(event.src_path)


class FileWatcherService:
    """Main watcher service that monitors directories.
    
    Manages the watchdog Observer and handles starting/stopping
    the monitoring service.
    """

    def __init__(
        self,
        config: WatcherConfig,
        processing_queue: Queue
    ):
        """Initialize the watcher service.
        
        Args:
            config: Watcher configuration.
            processing_queue: Queue to add files for processing.
        """
        self.config = config
        self.queue = processing_queue
        self.observer = Observer()
        self.handler = OrganizerEventHandler(processing_queue, config)
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if the watcher is running."""
        return self._running and self.observer.is_alive()

    def start(self) -> None:
        """Start watching configured directories.
        
        Raises:
            RuntimeError: If no valid directories to watch.
        """
        valid_dirs = []
        for directory in self.config.watch_directories:
            if directory.exists() and directory.is_dir():
                self.observer.schedule(
                    self.handler,
                    str(directory),
                    recursive=self.config.recursive
                )
                valid_dirs.append(directory)
                logger.info(f"Watching directory: {directory}")
            else:
                logger.warning(f"Directory does not exist, skipping: {directory}")

        if not valid_dirs:
            raise RuntimeError("No valid directories to watch")

        self.observer.start()
        self._running = True
        logger.info(f"File watcher started, monitoring {len(valid_dirs)} directories")

    def stop(self) -> None:
        """Stop the watcher service."""
        if self._running:
            self._running = False
            self.observer.stop()
            self.observer.join(timeout=5.0)
            logger.info("File watcher stopped")

    def get_watched_directories(self) -> List[Path]:
        """Get list of directories being watched.
        
        Returns:
            List of directory paths.
        """
        return [
            d for d in self.config.watch_directories
            if d.exists() and d.is_dir()
        ]
