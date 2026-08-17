"""Desktop document-readiness state-machine tests."""

from __future__ import annotations

from threading import Event, Thread

import pytest

from namisync.interfaces.web.readiness import (
    CommandPhase,
    DesktopReadinessGate,
    DesktopStartupError,
    ReadinessContext,
)


def _readiness_gate() -> DesktopReadinessGate:
    return DesktopReadinessGate(lambda _seconds, _callback: lambda: None)


def test_readiness_gate_opens_once_after_all_three_readiness_signals() -> None:
    scheduled: list[tuple[float, object]] = []
    cancellations: list[str] = []
    publications: list[object] = []
    opens: list[str] = []
    refusals: list[Exception] = []

    def schedule(seconds: float, callback: object):
        scheduled.append((seconds, callback))
        return lambda: cancellations.append("cancel")

    gate = DesktopReadinessGate(schedule)
    gate.bind(
        request_publication=lambda _generation, callback: publications.append(
            callback
        ),
        open_desktop=lambda: opens.append("open") or True,
        refuse_desktop=refusals.append,
    )

    assert gate.command_context() == ReadinessContext(
        CommandPhase.BOOTSTRAP,
        0,
    )
    gate.acknowledge_shell(0)
    assert scheduled == []
    assert publications == []
    assert not gate.is_open()

    gate.native_loaded()
    gate.native_loaded()
    gate.acknowledge_shell(0)

    assert len(scheduled) == 1
    assert scheduled[0][0] == 5.0
    assert len(publications) == 1
    assert opens == []
    publications[0](None)

    assert gate.is_open()
    assert gate.command_context() == ReadinessContext(
        CommandPhase.OPEN,
        0,
    )
    assert opens == ["open"]
    assert cancellations == ["cancel"]
    assert refusals == []

    publications[0](RuntimeError("late publication failure"))
    scheduled[0][1]()
    assert gate.is_open()
    assert opens == ["open"]
    assert refusals == []


def test_readiness_gate_timeout_is_terminal_before_late_shell_ack() -> None:
    scheduled: list[tuple[float, object]] = []
    cancellations: list[str] = []
    publications: list[object] = []
    opens: list[str] = []
    refusals: list[Exception] = []

    def schedule(seconds: float, callback: object):
        scheduled.append((seconds, callback))
        return lambda: cancellations.append("cancel")

    gate = DesktopReadinessGate(schedule)
    gate.bind(
        request_publication=lambda _generation, callback: publications.append(
            callback
        ),
        open_desktop=lambda: opens.append("open") or True,
        refuse_desktop=refusals.append,
    )
    gate.native_loaded()

    scheduled[0][1]()
    gate.acknowledge_shell(0)

    assert not gate.is_open()
    assert gate.command_context() is None
    assert publications == []
    assert opens == []
    assert cancellations == ["cancel"]
    assert len(refusals) == 1
    assert isinstance(refusals[0], DesktopStartupError)
    assert "startup deadline" in str(refusals[0])


def test_readiness_gate_cancel_suppresses_late_ack_and_publication() -> None:
    scheduled: list[tuple[float, object]] = []
    cancellations: list[str] = []
    publications: list[object] = []
    opens: list[str] = []

    def schedule(seconds: float, callback: object):
        scheduled.append((seconds, callback))
        return lambda: cancellations.append("cancel")

    gate = DesktopReadinessGate(schedule)
    gate.bind(
        request_publication=lambda _generation, callback: publications.append(
            callback
        ),
        open_desktop=lambda: opens.append("open") or True,
        refuse_desktop=lambda _error: None,
    )
    gate.native_loaded()
    gate.cancel()
    gate.acknowledge_shell(0)
    gate.appearance_published(None)

    assert not gate.is_open()
    assert gate.command_context() is None
    assert publications == []
    assert opens == []
    assert cancellations == ["cancel"]


def test_cancel_after_open_callback_closes_admission_during_timer_cleanup() -> None:
    cancel_entered = Event()
    release_cancel = Event()
    publications: list[object] = []
    opens: list[str] = []

    def schedule(_seconds: float, _callback: object):
        def cancel() -> None:
            cancel_entered.set()
            assert release_cancel.wait(1.0)

        return cancel

    gate = DesktopReadinessGate(schedule)
    gate.bind(
        request_publication=lambda _generation, callback: publications.append(
            callback
        ),
        open_desktop=lambda: opens.append("open") or True,
        refuse_desktop=lambda _error: None,
    )
    gate.acknowledge_shell(0)
    gate.native_loaded()

    publisher = Thread(target=lambda: publications[0](None))
    publisher.start()
    assert cancel_entered.wait(1.0)
    gate.cancel()
    release_cancel.set()
    publisher.join(1.0)

    assert not publisher.is_alive()
    assert not gate.is_open()
    assert gate.command_context() is None
    assert opens == ["open"]


def test_readiness_gate_keeps_commands_closed_when_open_callback_declines() -> None:
    publications: list[object] = []
    gate = _readiness_gate()
    gate.bind(
        request_publication=lambda _generation, callback: publications.append(
            callback
        ),
        open_desktop=lambda: False,
        refuse_desktop=lambda _error: pytest.fail("open refusal was reported"),
    )
    gate.acknowledge_shell(0)
    gate.native_loaded()

    publications[0](None)

    assert not gate.is_open()
    assert gate.command_context() is None
    gate.acknowledge_shell(0)
    assert len(publications) == 1


def test_reload_starts_a_closed_generation_and_ignores_stale_callbacks() -> None:
    scheduled: list[tuple[float, object]] = []
    publications: list[object] = []
    publication_generations: list[int] = []
    opens: list[str] = []
    refusals: list[Exception] = []

    def schedule(seconds: float, callback: object):
        scheduled.append((seconds, callback))
        return lambda: None

    gate = DesktopReadinessGate(schedule)

    def request_publication(generation: int, callback: object) -> None:
        publication_generations.append(generation)
        publications.append(callback)

    gate.bind(
        request_publication=request_publication,
        open_desktop=lambda: opens.append("open") or True,
        refuse_desktop=refusals.append,
    )
    gate.acknowledge_shell(0)
    gate.native_loaded()
    first_publication = publications[0]
    first_deadline = scheduled[0][1]
    first_publication(None)
    assert gate.is_open()

    gate.begin_generation()

    assert not gate.is_open()
    assert gate.command_context() == ReadinessContext(
        CommandPhase.BOOTSTRAP,
        1,
    )
    assert len(scheduled) == 1
    gate.acknowledge_shell(0)
    gate.native_loaded()
    assert len(publications) == 1
    assert len(scheduled) == 2
    gate.acknowledge_shell(1)
    assert len(publications) == 2

    first_publication(RuntimeError("stale document publication"))
    first_deadline()
    assert not gate.is_open()
    assert refusals == []

    publications[1](None)

    assert gate.is_open()
    assert opens == ["open", "open"]
    assert refusals == []
    assert publication_generations == [0, 1]
