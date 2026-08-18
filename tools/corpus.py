"""Corpus ownership, target pre-state materialization, and teardown.

The verifier only reads, so its corpus needs nothing beyond a path. The
executor writes, so the tools own the target tree outright: they claim a
directory, materialize a pre-state into it before each run, and tear it down
afterwards.

Ownership markers and leases live *beside* the target directory, never inside
it. Files within the target root would change the measured operation mix.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import msvcrt
import os
from pathlib import Path
from pathlib import PurePosixPath
import random
import shutil
import stat
import tempfile
from time import perf_counter
from typing import BinaryIO, Iterable

from namisync.core.pathing import to_extended_length_path
from namisync.core.root_authority import is_reparse_stat


MARKER_SUFFIX = ".rig-owned"
LEASE_SUFFIX = ".rig-lease"
OUTPUTS_SUFFIX = ".rig-outputs.json"
LEASE_MAGIC = b"namisync-tools-workspace-lease-v1\n"
MARKER_SCHEMA = 1
MARKER_OWNER = "namisync-tools"
MARKER_MAX_BYTES = 4096
OUTPUTS_SCHEMA = 1
OUTPUTS_OWNER = "namisync-tools-output-manifest"
OUTPUTS_MAX_BYTES = 64 * 1024 * 1024

_UNITS = {"B": 1, "KIB": 1024, "MIB": 1024**2, "GIB": 1024**3}
_CLAIM_TOKEN = object()


class CorpusError(RuntimeError):
    """A corpus or workspace path is unusable or not tool-owned."""


def marker_for(target: Path) -> Path:
    target = Path(target)
    return target.parent / f"{target.name}{MARKER_SUFFIX}"


def lease_for(target: Path) -> Path:
    target = Path(target)
    return target.parent / f"{target.name}{LEASE_SUFFIX}"


def outputs_for(target: Path) -> Path:
    target = Path(target)
    return target.parent / f"{target.name}{OUTPUTS_SUFFIX}"


@dataclass(frozen=True, slots=True)
class OutputEntry:
    path: str
    kind: str
    device: int
    inode: int
    size: int
    mtime_ns: int
    nlink: int
    attributes: int | None


@dataclass(frozen=True, slots=True)
class CleanupPlan:
    target: Path
    manifest: Path | None
    entries: tuple[OutputEntry, ...]
    manifest_identity: tuple[int, int] | None = None
    forced: bool = False

    @property
    def files(self) -> int:
        return sum(entry.kind == "file" for entry in self.entries)

    @property
    def directories(self) -> int:
        return sum(entry.kind == "directory" for entry in self.entries)

    @property
    def bytes(self) -> int:
        return sum(entry.size for entry in self.entries if entry.kind == "file")


@dataclass(frozen=True, slots=True)
class CleanupResult:
    files: int
    directories: int
    bytes: int
    forced: bool


class WorkspaceClaim:
    """A live, exclusively held claim on one tool-owned directory."""

    __slots__ = ("_closed", "_identity", "_lease", "_lease_path", "_retired", "target")

    def __init__(
        self,
        target: Path,
        identity: tuple[int, int],
        lease_path: Path,
        lease: BinaryIO,
        *,
        _token: object,
    ) -> None:
        if _token is not _CLAIM_TOKEN:
            raise TypeError("workspace claims must be created with claim()")
        self.target = target
        self._identity = identity
        self._lease_path = lease_path
        self._lease = lease
        self._closed = False
        self._retired = False

    def __enter__(self) -> WorkspaceClaim:
        try:
            self.validate()
            return self
        except BaseException:
            self.close()
            raise

    def __exit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback
        self.close()

    def close(self) -> None:
        """Release the exclusive lease without removing the ownership marker."""

        if self._closed:
            return
        self._closed = True
        _release_lease(self._lease, self._lease_path)

    def validate(self) -> Path:
        """Return the target only while the lease and bound identity are valid."""

        if self._closed or self._lease.closed or self._retired:
            raise CorpusError(f"workspace claim is no longer live: {self.target}")
        _validate_plain_path(self.target)
        actual_identity = _directory_identity(self.target)
        if actual_identity != self._identity:
            raise CorpusError(
                f"workspace directory was replaced after it was claimed: {self.target}"
            )
        _validate_marker(marker_for(self.target), self.target, self._identity)
        return self.target

    def _retire(self) -> None:
        self._retired = True


def claim(target: Path) -> WorkspaceClaim:
    """Create or adopt a tool-owned workspace and hold its exclusive lease.

    Existing nonempty directories must already have a valid marker. Empty
    unmarked directories can be claimed because they contain no user data.
    """

    requested = Path(target).absolute()
    target = _resolve_plain_workspace_path(requested)
    _reject_dangerous(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    lease_path = lease_for(target)
    lease = _acquire_lease(lease_path, target)
    try:
        marker = marker_for(target)
        if target.exists():
            if not target.is_dir():
                raise CorpusError(f"workspace path is not a directory: {target}")
            identity = _directory_identity(target)
            if marker.exists():
                _validate_marker(marker, target, identity)
            else:
                with os.scandir(to_extended_length_path(str(target))) as entries:
                    if next(entries, None) is not None:
                        raise CorpusError(
                            "refusing to use nonempty directory without a valid "
                            f"marker: {target}"
                        )
                _write_marker(marker, target, identity)
        else:
            if marker.exists():
                raise CorpusError(
                    f"ownership marker is stale because its directory is missing: {marker}"
                )
            target.mkdir()
            identity = _directory_identity(target)
            _write_marker(marker, target, identity)
        return WorkspaceClaim(
            target,
            identity,
            lease_path,
            lease,
            _token=_CLAIM_TOKEN,
        )
    except BaseException:
        _release_lease(lease, lease_path)
        raise


def is_owned(target: Path) -> bool:
    """Return whether a directory has a valid marker bound to its identity."""

    try:
        target = _resolve_plain_workspace_path(Path(target).absolute())
        identity = _directory_identity(target)
        _validate_marker(marker_for(target), target, identity)
    except (CorpusError, OSError):
        return False
    return True


def record_outputs(
    workspace: WorkspaceClaim,
    *,
    files: Iterable[str],
    directories: Iterable[str],
) -> Path:
    """Record only a predeclared, completely validated output set."""

    target = _claimed_target(workspace)
    file_paths = {_relative_path(path) for path in files}
    directory_paths = {_relative_path(path) for path in directories}
    overlap = file_paths & directory_paths
    if overlap:
        raise CorpusError(
            f"output paths cannot be both files and directories: {sorted(overlap)!r}"
        )
    expected = file_paths | directory_paths
    actual = _inventory(target)
    if set(actual) != expected:
        unknown = sorted(set(actual) - expected)
        missing = sorted(expected - set(actual))
        raise CorpusError(
            "refusing to record an output manifest because the workspace does "
            f"not match the declared outputs; unknown={unknown[:5]!r}, "
            f"missing={missing[:5]!r}: {target}"
        )
    for path in file_paths:
        if actual[path].kind != "file":
            raise CorpusError(f"declared output is not a regular file: {path}")
    for path in directory_paths:
        if actual[path].kind != "directory":
            raise CorpusError(f"declared output is not a directory: {path}")

    manifest = outputs_for(target)
    previous_identity = None
    if manifest.exists() or _is_reparse_point(manifest):
        _, previous_identity = _load_outputs(manifest, target, workspace._identity)
    payload = {
        "schema": OUTPUTS_SCHEMA,
        "owner": OUTPUTS_OWNER,
        "path": str(target),
        "device": workspace._identity[0],
        "inode": workspace._identity[1],
        "entries": [_entry_payload(actual[path]) for path in sorted(actual)],
    }
    _write_outputs(manifest, payload, previous_identity)
    return manifest


def inspect_cleanup(workspace: WorkspaceClaim) -> CleanupPlan:
    """Validate an exact cleanup set without mutating the workspace."""

    target = _claimed_target(workspace)
    manifest = outputs_for(target)
    actual = _inventory(target)
    if not manifest.exists() and not _is_reparse_point(manifest):
        if actual:
            raise CorpusError(
                "refusing to delete a nonempty workspace without an exact output "
                f"manifest: {target}. Inspect it, then use clean --force-all only "
                "if every current entry may be removed."
            )
        return CleanupPlan(target, None, ())

    expected, manifest_identity = _load_outputs(
        manifest, target, workspace._identity
    )
    unknown = sorted(set(actual) - set(expected))
    if unknown:
        raise CorpusError(
            "refusing cleanup because the workspace contains paths not owned by "
            f"the output manifest: {unknown[:5]!r}. Nothing was deleted: {target}"
        )
    for path, current in actual.items():
        _require_entry_match(expected[path], current, full=current.kind == "file")
    return CleanupPlan(
        target,
        manifest,
        tuple(actual[path] for path in sorted(actual)),
        manifest_identity,
    )


def inspect_force_cleanup(workspace: WorkspaceClaim) -> CleanupPlan:
    """Inventory an explicitly authorized whole-root cleanup without mutation."""

    target = _claimed_target(workspace)
    actual = _inventory(target)
    manifest = outputs_for(target)
    recognized_manifest: Path | None = None
    manifest_identity: tuple[int, int] | None = None
    if manifest.exists() or _is_reparse_point(manifest):
        try:
            _, manifest_identity = _load_outputs(
                manifest, target, workspace._identity
            )
        except CorpusError:
            pass
        else:
            recognized_manifest = manifest
    return CleanupPlan(
        target,
        recognized_manifest,
        tuple(actual[path] for path in sorted(actual)),
        manifest_identity,
        True,
    )


def empty(
    workspace: WorkspaceClaim,
    plan: CleanupPlan | None = None,
) -> CleanupResult:
    """Remove only exact manifest-owned outputs while retaining the root."""

    selected = inspect_cleanup(workspace) if plan is None else plan
    if selected.forced:
        raise CorpusError("an exact cleanup cannot apply a --force-all plan")
    return _apply_cleanup(workspace, selected)


def force_empty(
    workspace: WorkspaceClaim,
    plan: CleanupPlan | None = None,
) -> CleanupResult:
    """Remove a whole inspected root after explicit caller authorization."""

    selected = inspect_force_cleanup(workspace) if plan is None else plan
    if not selected.forced:
        raise CorpusError("--force-all cleanup requires a force cleanup plan")
    return _apply_cleanup(workspace, selected)


def teardown(
    workspace: WorkspaceClaim,
    plan: CleanupPlan | None = None,
) -> CleanupResult:
    """Exactly clean and retire a claimed workspace root."""

    result = empty(workspace, plan)
    return _retire_workspace(workspace, result)


def force_teardown(
    workspace: WorkspaceClaim,
    plan: CleanupPlan | None = None,
) -> CleanupResult:
    """Retire a whole inspected root after explicit caller authorization."""

    result = force_empty(workspace, plan)
    return _retire_workspace(workspace, result)


@dataclass(frozen=True, slots=True)
class MaterializeResult:
    files: int
    bytes_copied: int
    seconds: float


def materialize(
    template: Path,
    workspace: WorkspaceClaim,
    *,
    cleanup_plan: CleanupPlan | None = None,
) -> MaterializeResult:
    """Copy a template pre-state into a claimed target, preserving mtimes.

    Timestamps must survive, otherwise the planner sees every target file as
    stale and the operation mix collapses to all-UPDATE.
    """

    target = _claimed_target(workspace)
    template = Path(template).resolve()
    if not template.is_dir():
        raise CorpusError(f"template is not a directory: {template}")
    if (
        template == target
        or template.is_relative_to(target)
        or target.is_relative_to(template)
    ):
        raise CorpusError(f"template and target must not overlap: {template}, {target}")
    empty(workspace, cleanup_plan)

    started = perf_counter()
    files = 0
    copied = 0
    output_files: set[str] = set()
    output_directories: set[str] = set()
    native_template = to_extended_length_path(str(template))
    for source_dir, _, names in os.walk(native_template, onerror=_raise_walk_error):
        relative = os.path.relpath(source_dir, native_template)
        destination_dir = target if relative == "." else target / relative
        os.makedirs(to_extended_length_path(str(destination_dir)), exist_ok=True)
        if relative != ".":
            output_directories.add(_relative_path(relative))
        for name in names:
            source = to_extended_length_path(str(Path(source_dir) / name))
            destination = to_extended_length_path(str(destination_dir / name))
            shutil.copy2(source, destination)
            output_files.add(
                _relative_path(str(Path(relative) / name) if relative != "." else name)
            )
            files += 1
            copied += os.stat(source).st_size
    record_outputs(
        workspace,
        files=output_files,
        directories=output_directories,
    )
    return MaterializeResult(files, copied, perf_counter() - started)


@dataclass(frozen=True, slots=True)
class GenerateResult:
    files: int
    bytes_written: int
    seconds: float


def generate(
    workspace: WorkspaceClaim,
    spec: str,
    *,
    seed: int = 0,
    per_directory: int = 256,
    cleanup_plan: CleanupPlan | None = None,
) -> GenerateResult:
    """Replace a claimed root with a deterministic ``count@size`` tree."""

    root = _claimed_target(workspace)
    groups = parse_spec(spec)
    empty(workspace, cleanup_plan)

    started = perf_counter()
    rng = random.Random(seed)
    files = 0
    written = 0
    index = 0
    output_files: set[str] = set()
    output_directories: set[str] = set()
    for count, size in groups:
        for _ in range(count):
            directory = root / f"d{index // per_directory:04d}"
            directory.mkdir(parents=True, exist_ok=True)
            output_directories.add(_relative_path(directory.relative_to(root).as_posix()))
            path = directory / f"f{index:06d}_{size}.bin"
            with open(to_extended_length_path(str(path)), "wb") as handle:
                remaining = size
                while remaining:
                    block = min(remaining, 1024 * 1024)
                    handle.write(rng.randbytes(block))
                    remaining -= block
            output_files.add(_relative_path(path.relative_to(root).as_posix()))
            files += 1
            written += size
            index += 1
    record_outputs(
        workspace,
        files=output_files,
        directories=output_directories,
    )
    return GenerateResult(files, written, perf_counter() - started)


def parse_spec(spec: str) -> tuple[tuple[int, int], ...]:
    """Parse ``count@size`` groups into ``(count, size_bytes)`` pairs."""

    groups: list[tuple[int, int]] = []
    for raw in spec.split(","):
        chunk = raw.strip()
        if not chunk:
            continue
        count_text, _, size_text = chunk.partition("@")
        if not size_text:
            raise ValueError(f"corpus group {chunk!r} must be written as count@size")
        try:
            count = int(count_text)
        except ValueError:
            raise ValueError(f"corpus group {chunk!r} has a non-numeric count") from None
        if count <= 0:
            raise ValueError(f"corpus group {chunk!r} must request at least one file")
        groups.append((count, parse_size(size_text)))
    if not groups:
        raise ValueError("corpus specification is empty")
    return tuple(groups)


def parse_size(text: str) -> int:
    """Parse ``4KiB`` / ``1MiB`` / ``512`` into a byte count."""

    value = text.strip().upper()
    for suffix, multiplier in sorted(_UNITS.items(), key=lambda item: -len(item[0])):
        if value.endswith(suffix):
            number = value[: -len(suffix)].strip()
            break
    else:
        number, multiplier = value, 1
    try:
        scaled = float(number) * multiplier
    except (OverflowError, ValueError):
        raise ValueError(f"cannot parse size {text!r}") from None
    if not math.isfinite(scaled):
        raise ValueError(f"size {text!r} must be finite")
    size = int(scaled)
    if size < 0 or size != scaled:
        raise ValueError(f"size {text!r} must be a non-negative whole number of bytes")
    return size


def _inventory(target: Path) -> dict[str, OutputEntry]:
    found: dict[str, OutputEntry] = {}
    pending: list[tuple[str, str]] = [
        (to_extended_length_path(str(target)), "")
    ]
    while pending:
        native_directory, relative_directory = pending.pop()
        try:
            with os.scandir(native_directory) as entries:
                for entry in entries:
                    relative = (
                        entry.name
                        if not relative_directory
                        else f"{relative_directory}/{entry.name}"
                    )
                    canonical = _relative_path(relative)
                    if _dir_entry_is_reparse(entry):
                        raise CorpusError(
                            f"refusing a workspace containing a reparse point: "
                            f"{target / Path(*PurePosixPath(canonical).parts)}"
                        )
                    try:
                        details = os.stat(entry.path, follow_symlinks=False)
                    except OSError as error:
                        raise CorpusError(
                            f"workspace entry is unreadable: {canonical}: {error}"
                        ) from error
                    if stat.S_ISDIR(details.st_mode):
                        kind = "directory"
                        pending.append((entry.path, canonical))
                    elif stat.S_ISREG(details.st_mode):
                        kind = "file"
                    else:
                        raise CorpusError(
                            f"refusing unsupported workspace entry: {canonical}"
                        )
                    found[canonical] = _output_entry(canonical, kind, details)
        except CorpusError:
            raise
        except OSError as error:
            raise CorpusError(
                f"could not inventory workspace directory {target}: {error}"
            ) from error
    return found


def _output_entry(path: str, kind: str, details: os.stat_result) -> OutputEntry:
    return OutputEntry(
        path=path,
        kind=kind,
        device=details.st_dev,
        inode=details.st_ino,
        size=details.st_size,
        mtime_ns=details.st_mtime_ns,
        nlink=details.st_nlink,
        attributes=getattr(details, "st_file_attributes", None),
    )


def _entry_payload(entry: OutputEntry) -> dict[str, object]:
    return {
        "path": entry.path,
        "kind": entry.kind,
        "device": entry.device,
        "inode": entry.inode,
        "size": entry.size,
        "mtime_ns": entry.mtime_ns,
        "nlink": entry.nlink,
        "attributes": entry.attributes,
    }


def _load_outputs(
    manifest: Path,
    target: Path,
    identity: tuple[int, int],
) -> tuple[dict[str, OutputEntry], tuple[int, int]]:
    if _is_reparse_point(manifest):
        raise CorpusError(f"output manifest must not be a reparse point: {manifest}")
    try:
        with open(to_extended_length_path(str(manifest)), encoding="utf-8") as handle:
            details = os.fstat(handle.fileno())
            if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
                raise CorpusError(
                    f"output manifest must be one ordinary single-link file: {manifest}"
                )
            if details.st_size > OUTPUTS_MAX_BYTES:
                raise CorpusError(f"output manifest is too large: {manifest}")
            payload = json.load(handle, object_pairs_hook=_strict_object)
    except CorpusError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise CorpusError(f"output manifest is missing or malformed: {manifest}") from error
    if not isinstance(payload, dict) or set(payload) != {
        "schema",
        "owner",
        "path",
        "device",
        "inode",
        "entries",
    }:
        raise CorpusError(f"output manifest has an unsupported schema: {manifest}")
    expected_header = {
        "schema": OUTPUTS_SCHEMA,
        "owner": OUTPUTS_OWNER,
        "path": str(target),
        "device": identity[0],
        "inode": identity[1],
    }
    if any(
        type(payload[key]) is not type(value) or payload[key] != value
        for key, value in expected_header.items()
    ):
        raise CorpusError(
            f"output manifest does not describe this workspace: {manifest}"
        )
    raw_entries = payload["entries"]
    if not isinstance(raw_entries, list):
        raise CorpusError(f"output manifest entries must be a list: {manifest}")
    decoded: dict[str, OutputEntry] = {}
    fields = {
        "path",
        "kind",
        "device",
        "inode",
        "size",
        "mtime_ns",
        "nlink",
        "attributes",
    }
    for raw in raw_entries:
        if not isinstance(raw, dict) or set(raw) != fields:
            raise CorpusError(f"output manifest entry schema is invalid: {manifest}")
        path = _relative_path(_manifest_string(raw, "path"))
        kind = _manifest_string(raw, "kind")
        if kind not in {"file", "directory"}:
            raise CorpusError(f"output manifest entry kind is invalid: {manifest}")
        attributes = raw["attributes"]
        if attributes is not None and type(attributes) is not int:
            raise CorpusError(
                f"output manifest entry attributes are invalid: {manifest}"
            )
        entry = OutputEntry(
            path,
            kind,
            _manifest_int(raw, "device"),
            _manifest_int(raw, "inode"),
            _manifest_int(raw, "size"),
            _manifest_int(raw, "mtime_ns"),
            _manifest_int(raw, "nlink"),
            attributes,
        )
        if path in decoded:
            raise CorpusError(f"output manifest contains a duplicate path: {path}")
        decoded[path] = entry
    if list(decoded) != sorted(decoded):
        raise CorpusError(f"output manifest entries are not sorted: {manifest}")
    return decoded, (details.st_dev, details.st_ino)


def _write_outputs(
    manifest: Path,
    payload: dict[str, object],
    previous_identity: tuple[int, int] | None,
) -> None:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    if len(encoded.encode("utf-8")) > OUTPUTS_MAX_BYTES:
        raise CorpusError(
            f"output manifest would exceed {OUTPUTS_MAX_BYTES} bytes: {manifest}"
        )
    temporary: Path | None = None
    descriptor: int | None = None
    try:
        descriptor, name = tempfile.mkstemp(
            dir=manifest.parent,
            prefix=f".{manifest.name}.",
            suffix=".tmp",
        )
        temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = None
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if previous_identity is None:
            os.rename(temporary, manifest)
        else:
            current = os.stat(to_extended_length_path(str(manifest)))
            if (current.st_dev, current.st_ino) != previous_identity:
                raise CorpusError(
                    f"output manifest was replaced before publication: {manifest}"
                )
            os.replace(temporary, manifest)
        temporary = None
    except CorpusError:
        raise
    except OSError as error:
        raise CorpusError(f"cannot publish output manifest {manifest}: {error}") from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _apply_cleanup(
    workspace: WorkspaceClaim,
    plan: CleanupPlan,
) -> CleanupResult:
    target = _claimed_target(workspace)
    if plan.target != target:
        raise CorpusError(
            f"cleanup plan belongs to a different workspace: {plan.target}, {target}"
        )
    if not plan.forced:
        expected_manifest = outputs_for(target)
        if plan.manifest is None:
            if plan.entries:
                raise CorpusError(
                    "a nonempty exact cleanup plan requires the bound output "
                    f"manifest: {expected_manifest}"
                )
        else:
            if plan.manifest != expected_manifest:
                raise CorpusError(
                    "cleanup plan cites an unexpected output manifest: "
                    f"{plan.manifest}"
                )
            recorded, manifest_identity = _load_outputs(
                expected_manifest,
                target,
                workspace._identity,
            )
            if manifest_identity != plan.manifest_identity:
                raise CorpusError(
                    f"output manifest was replaced after cleanup inspection: "
                    f"{expected_manifest}"
                )
            for entry in plan.entries:
                authoritative = recorded.get(entry.path)
                if authoritative is None:
                    raise CorpusError(
                        "cleanup plan contains a path absent from the output "
                        f"manifest: {entry.path}"
                    )
                _require_entry_match(
                    authoritative,
                    entry,
                    full=entry.kind == "file",
                )
    expected_entries = {entry.path: entry for entry in plan.entries}
    if len(expected_entries) != len(plan.entries):
        raise CorpusError("cleanup plan contains duplicate output paths")
    current_entries = _inventory(target)
    if set(current_entries) != set(expected_entries):
        added = sorted(set(current_entries) - set(expected_entries))
        missing = sorted(set(expected_entries) - set(current_entries))
        raise CorpusError(
            "cleanup plan no longer matches the workspace; nothing was deleted; "
            f"added={added[:5]!r}, missing={missing[:5]!r}: {target}"
        )
    for path, expected in expected_entries.items():
        _require_entry_match(
            expected,
            current_entries[path],
            full=expected.kind == "file",
        )

    removed_files = 0
    removed_directories = 0
    removed_bytes = 0
    removed_paths: list[str] = []
    manifest = plan.manifest
    try:
        for expected in (entry for entry in plan.entries if entry.kind == "file"):
            current = _stat_relative(plan.target, expected.path)
            _require_entry_match(expected, current, full=True)
            _unlink_writable(_entry_path(plan.target, expected.path))
            removed_files += 1
            removed_bytes += expected.size
            removed_paths.append(expected.path)
        directories = sorted(
            (entry for entry in plan.entries if entry.kind == "directory"),
            key=lambda entry: (-len(PurePosixPath(entry.path).parts), entry.path),
        )
        for expected in directories:
            current = _stat_relative(plan.target, expected.path)
            _require_entry_match(expected, current, full=False)
            os.rmdir(to_extended_length_path(str(_entry_path(plan.target, expected.path))))
            removed_directories += 1
            removed_paths.append(expected.path)
    except BaseException as error:
        retained = (
            f"output manifest retained at {manifest}"
            if manifest is not None
            else f"workspace retained at {plan.target}"
        )
        raise _partial_cleanup_error(
            removed_files,
            removed_directories,
            removed_bytes,
            removed_paths,
            retained,
            error,
        ) from error
    try:
        remaining = _inventory(_claimed_target(workspace))
    except BaseException as error:
        raise _partial_cleanup_error(
            removed_files,
            removed_directories,
            removed_bytes,
            removed_paths,
            f"workspace state could not be validated at {plan.target}",
            error,
        ) from error
    if remaining:
        raise _partial_cleanup_error(
            removed_files,
            removed_directories,
            removed_bytes,
            removed_paths,
            f"workspace retained with {len(remaining)} late entries at {plan.target}",
            CorpusError("entries appeared after the pre-delete validation"),
        )
    if manifest is not None:
        try:
            _, current_identity = _load_outputs(
                manifest, plan.target, workspace._identity
            )
            if current_identity != plan.manifest_identity:
                raise CorpusError(
                    f"output manifest was replaced before cleanup completed: {manifest}"
                )
            _unlink_writable(manifest)
        except BaseException as error:
            manifest_state = (
                f"output manifest retained or replaced at {manifest}"
                if manifest.exists() or _is_reparse_point(manifest)
                else f"output manifest is missing from {manifest}"
            )
            raise _partial_cleanup_error(
                removed_files,
                removed_directories,
                removed_bytes,
                removed_paths,
                manifest_state,
                error,
            ) from error
    return CleanupResult(
        removed_files,
        removed_directories,
        plan.bytes,
        plan.forced,
    )


def _partial_cleanup_error(
    files: int,
    directories: int,
    bytes_removed: int,
    paths: list[str],
    retained_state: str,
    cause: BaseException,
) -> CorpusError:
    return CorpusError(
        f"cleanup stopped after removing {files} files, {directories} "
        f"directories, and {bytes_removed} bytes; removed paths={paths!r}; "
        f"{retained_state}: {cause}"
    )


def _retire_workspace(
    workspace: WorkspaceClaim,
    result: CleanupResult,
) -> CleanupResult:
    target = workspace.target
    marker = marker_for(target)
    try:
        _claimed_target(workspace)
    except BaseException as error:
        raise CorpusError(
            f"removed {result.files} files, {result.directories} directories, "
            f"and {result.bytes} bytes; workspace root {_path_state(target)}; "
            f"ownership marker {_path_state(marker)}: {error}"
        ) from error
    try:
        os.rmdir(to_extended_length_path(str(target)))
    except BaseException as error:
        raise CorpusError(
            f"removed {result.files} files, {result.directories} directories, "
            f"and {result.bytes} bytes; workspace root {_path_state(target)}; "
            f"ownership marker {_path_state(marker)}: {error}"
        ) from error
    try:
        _unlink_writable(marker)
    except BaseException as error:
        workspace._retire()
        raise CorpusError(
            f"removed {result.files} files, {result.directories} directories, "
            f"and {result.bytes} bytes; workspace root {_path_state(target)}; "
            f"ownership marker {_path_state(marker)}: {error}"
        ) from error
    workspace._retire()
    return result


def _path_state(path: Path) -> str:
    if path.exists() or _is_reparse_point(path):
        return f"retained at {path}"
    return f"missing from {path}"


def _stat_relative(target: Path, relative: str) -> OutputEntry:
    path = _entry_path(target, relative)
    if _is_reparse_point(path):
        raise CorpusError(f"workspace entry became a reparse point: {path}")
    try:
        details = os.stat(to_extended_length_path(str(path)), follow_symlinks=False)
    except OSError as error:
        raise CorpusError(f"workspace entry changed before cleanup: {path}") from error
    if stat.S_ISDIR(details.st_mode):
        kind = "directory"
    elif stat.S_ISREG(details.st_mode):
        kind = "file"
    else:
        raise CorpusError(f"workspace entry became unsupported before cleanup: {path}")
    return _output_entry(relative, kind, details)


def _require_entry_match(
    expected: OutputEntry,
    actual: OutputEntry,
    *,
    full: bool,
) -> None:
    identity = (expected.kind, expected.device, expected.inode)
    observed_identity = (actual.kind, actual.device, actual.inode)
    if identity != observed_identity:
        raise CorpusError(
            f"output identity changed before cleanup: {expected.path}"
        )
    if full and expected != actual:
        raise CorpusError(
            f"output file metadata changed before cleanup: {expected.path}"
        )


def _entry_path(target: Path, relative: str) -> Path:
    return target.joinpath(*PurePosixPath(relative).parts)


def _relative_path(value: str) -> str:
    normalized = str(value).replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise CorpusError(f"invalid output-relative path: {value!r}")
    return path.as_posix()


def _manifest_string(row: dict[str, object], field: str) -> str:
    value = row[field]
    if not isinstance(value, str):
        raise CorpusError(f"output manifest field {field} must be a string")
    return value


def _manifest_int(row: dict[str, object], field: str) -> int:
    value = row[field]
    if type(value) is not int:
        raise CorpusError(f"output manifest field {field} must be an integer")
    return value


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON field {key!r}")
        value[key] = item
    return value


def _dir_entry_is_reparse(entry: os.DirEntry[str]) -> bool:
    return is_reparse_stat(entry.stat(follow_symlinks=False))


def _claimed_target(workspace: WorkspaceClaim) -> Path:
    if not isinstance(workspace, WorkspaceClaim):
        raise TypeError("a live WorkspaceClaim from claim() is required")
    return workspace.validate()


def _directory_identity(target: Path) -> tuple[int, int]:
    try:
        details = os.stat(to_extended_length_path(str(target)))
    except OSError as error:
        raise CorpusError(f"workspace directory is missing or unreadable: {target}") from error
    if not stat.S_ISDIR(details.st_mode):
        raise CorpusError(f"workspace path is not a directory: {target}")
    return details.st_dev, details.st_ino


def _marker_payload(target: Path, identity: tuple[int, int]) -> dict[str, object]:
    return {
        "schema": MARKER_SCHEMA,
        "owner": MARKER_OWNER,
        "path": str(target),
        "device": identity[0],
        "inode": identity[1],
    }


def _write_marker(marker: Path, target: Path, identity: tuple[int, int]) -> None:
    payload = json.dumps(_marker_payload(target, identity), sort_keys=True) + "\n"
    try:
        with open(to_extended_length_path(str(marker)), "x", encoding="utf-8") as handle:
            handle.write(payload)
    except OSError as error:
        raise CorpusError(f"could not create ownership marker: {marker}") from error


def _validate_marker(marker: Path, target: Path, identity: tuple[int, int]) -> None:
    expected = _marker_payload(target, identity)
    if _is_reparse_point(marker):
        raise CorpusError(f"ownership marker must not be a reparse point: {marker}")
    try:
        with open(to_extended_length_path(str(marker)), encoding="utf-8") as handle:
            details = os.fstat(handle.fileno())
            if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
                raise CorpusError(
                    f"ownership marker must be one ordinary single-link file: {marker}"
                )
            if details.st_size > MARKER_MAX_BYTES:
                raise CorpusError(f"ownership marker is too large: {marker}")
            actual = json.load(handle, object_pairs_hook=_strict_object)
    except CorpusError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise CorpusError(f"ownership marker is missing or malformed: {marker}") from error
    if not isinstance(actual, dict) or set(actual) != set(expected):
        raise CorpusError(f"ownership marker has an unsupported schema: {marker}")
    if any(
        type(actual[key]) is not type(value) or actual[key] != value
        for key, value in expected.items()
    ):
        raise CorpusError(f"ownership marker does not describe this directory: {marker}")


def _acquire_lease(lease_path: Path, target: Path) -> BinaryIO:
    existing = False
    try:
        lease = open(to_extended_length_path(str(lease_path)), "x+b")
    except FileExistsError:
        if _is_reparse_point(lease_path) or not lease_path.is_file():
            raise CorpusError(
                f"refusing unrecognized workspace lease artifact: {lease_path}"
            ) from None
        try:
            lease = open(to_extended_length_path(str(lease_path)), "r+b")
        except OSError as error:
            raise CorpusError(f"cannot open workspace lease: {lease_path}") from error
        existing = True
    except OSError as error:
        raise CorpusError(f"cannot create workspace lease: {lease_path}") from error
    else:
        try:
            lease.write(LEASE_MAGIC)
            lease.flush()
        except BaseException:
            lease.close()
            _remove_unused_lease(lease_path)
            raise

    try:
        lease.seek(0)
        msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as error:
        lease.close()
        raise CorpusError(f"workspace is already claimed by another tool: {target}") from error
    if existing:
        try:
            lease.seek(0)
            recognized = (
                os.fstat(lease.fileno()).st_size == len(LEASE_MAGIC)
                and lease.read(len(LEASE_MAGIC)) == LEASE_MAGIC
            )
        except OSError as error:
            _release_lease(lease, lease_path)
            raise CorpusError(f"cannot validate workspace lease: {lease_path}") from error
        if not recognized:
            _release_lease(lease, lease_path)
            raise CorpusError(
                f"refusing unrecognized workspace lease artifact: {lease_path}"
            )
    return lease


def _release_lease(lease: BinaryIO, lease_path: Path) -> None:
    try:
        try:
            lease.seek(0)
            msvcrt.locking(lease.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            lease.close()
    finally:
        _remove_unused_lease(lease_path)


def _remove_unused_lease(lease_path: Path) -> None:
    try:
        if _is_reparse_point(lease_path) or not lease_path.is_file():
            return
        with open(to_extended_length_path(str(lease_path)), "rb") as handle:
            if os.fstat(handle.fileno()).st_size != len(LEASE_MAGIC):
                return
            if handle.read(len(LEASE_MAGIC)) != LEASE_MAGIC:
                return
        os.unlink(to_extended_length_path(str(lease_path)))
    except FileNotFoundError:
        pass
    except PermissionError:
        # Another claimant acquired the same lease between unlock and cleanup.
        pass


def _unlink_writable(path: Path) -> None:
    native_path = to_extended_length_path(str(path))
    try:
        os.unlink(native_path)
    except PermissionError:
        os.chmod(native_path, stat.S_IWRITE)
        os.unlink(native_path)


def _raise_walk_error(error: OSError) -> None:
    raise CorpusError(f"could not walk template directory: {error}") from error


def _is_reparse_point(path: Path) -> bool:
    try:
        observed = os.lstat(to_extended_length_path(str(path)))
    except FileNotFoundError:
        return False
    return is_reparse_stat(observed)


def _resolve_plain_workspace_path(requested: Path) -> Path:
    try:
        current = Path(requested.anchor)
        for part in requested.parts[1:]:
            current /= part
            if _is_reparse_point(current):
                raise CorpusError(
                    "workspace path must not traverse a reparse point: "
                    f"{current} (requested {requested})"
                )
        resolved = requested.resolve()
    except OSError as error:
        raise CorpusError(f"workspace path is unreadable: {requested}") from error
    if resolved != requested:
        raise CorpusError(
            "workspace path must not traverse an alias or reparse point: "
            f"{requested} resolves to {resolved}"
        )
    return resolved


def _validate_plain_path(path: Path) -> None:
    try:
        if _is_reparse_point(path) or path.resolve() != path:
            raise CorpusError(
                f"workspace directory was replaced by a reparse point: {path}"
            )
    except OSError as error:
        raise CorpusError(f"workspace directory is unreadable: {path}") from error


def _reject_dangerous(path: Path) -> None:
    resolved = Path(path).resolve()
    if resolved.parent == resolved:
        raise CorpusError(f"refusing to operate on a filesystem root: {resolved}")
    repository = Path(__file__).resolve().parents[1]
    for guarded in (Path.home().resolve(), Path.cwd().resolve(), repository):
        if resolved == guarded or guarded.is_relative_to(resolved):
            raise CorpusError(
                f"refusing to operate on {resolved}: it contains or equals {guarded}"
            )
    if resolved.is_relative_to(repository):
        raise CorpusError(
            f"refusing to operate inside the repository: {resolved}. "
            "Tool workspaces belong on the volume under test, not in the source tree."
        )
