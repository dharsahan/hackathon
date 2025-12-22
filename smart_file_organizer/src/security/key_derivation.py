"""
Key Derivation Service
======================

Secure key derivation using Argon2id.
Generates encryption keys from passwords with memory-hard protection.
"""

import os
import secrets
from dataclasses import dataclass
from typing import Optional

from src.utils.logging_config import get_logger
from src.utils.exceptions import EncryptionError, ErrorCode

logger = get_logger(__name__)

# Lazy import for argon2
argon2 = None


def _import_argon2():
    """Lazy import argon2."""
    global argon2
    if argon2 is None:
        try:
            from argon2.low_level import hash_secret_raw, Type
            argon2 = {'hash_secret_raw': hash_secret_raw, 'Type': Type}
        except ImportError:
            argon2 = False
    return argon2


@dataclass
class DerivedKey:
    """Container for derived cryptographic key.
    
    Attributes:
        key: The derived key bytes.
        salt: Salt used for derivation.
        params: Parameters used for key derivation.
    """
    key: bytes
    salt: bytes
    params: dict = None
    
    def __post_init__(self):
        if self.params is None:
            self.params = {}
    
    def to_dict(self) -> dict:
        """Convert to dictionary (excludes key for safety)."""
        return {
            "salt_hex": self.salt.hex(),
            "key_length": len(self.key),
            "params": self.params,
        }


class KeyDerivationService:
    """Secure key derivation using Argon2id.
    
    Argon2id is the recommended password hashing algorithm,
    providing protection against both side-channel and GPU attacks.
    """
    
    # OWASP recommended parameters
    DEFAULT_MEMORY_COST = 65536    # 64 MB
    DEFAULT_TIME_COST = 3          # 3 iterations
    DEFAULT_PARALLELISM = 4        # 4 threads
    DEFAULT_HASH_LENGTH = 32       # 256 bits (for AES-256)
    DEFAULT_SALT_LENGTH = 16       # 128 bits
    
    def __init__(
        self,
        memory_cost: int = DEFAULT_MEMORY_COST,
        time_cost: int = DEFAULT_TIME_COST,
        parallelism: int = DEFAULT_PARALLELISM,
        hash_length: int = DEFAULT_HASH_LENGTH
    ):
        """Initialize key derivation service.
        
        Args:
            memory_cost: Memory cost in KB.
            time_cost: Number of iterations.
            parallelism: Degree of parallelism.
            hash_length: Length of derived key in bytes.
        """
        self.memory_cost = memory_cost
        self.time_cost = time_cost
        self.parallelism = parallelism
        self.hash_length = hash_length
    
    def derive_key(
        self,
        password: str,
        salt: Optional[bytes] = None
    ) -> DerivedKey:
        """Derive a cryptographic key from a password.
        
        Args:
            password: The password to derive from.
            salt: Optional salt. Generated if not provided.
        
        Returns:
            DerivedKey containing key and salt.
        
        Raises:
            EncryptionError: If key derivation fails.
        """
        argon2_lib = _import_argon2()
        
        if not argon2_lib or argon2_lib is False:
            raise EncryptionError(
                "argon2-cffi library not available",
                operation="key_derivation",
                error_code=ErrorCode.KEY_DERIVATION_FAILED
            )
        
        # Generate salt if not provided
        if salt is None:
            salt = secrets.token_bytes(self.DEFAULT_SALT_LENGTH)
        
        try:
            key = argon2_lib['hash_secret_raw'](
                secret=password.encode('utf-8'),
                salt=salt,
                time_cost=self.time_cost,
                memory_cost=self.memory_cost,
                parallelism=self.parallelism,
                hash_len=self.hash_length,
                type=argon2_lib['Type'].ID  # Argon2id
            )
            
            logger.debug("Key derived successfully")
            
            return DerivedKey(
                key=key,
                salt=salt,
                params={
                    "algorithm": "argon2id",
                    "memory_cost": self.memory_cost,
                    "time_cost": self.time_cost,
                    "parallelism": self.parallelism,
                    "hash_length": self.hash_length,
                }
            )
            
        except Exception as e:
            raise EncryptionError(
                f"Key derivation failed: {e}",
                operation="key_derivation",
                error_code=ErrorCode.KEY_DERIVATION_FAILED
            )
    
    def verify_password(
        self,
        password: str,
        salt: bytes,
        expected_key: bytes
    ) -> bool:
        """Verify a password against a previously derived key.
        
        Args:
            password: Password to verify.
            salt: Salt used in original derivation.
            expected_key: Expected derived key.
        
        Returns:
            True if password matches.
        """
        try:
            derived = self.derive_key(password, salt)
            return secrets.compare_digest(derived.key, expected_key)
        except EncryptionError:
            return False
    
    def generate_salt(self) -> bytes:
        """Generate a cryptographically secure salt.
        
        Returns:
            Random salt bytes.
        """
        return secrets.token_bytes(self.DEFAULT_SALT_LENGTH)
    
    def is_available(self) -> bool:
        """Check if key derivation is available.
        
        Returns:
            True if argon2 library is installed.
        """
        argon2_lib = _import_argon2()
        return argon2_lib and argon2_lib is not False
