# petstore, the project

A small Python library of tools I reuse across projects, installed as a git
dependency rather than from an index:

    uv add git+https://github.com/scriptedworld/petstore

## What it is FOR

One home for the Python helpers more than one tool here needs, so each is
written, gated and tested once. The public surface is `petstore/__init__.py`:

    Validated, Rule, ValidationError     check a value when it is assigned
    validate                             the same rules over a plain value
    Stub, generate, CallEvent            a scripted callable passed through a seam
    locked, make_locked, Lock*Error      a cross-process lock named for a path
    zip_iter, ZipMode                    zip with four termination policies
    petstore.proc                        the one place to start another program
    petstore.metrics                     counters, measures and a recorder by name
    petstore.complexity                  tests holding code to a time or memory class

`petstore.proc`, `petstore.metrics` and `petstore.complexity` are imported as
modules rather than from `petstore`; metrics' `Counter` would otherwise shadow
`collections.Counter`.

petstore has no runtime dependencies.

`Stub` is the reason IO is testable here without a mock. Code that does IO takes
the IO as an argument, and a test passes a stub that reaches the failure it
exists for. `docs/architecture/function-boundaries.md` is the pattern.

## Layout

    src/petstore/          the library, one module per tool
    tests/                 one test module per library module
    docs/modules/          one guide per module
    docs/testing/          generate's guide
    docs/REQUIREMENTS/     one directory per module, one file per requirement
    docs/architecture/     the IO seam pattern
    docs/tooling-and-runbook.md   setup, the gate, the hooks, troubleshooting
    Justfile, just/        the recipes; just/project.just is petstore's own
    README.md              the front door, for somebody arriving cold

## Requirements

`docs/REQUIREMENTS/<module>/FR-x.y-<slug>.md`, checked by toolbox's
`test-traceability.py` against `# COVERS` comments on the tests. The major
number is the module; `docs/REQUIREMENTS/README.md` maps the `PS-` IDs the
requirements carried before.

## The gate

    just checks

toolbox's `python-std-quality` and `common-quality` jigs through bolt, the
second with toolbox's `requirements-directory` definitions. Each verdict is
`success` in the `result.yaml` whose path `just checks` prints. The thresholds
are the jigs', stated in toolbox's jig files; petstore sets none of its own.
bolt reads definitions only from the config directory, so an override petstore
needs has to ship in toolbox.

Run `just checks` and commit with the sandbox off: inside it ruff fails reading
the sandbox's device mounts, and git records the host identity as author.

## How it fits against its siblings

`just/base.just` and `bolt.secrets.yaml` are vendored from `toolbox` and
refreshed by `just vendor`. The gate runs toolbox's jigs and scripts from a
checkout beside this tree, and needs `bolt` on `PATH`. No other project
installs petstore yet.

## What is decided, and what is open

`docs/DECISIONS/` holds one file per decision. `NEXT_STEPS.md` holds what is
open.
