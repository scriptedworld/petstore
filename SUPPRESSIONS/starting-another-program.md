# Starting another program: `nosec B404, B603, B606`, `noqa S603, S606`

Bandit's B404 is *consider the security implications of importing
subprocess*, B603 *subprocess call, check for execution of untrusted input*,
and B606 *starting a process without a shell*. Ruff's S603 and S606 are the
same two calls checked again.

`petstore.proc` exists so that tools starting a program do it in one place:
`capture`, `through` and `wait` run one through a single private `_run`, and
`become` replaces this process with it. Running a named program is what those
tools are for, and bandit cannot tell that from injection. Collected here, it
is one judgement made once, and every adopter carries no pragma of its own,
test suites included, since they start programs through `capture` too.

## The question, and the answer

Asked whether to approve three pragma lines for five rule ids in
`src/petstore/proc.py`, and register them here, the answer was:

> I am fine with those being added to SUPPRESSIONS.

Approved by J W, 2026-10-03.

## What makes it safe

Nothing in petstore takes a command from input; a caller passes commands built
from literals and paths it owns. A list is passed, never a string, and no
shell is involved, so a value carrying a space or a semicolon is one argument
rather than two commands. That is what B603 and B606 ask about, and the list
form answers them.

## Expiry and removal

No expiry: the module is the place these belong for as long as it exists.
Removed with the module, or when bandit and ruff can be told a whole module
starts programs by design.

## Scope

Three lines, each naming its ids and nothing else. Every other rule stays in
force on the file.

    src/petstore/proc.py   #nosec B404
    src/petstore/proc.py   #nosec B603
    src/petstore/proc.py   #nosec B606
    src/petstore/proc.py   # noqa: S603
    src/petstore/proc.py   # noqa: S606
