"""Exception graph lifecycle helpers."""

from __future__ import annotations

from traceback import clear_frames


_TRACEBACK_DESCRIPTOR = BaseException.__traceback__
_CAUSE_DESCRIPTOR = BaseException.__cause__
_CONTEXT_DESCRIPTOR = BaseException.__context__


def retire_exception_graph(error: BaseException) -> None:
    """Release traceback, cause, and context without subclass attribute hooks."""

    raw_traceback = _TRACEBACK_DESCRIPTOR.__get__(error, BaseException)
    if raw_traceback is not None:
        clear_frames(raw_traceback)
    _TRACEBACK_DESCRIPTOR.__set__(error, None)
    _CAUSE_DESCRIPTOR.__set__(error, None)
    _CONTEXT_DESCRIPTOR.__set__(error, None)
