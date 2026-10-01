# generate is built on Stub

`petstore.generate` is the one-behavior short form of `petstore.Stub`: it builds
a stub whose script is a single `always()` link. There is one seam double, not
two, so it carries one call history, one typing and one set of requirements.

The alternative, a test fixture returning a plain function with attributes set
on it, cannot be installed by another project and duplicates what `Stub`
records. FR-4.13 requires the `Stub` return type, and FR-4.6, which required
the plain function, is retired.

The documentation and the IO seam pattern use `Stub`, and mention `generate`
where a seam does the same thing on every call.
