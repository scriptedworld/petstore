"""Tests for exclusive, cross-process path locks."""

from __future__ import annotations

import hashlib
import multiprocessing
import os
import stat
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from petstore.locking import LockError, LockPolicy, LockTimeoutError, _locked, _runtime_dir, make_locked
from petstore.stubs import Stub

if TYPE_CHECKING:
    from contextlib import AbstractContextManager
    from multiprocessing.synchronize import Event

HANDLE = 7
RUNTIME_DIR = "/run/user/test"
FREE = True
HELD = False


def _stubs(**overrides: Stub[..., Any]) -> dict[str, Stub[..., Any]]:
    """Return a scripted stub for every lock boundary, replacing the named ones."""
    defaults = {
        "runtime_dir": Stub().returns(RUNTIME_DIR).always(),
        "open_lock": Stub(parameters=["lock_file"]).returns(HANDLE).always(),
        "try_lock": Stub(parameters=["handle"]).returns(FREE).always(),
        "wait_lock": Stub(parameters=["handle"]).returns(None).always(),
        "release": Stub(parameters=["handle"]).returns(None).always(),
        "clock": Stub().returns(0.0).always(),
        "sleep": Stub(parameters=["seconds"]).returns(None).always(),
    }
    return defaults | overrides


def _policy(stubs: dict[str, Stub[..., Any]]) -> LockPolicy:
    """Assemble a lock policy from scripted boundary stubs."""
    return LockPolicy(**stubs)


def _enter(manager: AbstractContextManager[None]) -> None:
    """Enter and leave a context manager, so a failure to enter can be asserted."""
    with manager:
        pass


def _opened_lock_file(stubs: dict[str, Stub[..., Any]]) -> Path:
    """Return the lock file the first acquisition asked to open."""
    bound = stubs["open_lock"].calls[0].bound_arguments
    assert bound is not None
    lock_file = bound["lock_file"]
    assert isinstance(lock_file, Path)
    return lock_file


def _hold_lock(lock_dir: Path, target: Path, held: Event, done: Event) -> None:
    """Hold a real lock in a child process until the parent says to let go."""
    with make_locked(lock_dir=lock_dir)(target):
        held.set()
        done.wait(timeout=10)


# COVERS FR-5.1 | property
def test_a_held_lock_excludes_a_second_holder_until_released(tmp_path: Path) -> None:
    """Verify a second holder cannot acquire a held lock, and can once it is released."""
    locker = make_locked(lock_dir=tmp_path)
    target = tmp_path / "resource"

    with locker(target, timeout=0), pytest.raises(LockTimeoutError):
        _enter(locker(target, timeout=0))

    _enter(locker(target, timeout=0))


# COVERS FR-5.1 | positive
def test_a_lock_held_in_another_process_excludes_this_one(tmp_path: Path) -> None:
    """Verify exclusion holds across processes, not only within one."""
    locker = make_locked(lock_dir=tmp_path)
    target = tmp_path / "resource"
    context = multiprocessing.get_context("fork")
    held = context.Event()
    done = context.Event()
    child = context.Process(target=_hold_lock, args=(tmp_path, target, held, done))

    child.start()
    try:
        assert held.wait(timeout=10)
        with pytest.raises(LockTimeoutError):
            _enter(locker(target, timeout=0))
    finally:
        done.set()
        child.join(timeout=10)

    assert child.exitcode == 0
    _enter(locker(target, timeout=0))


# COVERS FR-5.2 | positive
def test_without_a_timeout_acquisition_blocks_once_instead_of_polling() -> None:
    """Verify a blocking wait makes one blocking attempt and never polls."""
    stubs = _stubs()

    _enter(_locked("alpha", timeout=None, lock_dir=None, policy=_policy(stubs)))

    assert stubs["wait_lock"].calls[0].args == (HANDLE,)
    assert stubs["try_lock"].call_count == 0
    assert stubs["sleep"].call_count == 0


# COVERS FR-5.3 | positive
def test_with_a_timeout_acquisition_retries_until_the_lock_is_free() -> None:
    """Verify failed attempts sleep one poll interval and try again."""
    held_attempts = 2
    stubs = _stubs(
        try_lock=Stub(parameters=["handle"]).returns(HELD).times(held_attempts).returns(FREE),
        clock=Stub().returns(0.0).returns(0.02).returns(0.04),
    )

    _enter(_locked("alpha", timeout=1, lock_dir=None, policy=_policy(stubs)))

    assert stubs["try_lock"].call_count == held_attempts + 1
    assert [call.args for call in stubs["sleep"].calls] == [(0.05,), (0.05,)]
    assert stubs["wait_lock"].call_count == 0


# COVERS FR-5.3 | negative
def test_acquisition_times_out_when_the_lock_stays_held() -> None:
    """Verify LockTimeoutError once the timeout passes, and a negative timeout is refused."""
    stubs = _stubs(
        try_lock=Stub(parameters=["handle"]).returns(HELD).always(),
        clock=Stub().returns(0.0).returns(0.5).returns(1.0),
    )

    with pytest.raises(LockTimeoutError, match=r"still held after 1 seconds"):
        _enter(_locked("alpha", timeout=1, lock_dir=None, policy=_policy(stubs)))

    refused = _stubs()
    with pytest.raises(ValueError, match=r"must not be negative"):
        _enter(_locked("alpha", timeout=-1, lock_dir=None, policy=_policy(refused)))
    assert refused["open_lock"].call_count == 0


# COVERS FR-5.3 | edge
def test_zero_timeout_tries_once_and_short_waits_never_oversleep() -> None:
    """Verify a zero timeout makes one attempt, and a sleep never exceeds the time remaining."""
    single = _stubs(try_lock=Stub(parameters=["handle"]).returns(HELD).always())
    with pytest.raises(LockTimeoutError):
        _enter(_locked("alpha", timeout=0, lock_dir=None, policy=_policy(single)))
    assert single["try_lock"].call_count == 1
    assert single["sleep"].call_count == 0

    short = _stubs(
        try_lock=Stub(parameters=["handle"]).returns(HELD).returns(FREE),
        clock=Stub().returns(0.0).returns(0.01),
    )
    _enter(_locked("alpha", timeout=0.03, lock_dir=None, policy=_policy(short)))
    assert short["sleep"].calls[0].args[0] == pytest.approx(0.02)


# COVERS FR-5.4 | property
def test_the_lock_is_released_when_the_block_exits_normally() -> None:
    """Verify a clean exit releases the handle exactly once."""
    stubs = _stubs()

    _enter(_locked("alpha", timeout=None, lock_dir=None, policy=_policy(stubs)))

    assert [call.args for call in stubs["release"].calls] == [(HANDLE,)]


# COVERS FR-5.4 | negative
def test_the_lock_is_released_when_the_block_raises_or_acquisition_times_out() -> None:
    """Verify failures inside the block or while waiting still release the handle."""
    raising = _stubs()
    message = "work failed"
    with pytest.raises(RuntimeError, match=message), _locked("alpha", timeout=None, lock_dir=None, policy=_policy(raising)):
        raise RuntimeError(message)
    assert raising["release"].call_count == 1

    timing_out = _stubs(try_lock=Stub(parameters=["handle"]).returns(HELD).always())
    with pytest.raises(LockTimeoutError):
        _enter(_locked("alpha", timeout=0, lock_dir=None, policy=_policy(timing_out)))
    assert timing_out["release"].call_count == 1


# COVERS FR-5.5 | positive
def test_lock_files_are_digests_of_the_resolved_path_in_the_lock_directory(tmp_path: Path) -> None:
    """Verify the default runtime directory, an explicit directory, and the digest name."""
    target = tmp_path / "resource"
    expected_name = hashlib.sha256(os.fsencode(target.resolve())).hexdigest() + ".lock"

    runtime = _stubs()
    _enter(_locked(target, timeout=None, lock_dir=None, policy=_policy(runtime)))
    explicit = _stubs()
    _enter(_locked(target, timeout=None, lock_dir=tmp_path, policy=_policy(explicit)))

    assert _opened_lock_file(runtime) == Path(RUNTIME_DIR) / "petstore" / "locks" / expected_name
    assert _opened_lock_file(explicit) == tmp_path / expected_name


# COVERS FR-5.5 | edge
def test_spellings_of_one_location_share_a_lock_and_other_locations_do_not(tmp_path: Path) -> None:
    """Verify naming follows the resolved location rather than the text of the path."""
    (tmp_path / "nested").mkdir()
    stubs = _stubs()
    policy = _policy(stubs)

    for spelling in (tmp_path / "resource", tmp_path / "nested" / ".." / "resource", tmp_path / "other"):
        _enter(_locked(spelling, timeout=None, lock_dir=tmp_path, policy=policy))

    names = [call.bound_arguments for call in stubs["open_lock"].calls]
    assert names[0] == names[1]
    assert names[0] != names[2]


# COVERS FR-5.5 | negative
def test_without_a_runtime_or_lock_directory_no_lock_file_is_opened() -> None:
    """Verify a missing runtime directory is reported rather than guessed around."""
    stubs = _stubs(runtime_dir=Stub().returns(None).always())

    with pytest.raises(LockError, match=r"XDG_RUNTIME_DIR is not set"):
        _enter(_locked("alpha", timeout=None, lock_dir=None, policy=_policy(stubs)))

    assert stubs["open_lock"].call_count == 0


# COVERS FR-5.6 | positive
def test_the_composed_lock_and_runtime_boundary_use_the_real_system(tmp_path: Path) -> None:
    """Verify the factory binds its directory and the production boundaries work end to end."""
    locker = make_locked(lock_dir=tmp_path)

    with locker(tmp_path / "resource"):
        assert len(list(tmp_path.glob("*.lock"))) == 1

    assert _runtime_dir() == os.environ.get("XDG_RUNTIME_DIR")


# COVERS FR-5.6 | property
def test_lock_directories_and_files_are_private_to_their_owner(tmp_path: Path) -> None:
    """Verify a newly created lock directory and lock file grant nothing to others."""
    lock_dir = tmp_path / "locks"

    _enter(make_locked(lock_dir=lock_dir)(tmp_path / "resource"))

    (lock_file,) = lock_dir.glob("*.lock")
    assert stat.S_IMODE(lock_dir.stat().st_mode) & 0o077 == 0
    assert stat.S_IMODE(lock_file.stat().st_mode) & 0o077 == 0
