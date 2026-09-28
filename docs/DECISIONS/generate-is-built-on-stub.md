# generate is built on Stub

Decided 2026-09-28.

`petstore.generate` is the one-behavior short form of `petstore.Stub`: it builds
a stub whose script is a single `always()` link. There is one seam double, not
two, so it carries one call history, one typing and one set of requirements.

It replaced a `generate` in `tests/conftest.py` that returned a plain function
with attributes set on it. That one could not be installed by another project,
and it duplicated what `Stub` already recorded. PS-TEST-006 was retired for
PS-TEST-013 when the return type became `Stub`.

The documentation and the IO seam pattern use `Stub`, and mention `generate`
where a seam does the same thing on every call.
