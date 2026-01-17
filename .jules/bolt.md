## 2024-05-23 - Lazy Partial Hashing Optimization
**Learning:** In deduplication systems, most files have unique sizes. Deferring even the "cheap" partial hash computation (reading 3 chunks) until a size collision occurs saves significant I/O for the majority of files.
**Action:** When designing multi-stage filters (Size -> Partial Hash -> Full Hash), consider if the earlier stages can be made even lazier by deferring computation until a collision in the *previous* stage actually mandates it.

## 2024-05-24 - Reuse Partial Hash for Small Files
**Learning:** For files smaller than the total sample size (e.g., 3 chunks), the "partial" hash calculation reads the entire file. Re-reading the file to compute the "full" hash is redundant.
**Action:** Check if the partial hash covered the entire file (based on file size) and reuse the result as the full hash to avoid unnecessary I/O.
