# petstore's own recipes. No template writes this file.
#
# just is the only task interface this tree has: no task is defined in any other
# runner. Where a recipe does one of base.just's ten jobs, it takes that name,
# so the whole gate is `checks` here as it is in every tree.
#
# Every recipe runs through uv. petstore's tools are pinned in uv.lock, and a
# bare `mypy` or `pytest` from PATH is a different version against a different
# interpreter. The one exception is `leak-scan`, which base.just supplies and
# which runs bolt, invoking the secrets checkers from PATH by design.
#
# The order in `checks` is cheapest first, so a formatting slip fails in a
# second, not after the whole suite. just stops at the first failing
# line, so the first failure is the one reported.

# everything: formatting, lint, types, analysis, wording, traceability, coverage, secrets
checks:
    @just format-check
    @just lint
    @just typecheck
    @just pylint
    @just complexity
    @just docs
    @just dead-code
    @just security
    @just wording
    @just requirements
    @just coverage
    @just leak-scan

# The wording check is toolbox's bin/voice-tells.py, run from a toolbox
# checkout beside this tree; `just toolbox=/path/to/toolbox wording` names
# another. Commits after the SHA in .voice-review-start are read as well.
toolbox := "../toolbox"

# the writing standard's wording, over every file and every commit since the start SHA
wording:
    python3 {{ toolbox }}/bin/voice-tells.py --all-files

# the same check over one commit message; the commit-msg hook passes its file
wording-commit-msg file:
    python3 {{ toolbox }}/bin/voice-tells.py --commit-msg-filename {{ file }}

# `test` is the suite without coverage. pyproject's pytest options always measure and
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

# every test cites a requirement and every settled requirement has a test
requirements:
    python3 {{ toolbox }}/bin/test-traceability.py --requirements docs/REQUIREMENTS .

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
