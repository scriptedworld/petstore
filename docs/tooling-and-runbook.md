# Tooling and project runbook

This document is the operational reference for developing, validating, and
maintaining petstore.

## Supported environments

The repository is designed to work in either of these environments:

1. A Dev Container built from `.devcontainer/devcontainer.json`.
2. A local Python environment managed exclusively through UV.

Host-specific tools such as `mise` may expose UV, but project commands must not
depend on them. The Dev Container is the portability reference and contains its
own digest-pinned Python and UV environment.

## Structured-data format

YAML is the project default whenever a tool or internal format permits a
choice. New project-owned registries, policies, and portable configuration
files use YAML, not TOML or JSON.

Mandatory ecosystem formats remain in their required native representation.
Examples include `pyproject.toml`, `uv.lock`, and `.devcontainer/devcontainer.json`.
Requirement registries are named for their module, such as
`docs/modules/iteration.requirements.yaml`.

## First-time setup

### Dev Container

Open the repository using a client that implements the Development Container
specification. Container creation performs a frozen synchronization from
`uv.lock` and installs the Git hooks when Git metadata is available.

After creation, verify the environment:

```console
uv run just checks
```

### Local environment

Install UV, then run:

```console
uv sync --frozen
uv run just hooks
uv run just checks
```

`uv sync --frozen` fails on an outdated lockfile instead of silently changing
it. Dependency changes are made deliberately with `uv add`, `uv remove`,
or `uv lock`, followed by review of `uv.lock`.

## just is the task interface

`just` owns the executable project workflow, and it is the only task runner the
repository has. Pre-commit hooks and documentation call `just` recipes, never
individual tools. My projects share the recipe names, so the same words work in
every tree.

`just` itself is pinned in `uv.lock` as the `rust-just` development dependency.
`uv run just <recipe>` therefore needs nothing installed beyond UV, and behaves
identically on a host, in the Dev Container, and in automation. Where `just` is
installed system-wide, `just <recipe>` is the same command.

The recipes are layered through imports, and the first layer to define a recipe
wins:

| File | Owner | Holds |
| --- | --- | --- |
| `Justfile` | Shared | Imports only, plus `default`. Identical in every project. |
| `just/project.just` | This repository | petstore's own recipes, which override the base. |
| `just/base.just` | toolbox, vendored | The ten standard recipes, each a working default or a no-op that succeeds. |

`just/base.just` and `bolt.secrets.yaml` are copies of
[toolbox](https://github.com/scriptedworld/toolbox)'s, committed so a clone
needs nothing beside it. Edit neither here. `just vendor` replaces both with
toolbox's `main`, and `git diff` shows what changed upstream.

`leak-scan` runs the secrets jig through
[bolt](https://github.com/scriptedworld/bolt), with `gitleaks` and
`detect-secrets` on `PATH`. bolt's `docs/runbook.md` says how to build it.

`wording` runs toolbox's `bin/voice-tells.py` from a toolbox checkout beside
this tree; `just toolbox=/path/to/toolbox wording` names another. It reads
every file, and every commit after the SHA in `.voice-review-start`.

List every recipe:

```console
uv run just --list
```

Frequently used recipes:

| Recipe | Purpose |
| --- | --- |
| `checks` | Run every quality gate, cheapest first, stopping at the first failure. |
| `test` | Run the suite without coverage, for a fast inner loop. |
| `coverage` | Run the suite with 100% line and branch coverage enforced. |
| `fix` | Format files and apply safe Ruff fixes. |
| `requirements` | Validate requirement-to-test traceability and emit canonical YAML evidence. |
| `leak-scan` | Run toolbox's secrets jig through bolt. |
| `wording` | Check files and recent commits against the writing standard's wording. |
| `hooks` | Install the configured `pre-commit` and `commit-msg` hooks. |
| `hooks-run` | Run file-oriented pre-commit hooks against the repository. |
| `commit` | Create a Conventional Commit through Commitizen. |
| `commit-check` | Validate a commit message. |
| `clean` | Remove run directories, caches, and build output. The virtual environment is kept. |
| `vendor` | Replace the files taken from toolbox with its `main` branch. |

Individual recipes are useful for quick feedback, but `checks` is the
authoritative final result.

## Quality gate coverage

| Gate | `src/` | `tests/` | Policy |
| --- | --- | --- | --- |
| Ruff formatting and lint | Yes | Yes | Maximum line length 150; no unapproved inline suppressions. |
| Mypy | Yes | Yes | Strict mode. |
| Pylint | Yes | Yes | Any finding fails; averaged scoring is disabled. |
| Complexipy | Yes | Yes | Maximum cognitive complexity 15 per function. |
| Nesting checks | Yes | Yes | Maximum three nested blocks. |
| Interrogate | Yes | No | Production documentation coverage must be 100%. |
| Vulture | Yes | Yes | Dead-code checks use 100% confidence. |
| Bandit | Yes | No | Production security findings fail the gate. |
| Pytest and Coverage | Produces coverage | Executes tests | Production line and branch coverage must each reach 100%. |
| Wording (`wording`) | Yes | Yes | Every tracked text file and every commit after `.voice-review-start`; any finding fails. |
| Secrets jig (`leak-scan`) | Yes | Yes | Run through bolt over the whole repository; the verdict is read from bolt's `result.yaml`, never its exit status. |

Quality thresholds apply to each finding, function, or file as appropriate.
Scores must not be averaged across a file to hide a local failure.

## Pre-commit and commits

`.pre-commit-config.yaml` installs two hook types, and each calls a `just`
recipe and nothing else:

- `pre-commit` runs `uv run just checks`, so a commit runs exactly the gate that
  runs by hand.
- `commit-msg` runs `uv run just commit-check`, which validates the message with
  Commitizen, and `uv run just wording-commit-msg`, which checks its wording.

All commit messages must follow Conventional Commits. The normal workflow is:

```console
uv run just commit
```

`pre-commit` refuses to install on a machine where git's `core.hooksPath` is set
globally, because git then reads no repository's `.git/hooks`. The Dev Container
does not set it, so the hooks install and run there.

Bypassing a local hook does not waive a requirement. The same checks must run
in automation when continuous integration is added.

## Module documentation and requirements

Every production module has a Markdown guide and a canonical
`*.requirements.yaml` registry under `docs/modules/`. YAML is the sole normative
source for requirement statements and lifecycle metadata. Requirement IDs are
never deleted or reused.

Every test uses `pytest.mark.requirement` to record:

- one or more covered requirement IDs;
- the invoked functionality;
- the test classification, such as `positive`, `negative`, `edge`, `property`,
  `invariant`, or `regression`.

When adding or changing behavior:

1. Add a requirement to the canonical YAML registry first. Never change the
   meaning of an active requirement; retire it and allocate a new ID instead.
2. Implement the behavior using the functional boundary-composition standard
   when a genuine seam is required.
3. Add tests with complete requirement metadata.
4. Run `uv run just checks`.
5. Confirm that `uv run just requirements` reports every active requirement,
   required test classification, and declared functionality as covered.

The checker and its stable finding codes are documented in
[`modules/traceability.md`](modules/traceability.md). It statically parses tests
without importing or executing them and emits the canonical tool-result format
documented in [`modules/tool-output.md`](modules/tool-output.md).

Mechanical traceability proves that the declared evidence is complete and
internally consistent. It does not prove that the assertions establish the
requirement; that takes reading the tests.

## Exception and I/O seams

Every IO boundary is a small function passed in through a keyword-only
parameter whose default is that function. A non-IO operation gets a seam only
when the failure a test needs is hard to provoke for real. A test passes a
`petstore.Stub` through the seam, so nothing is patched.

Several boundaries that vary together go in one immutable function policy,
bound by a composition factory.
[`architecture/function-boundaries.md`](architecture/function-boundaries.md)
has both forms with worked examples.

The project uses no mocks or runtime patching. One approved by me before it is
written gets a file of its own in `docs/MOCKS/`, giving its exact location and
mechanism, the reason, an expiry date and a removal condition. The directory
exists only once there is an entry.

## Suppressions and safety findings

An inline `# noqa` or `# nosec`, a tool configuration exception, or an accepted
safety finding is approved by me before it is added, and gets a file of its own
in `docs/SUPPRESSIONS/` containing:

- scope, tool, and exact rule;
- the reason it is safe and was allowed;
- approver and approval date;
- mandatory expiry date;
- removal condition.

Expired entries fail the project policy. Renewals require fresh approval and
must never silently extend an expiry date.

## Network policy

Normal quality gates and Git hooks should be offline-capable after environment
creation. Network access is expected only for explicit operations such as:

- downloading the pinned Dev Container images;
- installing packages from `uv.lock`;
- deliberately updating tool rules or vulnerability databases.

Secret verification, telemetry, repository outreach, and implicit database
updates are not allowed during ordinary checks. A check that needs updated
rules or databases keeps the update as a separate, explicit command, and
enforces offline.

## Troubleshooting

### The lockfile is stale

Run `uv lock`, review the dependency changes, then rerun `uv sync --frozen` and
`uv run just checks`.

### Hooks are missing

Run `uv run just hooks`. Hook installation requires a functional Git repository.

### A quality tool needs a cache directory

Use a writable cache directory appropriate to the environment. CI and container
configuration should supply this explicitly, so no tool writes into an
unavailable host home directory.

### A finding appears incorrect

Fix or restructure the code first. Where a suppression is genuinely necessary,
ask me before changing configuration or adding an inline declaration, then
record the approved exception and its expiry in `docs/SUPPRESSIONS/`.

### The host behaves differently from the container

Treat the digest-pinned Dev Container as the reference. Rebuild it and run
`uv run just checks` inside it. Resolve any difference that remains in the
checked-in project configuration, not in undocumented host setup.
