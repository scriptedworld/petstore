# Shared tool configuration is vendored

Decided 2026-09-28.

`just/base.just` and `bolt.secrets.yaml` come from a private repository of
shared tooling. They are committed here as real files, not symlinks into it, so
a clone of petstore runs every recipe without that repository beside it.

The cost is drift: an improvement upstream does not arrive here until the files
are copied again. That is accepted, because a public tree whose `Justfile`
fails on its first import cannot run its own gate at all.
