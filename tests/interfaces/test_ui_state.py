from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Callable

import pytest

import namisync.interfaces.ui_state as ui_state_module
from namisync.interfaces.ui_state import (
    AppearanceValue,
    CosmeticDisposition,
    CosmeticReplaceResult,
    CosmeticSectionSnapshot,
    ThemeMode,
    UiStateOwner,
)


_MAX_DOCUMENT_BYTES = 1024 * 1024
_APPEARANCE = "appearance"
_VALUE_VERSION = 1


def _read(owner: UiStateOwner) -> CosmeticSectionSnapshot:
    return owner.read_section(_APPEARANCE, _VALUE_VERSION)


def _replace(
    owner: UiStateOwner,
    *,
    expected_revision: int,
    theme: str,
) -> CosmeticReplaceResult:
    return owner.replace_section(
        _APPEARANCE,
        _VALUE_VERSION,
        expected_revision,
        AppearanceValue(ThemeMode(theme)),
    )


def _wait_until(predicate: Callable[[], bool], *, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    assert predicate()


def _document(theme: str = "system") -> dict[str, object]:
    return {
        "schema_version": 1,
        "sections": {
            "appearance": {
                "value_version": 1,
                "value": {"theme": theme},
            }
        },
    }


def _write_document(path: Path, value: object) -> bytes:
    payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
    path.write_bytes(payload)
    return payload


def test_br_g_46_missing_ui_state_is_clean_default_and_creates_no_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ui-state.json"
    owner = UiStateOwner(path)

    try:
        snapshot = _read(owner)

        assert snapshot == CosmeticSectionSnapshot(
            section="appearance",
            value_version=1,
            revision=0,
            dirty=False,
            value=AppearanceValue(ThemeMode.SYSTEM),
        )
        assert not path.exists()
    finally:
        owner.close()

    assert not path.exists()


def test_br_g_46_ui_state_round_trips_the_exact_v1_typed_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 0.01)
    path = tmp_path / "ui-state.json"
    owner = UiStateOwner(path)

    try:
        result = _replace(owner, expected_revision=0, theme="light")
        assert result.disposition is CosmeticDisposition.APPLIED
        assert result.revision == 1
        assert result.dirty is True
        _wait_until(lambda: path.exists() and not _read(owner).dirty)
    finally:
        owner.close()

    assert json.loads(path.read_text(encoding="utf-8")) == _document("light")
    assert not tuple(tmp_path.glob(".ui-state.json.*.tmp"))

    reopened = UiStateOwner(path)
    try:
        assert _read(reopened) == CosmeticSectionSnapshot(
            section="appearance",
            value_version=1,
            revision=0,
            dirty=False,
            value=AppearanceValue(ThemeMode.LIGHT),
        )
    finally:
        reopened.close()


def test_br_g_46_canonical_write_bound_prevents_atomic_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    path = tmp_path / "ui-state.json"
    original = _write_document(path, _document())
    owner = UiStateOwner(path)
    atomic_writes: list[bytes] = []
    monkeypatch.setattr(ui_state_module, "UI_STATE_MAX_BYTES", 1)
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 60.0)
    monkeypatch.setattr(
        ui_state_module,
        "_atomic_write",
        lambda _path, payload: atomic_writes.append(payload),
    )

    with caplog.at_level(logging.WARNING, logger="namisync.interfaces.ui_state"):
        result = _replace(owner, expected_revision=0, theme="light")
        assert result.disposition is CosmeticDisposition.APPLIED
        assert result.dirty is True
        owner.close()

    assert atomic_writes == []
    assert path.read_bytes() == original
    messages = [record.getMessage() for record in caplog.records]
    assert messages.count(
        "ui_state.save_failed exception_type=UiStateFormatError"
    ) == 1
    assert all(record.exc_info is None for record in caplog.records)


def test_br_g_46_failed_atomic_replace_preserves_old_file_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 0.01)
    path = tmp_path / "ui-state.json"
    original = _write_document(path, _document())
    owner = UiStateOwner(path)
    attempted = threading.Event()
    calls = 0
    secret = str(path)

    def fail_replace(_source: object, _target: object) -> None:
        nonlocal calls
        calls += 1
        attempted.set()
        raise OSError(f"replace failed for secret path {secret}")

    monkeypatch.setattr(ui_state_module.os, "replace", fail_replace)

    with caplog.at_level(logging.WARNING, logger="namisync.interfaces.ui_state"):
        result = _replace(owner, expected_revision=0, theme="dark")
        assert result.disposition is CosmeticDisposition.APPLIED
        assert attempted.wait(1)
        owner.close()

    assert calls == 1
    assert path.read_bytes() == original
    assert not tuple(tmp_path.glob(".ui-state.json.*.tmp"))
    messages = [record.getMessage() for record in caplog.records]
    assert messages.count("ui_state.save_failed exception_type=OSError") == 1
    assert secret not in "\n".join(messages)
    assert "replace failed" not in "\n".join(messages)
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.parametrize("theme", [True, 1, "", "auto", "LIGHT"])
def test_br_g_46_theme_mode_is_typed_and_exact(theme: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        ThemeMode(theme)  # type: ignore[arg-type]


def test_br_g_46_public_section_and_revision_validation_is_exact(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ui-state.json"
    owner = UiStateOwner(path)

    try:
        for section, value_version in (
            ("other", 1),
            (_APPEARANCE, True),
            (_APPEARANCE, 1.0),
            (_APPEARANCE, 2),
        ):
            with pytest.raises(ValueError):
                owner.read_section(section, value_version)  # type: ignore[arg-type]

        for revision in (
            -1,
            True,
            1.0,
            ui_state_module.MAX_JAVASCRIPT_SAFE_INTEGER + 1,
        ):
            with pytest.raises(ValueError):
                owner.replace_section(
                    _APPEARANCE,
                    _VALUE_VERSION,
                    revision,  # type: ignore[arg-type]
                    AppearanceValue(ThemeMode.LIGHT),
                )

        assert _read(owner) == CosmeticSectionSnapshot(
            section="appearance",
            value_version=1,
            revision=0,
            dirty=False,
            value=AppearanceValue(ThemeMode.SYSTEM),
        )
    finally:
        owner.close()

    assert not path.exists()


def test_br_g_46_revision_exhaustion_refuses_mutation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ui-state.json"
    owner = UiStateOwner(path)
    with owner._condition:
        owner._appearance_revision = ui_state_module.MAX_JAVASCRIPT_SAFE_INTEGER

    try:
        with pytest.raises(OverflowError, match="revision is exhausted"):
            _replace(
                owner,
                expected_revision=ui_state_module.MAX_JAVASCRIPT_SAFE_INTEGER,
                theme="dark",
            )
        snapshot = _read(owner)
        assert snapshot.revision == ui_state_module.MAX_JAVASCRIPT_SAFE_INTEGER
        assert snapshot.dirty is False
        assert snapshot.value == AppearanceValue(ThemeMode.SYSTEM)
    finally:
        owner.close()

    assert not path.exists()


def test_br_g_46_read_bound_accepts_limit_and_rejects_limit_plus_one(
    tmp_path: Path,
) -> None:
    encoded = json.dumps(_document(), separators=(",", ":")).encode("utf-8")
    at_limit = encoded + b" " * (_MAX_DOCUMENT_BYTES - len(encoded))
    over_limit = at_limit + b" "
    path = tmp_path / "ui-state.json"

    path.write_bytes(at_limit)
    accepted = UiStateOwner(path)
    try:
        assert _read(accepted).dirty is False
        assert _read(accepted).value == AppearanceValue(ThemeMode.SYSTEM)
    finally:
        accepted.close()

    path.write_bytes(over_limit)
    rejected = UiStateOwner(path)
    try:
        assert _read(rejected).dirty is True
        assert _read(rejected).value == AppearanceValue(ThemeMode.SYSTEM)
        assert path.read_bytes() == over_limit
    finally:
        rejected.close()


@pytest.mark.parametrize(
    "payload",
    [
        b'{"schema_version":1,"schema_version":1,"sections":{}}',
        b'{"schema_version":1,"sections":{"appearance":'
        b'{"value_version":1,"value":{"theme":"system","theme":"dark"}}}}',
        b'{"schema_version":true,"sections":{"appearance":'
        b'{"value_version":1,"value":{"theme":"system"}}}}',
        b'{"schema_version":1,"sections":{"appearance":'
        b'{"value_version":1,"value":{"theme":NaN}}}}',
        b'{"schema_version":1,"sections":{"appearance":'
        b'{"value_version":1,"value":{"theme":"system","extra":null}}}}',
        b'{"schema_version":1,"sections":{"appearance":'
        b'{"value_version":true,"value":{"theme":"system"}}}}',
        b'{"schema_version":1,"sections":{"appearance":'
        b'{"value_version":1.0,"value":{"theme":"system"}}}}',
        b'{"schema_version":1,"sections":{"appearance":'
        b'{"value_version":1,"value":{"theme":"auto"}}}}',
        b'{"schema_version":1,"sections":{"appearance":'
        b'{"value_version":1,"value":{"theme":1}}}}',
        b'{"schema_version":1,"sections":{"appearance":'
        b'{"value_version":1,"value":{"theme":"system"}},"other":{}}}',
        b'{"schema_version":1,"sections":[],"extra":null}',
        b'{"schema_version":1,"sections":{"appearance":'
        b'{"value_version":1}}}',
        b'{"schema_version":1,"sections":{}}',
        b'not-json',
        b'\xff',
    ],
)
def test_br_g_46_invalid_current_documents_fall_back_without_load_mutation(
    tmp_path: Path,
    payload: bytes,
) -> None:
    path = tmp_path / "ui-state.json"
    path.write_bytes(payload)
    owner = UiStateOwner(path)

    try:
        snapshot = _read(owner)
        assert snapshot.revision == 0
        assert snapshot.dirty is True
        assert snapshot.value == AppearanceValue(ThemeMode.SYSTEM)
        assert path.read_bytes() == payload
    finally:
        owner.close()


def test_br_g_46_excessively_deep_json_falls_back_without_escaping_load(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ui-state.json"
    opening = b'[{"nested":' * 1200
    closing = b"}]" * 1200
    payload = b'{"schema_version":1,"sections":' + opening + b"null" + closing + b"}"
    path.write_bytes(payload)

    owner = UiStateOwner(path)
    try:
        assert _read(owner).dirty is True
        assert _read(owner).value == AppearanceValue(ThemeMode.SYSTEM)
        assert path.read_bytes() == payload
    finally:
        owner.close()


def test_br_g_46_pathological_json_integer_falls_back_without_escaping_load(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ui-state.json"
    payload = (
        b'{"schema_version":1,"sections":{"appearance":'
        b'{"value_version":1,"value":{"theme":'
        + b"1" * 5_000
        + b"}}}}"
    )
    assert len(payload) <= _MAX_DOCUMENT_BYTES
    path.write_bytes(payload)

    owner = UiStateOwner(path)
    try:
        snapshot = _read(owner)
        assert snapshot.revision == 0
        assert snapshot.dirty is True
        assert snapshot.value == AppearanceValue(ThemeMode.SYSTEM)
        assert path.read_bytes() == payload
    finally:
        owner.close()


def test_br_g_46_read_oserror_preserves_artifact_and_blocks_every_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 60.0)
    path = tmp_path / "ui-state.json"
    original = _write_document(path, _document("dark"))
    secret = str(path)
    writes: list[bytes] = []

    def fail_read(_path: Path) -> bytes:
        raise PermissionError(f"cannot read secret path {secret}")

    monkeypatch.setattr(ui_state_module, "_read_bounded", fail_read)
    monkeypatch.setattr(
        ui_state_module,
        "_atomic_write",
        lambda _path, payload: writes.append(payload),
    )

    with caplog.at_level(logging.WARNING, logger="namisync.interfaces.ui_state"):
        owner = UiStateOwner(path)
        snapshot = _read(owner)
        assert snapshot.dirty is True
        assert snapshot.value == AppearanceValue(ThemeMode.SYSTEM)

        result = _replace(owner, expected_revision=0, theme="light")
        assert result.disposition is CosmeticDisposition.APPLIED
        assert result.dirty is True
        assert result.value == AppearanceValue(ThemeMode.LIGHT)
        owner.close()

    assert writes == []
    assert path.read_bytes() == original
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert secret not in messages
    assert "cannot read secret path" not in messages
    assert all(record.exc_info is None for record in caplog.records)


def test_br_g_46_exact_legacy_prototype_is_dirty_and_repaired_only_on_schedule(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 0.01)
    path = tmp_path / "ui-state.json"
    legacy = {
        "recent_sources": [],
        "recent_targets": [],
        "window": {},
        "columns": {},
        "sort": {},
    }
    original = _write_document(path, legacy)
    owner = UiStateOwner(path)

    try:
        snapshot = _read(owner)
        assert snapshot.revision == 0
        assert snapshot.dirty is True
        assert snapshot.value == AppearanceValue(ThemeMode.SYSTEM)
        assert path.read_bytes() == original

        result = _replace(owner, expected_revision=0, theme="system")
        assert result.disposition is CosmeticDisposition.NOOP
        _wait_until(lambda: not _read(owner).dirty)
    finally:
        owner.close()

    assert json.loads(path.read_text(encoding="utf-8")) == _document()


@pytest.mark.parametrize(
    "forward_document",
    [
        {
            "schema_version": 2,
            "sections": {
                "appearance": {
                    "value_version": 1,
                    "value": {"theme": "dark"},
                }
            },
        },
        {
            "schema_version": 1,
            "sections": {
                "appearance": {
                    "value_version": 2,
                    "value": {"theme": "dark", "future": True},
                }
            },
        },
    ],
)
def test_br_g_46_forward_state_stays_session_only_and_is_never_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    forward_document: object,
) -> None:
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 0.01)
    writes: list[bytes] = []
    monkeypatch.setattr(
        ui_state_module,
        "_atomic_write",
        lambda _path, payload: writes.append(payload),
    )
    path = tmp_path / "ui-state.json"
    original = _write_document(path, forward_document)
    owner = UiStateOwner(path)

    try:
        assert _read(owner).dirty is True
        result = _replace(owner, expected_revision=0, theme="light")
        assert result.disposition is CosmeticDisposition.APPLIED
        assert result.revision == 1
        assert result.value == AppearanceValue(ThemeMode.LIGHT)
        time.sleep(0.05)
        assert writes == []
        assert path.read_bytes() == original
    finally:
        owner.close()

    assert writes == []
    assert path.read_bytes() == original


def test_br_g_46_replacement_revision_and_dirty_decision_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 60.0)
    writes: list[bytes] = []
    monkeypatch.setattr(
        ui_state_module,
        "_atomic_write",
        lambda _path, payload: writes.append(payload),
    )
    owner = UiStateOwner(tmp_path / "ui-state.json")

    assert _replace(
        owner, expected_revision=0, theme="system"
    ).disposition is CosmeticDisposition.NOOP
    assert writes == []

    applied = _replace(owner, expected_revision=0, theme="light")
    assert applied.disposition is CosmeticDisposition.APPLIED
    assert applied.revision == 1
    assert applied.dirty is True

    same_dirty = _replace(owner, expected_revision=1, theme="light")
    assert same_dirty.disposition is CosmeticDisposition.NOOP
    assert same_dirty.revision == 1
    assert same_dirty.dirty is True

    stale_same = _replace(owner, expected_revision=0, theme="light")
    assert stale_same.disposition is CosmeticDisposition.NOOP
    assert stale_same.revision == 1

    stale_different = _replace(owner, expected_revision=0, theme="dark")
    assert stale_different.disposition is CosmeticDisposition.CONFLICT
    assert stale_different.revision == 1
    assert stale_different.value == AppearanceValue(ThemeMode.LIGHT)

    owner.close()
    assert len(writes) == 1

    clean = UiStateOwner(tmp_path / "clean-ui-state.json")
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 0.01)
    first = _replace(clean, expected_revision=0, theme="dark")
    _wait_until(lambda: not _read(clean).dirty)
    before = len(writes)
    same_clean = _replace(clean, expected_revision=first.revision, theme="dark")
    assert same_clean.disposition is CosmeticDisposition.NOOP
    time.sleep(0.05)
    assert len(writes) == before
    clean.close()


def test_br_g_46_concurrent_expected_revision_replacements_are_serialized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 60.0)
    owner = UiStateOwner(tmp_path / "ui-state.json")
    barrier = threading.Barrier(3)
    results = []

    def replace(theme: str) -> None:
        barrier.wait()
        results.append(_replace(owner, expected_revision=0, theme=theme))

    threads = [
        threading.Thread(target=replace, args=(theme,))
        for theme in ("light", "dark")
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(2)

    try:
        assert not any(thread.is_alive() for thread in threads)
        assert {result.disposition for result in results} == {
            CosmeticDisposition.APPLIED,
            CosmeticDisposition.CONFLICT,
        }
        assert _read(owner).revision == 1
    finally:
        owner.close()


def test_br_g_46_writer_coalesces_changes_for_250_milliseconds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writes: list[tuple[float, bytes]] = []

    def capture(_path: Path, payload: bytes) -> None:
        writes.append((time.monotonic(), payload))

    monkeypatch.setattr(ui_state_module, "_atomic_write", capture)
    owner = UiStateOwner(tmp_path / "ui-state.json")
    started = time.monotonic()

    try:
        _replace(owner, expected_revision=0, theme="light")
        _replace(owner, expected_revision=1, theme="dark")
        _replace(owner, expected_revision=2, theme="system")

        time.sleep(0.15)
        assert writes == []
        _wait_until(lambda: len(writes) == 1)
        assert writes[0][0] - started >= 0.20
        assert json.loads(writes[0][1]) == _document("system")
        _wait_until(lambda: not _read(owner).dirty)
    finally:
        owner.close()

    assert len(writes) == 1


def test_br_g_46_old_in_flight_generation_cannot_mark_newer_state_clean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 0.01)
    first_started = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()
    release_second = threading.Event()
    payloads: list[bytes] = []

    def controlled_write(_path: Path, payload: bytes) -> None:
        payloads.append(payload)
        if len(payloads) == 1:
            first_started.set()
            assert release_first.wait(2)
        else:
            second_started.set()
            assert release_second.wait(2)

    monkeypatch.setattr(ui_state_module, "_atomic_write", controlled_write)
    owner = UiStateOwner(tmp_path / "ui-state.json")

    try:
        _replace(owner, expected_revision=0, theme="light")
        assert first_started.wait(1)
        _replace(owner, expected_revision=1, theme="dark")
        release_first.set()
        assert second_started.wait(1)

        between = _read(owner)
        assert between.revision == 2
        assert between.value == AppearanceValue(ThemeMode.DARK)
        assert between.dirty is True

        release_second.set()
        _wait_until(lambda: not _read(owner).dirty)
    finally:
        release_first.set()
        release_second.set()
        owner.close()

    assert [json.loads(payload) for payload in payloads] == [
        _document("light"),
        _document("dark"),
    ]


def test_br_g_46_failed_schedule_gets_one_attempt_and_close_does_not_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 0.01)
    attempted = threading.Event()
    calls = 0
    secret = str(tmp_path / "do-not-log.json")

    def fail(_path: Path, _payload: bytes) -> None:
        nonlocal calls
        calls += 1
        attempted.set()
        raise OSError(f"secret payload at {secret}")

    monkeypatch.setattr(ui_state_module, "_atomic_write", fail)
    owner = UiStateOwner(tmp_path / "ui-state.json")

    with caplog.at_level(logging.WARNING, logger="namisync.interfaces.ui_state"):
        _replace(owner, expected_revision=0, theme="light")
        assert attempted.wait(1)
        time.sleep(0.05)
        assert calls == 1
        assert _read(owner).dirty is True
        owner.close()

    assert calls == 1
    messages = [record.getMessage() for record in caplog.records]
    assert messages.count("ui_state.save_failed exception_type=OSError") == 1
    assert all(record.exc_info is None for record in caplog.records)
    assert secret not in "\n".join(messages)
    assert "secret payload" not in "\n".join(messages)


def test_br_g_46_current_revision_same_value_explicitly_retries_failed_save(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 0.01)
    first_attempted = threading.Event()
    calls = 0

    def fail_once(_path: Path, _payload: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            first_attempted.set()
            raise OSError("first attempt fails")

    monkeypatch.setattr(ui_state_module, "_atomic_write", fail_once)
    owner = UiStateOwner(tmp_path / "ui-state.json")

    try:
        applied = _replace(owner, expected_revision=0, theme="dark")
        assert first_attempted.wait(1)
        time.sleep(0.05)
        assert calls == 1
        assert _read(owner).dirty is True

        retried = _replace(
            owner,
            expected_revision=applied.revision,
            theme="dark",
        )
        assert retried.disposition is CosmeticDisposition.NOOP
        assert retried.dirty is True
        _wait_until(lambda: calls == 2 and not _read(owner).dirty)
    finally:
        owner.close()

    assert calls == 2


def test_br_g_46_stale_same_value_after_failed_save_does_not_reschedule(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 0.01)
    first_attempted = threading.Event()
    calls = 0

    def fail(_path: Path, _payload: bytes) -> None:
        nonlocal calls
        calls += 1
        first_attempted.set()
        raise OSError("save fails")

    monkeypatch.setattr(ui_state_module, "_atomic_write", fail)
    owner = UiStateOwner(tmp_path / "ui-state.json")

    try:
        applied = _replace(owner, expected_revision=0, theme="light")
        assert applied.disposition is CosmeticDisposition.APPLIED
        assert first_attempted.wait(1)

        def writer_is_idle() -> bool:
            with owner._condition:
                return (
                    owner._active_generation is None
                    and owner._pending_write is None
                )

        _wait_until(writer_is_idle)
        assert calls == 1

        stale = _replace(owner, expected_revision=0, theme="light")
        assert stale.disposition is CosmeticDisposition.NOOP
        assert stale.revision == 1
        assert stale.dirty is True
        time.sleep(0.05)
        assert calls == 1
    finally:
        owner.close()

    assert calls == 1


def test_br_g_46_subscribers_receive_snapshot_and_sequentially_isolate_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 60.0)
    owner = UiStateOwner(tmp_path / "ui-state.json")
    first_seen: list[tuple[int, str]] = []
    second_seen: list[tuple[int, str]] = []

    def failing(_snapshot: CosmeticSectionSnapshot) -> None:
        raise RuntimeError("subscriber secret")

    first = owner.subscribe(
        _APPEARANCE,
        lambda snapshot: first_seen.append((snapshot.revision, snapshot.value.theme)),
    )
    broken = owner.subscribe(_APPEARANCE, failing)
    second = owner.subscribe(
        _APPEARANCE,
        lambda snapshot: second_seen.append((snapshot.revision, snapshot.value.theme)),
    )

    assert first.snapshot == second.snapshot == _read(owner)
    assert first_seen == second_seen == []

    with caplog.at_level(logging.WARNING, logger="namisync.interfaces.ui_state"):
        light = _replace(owner, expected_revision=0, theme="light")
        first.close()
        dark = _replace(owner, expected_revision=1, theme="dark")

    try:
        assert light.disposition is CosmeticDisposition.APPLIED
        assert dark.disposition is CosmeticDisposition.APPLIED
        assert first_seen == [(1, "light")]
        assert second_seen == [(1, "light"), (2, "dark")]
        assert broken.snapshot.revision == 0
        messages = [record.getMessage() for record in caplog.records]
        assert messages.count(
            "ui_state.subscriber_failed exception_type=RuntimeError"
        ) == 2
        assert "subscriber secret" not in "\n".join(messages)
        assert all(record.exc_info is None for record in caplog.records)
    finally:
        first.close()
        broken.close()
        second.close()
        owner.close()


def test_br_g_46_close_flushes_only_current_never_attempted_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 60.0)
    writes: list[bytes] = []
    monkeypatch.setattr(
        ui_state_module,
        "_atomic_write",
        lambda _path, payload: writes.append(payload),
    )
    owner = UiStateOwner(tmp_path / "ui-state.json")
    _replace(owner, expected_revision=0, theme="light")
    _replace(owner, expected_revision=1, theme="dark")

    owner.close()
    owner.close()

    assert [json.loads(payload) for payload in writes] == [_document("dark")]
    time.sleep(0.05)
    assert len(writes) == 1
    with pytest.raises(RuntimeError, match="closed"):
        _replace(owner, expected_revision=2, theme="system")


def test_br_g_46_close_repairs_recoverable_dirty_load_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writes: list[bytes] = []
    monkeypatch.setattr(
        ui_state_module,
        "_atomic_write",
        lambda _path, payload: writes.append(payload),
    )
    path = tmp_path / "ui-state.json"
    path.write_text("not-json", encoding="utf-8")
    owner = UiStateOwner(path)
    assert _read(owner).dirty is True

    owner.close()
    owner.close()

    assert [json.loads(payload) for payload in writes] == [_document()]


def test_br_g_46_close_waits_for_in_flight_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 0.01)
    write_started = threading.Event()
    release_write = threading.Event()
    close_done = threading.Event()

    def block(_path: Path, _payload: bytes) -> None:
        write_started.set()
        assert release_write.wait(2)

    monkeypatch.setattr(ui_state_module, "_atomic_write", block)
    owner = UiStateOwner(tmp_path / "ui-state.json")
    _replace(owner, expected_revision=0, theme="dark")
    assert write_started.wait(1)
    writer = owner._writer_thread
    assert writer is not None

    def close() -> None:
        owner.close()
        close_done.set()

    thread = threading.Thread(target=close)
    thread.start()
    try:
        assert not close_done.wait(0.05)
        release_write.set()
        assert close_done.wait(1)
    finally:
        release_write.set()
        thread.join(2)

    assert not thread.is_alive()
    assert not writer.is_alive()


def test_br_g_46_close_waits_for_old_write_then_flushes_latest_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ui_state_module, "_WRITE_DELAY_SECONDS", 0.01)
    path = tmp_path / "ui-state.json"
    original_atomic_write = ui_state_module._atomic_write
    first_started = threading.Event()
    release_first = threading.Event()
    close_done = threading.Event()
    payloads: list[bytes] = []

    def controlled_write(target: Path, payload: bytes) -> None:
        payloads.append(payload)
        if len(payloads) == 1:
            first_started.set()
            assert release_first.wait(2)
        original_atomic_write(target, payload)

    monkeypatch.setattr(ui_state_module, "_atomic_write", controlled_write)
    owner = UiStateOwner(path)
    _replace(owner, expected_revision=0, theme="light")
    assert first_started.wait(1)
    _replace(owner, expected_revision=1, theme="dark")

    def close() -> None:
        owner.close()
        close_done.set()

    thread = threading.Thread(target=close)
    thread.start()
    try:
        _wait_until(lambda: not owner._accepting)
        assert not close_done.is_set()
        release_first.set()
        assert close_done.wait(1)
    finally:
        release_first.set()
        thread.join(2)

    assert not thread.is_alive()
    assert [json.loads(payload) for payload in payloads] == [
        _document("light"),
        _document("dark"),
    ]
    assert json.loads(path.read_text(encoding="utf-8")) == _document("dark")
