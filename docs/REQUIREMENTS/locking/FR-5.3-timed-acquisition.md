# FR-5.3, Timed acquisition

| ID | Requirement | |
|---|---|---|
| FR-5.3 | With a timeout, acquisition shall retry without blocking, sleeping no longer than the time remaining, until the lock is free or the timeout passes, at which point LockTimeoutError shall be raised. A zero timeout shall make exactly one attempt. A negative timeout shall raise ValueError before any lock file is opened. | [A] |

Formerly PS-LOCK-003.
