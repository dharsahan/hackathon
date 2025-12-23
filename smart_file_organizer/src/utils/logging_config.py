"""
Logging Configuration
=====================

Provides structured JSON logging with correlation IDs for request tracing.
Supports both console and file output with configurable log levels.
"""

import logging
import logging.handlers
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
import threading


# Thread-local storage for correlation IDs
_thread_local = threading.local()


def get_correlation_id() -> str:
    """Get the current correlation ID for the thread."""
    if not hasattr(_thread_local, 'correlation_id'):
        _thread_local.correlation_id = str(uuid.uuid4())[:8]
    return _thread_local.correlation_id


def set_correlation_id(correlation_id: str) -> None:
    """Set a correlation ID for the current thread."""
    _thread_local.correlation_id = correlation_id


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, 'file_path'):
            log_data["file_path"] = record.file_path
        if hasattr(record, 'category'):
            log_data["category"] = record.category
        if hasattr(record, 'operation'):
            log_data["operation"] = record.operation
        if hasattr(record, 'duration_ms'):
            log_data["duration_ms"] = record.duration_ms

        return json.dumps(log_data)


class ConsoleFormatter(logging.Formatter):
    """Human-readable colored console formatter."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        """Format with colors for console output."""
        color = self.COLORS.get(record.levelname, '')
        timestamp = datetime.now().strftime('%H:%M:%S')

        # Build the message
        msg = f"{color}[{timestamp}] {record.levelname:8}{self.RESET} "
        msg += f"[{get_correlation_id()}] "
        msg += f"{record.name}: {record.getMessage()}"

        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)

        return msg


@dataclass
class LoggingConfig:
    """Configuration for the logging system."""
    level: str = "INFO"
    log_dir: Path = field(default_factory=lambda: Path.home() / ".smart_organizer" / "logs")
    console_output: bool = True
    file_output: bool = True
    json_format: bool = False  # Use JSON for console
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


def setup_logging(config: Optional[LoggingConfig] = None) -> None:
    """Set up the logging system.
    
    Args:
        config: Logging configuration. Uses defaults if not provided.
    """
    if config is None:
        config = LoggingConfig()

    # Get the root logger for our application
    root_logger = logging.getLogger("smart_organizer")
    root_logger.setLevel(getattr(logging, config.level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    if config.console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        if config.json_format:
            console_handler.setFormatter(JSONFormatter())
        else:
            console_handler.setFormatter(ConsoleFormatter())
        root_logger.addHandler(console_handler)

    # File handler
    if config.file_output:
        config.log_dir.mkdir(parents=True, exist_ok=True)
        log_file = config.log_dir / "smart_organizer.log"

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=config.max_file_size,
            backupCount=config.backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    # Prevent propagation to root logger
    root_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.
    
    Args:
        name: Name of the module (typically __name__).
    
    Returns:
        Logger instance with the correct prefix.
    """
    if name.startswith("src."):
        name = name[4:]  # Remove 'src.' prefix
    return logging.getLogger(f"smart_organizer.{name}")


class LogContext:
    """Context manager for adding extra context to log messages."""

    def __init__(self, logger: logging.Logger, **context):
        """Initialize with context fields.
        
        Args:
            logger: Logger to add context to.
            **context: Key-value pairs to add to log records.
        """
        self.logger = logger
        self.context = context
        self._old_factory = None

    def __enter__(self):
        """Set up the log record factory with extra context."""
        old_factory = logging.getLogRecordFactory()
        context = self.context

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            for key, value in context.items():
                setattr(record, key, value)
            return record

        self._old_factory = old_factory
        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore the original log record factory."""
        if self._old_factory:
            logging.setLogRecordFactory(self._old_factory)
        return False


class Timer:
    """Context manager for timing operations and logging duration."""

    def __init__(self, logger: logging.Logger, operation: str):
        """Initialize timer.
        
        Args:
            logger: Logger to log the duration to.
            operation: Name of the operation being timed.
        """
        self.logger = logger
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        """Start the timer."""
        import time
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the timer and log the duration."""
        import time
        duration_ms = (time.perf_counter() - self.start_time) * 1000

        old_factory = logging.getLogRecordFactory()

        def factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.operation = self.operation
            record.duration_ms = round(duration_ms, 2)
            return record

        logging.setLogRecordFactory(factory)
        self.logger.info(f"Operation completed: {self.operation}")
        logging.setLogRecordFactory(old_factory)

        return False
