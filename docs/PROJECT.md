# petstore, the project

A small Python library of tools I reuse across projects, installed as a git
dependency rather than from an index:

    uv add git+https://github.com/scriptedworld/petstore

## What it is FOR

One home for the Python helpers more than one tool here needs, so each is
written, gated and tested once. The public surface is `petstore/__init__.py`:

    Validated, Rule, ValidationError     check a value when it is assigned
    Stub, generate, CallEvent            a scripted callable passed through a seam
    locked, make_locked, Lock*Error      a cross-process lock named for a path
    zip_iter, ZipMode                    zip with four termination policies

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

Ruff format and lint, mypy strict, pylint, complexipy, interrogate, vulture,
bandit, requirement traceability, pytest at 100% line and branch coverage, and
bolt's secrets scan, cheapest first. The Python tools run through `uv run` at
the version `uv.lock` pins; wording and traceability run toolbox's scripts. The
secrets verdict is `success` in the bolt run's
`result.yaml`, which `just checks` prints the path of.

Run `just checks` and commit with the sandbox off: inside it ruff fails reading
the sandbox's device mounts, and git records the host identity as author.

## How it fits against its siblings

`just/base.just` and `bolt.secrets.yaml` are vendored from `toolbox` and
refreshed by `just vendor`. `wording` and `requirements` need a toolbox
checkout beside this tree, and `leak-scan` needs `bolt` on `PATH`. Nothing installs petstore yet.

## What is decided, and what is open

`docs/DECISIONS/` holds one file per decision. `NEXT_STEPS.md` holds what is
open.
