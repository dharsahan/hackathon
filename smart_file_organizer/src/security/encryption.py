"""
AES-256 Encryption
==================

Provides AES-256-GCM encryption for securing sensitive files.
Supports both raw byte encryption and encrypted archive creation.
"""

from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
import os

from src.utils.logging_config import get_logger
from src.utils.exceptions import EncryptionError, ErrorCode

logger = get_logger(__name__)

# Lazy imports
AESGCM = None
pyzipper = None


def _import_cryptography():
    """Lazy import cryptography."""
    global AESGCM
    if AESGCM is None:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM
            AESGCM = _AESGCM
        except ImportError:
            AESGCM = False
    return AESGCM


def _import_pyzipper():
    """Lazy import pyzipper."""
    global pyzipper
    if pyzipper is None:
        try:
            import pyzipper as _pyzipper
            pyzipper = _pyzipper
        except ImportError:
            pyzipper = False
    return pyzipper


@dataclass
class EncryptedData:
    """Container for encrypted data.
    
    Attributes:
        ciphertext: Encrypted data including nonce.
        nonce_size: Size of nonce prefix.
    """
    ciphertext: bytes
    nonce_size: int = 12
    
    @property
    def nonce(self) -> bytes:
        """Extract nonce from ciphertext."""
        return self.ciphertext[:self.nonce_size]
    
    @property
    def encrypted_content(self) -> bytes:
        """Extract encrypted content without nonce."""
        return self.ciphertext[self.nonce_size:]


class AESEncryptor:
    """AES-256-GCM encryption for data and files.
    
    Uses Galois/Counter Mode (GCM) for authenticated encryption,
    providing both confidentiality and integrity.
    """
    
    NONCE_SIZE = 12      # 96 bits (recommended for GCM)
    KEY_SIZE = 32        # 256 bits
    BUFFER_SIZE = 65536  # 64KB chunk for file operations
    
    def __init__(self):
        """Initialize AES encryptor."""
        self._verify_available()
    
    def _verify_available(self) -> None:
        """Verify cryptography library is available."""
        AESGCM_cls = _import_cryptography()
        if not AESGCM_cls or AESGCM_cls is False:
            logger.warning("cryptography library not available")
    
    def encrypt_bytes(
        self,
        data: bytes,
        key: bytes,
        associated_data: Optional[bytes] = None
    ) -> bytes:
        """Encrypt data using AES-256-GCM.
        
        Args:
            data: Data to encrypt.
            key: 256-bit encryption key.
            associated_data: Optional additional authenticated data.
        
        Returns:
            Nonce + ciphertext bytes.
        
        Raises:
            EncryptionError: If encryption fails.
        """
        AESGCM_cls = _import_cryptography()
        if not AESGCM_cls or AESGCM_cls is False:
            raise EncryptionError(
                "cryptography library not available",
                operation="encrypt",
                error_code=ErrorCode.ENCRYPTION_FAILED
            )
        
        if len(key) != self.KEY_SIZE:
            raise EncryptionError(
                f"Key must be {self.KEY_SIZE} bytes",
                operation="encrypt",
                error_code=ErrorCode.ENCRYPTION_FAILED
            )
        
        try:
            nonce = os.urandom(self.NONCE_SIZE)
            aesgcm = AESGCM_cls(key)
            ciphertext = aesgcm.encrypt(nonce, data, associated_data)
            return nonce + ciphertext
            
        except Exception as e:
            raise EncryptionError(
                f"Encryption failed: {e}",
                operation="encrypt",
                error_code=ErrorCode.ENCRYPTION_FAILED
            )
    
    def decrypt_bytes(
        self,
        encrypted_data: bytes,
        key: bytes,
        associated_data: Optional[bytes] = None
    ) -> bytes:
        """Decrypt data using AES-256-GCM.
        
        Args:
            encrypted_data: Nonce + ciphertext bytes.
            key: 256-bit decryption key.
            associated_data: Optional additional authenticated data.
        
        Returns:
            Decrypted plaintext bytes.
        
        Raises:
            EncryptionError: If decryption fails.
        """
        AESGCM_cls = _import_cryptography()
        if not AESGCM_cls or AESGCM_cls is False:
            raise EncryptionError(
                "cryptography library not available",
                operation="decrypt",
                error_code=ErrorCode.DECRYPTION_FAILED
            )
        
        if len(key) != self.KEY_SIZE:
            raise EncryptionError(
                f"Key must be {self.KEY_SIZE} bytes",
                operation="decrypt",
                error_code=ErrorCode.DECRYPTION_FAILED
            )
        
        if len(encrypted_data) <= self.NONCE_SIZE:
            raise EncryptionError(
                "Invalid encrypted data: too short",
                operation="decrypt",
                error_code=ErrorCode.DECRYPTION_FAILED
            )
        
        try:
            nonce = encrypted_data[:self.NONCE_SIZE]
            ciphertext = encrypted_data[self.NONCE_SIZE:]
            
            aesgcm = AESGCM_cls(key)
            return aesgcm.decrypt(nonce, ciphertext, associated_data)
            
        except Exception as e:
            raise EncryptionError(
                f"Decryption failed: {e}",
                operation="decrypt",
                error_code=ErrorCode.DECRYPTION_FAILED
            )
    
    def encrypt_file(
        self,
        input_path: Path,
        output_path: Path,
        key: bytes
    ) -> Path:
        """Encrypt a file.
        
        Args:
            input_path: Path to file to encrypt.
            output_path: Path for encrypted output.
            key: 256-bit encryption key.
        
        Returns:
            Path to encrypted file.
        """
        with open(input_path, 'rb') as f:
            data = f.read()
        
        encrypted = self.encrypt_bytes(data, key)
        
        with open(output_path, 'wb') as f:
            f.write(encrypted)
        
        logger.info(f"Encrypted file: {input_path.name} -> {output_path.name}")
        return output_path
    
    def decrypt_file(
        self,
        input_path: Path,
        output_path: Path,
        key: bytes
    ) -> Path:
        """Decrypt a file.
        
        Args:
            input_path: Path to encrypted file.
            output_path: Path for decrypted output.
            key: 256-bit decryption key.
        
        Returns:
            Path to decrypted file.
        """
        with open(input_path, 'rb') as f:
            encrypted = f.read()
        
        decrypted = self.decrypt_bytes(encrypted, key)
        
        with open(output_path, 'wb') as f:
            f.write(decrypted)
        
        logger.info(f"Decrypted file: {input_path.name} -> {output_path.name}")
        return output_path
    
    def is_available(self) -> bool:
        """Check if encryption is available.
        
        Returns:
            True if cryptography library is installed.
        """
        AESGCM_cls = _import_cryptography()
        return AESGCM_cls and AESGCM_cls is not False


class SecureArchiver:
    """Creates AES-256 encrypted ZIP archives.
    
    Uses pyzipper for creating password-protected ZIP files
    with AES-256 encryption.
    """
    
    def __init__(self):
        """Initialize secure archiver."""
        pass
    
    def create_archive(
        self,
        file_paths: List[Path],
        archive_path: Path,
        password: str,
        compression_level: int = 9
    ) -> Path:
        """Create an encrypted ZIP archive.
        
        Args:
            file_paths: List of files to archive.
            archive_path: Path for output archive.
            password: Password for encryption.
            compression_level: Compression level (0-9).
        
        Returns:
            Path to created archive.
        
        Raises:
            EncryptionError: If archive creation fails.
        """
        pyzipper_lib = _import_pyzipper()
        if not pyzipper_lib or pyzipper_lib is False:
            raise EncryptionError(
                "pyzipper library not available",
                operation="create_archive",
                error_code=ErrorCode.ENCRYPTION_FAILED
            )
        
        try:
            with pyzipper_lib.AESZipFile(
                archive_path,
                'w',
                compression=pyzipper_lib.ZIP_LZMA,
                encryption=pyzipper_lib.WZ_AES
            ) as zf:
                zf.setpassword(password.encode('utf-8'))
                zf.setencryption(pyzipper_lib.WZ_AES, nbits=256)
                
                for file_path in file_paths:
                    if file_path.exists():
                        zf.write(file_path, arcname=file_path.name)
            
            logger.info(f"Created encrypted archive: {archive_path.name}")
            return archive_path
            
        except Exception as e:
            raise EncryptionError(
                f"Failed to create archive: {e}",
                file_path=str(archive_path),
                operation="create_archive",
                error_code=ErrorCode.ENCRYPTION_FAILED
            )
    
    def create_single_file_archive(
        self,
        file_path: Path,
        password: str
    ) -> Path:
        """Create encrypted archive from single file.
        
        Args:
            file_path: File to archive.
            password: Password for encryption.
        
        Returns:
            Path to created archive.
        """
        archive_path = file_path.with_suffix('.zip')
        return self.create_archive([file_path], archive_path, password)
    
    def extract_archive(
        self,
        archive_path: Path,
        password: str,
        dest_dir: Path
    ) -> List[Path]:
        """Extract files from encrypted archive.
        
        Args:
            archive_path: Path to archive.
            password: Password for decryption.
            dest_dir: Destination directory.
        
        Returns:
            List of extracted file paths.
        
        Raises:
            EncryptionError: If extraction fails.
        """
        pyzipper_lib = _import_pyzipper()
        if not pyzipper_lib or pyzipper_lib is False:
            raise EncryptionError(
                "pyzipper library not available",
                operation="extract_archive",
                error_code=ErrorCode.DECRYPTION_FAILED
            )
        
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with pyzipper_lib.AESZipFile(archive_path, 'r') as zf:
                zf.setpassword(password.encode('utf-8'))
                zf.extractall(dest_dir)
                extracted = [dest_dir / name for name in zf.namelist()]
            
            logger.info(
                f"Extracted {len(extracted)} files from {archive_path.name}"
            )
            return extracted
            
        except Exception as e:
            raise EncryptionError(
                f"Failed to extract archive: {e}",
                file_path=str(archive_path),
                operation="extract_archive",
                error_code=ErrorCode.DECRYPTION_FAILED
            )
    
    def is_available(self) -> bool:
        """Check if archiver is available.
        
        Returns:
            True if pyzipper library is installed.
        """
        pyzipper_lib = _import_pyzipper()
        return pyzipper_lib and pyzipper_lib is not False
