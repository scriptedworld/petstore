"""Exclusive, cross-process locks named for a filesystem path.

    from petstore import locked

    with locked("/srv/app/socket"):
        ...  # no other process holding a lock on that path runs this concurrently

The lock is an advisory ``flock`` on a lock file named for the path, not on the
path itself. The path does not need to exist and can name anything (a file, a
socket, a directory), and locking never interferes with other users of the
thing it names. Paths are resolved first, so different spellings of one location
share a lock, symlinks included.

Lock files live in a per-user runtime directory, ``$XDG_RUNTIME_DIR/petstore/locks``
by default. There is deliberately no fallback to a shared directory such as
``/tmp``, where another user could hold the lock or plant a symlink in its place;
without a runtime directory, pass ``lock_dir`` to ``make_locked``. Lock files are
left in place after release, because deleting one would let a waiter lock a file
that a newcomer can no longer see.

Waiting blocks indefinitely unless a ``timeout`` in seconds is given, in which
case ``LockTimeoutError`` is raised once it passes. A lock is not re-entrant:
acquiring the same path again while holding it waits on yourself.

Only POSIX systems provide ``flock``.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from contextlib import AbstractContextManager

__all__ = ["LockError", "LockPolicy", "LockTimeoutError", "PathLocker", "locked", "make_locked"]

StrPath = str | os.PathLike[str]

# How long to sleep between attempts while waiting with a timeout.
_POLL_SECONDS = 0.05


class LockError(Exception):
    """Raised when a path lock cannot be set up or acquired."""


class LockTimeoutError(LockError, TimeoutError):
    """Raised when a path lock is still held by another holder after the timeout."""


class LockPolicy(NamedTuple):
    """Operating-system boundaries used to wait for, take, and give up a path lock."""

    runtime_dir: Callable[[], str | None]
    open_lock: Callable[[Path], int]
    try_lock: Callable[[int], bool]
    wait_lock: Callable[[int], None]
    release: Callable[[int], None]
    clock: Callable[[], float]
    sleep: Callable[[float], None]


class PathLocker(Protocol):
    """The operational signature of a composed path lock."""

    def __call__(self, path: StrPath, *, timeout: float | None = None) -> AbstractContextManager[None]:
        """Hold an exclusive lock named for *path* for the duration of a with block."""


def _runtime_dir() -> str | None:
    """Return the per-user runtime directory, if the session defines one."""
    return os.environ.get("XDG_RUNTIME_DIR")


def _open_lock(lock_file: Path) -> int:
    """Create the lock file privately if needed and open a descriptor on it."""
    lock_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return os.open(lock_file, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)


def _try_lock(handle: int) -> bool:
    """Take the exclusive lock without waiting, reporting whether it was free."""
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    return True


def _wait_lock(handle: int) -> None:
    """Take the exclusive lock, waiting for as long as another holder keeps it."""
    fcntl.flock(handle, fcntl.LOCK_EX)


def _release(handle: int) -> None:
    """Give up the lock, including for any forked child sharing it, then close."""
    fcntl.flock(handle, fcntl.LOCK_UN)
    os.close(handle)


PRODUCTION_LOCK_POLICY = LockPolicy(
    runtime_dir=_runtime_dir,
    open_lock=_open_lock,
    try_lock=_try_lock,
    wait_lock=_wait_lock,
    release=_release,
    clock=time.monotonic,
    sleep=time.sleep,
)


def _lock_file(path: StrPath, directory: Path) -> Path:
    """Name the lock file for *path*: a digest of its resolved location."""
    digest = hashlib.sha256(os.fsencode(Path(path).resolve())).hexdigest()
    return directory / f"{digest}.lock"


def _lock_directory(lock_dir: Path | None, runtime_dir: str | None) -> Path:
    """Choose the directory lock files live in."""
    if lock_dir is not None:
        return lock_dir
    if not runtime_dir:
        message = "XDG_RUNTIME_DIR is not set; pass lock_dir to make_locked() to choose where lock files live"
        raise LockError(message)
    return Path(runtime_dir) / "petstore" / "locks"


def _acquire(handle: int, path: StrPath, *, timeout: float | None, policy: LockPolicy) -> None:
    """Take the lock on an open handle, waiting at most *timeout* seconds if given."""
    if timeout is None:
        policy.wait_lock(handle)
        return
    deadline = policy.clock() + timeout
    while not policy.try_lock(handle):
        remaining = deadline - policy.clock()
        if remaining <= 0:
            message = f"lock on {os.fspath(path)!r} still held after {timeout} seconds"
            raise LockTimeoutError(message)
        policy.sleep(min(_POLL_SECONDS, remaining))


@contextmanager
def _locked(path: StrPath, *, timeout: float | None, lock_dir: Path | None, policy: LockPolicy) -> Iterator[None]:
    """Implement holding a path lock with explicit boundary strategies."""
    if timeout is not None and timeout < 0:
        message = f"timeout must not be negative, got {timeout}"
        raise ValueError(message)
    directory = _lock_directory(lock_dir, policy.runtime_dir())
    handle = policy.open_lock(_lock_file(path, directory))
    try:
        _acquire(handle, path, timeout=timeout, policy=policy)
        yield
    finally:
        policy.release(handle)


def make_locked(*, lock_dir: Path | None = None, policy: LockPolicy = PRODUCTION_LOCK_POLICY) -> PathLocker:
    """Bind a lock directory and boundaries, returning the operational path lock.

    Args:
        lock_dir: Where lock files live. Defaults to a directory under
            ``$XDG_RUNTIME_DIR``, looked up each time a lock is taken.
        policy: The operating-system boundaries to use.

    Returns:
        A callable used as ``with locker(path, timeout=...):``.

    """

    def locker(path: StrPath, *, timeout: float | None = None) -> AbstractContextManager[None]:
        """Hold an exclusive lock named for *path* for the duration of a with block."""
        return _locked(path, timeout=timeout, lock_dir=lock_dir, policy=policy)

    return locker


locked = make_locked()
