"""Shared pytest fixtures and deterministic seam stubs."""

from __future__ import annotations

from inspect import Parameter, Signature, signature
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, NamedTuple, NoReturn, Protocol, TypeVar, cast, overload

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator


ResultT_co = TypeVar("ResultT_co", covariant=True)
ReturnT = TypeVar("ReturnT")
YieldT = TypeVar("YieldT")
ExceptionSpec = BaseException | type[BaseException]
_UNSET = object()


class CallEvent(NamedTuple):
    """Immutable metadata captured for one generated-function invocation."""

    args: tuple[object, ...]
    kwargs: MappingProxyType[str, object]
    bound_arguments: MappingProxyType[str, object] | None


class GeneratedFunction(Protocol[ResultT_co]):
    """Callable protocol exposing generated stub metadata."""

    calls: tuple[CallEvent, ...]
    call_count: int
    call_signature: Signature | None

    def __call__(self, *args: object, **kwargs: object) -> ResultT_co:
        """Invoke the generated behavior."""


@overload
def generate(
    *,
    returns: ReturnT,
    raises: object = _UNSET,
    yields: object = _UNSET,
    parameters: Iterable[str] | None = None,
    signature_from: Callable[..., object] | None = None,
) -> GeneratedFunction[ReturnT]: ...


@overload
def generate(
    *,
    returns: object = _UNSET,
    raises: ExceptionSpec,
    yields: object = _UNSET,
    parameters: Iterable[str] | None = None,
    signature_from: Callable[..., object] | None = None,
) -> GeneratedFunction[NoReturn]: ...


@overload
def generate(
    *,
    returns: object = _UNSET,
    raises: object = _UNSET,
    yields: Iterable[YieldT],
    parameters: Iterable[str] | None = None,
    signature_from: Callable[..., object] | None = None,
) -> GeneratedFunction[Iterator[YieldT]]: ...


def generate(
    *,
    returns: object = _UNSET,
    raises: object = _UNSET,
    yields: object = _UNSET,
    parameters: Iterable[str] | None = None,
    signature_from: Callable[..., object] | None = None,
) -> GeneratedFunction[Any]:
    """Generate a function configured to return, raise, or yield values."""
    behaviors = (returns is not _UNSET, raises is not _UNSET, yields is not _UNSET)
    if sum(behaviors) != 1:
        message = "generate requires exactly one of returns, raises, or yields"
        raise ValueError(message)

    call_signature = _make_signature(parameters, signature_from)
    yielded_values = tuple(cast("Iterable[object]", yields)) if yields is not _UNSET else ()
    history: list[CallEvent] = []

    def generated(*args: object, **kwargs: object) -> object:
        """Record a call and perform the configured behavior."""
        bound_arguments = _bind_arguments(call_signature, args, kwargs)
        history.append(CallEvent(args, MappingProxyType(dict(kwargs)), bound_arguments))
        configured.calls = tuple(history)
        configured.call_count = len(history)
        if raises is not _UNSET:
            _raise(cast("ExceptionSpec", raises))
        if yields is not _UNSET:
            return iter(yielded_values)
        return returns

    configured = cast("GeneratedFunction[object]", generated)
    configured.calls = ()
    configured.call_count = 0
    configured.call_signature = call_signature
    return configured


def _make_signature(
    parameters: Iterable[str] | None,
    signature_from: Callable[..., object] | None,
) -> Signature | None:
    """Build a call signature from one optional configuration source."""
    if parameters is not None and signature_from is not None:
        message = "parameters and signature_from are mutually exclusive"
        raise ValueError(message)
    if signature_from is not None:
        return signature(signature_from)
    if parameters is None:
        return None
    declared = tuple(Parameter(name, Parameter.POSITIONAL_OR_KEYWORD) for name in parameters)
    return Signature(declared)


def _bind_arguments(
    call_signature: Signature | None,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> MappingProxyType[str, object] | None:
    """Bind supplied arguments when a generated function has a signature."""
    if call_signature is None:
        return None
    bound = call_signature.bind(*args, **kwargs)
    return MappingProxyType(dict(bound.arguments))


def _raise(exception: ExceptionSpec) -> NoReturn:
    """Raise a configured exception instance or zero-argument type."""
    if isinstance(exception, type):
        raise exception
    raise exception
