"""Tests holding pyproject's version and the git release tags together."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import petstore
from petstore.proc import capture

ROOT = Path(__file__).resolve().parents[1]
RELEASE_TAG = re.compile(r"v(\d+)\.(\d+)\.(\d+)")


def version() -> str:
    """Return the version pyproject.toml declares."""
    with (ROOT / "pyproject.toml").open("rb") as file:
        declared: str = tomllib.load(file)["project"]["version"]
    return declared


def git(*args: str) -> list[str]:
    """Return the lines git prints for args, run in this repository."""
    finished = capture(["git", *args], cwd=ROOT, timeout=60, check=True)
    return finished.stdout.split()


def parts(tag: str) -> tuple[int, ...]:
    """Return a release tag's numbers, for comparing versions in order."""
    match = RELEASE_TAG.fullmatch(tag)
    assert match is not None, tag
    return tuple(int(number) for number in match.groups())


# COVERS FR-9.1 | positive
def test_dunder_version_reads_pyproject() -> None:
    """petstore.__version__ is the version pyproject.toml declares, read back rather than written twice."""
    assert petstore.__version__ == version()


# COVERS FR-9.1 | property
def test_version_equals_the_tag_on_this_commit() -> None:
    """A commit carrying a release tag declares exactly that version."""
    for tag in git("tag", "--points-at", "HEAD", "--list", "v*"):
        assert tag == f"v{version()}"


# COVERS FR-9.1 | property
def test_version_is_not_below_the_latest_release() -> None:
    """The declared version never falls behind a release this commit already contains."""
    released = git("tag", "--merged", "HEAD", "--list", "v*")
    if released:
        latest = max(released, key=parts)
        assert parts(f"v{version()}") >= parts(latest), latest


# COVERS FR-9.2 | property
def test_every_release_tag_is_named_for_its_version() -> None:
    """Every v* tag is vMAJOR.MINOR.PATCH, and no tag at all is pure hex."""
    tags = git("tag", "--list")
    assert all(RELEASE_TAG.fullmatch(tag) for tag in tags if tag.startswith("v")), tags
    assert not [tag for tag in tags if re.fullmatch(r"[0-9a-f]+", tag)], tags
