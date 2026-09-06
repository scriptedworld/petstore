# Tooling and project runbook

This document is the operational reference for developing, validating, and
maintaining PetStore. The same structure is intended to become the baseline for
future Python projects after it has been proven here.

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
files should use YAML rather than TOML or JSON.

Mandatory ecosystem formats remain in their required native representation.
Examples include `pyproject.toml`, `uv.lock`, and `.devcontainer/devcontainer.json`.
Requirement registries will use names such as
`docs/modules/iteration.requirements.yaml`.

## First-time setup

### Dev Container

Open the repository using a client that implements the Development Container
specification. Container creation performs a frozen synchronization from
`uv.lock` and installs the Git hooks when Git metadata is available.

After creation, verify the environment:

```console
uv run poe quality
```

### Local environment

Install UV, then run:

```console
uv sync --frozen
uv run poe hooks
uv run poe quality
```

`uv sync --frozen` must fail rather than silently changing an outdated
lockfile. Dependency changes are made deliberately with `uv add`, `uv remove`,
or `uv lock`, followed by review of `uv.lock`.

## Poe is the task interface

Poe owns the executable project workflow. Pre-commit and documentation should
delegate to Poe rather than duplicate individual tool commands.

List the available tasks:

```console
uv run poe --help
```

Frequently used tasks:

| Task | Purpose |
| --- | --- |
| `quality` | Run every required quality gate in the standard order. |
| `fix` | Format files and apply safe Ruff fixes. |
| `test` | Run Pytest with line and branch coverage. |
| `requirements` | Validate requirement-to-test traceability and emit canonical YAML evidence. |
| `hooks` | Install the configured `pre-commit` and `commit-msg` hooks. |
| `hooks-run` | Run file-oriented pre-commit hooks against the repository. |
| `commit` | Create a Conventional Commit through Commitizen. |
| `commit-check` | Validate an existing commit message. |

Individual quality tasks are useful for quick feedback, but `quality` is the
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

Quality thresholds apply to each finding, function, or file as appropriate.
Scores must not be averaged across a file to hide a local failure.

## Pre-commit and commits

`.pre-commit-config.yaml` installs two hook types:

- `pre-commit` delegates the complete validation to `uv run poe quality`.
- `commit-msg` delegates message validation to Commitizen.

All commit messages must follow Conventional Commits. The normal workflow is:

```console
uv run poe commit
```

Bypassing a local hook does not waive a requirement. The same checks must run
in automation when continuous integration is added.

## Module documentation and requirements

Every production module has a human-oriented Markdown guide and a canonical
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
4. Run `uv run poe quality`.
5. Confirm that `uv run poe requirements` reports every active requirement,
   required test classification, and declared functionality as covered.

The checker and its stable finding codes are documented in
[`modules/traceability.md`](modules/traceability.md). It statically parses tests
without importing or executing them and emits the canonical tool-result format
documented in [`modules/tool-output.md`](modules/tool-output.md).

Mechanical traceability proves that the declared evidence is complete and
internally consistent. It does not prove that assertions semantically establish
the requirement. A future agent skill will consume the normalized evidence to
review that deeper relationship.

## Exception and I/O seams

All I/O boundaries are isolated behind seam functions. Non-I/O operations use
an injected seam only when inducing a required exception type directly would
otherwise be difficult or unreliable. Ordinary validation failures that are
easy to construct do not justify injection parameters.

The canonical implementation pattern is documented in
[`architecture/function-boundaries.md`](architecture/function-boundaries.md).
A private implementation function receives explicit keyword-only strategies or
one immutable function policy. An operation-specific composition factory binds
the production implementations and returns a closure with the clean public
signature. Production defaults belong to the factory, not the implementation.
The closure performs pass-through wiring only.

Use one strategy function for one boundary. Use a function policy only for a
cohesive group of related boundary functions that normally varies together. A
policy is an immutable typed bag of functions, not a service container. Pure
logic and directly inducible failures do not receive seams.

The project currently uses no mocks or runtime patching. `MOCKS.md` contains an
empty approved ledger and a clearly non-operative example of the required
format. Mocks must not be added speculatively; a real entry requires explicit
human approval, exact usage details, a reason, an expiry date, and a removal
condition.

## Suppressions and safety findings

`SUPPRESSIONS.md` is the only project-wide suppression ledger. An inline
`# noqa` or `# nosec`, tool configuration exception, or accepted safety finding
requires prior human approval and a ledger entry containing:

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
updates are not allowed during ordinary checks. Future secrets and dependency
vulnerability tasks must provide separate explicit update commands and offline
enforcement commands.

## Troubleshooting

### The lockfile is stale

Run `uv lock`, review the dependency changes, then rerun `uv sync --frozen` and
`uv run poe quality`.

### Hooks are missing

Run `uv run poe hooks`. Hook installation requires a functional Git repository.

### A quality tool needs a cache directory

Use a writable cache directory appropriate to the environment. CI and container
configuration should supply this explicitly rather than writing into an
unavailable host home directory.

### A finding appears incorrect

Fix or restructure the code first. If suppression is genuinely necessary, stop
and obtain human approval before changing configuration or adding an inline
declaration. Record the approved exception and expiry in `SUPPRESSIONS.md`.

### The host behaves differently from the container

Treat the digest-pinned Dev Container as the reference. Rebuild it and run
`uv run poe quality` inside it. Differences that remain must be resolved in the
checked-in project configuration rather than through undocumented host setup.
