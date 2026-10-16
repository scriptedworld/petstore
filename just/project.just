# petstore's own recipes. No template writes this file.
#
# just is the only task interface this tree has: no task is defined in any other
# runner. Where a recipe does one of base.just's ten jobs, it takes that name,
# so the whole gate is `checks` here as it is in every tree.
#
# The gate is toolbox's jigs, run through bolt from a toolbox checkout beside
# this tree, so every step reports a result envelope and its verdict is read
# from the run's result.yaml. `just toolbox=/path/to/toolbox checks` names
# another checkout. The jigs call their tools from PATH, and `checks` runs
# bolt under `uv run --locked`, so the locked environment's bin comes first:
# its python3, which toolbox's adapters import wrench and yaml from, and the
# tools uv.lock pins. A tool the environment does not hold, such as bolt or
# detect-secrets, still comes from the host.
#
# common-quality holds traceability, suppressions, wording and secrets. Its
# `requirements-directory` definitions, which toolbox ships, point it at
# docs/REQUIREMENTS.
toolbox := "../toolbox"

# everything: the Python jig, then traceability, suppressions, wording and secrets
checks:
    @uv run --locked just _verdict python-std-quality --config-dir {{ toolbox }}
    @uv run --locked just _verdict common-quality --config-dir {{ toolbox }} --definitions requirements-directory

# the python3 `checks` gives the jigs, and the wrench it imports
gate-env:
    @uv run --locked which python3
    @uv pip show wrench

# the writing standard's wording over one commit message; the commit-msg hook passes its file
wording-commit-msg file:
    python3 {{ toolbox }}/bin/voice-tells.py --commit-msg-filename {{ file }}

# The single-tool recipes take the paths to check, defaulting to the tree, so
# one file is `just lint src/petstore/proc.py`. `checks` is still the verdict.

# the suite, or the named tests
test *args:
    uv run pytest {{ args }}

# the suite under coverage, reported per file; the jig holds the minimum
coverage:
    uv run coverage run -m pytest -q
    uv run coverage report

# formatting verified, nothing written
format-check *paths=".":
    uv run ruff format --check {{ paths }}

# formatting written
format *paths=".":
    uv run ruff format {{ paths }}

# ruff lint, nothing written
lint *paths=".":
    uv run ruff check {{ paths }}

# ruff lint with its safe fixes written
lint-fix *paths=".":
    uv run ruff check --fix {{ paths }}

# mypy, strict as pyproject.toml sets it
types *paths=".":
    uv run mypy {{ paths }}

# bandit over the source, and over the tests except assert
security:
    uv run bandit -r -q src
    uv run bandit -r -q --skip B101 tests

# formatting and safe lint fixes written
fix:
    @just format
    @just lint-fix

# resolve dependencies again into uv.lock, after pyproject.toml changes
lock:
    uv lock

# the wheel and source distribution
dist:
    uv build

# base.just and bolt.secrets.yaml are toolbox's, committed here so a clone runs
# every recipe with nothing beside it. `vendor` replaces both with toolbox's
# main branch on GitHub; `git diff` then shows what changed upstream. Each is
# fetched to a temporary name and moved into place, so a half-written download
# never replaces a working file.

# refresh the files taken from toolbox, from its main branch
vendor:
    curl -fsSL -o just/base.just.tmp https://raw.githubusercontent.com/scriptedworld/toolbox/main/just/base.just
    mv just/base.just.tmp just/base.just
    curl -fsSL -o bolt.secrets.yaml.tmp https://raw.githubusercontent.com/scriptedworld/toolbox/main/bolt.secrets.yaml
    mv bolt.secrets.yaml.tmp bolt.secrets.yaml

# A release is commitizen's bump of the one version in pyproject.toml, an
# annotated tag vX.Y.Z on that commit, and both pushed. Consumers pin the tag,
# never a commit hash: a quoted hex hash in their pyproject.toml reads as a
# secret to detect-secrets. Before 1.0, a minor release may break things. A
# pushed tag is never moved or deleted; a mistake is fixed by the next patch
# release.
#
# cz bump works out the increment from the conventional commits since the last
# tag, writes CHANGELOG.md, relocks (its pre_bump_hooks), and commits with
# `git commit -a`. That is why the tree must be clean first: -a then picks up
# only the bump's own files, pyproject.toml, uv.lock and CHANGELOG.md.

# release, or release --increment PATCH: gate, cz bump and tag, push both, show the tag on origin
[positional-arguments]
release *bump_args:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ "$(git branch --show-current)" != main ]; then echo "refused: release from main" >&2; exit 1; fi
    if ! git diff --quiet || ! git diff --cached --quiet; then echo "refused: commit or stash your changes first" >&2; exit 1; fi
    just checks
    uv run cz bump --yes "$@"
    version=$(uv run cz version --project)
    git push --follow-tags origin main
    git ls-remote --tags origin "v$version"

# `hooks` refuses on any machine with a global core.hooksPath, including the
# development host: git reads no .git/hooks there, and pre-commit will not
# install into a directory git ignores. It works in the devcontainer and
# anywhere else core.hooksPath is unset.

# install the pre-commit and commit-msg hooks
hooks:
    uv run pre-commit install --install-hooks

# run every file-oriented pre-commit hook across the tree
hooks-run:
    uv run pre-commit run --all-files

# write a Conventional Commit interactively
commit:
    uv run cz commit

# print the whole changelog as CHANGELOG.md.j2 renders it, writing nothing
changelog-preview:
    uv run cz changelog --dry-run

# check a commit message is a Conventional Commit; the commit-msg hook passes its file
commit-check *args:
    uv run cz check {{ args }}

# `clean` removes only what nothing executes. The virtual environment is left,
# because tools run from it, and base.just's reason for the rule applies here.

# remove run directories and build output
clean:
    rm -rf .bolt-* dist build .coverage coverage.xml
    rm -rf .ruff_cache .mypy_cache .pytest_cache .complexipy_cache
    find . -path ./.venv -prune -o -name __pycache__ -type d -prune -exec rm -rf {} +
