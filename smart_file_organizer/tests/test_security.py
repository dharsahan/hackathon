"""
Unit tests for security module.
"""

import pytest
from pathlib import Path
import tempfile
import os

from src.security.key_derivation import KeyDerivationService
from src.security.encryption import AESEncryptor
from src.security.secure_delete import SecureDeleter


class TestKeyDerivationService:
    """Tests for KeyDerivationService."""
    
    @pytest.fixture
    def service(self):
        """Create service with fast parameters for testing."""
        return KeyDerivationService(
            memory_cost=1024,  # Low for fast tests
            time_cost=1,
            parallelism=1
        )
    
    def test_derive_key(self, service):
        """Test basic key derivation."""
        if not service.is_available():
            pytest.skip("argon2 not available")
        
        result = service.derive_key("test_password")
        
        assert len(result.key) == 32  # 256 bits
        assert len(result.salt) == 16  # 128 bits
        assert result.params['algorithm'] == 'argon2id'
    
    def test_consistent_with_same_salt(self, service):
        """Test same password + salt gives same key."""
        if not service.is_available():
            pytest.skip("argon2 not available")
        
        salt = service.generate_salt()
        
        result1 = service.derive_key("password123", salt)
        result2 = service.derive_key("password123", salt)
        
        assert result1.key == result2.key
    
    def test_different_with_different_salt(self, service):
        """Test different salts give different keys."""
        if not service.is_available():
            pytest.skip("argon2 not available")
        
        result1 = service.derive_key("password123")
        result2 = service.derive_key("password123")
        
        # Different random salts = different keys
        assert result1.key != result2.key
    
    def test_verify_password(self, service):
        """Test password verification."""
        if not service.is_available():
            pytest.skip("argon2 not available")
        
        derived = service.derive_key("correct_password")
        
        assert service.verify_password(
            "correct_password",
            derived.salt,
            derived.key
        ) is True
        
        assert service.verify_password(
            "wrong_password",
            derived.salt,
            derived.key
        ) is False


class TestAESEncryptor:
    """Tests for AESEncryptor."""
    
    @pytest.fixture
    def encryptor(self):
        """Create encryptor instance."""
        return AESEncryptor()
    
    def test_encrypt_decrypt_bytes(self, encryptor):
        """Test encryption and decryption of bytes."""
        if not encryptor.is_available():
            pytest.skip("cryptography not available")
        
        key = os.urandom(32)
        plaintext = b"Hello, this is a secret message!"
        
        encrypted = encryptor.encrypt_bytes(plaintext, key)
        decrypted = encryptor.decrypt_bytes(encrypted, key)
        
        assert decrypted == plaintext
        assert encrypted != plaintext
    
    def test_different_nonces(self, encryptor):
        """Test same plaintext produces different ciphertext."""
        if not encryptor.is_available():
            pytest.skip("cryptography not available")
        
        key = os.urandom(32)
        plaintext = b"Same message"
        
        encrypted1 = encryptor.encrypt_bytes(plaintext, key)
        encrypted2 = encryptor.encrypt_bytes(plaintext, key)
        
        # Different nonces = different ciphertext
        assert encrypted1 != encrypted2
    
    def test_invalid_key_size(self, encryptor):
        """Test error on invalid key size."""
        if not encryptor.is_available():
            pytest.skip("cryptography not available")
        
        with pytest.raises(Exception):
            encryptor.encrypt_bytes(b"test", b"short_key")
    
    def test_file_encryption(self, encryptor):
        """Test file encryption and decryption."""
        if not encryptor.is_available():
            pytest.skip("cryptography not available")
        
        key = os.urandom(32)
        content = b"File content to encrypt"
        
        with tempfile.NamedTemporaryFile(delete=False) as src, \
             tempfile.NamedTemporaryFile(delete=False) as enc, \
             tempfile.NamedTemporaryFile(delete=False) as dec:
            src.write(content)
            src.flush()
            
            encryptor.encrypt_file(Path(src.name), Path(enc.name), key)
            encryptor.decrypt_file(Path(enc.name), Path(dec.name), key)
            
            with open(dec.name, 'rb') as f:
                decrypted = f.read()
            
            assert decrypted == content
            
            os.unlink(src.name)
            os.unlink(enc.name)
            os.unlink(dec.name)


class TestSecureDeleter:
    """Tests for SecureDeleter."""
    
    @pytest.fixture
    def deleter(self):
        """Create deleter with 1 pass for fast tests."""
        return SecureDeleter(passes=1)
    
    def test_secure_delete(self, deleter):
        """Test secure file deletion."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Content to delete securely")
            f.flush()
            path = Path(f.name)
        
        assert path.exists()
        
        result = deleter.secure_delete(path)
        
        assert result is True
        assert not path.exists()
    
    def test_delete_nonexistent_file(self, deleter):
        """Test deleting non-existent file returns False."""
        result = deleter.secure_delete(Path("/nonexistent/file.txt"))
        
        assert result is False
    
    def test_quick_delete(self, deleter):
        """Test quick delete with single pass."""
        deleter = SecureDeleter(passes=3)  # Default 3 passes
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Quick delete test")
            f.flush()
            path = Path(f.name)
        
        result = deleter.quick_delete(path)
        
        assert result is True
        assert not path.exists()
