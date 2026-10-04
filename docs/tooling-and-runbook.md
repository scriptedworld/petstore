# Tooling and project runbook

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

`just` itself is pinned in `uv.lock` as the `rust-just` development dependency,
so `uv run just <recipe>` needs nothing installed beyond UV for the recipes
that run through uv. Where `just` is installed system-wide, `just <recipe>` is
the same command.

`checks` needs more: a [toolbox](https://github.com/scriptedworld/toolbox)
checkout beside this tree, [bolt](https://github.com/scriptedworld/bolt), and
the tools the jigs call on `PATH` (ruff, mypy, pylint, complexipy, vulture,
interrogate, bandit, gitleaks, detect-secrets). bolt's `docs/runbook.md` says
how to build it and install them.

The recipes are layered through imports, and the first layer to define a recipe
wins:

| File | Owner | Holds |
| --- | --- | --- |
| `Justfile` | Shared | Imports only, plus `default`. Identical in every project. |
| `just/project.just` | This repository | petstore's own recipes, which override the base. |
| `just/base.just` | toolbox, vendored | The ten standard recipes, each a working default or a no-op that succeeds. |

`just/base.just` and `bolt.secrets.yaml` are copies of
[toolbox](https://github.com/scriptedworld/toolbox)'s, committed so the
Justfile loads without a toolbox checkout. Edit neither here. `just vendor`
replaces both with toolbox's `main`, and `git diff` shows what changed
upstream.

`checks` runs the `python-std-quality` and `common-quality` jigs from the
toolbox checkout; `just toolbox=/path/to/toolbox checks` names another.
`common-quality` takes toolbox's `requirements-directory` definitions, which
point it at `docs/REQUIREMENTS`. `leak-scan` runs the vendored secrets jig
alone.

List every recipe:

```console
uv run just --list
```

Frequently used recipes:

| Recipe | Purpose |
| --- | --- |
| `checks` | Run the whole gate: the Python jig, then traceability, suppressions, wording and secrets. |
| `test` | Run the suite, or the tests named: `just test tests/test_proc.py`. |
| `lint`, `types`, `format-check` | ruff, mypy or the formatter alone, over the paths named or the tree. |
| `security` | bandit over the source, and over the tests except `assert`. |
| `coverage` | Run the suite under coverage and report it per file. |
| `fix` | Format files and apply safe Ruff fixes. |
| `leak-scan` | Run toolbox's secrets jig through bolt. |
| `hooks` | Install the configured `pre-commit` and `commit-msg` hooks. |
| `hooks-run` | Run file-oriented pre-commit hooks against the repository. |
| `commit` | Create a Conventional Commit through Commitizen. |
| `commit-check` | Validate a commit message. |
| `clean` | Remove run directories, caches, and build output. The virtual environment is kept. |
| `vendor` | Replace the files taken from toolbox with its `main` branch. |

## Quality gate coverage

The Python checks are toolbox's `python-std-quality` jig: ruff formatting and
the ruff rules `pyproject.toml` selects, mypy strict as `pyproject.toml` sets
it, duplication and nesting, complexity, dead code, docstrings, bandit, and the
suite under per-file line and branch coverage. Its thresholds are the ones that
apply, and `bolt.python-std-quality.yaml` in toolbox states each beside the
task that holds it.

Then toolbox's `common-quality` jig:

| Task | Policy |
| --- | --- |
| `traceability` | Every test cites a requirement, and every settled requirement has a test. |
| `suppressions` | Every suppression pragma is registered in `SUPPRESSIONS/`, and every entry is real. |
| `wording` | Every tracked text file and every commit after `.voice-review-start`; any finding fails. |
| `secrets` | The secrets jig over the whole repository and its history. |

Each bolt run's verdict is `success` in the `result.yaml` it names, never its
exit status. Thresholds apply per file or per function, never averaged.

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

## Module documentation and requirements

Every production module has a Markdown guide under `docs/modules/`, and its
requirements are under `docs/REQUIREMENTS/<module>/`, one file per requirement
holding a single table row. [`REQUIREMENTS/README.md`](REQUIREMENTS/README.md)
says how the IDs are numbered. An ID is never deleted or reused: a retired
requirement stays, renamed to end `.retired.md`.

Every test carries a comment directly above it naming what it covers and how:

```python
# COVERS FR-1.2, FR-1.13 | positive
def test_shortest_matches_python_zip() -> None:
```

The kind is one of `positive`, `negative`, `edge`, `property` or `regression`.

When adding or changing behavior:

1. Add the requirement first. Never change the meaning of an active one;
   retire it and add a new ID instead.
2. Implement the behavior, with a seam where a boundary needs one.
3. Add tests carrying `COVERS` comments.
4. Run `uv run just checks`.

The `common-quality` jig's `traceability` task runs toolbox's
`bin/test-traceability.py`. It fails a test that cites nothing or cites an
unknown or retired ID, and a settled requirement no test cites.

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
in `SUPPRESSIONS/`, which the gate reads, containing:

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
record the approved exception and its expiry in `SUPPRESSIONS/`.

### The host behaves differently from the container

Treat the digest-pinned Dev Container as the reference. Rebuild it and run
`uv run just checks` inside it. Resolve any difference that remains in the
checked-in project configuration, not in undocumented host setup.
