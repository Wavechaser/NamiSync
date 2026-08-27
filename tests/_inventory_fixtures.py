"""Shared inventory runtime fixtures for workflow and interface tests."""

from __future__ import annotations

from pathlib import Path
from time import monotonic, sleep

from namisync.core.models import (
    CapabilityProfile,
    FileIdentity,
    FileRecord,
    IgnoreSet,
    MetadataSnapshot,
    Root,
    ScanResult,
    ScanScope,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.recording import HostCommand, LocationCommand, VolumeCommand
from namisync.core.session import RunContext, SessionState
from namisync.db.recorder import LedgerRecorder
from namisync.db.schema import initialize_history
from namisync.dispatcher import Dispatcher
from namisync.workflows.inventory import MountedVolume
from namisync.workflows.runtime import LocalWorkflowRuntime

from _db_fixtures import FakeClock, NOW


VOLUME_ID = VolumeId("runtime-volume", "NTFS")
PROFILE = CapabilityProfile("NTFS", 100, True, False, 32767, True, True)


def _file(path: str, index: int) -> FileRecord:
    return FileRecord(
        path,
        normalize_relative_path(path),
        7,
        11 + index,
        FileIdentity(VOLUME_ID.serial, index),
        1,
        MetadataSnapshot(0, 3),
    )


class _Resolver:
    def __init__(self, *mounts: Path) -> None:
        self.mounts = tuple(mounts)

    def mounted_volumes(
        self, volume_id: VolumeId, hints: tuple[str, ...] = ()
    ) -> tuple[MountedVolume, ...]:
        assert volume_id == VOLUME_ID
        return tuple(
            MountedVolume(
                str(mount),
                VolumeEvidence("Runtime", str(mount)),
            )
            for mount in self.mounts
        )

    def probe_root(self, root_path: str) -> None:
        next(Path(root_path).iterdir(), None)


class _Scanner:
    def __init__(self, mount: Path, records: tuple[FileRecord, ...]) -> None:
        self.mount = mount
        self.records = records
        self.calls: list[ScanScope] = []

    def __call__(
        self,
        root: Root,
        ignores: IgnoreSet,
        context: RunContext,
        scope: ScanScope | None,
        *,
        trusted_anchor: str | None = None,
        population_admission=None,
    ) -> ScanResult:
        assert scope is not None
        assert trusted_anchor == str(self.mount)
        self.calls.append(scope)
        selected = set(scope.selected_paths)
        records = (
            self.records
            if not selected
            else tuple(row for row in self.records if row.rel_path in selected)
        )
        if population_admission is not None:
            population_admission.require_source_rows(len(records))
            population_admission.require_informational_source_rows(0)
        return ScanResult(
            root,
            VOLUME_ID,
            VolumeEvidence("Runtime", str(self.mount)),
            PROFILE,
            records,
            (),
            (),
            (),
            scope,
            True,
        )


def _seed_location(ledger: Path, mount: Path) -> int:
    with LedgerRecorder(ledger, clock=FakeClock()) as recorder:
        host_id = recorder.ensure_host(HostCommand("host", "Host", NOW))
        assert host_id > 0
        volume_id = recorder.observe_volume(
            VolumeCommand(
                VOLUME_ID,
                VolumeEvidence("Runtime", str(mount)),
                NOW,
            )
        )
        return recorder.ensure_location(
            LocationCommand(volume_id, "managed", NOW)
        )


def _wait_for(
    dispatcher: Dispatcher,
    session_id,
    state: SessionState,
    timeout: float = 2.0,
):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        record = dispatcher.get(session_id)
        if record.state is state and (
            state
            not in {
                SessionState.COMPLETED,
                SessionState.FAILED,
                SessionState.CANCELED,
                SessionState.REFUSED,
            }
            or record.result is not None
        ):
            return record
        sleep(0.005)
    raise AssertionError(f"session did not reach {state}: {dispatcher.get(session_id)}")


def _runtime(
    tmp_path: Path,
    resolver: _Resolver,
    scanner: _Scanner,
    runners,
) -> tuple[LocalWorkflowRuntime, int]:
    ledger = tmp_path / "ledger.db"
    location_id = _seed_location(ledger, scanner.mount)
    initialize_history(tmp_path / "history.db")
    runtime = LocalWorkflowRuntime(
        ledger,
        tmp_path / "history.db",
        clock=FakeClock(),
        host_key="host",
        host_name="Host",
        mounted_volume_resolver=resolver,
        inventory_scanner=scanner,
        integrity_runners=runners,
    )
    return runtime, location_id
