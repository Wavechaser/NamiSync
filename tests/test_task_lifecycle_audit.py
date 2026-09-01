from __future__ import annotations

import copy
from pathlib import Path

import pytest

from tools import task_lifecycle_audit as audit


BASELINE = Path(__file__).parents[1] / "tools" / "task_lifecycle_baseline.json"


@pytest.fixture(scope="module")
def boundary_capture() -> dict[str, object]:
    return audit.capture_boundaries(audit.DEFAULT_FIXTURE_ROOT)


def test_real_boundary_capture_is_complete_and_plan_only(
    boundary_capture: dict[str, object],
) -> None:
    audit.validate_capture(boundary_capture)
    assert boundary_capture["filesystem"]["before"] == boundary_capture["filesystem"]["after"]
    assert boundary_capture["persistence"]["before"] == boundary_capture["persistence"]["after"]
    assert boundary_capture["cli"]["exit_code"] == 0
    assert boundary_capture["cli"]["stderr"] == ""
    assert "Capacity: required=32; free=1099511627776; reclaimable-temp=0" in (
        boundary_capture["cli"]["stdout"]
    )
    assert "Plan left uncommitted" in boundary_capture["cli"]["stdout"]


def test_committed_boundary_baseline_matches_current_capture(
    boundary_capture: dict[str, object],
) -> None:
    audit.verify_captures(audit.read_capture(BASELINE), boundary_capture)


def test_corpus_format_version_is_frozen_for_active_register() -> None:
    assert audit.FORMAT_VERSION == 1
    assert audit.read_capture(BASELINE)["format_version"] == 1


def test_normalization_preserves_generated_identity_relationships_and_fixed_ids(
    tmp_path: Path,
) -> None:
    first = "task-" + "e" * 32
    second = "d" * 32
    fixed = "f" * 32
    normalized = audit.normalize_capture(
        {"generated": [first, second, first, second], "fixed": fixed},
        tmp_path,
        frozenset({first, second}),
    )
    assert normalized == {
        "fixed": fixed,
        "generated": [
            "$OPAQUE_0001",
            "$OPAQUE_0002",
            "$OPAQUE_0001",
            "$OPAQUE_0002",
        ],
    }


def _mutate_bridge_response(capture: dict[str, object]) -> None:
    capture["bridge"]["responses"]["start_plan"]["result"]["request_id"] = "$OPAQUE_CHANGED"


def _mutate_cli_line(capture: dict[str, object]) -> None:
    capture["cli"]["stdout"] += "changed boundary line\n"


def _mutate_event_sequence(capture: dict[str, object]) -> None:
    event_stream = capture["bridge"]["event_stream"]
    event = next(update["event"] for update in event_stream if update["update_type"] == "event")
    event["sequence"] += 1_000


def _mutate_fixed_drain_identity(capture: dict[str, object]) -> None:
    capture["bridge"]["responses"]["next_events"][0]["result"]["drain_id"] = (
        "f" * 32
    )


def _mutate_persisted_hash(capture: dict[str, object]) -> None:
    capture["persistence"]["after"][0]["sha256"] = "0" * 64


def _mutate_filesystem_manifest(capture: dict[str, object]) -> None:
    capture["filesystem"]["after"]["bridge"]["target"].append(
        {
            "path": "unexpected.txt",
            "kind": "file",
            "mtime_ns": 1_700_000_000_000_000_000,
            "size": 1,
            "sha256": "0" * 64,
        }
    )


@pytest.mark.parametrize(
    "mutator",
    [
        _mutate_bridge_response,
        _mutate_cli_line,
        _mutate_event_sequence,
        _mutate_fixed_drain_identity,
        _mutate_persisted_hash,
        _mutate_filesystem_manifest,
    ],
    ids=(
        "bridge-response",
        "cli-line",
        "event-sequence",
        "fixed-drain-identity",
        "persisted-hash",
        "filesystem-manifest",
    ),
)
def test_boundary_corruption_never_validates(
    boundary_capture: dict[str, object],
    mutator,
) -> None:
    changed = copy.deepcopy(boundary_capture)
    mutator(changed)

    with pytest.raises(audit.AuditError):
        audit.verify_captures(boundary_capture, changed)


def test_capture_io_and_verify_cli_contract(
    boundary_capture: dict[str, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    audit.write_capture(baseline, boundary_capture)
    monkeypatch.setattr(
        audit,
        "capture_boundaries",
        lambda _fixture_root: copy.deepcopy(boundary_capture),
    )

    result = audit.main(
        [
            "verify",
            "--baseline",
            str(baseline),
            "--output",
            str(current),
            "--fixture-root",
            str(tmp_path / "unused-fixture"),
        ]
    )

    assert result == 0
    assert audit.read_capture(current) == boundary_capture
    assert capsys.readouterr().out == "task lifecycle boundary corpus matches\n"
