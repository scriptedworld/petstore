# Path locks

Module: `petstore.locking`

Public API: `petstore.locked`, `petstore.make_locked`, `petstore.LockError`,
`petstore.LockTimeoutError`, `petstore.locking.LockPolicy`,
`petstore.locking.PathLocker`

## Purpose

This module provides an exclusive lock named for a filesystem path and honored
across processes. It serializes work that concerns one location, a socket, a
file being rewritten, a directory being rebuilt, among independent processes
that agree on the path, without those processes sharing anything else.

## Usage

```python
from petstore import LockTimeoutError, locked

with locked("/srv/app/socket"):
    ...  # no other holder of this path's lock runs concurrently

try:
    with locked("/srv/app/socket", timeout=5):
        ...
except LockTimeoutError:
    ...  # still held by someone else after five seconds
```

Without a timeout, acquisition waits for as long as another holder keeps the
lock. With one, it retries until the lock is free or the timeout passes. A zero
timeout makes exactly one attempt.

## Semantics

The lock is an advisory `flock` on a lock file named for a digest of the resolved
path, not on the path itself. The path does not need to exist and can name
anything, and locking never interferes with other users of the thing it names.
Because paths are resolved first, different spellings of one location share a
lock, symlinks included. Being advisory, it excludes only other holders of the
same lock, not arbitrary processes touching the path.

Lock files live in `$XDG_RUNTIME_DIR/petstore/locks`: per-user, private, and
cleared at logout. There is deliberately no fallback to a shared directory such
as `/tmp`, where another user could hold the lock or plant a symlink. Where no
runtime directory exists, such as some system services, choose one explicitly:

```python
from pathlib import Path

from petstore import make_locked

service_locked = make_locked(lock_dir=Path("/var/lib/myservice/locks"))

with service_locked("/var/lib/myservice/state"):
    ...
```

Lock files are left in place after release. Deleting one would let a waiter
hold a lock on a file that a newcomer can no longer see, so two holders could
run at once.

A lock is not re-entrant: acquiring the same path again while holding it waits
on yourself. A forked child inherits a lock its parent holds, and the lock is
released for both when the holder's block exits. Only POSIX systems provide
`flock`.

## Canonical requirements

[`locking.requirements.yaml`](locking.requirements.yaml) is the sole normative
source for this module's requirements. Requirement statements must not be
duplicated or edited in this Markdown file.

The YAML registry is append-only after requirements become active. IDs are
never deleted or reused; replaced behavior is retained with `status: retired`
and linked to its replacement through `superseded_by`.

| ID | Status | Title |
| --- | --- | --- |
| `PS-LOCK-001` | Active | Cross-process exclusion |
| `PS-LOCK-002` | Active | Blocking acquisition |
| `PS-LOCK-003` | Active | Timed acquisition |
| `PS-LOCK-004` | Active | Release |
| `PS-LOCK-005` | Active | Lock naming |
| `PS-LOCK-006` | Active | Composition and production boundaries |
