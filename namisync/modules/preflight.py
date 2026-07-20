"""Scoped read-only observation and pure M0 execution judgment."""

from __future__ import annotations

import os
import shutil
import stat as stat_module
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Protocol

from namisync.core.evidence import Outcome
from namisync.core.execution import ExecutionSet
from namisync.core.models import (
    CapabilityProfile,
    EntryKind,
    FileIdentity,
    FileStat,
    MetadataSnapshot,
    Root,
    VolumeEvidence,
    VolumeId,
    owned_temp_run_id,
)
from namisync.core.pathing import (
    is_path_below,
    join_under_root,
    normalize_relative_path,
    validate_relative_path,
)
from namisync.core.planning import (
    FilterSet,
    OperationKind,
    PlanOperation,
    calculate_required_bytes,
    quarantined_operation_ids,
)
from namisync.core.preflight import (
    ObservedWorld,
    Refusal,
    RefusalCode,
    RootObservation,
    StatObservation,
    Subject,
    TrashObservation,
    Verdict,
)


class SettingsReader(Protocol):
    def read_filters(self) -> FilterSet: ...

    def read_policy_fingerprint(self) -> str: ...


class ObservationFileSystem(Protocol):
    def observe_root(self, root: Root) -> RootObservation: ...

    def stat(self, root: Root, rel_path: str, profile: CapabilityProfile) -> StatObservation: ...

    def free_space(self, target: Root) -> int: ...

    def reclaimable_temp_bytes(
        self,
        target: Root,
        parent_paths: frozenset[str],
        current_run_id: str,
    ) -> int: ...

    def observe_trash(self, target: Root, expected_volume: VolumeId | None) -> TrashObservation: ...

    def now_utc(self) -> datetime: ...


class StaticSettingsReader:
    def __init__(self, filters: FilterSet, policy_fingerprint: str) -> None:
        self._filters = filters
        self._policy_fingerprint = policy_fingerprint

    def read_filters(self) -> FilterSet:
        return self._filters

    def read_policy_fingerprint(self) -> str:
        return self._policy_fingerprint


def _volume_observation(path: str) -> tuple[VolumeId, VolumeEvidence]:
    if os.name != "nt":
        observed = os.stat(path, follow_symlinks=False)
        return VolumeId(f"{observed.st_dev:x}", "UNKNOWN"), VolumeEvidence(device_id=str(Path(path).anchor))

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    volume_path = ctypes.create_unicode_buffer(32768)
    if not kernel32.GetVolumePathNameW(path, volume_path, len(volume_path)):
        raise OSError(ctypes.get_last_error(), "GetVolumePathNameW failed", path)
    label = ctypes.create_unicode_buffer(261)
    filesystem = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    max_component = wintypes.DWORD()
    flags = wintypes.DWORD()
    if not kernel32.GetVolumeInformationW(
        volume_path.value,
        label,
        len(label),
        ctypes.byref(serial),
        ctypes.byref(max_component),
        ctypes.byref(flags),
        filesystem,
        len(filesystem),
    ):
        raise OSError(ctypes.get_last_error(), "GetVolumeInformationW failed", path)
    fs_type = filesystem.value.upper() or "UNKNOWN"
    return VolumeId(f"{serial.value:08X}", fs_type), VolumeEvidence(label.value or None, volume_path.value)


class LocalObservationFileSystem:
    """Read-only local observation implementation used by composition roots."""

    def observe_root(self, root: Root) -> RootObservation:
        try:
            resolved = str(Path(root.path).resolve(strict=True))
            if not Path(resolved).is_dir():
                raise NotADirectoryError(resolved)
            volume_id, evidence = _volume_observation(resolved)
            return RootObservation(resolved, volume_id, evidence)
        except (OSError, PermissionError) as error:
            return RootObservation(None, None, None, str(error))

    def stat(self, root: Root, rel_path: str, profile: CapabilityProfile) -> StatObservation:
        try:
            canonical = validate_relative_path(rel_path)
            candidate = join_under_root(root.path, canonical)
            resolved_root = str(Path(root.path).resolve(strict=True))
            resolved_candidate = str(Path(candidate).resolve(strict=False))
            contained = is_path_below(resolved_candidate, resolved_root)
            representable = len(resolved_candidate) <= profile.max_path
            if not contained:
                return StatObservation(None, "resolved path escapes root", False, representable)
            try:
                observed = os.stat(candidate, follow_symlinks=False)
            except FileNotFoundError:
                return StatObservation(None, None, True, representable)
            if stat_module.S_ISREG(observed.st_mode):
                kind = EntryKind.FILE
                size = int(observed.st_size)
            elif stat_module.S_ISDIR(observed.st_mode):
                kind = EntryKind.DIRECTORY
                size = 0
            else:
                return StatObservation(None, "unsupported entry type", True, representable)
            volume_id, _ = _volume_observation(root.path)
            identity = (
                FileIdentity(volume_id.serial, int(observed.st_ino))
                if profile.stable_file_identity and int(observed.st_ino) > 0
                else None
            )
            attributes = int(getattr(observed, "st_file_attributes", 0))
            created = getattr(observed, "st_birthtime_ns", None)
            if created is None and os.name == "nt":
                created = getattr(observed, "st_ctime_ns", None)
            snapshot = FileStat(
                kind,
                size,
                int(observed.st_mtime_ns),
                identity,
                max(1, int(getattr(observed, "st_nlink", 1))),
                MetadataSnapshot(attributes, int(created) if created is not None else None),
            )
            return StatObservation(snapshot, None, True, representable)
        except (OSError, PermissionError, ValueError) as error:
            return StatObservation(None, str(error), True, False)

    def free_space(self, target: Root) -> int:
        return int(shutil.disk_usage(target.path).free)

    def reclaimable_temp_bytes(
        self,
        target: Root,
        parent_paths: frozenset[str],
        current_run_id: str,
    ) -> int:
        total = 0
        target_volume, _ = _volume_observation(target.path)
        for parent_path in sorted(parent_paths, key=lambda value: (normalize_relative_path(value, allow_root=True), value)):
            if parent_path and (
                normalize_relative_path(parent_path) == ".SYNCTRASH"
                or normalize_relative_path(parent_path).startswith(".SYNCTRASH\\")
            ):
                continue
            absolute = target.path if not parent_path else join_under_root(target.path, parent_path)
            try:
                parent_volume, _ = _volume_observation(absolute)
                if parent_volume != target_volume:
                    continue
                with os.scandir(absolute) as entries:
                    for entry in entries:
                        owner = owned_temp_run_id(entry.name)
                        if (
                            owner is not None
                            and owner != current_run_id
                            and entry.is_file(follow_symlinks=False)
                        ):
                            total += int(entry.stat(follow_symlinks=False).st_size)
            except (FileNotFoundError, PermissionError, NotADirectoryError):
                continue
        return total

    def observe_trash(self, target: Root, expected_volume: VolumeId | None) -> TrashObservation:
        trash = os.path.join(target.path, ".synctrash")
        try:
            root_resolved = str(Path(target.path).resolve(strict=True))
            trash_path = Path(trash)
            exists = trash_path.exists()
            resolved = str(trash_path.resolve(strict=False))
            contained = is_path_below(resolved, root_resolved)
            junction = bool(exists and hasattr(trash_path, "is_junction") and trash_path.is_junction())
            attributes = int(getattr(os.lstat(trash), "st_file_attributes", 0)) if exists else 0
            reparse_safe = not exists or not (
                trash_path.is_symlink() or junction or attributes & 0x00000400
            )
            available = not exists or trash_path.is_dir()
            writable_path = trash if exists else target.path
            writable = os.access(writable_path, os.W_OK)
            actual_volume, _ = _volume_observation(resolved if exists else target.path)
            same_volume = expected_volume is not None and actual_volume == expected_volume
            return TrashObservation(resolved, available, contained, same_volume, writable, reparse_safe)
        except (OSError, PermissionError) as error:
            return TrashObservation(None, False, False, False, False, False, str(error))

    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)


def _operation_subjects(xset: ExecutionSet) -> tuple[dict[Subject, tuple[Root, str, CapabilityProfile]], frozenset[str]]:
    subjects: dict[Subject, tuple[Root, str, CapabilityProfile]] = {}
    target_parents: set[str] = set()
    plan = xset.plan
    for operation in xset.remaining():
        if operation.source_rel_path is not None:
            subject = Subject(plan.source_root.root_id, normalize_relative_path(operation.source_rel_path))
            subjects[subject] = (plan.source_root, operation.source_rel_path, plan.source_profile)
        target_subject = Subject(plan.target_root.root_id, normalize_relative_path(operation.target_rel_path))
        subjects[target_subject] = (plan.target_root, operation.target_rel_path, plan.target_profile)
        parent = str(PureWindowsPath(operation.target_rel_path).parent)
        parent = "" if parent == "." else parent
        target_parents.add(parent)
        if parent:
            parent_subject = Subject(plan.target_root.root_id, normalize_relative_path(parent))
            subjects.setdefault(parent_subject, (plan.target_root, parent, plan.target_profile))
        if operation.prior_target_rel_path is not None:
            prior_subject = Subject(plan.target_root.root_id, normalize_relative_path(operation.prior_target_rel_path))
            subjects[prior_subject] = (plan.target_root, operation.prior_target_rel_path, plan.target_profile)
            prior_parent = str(PureWindowsPath(operation.prior_target_rel_path).parent)
            prior_parent = "" if prior_parent == "." else prior_parent
            target_parents.add(prior_parent)
            if prior_parent:
                parent_subject = Subject(plan.target_root.root_id, normalize_relative_path(prior_parent))
                subjects.setdefault(parent_subject, (plan.target_root, prior_parent, plan.target_profile))
    return subjects, frozenset(target_parents)


def observe(
    xset: ExecutionSet,
    fs: ObservationFileSystem,
    settings: SettingsReader,
) -> ObservedWorld:
    """Read the current scoped world without making any safety decision."""

    subjects, target_parents = _operation_subjects(xset)
    stats: dict[Subject, StatObservation] = {}
    paths: dict[Subject, str] = {}
    for subject, (root, rel_path, profile) in sorted(subjects.items()):
        try:
            stats[subject] = fs.stat(root, rel_path, profile)
        except (OSError, PermissionError, ValueError) as error:
            stats[subject] = StatObservation(None, str(error))
        paths[subject] = rel_path
    roots: dict[str, RootObservation] = {}
    for root in (xset.plan.source_root, xset.plan.target_root):
        try:
            roots[root.root_id] = fs.observe_root(root)
        except (OSError, PermissionError, ValueError) as error:
            roots[root.root_id] = RootObservation(None, None, None, str(error))
    try:
        free_space = fs.free_space(xset.plan.target_root)
    except (OSError, PermissionError):
        free_space = None
    try:
        reclaimable = fs.reclaimable_temp_bytes(
            xset.plan.target_root,
            target_parents,
            str(xset.run_id),
        )
    except (OSError, PermissionError):
        reclaimable = 0
    remaining = xset.remaining()
    needs_trash = any(
        operation.kind is OperationKind.TRASH
        or (
            xset.plan.trash_on_update
            and operation.kind in {OperationKind.UPDATE, OperationKind.MOVE_UPDATE}
        )
        for operation in remaining
    )
    if needs_trash:
        try:
            trash = fs.observe_trash(xset.plan.target_root, xset.plan.target_volume_id)
        except (OSError, PermissionError, ValueError) as error:
            trash = TrashObservation(None, False, False, False, False, False, str(error))
    else:
        trash = None
    settings_error = None
    try:
        current_filters = settings.read_filters()
        current_policy_fingerprint = settings.read_policy_fingerprint()
    except (OSError, PermissionError, ValueError) as error:
        current_filters = xset.plan.filter_snapshot
        current_policy_fingerprint = xset.plan.policy_fingerprint
        settings_error = str(error)
    return ObservedWorld(
        stats=stats,
        paths=paths,
        target_parent_paths=target_parents,
        roots=roots,
        free_space=free_space,
        reclaimable_temp_bytes=reclaimable,
        trash=trash,
        current_filters=current_filters,
        current_policy_fingerprint=current_policy_fingerprint,
        observed_at=fs.now_utc(),
        settings_error=settings_error,
    )


def _paths_overlap(first: str, second: str) -> bool:
    first_norm = os.path.normcase(os.path.abspath(first))
    second_norm = os.path.normcase(os.path.abspath(second))
    try:
        common = os.path.normcase(os.path.commonpath((first_norm, second_norm)))
    except ValueError:
        return False
    return common in {first_norm, second_norm}


def _add_stat_refusals(
    refusals: list[Refusal],
    operation: PlanOperation,
    subject: Subject,
    observation: StatObservation | None,
    expected: FileStat | None,
    *,
    source_subject: bool,
    granularity_ns: int,
) -> None:
    if observation is None or observation.error is not None:
        refusals.append(
            Refusal(RefusalCode.OBSERVATION_UNAVAILABLE, operation.op_id, subject, observation.error if observation else "missing observation")
        )
        return
    if not observation.contained:
        refusals.append(Refusal(RefusalCode.PATH_ESCAPE, operation.op_id, subject))
    if not observation.representable:
        refusals.append(Refusal(RefusalCode.PATH_UNREPRESENTABLE, operation.op_id, subject))
    actual = observation.stat
    if expected is None:
        if actual is not None:
            refusals.append(Refusal(RefusalCode.DESTINATION_APPEARED, operation.op_id, subject))
        return
    if actual is None:
        code = RefusalCode.SOURCE_DRIFT if source_subject else RefusalCode.TARGET_DRIFT
        refusals.append(Refusal(code, operation.op_id, subject, "expected entry is absent"))
        return
    if actual.kind is not expected.kind:
        refusals.append(Refusal(RefusalCode.TYPE_CHANGED, operation.op_id, subject))
    if (
        expected.file_identity is not None
        and actual.file_identity != expected.file_identity
    ):
        refusals.append(Refusal(RefusalCode.IDENTITY_CHANGED, operation.op_id, subject))
    if actual.size != expected.size:
        refusals.append(Refusal(RefusalCode.SIZE_CHANGED, operation.op_id, subject))
    if abs(actual.mtime_ns - expected.mtime_ns) > granularity_ns:
        refusals.append(Refusal(RefusalCode.MTIME_CHANGED, operation.op_id, subject))
    if actual.metadata != expected.metadata or actual.nlink != expected.nlink:
        refusals.append(Refusal(RefusalCode.METADATA_CHANGED, operation.op_id, subject))


def preflight(xset: ExecutionSet, world: ObservedWorld) -> Verdict:
    """Purely judge all applicable refusal reasons for an execution set."""

    plan = xset.plan
    refusals: list[Refusal] = []
    source_root = world.roots.get(plan.source_root.root_id)
    target_root = world.roots.get(plan.target_root.root_id)
    for expected, observed in ((plan.source_volume_id, source_root), (plan.target_volume_id, target_root)):
        if observed is None or observed.error is not None or observed.resolved_path is None:
            refusals.append(Refusal(RefusalCode.ROOT_UNAVAILABLE, detail=observed.error if observed else "missing root observation"))
            continue
        if observed.volume_evidence is not None and observed.volume_evidence.clone_ambiguous:
            refusals.append(Refusal(RefusalCode.VOLUME_CLONE_AMBIGUOUS))
        if expected is None or observed.volume_id != expected:
            refusals.append(Refusal(RefusalCode.ROOT_CHANGED))
    if (
        source_root is not None
        and target_root is not None
        and source_root.resolved_path is not None
        and target_root.resolved_path is not None
        and _paths_overlap(source_root.resolved_path, target_root.resolved_path)
    ):
        refusals.append(Refusal(RefusalCode.ROOTS_OVERLAP))

    if world.current_filters != plan.filter_snapshot:
        refusals.append(Refusal(RefusalCode.FILTER_DRIFT))
    if world.current_policy_fingerprint != plan.policy_fingerprint:
        refusals.append(Refusal(RefusalCode.OPTIONS_DRIFT))
    if world.settings_error is not None:
        refusals.append(
            Refusal(
                RefusalCode.OBSERVATION_UNAVAILABLE,
                detail=f"semantic settings unavailable: {world.settings_error}",
            )
        )

    operations_by_id = {operation.op_id: operation for operation in plan.operations}
    remaining = xset.remaining()
    remaining_ids = {operation.op_id for operation in remaining}
    quarantined = quarantined_operation_ids(plan.operations)
    direct_target_subjects: set[Subject] = set()
    created_directory_keys = {
        normalize_relative_path(operation.target_rel_path)
        for operation in remaining
        if operation.kind is OperationKind.MKDIR
    }
    unavailable = {
        Outcome.FAILED,
        Outcome.CANCELED,
        Outcome.DEFERRED,
        Outcome.BLOCKED,
    }
    for operation in remaining:
        if operation.kind in {
            OperationKind.MOVE,
            OperationKind.MOVE_UPDATE,
            OperationKind.TRASH,
            OperationKind.DELETE,
        }:
            if not plan.source_complete:
                refusals.append(
                    Refusal(RefusalCode.INCOMPLETE_SOURCE_SCAN, operation.op_id)
                )
            if not plan.target_complete:
                refusals.append(
                    Refusal(RefusalCode.INCOMPLETE_TARGET_SCAN, operation.op_id)
                )
        if operation.blocked:
            refusals.append(Refusal(RefusalCode.OPERATION_BLOCKED, operation.op_id, detail=operation.blocked_reason.value))
        elif operation.op_id in quarantined:
            refusals.append(
                Refusal(RefusalCode.BLOCKED_CORRESPONDENCE, operation.op_id)
            )
        for dependency in operation.dependencies:
            if dependency not in xset.selection:
                refusals.append(Refusal(RefusalCode.SELECTION_NOT_CLOSED, operation.op_id, detail=str(dependency)))
                continue
            dependency_status = xset.status.get(dependency)
            dependency_operation = operations_by_id.get(dependency)
            if dependency_status in unavailable or (dependency_operation is not None and dependency_operation.blocked):
                refusals.append(Refusal(RefusalCode.DEPENDENCY_UNAVAILABLE, operation.op_id, detail=str(dependency)))
            elif dependency_status is None and dependency not in remaining_ids:
                refusals.append(Refusal(RefusalCode.DEPENDENCY_UNAVAILABLE, operation.op_id, detail=str(dependency)))

        if operation.source_rel_path is not None and operation.source_expected is not None:
            subject = Subject(plan.source_root.root_id, normalize_relative_path(operation.source_rel_path))
            _add_stat_refusals(
                refusals,
                operation,
                subject,
                world.stats.get(subject),
                operation.source_expected,
                source_subject=True,
                granularity_ns=plan.source_profile.mtime_granularity_ns,
            )
        target_subject = Subject(plan.target_root.root_id, normalize_relative_path(operation.target_rel_path))
        direct_target_subjects.add(target_subject)
        _add_stat_refusals(
            refusals,
            operation,
            target_subject,
            world.stats.get(target_subject),
            operation.target_expected,
            source_subject=False,
            granularity_ns=plan.target_profile.mtime_granularity_ns,
        )
        if operation.prior_target_rel_path is not None:
            prior_subject = Subject(plan.target_root.root_id, normalize_relative_path(operation.prior_target_rel_path))
            direct_target_subjects.add(prior_subject)
            _add_stat_refusals(
                refusals,
                operation,
                prior_subject,
                world.stats.get(prior_subject),
                operation.prior_target_expected,
                source_subject=False,
                granularity_ns=plan.target_profile.mtime_granularity_ns,
            )

    for subject, rel_path in world.paths.items():
        if subject.root_id != plan.target_root.root_id or subject in direct_target_subjects:
            continue
        observation = world.stats.get(subject)
        if observation is None or observation.error is not None:
            refusals.append(
                Refusal(
                    RefusalCode.OBSERVATION_UNAVAILABLE,
                    subject=subject,
                    detail=observation.error if observation else "missing parent observation",
                )
            )
            continue
        if not observation.contained:
            refusals.append(Refusal(RefusalCode.PATH_ESCAPE, subject=subject))
        if not observation.representable:
            refusals.append(Refusal(RefusalCode.PATH_UNREPRESENTABLE, subject=subject))
        if observation.stat is None and normalize_relative_path(rel_path) not in created_directory_keys:
            refusals.append(Refusal(RefusalCode.TARGET_DRIFT, subject=subject, detail="required parent is absent"))
        elif observation.stat is not None and observation.stat.kind is not EntryKind.DIRECTORY:
            refusals.append(Refusal(RefusalCode.TYPE_CHANGED, subject=subject, detail="required parent is not a directory"))

    required_bytes = calculate_required_bytes(
        remaining,
        target_profile=plan.target_profile,
        trash_on_update=plan.trash_on_update,
    )
    if world.free_space is None:
        refusals.append(Refusal(RefusalCode.OBSERVATION_UNAVAILABLE, detail="target free space unavailable"))
    elif required_bytes > world.free_space + world.reclaimable_temp_bytes:
        refusals.append(
            Refusal(
                RefusalCode.INSUFFICIENT_SPACE,
                detail=f"required={required_bytes}; available={world.free_space + world.reclaimable_temp_bytes}",
            )
        )

    needs_trash = any(
        operation.kind is OperationKind.TRASH
        or (plan.trash_on_update and operation.kind in {OperationKind.UPDATE, OperationKind.MOVE_UPDATE})
        for operation in remaining
    )
    if needs_trash:
        trash = world.trash
        if trash is None or not trash.available:
            refusals.append(Refusal(RefusalCode.TRASH_UNAVAILABLE, detail=trash.error if trash else "missing trash observation"))
        if trash is not None:
            if not trash.contained:
                refusals.append(Refusal(RefusalCode.TRASH_ESCAPE))
            if not trash.same_volume:
                refusals.append(Refusal(RefusalCode.TRASH_OFF_VOLUME))
            if not trash.writable:
                refusals.append(Refusal(RefusalCode.TRASH_NOT_WRITABLE))
            if not trash.reparse_safe:
                refusals.append(Refusal(RefusalCode.TRASH_REPARSE))

    unique = {
        (refusal.code, refusal.op_id, refusal.subject, refusal.detail): refusal for refusal in refusals
    }
    ordered = tuple(
        sorted(
            unique.values(),
            key=lambda refusal: (
                refusal.code.value,
                str(refusal.op_id or ""),
                refusal.subject or Subject("", ""),
                refusal.detail,
            ),
        )
    )
    return Verdict(not ordered, ordered, world)
