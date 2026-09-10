"""Ordinary BR-G-32 evidence for bounded folder-slot authority."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from itertools import count
from threading import Event, Lock, Thread

import pytest

from namisync.core.models import VolumeId
from namisync.interfaces.web.slots import FolderSlotTable, SlotUnavailableError
from namisync.workflows import (
    LocationBinding,
    LocationCandidate,
    LocationCandidateResult,
    LocationCandidateState,
    VolumeResolution,
    VolumeResolutionState,
)


def _token(value: int) -> str:
    return f"{value:032x}"


class _Clock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _tokens(start: int = 0):
    values = count(start)
    return lambda: _token(next(values))


def _ambiguous(path: str = r"C:\source") -> tuple[LocationCandidate, LocationCandidateResult]:
    candidate = LocationCandidate.literal(path)
    binding = LocationBinding(
        VolumeId("serial", "NTFS"), "folder", "C:\\", ("C:\\", "D:\\"), True
    )
    resolution = VolumeResolution(
        VolumeResolutionState.AMBIGUOUS,
        binding,
        candidates=("C:\\", "D:\\"),
        detail="Choose a current mount",
    )
    return candidate, LocationCandidateResult(
        candidate,
        LocationCandidateState.AMBIGUOUS,
        binding,
        None,
        ("C:\\", "D:\\"),
        "Choose a current mount",
        resolution,
    )


def test_br_g_32_slots_are_opaque_nonconsuming_and_purpose_bound() -> None:
    table = FolderSlotTable(token=_tokens())
    source_id, source_display = table.store(
        "C:\\private\\source U0001f30a",
        purpose="source",
    )
    target_id, target_display = table.store(
        "D:\\private\\target",
        purpose="target",
    )

    assert source_id == "slot-" + _token(0)
    assert target_id == "slot-" + _token(1)
    assert source_display == "C:\\private\\source U0001f30a"
    assert target_display == "D:\\private\\target"
    assert table.resolve_pair(source_id, target_id) == (
        "C:\\private\\source U0001f30a",
        "D:\\private\\target",
    )
    assert table.resolve_pair(source_id, target_id) == (
        "C:\\private\\source U0001f30a",
        "D:\\private\\target",
    )

    with pytest.raises(SlotUnavailableError):
        table.resolve_pair("slot-" + _token(31), target_id)
    with pytest.raises(SlotUnavailableError):
        table.resolve_pair(target_id, source_id)


@pytest.mark.parametrize("path", ["", "\ud800"])
def test_br_g_32_slots_require_nonempty_valid_unicode_paths(path: str) -> None:
    table = FolderSlotTable(token=_tokens())

    with pytest.raises(ValueError):
        table.store(path, purpose="source")


def test_br_g_32_slots_reject_non_string_purpose_without_mutation() -> None:
    table = FolderSlotTable(token=_tokens())

    with pytest.raises(ValueError, match="purpose"):
        table.store("path", purpose=[])  # type: ignore[arg-type]

    assert table._entries == {}


def test_br_g_32_slot_expiry_is_fixed_at_the_exact_thirty_minute_edge() -> None:
    clock = _Clock()
    table = FolderSlotTable(clock=clock, token=_tokens())
    source_id, _ = table.store("source", purpose="source")
    target_id, _ = table.store("target", purpose="target")

    clock.now = 1_799.999
    assert table.resolve_pair(source_id, target_id) == ("source", "target")

    clock.now = 1_800.0
    with pytest.raises(SlotUnavailableError):
        table.resolve_pair(source_id, target_id)


def test_br_g_32_thirty_third_slot_evicts_lru_with_slot_id_tiebreak() -> None:
    clock = _Clock()
    table = FolderSlotTable(clock=clock, token=_tokens())
    source_ids = [
        table.store(f"source-{index}", purpose="source")[0]
        for index in range(31)
    ]
    target_id, _ = table.store("target", purpose="target")

    clock.now = 1.0
    assert table.resolve_pair(source_ids[0], target_id) == (
        "source-0",
        "target",
    )

    clock.now = 2.0
    table.store("source-new", purpose="source")

    assert table.resolve_pair(source_ids[0], target_id) == (
        "source-0",
        "target",
    )
    with pytest.raises(SlotUnavailableError):
        table.resolve_pair(source_ids[1], target_id)

    tied = FolderSlotTable(clock=_Clock(), token=_tokens())
    tied_sources = [
        tied.store(f"tied-{index}", purpose="source")[0]
        for index in range(31)
    ]
    tied_target, _ = tied.store("target", purpose="target")
    tied.store("replacement", purpose="source")
    with pytest.raises(SlotUnavailableError):
        tied.resolve_pair(tied_sources[0], tied_target)
    assert tied.resolve_pair(tied_sources[1], tied_target) == (
        "tied-1",
        "target",
    )


def test_br_g_32_expired_slots_are_swept_before_capacity_eviction() -> None:
    clock = _Clock()
    table = FolderSlotTable(clock=clock, token=_tokens())
    old_ids = [
        table.store(f"old-{index}", purpose="source")[0]
        for index in range(32)
    ]

    clock.now = 1_800.0
    current_id, _ = table.store("current", purpose="source")

    assert set(table._entries) == {current_id}
    assert not set(old_ids) & set(table._entries)


def test_br_g_32_failed_pair_resolution_touches_neither_slot() -> None:
    clock = _Clock()
    table = FolderSlotTable(clock=clock, token=_tokens())
    source_ids = [
        table.store(f"source-{index}", purpose="source")[0]
        for index in range(31)
    ]
    target_id, _ = table.store("target", purpose="target")

    clock.now = 1.0
    with pytest.raises(SlotUnavailableError):
        table.resolve_pair(source_ids[0], "slot-" + _token(99))
    assert table._entries[source_ids[0]].last_used == 0.0
    assert table._entries[target_id].last_used == 0.0

    clock.now = 2.0
    table.store("replacement", purpose="source")

    with pytest.raises(SlotUnavailableError):
        table.resolve_pair(source_ids[0], target_id)


def test_br_g_32_successful_pair_resolution_touches_both_slots() -> None:
    clock = _Clock()
    table = FolderSlotTable(clock=clock, token=_tokens())
    source_id, _ = table.store("source", purpose="source")
    target_id, _ = table.store("target", purpose="target")
    for index in range(30):
        table.store(f"filler-{index}", purpose="source")

    clock.now = 1.0
    assert table.resolve_pair(source_id, target_id) == ("source", "target")
    clock.now = 2.0
    table.store("replacement", purpose="source")

    assert table.resolve_pair(source_id, target_id) == ("source", "target")


def test_br_g_32_slot_id_collision_remints_without_overwriting() -> None:
    candidates = iter((_token(7), _token(7), _token(8)))
    table = FolderSlotTable(token=lambda: next(candidates))

    first, _ = table.store("first", purpose="source")
    second, _ = table.store("second", purpose="target")

    assert first == "slot-" + _token(7)
    assert second == "slot-" + _token(8)
    assert table.resolve_pair(first, second) == ("first", "second")


def test_br_g_32_slot_capacity_is_bounded_under_concurrent_insertion() -> None:
    table = FolderSlotTable(token=_tokens())

    with ThreadPoolExecutor(max_workers=16) as workers:
        results = tuple(
            workers.map(
                lambda index: table.store(
                    f"path-{index}",
                    purpose="source",
                )[0],
                range(128),
            )
        )

    assert len(results) == 128
    assert len(set(results)) == 128
    assert len(table._entries) == 32


def test_br_g_32_ambiguity_continuation_shares_capacity_and_is_not_startable() -> None:
    table = FolderSlotTable(token=_tokens())
    candidate, result = _ambiguous()
    admissions = []
    continuation = table.store_continuation(
        candidate,
        result,
        purpose="source",
        admit=lambda slot_id, retained: (
            admissions.append((slot_id, retained)) or retained
        ),
    )

    with pytest.raises(SlotUnavailableError):
        table.resolve(continuation, purpose="source")
    with pytest.raises(SlotUnavailableError):
        table.resolve_continuation(
            continuation, purpose="target", mount_index=0
        )
    assert table.resolve_continuation(
        continuation, purpose="source", mount_index=1
    ) == (candidate, result.binding, result.candidates, "D:\\")
    assert admissions == [(continuation, {
        "candidate": {
            "kind": "literal_path",
            "path": r"C:\source",
            "location_id": None,
            "selected_mount": None,
        },
        "binding": {
            "volume_id": {"serial": "serial", "fs_type": "NTFS"},
            "volume_relative_path": "folder",
            "selected_mount": "C:\\",
            "expected_mounts": ("C:\\", "D:\\"),
            "explicit_ambiguity_choice": True,
            "location_id": None,
        },
        "candidates": ("C:\\", "D:\\"),
    })]


def test_br_g_32_continuation_response_admission_precedes_eviction() -> None:
    table = FolderSlotTable(token=_tokens())
    retained = [table.store(f"path-{index}", purpose="source")[0] for index in range(32)]
    candidate, result = _ambiguous()

    with pytest.raises(RuntimeError, match="too large"):
        table.store_continuation(
            candidate,
            result,
            purpose="source",
            admit=lambda _slot_id, _retained: (
                _ for _ in ()
            ).throw(RuntimeError("too large")),
        )

    assert set(table._entries) == set(retained)


def test_br_g_32_concurrent_resolution_and_churn_is_atomic_and_bounded() -> None:
    table = FolderSlotTable(token=_tokens())
    pair_lock = Lock()
    pairs: list[tuple[str, str, str, str]] = []
    for index in range(16):
        source_path = f"source-{index}"
        target_path = f"target-{index}"
        source_id, _ = table.store(source_path, purpose="source")
        target_id, _ = table.store(target_path, purpose="target")
        pairs.append((source_id, target_id, source_path, target_path))

    start = Event()
    observations: list[str] = []
    failures: list[BaseException] = []
    result_lock = Lock()

    def churn() -> None:
        try:
            assert start.wait(1.0)
            for index in range(16, 144):
                source_path = f"source-{index}"
                target_path = f"target-{index}"
                source_id, _ = table.store(source_path, purpose="source")
                target_id, _ = table.store(target_path, purpose="target")
                with pair_lock:
                    pairs.append(
                        (source_id, target_id, source_path, target_path)
                    )
        except BaseException as error:
            with result_lock:
                failures.append(error)

    def resolve(offset: int) -> None:
        try:
            assert start.wait(1.0)
            for turn in range(400):
                with pair_lock:
                    candidate = pairs[(turn + offset) % len(pairs)]
                source_id, target_id, source_path, target_path = candidate
                try:
                    resolved = table.resolve_pair(source_id, target_id)
                except SlotUnavailableError:
                    outcome = "unavailable"
                else:
                    assert resolved == (source_path, target_path)
                    outcome = "complete"
                with result_lock:
                    observations.append(outcome)
        except BaseException as error:
            with result_lock:
                failures.append(error)

    threads = [Thread(target=churn, daemon=True)] + [
        Thread(target=resolve, args=(offset,), daemon=True)
        for offset in range(8)
    ]
    for thread in threads:
        thread.start()
    start.set()
    for thread in threads:
        thread.join(5.0)

    assert not [thread for thread in threads if thread.is_alive()]
    assert failures == []
    assert observations
    assert set(observations) <= {"complete", "unavailable"}
    assert len(table._entries) == 32
