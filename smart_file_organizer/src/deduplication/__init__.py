"""Deduplication module."""

from .hash_engine import (
    DeduplicationEngine,
    PartialHasher,
    FullHasher,
    HashResult,
    DuplicateStatus,
)
from .perceptual_hash import PerceptualHashEngine, PerceptualHashResult

__all__ = [
    "DeduplicationEngine",
    "PartialHasher",
    "FullHasher",
    "HashResult",
    "DuplicateStatus",
    "PerceptualHashEngine",
    "PerceptualHashResult",
]
