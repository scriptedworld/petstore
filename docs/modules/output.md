# Program output

Module: `petstore.output`

Public API: `configure`, and the filter run as `python -m petstore.output`.

This guide is the module's spec. The module is not built yet; the
requirements, tests and code are derived from this file. A line saying
*Checked* cites a probe under `evidence/` in clank's
`tasks/petstore/output/10-spec-the-output-module` task, which regenerates what
it states when run from this tree's `.ephemera/felix-output/`.

## Purpose

A Python program writes its output through `logging`, never `print` and never
a direct write to `sys.stdout` or `sys.stderr`, and petstore carries the module
that sets it up, so every project takes the same handlers and the same form
from one release. That is the ruling in silo
`docs/DECISIONS/program-output-goes-through-logging.md`.

What it writes is for a machine first. Each entry is one JSON object, so
whatever reads a program's output can always parse it, and a person reads it
through the filter below. Those rulings are the same file's section "Every
entry is one JSON object", silo `4b60289`.

This module is the one place in petstore, and in a program using it, that
writes to the standard streams, as `petstore.proc` is the one place that starts
another program.

## Usage

```python
import logging

from petstore import output

log = logging.getLogger(__name__)


def main() -> int:
    output.configure()
    log.info("%s", uri)  # data: one object on stdout
    log.error("refused: %s", why)  # for a person: one object on stderr
    return 0
```

    python -m template.new list projects 2>&1 | python -m petstore.output

## The entry

Each entry is one JSON object with these members:

    level     the record's level name, such as "INFO"
    logger    the logger's name, such as "template.new"
    time      when the record was made, ISO 8601 in UTC
    message   the message, with its arguments applied
    exception the formatted traceback, present only when the record has one

`message` holds the message exactly as the program made it. A line of data
logged as `log.info("%s", line)` is recovered by parsing the object and taking
`message`, character for character, newlines and all. Nothing is appended to it
and nothing is stripped.

An entry is written as compact JSON with every non-ASCII character escaped,
so what reaches the stream is ASCII. A message no encoding could carry, such as
a path holding an undecodable byte, still writes, and parses back to the same
string. Checked: `json.dumps` with `ensure_ascii` writes `"café \udcff"`
for that message and `json.loads` returns it unchanged
(`evidence/probe_json.py`).

### Reading a stream

A stream is a sequence of JSON objects. A reader parses objects; it never
splits on newlines, and the module promises nothing about where newlines fall
between or inside entries. Today each entry is followed by one newline; that
is a convenience to a person looking at raw output, not part of the contract.

## Which stream

    INFO up to, not including, WARNING    stdout
    every other level that is enabled     stderr

stdout carries a program's results and stderr everything else: warnings and
errors, and DEBUG when a program enables it. A program whose stdout is read by
another program logs only its results at INFO.

The streams are looked up when each entry is written, not when `configure` is
called, so pytest's `capsys`, `contextlib.redirect_stdout` and anything else
that replaces `sys.stdout` sees the entry. Checked under pytest: a handler
holding the stream it was built with lost a later test's line and wrote
`--- Logging error ---` instead, while one that looks the stream up wrote it
(`evidence/test_probe_capture.py`, tests b and d).

Each entry is flushed when it is written, so it reaches the stream before
anything a child started afterwards writes.

## When a write fails

A failed write raises from the logging call, as `print` does: a closed pipe
raises `BrokenPipeError` at `log.info`. logging's default is to print
`--- Logging error ---` with a traceback to stderr and carry on, which loses
the line and leaves the exit status at 0. Checked: 200000 records into
`head -1` wrote 3199971 lines of those reports to stderr, where `print` raised
on the first failed write (`evidence/run_probes.sh`). A handler
whose `handleError` raises propagates the error out of the logging call
(`evidence/test_probe_capture.py`, test e).

## configure

`configure()` takes no arguments and is called by an entry point, once, before
it logs.

- It puts two handlers on the root logger, one per stream as above, and sets
  the root level to INFO.
- Called again, it replaces the handlers it put there before. One record is
  never written twice, however many times it is called.
- It leaves every other handler alone, on the root logger and elsewhere.
  pytest keeps its own handlers on the root logger for `caplog` and its
  reports (four of them, counted in `test_probe_capture.py`, test d); removing
  them would break `caplog` in an adopter's tests.
- Never called, logging's own last resort applies: INFO is not written at
  all, and WARNING and above reach stderr as the bare message, not as JSON.
  Checked: unconfigured, `info` wrote nothing and `warning` wrote
  `warning-line` (`evidence/run_probes.sh`, case `unconfigured`). An adopter's test of
  its entry point catches a missing call, because the output it compares never
  arrives.

### A library, and an entry point

An entry point calls `configure`. A library, petstore's own modules among
them, never does: it takes `logging.getLogger(__name__)` and adds no handler,
not even a `NullHandler`, so that a program which forgets `configure` still
sees its warnings through the last resort. petstore's modules log nothing
today.

Every logger that propagates to the root reaches the streams, a dependency's
included. A dependency logging at INFO lands on stdout among the results; a
program quiets it by setting that logger's level. None of the interview
template's dependencies logs at INFO today: copier's tree logs through
plumbum at DEBUG only (`grep` for `logger.info` and `logger.warning` over
plumbum and copier in the template's environment found none).

## The filter

    python -m petstore.output [FILE...]

Reads a stream of entries from each file, or from stdin, and writes them as
text for a person: one block per entry, the level and logger, then the
message with its newlines as real line breaks, then the traceback when there
is one. Anything in the stream that does not parse as an object, such as a
child program's own output, is passed through unchanged, so a mixed stream is
still readable.

The filter's text is for reading. A program never reads it.

## With petstore.proc

`wait` and `become` flush stdout before the child starts. Entries are already
flushed when written, so the flush changes nothing for them; it stays for
anything else holding buffered output, and `proc` is unchanged.

A child started by `through`, `wait` or `become` writes its own output
straight to the descriptor, not as entries, so a stream carrying it is no
longer only objects. Whether that output is logged as entries or kept raw is
open, below.

## The ban, in an adopter

An adopter refuses the direct writes with ruff:

```toml
[tool.ruff.lint]
extend-select = ["T201", "TID251"]

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"sys.stdout".msg = "write output through logging; petstore.output configures it"
"sys.stderr".msg = "write output through logging; petstore.output configures it"
"sys.__stdout__".msg = "write output through logging; petstore.output configures it"
"sys.__stderr__".msg = "write output through logging; petstore.output configures it"
```

Checked over a sample of eleven direct writes
(`evidence/ban/`): it refuses `print`, `print(file=...)`,
`sys.stdout.write`, `writelines`, `.buffer.write`, `.flush`, `sys.__stdout__`,
and `from sys import stdout` at the import. It does not refuse
`os.write(1, ...)`; banning `os.write` would refuse every descriptor write, so
that one is left to review.

The ban refuses naming the streams at all, so `through(cmd, sys.stdout,
sys.stderr)` is refused too. A program that gives a child its own streams uses
`wait`.

petstore needs no exemption in an adopter: ruff lints the adopter's tree, and
petstore's code is in the installed package, not in it.

## Moving a caller over

The interview template's call sites become one logging call each:

    sys.stdout.writelines(f"{line}\n" for line in lines)   log.info("%s", line) per line
    sys.stderr.write(f"refused: {refusal}\n")              log.error("refused: %s", refusal)

Their output changes form: every reader of it, the interview root's
`just open` reading `new.py uri` and the template's tests comparing `drift`,
`list` and `exercise` output exactly, parses entries and compares `message`.
That is a rewrite of those readers, not a move.

## Left out, and why

- **A text mode.** No setting writes text instead of entries. A person reads
  through the filter; turning text back into entries is the direction that
  cannot be done reliably.
- **Indented entries behind an environment variable.** Considered and
  deferred. Readers parse objects, so it can be added without breaking one,
  but it does not make an embedded newline readable, which the filter does.
- **Extra members from `extra=`.** The entry has the members above and no
  others. Structured fields are a later change to this contract.
- **Child output, signals and threads.** SIGPIPE handling, output from other
  processes and ordering between threads are as logging and the operating
  system leave them.
- **Output written by other code.** argparse's usage and errors, an uncaught
  exception's traceback and a library's direct writes reach the streams as
  that code writes them.

## Open

- Whether a child's output started through `petstore.proc` is logged as
  entries or kept raw. Asked in the task that wrote this spec.
- Whether petstore bans the direct writes in its own tree. Doing so needs a
  `TID251` exemption for this module and `proc.py`, which is a suppression
  under the estate's rule 4 and is asked before it is written. Nothing in this spec
  depends on it.

## Requirements

`docs/REQUIREMENTS/output/` will hold this module's requirements, written
from this guide after its review.
