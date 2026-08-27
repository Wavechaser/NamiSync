"""Focused contract tests for bounded host-to-document messages."""

from __future__ import annotations

import gc
import json
import weakref
from pathlib import Path
from types import SimpleNamespace

import pytest

from namisync.interfaces.ui_state import MAX_JAVASCRIPT_SAFE_INTEGER
from namisync.interfaces.web.document_channel import (
    DocumentChannel,
    DocumentChannelBusyError,
    DocumentMessageTooLargeError,
    DocumentPostKind,
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


@pytest.mark.parametrize("retire", ("replace", "close"))
def test_channel_retirement_after_queue_prevents_ordinary_sink(retire: str) -> None:
    native_window, core = _native_window()
    queued: list[object] = []
    completions: list[Exception | None] = []
    channel = DocumentChannel(
        native_window,
        invoke=lambda _owner, callback: queued.append(callback),
    )
    channel.post(
        {"kind": "ordinary"},
        still_current=lambda: True,
        completion=completions.append,
    )

    getattr(channel, "replace_document" if retire == "replace" else "close")()
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


def test_ordinary_channel_keeps_independent_queued_posts() -> None:
    native_window, core = _native_window()
    queued: list[object] = []
    completions: list[Exception | None] = []
    channel = DocumentChannel(
        native_window,
        invoke=lambda _owner, callback: queued.append(callback),
    )

    for value in (1, 2):
        channel.post(
            {"value": value},
            still_current=lambda: True,
            completion=completions.append,
        )
    queued.pop()()
    queued.pop()()

    assert [json.loads(value) for value in core.encoded] == [
        {"value": 2},
        {"value": 1},
    ]
    assert completions == [None, None]


def test_acknowledged_channel_retains_required_post_until_exact_echo() -> None:
    native_window, core = _native_window()
    completions: list[Exception | None] = []
    channel = DocumentChannel(native_window, require_acknowledgment=True)

    channel.post(
        {"kind": "readiness", "challenge": "a" * 32},
        still_current=lambda: True,
        completion=completions.append,
        kind=DocumentPostKind.REQUIRED,
        acknowledgment=(7, "a" * 32),
    )

    assert len(core.encoded) == 1
    assert completions == []
    assert not channel.acknowledge(
        DocumentPostKind.REQUIRED,
        (6, "a" * 32),
    )
    assert completions == []
    assert channel.acknowledge(
        DocumentPostKind.REQUIRED,
        (7, "a" * 32),
    )
    assert completions == [None]


def test_sent_post_releases_pre_send_owners_before_acknowledgment() -> None:
    native_window, _core = _native_window()
    channel = DocumentChannel(native_window, require_acknowledgment=True)

    class Marker:
        pass

    current_marker = Marker()
    completion_marker = Marker()
    current_reference = weakref.ref(current_marker)
    completion_reference = weakref.ref(completion_marker)

    def still_current(owner: Marker = current_marker) -> bool:
        del owner
        return True

    completions: list[Exception | None] = []

    def complete(
        error: Exception | None,
        owner: Marker = completion_marker,
    ) -> None:
        del owner
        completions.append(error)

    channel.post(
        {"kind": "readiness"},
        still_current=still_current,
        completion=complete,
        acknowledgment=(7, "a" * 32),
    )
    del current_marker, completion_marker, still_current, complete
    gc.collect()

    assert current_reference() is None
    assert completion_reference() is not None
    assert completions == []
    assert channel.acknowledge(
        DocumentPostKind.REQUIRED,
        (7, "a" * 32),
    )
    gc.collect()
    assert completion_reference() is None
    assert completions == [None]


def test_appearance_acknowledgment_uses_the_complete_safe_integer_domain() -> None:
    native_window, _core = _native_window()
    completions: list[Exception | None] = []
    channel = DocumentChannel(native_window, require_acknowledgment=True)

    channel.post(
        {"kind": "appearance", "revision": MAX_JAVASCRIPT_SAFE_INTEGER},
        still_current=lambda: True,
        completion=completions.append,
        kind=DocumentPostKind.REPLACEABLE,
        acknowledgment=MAX_JAVASCRIPT_SAFE_INTEGER,
    )

    assert channel.acknowledge(
        DocumentPostKind.REPLACEABLE,
        MAX_JAVASCRIPT_SAFE_INTEGER,
    )
    assert completions == [None]
    with pytest.raises(ValueError, match="token is invalid"):
        channel.post(
            {"kind": "appearance"},
            still_current=lambda: True,
            completion=completions.append,
            kind=DocumentPostKind.REPLACEABLE,
            acknowledgment=MAX_JAVASCRIPT_SAFE_INTEGER + 1,
        )


@pytest.mark.parametrize(
    ("kind", "acknowledgment"),
    [
        (DocumentPostKind.REQUIRED, 1),
        (DocumentPostKind.REQUIRED, (1, "A" * 32)),
        (DocumentPostKind.REQUIRED, (1, "a" * 31)),
        (DocumentPostKind.REPLACEABLE, (1, "a" * 32)),
    ],
)
def test_acknowledgment_kind_accepts_only_its_live_identity_shape(
    kind: DocumentPostKind,
    acknowledgment: object,
) -> None:
    native_window, _core = _native_window()
    channel = DocumentChannel(native_window, require_acknowledgment=True)

    with pytest.raises(ValueError, match="token is invalid"):
        channel.post(
            {"kind": kind.value},
            still_current=lambda: True,
            completion=lambda _error: None,
            kind=kind,
            acknowledgment=acknowledgment,
        )


def test_required_post_is_never_replaced_by_appearance_coalescing() -> None:
    native_window, core = _native_window()
    queued: list[object] = []
    outcomes: dict[str, list[Exception | None]] = {
        "readiness": [],
        "first": [],
        "latest": [],
        "second_readiness": [],
    }
    channel = DocumentChannel(
        native_window,
        invoke=lambda _owner, callback: queued.append(callback),
        require_acknowledgment=True,
    )
    channel.post(
        {"kind": "readiness"},
        still_current=lambda: True,
        completion=outcomes["readiness"].append,
        acknowledgment=(1, "a" * 32),
    )
    channel.post(
        {"kind": "appearance", "revision": 1},
        still_current=lambda: True,
        completion=outcomes["first"].append,
        kind=DocumentPostKind.REPLACEABLE,
        acknowledgment=1,
    )
    channel.post(
        {"kind": "appearance", "revision": 2},
        still_current=lambda: True,
        completion=outcomes["latest"].append,
        kind=DocumentPostKind.REPLACEABLE,
        acknowledgment=2,
    )
    channel.post(
        {"kind": "readiness", "challenge": "b"},
        still_current=lambda: True,
        completion=outcomes["second_readiness"].append,
        acknowledgment=(2, "b" * 32),
    )

    assert len(queued) == 1
    assert len(outcomes["first"]) == 1
    assert isinstance(outcomes["first"][0], DocumentStaleError)
    assert len(outcomes["second_readiness"]) == 1
    assert isinstance(
        outcomes["second_readiness"][0],
        DocumentChannelBusyError,
    )
    queued[0]()
    assert [json.loads(value)["kind"] for value in core.encoded] == ["readiness"]
    assert outcomes["readiness"] == []
    assert channel.acknowledge(DocumentPostKind.REQUIRED, (1, "a" * 32))
    assert len(queued) == 2
    queued[1]()
    assert [json.loads(value) for value in core.encoded] == [
        {"kind": "readiness"},
        {"kind": "appearance", "revision": 2},
    ]
    assert outcomes["readiness"] == [None]
    assert outcomes["latest"] == []
    assert channel.acknowledge(DocumentPostKind.REPLACEABLE, 2)
    assert outcomes["latest"] == [None]


def test_document_replacement_retires_sent_and_queued_ownership() -> None:
    native_window, core = _native_window()
    queued: list[object] = []
    required: list[Exception | None] = []
    replaceable: list[Exception | None] = []
    channel = DocumentChannel(
        native_window,
        invoke=lambda _owner, callback: queued.append(callback),
        require_acknowledgment=True,
    )
    channel.post(
        {"kind": "readiness"},
        still_current=lambda: True,
        completion=required.append,
        acknowledgment=(1, "a" * 32),
    )
    channel.post(
        {"kind": "appearance"},
        still_current=lambda: True,
        completion=replaceable.append,
        kind=DocumentPostKind.REPLACEABLE,
        acknowledgment=1,
    )

    channel.replace_document()
    queued[0]()

    assert core.encoded == []
    assert len(required) == len(replaceable) == 1
    assert isinstance(required[0], DocumentStaleError)
    assert isinstance(replaceable[0], DocumentStaleError)


@pytest.mark.parametrize("retire", ("replace", "close"))
def test_hostile_currency_predicate_cannot_post_after_retirement(retire: str) -> None:
    native_window, core = _native_window()
    queued: list[object] = []
    completions: list[Exception | None] = []
    channel = DocumentChannel(
        native_window,
        invoke=lambda _owner, callback: queued.append(callback),
        require_acknowledgment=True,
    )

    def retire_then_claim_current() -> bool:
        getattr(
            channel,
            "replace_document" if retire == "replace" else "close",
        )()
        return True

    channel.post(
        {"kind": "hostile"},
        still_current=retire_then_claim_current,
        completion=completions.append,
        acknowledgment=(1, "a" * 32),
    )
    queued[0]()

    assert core.encoded == []
    assert len(completions) == 1
    assert isinstance(completions[0], DocumentStaleError)


def test_document_epoch_is_captured_before_payload_construction() -> None:
    native_window, core = _native_window()
    queued: list[object] = []
    completions: list[Exception | None] = []
    channel = DocumentChannel(
        native_window,
        invoke=lambda _owner, callback: queued.append(callback),
        require_acknowledgment=True,
    )

    class ReplacingPayload(dict[str, object]):
        def items(self):
            channel.replace_document()
            return super().items()

    channel.post(
        ReplacingPayload(kind="constructed-during-reload"),
        still_current=lambda: True,
        completion=completions.append,
        acknowledgment=(1, "a" * 32),
    )

    assert queued == []
    assert core.encoded == []
    assert len(completions) == 1
    assert isinstance(completions[0], DocumentStaleError)


def test_repeated_replacement_keeps_one_queued_native_dispatch_owner() -> None:
    native_window, core = _native_window()
    queued: list[object] = []
    completions: list[tuple[int, Exception | None]] = []
    channel = DocumentChannel(
        native_window,
        invoke=lambda _owner, callback: queued.append(callback),
        require_acknowledgment=True,
    )

    for generation in range(8):
        if generation:
            channel.replace_document()
        channel.post(
            {"generation": generation},
            still_current=lambda: True,
            completion=lambda error, generation=generation: completions.append(
                (generation, error)
            ),
            acknowledgment=(generation, "a" * 32),
        )
        assert len(queued) == 1

    queued[0]()

    assert [json.loads(value) for value in core.encoded] == [{"generation": 7}]
    assert [generation for generation, _error in completions] == list(range(7))
    assert all(isinstance(error, DocumentStaleError) for _, error in completions)
    assert channel.acknowledge(DocumentPostKind.REQUIRED, (7, "a" * 32))
    assert completions[-1] == (7, None)


def test_consumed_sink_failure_releases_its_traceback_frame() -> None:
    native_window, core = _native_window()
    retained: list[weakref.ReferenceType[object]] = []
    completions: list[Exception | None] = []

    class Marker:
        pass

    def refuse(_value: str) -> None:
        marker = Marker()
        retained.append(weakref.ref(marker))
        raise RuntimeError("injected sink failure")

    core.PostWebMessageAsJson = refuse
    DocumentChannel(native_window).post(
        {"kind": "test"},
        still_current=lambda: True,
        completion=completions.append,
    )
    gc.collect()

    assert len(completions) == 1
    assert isinstance(completions[0], RuntimeError)
    assert retained[0]() is None


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
