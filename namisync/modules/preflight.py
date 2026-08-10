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
    from_extended_length_path,
    is_path_below,
    join_under_root,
    lexical_absolute_path,
    logical_error_text,
    normalize_relative_path,
    to_extended_length_path,
    validate_relative_path,
)
from namisync.core.planning import (
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
from namisync.core.root_authority import (
    RootAuthority,
    RootAuthorityError,
    RootAuthorityIssue,
    admit_existing_relative_chain,
    admit_root,
    is_directory_stat,
    is_placeholder_stat,
    is_reparse_stat,
    observe_native_volume,
)


class ObservationFileSystem(Protocol):
    def observe_root(self, authority: RootAuthority) -> RootObservation: ...

    def stat(
        self,
        authority: RootAuthority,
        rel_path: str,
        profile: CapabilityProfile,
    ) -> StatObservation: ...

    def free_space(self, authority: RootAuthority) -> int: ...

    def reclaimable_temp_bytes(
        self,
        authority: RootAuthority,
        parent_paths: frozenset[str],
        current_run_id: str,
    ) -> int: ...

    def observe_trash(
        self,
        authority: RootAuthority,
    ) -> TrashObservation: ...

    def now_utc(self) -> datetime: ...


def _native_path(path: str | Path) -> str:
    return to_extended_length_path(str(path))


def _resolved_logical_path(path: str | Path, *, strict: bool) -> str:
    resolved = Path(_native_path(path)).resolve(strict=strict)
    return from_extended_length_path(str(resolved))


def _root_authority(
    root: Root,
    expected_volume: VolumeId | None,
    reviewed_evidence: VolumeEvidence | None,
) -> RootAuthority:
    return RootAuthority(
        root.path,
        None if reviewed_evidence is None else reviewed_evidence.device_id,
        expected_volume,
    )


def _classify_root_facts(
    expected_volume: VolumeId | None,
    reviewed_anchor: str | None,
    observed: RootObservation | None,
) -> RootAuthorityIssue | None:
    if observed is None:
        return RootAuthorityIssue.ANCHOR_UNAVAILABLE
    if observed.error is not None or observed.resolved_path is None:
        return observed.authority_issue or RootAuthorityIssue.ANCHOR_UNAVAILABLE
    if reviewed_anchor is not None:
        evidence_anchor = (
            None
            if observed.volume_evidence is None
            else observed.volume_evidence.device_id
        )
        if not evidence_anchor:
            return RootAuthorityIssue.ANCHOR_UNAVAILABLE
        try:
            current_anchor = lexical_absolute_path(evidence_anchor)
            expected_anchor = lexical_absolute_path(reviewed_anchor)
        except (OSError, TypeError, ValueError):
            return RootAuthorityIssue.ANCHOR_UNAVAILABLE
        if os.path.normcase(os.path.normpath(current_anchor)) != os.path.normcase(
            os.path.normpath(expected_anchor)
        ):
            return RootAuthorityIssue.ANCHOR_CHANGED
    if expected_volume is None or observed.volume_id != expected_volume:
        return RootAuthorityIssue.VOLUME_CHANGED
    return None


class LocalObservationFileSystem:
    """Read-only local observation implementation used by composition roots."""

    def observe_root(self, authority: RootAuthority) -> RootObservation:
        try:
            admitted = admit_root(authority)
            resolved = _resolved_logical_path(
                authority.logical_root,
                strict=True,
            )
            return RootObservation(
                resolved,
                admitted.volume_id,
                admitted.evidence,
            )
        except RootAuthorityError as error:
            return RootObservation(
                None,
                None,
                None,
                logical_error_text(error),
                error.issue,
            )
        except (OSError, PermissionError, ValueError) as error:
            return RootObservation(
                None, None, None, logical_error_text(error)
            )

    def stat(
        self,
        authority: RootAuthority,
        rel_path: str,
        profile: CapabilityProfile,
    ) -> StatObservation:
        try:
            canonical = validate_relative_path(rel_path)
            candidate = join_under_root(authority.logical_root, canonical)
        except (OSError, PermissionError, ValueError) as error:
            return StatObservation(
                None, logical_error_text(error), True, False
            )

        admitted = admit_root(authority)
        try:
            exists = admit_existing_relative_chain(
                authority,
                canonical,
                include_leaf=True,
            )
            resolved_root = _resolved_logical_path(
                authority.logical_root,
                strict=True,
            )
            resolved_candidate = _resolved_logical_path(
                candidate, strict=False
            )
            contained = is_path_below(resolved_candidate, resolved_root)
            representable = len(resolved_candidate) <= profile.max_path
            if not contained:
                return StatObservation(None, "resolved path escapes root", False, representable)
            if not exists:
                return StatObservation(None, None, True, representable)
            try:
                observed = os.stat(
                    _native_path(candidate), follow_symlinks=False
                )
            except FileNotFoundError:
                return StatObservation(None, None, True, representable)
            if is_placeholder_stat(observed):
                raise RootAuthorityError(
                    RootAuthorityIssue.PLACEHOLDER_COMPONENT,
                    candidate,
                    "path contains a placeholder component",
                )
            if is_reparse_stat(observed):
                raise RootAuthorityError(
                    RootAuthorityIssue.REPARSE_COMPONENT,
                    candidate,
                    "path contains a reparse component",
                )
            if is_directory_stat(observed):
                kind = EntryKind.DIRECTORY
                size = 0
            elif stat_module.S_ISREG(observed.st_mode):
                kind = EntryKind.FILE
                size = int(observed.st_size)
            else:
                return StatObservation(None, "unsupported entry type", True, representable)
            identity = (
                FileIdentity(admitted.volume_id.serial, int(observed.st_ino))
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
            return StatObservation(
                None, logical_error_text(error), True, False
            )

    def free_space(self, authority: RootAuthority) -> int:
        admit_root(authority)
        return int(
            shutil.disk_usage(_native_path(authority.logical_root)).free
        )

    def reclaimable_temp_bytes(
        self,
        authority: RootAuthority,
        parent_paths: frozenset[str],
        current_run_id: str,
    ) -> int:
        total = 0
        admitted = admit_root(authority)
        root = authority.logical_root
        for parent_path in sorted(parent_paths, key=lambda value: (normalize_relative_path(value, allow_root=True), value)):
            if parent_path and (
                normalize_relative_path(parent_path) == ".SYNCTRASH"
                or normalize_relative_path(parent_path).startswith(".SYNCTRASH\\")
            ):
                continue
            absolute = root if not parent_path else join_under_root(root, parent_path)
            try:
                if parent_path and not admit_existing_relative_chain(
                    authority,
                    parent_path,
                    include_leaf=True,
                ):
                    continue
                if parent_path:
                    parent_stat = os.stat(
                        _native_path(absolute),
                        follow_symlinks=False,
                    )
                    if (
                        is_placeholder_stat(parent_stat)
                        or is_reparse_stat(parent_stat)
                        or not is_directory_stat(parent_stat)
                    ):
                        continue
                parent_volume = observe_native_volume(absolute)
                if parent_volume.volume_id != admitted.volume_id:
                    continue
                with os.scandir(_native_path(absolute)) as entries:
                    for entry in entries:
                        owner = owned_temp_run_id(entry.name)
                        if (
                            owner is not None
                            and owner != current_run_id
                            and entry.is_file(follow_symlinks=False)
                        ):
                            total += int(entry.stat(follow_symlinks=False).st_size)
            except OSError:
                continue
        return total

    def observe_trash(
        self,
        authority: RootAuthority,
    ) -> TrashObservation:
        trash = os.path.join(authority.logical_root, ".synctrash")
        admit_root(authority)
        try:
            exists = admit_existing_relative_chain(
                authority,
                ".synctrash",
                include_leaf=True,
            )
            root_resolved = _resolved_logical_path(
                authority.logical_root,
                strict=True,
            )
            resolved = _resolved_logical_path(
                trash,
                strict=False,
            )
            contained = is_path_below(resolved, root_resolved)
            if not contained:
                return TrashObservation(
                    resolved,
                    False,
                    False,
                    False,
                    False,
                    False,
                    "trash path resolves outside target root",
                )
            if exists:
                observed = os.stat(
                    _native_path(trash),
                    follow_symlinks=False,
                )
                if is_placeholder_stat(observed):
                    raise RootAuthorityError(
                        RootAuthorityIssue.PLACEHOLDER_COMPONENT,
                        trash,
                        "trash path is a placeholder",
                    )
                if is_reparse_stat(observed):
                    raise RootAuthorityError(
                        RootAuthorityIssue.REPARSE_COMPONENT,
                        trash,
                        "trash path is a reparse component",
                    )
                available = is_directory_stat(observed)
            else:
                available = True
            writable_path = _native_path(
                trash if exists else authority.logical_root
            )
            writable = os.access(writable_path, os.W_OK)
            actual_volume = observe_native_volume(
                resolved if exists else authority.logical_root
            )
            same_volume = (
                authority.expected_volume_id is not None
                and actual_volume.volume_id == authority.expected_volume_id
            )
            return TrashObservation(
                resolved,
                available,
                contained,
                same_volume,
                writable,
                True,
            )
        except (OSError, PermissionError, ValueError) as error:
            return TrashObservation(
                None,
                False,
                False,
                False,
                False,
                False,
                logical_error_text(error),
            )

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
) -> ObservedWorld:
    """Read the current scoped world without making any safety decision."""

    plan = xset.plan

    def authority_for(root: Root) -> RootAuthority:
        if root.root_id == plan.source_root.root_id:
            return _root_authority(
                root,
                plan.source_volume_id,
                plan.source_volume_evidence,
            )
        return _root_authority(
            root,
            plan.target_volume_id,
            plan.target_volume_evidence,
        )

    roots: dict[str, RootObservation] = {}
    authorities: dict[str, RootAuthority] = {}
    admitted_roots: dict[str, bool] = {}

    def reject_root(root: Root, error: RootAuthorityError) -> None:
        roots[root.root_id] = RootObservation(
            None,
            None,
            None,
            logical_error_text(error),
            error.issue,
        )
        admitted_roots[root.root_id] = False

    for root in (xset.plan.source_root, xset.plan.target_root):
        try:
            authority = authority_for(root)
            authorities[root.root_id] = authority
            observation = fs.observe_root(authority)
        except RootAuthorityError as error:
            reject_root(root, error)
        except (OSError, PermissionError, ValueError) as error:
            observation = RootObservation(
                None, None, None, logical_error_text(error)
            )
            roots[root.root_id] = observation
            admitted_roots[root.root_id] = False
        else:
            roots[root.root_id] = observation
            admitted_roots[root.root_id] = _classify_root_facts(
                authority.expected_volume_id,
                authority.reviewed_anchor,
                observation,
            ) is None

    subjects, target_parents = _operation_subjects(xset)
    stats: dict[Subject, StatObservation] = {}
    paths: dict[Subject, str] = {}
    for subject, (root, rel_path, profile) in sorted(subjects.items()):
        paths[subject] = rel_path
        if not admitted_roots.get(root.root_id, False):
            root_observation = roots.get(root.root_id)
            stats[subject] = StatObservation(
                None,
                root_observation.error
                if (
                    root_observation is not None
                    and root_observation.error is not None
                )
                else "root observation unavailable",
            )
            continue
        try:
            stats[subject] = fs.stat(
                authorities[root.root_id],
                rel_path,
                profile,
            )
        except RootAuthorityError as error:
            reject_root(root, error)
            stats[subject] = StatObservation(
                None,
                logical_error_text(error),
            )
        except (OSError, PermissionError, ValueError) as error:
            stats[subject] = StatObservation(
                None, logical_error_text(error)
            )

    target = xset.plan.target_root
    if admitted_roots.get(target.root_id, False):
        try:
            free_space = fs.free_space(authorities[target.root_id])
        except RootAuthorityError as error:
            reject_root(target, error)
            free_space = None
        except (OSError, PermissionError, ValueError):
            free_space = None
    else:
        free_space = None

    if admitted_roots.get(target.root_id, False):
        try:
            reclaimable = fs.reclaimable_temp_bytes(
                authorities[target.root_id],
                target_parents,
                str(xset.run_id),
            )
        except RootAuthorityError as error:
            reject_root(target, error)
            reclaimable = 0
        except (OSError, PermissionError, ValueError):
            reclaimable = 0
    else:
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
    if needs_trash and admitted_roots.get(target.root_id, False):
        try:
            trash = fs.observe_trash(
                authorities[target.root_id]
            )
        except RootAuthorityError as error:
            reject_root(target, error)
            trash = TrashObservation(
                None,
                False,
                False,
                False,
                False,
                False,
                logical_error_text(error),
            )
        except (OSError, PermissionError, ValueError) as error:
            trash = TrashObservation(
                None,
                False,
                False,
                False,
                False,
                False,
                logical_error_text(error),
            )
    else:
        trash = None
    return ObservedWorld(
        stats=stats,
        paths=paths,
        target_parent_paths=target_parents,
        roots=roots,
        free_space=free_space,
        reclaimable_temp_bytes=reclaimable,
        trash=trash,
        observed_at=fs.now_utc(),
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
    for expected, reviewed_evidence, observed in (
        (
            plan.source_volume_id,
            plan.source_volume_evidence,
            source_root,
        ),
        (
            plan.target_volume_id,
            plan.target_volume_evidence,
            target_root,
        ),
    ):
        issue = _classify_root_facts(
            expected,
            (
                None
                if reviewed_evidence is None
                else reviewed_evidence.device_id
            ),
            observed,
        )
        if issue is not None:
            changed = issue in {
                RootAuthorityIssue.ANCHOR_CHANGED,
                RootAuthorityIssue.VOLUME_CHANGED,
            }
            refusals.append(
                Refusal(
                    RefusalCode.ROOT_CHANGED
                    if changed
                    else RefusalCode.ROOT_UNAVAILABLE,
                    detail=(
                        ""
                        if changed
                        else (
                            (
                                observed.error
                                or "root authority observation unavailable"
                            )
                            if observed is not None
                            else "missing root observation"
                        )
                    ),
                )
            )
        if (
            observed is not None
            and observed.error is None
            and observed.resolved_path is not None
            and observed.volume_evidence is not None
            and observed.volume_evidence.clone_ambiguous
        ):
            refusals.append(Refusal(RefusalCode.VOLUME_CLONE_AMBIGUOUS))
    if (
        source_root is not None
        and target_root is not None
        and source_root.resolved_path is not None
        and target_root.resolved_path is not None
        and _paths_overlap(source_root.resolved_path, target_root.resolved_path)
    ):
        refusals.append(Refusal(RefusalCode.ROOTS_OVERLAP))

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
