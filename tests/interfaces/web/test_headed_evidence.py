"""Immutable headed subprocess evidence protocol tests."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace

import pytest

import _headed_evidence as evidence
import _headed_native as headed_native
from _headed_evidence import (
    EvidencePaths,
    EvidenceProtocolError,
    EvidencePublisher,
    EvidenceReader,
    require_host_final,
)
from _headed_native import wait_for_initial_evidence


def _paths(root: Path) -> EvidencePaths:
    return EvidencePaths(root.resolve())


def _record(milestone: str, payload: dict[str, object]) -> bytes:
    return (
        json.dumps(
            {
                "milestone": milestone,
                "payload": payload,
                "schema": "namisync-headed-evidence-v1",
            },
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def test_ready_and_final_are_canonical_immutable_milestones(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    publisher = EvidencePublisher(paths)
    publisher.publish_ready({"label": "café", "nested": {"count": 2}})
    publisher.publish_final({"exit_code": 0})

    assert paths.ready.read_bytes() == _record(
        "ready", {"label": "café", "nested": {"count": 2}}
    )
    assert paths.final.read_bytes() == _record("final", {"exit_code": 0})
    reader = EvidenceReader(paths)
    assert reader.available_initial() == "ready"
    ready = reader.read_ready()
    assert ready == {"label": "café", "nested": {"count": 2}}
    assert ready is not None
    ready["label"] = "changed"
    assert reader.read_ready() == {
        "label": "café",
        "nested": {"count": 2},
    }
    assert reader.read_final() == {"exit_code": 0}
    reader.assert_consistent(require_final=True)


def test_publisher_enforces_initial_exclusion_and_terminal_final(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    publisher = EvidencePublisher(paths)
    publisher.publish_ready({"ok": True})
    with pytest.raises(EvidenceProtocolError, match="mutually exclusive"):
        publisher.publish_failure({"error": "late"})
    with pytest.raises(EvidenceProtocolError, match="mutually exclusive"):
        publisher.publish_ready({"ok": True})
    publisher.publish_final({"exit_code": 0})
    with pytest.raises(EvidenceProtocolError, match="after final"):
        publisher.publish_final({"exit_code": 0})
    with pytest.raises(EvidenceProtocolError, match="after final"):
        publisher.publish_ready({"ok": True})

    other_root = tmp_path / "failure"
    other_root.mkdir()
    failed = EvidencePublisher(_paths(other_root))
    failed.publish_failure({"error": "startup"})
    with pytest.raises(EvidenceProtocolError, match="mutually exclusive"):
        failed.publish_ready({"ok": True})


def test_final_only_requires_an_explicit_reader_policy(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    EvidencePublisher(paths).publish_final({"refused": True})
    reader = EvidenceReader(paths)
    assert reader.read_final() == {"refused": True}
    with pytest.raises(EvidenceProtocolError, match="Final-only|final-only"):
        reader.assert_consistent(require_final=True)
    reader.assert_consistent(require_final=True, allow_final_only=True)


@pytest.mark.parametrize(
    "encoded",
    [
        b"{}\n",
        b"\xff\n",
        b'{"milestone":"ready","payload":{"value":NaN},'
        b'"schema":"namisync-headed-evidence-v1"}\n',
        b'{"milestone": "ready", "payload": {}, '
        b'"schema": "namisync-headed-evidence-v1"}\n',
        b'{"extra":1,"milestone":"ready","payload":{},'
        b'"schema":"namisync-headed-evidence-v1"}\n',
        _record("failure", {}),
    ],
)
def test_reader_rejects_malformed_or_noncanonical_records(
    tmp_path: Path,
    encoded: bytes,
) -> None:
    paths = _paths(tmp_path)
    paths.ready.write_bytes(encoded)
    with pytest.raises(EvidenceProtocolError):
        EvidenceReader(paths).read_ready()


def test_writer_and_reader_enforce_exact_payload_and_byte_bound(tmp_path: Path) -> None:
    publisher = EvidencePublisher(_paths(tmp_path))
    with pytest.raises(TypeError, match="exact object"):
        publisher.publish_ready([])  # type: ignore[arg-type]
    with pytest.raises(EvidenceProtocolError, match="exact JSON"):
        publisher.publish_ready({"value": object()})
    with pytest.raises(EvidenceProtocolError, match="exact JSON"):
        publisher.publish_ready({"value": ("tuple",)})
    with pytest.raises(EvidenceProtocolError, match="exact JSON"):
        publisher.publish_ready({1: "coerced key"})  # type: ignore[dict-item]
    cycle: dict[str, object] = {}
    cycle["cycle"] = cycle
    with pytest.raises(EvidenceProtocolError, match="exact JSON"):
        publisher.publish_ready(cycle)
    with pytest.raises(EvidenceProtocolError, match="1048576"):
        publisher.publish_ready({"value": "x" * 1_048_576})

    oversized = tmp_path / "oversized"
    oversized.mkdir()
    oversized_paths = _paths(oversized)
    oversized_paths.ready.write_bytes(b"x" * 1_048_577)
    with pytest.raises(EvidenceProtocolError, match="1048576"):
        EvidenceReader(oversized_paths).read_ready()


def test_reader_normalizes_excessive_json_nesting(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.ready.write_bytes(
        b'{"milestone":"ready","payload":'
        + (b'{"nested":' * 1_100)
        + b'{}'
        + (b'}' * 1_100)
        + b',"schema":"namisync-headed-evidence-v1"}\n'
    )

    with pytest.raises(EvidenceProtocolError, match="JSON"):
        EvidenceReader(paths).read_ready()


def test_preexisting_destination_is_untouched_and_failed_move_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    paths.ready.write_bytes(b"sentinel")
    with pytest.raises(FileExistsError):
        EvidencePublisher(paths).publish_ready({"ok": True})
    assert paths.ready.read_bytes() == b"sentinel"
    assert paths.orphan_temporaries() == ()

    failed_root = tmp_path / "failed-move"
    failed_root.mkdir()
    failed_paths = _paths(failed_root)
    monkeypatch.setattr(
        evidence,
        "_move_no_replace",
        lambda _source, _target: (_ for _ in ()).throw(OSError("injected")),
    )
    with pytest.raises(OSError, match="injected"):
        EvidencePublisher(failed_paths).publish_ready({"ok": True})
    assert not failed_paths.ready.exists()
    assert failed_paths.orphan_temporaries() == ()


def test_reader_rejects_contradiction_or_milestones_after_observed_final(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    EvidencePublisher(paths).publish_ready({"ok": True})
    EvidencePublisher(paths).publish_failure({"error": "contradiction"})
    with pytest.raises(EvidenceProtocolError, match="cannot both"):
        EvidenceReader(paths).available_initial()

    final_root = tmp_path / "after-final"
    final_root.mkdir()
    final_paths = _paths(final_root)
    EvidencePublisher(final_paths).publish_final({"exit_code": 0})
    reader = EvidenceReader(final_paths)
    assert reader.read_final() == {"exit_code": 0}
    EvidencePublisher(final_paths).publish_ready({"ok": True})
    with pytest.raises(EvidenceProtocolError, match="changed after final"):
        reader.assert_consistent(require_final=True, allow_final_only=True)


def test_consistency_check_rejects_orphan_protocol_temporary(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    EvidencePublisher(paths).publish_ready({"ok": True})
    orphan = tmp_path / ".namisync-headed-evidence-ready-1-deadbeef.tmp"
    orphan.write_bytes(b"partial")
    with pytest.raises(EvidenceProtocolError, match=orphan.name):
        EvidenceReader(paths).assert_consistent(require_final=False)


def test_distinct_final_publish_completes_while_ready_file_is_held_open(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    publisher = EvidencePublisher(paths)
    publisher.publish_ready({"ok": True})
    finished = Event()
    failures: list[BaseException] = []

    def publish_final() -> None:
        try:
            publisher.publish_final({"exit_code": 0})
        except BaseException as error:
            failures.append(error)
        finally:
            finished.set()

    with paths.ready.open("rb") as held_ready:
        original = held_ready.read()
        if os.name == "nt":
            replacement = tmp_path / "old-live-snapshot.tmp"
            replacement.write_bytes(b"replacement")
            with pytest.raises(PermissionError):
                replacement.replace(paths.ready)
            replacement.unlink()
        worker = Thread(target=publish_final, daemon=True)
        worker.start()
        assert finished.wait(1.0)
        worker.join(1.0)
        assert held_ready.seek(0) == 0
        assert held_ready.read() == original
    assert failures == []
    reader = EvidenceReader(paths)
    assert reader.read_ready() == {"ok": True}
    assert reader.read_final() == {"exit_code": 0}
    reader.assert_consistent(require_final=True)
    assert paths.orphan_temporaries() == ()


def test_shared_waiter_returns_the_single_cached_initial_payload(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    EvidencePublisher(paths).publish_ready({"phase": "complete"})

    class Process:
        def poll(self) -> object:
            raise AssertionError("published evidence must win before process polling")

    class Deadline:
        def remaining(self) -> float:
            raise AssertionError("published evidence must not consume deadline")

    assert wait_for_initial_evidence(
        EvidenceReader(paths),
        Process(),  # type: ignore[arg-type]
        deadline=Deadline(),  # type: ignore[arg-type]
    ) == ("ready", {"phase": "complete"})


def test_shared_waiter_reports_a_child_that_exits_before_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = EvidenceReader(_paths(tmp_path))
    process = SimpleNamespace(poll=lambda: 7)
    completed = SimpleNamespace(returncode=7, stdout="child-out", stderr="child-err")
    monkeypatch.setattr(
        headed_native,
        "wait_for_process",
        lambda actual, *, deadline: (
            completed
            if actual is process and deadline == "deadline"
            else pytest.fail("unexpected process wait")
        ),
    )

    with pytest.raises(AssertionError, match=r"(?s)child-out.*child-err"):
        wait_for_initial_evidence(
            reader,
            process,  # type: ignore[arg-type]
            deadline="deadline",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("payload", "exit_code"),
    [
        ({"host_returned": 1, "exit_code": 0}, 0),
        ({"host_returned": True, "exit_code": False}, 0),
        ({"host_returned": True, "exit_code": 0}, False),
        ({"host_returned": True}, 0),
        ({"host_returned": True, "exit_code": 0, "extra": True}, 0),
        ({"host_returned": True, "exit_code": 1}, 0),
    ],
)
def test_common_host_final_rejects_coercive_or_inexact_values(
    payload: dict[str, object],
    exit_code: object,
) -> None:
    with pytest.raises(EvidenceProtocolError, match="host final"):
        require_host_final(payload, exit_code=exit_code)  # type: ignore[arg-type]


def test_common_host_final_returns_the_exact_host_state() -> None:
    assert require_host_final(
        {"host_returned": True, "exit_code": 0},
        exit_code=0,
    ) is True
    assert require_host_final(
        {"host_returned": False, "exit_code": 1},
        exit_code=1,
    ) is False


def test_headed_evidence_protocol_stays_test_only_and_owns_milestone_paths() -> None:
    repository = Path(__file__).parents[3]
    production_sources = tuple((repository / "namisync").rglob("*.py"))
    assert production_sources
    for source in production_sources:
        assert "_headed_evidence" not in source.read_text(encoding="utf-8"), source

    children = (
        "_bridge_event_benchmark_child.py",
        "_component_gallery_child.py",
        "_headed_host_child.py",
        "_materials_gate_child.py",
        "_native_gate_child.py",
        "_shell_gate_child.py",
        "_transport_gate_child.py",
    )
    for name in children:
        source = Path(__file__).with_name(name)
        text = source.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(source))
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"replace", "rename"}
            and any(
                isinstance(argument, ast.Constant)
                and argument.value in {"ready.json", "failure.json", "final.json"}
                for argument in node.args
            )
            for node in ast.walk(tree)
        ), source
        assert all(
            milestone not in text
            for milestone in ("ready.json", "failure.json", "final.json")
        ), source
