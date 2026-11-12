"""Exception graph lifecycle helpers."""

from __future__ import annotations

from traceback import clear_frames
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session import FailureDetail


_TRACEBACK_DESCRIPTOR = BaseException.__traceback__
_CAUSE_DESCRIPTOR = BaseException.__cause__
_CONTEXT_DESCRIPTOR = BaseException.__context__
_GROUP_EXCEPTIONS_DESCRIPTOR = BaseExceptionGroup.exceptions


def retire_exception_graph(error: BaseException) -> None:
    """Release lifecycle graphs without invoking subclass attribute hooks."""

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


def retired_failure_detail(
    error: BaseException,
    *,
    type_name: str | None = None,
) -> FailureDetail:
    """Project one live exception, then retire its lifecycle links."""

    try:
        from .pathing import logical_error_text
        from .session import FailureDetail

        return FailureDetail(
            type(error).__name__ if type_name is None else type_name,
            logical_error_text(error),
        )
    finally:
        retire_exception_graph(error)
