# Next steps

petstore is being made ready to publish. The work is tracked outside this
repository. What it waits on:

- A `proc` subprocess module lands before publishing. Its bandit findings are
  put to me before any suppression is written.
- `Stub` is trimmed to what reaches a failure, from a proposal I have not seen
  yet.

## Not kept: the oslo history

A second, unrelated history of this project (`a7149e4`, `10e1a910`) survives
only in a local snapshot. It is not kept. Compared with `diff -ru` over
`src`, `tests` and `docs`, the snapshot's working tree holds nothing this
tree lacks, and its one extra file, `tests/conftest.py`, is the `generate` that
`petstore.stubs` holds. The two commits were not compared individually.
