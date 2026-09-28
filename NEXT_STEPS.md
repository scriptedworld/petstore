# Next steps

petstore is being made ready to publish. The work is tracked outside this
repository. What it waits on:

- A `proc` subprocess module lands before publishing. Its bandit findings are
  put to me before any suppression is written.
- Requirements move from the per-module YAML registries to
  `docs/REQUIREMENTS/<category>/<requirement>.md`, checked by toolbox's
  `common-quality` jig. `petstore.traceability`, `petstore.tool_output` and
  `petstore-requirements` retire with them, since toolbox checks traceability
  and wrench owns the result envelope.
- Then `just checks` runs only bolt jigs (`python-std-quality` and
  `common-quality`) from a toolbox checkout, so every step reports a wrench
  envelope. The jigs' thresholds replace petstore's stricter ones.
- `Stub` is trimmed to what reaches a failure, from a proposal I have not seen
  yet.

## Not kept: the oslo history

A second, unrelated history of this project (`a7149e4`, `10e1a910`) survives
only in a local snapshot. It is not kept. Checked 2026-09-28 with `diff -ru`
over `src`, `tests` and `docs`: the snapshot's working tree holds nothing this
tree lacks, and its one extra file, `tests/conftest.py`, is the `generate` that
`40b3cf1` replaced. The two commits were not compared individually.

## Working here under the sandbox

- Commit with the sandbox off. Inside it git cannot read the global config and
  records the host identity as author, which would go public. Check with
  `git log -1 --format=%ae`.
- Run `just checks` with the sandbox off. The sandbox mounts character devices
  over protected paths such as `.claude/loop.md`, and `ruff format --check`
  fails reading them with `Permission denied`.
