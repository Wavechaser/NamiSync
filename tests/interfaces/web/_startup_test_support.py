"""Shared startup and command-composition drivers for headed test seams."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from threading import Thread
from types import MappingProxyType
from unittest.mock import patch


_CHALLENGE = re.compile(r"[0-9a-f]{32}")


class StartupHandshakeDocumentChannel:
    """Capture only the neutral readiness post for one fake document."""

    def __init__(self, window: object) -> None:
        self._messages: list[dict[str, object]] = []
        self._posted: list[dict[str, object]] = []
        setattr(window, "_startup_test_channel", self)

    @property
    def posts(self) -> tuple[dict[str, object], ...]:
        return tuple(dict(message) for message in self._posted)

    def post(
        self,
        payload: object,
        *,
        still_current: Callable[[], bool],
        completion: Callable[[Exception | None], None],
        **_ownership: object,
    ) -> None:
        if (
            type(payload) is not dict
            or set(payload) != {"kind", "challenge"}
            or payload.get("kind") != "namisync.readiness.v1"
            or type(payload.get("challenge")) is not str
            or _CHALLENGE.fullmatch(payload["challenge"]) is None
        ):
            raise AssertionError("startup posted a non-readiness document message")
        if not still_current():
            raise AssertionError("startup posted a stale readiness challenge")
        if self._posted:
            raise AssertionError("startup published more than one readiness challenge")
        message = dict(payload)
        self._messages.append(message)
        self._posted.append(message)
        completion(None)

    def take(self) -> dict[str, object]:
        if len(self._messages) != 1:
            raise AssertionError("startup must publish exactly one readiness challenge")
        return self._messages.pop()


def _exposed_dispatch(window: object) -> Callable[[str], object]:
    functions = getattr(window, "exposed_functions", None)
    if type(functions) not in {list, tuple} or len(functions) != 1:
        raise AssertionError("test window must expose exactly one bridge function")
    dispatch = functions[0]
    if not callable(dispatch):
        raise AssertionError("test window bridge function must be callable")
    return dispatch


def _dispatch(
    dispatch: Callable[[str], object],
    *,
    request_id: str,
    command: str,
    payload: Mapping[str, object],
) -> object:
    command_json = json.dumps(
        {
            "schema_version": 1,
            "request_id": request_id,
            "command": command,
            "payload": dict(payload),
        },
        separators=(",", ":"),
    )
    replies: list[object] = []
    errors: list[BaseException] = []

    def invoke() -> None:
        try:
            replies.append(dispatch(command_json))
        except BaseException as error:
            errors.append(error)

    worker = Thread(target=invoke, name="namisync-test-bridge", daemon=True)
    worker.start()
    worker.join(5.0)
    if worker.is_alive():
        raise AssertionError("test native bridge worker did not exit")
    if errors:
        raise errors[0]
    return replies[0]


def drive_startup_handshake(window: object) -> None:
    """Drive one fake host generation through the bilateral readiness join."""

    events = getattr(window, "events", None)
    before_load = getattr(events, "before_load", None)
    loaded = getattr(events, "loaded", None)
    if not callable(getattr(before_load, "emit", None)):
        raise AssertionError("test window must expose a before_load hook")
    if not callable(getattr(loaded, "emit", None)):
        raise AssertionError("test window must expose a loaded hook")
    before_load.emit()
    channel = getattr(window, "_startup_test_channel", None)
    if type(channel) is not StartupHandshakeDocumentChannel:
        raise AssertionError("startup did not bind the shared test document channel")

    gate = getattr(window, "startup_gate", None)
    if gate is not None:
        context = gate.command_context()
        generation = getattr(context, "generation", None)
        if type(generation) is not int:
            raise AssertionError("startup gate did not expose a bootstrap generation")
        gate.acknowledge_shell(generation)
        loaded.emit()
        challenge_message = channel.take()
        if not gate.acknowledge_echo(generation, challenge_message["challenge"]):
            raise AssertionError("startup gate refused its current readiness echo")
        if not gate.is_open():
            raise AssertionError("startup gate did not open after the complete handshake")
        return

    sequence = getattr(window, "_test_request_sequence", 0)
    if type(sequence) is not int or sequence < 0:
        raise AssertionError("test request sequence is invalid")
    shell_id = f"{sequence + 1:032x}"
    echo_id = f"{sequence + 2:032x}"
    setattr(window, "_test_request_sequence", sequence + 2)
    dispatch = _exposed_dispatch(window)

    shell = _dispatch(
        dispatch,
        request_id=shell_id,
        command="shell_ready",
        payload={},
    )
    assert shell == {
        "schema_version": 1,
        "request_id": shell_id,
        "ok": True,
        "result": {"acknowledged": True},
    }
    loaded.emit()
    challenge_message = channel.take()

    echo = _dispatch(
        dispatch,
        request_id=echo_id,
        command="readiness_echo",
        payload={"challenge": challenge_message["challenge"]},
    )
    assert echo == {
        "schema_version": 1,
        "request_id": echo_id,
        "ok": True,
        "result": {"acknowledged": True},
    }


ExtensionFactory = Callable[[object, object], Mapping[str, object]]
CompositionObserver = Callable[[Mapping[str, object], Mapping[str, object]], None]
DispatcherObserver = Callable[[object], None]


@contextmanager
def headed_command_extension(
    host: object,
    extension_factory: ExtensionFactory,
    *,
    observe_composition: CompositionObserver | None = None,
    observe_dispatcher: DispatcherObserver | None = None,
) -> Iterator[None]:
    """Patch one headed host with immutable, collision-refusing test commands."""

    original_commands = host._production_commands
    original_dispatcher = host._bridge_dispatcher
    captured: dict[str, object] = {}

    def commands(
        *,
        picker: object,
        slots: object,
        registry: object,
        cosmetics: object,
        startup_gate: object,
        **callbacks: object,
    ) -> Mapping[str, object]:
        production = original_commands(
            picker=picker,
            slots=slots,
            registry=registry,
            cosmetics=cosmetics,
            startup_gate=startup_gate,
            **callbacks,
        )
        captured.update(
            commands=production,
            registry=registry,
            startup_gate=startup_gate,
        )
        return production

    def dispatcher(
        document: object,
        commands: object,
        startup_gate: object,
    ) -> object:
        if commands is not captured.get("commands"):
            raise RuntimeError("headed command table changed before composition")
        if startup_gate is not captured.get("startup_gate"):
            raise RuntimeError("headed startup gate changed before composition")
        production = dict(commands)
        additions = dict(extension_factory(document, captured["registry"]))
        collisions = sorted(set(production).intersection(additions))
        if collisions:
            names = ", ".join(collisions)
            raise RuntimeError(f"test command collides with production: {names}")
        combined = MappingProxyType({**production, **additions})
        if observe_composition is not None:
            observe_composition(MappingProxyType(production), combined)
        value = original_dispatcher(document, combined, startup_gate)
        if observe_dispatcher is not None:
            observe_dispatcher(value)
        return value

    with (
        patch.object(host, "_production_commands", commands),
        patch.object(host, "_bridge_dispatcher", dispatcher),
    ):
        yield
