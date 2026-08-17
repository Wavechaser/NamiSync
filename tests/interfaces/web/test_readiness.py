"""Desktop bilateral document-readiness state-machine tests."""

from __future__ import annotations

from threading import Event, Lock, Thread

import pytest

from namisync.interfaces.web import readiness
from namisync.interfaces.web.readiness import (
    CommandPhase,
    DesktopReadinessGate,
    DesktopStartupError,
    ReadinessContext,
)


_CHALLENGE = "0123456789abcdef0123456789abcdef"


def _gate() -> DesktopReadinessGate:
    return DesktopReadinessGate(lambda _seconds, _callback: lambda: None)


def _bind(
    gate: DesktopReadinessGate,
    *,
    surfaces: list[object],
    posts: list[tuple[int, str, object]],
    opens: list[str],
    refusals: list[Exception],
) -> None:
    gate.bind(
        request_surface_settlement=surfaces.append,
        request_challenge_post=lambda generation, challenge, callback: posts.append(
            (generation, challenge, callback)
        ),
        open_desktop=lambda: opens.append("open") or True,
        refuse_desktop=refusals.append,
    )


def test_gate_opens_only_after_safe_surface_post_and_matching_echo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(readiness.secrets, "token_hex", lambda _bytes: _CHALLENGE)
    scheduled: list[tuple[float, object]] = []
    cancellations: list[str] = []
    surfaces: list[object] = []
    posts: list[tuple[int, str, object]] = []
    opens: list[str] = []
    refusals: list[Exception] = []

    def schedule(seconds: float, callback: object):
        scheduled.append((seconds, callback))
        return lambda: cancellations.append("cancel")

    gate = DesktopReadinessGate(schedule)
    _bind(
        gate,
        surfaces=surfaces,
        posts=posts,
        opens=opens,
        refusals=refusals,
    )

    assert gate.command_context() == ReadinessContext(CommandPhase.BOOTSTRAP, 0)
    gate.acknowledge_shell(0)
    assert surfaces == []
    gate.native_loaded()
    gate.native_loaded()
    gate.acknowledge_shell(0)

    assert len(scheduled) == 1
    assert scheduled[0][0] == 5.0
    assert len(surfaces) == 1
    surfaces[0](None)
    assert posts == [(0, _CHALLENGE, posts[0][2])]
    assert not gate.acknowledge_echo(0, "f" * 32)
    assert not gate.is_open()

    posts[0][2](None)
    assert not gate.is_open()
    assert gate.acknowledge_echo(0, _CHALLENGE)

    assert gate.is_open()
    assert gate.command_context() == ReadinessContext(CommandPhase.OPEN, 0)
    assert gate.acknowledge_echo(0, _CHALLENGE)
    assert opens == ["open"]
    assert cancellations == ["cancel"]
    assert refusals == []

    surfaces[0](RuntimeError("late"))
    posts[0][2](RuntimeError("late"))
    scheduled[0][1]()
    assert gate.is_open()
    assert opens == ["open"]


def test_echo_before_post_completion_is_remembered_and_replay_is_truthful(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(readiness.secrets, "token_hex", lambda _bytes: _CHALLENGE)
    surfaces: list[object] = []
    posts: list[tuple[int, str, object]] = []
    opens: list[str] = []
    gate = _gate()
    _bind(gate, surfaces=surfaces, posts=posts, opens=opens, refusals=[])
    gate.native_loaded()
    gate.acknowledge_shell(0)
    surfaces[0](None)

    assert gate.recognizes_echo(0, _CHALLENGE)
    assert not gate.acknowledge_echo(0, _CHALLENGE)
    assert opens == []
    posts[0][2](None)

    assert gate.is_open()
    assert gate.acknowledge_echo(0, _CHALLENGE)
    assert opens == ["open"]


@pytest.mark.parametrize("first", ["native", "shell"])
def test_native_and_shell_join_is_order_independent(first: str) -> None:
    surfaces: list[object] = []
    gate = _gate()
    _bind(gate, surfaces=surfaces, posts=[], opens=[], refusals=[])

    if first == "native":
        gate.native_loaded()
        assert surfaces == []
        gate.acknowledge_shell(0)
    else:
        gate.acknowledge_shell(0)
        assert surfaces == []
        gate.native_loaded()

    assert len(surfaces) == 1


def test_timeout_is_terminal_before_late_surface_or_echo() -> None:
    scheduled: list[tuple[float, object]] = []
    cancellations: list[str] = []
    surfaces: list[object] = []
    posts: list[tuple[int, str, object]] = []
    opens: list[str] = []
    refusals: list[Exception] = []

    def schedule(seconds: float, callback: object):
        scheduled.append((seconds, callback))
        return lambda: cancellations.append("cancel")

    gate = DesktopReadinessGate(schedule)
    _bind(
        gate,
        surfaces=surfaces,
        posts=posts,
        opens=opens,
        refusals=refusals,
    )
    gate.native_loaded()
    scheduled[0][1]()
    gate.acknowledge_shell(0)

    assert gate.command_context() is None
    assert surfaces == []
    assert posts == []
    assert opens == []
    assert cancellations == ["cancel"]
    assert len(refusals) == 1
    assert isinstance(refusals[0], DesktopStartupError)


def test_surface_or_post_failure_refuses_only_current_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(readiness.secrets, "token_hex", lambda _bytes: _CHALLENGE)
    for failure_at in ("surface", "post"):
        surfaces: list[object] = []
        posts: list[tuple[int, str, object]] = []
        refusals: list[Exception] = []
        gate = _gate()
        _bind(gate, surfaces=surfaces, posts=posts, opens=[], refusals=refusals)
        gate.native_loaded()
        gate.acknowledge_shell(0)
        error = RuntimeError(failure_at)
        if failure_at == "surface":
            surfaces[0](error)
        else:
            surfaces[0](None)
            posts[0][2](error)
        assert gate.command_context() is None
        assert refusals == [error] if failure_at == "surface" else len(refusals) == 1


def test_reload_revokes_challenge_and_suppresses_stale_callbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    challenges = iter((_CHALLENGE, "fedcba9876543210fedcba9876543210"))
    monkeypatch.setattr(readiness.secrets, "token_hex", lambda _bytes: next(challenges))
    scheduled: list[tuple[float, object]] = []
    surfaces: list[object] = []
    posts: list[tuple[int, str, object]] = []
    opens: list[str] = []
    refusals: list[Exception] = []
    gate = DesktopReadinessGate(
        lambda seconds, callback: scheduled.append((seconds, callback)) or (lambda: None)
    )
    _bind(
        gate,
        surfaces=surfaces,
        posts=posts,
        opens=opens,
        refusals=refusals,
    )
    gate.native_loaded()
    gate.acknowledge_shell(0)
    surfaces[0](None)
    stale_post = posts[0][2]
    stale_deadline = scheduled[0][1]

    gate.begin_generation()
    assert not gate.recognizes_echo(0, _CHALLENGE)
    assert not gate.acknowledge_echo(0, _CHALLENGE)
    stale_post(None)
    stale_deadline()
    assert refusals == []

    gate.native_loaded()
    gate.acknowledge_shell(1)
    surfaces[1](None)
    current = posts[1][1]
    posts[1][2](None)
    assert gate.acknowledge_echo(1, current)
    assert opens == ["open"]


def test_cancel_revokes_exact_echo_and_suppresses_late_callbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(readiness.secrets, "token_hex", lambda _bytes: _CHALLENGE)
    surfaces: list[object] = []
    posts: list[tuple[int, str, object]] = []
    opens: list[str] = []
    gate = _gate()
    _bind(gate, surfaces=surfaces, posts=posts, opens=opens, refusals=[])
    gate.native_loaded()
    gate.acknowledge_shell(0)
    surfaces[0](None)
    gate.cancel()

    posts[0][2](None)
    assert not gate.acknowledge_echo(0, _CHALLENGE)
    assert not gate.recognizes_echo(0, _CHALLENGE)
    assert opens == []


def test_open_callback_decline_keeps_admission_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(readiness.secrets, "token_hex", lambda _bytes: _CHALLENGE)
    surfaces: list[object] = []
    posts: list[tuple[int, str, object]] = []
    gate = _gate()
    gate.bind(
        request_surface_settlement=surfaces.append,
        request_challenge_post=lambda generation, challenge, callback: posts.append(
            (generation, challenge, callback)
        ),
        open_desktop=lambda: False,
        refuse_desktop=lambda _error: pytest.fail("declined open was reported"),
    )
    gate.native_loaded()
    gate.acknowledge_shell(0)
    surfaces[0](None)
    posts[0][2](None)

    assert not gate.acknowledge_echo(0, _CHALLENGE)
    assert gate.command_context() is None


def test_callbacks_are_reentrant_and_never_run_under_gate_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(readiness.secrets, "token_hex", lambda _bytes: _CHALLENGE)
    observed: list[object] = []
    gate = _gate()

    def request_surface(callback: object) -> None:
        observed.append(gate.command_context())
        callback(None)

    def request_post(_generation: int, _challenge: str, callback: object) -> None:
        observed.append(gate.command_context())
        callback(None)

    def open_desktop() -> bool:
        observed.append(gate.command_context())
        return True

    gate.bind(
        request_surface_settlement=request_surface,
        request_challenge_post=request_post,
        open_desktop=open_desktop,
        refuse_desktop=lambda _error: observed.append(gate.command_context()),
    )
    gate.native_loaded()
    gate.acknowledge_shell(0)
    assert gate.acknowledge_echo(0, _CHALLENGE)
    assert len(observed) == 3


def test_concurrent_exact_echo_opens_at_most_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(readiness.secrets, "token_hex", lambda _bytes: _CHALLENGE)
    surfaces: list[object] = []
    posts: list[tuple[int, str, object]] = []
    entered = Event()
    release = Event()
    opens: list[str] = []
    opens_lock = Lock()

    def open_desktop() -> bool:
        with opens_lock:
            opens.append("open")
        entered.set()
        assert release.wait(1.0)
        return True

    gate = _gate()
    gate.bind(
        request_surface_settlement=surfaces.append,
        request_challenge_post=lambda generation, challenge, callback: posts.append(
            (generation, challenge, callback)
        ),
        open_desktop=open_desktop,
        refuse_desktop=lambda _error: None,
    )
    gate.native_loaded()
    gate.acknowledge_shell(0)
    surfaces[0](None)
    posts[0][2](None)

    results: list[bool] = []
    first = Thread(target=lambda: results.append(gate.acknowledge_echo(0, _CHALLENGE)))
    first.start()
    assert entered.wait(1.0)
    second = Thread(target=lambda: results.append(gate.acknowledge_echo(0, _CHALLENGE)))
    second.start()
    second.join(1.0)
    release.set()
    first.join(1.0)

    assert not first.is_alive()
    assert not second.is_alive()
    assert opens == ["open"]
    assert sorted(results) == [False, True]
