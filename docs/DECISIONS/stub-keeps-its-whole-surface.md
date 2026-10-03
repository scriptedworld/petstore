# Stub keeps its whole surface

Nothing is cut from `Stub` or `generate`. A test reaching a failure needs
construction, `returns`, `raises`, `times`, `always` and the call history;
`yields`, `yields_from`, `over` and a public `make_signature` stay beside them.

`generate` is the short form. It is the easiest way to stand in for a boundary
that does one thing on every call, and the tests that already use it stay
simple, while `Stub` carries everything beyond that.
`generate-is-built-on-stub.md` says how the two share one implementation.
