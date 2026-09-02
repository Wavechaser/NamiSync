"""Adapter-local exception graph retirement."""

from __future__ import annotations

from traceback import clear_frames


_TRACEBACK_DESCRIPTOR = BaseException.__traceback__
_CAUSE_DESCRIPTOR = BaseException.__cause__
_CONTEXT_DESCRIPTOR = BaseException.__context__
_GROUP_EXCEPTIONS_DESCRIPTOR = BaseExceptionGroup.exceptions


def retire_exception_graph(error: BaseException) -> None:
    """Release private exception graphs without invoking subclass hooks."""

    pending = [error]
    retired: set[int] = set()
    while pending:
        current = pending.pop()
        identity = id(current)
        if identity in retired:
            continue
        retired.add(identity)
        if isinstance(current, BaseExceptionGroup):
            pending.extend(
                _GROUP_EXCEPTIONS_DESCRIPTOR.__get__(
                    current,
                    BaseExceptionGroup,
                )
            )
        raw_traceback = _TRACEBACK_DESCRIPTOR.__get__(current, BaseException)
        if raw_traceback is not None:
            clear_frames(raw_traceback)
        _TRACEBACK_DESCRIPTOR.__set__(current, None)
        _CAUSE_DESCRIPTOR.__set__(current, None)
        _CONTEXT_DESCRIPTOR.__set__(current, None)
