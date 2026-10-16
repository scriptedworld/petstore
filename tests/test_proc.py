"""Tests for starting other programs, run against real child processes."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import assert_type

import pytest

import petstore.proc
from petstore.proc import Error, Failed, Result, TimeoutExpired, capture, through

PYTHON = sys.executable
EXITED = 3


def _python(code: str) -> list[str]:
    """Return a command running code in this interpreter."""
    return [PYTHON, "-c", code]


# COVERS FR-6.1 | positive
def test_capture_returns_the_exit_status_and_both_streams_as_text() -> None:
    """Verify capture collects stdout, stderr and the status of a finished program."""
    finished = capture(_python(f"import sys; print('out'); print('err', file=sys.stderr); sys.exit({EXITED})"))

    assert finished.returncode == EXITED
    assert finished.stdout == "out\n"
    assert finished.stderr == "err\n"


# COVERS FR-6.2 | negative
def test_capture_with_check_raises_on_a_non_zero_exit() -> None:
    """Verify check=True turns a failing exit into Failed carrying the status."""
    with pytest.raises(Failed) as failure:
        capture(_python(f"import sys; sys.exit({EXITED})"), check=True)

    assert failure.value.returncode == EXITED
    assert capture(_python("pass"), check=True).returncode == 0


# COVERS FR-6.2 | edge
def test_capture_raises_when_the_timeout_passes_first() -> None:
    """Verify a program outliving its timeout raises TimeoutExpired."""
    with pytest.raises(TimeoutExpired):
        capture(_python("import time; time.sleep(5)"), timeout=0.2)


# COVERS FR-6.3 | positive
def test_through_hands_streams_with_a_descriptor_to_the_child(tmp_path: Path) -> None:
    """Verify the child writes straight into real files and its status comes back."""
    out_path, err_path = tmp_path / "out", tmp_path / "err"
    with out_path.open("w") as out, err_path.open("w") as err:
        status = through(_python(f"import sys; print('o'); print('e', file=sys.stderr); sys.exit({EXITED})"), out, err)

    assert status == EXITED
    assert out_path.read_text() == "o\n"
    assert err_path.read_text() == "e\n"


# COVERS FR-6.3 | edge
def test_through_writes_captured_output_to_streams_without_a_descriptor() -> None:
    """Verify output still reaches a StringIO, which a child cannot write to."""
    out, err = io.StringIO(), io.StringIO()

    status = through(_python("import sys; print('o'); print('e', file=sys.stderr)"), out, err)

    assert status == 0
    assert out.getvalue() == "o\n"
    assert err.getvalue() == "e\n"


# COVERS FR-6.4 | positive
def test_wait_flushes_stdout_before_the_child_writes() -> None:
    """Verify a buffered heading reaches the pipe before the child's own output."""
    parent = (
        "import sys; from petstore.proc import wait; "
        "sys.stdout.write('heading\\n'); "
        f"status = wait([{PYTHON!r}, '-c', 'print(\"child\"); raise SystemExit(5)']); "
        "print(status)"
    )

    assert capture(_python(parent), check=True).stdout == "heading\nchild\n5\n"


# COVERS FR-6.5 | positive
def test_become_flushes_then_replaces_the_process_with_a_program_on_path() -> None:
    """Verify become flushes, then runs a program from PATH in this process's place."""
    executable = Path(PYTHON)
    parent = (
        "import sys; from petstore.proc import become; "
        "sys.stdout.write('before\\n'); "
        f"become([{executable.name!r}, '-c', 'print(\"after\")']); "
        "print('returned')"
    )

    finished = capture(_python(parent), env={"PATH": str(executable.parent)}, check=True)

    assert finished.stdout == "before\nafter\n"


# COVERS FR-6.6 | property
@pytest.mark.parametrize(
    "argument",
    ["two words", "; echo injected", "$(echo expanded)", "`echo ticked`", "a | b > c", "'\"", "*", ""],
)
def test_an_argument_reaches_the_child_as_one_argument(argument: str) -> None:
    """Verify no shell splits, expands or interprets an argument."""
    finished = capture([*_python("import sys; print(repr(sys.argv[1:]))"), argument], check=True)

    assert finished.stdout == f"{[argument]!r}\n"


# COVERS FR-6.7 | positive
def test_a_caller_names_every_outcome_from_petstore_proc() -> None:
    """Verify results and failures are named here, so a caller needs no subprocess import."""
    assert isinstance(capture(_python("pass")), Result)
    assert issubclass(Failed, Error)
    assert issubclass(TimeoutExpired, Error)
    with pytest.raises(Error):
        capture(_python(f"raise SystemExit({EXITED})"), check=True)
    assert set(petstore.proc.__all__) >= {"Error", "Failed", "Result", "TimeoutExpired"}


# COVERS FR-6.8 | positive
def test_capture_runs_in_the_given_directory_with_only_the_given_environment(tmp_path: Path) -> None:
    """Verify cwd and env reach the child, and env replaces this process's environment."""
    code = "import os; print(os.getcwd()); print(os.environ.get('PROBE')); print('HOME' in os.environ)"

    finished = capture(_python(code), cwd=tmp_path, env={"PROBE": "set"}, check=True)

    assert finished.stdout.splitlines() == [str(tmp_path.resolve()), "set", "False"]


# COVERS FR-6.9 | positive
def test_capture_writes_a_string_to_standard_input_and_returns_text() -> None:
    """Verify a string reaches the child's stdin, which is closed after it, and output stays text."""
    finished = capture(_python("import sys; print(repr(sys.stdin.read()))"), stdin="one\ntwo\n", check=True)

    assert_type(finished, Result[str])
    assert finished.stdout == "'one\\ntwo\\n'\n"


# COVERS FR-6.9 | edge
def test_an_empty_string_gives_the_child_an_empty_closed_stdin() -> None:
    """Verify stdin='' is an input of nothing, so a child reading to the end gets no line."""
    finished = capture(_python("import sys; print(repr(sys.stdin.read()))"), stdin="", check=True)

    assert finished.stdout == "''\n"


# COVERS FR-6.9 | positive
def test_wait_writes_a_string_to_the_child_in_place_of_this_process_stdin() -> None:
    """Verify wait feeds the child the given string, not the parent's own standard input."""
    parent = (
        "from petstore.proc import wait; "
        f"status = wait([{PYTHON!r}, '-c', 'import sys; print(sys.stdin.read().upper())'], stdin='fed'); "
        "print(status)"
    )

    assert capture(_python(parent), stdin="parent's own", check=True).stdout == "FED\n0\n"


# COVERS FR-6.10 | positive
def test_bytes_reach_the_child_unchanged_and_output_returns_as_bytes() -> None:
    """Verify a NUL and a byte no codec decodes pass through, and both streams come back as bytes."""
    reverse = "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read()[::-1]); sys.stderr.buffer.write(b'\\xfe')"

    finished = capture(_python(reverse), stdin=b"run.sh\0\xff", check=True)

    assert_type(finished, Result[bytes])
    assert finished.stdout == b"\xff\0hs.nur"
    assert finished.stderr == b"\xfe"
