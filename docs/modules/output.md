# Program output

Module: `petstore.output`

Public API: `configure`, `flush`, and the filter run as
`python -m petstore.output`.

This guide is the module's spec. The module is not built yet; the
requirements, tests and code are derived from this file. A line saying
*Checked* cites a probe under `evidence/` in one of the tasks of clank's
`petstore/output` group named `spec-the-output-module`,
`amend-the-spec-to-the-review` or
`amend-the-spec-to-the-answers-and-the-re-read`, or the one named
`amend-the-spec-to-the-re-read-of-the-second-amendment`. The probes
regenerate what they state when run from this tree's `.ephemera/`.

A clank task is cited here by its name and its group, never by its number or
state, because both change as the group moves: the directory is the one under
`tasks/petstore/output/` whose name, less the leading number and the trailing
state, is that name. An answered question is cited by its file's name, which
stays, and is found with `find` over clank's `tasks/petstore/` for
`<name>.question.answered`.

## Purpose

A Python program writes its log entries through `logging`, never `print` and
never a direct write to `sys.stdout` or `sys.stderr`, and petstore carries the
module that sets it up, so every project takes the same handlers and the same
form from one release. That is the ruling in silo
`docs/DECISIONS/program-output-goes-through-logging.md`, whose opening silo
`6012b71` narrowed from "output" to "log entries".

A result is not a log entry. The same file's section "Results and log entries
go to different places" (silo `8f2a4b8`) sends logging to stderr, and a
program's result to stdout or to a chosen output file. This module carries log
entries and nothing else: it never writes a result. The standard states the
split as SR-OUT.1 (log entries go through logging), SR-OUT.2 (the result on
stdout or in the chosen file, every log entry on stderr, filterable by level),
SR-OUT.8 (each log entry is one JSON object) and SR-OUT.9 (library code never
prints), in silo `docs/PATTERNS/code/REQUIREMENTS.md`.

What the module writes is for a machine first. Each entry is one JSON object,
so whatever reads a program's log can always parse it, and a person reads it
through the filter below. Those rulings are the same file's section "Every
entry is one JSON object", silo `4b60289`.

This module writes the log entries, and it flushes the streams for `proc`
before a child starts (see "With petstore.proc"). It is the only place that
writes a log entry, and `petstore.proc` is the only place that starts another
program. Whether it is the only place in petstore that names a standard stream
depends on where petstore's result writer sits, which is open (see "Open"):
the writer names stdout or the chosen file, so if it sits in another module
that module names a stream too. In either case `proc` names none.

A result is written by a petstore result writer, not by this module. Silo's
section "One writer writes the result" (silo `cae172f`) says
it writes wrench's result envelope (`schemas/envelope.schema.json`, one JSON
object carrying `success`) to stdout, or to the chosen output file, and that
the writer is a task of its own. Its form is that file's; this guide adds
nothing to it. That section was settled by alberta from guidance and is open to
overruling.

## Usage

```python
import logging

from petstore import output

log = logging.getLogger(__name__)


def main() -> int:
    output.configure()
    log.info("fetching %s", name)  # a log entry: one object on stderr
    log.error("refused: %s", why)  # a log entry: one object on stderr
    return 0
```

    python -m template.new list projects 2>&1 | python -m petstore.output

The program's result is not logged. In the line above, the result on stdout
reaches the filter beside the entries on stderr and passes through it
unchanged; the entries are shown as text.

## The entry

Each entry is one JSON object with these members:

    level     the record's level name, such as "INFO"
    logger    the logger's name, such as "template.new"
    time      when the record was made, in UTC, such as
              "2026-11-02T01:02:03.123456+00:00"
    message   the message, with its arguments applied
    exception the formatted traceback, present only when the record has one

`time` is ISO 8601 with a date, a time, six digits of fraction always, and the
offset written `+00:00`, never `Z`. `level`, `logger`, `time` and `message` are
strings and always present.

`message` holds the message exactly as the program made it. A message logged as
`log.info("%s", text)` is recovered by parsing the object and taking `message`,
character for character, newlines and all. Nothing is appended to it and
nothing is stripped.

An entry is written as compact JSON with every non-ASCII character escaped,
so what reaches the stream is ASCII. A message no encoding could carry, such as
a path holding an undecodable byte, still writes, and parses back to the same
string. Checked: `json.dumps` with `ensure_ascii` writes `"caf\u00e9 \udcff"`
for the message `café` followed by a space and the lone surrogate `\udcff`, and
`json.loads` returns the original unchanged (`evidence/probe_json.py`).

### Reading a stream

An entry is a JSON object that has the members `level`, `logger`, `time` and
`message`. Everything else in a stream is raw text: text that does not parse as
an object, and an object lacking any of those four members, such as a child's
own JSON or a result.

A reader finds entries by trying to parse an object at each `{`, not by
splitting on newlines, and the module promises nothing about where newlines
fall between or inside entries. Today each entry is followed by one newline;
that is a convenience to a person looking at raw output, not part of the
contract. The rule is:

- At a `{` that begins an object with the four members, the object is an
  entry and the reader continues after it.
- At a `{` that begins an object lacking one, the whole object is raw text and
  the reader continues after it. An object nested inside it is not read as an
  entry.
- At a `{` that does not begin an object that parses, that one character is raw
  text and the reader continues at the next.

An entry is therefore found even when raw text before it ends without a
newline, and raw text holding a `{` splits into pieces that the filter writes
back in order. Raw text that itself contains an object with all four members is
read as an entry; nothing in the stream tells the two apart, and the module
cannot prevent a child from printing one.

Raw text reaches a stream in these places, and no others the module controls:

- The output of a child started by `petstore.proc.wait`, and of a program that
  replaced this one through `become`, which are handed the real descriptors
  (see "With petstore.proc").
- The bare warnings of a program that never called `configure` (see
  "configure").
- Output written by other code: argparse's usage and errors, an uncaught
  exception's traceback and a library's direct writes (see "Left out").
- The program's result, on stdout, which is not an entry.

A reader of a program's log reads stderr. A reader of its result reads stdout,
where raw text can still be a child's, or the chosen output file, in which case
stdout carries no result (SR-OUT.2).

## Which stream

Every entry goes to stderr, at every level that is enabled. There is one
handler. The level is a member of the entry, and a reader filters by it; the
stream does not carry it.

The stream is looked up when each entry is written, not when `configure` is
called, so pytest's `capsys`, `contextlib.redirect_stderr` and anything else
that replaces `sys.stderr` sees the entry. Checked under pytest with stdout: a
handler holding the stream it was built with lost a later test's line and wrote
`--- Logging error ---` instead, while one that looks the stream up wrote it
(`evidence/test_probe_capture.py`, tests b and d). Checked for stderr without
pytest: a handler built holding `sys.stderr` wrote to the old stream after it
was replaced, and one that looks it up wrote to the replacement
(`evidence/probe_stderr_lookup.py` in the task `amend-the-spec-to-the-review`).

Each entry is flushed when it is written, so it reaches stderr before anything
a child started afterwards writes.

## When a write fails

A failed write raises from the logging call, as `print` does: a closed pipe
raises `BrokenPipeError` at `log.info`. logging's default is to print
`--- Logging error ---` with a traceback to stderr and carry on, which loses
the line and does not stop the program. Checked, with the entries on stdout
as the probe had them: 200000 records into `head -1` wrote about 3.2 million
lines of those reports (3199971 and 3199987 in two runs) to stderr, where
`print` raised on the first failed write (`evidence/run_probes.sh`). The
handler is the same for stderr, but the reports are not: they go to stderr,
which is the closed stream, so there is no flood to see. A handler whose
`handleError` raises propagates the error out of the logging call
(`evidence/test_probe_capture.py`, test e).

The program's exit status after a lost line is not the logging call's to set.
In the shape the re-read tried, a reader that closed after one line and a
writer of 20000 records, the default handler completed every call and the
process exited 120, the interpreter failing to flush at shutdown; a program
with nothing buffered at exit may differ.

## configure

`configure()` takes no arguments and is called by an entry point, once, before
it logs.

- It puts one handler on the root logger, writing to stderr as above, and sets
  the root level to INFO.
- A program that wants DEBUG sets the root logger's level after `configure()`.
  Calling `configure()` again resets that level to INFO.
- Called again, it replaces the handler it put there before. One record is
  never written twice, however many times it is called.
- It leaves every other handler alone, on the root logger and elsewhere.
  pytest keeps its own handlers on the root logger for `caplog` and its
  reports (four of them, counted in `test_probe_capture.py`, test d); removing
  them would break `caplog` in an adopter's tests.
- Never called, logging's own last resort applies: INFO is not written at
  all, and WARNING and above reach stderr as the bare message, not as JSON.
  Checked: unconfigured, `info` wrote nothing and `warning` wrote
  `warning-line` (`evidence/run_probes.sh`, case `unconfigured`). An adopter's
  test of its entry point catches a missing call, because the output it
  compares never arrives.

`configure` takes no stream, against petstore's
`docs/DECISIONS/io-defaults-go-on-the-argument.md`, which puts an IO default on
an argument so a test can replace it. Here the stream is `sys.stderr`, which a
test already replaces through `capsys`, and the handler looks it up at each
write, so an argument would add a seam for something that has one. That is the
precedent of `docs/modules/proc.md`, "Testing code that uses it": test against
the real thing when it is cheap.

### A library, and an entry point

An entry point calls `configure`. A library, petstore's own modules among
them, never does: it takes `logging.getLogger(__name__)` and adds no handler,
not even a `NullHandler`, so that a program which forgets `configure` still
sees its warnings through the last resort. Of petstore's modules only
`proc.logged` logs, under the logger name `petstore.proc`.

Every logger that propagates to the root reaches stderr, a dependency's
included; a program quiets one by setting that logger's level. None of the
interview template's dependencies logs at INFO today: a `grep` for
`logger.info` and `logger.warning` over plumbum and copier in the template's
environment found none. plumbum does log at ERROR, in `machines/session.py`,
on a connect timeout, and that reaches stderr as an entry.

## The filter

    python -m petstore.output [FILE...]

Reads a stream from each file, or from stdin, and writes it as text for a
person. Each entry is one block: the level and logger, then the message with its
newlines as real line breaks, then the traceback when there is one. Everything
the reader rule above calls raw text is passed through unchanged and in order,
so a mixed stream is still readable. That includes a program's result, so the
filter does not format a result, as silo's section "One writer writes the
result" has it: results stay machine-readable.

The filter never fails on what it is handed. A message holding a lone
surrogate, and any raw byte that is not valid text, is written with the
character's escape, such as `\udcff`, in place of the character: a UTF-8 stdout
cannot carry the surrogate, and writing it raised `UnicodeEncodeError` in the
probe run for the review. This is the one way raw text is not passed through
unchanged.

The filter's text is for reading. A program never reads it.

## With petstore.proc

What happens to a child's output depends on the kind of child. Capturing
output and logging it are separate things, so `proc` has a call for each. It
has a call for a child whose output is dropped, and two for children that need
the terminal:

    capture   a batch child; its output is returned and written nowhere
    logged    a batch child; its output is logged as entries
    quietly   a child whose output is dropped; nothing is read from it
    wait      an interactive child; it uses this process's own streams, raw
    become    this process is replaced by the child; its output is raw

`capture` and `become` are as `docs/modules/proc.md` describes them today.
`logged` and `quietly` are new and take the place of `through`, which is
removed. `wait` is as described there with one addition:

    wait(cmd, *, stdin=None, timeout=None) -> int

`timeout` is as `capture`'s: on expiry the child is killed and `TimeoutExpired`
is raised. It lets dotfiles' `run_command` keep its one-hour bound when it
moves to `wait` (below). `wait` starts its child through the call `proc`
already makes for every start, so the timeout adds no second call site and no
suppression. If the implementation finds it needs either, that comes back to J
under rule 4 before it is written. The answer is clank's
`wait-timeout-for-update.question.answered`, in the task
`amend-the-spec-to-the-answers-and-the-re-read`, option 1: settled by alberta on J's standing guidance, not an answer given by J.

### Choices made here

The answer to the child-output question (clank's
`child-output.question.answered`, in the task `spec-the-output-module`)
chose the option "Split by kind of child" and added that capturing and logging
are two separate things, so `proc` gives a log method and a capture method. The
option's text kept the name: `through` becomes the batch call. Two things here
depart from that. Both are flagged for whoever ruled, and neither reverses the
answer:

- **`through` is removed and `logged` added**, in place of keeping the name.
  A kept name with its `stdout` and `stderr` parameters gone would change under
  every caller without failing, and a caller passing `os.devnull` would start
  logging what it meant to drop. A removed name fails at the call. If the name
  is kept, `logged` below is `through` with those two parameters dropped and
  nothing else in this guide changes.
- **`quietly` is a third call**, beyond the log method and the capture method
  the answer names. The review in the task `review-the-output-spec` found that the alberta launches cannot move
  to `capture` and that nothing else drops output without a pipe (below).

### logged

    logged(cmd, *, timeout=None) -> int

Runs `cmd` to completion and returns its exit status. Its standard input is
this process's, as `through`'s was. It runs the child through the call `proc`
already makes for every start (`capture` uses it), with one change to the
runner that wraps that call, `_run` in `proc.py`: today it runs the child in
text mode unless `stdin` is bytes, and bytes `stdin` gives the child an empty,
closed stdin. `logged` needs the child's output as bytes and the child's stdin
left alone, which `_run` cannot give, so it takes a parameter that asks for
bytes output without touching stdin. Checked: through `_run` as it is, a child
writing `x\xffy` raised `UnicodeDecodeError` from `capture`, and
`capture(..., stdin=b"")`, the only route to bytes, left the child reading
`b''`. Text mode would not serve with an error handler either: with
`errors="surrogateescape"` text mode translated a child's `a\rb\r\n` to
`a\nb\n`, and the rules below keep a lone `\r` and remove a `\r\n` whole
(`evidence/probe_run.py` in the task
`amend-the-spec-to-the-re-read-of-the-second-amendment`). The parameter is on the same call,
with the same two pragma lines, so it is inside the answer below: no second
call site and no new suppression. If the implementation finds it needs either,
that comes back to J under rule 4 before it is written. `logged` reads both of the
child's pipes to the end and logs the child's lines after the child exits, not
as it produces them. A long-running child shows nothing until it ends, and its
output is held in memory until then, as `capture`'s is. Each line is logged as
one entry on the logger `petstore.proc`:

    the child's stdout   INFO
    the child's stderr   WARNING

This is the answer to the question of a second subprocess call site (clank's
`popen-call-site-for-logged.question.answered`, in the task
`split-the-stages-to-a-release`, option 2): no second call site and no new
suppression. No silo decision file
records it. It withdraws this guide's earlier promise that entries arrive while
the child runs; a child that must be seen as it works is an interactive child
and uses `wait`.

Both reach stderr like every entry. The level keeps the child's two streams
apart for a reader filtering by level. It says which stream the line came from,
not that the child failed: `git fetch` writes its ref update to stderr when
piped (measured by the review), and that line is logged at WARNING all the
same. A child whose stdout is the data a caller wants uses `capture`.

- The message is the line without its terminating newline. A terminating
  `\r\n` is removed whole. A last line with no newline is logged too. A `\r`
  anywhere else in a line stays in the message.
- Bytes are decoded so that none is lost: an undecodable byte becomes the lone
  surrogate `surrogateescape` gives it, which the entry carries and parses back
  to the same string (the case `evidence/probe_json.py` checks).
- The lines of the child's stdout are logged first, in the order the child
  wrote them, then the lines of its stderr in theirs. How the two interleaved
  in time is not kept; the level says which stream a line came from.
- On `timeout` the child is killed and `TimeoutExpired` is raised, as `capture`
  does, after the lines the child had written are logged. Checked: with both
  pipes captured, the exception carried `first` from stdout and `err` from
  stderr for a child that wrote both and then slept past the timeout
  (`evidence/probe_timeout.py` in the task
  `amend-the-spec-to-the-answers-and-the-re-read`). The exception's partial
  output is bytes whether the run was in text mode or not (`probe_run.py`,
  cases Q4 and Q5), so `logged` decodes those bytes and splits them into
  lines by the same rules as above before it logs them.
- A write failure while the lines are logged is raised from `logged`, as "When
  a write fails" says for any logging call. The child has already exited, so
  nothing is left running. The lines not yet logged are lost and the exit
  status is not returned.
- It takes `timeout` and nothing else, as `through` did. `capture` takes `cwd`,
  `env` and `stdin` as well; no caller of `through` needs them, and adding them
  later does not break a caller.
- It needs `configure` to have been called. Without it the child's stdout is
  not written at all and its stderr reaches stderr as bare text, per
  "configure".
- The child's streams are pipes, not a terminal. A child that buffers when
  piped, or changes its output when it is not a terminal, does so here; a child
  that prompts or paints a screen is an interactive child and uses `wait`. A
  prompt a child writes without a newline is logged with the rest, after the
  child exits, so a prompt is never seen while it can be answered.

### quietly

    quietly(cmd, *, timeout=None) -> int

Runs `cmd` to completion with its stdout and stderr sent to the null device,
and returns its exit status. Its standard input is this process's, as
`through`'s was. On `timeout` it raises `TimeoutExpired`, as `capture` does.
Nothing is read from the child, so a program that detaches and outlives the
call does not hold the call open. Checked: `setsid -f sleep 2` returned in
0.00s with its output on the null device and in 2.00s on a pipe
(`evidence/probe_quietly.py` in the task `amend-the-spec-to-the-review`; the review measured 0.00s and 4.00s
with a 4-second child). It starts the program through the runner that
`capture` uses, so it needs no new suppression.

### What changes for a caller of `through`

`through(cmd, stdout, stderr)` handed the child the streams it was given, or
captured and wrote to them when they had no descriptor. Its callers, by `grep`
for `through(` across the estate's repositories, are these:

- dotfiles' `run_command` (`update.py:53`) passes its own `stdout` and `stderr`
  (`update.py:179` hands it `sys.stdout` and `sys.stderr`) and wants a person to
  see the output as it comes. It moves to `wait`, not `logged`. It runs `apt`
  under `sudo` with no `-y`, and `update.py:105` and `:175` say `sudo` asks for
  the password on the terminal and apt asks there: an interactive child, by the
  rule above, and `logged` would show its prompt only after the child exits. Its
  streams, and the fallback it carries for a stream with no descriptor, go. The
  output stays raw, on this process's own streams. Its test,
  `tests/test_update.py:215-218`, passes real files and is rewritten with the
  move, and so is the wording of the requirement it covers there (FR-3.8 in
  dotfiles). `run_command` passes `UPDATE_TIMEOUT`, one hour, to `wait`'s new
  `timeout` and keeps its bound.
- alberta's four launches (`desk.py:227`, `face.py:767`, `music.py:250`, and
  `tests/display/test_face_window.py:518`) pass an open `os.devnull` for both
  streams and want no output. Each runs its program under `setsid -f`. They move
  to `quietly`, not `capture`: handed a pipe, the detached program holds it open
  and `capture` waits for it, which is the 2.00s above. `music.py:250` reads the
  status and does not ignore it; `quietly` returns it. The comment at
  `test_face_window.py:516`, that kitty would hold a captured pipe open, says the
  same.
- petstore's own `tests/test_proc.py:52-60` passes real files, and is the test
  of `FR-6.3` that moves with the row (below). Its second test, `:68`, passes
  `StringIO` for the fallback branch and moves with the row too.

After these moves no production code hands a child a stream of its choosing. The
first branch of `through`, the child writing straight into a given descriptor,
is taken for any pair of streams that both have a descriptor (`proc.py:144`).
It had four production callers: alberta's three launches (`desk.py:227`,
`face.py:767`, `music.py:250`), each handing it an open `os.devnull`, and
dotfiles' `run_command`, when `update` is given real streams, as `main` gives
it `sys.stdout` and `sys.stderr`. The fifth caller, alberta's
`test_face_window.py:518`, is a test. A `grep` for
`proc.through` over alberta, dotfiles, petstore, `~/interview` and `~/.hobby`
finds these four in production and no other (`.ephemera/hazel-output-70/refs.sh`
is the shape). The three launches move to `quietly` and `run_command` to
`wait`, which replaces it for a process's own streams. For a batch child there is no replacement: output that bypasses
logging is what the ruling removes. A caller that wants a child's output in a
file uses `capture` and writes the file, which holds the output in memory first.

Removing a name breaks its callers, so the release that carries it carries
their move.

### proc.md and the rows

`docs/modules/proc.md` describes code that exists, so it changes when the code
does and not before. As of `186f12e` the files that name `through` and change
then are:

- `docs/modules/proc.md`: the Public API line (`:5`), the `import sys` that
  only the `through` example uses (`:22`), the import line (`:24`), the
  example (`:33`) and the paragraph on `through` (`:49-51`), the last replaced
  by paragraphs on `logged` and `quietly`; `wait`'s new `timeout`; and a
  sentence that `wait` and `become` leave the child's output raw.
- `src/petstore/proc.py`: the runner `_run` takes the parameter `logged` needs
  (see "logged"), and the docstring that says bytes `stdin` is the only route
  to bytes output changes with it. The parameter adds no pragma line, and
  `SUPPRESSIONS/starting-another-program.md` lists its five pragma lines by
  file and rule id, with no line numbers, so the register's entries do not
  change for it.
- `README.md:204`, the sentence describing `through`, `wait` and `become`.
- `SUPPRESSIONS/starting-another-program.md:9`, which lists the calls that go
  through the private runner. It loses `through` and gains `logged` and
  `quietly`, both of which start their child through that runner. No new line
  is added to that file.

`FR-6.3`, the row for `through`, is superseded by rows for `logged` and
`quietly`, and its two `COVERS` marks in `tests/test_proc.py` (lines 51 and 63)
move with them. `FR-6.1`, `FR-6.4` and `FR-6.5` are unchanged. The supersession
is done in the task `split-the-stages-to-a-release`, with the rows for this module.

### flush

    flush() -> None

Flushes `sys.stdout` and `sys.stderr`, writes nothing, and needs no `configure`.
`wait` and `become` call it before the child starts, where `proc.py` flushed
stdout itself (`proc.py:160`, `:166`). It exists so that `proc.py` names no
stream: `proc.py` is not exempt from the ban in petstore's own tree (see "In
petstore's own tree"), and this module is. `proc` imports `petstore.output` for it;
this module imports nothing from `proc`. `proc.py`'s `import sys` goes with the
two lines.

The flush stays for the reason it had: `print()` is block-buffered when piped,
while the child writes straight to the descriptor, so without it the child's
output arrives before text that came earlier. Entries are already flushed when
written, so it changes nothing for them; it is for a result, or anything else
holding buffered output. `logged` and `quietly` need none: a child's output
reaches a stream only as entries, written after the entries before it, or not
at all. Flushing stderr as well as stdout is new and changes nothing a caller
can see, since entries are flushed when written.

## The ban, in an adopter, and in petstore

An adopter refuses the direct writes with ruff:

```toml
[tool.ruff.lint]
extend-select = ["T201", "TID251"]

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"sys.stdout".msg = "write log entries through logging; petstore.output configures it"
"sys.stderr".msg = "write log entries through logging; petstore.output configures it"
"sys.__stdout__".msg = "write log entries through logging; petstore.output configures it"
"sys.__stderr__".msg = "write log entries through logging; petstore.output configures it"
```

Checked over a sample of eleven direct writes
(`evidence/ban/`): it refuses `print`, `print(file=...)`,
`sys.stdout.write`, `writelines`, `.buffer.write`, `.flush`, `sys.__stdout__`,
and `from sys import stdout` at the import. It does not refuse
`os.write(1, ...)`; banning `os.write` would refuse every descriptor write, so
that one is left to review.

The ban refuses naming the streams at all, so handing a child `sys.stdout` is
refused wherever it is tried. A program that gives a child its own streams uses
`wait`, which names none.

The same ban refuses a program writing its result to stdout, which the standard
requires (SR-OUT.2) and the decision does not call a log entry. The path the
ban admits for it is petstore's result writer, which does not exist yet (see
"Writing a result" under "Left out"). This guide adds no exemption for it.

petstore needs no exemption in an adopter: ruff lints the adopter's tree, and
petstore's code is in the installed package, not in it.

### In petstore's own tree

petstore bans the same names in its own source. The `TID251` exemption covers
petstore's files for the logging and output code: this module, and the result
writer's lines if they sit in or are called through it, which is open (see
"Open"). It covers no other file. `proc.py` is not exempt: its two flushes move
into this module (`flush`, above). The answers are clank's
`tid251-exemption-in-petstore.question.answered` and
`which-files-the-tid251-exemption-covers.question.answered`, both in the task
`split-the-stages-to-a-release`; silo's section
"One writer writes the result" records the same ruling. The exemption is a
suppression and is registered in `SUPPRESSIONS/` with those answers when the
module's lines exist.

The result writer's exemption is not approved here. Silo's section leaves it to
be asked once the writer's lines exist. Where the writer sits is that task's to
say; that it sits inside this module or is called through it is alberta's
reading of the answer, not the answer's. The direct writes in `tests/test_proc.py`
and `proc.py` that clank's inbox entry `python-output-bypasses-logging` names are
for the task that folds that entry in.

## Moving a caller over

The interview template's call sites, read from its code, are of two kinds:

    new.py:297, exercise.py:82   sys.stderr.write(f"refused: {refusal}\n")
                                 -> log.error("refused: %s", refusal)

These are log entries, and move to one logging call each. Their readers are
whoever reads the refusal on stderr, who now reads an entry.

    new.py:299       the paths or the URI a command prints
    exercise.py:84   the paths written
    silo.py:168      the refresh report
    new.py:230       doctor's report, before the refusal

These write the command's product to stdout, so they are results: the
interview root's `just open` reads `new.py uri` from this stream and the
template's tests compare `drift`, `list` and `exercise` output exactly. They do
not move to logging. They stay as they are until petstore's result writer
lands, because the ban above refuses them and nothing yet admits a result; they
then move to it. Whether `doctor`'s table is a result or a report for a person is
for the template's owner to confirm when it moves. `bin/measure_memory.py` in
`rate-limiter` was not opened.

## Left out, and why

- **A text mode.** No setting writes text instead of entries. A person reads
  through the filter; turning text back into entries is the direction that
  cannot be done reliably.
- **Indented entries behind an environment variable.** Considered and
  deferred. Readers parse objects, so it can be added without breaking one,
  but it does not make an embedded newline readable, which the filter does.
- **Extra members from `extra=`.** The entry has the members above and no
  others. Structured fields are a later change to this contract.
- **Signals and threads.** SIGPIPE handling and ordering between threads are
  as logging and the operating system leave them.
- **Logging a child that needs the terminal.** `wait` and `become` stay raw: a
  child cannot be given a terminal and have its output logged, and `become`
  has no process left to log it.
- **Output written by other code.** argparse's usage and errors, an uncaught
  exception's traceback and a library's direct writes reach the streams as
  that code writes them.
- **Writing a result.** No function here writes a result. Silo's section "One
  writer writes the result" (`cae172f`) puts that in petstore's result writer,
  a task of its own that petstore's release does not wait on, and the log
  filter leaves results alone.

## Open

- Where petstore's result writer sits, and the exemption for its lines. Both
  are that task's: the writer exists after this module, the exemption is a
  suppression asked once its lines exist, and silo's section "One writer writes
  the result" is silent on which module exposes it. The two places in this guide
  that turn on the answer, who names a standard stream ("Purpose") and which
  files the `TID251` exemption covers ("In petstore's own tree"), say what
  holds either way.

## Requirements

`docs/REQUIREMENTS/output/` will hold this module's requirements, written
from this guide after its review.
