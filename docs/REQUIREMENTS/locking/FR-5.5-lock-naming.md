# FR-5.5, Lock naming

| ID | Requirement | |
|---|---|---|
| FR-5.5 | A lock file shall be named for a digest of the resolved path, so that different spellings of one location share a lock and different locations do not. Lock files shall live in the configured lock directory, or by default under the per-user runtime directory; with neither available, LockError shall be raised before any lock file is opened. | [A] |
