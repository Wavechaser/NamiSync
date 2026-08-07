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
import random
import shutil
import stat
from time import perf_counter
from typing import BinaryIO

from namisync.core.pathing import to_extended_length_path


MARKER_SUFFIX = ".rig-owned"
LEASE_SUFFIX = ".rig-lease"
LEASE_MAGIC = b"namisync-tools-workspace-lease-v1\n"
MARKER_SCHEMA = 1
MARKER_OWNER = "namisync-tools"
MARKER_MAX_BYTES = 4096

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
    if _is_reparse_point(requested):
        raise CorpusError(f"workspace path must not be a reparse point: {requested}")
    target = requested.resolve()
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

    target = Path(target).resolve()
    try:
        identity = _directory_identity(target)
        _validate_marker(marker_for(target), target, identity)
    except CorpusError:
        return False
    return True


def teardown(workspace: WorkspaceClaim) -> None:
    """Delete a claimed tree, tolerating read-only files and long paths."""

    target = _claimed_target(workspace)
    shutil.rmtree(to_extended_length_path(str(target)), onexc=_force_writable)
    _unlink_writable(marker_for(target))
    workspace._retire()


def empty(workspace: WorkspaceClaim) -> None:
    """Remove a claimed tree's contents while retaining its identity and marker."""

    target = _claimed_target(workspace)
    with os.scandir(to_extended_length_path(str(target))) as entries:
        for entry in entries:
            if entry.is_dir(follow_symlinks=False) or os.path.isjunction(entry.path):
                shutil.rmtree(entry.path, onexc=_force_writable)
            else:
                _unlink_writable(Path(entry.path))


@dataclass(frozen=True, slots=True)
class MaterializeResult:
    files: int
    bytes_copied: int
    seconds: float


def materialize(template: Path, workspace: WorkspaceClaim) -> MaterializeResult:
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
    empty(workspace)

    started = perf_counter()
    files = 0
    copied = 0
    native_template = to_extended_length_path(str(template))
    for source_dir, _, names in os.walk(native_template, onerror=_raise_walk_error):
        relative = os.path.relpath(source_dir, native_template)
        destination_dir = target if relative == "." else target / relative
        os.makedirs(to_extended_length_path(str(destination_dir)), exist_ok=True)
        for name in names:
            source = to_extended_length_path(str(Path(source_dir) / name))
            destination = to_extended_length_path(str(destination_dir / name))
            shutil.copy2(source, destination)
            files += 1
            copied += os.stat(source).st_size
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
) -> GenerateResult:
    """Replace a claimed root with a deterministic ``count@size`` tree."""

    root = _claimed_target(workspace)
    groups = parse_spec(spec)
    empty(workspace)

    started = perf_counter()
    rng = random.Random(seed)
    files = 0
    written = 0
    index = 0
    for count, size in groups:
        for _ in range(count):
            directory = root / f"d{index // per_directory:04d}"
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"f{index:06d}_{size}.bin"
            with open(to_extended_length_path(str(path)), "wb") as handle:
                remaining = size
                while remaining:
                    block = min(remaining, 1024 * 1024)
                    handle.write(rng.randbytes(block))
                    remaining -= block
            files += 1
            written += size
            index += 1
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
    try:
        with open(to_extended_length_path(str(marker)), encoding="utf-8") as handle:
            if os.fstat(handle.fileno()).st_size > MARKER_MAX_BYTES:
                raise CorpusError(f"ownership marker is too large: {marker}")
            actual = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
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


def _force_writable(function, path, error) -> None:
    # rmtree's onexc hook: the executor preserves FILE_ATTRIBUTE_READONLY, so a
    # torn-down tree routinely contains files rmtree cannot unlink as-is.
    del function, error
    os.chmod(path, stat.S_IWRITE)
    if os.path.isdir(path):
        os.rmdir(path)
    else:
        os.unlink(path)


def _raise_walk_error(error: OSError) -> None:
    raise CorpusError(f"could not walk template directory: {error}") from error


def _is_reparse_point(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


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
