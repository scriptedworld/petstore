"""Scripted test doubles that record how they were called.

A stub is built by chaining links that describe successive calls:

    fetch = Stub().returns(200).yields("a").yields("b").raises(TimeoutError)

    fetch()   # 200
    fetch()   # an iterator producing "a" then "b"
    fetch()   # raises TimeoutError

``returns`` and ``raises`` each describe one whole call. ``yields`` and
``yields_from`` mirror the statements they are named after and accumulate into
a single call's iterator: ``yields(a)`` is ``yield a``, and ``yields_from(a)``
is ``yield from a``. A run of them therefore builds one generator, which the
next ``returns`` or ``raises`` closes.

    Stub().yields(1).yields_from([2, 3]).returns(None)

    # call one produces 1, 2, 3; call two returns None

By default a link covers one call. A modifier widens the most recent link, and
each link takes at most one:

    Stub().returns("not ready").times(3).returns("ready")      # three calls, then one
    Stub().returns("warming").over(seconds=30).returns("up")   # for 30 seconds, then one
    Stub().returns("ready").always()                           # every call from here on

A timed link's window opens at the first call that reaches it, and is measured
by the stub's clock. Tests should pass their own clock rather than waiting, so
that time advances only when the test says it does.

Calling a stub more times than the script describes raises
``StubExhaustedError`` rather than silently repeating, so code that calls its
boundary more often than the test expects fails the test. Every
invocation is recorded whether or not it had a scripted outcome, so ``calls``
can be inspected after a failure as well as after a success.

A repeated generator link builds a fresh iterator on each call. Anything passed
to ``yields_from`` is iterated again each time, so give it a re-iterable such as
a list: a one-shot iterator is empty from the second call onwards.

Declaring a signature makes the stub reject calls the real function would
reject, and records the arguments bound to their parameter names:

    Stub(parameters=["path"]).returns(None)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import timedelta
from inspect import Parameter, Signature, signature
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Generic, NamedTuple, NoReturn, ParamSpec, TypeVar, cast, overload

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

__all__ = ["CallEvent", "Stub", "StubExhaustedError", "generate", "make_signature"]

ExceptionSpec = BaseException | type[BaseException]

P = ParamSpec("P")
R = TypeVar("R")
ReturnT = TypeVar("ReturnT")
YieldT = TypeVar("YieldT")
_UNSET = object()

# One generator step: whether to delegate to an iterable, and what to produce.
_Step = tuple[bool, object]


class StubExhaustedError(AssertionError):
    """Raised when a stub is called more times than its script describes."""


class CallEvent(NamedTuple):
    """What one invocation of a stub received."""

    args: tuple[object, ...]
    kwargs: MappingProxyType[str, object]
    bound_arguments: MappingProxyType[str, object] | None


@dataclass
class _Link:
    """One scripted outcome, and how many calls or how long it covers.

    With neither a call limit nor a time limit, the link covers every call.
    """

    outcome: Callable[[], object]
    calls: int | None = 1
    seconds: float | None = None
    modified: bool = False


@dataclass
class _Playback:
    """Where a stub is in its script: the current link and how it has been used."""

    link: int = 0
    served: int = 0
    started: float | None = None

    def advance(self) -> None:
        """Move to the next link, forgetting how the previous one was used."""
        self.link += 1
        self.served = 0
        self.started = None


def _raise(exception: ExceptionSpec) -> NoReturn:
    """Raise a configured exception instance or zero-argument type."""
    if isinstance(exception, type):
        raise exception
    raise exception


def _produce(steps: tuple[_Step, ...]) -> Iterator[object]:
    """Produce the values one generator link accumulated, in order."""
    for delegated, payload in steps:
        if delegated:
            yield from cast("Iterable[object]", payload)
        else:
            yield payload


def make_signature(
    parameters: Iterable[str] | None,
    signature_from: Callable[..., object] | None,
) -> Signature | None:
    """Build a call signature from at most one configuration source.

    Args:
        parameters: Positional-or-keyword parameter names to accept.
        signature_from: A callable whose signature is copied.

    Returns:
        The signature, or None when neither source is given.

    Raises:
        ValueError: If both sources are given.

    """
    if parameters is not None and signature_from is not None:
        message = "parameters and signature_from are mutually exclusive"
        raise ValueError(message)
    if signature_from is not None:
        return signature(signature_from)
    if parameters is None:
        return None
    declared = tuple(Parameter(name, Parameter.POSITIONAL_OR_KEYWORD) for name in parameters)
    return Signature(declared)


class Stub(Generic[P, R]):
    """A callable whose successive outcomes are scripted one link at a time.

    Built from a callable, the stub takes that callable's parameter and return
    types, so it type-checks wherever the callable would and a scripted return
    value of the wrong type is a type error. Built without one, it accepts any
    arguments and returns ``Any``.
    """

    @overload
    def __init__(
        self,
        signature_from: Callable[P, R],
        *,
        name: str = "stub",
        clock: Callable[[], float] = time.monotonic,
    ) -> None: ...

    @overload
    def __init__(
        self: Stub[..., Any],
        signature_from: Callable[..., object] | None = None,
        *,
        parameters: Iterable[str] | None = None,
        name: str = "stub",
        clock: Callable[[], float] = time.monotonic,
    ) -> None: ...

    def __init__(
        self,
        signature_from: Callable[..., object] | None = None,
        *,
        parameters: Iterable[str] | None = None,
        name: str = "stub",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Configure the call signature, diagnostics name, and clock.

        Args:
            signature_from: Copy the accepted signature from this callable.
            parameters: Accept exactly these positional-or-keyword names.
                Mutually exclusive with signature_from.
            name: Identifies this stub in the exhaustion message.
            clock: Returns the current time in seconds for timed links.

        """
        self._signature = make_signature(parameters, signature_from)
        self._name = name
        self._clock = clock
        self._links: list[_Link] = []
        self._open_steps: list[_Step] | None = None
        self._history: list[CallEvent] = []
        self._playback = _Playback()

    @property
    def calls(self) -> tuple[CallEvent, ...]:
        """Every invocation so far, in order."""
        return tuple(self._history)

    @property
    def call_count(self) -> int:
        """How many times this stub has been invoked."""
        return len(self._history)

    def returns(self, value: R) -> Stub[P, R]:
        """Add a call that returns *value*, closing any open generator link."""
        self._append(lambda: value)
        self._open_steps = None
        return self

    def raises(self, exception: ExceptionSpec) -> Stub[P, R]:
        """Add a call that raises *exception*, an instance or a zero-argument type."""
        self._append(lambda: _raise(exception))
        self._open_steps = None
        return self

    def yields(self, value: object) -> Stub[P, R]:
        """Produce *value* from the current generator link, as ``yield value`` does."""
        self._steps().append((False, value))
        return self

    def yields_from(self, values: Iterable[object]) -> Stub[P, R]:
        """Delegate to *values* from the current link, as ``yield from values`` does."""
        self._steps().append((True, values))
        return self

    def times(self, count: int) -> Stub[P, R]:
        """Make the most recent link cover *count* consecutive calls.

        Raises:
            ValueError: If count is below one, there is no link, or the link
                already has a modifier.

        """
        if count < 1:
            message = f"times() needs a count of at least one, got {count}"
            raise ValueError(message)
        self._modify_last("times").calls = count
        return self

    def over(self, *, hours: float = 0, minutes: float = 0, seconds: float = 0) -> Stub[P, R]:
        """Make the most recent link cover every call within a time window.

        The window opens at the first call that reaches the link.

        Raises:
            ValueError: If the duration is not positive, there is no link, or
                the link already has a modifier.

        """
        duration = timedelta(hours=hours, minutes=minutes, seconds=seconds).total_seconds()
        if duration <= 0:
            message = f"over() needs a positive duration, got {duration} seconds"
            raise ValueError(message)
        link = self._modify_last("over")
        link.calls = None
        link.seconds = duration
        return self

    def always(self) -> Stub[P, R]:
        """Make the most recent link cover this and every later call.

        Raises:
            ValueError: If there is no link, or the link already has a modifier.

        """
        self._modify_last("always").calls = None
        return self

    def _append(self, outcome: Callable[[], object]) -> None:
        """Add a link, refusing one that an unending link would make unreachable."""
        if self._links and self._links[-1].calls is None and self._links[-1].seconds is None:
            message = "no link may follow always(); the repeating link is never left"
            raise ValueError(message)
        self._links.append(_Link(outcome))

    def _modify_last(self, modifier: str) -> _Link:
        """Return the most recent link for one modifier, closing any open generator."""
        if not self._links:
            message = f"{modifier}() needs a preceding link"
            raise ValueError(message)
        link = self._links[-1]
        if link.modified:
            message = "a link takes at most one of times(), over(), or always()"
            raise ValueError(message)
        link.modified = True
        self._open_steps = None
        return link

    def _steps(self) -> list[_Step]:
        """Return the open generator link's steps, starting a link if none is open."""
        if self._open_steps is None:
            steps: list[_Step] = []
            self._append(lambda: _produce(tuple(steps)))
            self._open_steps = steps
        return self._open_steps

    def _covers(self, link: _Link, now: float) -> bool:
        """Report whether *link* still covers a call made at *now*."""
        playback = self._playback
        if link.seconds is not None:
            return playback.started is None or now - playback.started < link.seconds
        return link.calls is None or playback.served < link.calls

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Record this invocation, then perform the outcome scripted for it."""
        bound = None
        if self._signature is not None:
            bound = MappingProxyType(dict(self._signature.bind(*args, **kwargs).arguments))
        self._history.append(CallEvent(args, MappingProxyType(dict(kwargs)), bound))
        now = self._clock()
        playback = self._playback
        while playback.link < len(self._links) and not self._covers(self._links[playback.link], now):
            playback.advance()
        if playback.link >= len(self._links):
            message = f"{self._name} called {self.call_count} time(s); its script has no link left for this call"
            raise StubExhaustedError(message)
        if playback.started is None:
            playback.started = now
        playback.served += 1
        return cast("R", self._links[playback.link].outcome())


@overload
def generate(
    *,
    returns: ReturnT,
    parameters: Iterable[str] | None = None,
    signature_from: Callable[..., object] | None = None,
) -> Stub[..., ReturnT]: ...


@overload
def generate(
    *,
    raises: ExceptionSpec,
    parameters: Iterable[str] | None = None,
    signature_from: Callable[..., object] | None = None,
) -> Stub[..., NoReturn]: ...


@overload
def generate(
    *,
    yields: Iterable[YieldT],
    parameters: Iterable[str] | None = None,
    signature_from: Callable[..., object] | None = None,
) -> Stub[..., Iterator[YieldT]]: ...


def generate(
    *,
    returns: object = _UNSET,
    raises: object = _UNSET,
    yields: object = _UNSET,
    parameters: Iterable[str] | None = None,
    signature_from: Callable[..., object] | None = None,
) -> Stub[..., Any]:
    """Build a stub that does one thing on every call.

    The short form of a stub whose script is a single ``always()`` link: it
    returns *returns*, raises *raises*, or yields a fresh iterator over a
    snapshot of *yields*, however many times it is called.

    Args:
        returns: The value every call returns.
        raises: The exception every call raises, an instance or a
            zero-argument type.
        yields: Values snapshotted now and produced by every call's iterator.
        parameters: Accept exactly these positional-or-keyword names.
        signature_from: Copy the accepted signature from this callable.

    Returns:
        The configured stub.

    Raises:
        ValueError: If not exactly one of returns, raises, or yields is
            given, or if both signature sources are given.

    """
    if sum(behavior is not _UNSET for behavior in (returns, raises, yields)) != 1:
        message = "generate requires exactly one of returns, raises, or yields"
        raise ValueError(message)
    stub: Stub[..., Any] = Stub(signature_from, parameters=parameters, name="generated")
    if raises is not _UNSET:
        stub.raises(cast("ExceptionSpec", raises))
    elif yields is not _UNSET:
        stub.yields_from(tuple(cast("Iterable[object]", yields)))
    else:
        stub.returns(returns)
    return stub.always()
