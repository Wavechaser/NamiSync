"""Corpus ownership, target pre-state materialization, and teardown.

The verifier only reads, so its corpus needs nothing beyond a path. The
executor writes, so the rig owns the target tree outright: it claims a
directory, materializes a pre-state into it before each run, and tears it down
afterwards.

Ownership markers live *beside* the target directory, never inside it. A marker
within the target root would be scanned as target content, would change the
planned operation mix, and -- under a deletion policy -- could be trashed by
the very run whose teardown depends on it.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import random
import shutil
import stat
from time import perf_counter

from namisync.core.pathing import to_extended_length_path


MARKER_SUFFIX = ".rig-owned"
MARKER_TEXT = "Owned by tools/rig. Safe to delete when no rig run is active.\n"

_UNITS = {"B": 1, "KIB": 1024, "MIB": 1024**2, "GIB": 1024**3}


class CorpusError(RuntimeError):
    """A corpus or workspace path is unusable or not rig-owned."""


def marker_for(target: Path) -> Path:
    target = Path(target)
    return target.parent / f"{target.name}{MARKER_SUFFIX}"


def claim(target: Path) -> Path:
    """Create or adopt a rig-owned workspace directory.

    An existing directory is adopted only when it already carries the marker.
    """

    target = Path(target).resolve()
    _reject_dangerous(target)
    marker = marker_for(target)
    if target.exists():
        if not target.is_dir():
            raise CorpusError(f"workspace path is not a directory: {target}")
        if not marker.exists():
            raise CorpusError(
                f"refusing to use existing directory without a rig marker: {target}. "
                f"Create {marker.name} beside it to adopt it, or choose another path."
            )
    else:
        target.mkdir(parents=True)
    marker.write_text(MARKER_TEXT, encoding="utf-8")
    return target


def is_owned(target: Path) -> bool:
    return marker_for(Path(target).resolve()).exists()


def teardown(target: Path, *, release: bool = True) -> None:
    """Delete a rig-owned tree, tolerating read-only files and long paths."""

    target = Path(target).resolve()
    _reject_dangerous(target)
    marker = marker_for(target)
    if not marker.exists():
        raise CorpusError(
            f"refusing to tear down a directory the rig does not own: {target}"
        )
    if target.exists():
        shutil.rmtree(to_extended_length_path(str(target)), onexc=_force_writable)
    if release:
        marker.unlink(missing_ok=True)


def empty(target: Path) -> None:
    """Remove a rig-owned tree's contents while keeping the claim."""

    teardown(target, release=False)
    Path(target).mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class MaterializeResult:
    files: int
    bytes_copied: int
    seconds: float


def materialize(template: Path, target: Path) -> MaterializeResult:
    """Copy a template pre-state into a rig-owned target, preserving mtimes.

    Timestamps must survive, otherwise the planner sees every target file as
    stale and the operation mix collapses to all-UPDATE.
    """

    template = Path(template).resolve()
    target = Path(target).resolve()
    if not template.is_dir():
        raise CorpusError(f"template is not a directory: {template}")
    if not is_owned(target):
        raise CorpusError(f"refusing to materialize into an unowned directory: {target}")
    empty(target)

    started = perf_counter()
    files = 0
    copied = 0
    native_template = to_extended_length_path(str(template))
    for source_dir, _, names in os.walk(native_template):
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
    root: Path,
    spec: str,
    *,
    seed: int = 0,
    per_directory: int = 256,
) -> GenerateResult:
    """Write a deterministic tree from a ``count@size`` specification.

    ``2000@4KiB,200@1MiB,4@256MiB`` produces the same bytes for the same seed,
    so a generated corpus is as reproducible as a fixed one.
    """

    root = Path(root).resolve()
    _reject_dangerous(root)
    groups = parse_spec(spec)
    root.mkdir(parents=True, exist_ok=True)

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
    except ValueError:
        raise ValueError(f"cannot parse size {text!r}") from None
    size = int(scaled)
    if size < 0 or size != scaled:
        raise ValueError(f"size {text!r} must be a non-negative whole number of bytes")
    return size


def _force_writable(function, path, error) -> None:
    # rmtree's onexc hook: the executor preserves FILE_ATTRIBUTE_READONLY, so a
    # torn-down tree routinely contains files rmtree cannot unlink as-is.
    del function, error
    os.chmod(path, stat.S_IWRITE)
    if os.path.isdir(path):
        os.rmdir(path)
    else:
        os.unlink(path)


def _reject_dangerous(path: Path) -> None:
    resolved = Path(path).resolve()
    if resolved.parent == resolved:
        raise CorpusError(f"refusing to operate on a filesystem root: {resolved}")
    repository = Path(__file__).resolve().parents[2]
    for guarded in (Path.home().resolve(), Path.cwd().resolve(), repository):
        if resolved == guarded or guarded.is_relative_to(resolved):
            raise CorpusError(
                f"refusing to operate on {resolved}: it contains or equals {guarded}"
            )
    if resolved.is_relative_to(repository):
        raise CorpusError(
            f"refusing to operate inside the repository: {resolved}. "
            "Rig workspaces belong on the volume under test, not in the source tree."
        )
