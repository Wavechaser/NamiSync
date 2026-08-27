from __future__ import annotations

import gc
from weakref import ref

from namisync.core.exception_graph import retire_exception_graph


_TRACEBACK_DESCRIPTOR = BaseException.__traceback__
_CAUSE_DESCRIPTOR = BaseException.__cause__
_CONTEXT_DESCRIPTOR = BaseException.__context__


class _Retained:
    pass


class _HostileLifecycleDescriptor:
    def __init__(self, name: str) -> None:
        self._name = name

    def __get__(self, instance, owner):
        raise AssertionError(f"subclass {self._name} getter was invoked")

    def __set__(self, instance, value) -> None:
        raise AssertionError(f"subclass {self._name} setter was invoked")


class _HostileLifecycleError(RuntimeError):
    __traceback__ = _HostileLifecycleDescriptor("traceback")
    __cause__ = _HostileLifecycleDescriptor("cause")
    __context__ = _HostileLifecycleDescriptor("context")


class _HostileExceptionGroup(ExceptionGroup):
    __traceback__ = _HostileLifecycleDescriptor("traceback")
    __cause__ = _HostileLifecycleDescriptor("cause")
    __context__ = _HostileLifecycleDescriptor("context")
    exceptions = _HostileLifecycleDescriptor("exceptions")


def _captured_hostile_error() -> tuple[_HostileLifecycleError, ref[_Retained]]:
    retained = _Retained()
    retained_ref = ref(retained)
    try:
        raise ValueError("cause")
    except ValueError as cause:
        try:
            raise _HostileLifecycleError("failure") from cause
        except _HostileLifecycleError as error:
            return error, retained_ref


def test_retire_exception_graph_bypasses_hostile_lifecycle_descriptors() -> None:
    error, retained_ref = _captured_hostile_error()

    retire_exception_graph(error)
    gc.collect()

    assert _TRACEBACK_DESCRIPTOR.__get__(error, BaseException) is None
    assert _CAUSE_DESCRIPTOR.__get__(error, BaseException) is None
    assert _CONTEXT_DESCRIPTOR.__get__(error, BaseException) is None
    assert retained_ref() is None


def test_retire_exception_graph_retires_shared_nested_group_members() -> None:
    error, retained_ref = _captured_hostile_error()
    inner = _HostileExceptionGroup("inner", (error, error))
    fatal = KeyboardInterrupt("stop")
    root = BaseExceptionGroup(
        "root",
        (inner, fatal, inner),
    )
    retire_exception_graph(root)
    gc.collect()

    assert BaseExceptionGroup.exceptions.__get__(root, BaseExceptionGroup) == (
        inner,
        fatal,
        inner,
    )
    assert BaseExceptionGroup.exceptions.__get__(inner, BaseExceptionGroup) == (
        error,
        error,
    )
    for retired in (root, inner, error):
        assert _TRACEBACK_DESCRIPTOR.__get__(retired, BaseException) is None
        assert _CAUSE_DESCRIPTOR.__get__(retired, BaseException) is None
        assert _CONTEXT_DESCRIPTOR.__get__(retired, BaseException) is None
    assert retained_ref() is None
