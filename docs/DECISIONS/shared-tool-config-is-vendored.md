# Shared tool configuration is vendored

`just/base.just` and `bolt.secrets.yaml` belong to
[toolbox](https://github.com/scriptedworld/toolbox). They are committed here
as real files, not symlinks into a checkout beside this one, so a clone of
petstore loads its Justfile without that checkout. `checks`, which runs
toolbox's jigs, still needs it.

`just vendor` replaces both with toolbox's `main` on GitHub, and `git diff`
shows what changed upstream. That keeps refreshing to one command, with no
checkout of toolbox and no linking step.

The cost is drift between refreshes, which is accepted: a tree whose
`Justfile` fails on its first import cannot run its own gate at all.
