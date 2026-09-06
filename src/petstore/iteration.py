"""Lazy tools for combining iterables."""

from __future__ import annotations

from enum import Enum
from itertools import zip_longest
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


class ZipMode(str, Enum):
    """Termination and mismatch policies supported by :func:`zip_iter`."""

    SHORTEST = "shortest"
    STRICT = "strict"
    FIRST = "first"
    LONGEST = "longest"


def _parse_mode(mode: ZipMode | str) -> ZipMode:
    """Validate and normalize a mode."""
    try:
        return ZipMode(mode)
    except ValueError as error:
        choices = ", ".join(item.value for item in ZipMode)
        message = f"unsupported zip mode {mode!r}; expected one of: {choices}"
        raise ValueError(message) from error


def _parse_fillvalues(fillvalues: Iterable[Any] | None, iterable_count: int) -> tuple[Any, ...]:
    """Validate and normalize the per-input fill values."""
    if fillvalues is None:
        return (None,) * iterable_count

    parsed_fillvalues = tuple(fillvalues)
    if len(parsed_fillvalues) != iterable_count:
        message = f"expected {iterable_count} fill values, received {len(parsed_fillvalues)}"
        raise ValueError(message)
    return parsed_fillvalues


def _resolve_fillvalue(fillvalue: object) -> object:
    """Invoke a callable fill value or return a static value unchanged."""
    return fillvalue() if callable(fillvalue) else fillvalue
    if callable(fillvalue):
        return fillvalue()
    return fillvalue


def zip_iter(
    *iterables: Iterable[Any],
    mode: ZipMode | str = ZipMode.SHORTEST,
    fillvalues: Iterable[Any] | None = None,
) -> Iterator[tuple[Any, ...]]:
    """Lazily combine *iterables* according to a length-mismatch policy.

    Args:
        iterables: Any number of finite or infinite iterables.
        mode: ``shortest`` (Python), ``strict`` (equal lengths), ``first``
            (Ruby-like receiver length), or ``longest``.
        fillvalues: One missing-item value per input for ``first`` and
            ``longest``. A zero-argument callable is invoked for each missing
            position. Omitting this argument uses ``None`` for every input.

    Returns:
        A lazy, single-pass iterator of tuples.

    Raises:
        ValueError: If *mode* is unsupported, if the number of fill values does
            not match the inputs, or in ``strict`` mode when lengths differ.

    Iterator creation is deferred until the returned iterator is advanced.
    As with the built-in :func:`zip`, one extra value can be consumed from an
    earlier input while discovering that a later input is exhausted.

    """
    selected_mode = _parse_mode(mode)

    if selected_mode is ZipMode.SHORTEST:
        return _shortest(iterables)
    if selected_mode is ZipMode.STRICT:
        return _strict(iterables)
    parsed_fillvalues = _parse_fillvalues(fillvalues, len(iterables))
    if selected_mode is ZipMode.FIRST:
        return _first(iterables, parsed_fillvalues)
    return _longest(iterables, parsed_fillvalues)


def _shortest(iterables: tuple[Iterable[Any], ...]) -> Iterator[tuple[Any, ...]]:
    """Yield tuples until any input is exhausted."""
    yield from zip(*iterables, strict=False)


def _strict(iterables: tuple[Iterable[Any], ...]) -> Iterator[tuple[Any, ...]]:
    """Yield tuples while requiring equally sized inputs."""
    yield from zip(*iterables, strict=True)


def _first(
    iterables: tuple[Iterable[Any], ...],
    fillvalues: tuple[Any, ...],
) -> Iterator[tuple[Any, ...]]:
    """Yield as many tuples as the first input provides."""
    if not iterables:
        return

    first, *others = (iter(iterable) for iterable in iterables)
    missing = object()
    for first_value in first:
        values = [first_value]
        for index, other in enumerate(others, start=1):
            value = next(other, missing)
            values.append(_resolve_fillvalue(fillvalues[index]) if value is missing else value)
        yield tuple(values)


def _longest(
    iterables: tuple[Iterable[Any], ...],
    fillvalues: tuple[Any, ...],
) -> Iterator[tuple[Any, ...]]:
    """Yield tuples until every input is exhausted."""
    missing = object()
    for values in zip_longest(*iterables, fillvalue=missing):
        yield tuple(_resolve_fillvalue(fillvalues[index]) if value is missing else value for index, value in enumerate(values))
