"""The one place a program using petstore starts another program.

Running a named program is what many tools are for, and bandit cannot tell
that from injection. Collecting every start in this module makes that one
judgement, registered once in ``SUPPRESSIONS/starting-another-program.md``,
not one per call site in every tool that needs it. A test suite starts its
programs through ``capture`` too, so it carries no pragma of its own.

What keeps a caller safe is upstream of here: pass commands built from
literals and paths the caller owns, never from untrusted input. A list is
passed, never a string, and no shell is involved, so a value carrying a space
or a semicolon is one argument, not two commands.
"""

from __future__ import annotations

import os
import subprocess  # nosec B404
import sys
from typing import IO, TYPE_CHECKING, Any, NamedTuple, NoReturn, TypedDict, Unpack, overload

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

__all__ = ["Error", "Failed", "Result", "TimeoutExpired", "become", "capture", "through", "wait"]

# The failures a caller names, so catching one does not mean importing
# subprocess somewhere else.
Failed = subprocess.CalledProcessError
Error = subprocess.SubprocessError
Result = subprocess.CompletedProcess
TimeoutExpired = subprocess.TimeoutExpired

_Stream = IO[str] | int | None


class _Where(NamedTuple):
    """Where and for how long a program runs."""

    timeout: float | None = None
    cwd: str | Path | None = None
    env: Mapping[str, str] | None = None


_HERE = _Where()


def _run(
    cmd: Sequence[str],
    *,
    stdout: _Stream = None,
    stderr: _Stream = None,
    stdin: str | bytes | None = None,
    where: _Where = _HERE,
) -> subprocess.CompletedProcess[Any]:
    """Start cmd as a list, never through a shell. Every run below comes here.

    The exit status is never checked here; a caller that wants a failure
    raised asks the result for it. Bytes for stdin run the program without
    text mode, so a NUL or an undecodable byte reaches it unchanged and its
    output comes back as bytes.
    """
    return subprocess.run(  # noqa: S603
        list(cmd),  # nosec B603
        input=stdin,
        text=not isinstance(stdin, bytes),
        check=False,
        stdout=stdout,
        stderr=stderr,
        timeout=where.timeout,
        cwd=where.cwd,
        env=where.env,
    )


class _WhereArgs(TypedDict, total=False):
    """The keywords naming where and for how long, as capture takes them."""

    timeout: float | None
    cwd: str | Path | None
    env: Mapping[str, str] | None


@overload
def capture(
    cmd: Sequence[str],
    *,
    stdin: bytes,
    check: bool = False,
    **where: Unpack[_WhereArgs],
) -> subprocess.CompletedProcess[bytes]: ...


@overload
def capture(
    cmd: Sequence[str],
    *,
    stdin: str | None = None,
    check: bool = False,
    **where: Unpack[_WhereArgs],
) -> subprocess.CompletedProcess[str]: ...


def capture(
    cmd: Sequence[str],
    *,
    stdin: str | bytes | None = None,
    check: bool = False,
    **where: Unpack[_WhereArgs],
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    """Run to completion with stdout and stderr captured, as text unless stdin is bytes.

    Args:
        cmd: The program and its arguments.
        stdin: Written to the program's standard input, which is then closed.
            Bytes run it without text mode and return its output as bytes.
        check: Raise ``Failed`` on a non-zero exit.
        **where: Any of ``timeout``, the seconds to wait before giving up;
            ``cwd``, the directory the program runs in; and ``env``, the
            program's whole environment, in place of this process's.

    Returns:
        The finished program, with its exit status and output.

    Raises:
        Failed: When check is true and the program exits non-zero.
        TimeoutExpired: When timeout passes first.

    """
    finished = _run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=stdin, where=_Where(**where))
    if check:
        finished.check_returncode()
    return finished


def through(cmd: Sequence[str], stdout: IO[str], stderr: IO[str], *, timeout: float | None = None) -> int:
    """Run with the child writing to these streams, and return its exit status.

    A stream with no file descriptor, such as a ``StringIO``, cannot be handed
    to a child, so the output is captured and written to it instead; it
    reaches the stream it was given either way.
    """
    if _has_descriptor(stdout) and _has_descriptor(stderr):
        return _run(cmd, stdout=stdout, stderr=stderr, where=_Where(timeout)).returncode
    finished = capture(cmd, timeout=timeout)
    stdout.write(finished.stdout)
    stderr.write(finished.stderr)
    return finished.returncode


def wait(cmd: Sequence[str], *, stdin: str | bytes | None = None) -> int:
    """Run with this process's own streams, and return its exit status.

    stdout is flushed first: ``print()`` is block-buffered when piped, while
    the child writes straight to the descriptor, so without the flush its
    output arrives before the heading that introduces it. Given stdin, the
    child reads that instead of this process's standard input.
    """
    sys.stdout.flush()
    return _run(cmd, stdin=stdin).returncode


def become(cmd: Sequence[str]) -> NoReturn:
    """Replace this process with cmd, found on PATH. It does not return."""
    sys.stdout.flush()
    os.execvp(  # noqa: S606
        cmd[0],
        list(cmd),  # nosec B606
    )


def _has_descriptor(stream: IO[str]) -> bool:
    """Whether a child process can write to stream directly."""
    try:
        stream.fileno()
    except AttributeError, OSError, ValueError:
        return False
    return True
