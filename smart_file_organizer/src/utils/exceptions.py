"""
Custom Exceptions
=================

Defines custom exception classes for the Smart File Organizer.
All exceptions include error codes for programmatic handling.
"""

from enum import Enum
from typing import Optional, Any


class ErrorCode(Enum):
    """Error codes for programmatic error handling."""
    
    # General errors (1000-1099)
    UNKNOWN_ERROR = 1000
    CONFIGURATION_ERROR = 1001
    FILE_NOT_FOUND = 1002
    PERMISSION_DENIED = 1003
    
    # Processing errors (1100-1199)
    PROCESSING_FAILED = 1100
    UNSUPPORTED_FILE_TYPE = 1101
    FILE_TOO_LARGE = 1102
    FILE_CORRUPTED = 1103
    
    # Classification errors (1200-1299)
    CLASSIFICATION_FAILED = 1200
    LLM_UNAVAILABLE = 1201
    OCR_FAILED = 1202
    EXTRACTION_FAILED = 1203
    
    # Security errors (1300-1399)
    ENCRYPTION_FAILED = 1300
    DECRYPTION_FAILED = 1301
    KEY_DERIVATION_FAILED = 1302
    SECURE_DELETE_FAILED = 1303
    INVALID_PASSWORD = 1304
    
    # Deduplication errors (1400-1499)
    DEDUPLICATION_FAILED = 1400
    HASH_COMPUTATION_FAILED = 1401
    INDEX_CORRUPTED = 1402


class SmartOrganizerError(Exception):
    """Base exception for all Smart File Organizer errors.
    
    Attributes:
        message: Human-readable error message.
        error_code: Programmatic error code.
        details: Additional error context.
        cause: Original exception that caused this error.
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        details: Optional[dict] = None,
        cause: Optional[Exception] = None
    ):
        """Initialize the exception.
        
        Args:
            message: Human-readable error description.
            error_code: Programmatic error code.
            details: Additional context as key-value pairs.
            cause: Original exception if wrapping another error.
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
    
    def __str__(self) -> str:
        """Return a formatted error string."""
        result = f"[{self.error_code.name}] {self.message}"
        if self.details:
            result += f" | Details: {self.details}"
        if self.cause:
            result += f" | Caused by: {type(self.cause).__name__}: {self.cause}"
        return result
    
    def to_dict(self) -> dict:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "error_type": type(self).__name__,
            "message": self.message,
            "error_code": self.error_code.value,
            "error_name": self.error_code.name,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
        }


class ConfigurationError(SmartOrganizerError):
    """Raised when there's a configuration problem.
    
    Examples:
        - Invalid configuration file format
        - Missing required configuration values
        - Invalid configuration values
    """
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        expected_type: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if config_key:
            details["config_key"] = config_key
        if expected_type:
            details["expected_type"] = expected_type
        super().__init__(
            message,
            error_code=ErrorCode.CONFIGURATION_ERROR,
            details=details,
            **kwargs
        )


class FileProcessingError(SmartOrganizerError):
    """Raised when file processing fails.
    
    Examples:
        - File cannot be read
        - File is corrupted
        - File type not supported
    """
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.PROCESSING_FAILED,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if file_path:
            details["file_path"] = file_path
        super().__init__(
            message,
            error_code=error_code,
            details=details,
            **kwargs
        )


class ClassificationError(SmartOrganizerError):
    """Raised when file classification fails.
    
    Examples:
        - LLM not available
        - Unable to extract text
        - Classification timeout
    """
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        tier: Optional[int] = None,
        error_code: ErrorCode = ErrorCode.CLASSIFICATION_FAILED,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if file_path:
            details["file_path"] = file_path
        if tier:
            details["classification_tier"] = tier
        super().__init__(
            message,
            error_code=error_code,
            details=details,
            **kwargs
        )


class ExtractionError(SmartOrganizerError):
    """Raised when text/content extraction fails.
    
    Examples:
        - PDF parsing error
        - OCR failure
        - Unsupported document format
    """
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        extractor_type: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if file_path:
            details["file_path"] = file_path
        if extractor_type:
            details["extractor_type"] = extractor_type
        super().__init__(
            message,
            error_code=ErrorCode.EXTRACTION_FAILED,
            details=details,
            **kwargs
        )


class EncryptionError(SmartOrganizerError):
    """Raised when encryption/decryption fails.
    
    Examples:
        - Invalid password
        - Corrupted encrypted file
        - Key derivation failure
    """
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        operation: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.ENCRYPTION_FAILED,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if file_path:
            details["file_path"] = file_path
        if operation:
            details["operation"] = operation
        super().__init__(
            message,
            error_code=error_code,
            details=details,
            **kwargs
        )


class DeduplicationError(SmartOrganizerError):
    """Raised when deduplication operations fail.
    
    Examples:
        - Hash computation failure
        - Index corruption
        - File comparison error
    """
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        hash_type: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.DEDUPLICATION_FAILED,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if file_path:
            details["file_path"] = file_path
        if hash_type:
            details["hash_type"] = hash_type
        super().__init__(
            message,
            error_code=error_code,
            details=details,
            **kwargs
        )
