## 2024-05-23 - Lazy Partial Hashing Optimization
**Learning:** In deduplication systems, most files have unique sizes. Deferring even the "cheap" partial hash computation (reading 3 chunks) until a size collision occurs saves significant I/O for the majority of files.
**Action:** When designing multi-stage filters (Size -> Partial Hash -> Full Hash), consider if the earlier stages can be made even lazier by deferring computation until a collision in the *previous* stage actually mandates it.

## 2024-05-23 - Reuse Partial Hash for Small Files
**Learning:** For small files (<= 3 * chunk_size), the "partial" hash calculation reads the entire file. Reusing this result as the "full" hash avoids a completely redundant second read/hash operation during the full hash verification stage.
**Action:** Implement `is_calculating_full_hash()` in partial hashers to signal when the partial result can be promoted to a full result safely.
