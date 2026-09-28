# Next steps

petstore has no `docs/PROJECT.md` and no task tree in clank, so it has not been
commissioned. `/commission` is owed.

## Publishing

`the task tracker` asks for petstore to be made clean
enough to go public, and names six criteria. The coordinator makes the
visibility switch after one line to silo: clean or not, and where the report
is. The entry stays in the inbox until it is finished.

Where each criterion stands, measured 2026-09-28:

1. Gate: `just checks` passes at `40b3cf1`. 113 tests, 100% line and branch
   coverage, 53 of 53 active requirements with test evidence, and the bolt
   secrets result reads `success: true`.
2. Cold-read review: not run.
3. Secrets in history: gitleaks runs `detect` over the full history inside the
   gate and passed. The oslo history is not in this repository.
4. README: names Validated. Has no install-as-a-dependency instruction
   (`uv add git+https://github.com/scriptedworld/petstore`).
5. Inbox: `a-subprocess-utility-every-tool-can-use`,
   `the-oslo-unrelated-root-has-one-copy-left`, `voice-review` and
   `wording-check-findings` are unresolved.
6. Push: `main` is 3 commits ahead of `origin/main`.

A blocker the entry does not name: `just/base.just` and `bolt.secrets.yaml`
are tracked symlinks into `../toolbox`. In a public clone they dangle, and the
Justfile imports `base.just` without `?`, so every recipe fails. Installing
the package does not need `just` and is unaffected.

The brief's second part, the stub at IO boundaries:

- Done at `40b3cf1`: `docs/architecture/function-boundaries.md` uses
  `petstore.Stub` throughout and has a worked example provoking a full disk
  (`OSError(errno.ENOSPC)`) through a writer seam. The example was run and
  type-checked under `mypy --strict`.
- Not done: the README does not show the seam, and the estate pattern draft
  for `the task tracker` is not
  written. The brief says what it must contain, including why a stub passed
  through a declared seam is not a patch under global hard rule 4.

## Open questions

Put to the person on 2026-09-28, unanswered:

1. Scope: is the whole publish brief the next piece of work here (symlinks, README
   install section, seam docs, silo pattern draft, voice and wording fixes,
   cold-read review, push)?
2. Symlinks: vendor copies of `base.just` and `bolt.secrets.yaml` into the
   repository, or make both imports optional and document that `just` needs
   toolbox checked out beside it?
3. Subprocess utility: build the `proc` module the inbox entry proposes before
   publishing, or leave it with the reason recorded?
4. Oslo record: push the two commits the inbox entry names, whose only copy
   is `a local snapshot`, to a branch here, or drop
   them and have dotfiles correct its section 6a? The SHAs are the entry's
   and have not been resolved here.
5. Commission first, or go straight to the publish work?
6. Where the default reader goes: on the reading function's own argument, as
   the brief puts it, or bound by a composition factory, as
   `function-boundaries.md` does now?

Settled 2026-09-28: the docs and the pattern use `petstore.Stub`, and
`generate` is its one-behavior short form, built on it.

## Working here under the sandbox

- Commit with the sandbox off. Inside it git cannot read the global config and
  records `the machine's local address` as author, which would go public.
  Check with `git log -1 --format=%ae`.
- Run `just checks` with the sandbox off. The sandbox mounts character devices
  over protected paths such as `.claude/loop.md`, and `ruff format --check`
  fails reading them with `Permission denied`.
