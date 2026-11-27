from __future__ import annotations

import os
import struct

import pytest

import namisync.core.disk_topology as disk_topology
from namisync.core.disk_topology import (
    BUS_TYPE_USB,
    DiskFact,
    counts_as_spinning,
    disk_facts,
    volume_name,
)


GUID_NAME = "\\\\?\\Volume{0a1b2c3d-1111-2222-3333-444455556666}\\"
BUS_SATA = 11
BUS_NVME = 17


def _extents(*disks: int, pad: int = 0) -> bytes:
    body = b"".join(
        struct.pack("<I4xqq", disk, 0, 1 << 30) for disk in disks
    )
    return struct.pack("<I4x", len(disks)) + body + b"\0" * pad


def _descriptor(bus_type: int) -> bytes:
    return struct.pack("<IIBBBBIIIII", 1, 40, 0, 0, 0, 0, 0, 0, 0, 0, bus_type)


def _seek_descriptor(penalty: int) -> bytes:
    return struct.pack("<IIB3x", 1, 12, penalty)


class FakeNative:
    """Records handle lifetime and answers the patched native seam."""

    def __init__(
        self,
        extents: bytes | OSError,
        disks: dict[int, tuple[bytes | OSError, bytes | OSError] | OSError],
    ) -> None:
        self.extents = extents
        self.disks = disks
        self.next_handle = 100
        self.paths: dict[int, str] = {}
        self.opened: list[str] = []
        self.closed: list[int] = []
        self.requests: list[tuple[str, int, bytes | None, int]] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(disk_topology, "_IS_WINDOWS", True)
        monkeypatch.setattr(disk_topology, "_open_zero_access", self.open)
        monkeypatch.setattr(disk_topology, "_close_handle", self.close)
        monkeypatch.setattr(disk_topology, "_ioctl", self.ioctl)

    def open(self, path: str) -> int:
        self.opened.append(path)
        if path.startswith("\\\\.\\PhysicalDrive"):
            outcome = self.disks[int(path.removeprefix("\\\\.\\PhysicalDrive"))]
            if isinstance(outcome, OSError):
                raise outcome
        handle = self.next_handle
        self.next_handle += 1
        self.paths[handle] = path
        return handle

    def close(self, handle: int) -> None:
        self.closed.append(handle)

    def ioctl(
        self, handle: int, code: int, request: bytes | None, size: int
    ) -> bytes:
        path = self.paths[handle]
        self.requests.append((path, code, request, size))
        if code == disk_topology._IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS:
            reply = self.extents
        else:
            assert code == disk_topology._IOCTL_STORAGE_QUERY_PROPERTY
            assert request is not None
            device, seek = self.disks[
                int(path.removeprefix("\\\\.\\PhysicalDrive"))
            ]
            (property_id,) = struct.unpack_from("<I", request)
            reply = device if property_id == 0 else seek
        if isinstance(reply, OSError):
            raise reply
        return reply


@pytest.mark.parametrize("bus_type", [None, 0, BUS_TYPE_USB, BUS_SATA, BUS_NVME])
@pytest.mark.parametrize("seek_penalty", [None, True, False])
def test_counts_as_spinning_is_false_only_for_known_nonusb_without_seek_penalty(
    bus_type: int | None, seek_penalty: bool | None
) -> None:
    expected_nonspinning = (
        bus_type in (BUS_SATA, BUS_NVME) and seek_penalty is False
    )
    assert (
        counts_as_spinning(DiskFact(0, bus_type, seek_penalty))
        is not expected_nonspinning
    )


def test_disk_facts_reads_bus_and_seek_penalty_for_each_distinct_disk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FakeNative(
        _extents(3, 1, 3),
        {
            1: (_descriptor(BUS_SATA), _seek_descriptor(1)),
            3: (_descriptor(BUS_NVME), _seek_descriptor(0)),
        },
    )
    native.install(monkeypatch)

    facts = disk_facts(GUID_NAME)

    assert facts == (
        DiskFact(1, BUS_SATA, True),
        DiskFact(3, BUS_NVME, False),
    )
    assert native.opened == [
        GUID_NAME.rstrip("\\"),
        "\\\\.\\PhysicalDrive1",
        "\\\\.\\PhysicalDrive3",
    ]
    queries = [r for r in native.requests if r[2] is not None]
    assert [struct.unpack_from("<II", r[2]) for r in queries] == [
        (0, 0),
        (7, 0),
        (0, 0),
        (7, 0),
    ]
    assert sorted(native.closed) == sorted(native.paths)


def test_disk_facts_accepts_a_volume_name_without_its_trailing_separator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FakeNative(
        _extents(1), {1: (_descriptor(BUS_SATA), _seek_descriptor(1))}
    )
    native.install(monkeypatch)

    assert disk_facts(GUID_NAME.rstrip("\\")) == (DiskFact(1, BUS_SATA, True),)
    assert native.opened[0] == GUID_NAME.rstrip("\\")


@pytest.mark.parametrize(
    "name",
    ["C:\\", "\\\\.\\PhysicalDrive0", "\\\\?\\Volume{nope}\\", GUID_NAME + "x"],
)
def test_disk_facts_refuses_a_name_that_is_not_a_volume_guid_name(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    native = FakeNative(_extents(), {})
    native.install(monkeypatch)

    with pytest.raises(ValueError):
        disk_facts(name)
    assert native.opened == []


def test_disk_facts_raises_when_the_extents_reply_overflows_the_buffer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FakeNative(OSError(234, "DeviceIoControl failed"), {})
    native.install(monkeypatch)

    with pytest.raises(OSError):
        disk_facts(GUID_NAME)
    assert native.requests[0][3] == 4096
    assert native.closed == list(native.paths)
    assert len(native.opened) == 1


@pytest.mark.parametrize(
    "reply",
    [b"", b"\x01\0\0\0", struct.pack("<I4x", 2) + b"\0" * 24],
    ids=["empty", "header-cut", "count-exceeds-reply"],
)
def test_disk_facts_raises_when_the_extents_reply_is_truncated(
    monkeypatch: pytest.MonkeyPatch, reply: bytes
) -> None:
    native = FakeNative(reply, {})
    native.install(monkeypatch)

    with pytest.raises(OSError):
        disk_facts(GUID_NAME)
    assert native.closed == list(native.paths)


def test_disk_facts_raises_when_the_volume_cannot_be_opened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(path: str) -> int:
        raise OSError(5, "CreateFileW failed", path)

    monkeypatch.setattr(disk_topology, "_IS_WINDOWS", True)
    monkeypatch.setattr(disk_topology, "_open_zero_access", refuse)

    with pytest.raises(OSError):
        disk_facts(GUID_NAME)


def test_disk_facts_raises_when_the_reply_names_no_extent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FakeNative(_extents(), {})
    native.install(monkeypatch)

    with pytest.raises(OSError):
        disk_facts(GUID_NAME)
    assert native.closed == list(native.paths)


def test_a_physical_drive_that_cannot_be_opened_is_an_unknown_fact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FakeNative(
        _extents(0, 2),
        {
            0: OSError(5, "CreateFileW failed"),
            2: (_descriptor(BUS_NVME), _seek_descriptor(0)),
        },
    )
    native.install(monkeypatch)

    facts = disk_facts(GUID_NAME)

    assert facts == (DiskFact(0, None, None), DiskFact(2, BUS_NVME, False))
    assert counts_as_spinning(facts[0]) is True
    assert counts_as_spinning(facts[1]) is False
    assert sorted(native.closed) == sorted(native.paths)


@pytest.mark.parametrize(
    ("device", "seek", "expected"),
    [
        (OSError(1, "failed"), _seek_descriptor(0), DiskFact(4, None, False)),
        (_descriptor(BUS_SATA), OSError(1, "failed"), DiskFact(4, BUS_SATA, None)),
        (b"\0" * 16, _seek_descriptor(1), DiskFact(4, None, True)),
        (_descriptor(BUS_SATA)[:28], _seek_descriptor(1), DiskFact(4, None, True)),
        (_descriptor(BUS_SATA)[:31], _seek_descriptor(1), DiskFact(4, None, True)),
        (_descriptor(BUS_SATA), b"\0" * 8, DiskFact(4, BUS_SATA, None)),
        (OSError(1, "failed"), OSError(1, "failed"), DiskFact(4, None, None)),
    ],
    ids=[
        "device-query-fails",
        "seek-query-fails",
        "device-reply-short",
        "device-reply-ends-at-bus-type",
        "device-reply-cuts-bus-type",
        "seek-reply-short",
        "both-fail",
    ],
)
def test_a_failed_property_query_leaves_only_that_field_unknown(
    monkeypatch: pytest.MonkeyPatch,
    device: bytes | OSError,
    seek: bytes | OSError,
    expected: DiskFact,
) -> None:
    native = FakeNative(_extents(4), {4: (device, seek)})
    native.install(monkeypatch)

    assert disk_facts(GUID_NAME) == (expected,)
    assert sorted(native.closed) == sorted(native.paths)


def test_handles_close_when_a_property_query_raises_unexpectedly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = FakeNative(
        _extents(0), {0: (_descriptor(BUS_SATA), _seek_descriptor(0))}
    )
    native.install(monkeypatch)
    answer = native.ioctl

    def explode(handle: int, code: int, request: bytes | None, size: int) -> bytes:
        if native.paths[handle].startswith("\\\\.\\PhysicalDrive"):
            raise RuntimeError("unexpected")
        return answer(handle, code, request, size)

    monkeypatch.setattr(disk_topology, "_ioctl", explode)

    with pytest.raises(RuntimeError):
        disk_facts(GUID_NAME)
    assert sorted(native.closed) == sorted(native.paths)
    assert len(native.closed) == 2


def test_off_windows_disk_facts_are_empty_and_volume_name_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(disk_topology, "_IS_WINDOWS", False)

    assert disk_facts(GUID_NAME) == ()
    with pytest.raises(OSError):
        volume_name("C:\\")


def test_volume_name_looks_up_the_mount_point_of_the_roots_volume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    looked_up: list[str] = []

    def lookup(mount_point: str) -> str:
        looked_up.append(mount_point)
        return GUID_NAME

    monkeypatch.setattr(disk_topology, "_IS_WINDOWS", True)
    monkeypatch.setattr(
        disk_topology, "current_volume_anchor", lambda root: "D:\\mount"
    )
    monkeypatch.setattr(disk_topology, "_volume_name_for_mount_point", lookup)

    assert volume_name("D:\\mount\\data") == GUID_NAME
    assert looked_up == ["D:\\mount\\"]


@pytest.mark.skipif(os.name != "nt", reason="Windows native volume topology")
def test_the_system_volume_reports_at_least_one_disk() -> None:
    name = volume_name("C:\\")

    assert name.startswith("\\\\?\\Volume{")
    facts = disk_facts(name)
    assert len(facts) >= 1
    assert all(type(fact.disk_number) is int for fact in facts)
