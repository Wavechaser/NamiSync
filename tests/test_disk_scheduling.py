"""Physical-disk scheduling keys read from workflow checkpoints (M2-A8).

Unit tests replace the disk-topology reads the reader calls. The reference
test reads this machine's real disks through the real dispatcher; it creates
no files, and waits on barriers, run events and counted scheduler readings,
never on elapsed time. The deadlines only bound a failure.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier, Condition
from time import monotonic
from types import SimpleNamespace

import pytest

import namisync.core.disk_topology as disk_topology
import namisync.workflows.disk_scheduling as disk_scheduling
from _executor_fixtures import _plan, _xset
from namisync.core.disk_topology import DiskFact, counts_as_spinning
from namisync.core.integrity import IntegrityMode
from namisync.core.models import VolumeId
from namisync.core.session import OperationResult, SessionState
from namisync.dispatcher import (
    Dispatcher,
    InProcessResourceLockProvider,
    PreparedSession,
    WorkflowRegistration,
)
from namisync.workflows.disk_scheduling import read_disk_scheduling_keys
from namisync.workflows.inventory import (
    IntegrityWorkflowRequest,
    InventoryWorkflowRequest,
    LocationBinding,
)
from namisync.workflows.models import (
    ExecutionCheckpoint,
    ExecutionRequest,
    PlanRequest,
)

_LIMIT = 10.0
NOW = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
BUS_SATA = 11
BUS_NVME = 17

HDD = DiskFact(0, BUS_SATA, True)
NVME = DiskFact(2, BUS_NVME, False)
USB_SSD = DiskFact(5, disk_topology.BUS_TYPE_USB, False)
UNKNOWN = DiskFact(6, None, None)


def _volume(letter: str) -> str:
    return f"\\\\?\\Volume{{{letter * 8}-0000-0000-0000-000000000000}}\\"


class FakeTopology:
    """Answer the reader's topology calls from a root-letter table."""

    def __init__(
        self,
        disks: dict[str, tuple[DiskFact, ...] | BaseException],
        *,
        volume_errors: dict[str, BaseException] | None = None,
        identities: dict[str, VolumeId] | None = None,
        drives: tuple[str, ...] = (),
    ) -> None:
        self.disks = disks
        self.volume_errors = volume_errors or {}
        # Letters absent here carry every test binding's identity.
        self.identities = identities or {}
        self.drives = drives
        self.volume_calls: list[str] = []
        self.fact_calls: list[str] = []
        self.observe_calls: list[str] = []
        self.enumerations = 0

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(disk_scheduling, "volume_name", self.volume_name)
        monkeypatch.setattr(disk_scheduling, "disk_facts", self.disk_facts)
        monkeypatch.setattr(
            disk_scheduling, "observe_native_volume", self.observe_native_volume
        )
        monkeypatch.setattr(
            disk_scheduling, "logical_drive_roots", self.logical_drive_roots
        )

    def logical_drive_roots(self) -> tuple[str, ...]:
        self.enumerations += 1
        return self.drives

    def observe_native_volume(self, root: str) -> SimpleNamespace:
        self.observe_calls.append(root)
        return SimpleNamespace(
            volume_id=self.identities.get(root[0].upper(), BINDING_VOLUME)
        )

    def volume_name(self, root: str) -> str:
        self.volume_calls.append(root)
        letter = root[0].upper()
        error = self.volume_errors.get(letter)
        if error is not None:
            raise error
        return _volume(letter.lower() if letter.isalpha() else "0")

    def disk_facts(self, name: str) -> tuple[DiskFact, ...]:
        self.fact_calls.append(name)
        letter = next(
            (key for key in self.disks if _volume(key.lower()) == name), None
        )
        if letter is None:
            raise OSError(2, "unknown fake volume", name)
        outcome = self.disks[letter]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


BINDING_VOLUME = VolumeId("1234ABCD", "NTFS")


def _binding(mount: str) -> LocationBinding:
    return LocationBinding(
        BINDING_VOLUME,
        "",
        mount,
        (mount,),
        False,
    )


def _execution_checkpoint(source: str, target: str, *, started=None):
    xset = _xset(_plan(Path(source), Path(target), ()))
    return ExecutionCheckpoint(ExecutionRequest(xset, started))


def _checkpoints(first: str, second: str) -> dict[str, object]:
    """One checkpoint of each registered kind over ``first``/``second``."""

    return {
        "plan": PlanRequest("plan", first, second),
        "execution": _execution_checkpoint(first, second),
        "paused execution": _execution_checkpoint(first, second, started=NOW),
        "inventory": InventoryWorkflowRequest("inventory", _binding(first)),
        "verify": IntegrityWorkflowRequest(
            "verify", _binding(first), IntegrityMode.VERIFY
        ),
        "paused rebaseline": IntegrityWorkflowRequest(
            "rebaseline",
            _binding(first),
            IntegrityMode.REBASELINE,
            selection_item_ids=("7:11", "7:12"),
            completed_bytes=(("7:11", 7),),
            processed_bytes=7,
            bytes_total_high_water=9,
        ),
    }


@pytest.mark.parametrize("kind", list(_checkpoints("J:\\", "C:\\")))
def test_each_kind_keys_only_the_spinning_disks_under_its_roots(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    topology = FakeTopology({"J": (HDD,), "C": (NVME,)})
    topology.install(monkeypatch)

    hdd_first = read_disk_scheduling_keys(_checkpoints("J:\\a", "C:\\b")[kind])
    nvme_first = read_disk_scheduling_keys(_checkpoints("C:\\b", "J:\\a")[kind])

    assert hdd_first == frozenset({("disk", 0)})
    two_root = kind in ("plan", "execution", "paused execution")
    # Single-root kinds read only their binding's mount.
    assert nvme_first == (frozenset({("disk", 0)}) if two_root else frozenset())
    assert type(hdd_first) is frozenset
    for key in hdd_first:
        assert type(key) is tuple
        assert [type(part) for part in key] == [str, int]


@pytest.mark.parametrize("kind", ["inventory", "verify", "paused rebaseline"])
def test_a_binding_whose_volume_moved_is_keyed_at_its_current_mount(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    other = VolumeId("FEEDF00D", "NTFS")
    topology = FakeTopology(
        {"F": (NVME,), "M": (HDD,)},
        # F: now holds another volume, X: is a network letter, and the
        # binding's volume is mounted at M:.
        volume_errors={"X": OSError(2, "not a local volume")},
        identities={"F": other, "C": other},
        drives=("C:\\", "F:\\", "X:\\", "M:\\"),
    )
    topology.install(monkeypatch)

    keys = read_disk_scheduling_keys(_checkpoints("F:\\", "C:\\")[kind])

    assert keys == frozenset({("disk", 0)})
    # The recorded mount is tried first and the network letter never observed.
    assert [root.upper() for root in topology.observe_calls] == ["F:\\", "C:\\", "M:\\"]
    # Each letter is named once, the match included.
    assert [root.upper() for root in topology.volume_calls] == [
        "F:\\", "C:\\", "X:\\", "M:\\"
    ]
    assert topology.enumerations == 1
    assert topology.fact_calls == [_volume("m")]


@pytest.mark.parametrize("kind", ["inventory", "verify", "paused rebaseline"])
def test_a_binding_at_its_recorded_mount_lists_no_drive_letters(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    topology = FakeTopology({"J": (HDD,)}, drives=("C:\\", "J:\\"))
    topology.install(monkeypatch)

    keys = read_disk_scheduling_keys(_checkpoints("J:\\", "C:\\")[kind])

    assert keys == frozenset({("disk", 0)})
    assert topology.enumerations == 0
    assert topology.volume_calls == ["J:\\"]
    assert topology.fact_calls == [_volume("j")]


@pytest.mark.parametrize("kind", ["inventory", "verify"])
def test_a_binding_whose_volume_is_not_mounted_gets_no_keys(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    other = VolumeId("FEEDF00D", "NTFS")
    topology = FakeTopology(
        {"J": (HDD,)}, identities={"J": other}, drives=("J:\\",)
    )
    topology.install(monkeypatch)

    assert read_disk_scheduling_keys(_checkpoints("J:\\", "C:\\")[kind]) == frozenset()
    assert topology.fact_calls == []


def test_paths_are_resolved_at_read_time_and_volumes_read_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    topology = FakeTopology({"J": (HDD,)})
    topology.install(monkeypatch)

    keys = read_disk_scheduling_keys(PlanRequest("r", "J:\\a", "J:\\b"))

    assert keys == frozenset({("disk", 0)})
    assert [root.lower() for root in topology.volume_calls] == ["j:\\a", "j:\\b"]
    assert topology.fact_calls == [_volume("j")]


def test_spinning_rule_comes_from_core(monkeypatch: pytest.MonkeyPatch) -> None:
    spanned = (DiskFact(0, BUS_SATA, True), NVME, USB_SSD, UNKNOWN)
    topology = FakeTopology({"J": spanned, "C": (NVME,)})
    topology.install(monkeypatch)

    keys = read_disk_scheduling_keys(PlanRequest("r", "J:\\", "C:\\"))

    assert keys == frozenset(
        ("disk", fact.disk_number) for fact in spanned if counts_as_spinning(fact)
    )
    assert keys == frozenset({("disk", 0), ("disk", 5), ("disk", 6)})


@pytest.mark.parametrize(
    "failure",
    [
        {"volume": OSError(2, "volume gone")},
        {"volume": ValueError("not a local root")},
        {"facts": OSError(1, "extents unreadable")},
        {"facts": ValueError("not a volume GUID name")},
    ],
    ids=["volume-oserror", "volume-valueerror", "facts-oserror", "facts-valueerror"],
)
def test_an_unreadable_root_contributes_no_keys(
    monkeypatch: pytest.MonkeyPatch, failure: dict[str, BaseException]
) -> None:
    disks: dict[str, tuple[DiskFact, ...] | BaseException] = {"J": (HDD,)}
    volume_errors = {}
    if "volume" in failure:
        volume_errors["M"] = failure["volume"]
    else:
        disks["M"] = failure["facts"]
    topology = FakeTopology(disks, volume_errors=volume_errors)
    topology.install(monkeypatch)

    assert read_disk_scheduling_keys(PlanRequest("r", "M:\\", "J:\\")) == frozenset(
        {("disk", 0)}
    )
    assert read_disk_scheduling_keys(PlanRequest("r", "M:\\", "M:\\x")) == frozenset()


def test_unknown_checkpoints_read_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    topology = FakeTopology({"J": (HDD,)})
    topology.install(monkeypatch)

    assert read_disk_scheduling_keys(object()) == frozenset()
    assert read_disk_scheduling_keys(None) == frozenset()
    assert topology.volume_calls == []


def test_a_non_local_root_falls_back_through_core_without_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reader relies on core's local-volume check; a mapped letter adds none."""

    def forbidden(*args):
        raise AssertionError("an I/O-bearing read ran for a non-local root")

    monkeypatch.setattr(disk_topology, "_IS_WINDOWS", True)
    monkeypatch.setattr(
        disk_topology,
        "_query_dos_device",
        lambda name: "\\Device\\LanmanRedirector\\;Z:000\\server\\share",
    )
    monkeypatch.setattr(disk_topology, "current_volume_anchor", forbidden)
    monkeypatch.setattr(disk_topology, "_volume_name_for_mount_point", forbidden)
    monkeypatch.setattr(disk_topology, "_open_zero_access", forbidden)

    assert read_disk_scheduling_keys(
        PlanRequest("r", "Z:\\data", "\\\\server\\share\\b")
    ) == frozenset()


# --- Reference machine: real reads through the real dispatcher -------------

HDD_ROOTS = ("J:\\", "M:\\")
NVME_ROOTS = ("C:\\", "F:\\")


def _real_facts(root: str) -> tuple[DiskFact, ...] | None:
    try:
        return disk_topology.disk_facts(disk_topology.volume_name(root))
    except (OSError, ValueError):
        return None


def _reference_fixture() -> str | None:
    """Return why the reference disks are absent, or ``None`` if present."""

    if os.name != "nt":
        return "the reference disks exist only on the Windows reference machine"
    hdd = [_real_facts(root) for root in HDD_ROOTS]
    if any(not facts for facts in hdd) or hdd[0] != hdd[1]:
        return "J: and M: are not partitions of one readable disk"
    if not all(counts_as_spinning(fact) for fact in hdd[0]):
        return "the disk carrying J: and M: does not count as spinning"
    nvme = [_real_facts(root) for root in NVME_ROOTS]
    if any(not facts for facts in nvme) or any(
        counts_as_spinning(fact) for facts in nvme for fact in facts
    ):
        return "C: and F: are not both readable non-spinning disks"
    return None


class Runs:
    """Record each run's entry with the runs already inside, then gate exit."""

    def __init__(self) -> None:
        self._condition = Condition()
        self.inside: set[str] = set()
        self.overlaps: dict[str, frozenset[str]] = {}
        self.order: list[str] = []
        self.released: set[str] = set()
        self.barriers: dict[str, Barrier] = {}

    def run(self, name: str, context) -> OperationResult:
        with self._condition:
            self.overlaps[name] = frozenset(self.inside)
            self.inside.add(name)
            self.order.append(name)
            self._condition.notify_all()
        try:
            barrier = self.barriers.get(name)
            if barrier is not None:
                # Both members must be inside at once, or this breaks.
                barrier.wait()
            with self._condition:
                assert self._condition.wait_for(
                    lambda: name in self.released, _LIMIT
                ), f"{name} was never released"
        finally:
            with self._condition:
                self.inside.discard(name)
                self._condition.notify_all()
        return OperationResult(SessionState.COMPLETED)

    def started(self, name: str) -> bool:
        with self._condition:
            return self._condition.wait_for(lambda: name in self.order, _LIMIT)

    def release(self, *names: str) -> None:
        with self._condition:
            self.released.update(names)
            self._condition.notify_all()


class CountingReader:
    """The production reader, counted per checkpoint so tests can wait on passes."""

    def __init__(self) -> None:
        self._condition = Condition()
        self.readings: list[tuple[str, frozenset]] = []

    def __call__(self, checkpoint: object) -> frozenset:
        keys = read_disk_scheduling_keys(checkpoint)
        with self._condition:
            self.readings.append((checkpoint.request_id, keys))
            self._condition.notify_all()
        return keys

    def count(self, name: str) -> int:
        with self._condition:
            return sum(1 for read, _ in self.readings if read == name)

    def keys(self, name: str) -> frozenset:
        with self._condition:
            return next(keys for read, keys in reversed(self.readings) if read == name)

    def wait_count(self, name: str, count: int, timeout: float) -> bool:
        with self._condition:
            return self._condition.wait_for(
                lambda: sum(1 for read, _ in self.readings if read == name) >= count,
                timeout,
            )


def _reference_dispatcher(runs: Runs, reader: CountingReader) -> Dispatcher:
    @dataclass
    class Invocation:
        request: PlanRequest

        def run(self, context):
            return runs.run(self.request.request_id, context)

        def snapshot(self):
            return self.request

    registration = WorkflowRegistration(
        prepare=lambda request: PreparedSession(request, frozenset()),
        open=Invocation,
        read_scheduling_keys=reader,
    )
    return Dispatcher(
        {"sync.plan": registration},
        lock_provider=InProcessResourceLockProvider(),
    )


def _more_passes(
    dispatcher: Dispatcher, reader: CountingReader, name: str, session_id
) -> None:
    """Return after two more readings of ``name``, so one whole pass selected.

    Returns early if the session leaves the queue, since it is read no more.
    """

    target = reader.count(name) + 2
    deadline = monotonic() + _LIMIT
    while not reader.wait_count(name, target, 0.01):
        if dispatcher.get(session_id).state is not SessionState.PENDING:
            return
        assert monotonic() < deadline, "scheduler made no further pass"
        with dispatcher._condition:
            dispatcher._condition.notify_all()


def _wait_completed(dispatcher: Dispatcher, session_id) -> None:
    deadline = monotonic() + _LIMIT
    with dispatcher._condition:
        while True:
            record = dispatcher._records[session_id]
            if record.state is SessionState.COMPLETED and record.result is not None:
                return
            remaining = deadline - monotonic()
            assert remaining > 0, f"session did not complete: {record}"
            dispatcher._condition.wait(remaining)


_ABSENT = _reference_fixture()


@pytest.mark.skipif(_ABSENT is not None, reason=f"reference disks absent: {_ABSENT}")
def test_reference_disks_serialize_hdd_partitions_and_overlap_nvme_roots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hdd_disk = _real_facts("J:\\")[0].disk_number
    print()
    for root in HDD_ROOTS + NVME_ROOTS:
        print(
            f"{root} facts={_real_facts(root)} "
            f"keys={sorted(read_disk_scheduling_keys(PlanRequest('r', root, root)))}"
        )

    runs = Runs()
    reader = CountingReader()
    dispatcher = _reference_dispatcher(runs, reader)
    try:
        # Two NVMe-rooted sessions on the same pair of disks run together.
        runs.barriers["nvme-a"] = runs.barriers["nvme-b"] = Barrier(2, timeout=_LIMIT)
        nvme = [
            dispatcher.submit("sync.plan", PlanRequest("nvme-a", "C:\\", "F:\\")),
            dispatcher.submit("sync.plan", PlanRequest("nvme-b", "F:\\", "C:\\")),
        ]
        assert runs.started("nvme-a") and runs.started("nvme-b")
        assert reader.keys("nvme-a") == reader.keys("nvme-b") == frozenset()
        runs.release("nvme-a", "nvme-b")
        for session_id in nvme:
            _wait_completed(dispatcher, session_id)
        assert "nvme-a" in runs.overlaps["nvme-b"] or "nvme-b" in runs.overlaps["nvme-a"]

        # J: and M: share the spinning disk: M waits while J runs.
        j = dispatcher.submit("sync.plan", PlanRequest("on-j", "J:\\", "J:\\"))
        assert runs.started("on-j")
        m = dispatcher.submit("sync.plan", PlanRequest("on-m", "M:\\", "M:\\"))
        _more_passes(dispatcher, reader, "on-m", m)
        assert dispatcher.get(m).state is SessionState.PENDING
        assert reader.keys("on-j") == reader.keys("on-m") == frozenset(
            {("disk", hdd_disk)}
        )
        runs.release("on-j")
        assert runs.started("on-m")
        runs.release("on-m")
        for session_id in (j, m):
            _wait_completed(dispatcher, session_id)
        assert runs.overlaps["on-m"] == frozenset()
        assert runs.order.index("on-j") < runs.order.index("on-m")

        # An unreadable extents read falls back to no keys: J and M overlap.
        real_ioctl = disk_topology._ioctl

        def unreadable_extents(handle, code, request, size):
            if code == disk_topology._IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS:
                raise OSError(21, "injected unreadable extents")
            return real_ioctl(handle, code, request, size)

        monkeypatch.setattr(disk_topology, "_ioctl", unreadable_extents)
        runs.barriers["fallback-j"] = runs.barriers["fallback-m"] = Barrier(
            2, timeout=_LIMIT
        )
        fallback = [
            dispatcher.submit("sync.plan", PlanRequest("fallback-j", "J:\\", "J:\\")),
            dispatcher.submit("sync.plan", PlanRequest("fallback-m", "M:\\", "M:\\")),
        ]
        assert runs.started("fallback-j") and runs.started("fallback-m")
        assert reader.keys("fallback-j") == reader.keys("fallback-m") == frozenset()
        runs.release("fallback-j", "fallback-m")
        for session_id in fallback:
            _wait_completed(dispatcher, session_id)
        assert (
            "fallback-j" in runs.overlaps["fallback-m"]
            or "fallback-m" in runs.overlaps["fallback-j"]
        )
        # Keys stay out of every record, checkpoint and result.
        for session_id in nvme + [j, m] + fallback:
            assert "'disk'" not in repr(dispatcher.get(session_id))
    finally:
        for barrier in runs.barriers.values():
            barrier.abort()
        runs.release(*runs.barriers, "on-j", "on-m")
        result = dispatcher.shutdown(_LIMIT)
    assert result.complete, result
