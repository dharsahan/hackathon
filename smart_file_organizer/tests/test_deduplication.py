"""
Unit tests for deduplication module.
"""


from pathlib import Path
import tempfile
import os

from src.deduplication.hash_engine import (
    DeduplicationEngine,
    PartialHasher,
    FullHasher,
    DuplicateStatus,
)


class TestPartialHasher:
    """Tests for PartialHasher."""
    
    def test_small_file_full_hash(self):
        """Test small files get full hash."""
        hasher = PartialHasher(chunk_size=4096)
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Hello, World!")
            f.flush()
            
            hash1 = hasher.compute(Path(f.name))
            hash2 = hasher.compute(Path(f.name))
            
            assert hash1 == hash2
            assert len(hash1) == 64  # SHA-256 hex
            
            os.unlink(f.name)
    
    def test_large_file_partial_hash(self):
        """Test large files get partial hash."""
        hasher = PartialHasher(chunk_size=1024)
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # Write > 3 chunks
            f.write(os.urandom(5000))
            f.flush()
            
            hash1 = hasher.compute(Path(f.name))
            
            assert len(hash1) == 64
            
            os.unlink(f.name)
    
    def test_different_files_different_hashes(self):
        """Test different files produce different hashes."""
        hasher = PartialHasher()
        
        with tempfile.NamedTemporaryFile(delete=False) as f1, \
             tempfile.NamedTemporaryFile(delete=False) as f2:
            f1.write(b"File 1 content")
            f2.write(b"File 2 content")
            f1.flush()
            f2.flush()
            
            hash1 = hasher.compute(Path(f1.name))
            hash2 = hasher.compute(Path(f2.name))
            
            assert hash1 != hash2
            
            os.unlink(f1.name)
            os.unlink(f2.name)


class TestFullHasher:
    """Tests for FullHasher."""
    
    def test_consistent_hash(self):
        """Test same file always produces same hash."""
        hasher = FullHasher()
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Test content for hashing")
            f.flush()
            
            hash1 = hasher.compute(Path(f.name))
            hash2 = hasher.compute(Path(f.name))
            
            assert hash1 == hash2
            
            os.unlink(f.name)
    
    def test_md5_hash(self):
        """Test MD5 hash computation."""
        hasher = FullHasher()
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Test")
            f.flush()
            
            md5 = hasher.compute_md5(Path(f.name))
            
            assert len(md5) == 32  # MD5 hex length
            
            os.unlink(f.name)


class TestDeduplicationEngine:
    """Tests for DeduplicationEngine."""
    
    def test_unique_file(self):
        """Test unique file detection."""
        engine = DeduplicationEngine()
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Unique content 12345")
            f.flush()
            
            result = engine.check_duplicate(Path(f.name))
            
            assert result.status == DuplicateStatus.UNIQUE
            assert result.duplicate_of is None
            
            os.unlink(f.name)
    
    def test_duplicate_detection(self):
        """Test exact duplicate detection."""
        engine = DeduplicationEngine()
        
        content = b"Duplicate content test"
        
        with tempfile.NamedTemporaryFile(delete=False) as f1, \
             tempfile.NamedTemporaryFile(delete=False) as f2:
            f1.write(content)
            f2.write(content)
            f1.flush()
            f2.flush()
            
            result1 = engine.check_duplicate(Path(f1.name))
            result2 = engine.check_duplicate(Path(f2.name))
            
            assert result1.status == DuplicateStatus.UNIQUE
            assert result2.status == DuplicateStatus.EXACT_DUPLICATE
            assert result2.duplicate_of == Path(f1.name)
            
            os.unlink(f1.name)
            os.unlink(f2.name)
    
    def test_add_to_index(self):
        """Test adding files to index."""
        engine = DeduplicationEngine()
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Index test content")
            f.flush()
            
            result = engine.add_to_index(Path(f.name))
            
            assert result.partial_hash is not None
            assert result.full_hash is not None
            
            # Check it's in the index
            stats = engine.get_stats()
            assert stats['unique_full_hashes'] == 1
            
            os.unlink(f.name)
    
    def test_clear_index(self):
        """Test clearing the index."""
        engine = DeduplicationEngine()
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Clear test")
            f.flush()
            
            engine.add_to_index(Path(f.name))
            engine.clear()
            
            stats = engine.get_stats()
            assert stats['unique_full_hashes'] == 0
            
            os.unlink(f.name)
