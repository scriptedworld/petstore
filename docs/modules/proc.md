# Starting other programs

Module: `petstore.proc`

Public API: `capture`, `through`, `wait`, `become`, and the failure names
`Failed`, `Error`, `Result` and `TimeoutExpired`, all from `petstore.proc`.

## Purpose

Every program a tool starts goes through this module, so bandit's judgement
about starting programs is made once, in petstore, and registered in
`SUPPRESSIONS/starting-another-program.md`. A tool or a test suite that starts
programs through it carries no pragma of its own.

A command is always a sequence of strings and no shell is involved, so each
element reaches the program as one argument. Build commands from literals and
paths you own; never from untrusted input.

## Usage

```python
import sys

from petstore.proc import Failed, become, capture, through, wait

finished = capture(["git", "status", "--short"], cwd="/srv/repo")
finished.returncode, finished.stdout, finished.stderr

capture(["git", "fetch"], check=True, timeout=30)  # raises Failed or TimeoutExpired

through(["make"], sys.stdout, sys.stderr)  # the child writes to these streams
wait(["less", "README.md"])  # the child uses this process's streams
become(["python3", "-m", "http.server"])  # replaces this process; never returns
```

`capture` runs to completion with both streams captured as text. `check=True`
raises `Failed` on a non-zero exit, `timeout` raises `TimeoutExpired` when it
passes first, and `env` replaces this process's environment rather than adding
to it.

`through` hands its streams to the child when both have a file descriptor. A
stream with none, such as a `StringIO`, cannot be given to a child, so the
output is captured and written to it instead.

`wait` and `become` flush stdout first. `print()` is block-buffered when stdout
is a pipe, while the child writes straight to the descriptor, so without the
flush the child's output would arrive before whatever was printed ahead of it.
`become` finds its program on `PATH`.

## Testing code that uses it

Start a real program. `sys.executable -c` runs a short Python script as the
child, which is what petstore's own tests do, and needs no mock and no seam.

## Requirements

[`docs/REQUIREMENTS/proc/`](../REQUIREMENTS/proc/) holds this module's
requirements, `FR-6.x`, one file each. Tests cite them with a
`# COVERS <ids> | <kind>` comment directly above the test.
