"""Reusable tools for personal Python development."""

from importlib.metadata import version as _installed_version

from .iteration import ZipMode, zip_iter
from .locking import LockError, LockTimeoutError, locked, make_locked
from .stubs import CallEvent, Stub, StubExhaustedError, generate
from .validation import Rule, Validated, ValidationError, validate

__all__ = [
    "CallEvent",
    "LockError",
    "LockTimeoutError",
    "Rule",
    "Stub",
    "StubExhaustedError",
    "Validated",
    "ValidationError",
    "ZipMode",
    "generate",
    "locked",
    "make_locked",
    "validate",
    "zip_iter",
]

# Read from the installed metadata, so pyproject.toml stays the one place the
# version is written.
__version__ = _installed_version("petstore")
