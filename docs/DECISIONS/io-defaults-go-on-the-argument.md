# IO defaults go on the argument

Decided 2026-09-28.

A function that does IO takes the IO as an argument whose default is the real
boundary:

    def read_config(path: Path, *, reader: Reader = _read_text) -> Config:

A test passes its own reader, and production callers pass nothing. This is the
form the documentation leads with, because it is the smallest change that makes
a function testable and the easiest to adopt in existing code.

A composition factory, where the implementation takes its strategies with no
defaults and a factory binds the production ones, is the form for a function
with several seams that vary together. The documentation shows it second, as
that case, not as the default.

`docs/architecture/function-boundaries.md` and the runbook's "Exception and I/O
seams" section described the factory as the only form, with production defaults
banned from the implementation. They follow this decision.
