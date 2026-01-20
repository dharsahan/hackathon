"""
Processing Queue Manager
========================

Manages the file processing queue with worker threads.
Implements retry logic, status tracking, and graceful shutdown.
"""

import threading
from queue import Queue, Empty
from typing import Callable, Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import traceback

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ProcessingStatus(Enum):
    """Status of a processing task."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"


@dataclass
class ProcessingTask:
    """Represents a file processing task.

    Attributes:
        file_path: Path to the file to process.
        status: Current processing status.
        retry_count: Number of retry attempts.
        max_retries: Maximum retry attempts allowed.
        created_at: When the task was created.
        started_at: When processing started.
        completed_at: When processing completed.
        error: Error message if failed.
    """

    file_path: str
    status: ProcessingStatus = ProcessingStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    def mark_processing(self) -> None:
        """Mark task as currently processing."""
        self.status = ProcessingStatus.PROCESSING
        self.started_at = datetime.now()

    def mark_completed(self) -> None:
        """Mark task as successfully completed."""
        self.status = ProcessingStatus.COMPLETED
        self.completed_at = datetime.now()

    def mark_failed(self, error: str) -> None:
        """Mark task as failed.

        Args:
            error: Error message or description.
        """
        self.status = ProcessingStatus.FAILED
        self.completed_at = datetime.now()
        self.error = error

    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.retry_count < self.max_retries

    def increment_retry(self) -> None:
        """Increment retry count and mark as retrying."""
        self.retry_count += 1
        self.status = ProcessingStatus.RETRYING
        self.started_at = None
        self.completed_at = None
        self.error = None


@dataclass
class ProcessingStats:
    """Statistics for the processing queue."""

    total_processed: int = 0
    successful: int = 0
    failed: int = 0
    retried: int = 0
    pending: int = 0
    processing: int = 0

    def to_dict(self) -> Dict:
        """Convert stats to dictionary."""
        return {
            "total_processed": self.total_processed,
            "successful": self.successful,
            "failed": self.failed,
            "retried": self.retried,
            "pending": self.pending,
            "processing": self.processing,
        }


class ProcessingQueueManager:
    """Manages the file processing queue with worker threads.

    Features:
    - Thread pool for parallel processing
    - Automatic retry for failed tasks
    - Status tracking and statistics
    - Graceful shutdown support
    """

    def __init__(
        self,
        processor_callback: Callable[[str], bool],
        max_workers: int = 4,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        completion_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize the queue manager.

        Args:
            processor_callback: Function to process each file path.
                               Returns True on success, False on failure.
            max_workers: Maximum number of worker threads.
            max_retries: Maximum retry attempts for failed tasks.
            retry_delay: Delay in seconds between retries.
            completion_callback: Optional callback when a file completes.
        """
        self.queue: Queue[ProcessingTask] = Queue()
        self.processor = processor_callback
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.completion_callback = completion_callback

        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

        # Track active tasks
        self._active_tasks: Dict[str, ProcessingTask] = {}
        self._tasks_lock = threading.Lock()

        # Statistics
        self.stats = ProcessingStats()
        self._stats_lock = threading.Lock()

    def put(self, file_path: str) -> ProcessingTask:
        """Add a file to the processing queue.

        Args:
            file_path: Path to the file to process.

        Returns:
            The created ProcessingTask.
        """
        task = ProcessingTask(file_path=file_path, max_retries=self.max_retries)

        with self._tasks_lock:
            self._active_tasks[file_path] = task

        with self._stats_lock:
            self.stats.pending += 1

        self.queue.put(task)
        logger.debug(f"Added to queue: {file_path}")
        return task

    def start(self) -> None:
        """Start the queue processing workers."""
        if self._running:
            logger.warning("Queue manager already running")
            return

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._process_loop, daemon=True, name="QueueManager-MainLoop"
        )
        self._worker_thread.start()
        logger.info(f"Queue manager started with {self.max_workers} workers")

    def stop(self, wait: bool = True, timeout: float = 10.0) -> None:
        """Stop the queue processing.

        Args:
            wait: Whether to wait for pending tasks to complete.
            timeout: Maximum time to wait in seconds.
        """
        if not self._running:
            return

        self._running = False

        if wait and self._worker_thread:
            self._worker_thread.join(timeout=timeout)

        self.executor.shutdown(wait=wait)
        logger.info("Queue manager stopped")

    def _process_loop(self) -> None:
        """Main processing loop that dequeues and processes tasks."""
        while self._running:
            try:
                task = self.queue.get(timeout=1.0)

                with self._stats_lock:
                    self.stats.pending -= 1
                    self.stats.processing += 1

                # Submit to thread pool (fire-and-forget)
                _ = self.executor.submit(self._process_task, task)

            except Empty:
                # No items in queue, continue waiting
                continue
            except Exception as e:
                logger.error(f"Error in process loop: {e}")

    def _process_task(self, task: ProcessingTask) -> None:
        """Process a single task.

        Args:
            task: The task to process.
        """
        task.mark_processing()
        logger.info(f"Processing file: {task.file_path}")

        try:
            success = self.processor(task.file_path)

            if success:
                task.mark_completed()
                self._handle_success(task)
            else:
                self._handle_failure(task, "Processor returned False")

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Error processing {task.file_path}: {error_msg}")
            logger.debug(traceback.format_exc())
            self._handle_failure(task, error_msg)

    def _handle_success(self, task: ProcessingTask) -> None:
        """Handle successful task completion.

        Args:
            task: The completed task.
        """
        with self._stats_lock:
            self.stats.processing -= 1
            self.stats.total_processed += 1
            self.stats.successful += 1

        with self._tasks_lock:
            self._active_tasks.pop(task.file_path, None)

        logger.info(f"Successfully processed: {task.file_path}")

        if self.completion_callback:
            try:
                self.completion_callback(task.file_path)
            except Exception as e:
                logger.error(f"Error in completion callback: {e}")

    def _handle_failure(self, task: ProcessingTask, error: str) -> None:
        """Handle task failure with retry logic.

        Args:
            task: The failed task.
            error: Error description.
        """
        with self._stats_lock:
            self.stats.processing -= 1

        if task.can_retry():
            task.increment_retry()

            with self._stats_lock:
                self.stats.retried += 1
                self.stats.pending += 1

            logger.warning(
                f"Retrying ({task.retry_count}/{task.max_retries}): "
                f"{task.file_path} - {error}"
            )

            # Delay before retry
            threading.Timer(self.retry_delay, lambda: self.queue.put(task)).start()
        else:
            task.mark_failed(error)

            with self._stats_lock:
                self.stats.total_processed += 1
                self.stats.failed += 1

            with self._tasks_lock:
                self._active_tasks.pop(task.file_path, None)

            logger.error(
                f"Failed after {task.retry_count} retries: "
                f"{task.file_path} - {error}"
            )

    def get_stats(self) -> ProcessingStats:
        """Get current processing statistics.

        Returns:
            Copy of current statistics.
        """
        with self._stats_lock:
            return ProcessingStats(
                total_processed=self.stats.total_processed,
                successful=self.stats.successful,
                failed=self.stats.failed,
                retried=self.stats.retried,
                pending=self.stats.pending,
                processing=self.stats.processing,
            )

    def get_active_tasks(self) -> List[ProcessingTask]:
        """Get list of currently active tasks.

        Returns:
            List of active ProcessingTask objects.
        """
        with self._tasks_lock:
            return list(self._active_tasks.values())

    def get_queue_size(self) -> int:
        """Get current queue size.

        Returns:
            Number of items in queue.
        """
        return self.queue.qsize()

    def is_idle(self) -> bool:
        """Check if queue manager is idle.

        Returns:
            True if no pending or processing tasks.
        """
        with self._stats_lock:
            return self.stats.pending == 0 and self.stats.processing == 0
