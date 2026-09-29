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

`traceability` and `tool_output` are internal: they are the
`petstore-requirements` checker the gate runs over this repository's own
requirement registries.

`Stub` is the reason IO is testable here without a mock. Code that does IO takes
the IO as an argument, and a test passes a stub that reaches the failure it
exists for. `docs/architecture/function-boundaries.md` is the pattern.

## Layout

    src/petstore/          the library, one module per tool
    tests/                 one test module per library module
    docs/modules/          per module: a guide and its requirements registry
    docs/testing/          generate's guide and registry
    docs/architecture/     the IO seam pattern
    docs/tooling-and-runbook.md   setup, the gate, the hooks, troubleshooting
    Justfile, just/        the recipes; just/project.just is petstore's own
    README.md              the front door, for somebody arriving cold

## Requirements are YAML registries, one per module

`docs/modules/<module>.requirements.yaml`, read by `petstore-requirements`, not
by toolbox's `test-traceability.py`. Tests cite requirements with
`@pytest.mark.requirement(...)`, not `COVERS:` comments. The registry carries
retirement, `superseded_by` and `next_id`, so an ID is never reused.

Moving to the form my other projects use,
`docs/REQUIREMENTS/<category>/<requirement>.md`, is
decided and not started; `NEXT_STEPS.md` says what it waits on.

## The gate

    just checks

Ruff format and lint, mypy strict, pylint, complexipy, interrogate, vulture,
bandit, requirement traceability, pytest at 100% line and branch coverage, and
bolt's secrets scan, cheapest first. Every tool runs through `uv run` at the
version `uv.lock` pins. The secrets verdict is `success` in the bolt run's
`result.yaml`, which `just checks` prints the path of.

Run `just checks` and commit with the sandbox off: inside it ruff fails reading
the sandbox's device mounts, and git records the host identity as author.

## How it fits against its siblings

`just/base.just` and `bolt.secrets.yaml` are vendored from `toolbox` and
refreshed by `just vendor`. `wording` needs a toolbox checkout beside this
tree, and `leak-scan` needs `bolt` on `PATH`. Nothing installs petstore yet.

## What is decided, and what is open

`docs/DECISIONS/` holds one file per decision. `NEXT_STEPS.md` holds what is
open.
