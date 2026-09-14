# petstore's own recipes. No template writes this file.
#
# just is the only task interface this tree has: no task is defined in any other
# runner. Where a recipe does something among the estate's ten, it takes that
# name, so the whole gate is `checks` here as it is everywhere.
#
# EVERY RECIPE RUNS THROUGH uv. petstore's tools are pinned in uv.lock, and a
# bare `mypy` or `pytest` from PATH is a different version against a different
# interpreter. The one exception is `leak-scan`, which base.just supplies and
# which runs bolt, invoking the secrets checkers from PATH by design.
#
# THE ORDER IN `checks` IS CHEAPEST FIRST, so a formatting slip fails in a
# second rather than after the whole suite. just stops at the first failing
# line, so the first failure is the one reported.

# everything: formatting, lint, types, analysis, traceability, coverage, secrets
checks:
    @just format-check
    @just lint
    @just typecheck
    @just pylint
    @just complexity
    @just docs
    @just dead-code
    @just security
    @just requirements
    @just coverage
    @just leak-scan

# THE SUITE WITHOUT COVERAGE. pyproject's pytest options always measure and
# enforce coverage, so `test` switches that off to be the fast inner loop, and
# `coverage` is the run that holds the 100% line and branch minimum.

# the suite
test:
    uv run pytest --no-cov

# the suite with coverage, and the minimum enforced
coverage:
    uv run pytest

# formatting verified, nothing written
format-check:
    uv run ruff format --check .

# formatting written
format:
    uv run ruff format .

# ruff lint, nothing written
lint:
    uv run ruff check .

# ruff lint with its safe fixes written
lint-fix:
    uv run ruff check --fix .

# formatting and safe lint fixes written
fix:
    @just format
    @just lint-fix

# strict static type checking
typecheck:
    uv run mypy

# pylint over source and tests, any finding fails
pylint:
    uv run pylint src tests

# per-function cognitive complexity, at most 15
complexity:
    uv run complexipy --max-complexity-allowed 15 src tests

# production docstring coverage, 100% required
docs:
    uv run interrogate src

# unused production and test code
dead-code:
    uv run vulture

# static security checks on production code
security:
    uv run bandit -c pyproject.toml -r src

# requirement-to-test traceability, emitted as canonical YAML
requirements:
    uv run petstore-requirements

# the wheel and source distribution
dist:
    uv build

# REFUSES ON A MACHINE WITH A GLOBAL core.hooksPath, including the one this was
# written on: git reads no .git/hooks there, and pre-commit will not install
# into a directory git ignores. It works in the devcontainer and anywhere else
# core.hooksPath is unset. How the hook is wired estate-wide is silo's open
# question, filed at the task tracker.

# install the pre-commit and commit-msg hooks
hooks:
    uv run pre-commit install --install-hooks

# run every file-oriented pre-commit hook across the tree
hooks-run:
    uv run pre-commit run --all-files

# write a Conventional Commit interactively
commit:
    uv run cz commit

# check a commit message is a Conventional Commit; the commit-msg hook passes its file
commit-check *args:
    uv run cz check {{ args }}

# CLEAN REMOVES ONLY WHAT NOTHING EXECUTES. The virtual environment is left,
# because tools run from it, and base.just's reason for the rule applies here.

# remove run directories and build output
clean:
    rm -rf .bolt-* dist build .coverage coverage.xml
    rm -rf .ruff_cache .mypy_cache .pytest_cache .complexipy_cache
    find . -path ./.venv -prune -o -name __pycache__ -type d -prune -exec rm -rf {} +
