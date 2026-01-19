## 2024-05-23 - Lazy Partial Hashing Optimization
**Learning:** In deduplication systems, most files have unique sizes. Deferring even the "cheap" partial hash computation (reading 3 chunks) until a size collision occurs saves significant I/O for the majority of files.
**Action:** When designing multi-stage filters (Size -> Partial Hash -> Full Hash), consider if the earlier stages can be made even lazier by deferring computation until a collision in the *previous* stage actually mandates it.

## 2024-05-24 - Small File Deduplication Efficiency
**Learning:** When using partial hashing, small files (size <= 3 chunks) are effectively fully hashed during the "partial" stage. Re-running the full hasher in a later stage is redundant and doubles the I/O cost.
**Action:** In multi-stage processing pipelines, detect if an early "approximation" stage has inadvertently completed the work of a later "precise" stage, and reuse the result.
