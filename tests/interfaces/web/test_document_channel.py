"""Focused contract tests for bounded host-to-document messages."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from namisync.interfaces.web.document_channel import (
    DocumentChannel,
    DocumentMessageTooLargeError,
    DocumentStaleError,
)


class _Core:
    def __init__(self) -> None:
        self.encoded: list[str] = []

    def PostWebMessageAsJson(self, value: str) -> None:
        self.encoded.append(value)


def _native_window() -> tuple[SimpleNamespace, _Core]:
    core = _Core()
    return (
        SimpleNamespace(
            InvokeRequired=False,
            browser=SimpleNamespace(
                webview=SimpleNamespace(CoreWebView2=core),
            ),
        ),
        core,
    )


def test_document_message_is_canonical_ascii_and_posted_on_ui_dispatch() -> None:
    native_window, core = _native_window()
    dispatched: list[object] = []
    completions: list[Exception | None] = []

    def invoke(owner: object, callback: object) -> None:
        dispatched.append(owner)
        callback()

    DocumentChannel(native_window, invoke=invoke).post(
        {"z": "雪", "a": 1},
        still_current=lambda: True,
        completion=completions.append,
    )

    assert dispatched == [native_window]
    assert core.encoded == ['{"a":1,"z":"\\u96ea"}']
    assert completions == [None]


def test_payload_is_frozen_before_queued_document_post() -> None:
    native_window, core = _native_window()
    queued: list[object] = []
    payload = {"value": "before"}
    completions: list[Exception | None] = []

    DocumentChannel(
        native_window,
        invoke=lambda _owner, callback: queued.append(callback),
    ).post(
        payload,
        still_current=lambda: True,
        completion=completions.append,
    )
    payload["value"] = "after"
    queued[0]()

    assert json.loads(core.encoded[0]) == {"value": "before"}
    assert completions == [None]


def test_currency_is_rechecked_inside_queued_ui_callback_before_sink() -> None:
    native_window, core = _native_window()
    queued: list[object] = []
    current = True
    completions: list[Exception | None] = []

    DocumentChannel(
        native_window,
        invoke=lambda _owner, callback: queued.append(callback),
    ).post(
        {"kind": "test"},
        still_current=lambda: current,
        completion=completions.append,
    )
    current = False
    queued[0]()

    assert core.encoded == []
    assert len(completions) == 1
    assert isinstance(completions[0], DocumentStaleError)


def test_document_channel_accepts_exact_byte_ceiling_and_refuses_one_more() -> None:
    native_window, core = _native_window()
    base = len('{"value":""}'.encode("utf-8"))
    at_limit = {"value": "x" * (65_536 - base)}
    over_limit = {"value": "x" * (65_537 - base)}
    completions: list[Exception | None] = []
    channel = DocumentChannel(native_window)

    channel.post(
        at_limit,
        still_current=lambda: True,
        completion=completions.append,
    )
    channel.post(
        over_limit,
        still_current=lambda: True,
        completion=completions.append,
    )

    assert len(core.encoded[0].encode("utf-8")) == 65_536
    assert completions[0] is None
    assert isinstance(completions[1], DocumentMessageTooLargeError)
    assert len(core.encoded) == 1


@pytest.mark.parametrize(
    ("payload", "error_type"),
    (({"value": float("nan")}, ValueError), ({"value": object()}, TypeError)),
)
def test_invalid_json_is_reported_without_ui_dispatch(
    payload: object,
    error_type: type[Exception],
) -> None:
    native_window, core = _native_window()
    dispatched: list[object] = []
    completions: list[Exception | None] = []

    DocumentChannel(
        native_window,
        invoke=lambda _owner, callback: dispatched.append(callback),
    ).post(
        payload,
        still_current=lambda: True,
        completion=completions.append,
    )

    assert core.encoded == []
    assert dispatched == []
    assert len(completions) == 1
    assert isinstance(completions[0], error_type)


def test_completion_is_exactly_once_when_dispatch_runs_then_raises() -> None:
    native_window, core = _native_window()
    completions: list[Exception | None] = []

    def invoke(_owner: object, callback: object) -> None:
        callback()
        raise RuntimeError("injected post-dispatch failure")

    DocumentChannel(native_window, invoke=invoke).post(
        {"kind": "test"},
        still_current=lambda: True,
        completion=completions.append,
    )

    assert len(core.encoded) == 1
    assert completions == [None]


def test_sink_failure_reports_only_exception_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    native_window, core = _native_window()
    secret = "document-channel-secret"
    completions: list[Exception | None] = []

    def refuse(value: str) -> None:
        assert secret in value
        raise RuntimeError(secret)

    core.PostWebMessageAsJson = refuse
    DocumentChannel(native_window).post(
        {"value": secret},
        still_current=lambda: True,
        completion=completions.append,
    )

    assert len(completions) == 1
    assert isinstance(completions[0], RuntimeError)
    assert secret not in caplog.text


def test_document_channel_is_the_only_production_web_message_sink() -> None:
    web_root = Path(__file__).parents[3] / "namisync" / "interfaces" / "web"
    owners = {
        path.name
        for path in web_root.glob("*.py")
        if "PostWebMessageAsJson" in path.read_text(encoding="utf-8")
    }

    assert owners == {"document_channel.py"}
    source = (web_root / "document_channel.py").read_text(encoding="utf-8")
    assert "evaluate_js" not in source
    assert "run_js" not in source
