## 2024-05-23 - Lazy Partial Hashing Optimization
**Learning:** In deduplication systems, most files have unique sizes. Deferring even the "cheap" partial hash computation (reading 3 chunks) until a size collision occurs saves significant I/O for the majority of files.
**Action:** When designing multi-stage filters (Size -> Partial Hash -> Full Hash), consider if the earlier stages can be made even lazier by deferring computation until a collision in the *previous* stage actually mandates it.

## 2024-05-24 - Small File Hash Reuse
**Learning:** For small files (<= 3 * chunk_size), the partial hash computation effectively reads the entire file. Reusing this partial hash as the full hash eliminates a redundant second read and hash computation.
**Action:** When implementing multi-stage hashing, check if an earlier "partial" stage inadvertently completed the work of a later "full" stage for certain inputs (like small files).
