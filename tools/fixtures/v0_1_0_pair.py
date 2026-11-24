"""Produce a ledger/history pair written by the released NamiSync v0.1.0 CLI.

The saved pair in ``tests/assets/v0_1_0/`` is the fixture; this producer is
the method that made it. A rerun writes new run tokens, timestamps, volume
evidence and absolute paths, so its bytes never match the saved pair. The
producer never writes into ``tests/assets/``: promotion is a deliberate manual
copy of a reviewed run's ``data/`` files and ``provenance.json``.

v0.1.0 exits with its committed rows still in the ``-wal`` sidecar (the main
files hold only the schema), so the files it leaves are the main database plus
``-wal`` and ``-shm`` for each of the pair. The producer reads them only from
copies under ``OUTPUT/inspect``.

Containment: the released executable defaults to ``%LOCALAPPDATA%\\NamiSync``,
the user's live data. Every child therefore runs with ``LOCALAPPDATA`` pointed
at an empty folder inside OUTPUT, and every command that can open a database
also passes explicit ``--database`` and ``--history-database`` paths inside
OUTPUT; the three ``--help`` invocations exit inside argument parsing and run
only under the ``LOCALAPPDATA`` override. The run stops if anything appears in
that substitute folder; a change in the real live root's top-level listing is
only reported as a warning, since the user's own NamiSync may be running. The
GUI executable and the ``history`` command, which takes no ledger flag, are
never run.

OUTPUT must be new or empty and may not be, or lie inside, the live root
(resolved from the Windows known folder, not the environment) or
``tests/assets``. Both are compared by spelling and, when they exist, by
identity (``os.path.samefile`` on OUTPUT and each existing ancestor), which
catches case, ``..``, verbatim ``\\\\?\\``, UNC and junction aliases. If the
live root does not exist, only the spelling comparison applies.

Each step's ``expected`` exit is what v0.1.0 returned when the fixture was
made; a rerun that differs prints the provenance and exits 1.

Usage::

    python -m tools.fixtures.v0_1_0_pair dist/v0.1.0/NamiSync-0.1.0-windows-x64.zip build/<fresh-folder>
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import msvcrt
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import subprocess
import sys
from typing import Callable, Iterator
import uuid
import zipfile


ARCHIVE_NAME = "NamiSync-0.1.0-windows-x64.zip"
ARCHIVE_SHA256 = "652c55ca3c2ace0903732490ead0b907ac726dba5af4155aa5345db80c8e9efc"
EXECUTABLE_MEMBER = "NamiSync/namisync.exe"
SQLITE_MEMBER = "NamiSync/_internal/sqlite3.dll"
PROMPT_MARKER = b"uncommitted: "
STEP_TIMEOUT_SECONDS = 600
REPOSITORY = Path(__file__).resolve().parents[2]
FOLDERID_LOCAL_APP_DATA = uuid.UUID("F1B32785-6FBA-4FCF-9D55-7B8E7F157091")


class Refused(Exception):
    """The producer cannot run or continue safely."""


def live_root() -> Path:
    """Return the live data root from the LocalAppData known folder."""

    folder = (ctypes.c_ubyte * 16).from_buffer_copy(FOLDERID_LOCAL_APP_DATA.bytes_le)
    shell32 = ctypes.WinDLL("shell32")
    ole32 = ctypes.WinDLL("ole32")
    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    pointer = ctypes.c_void_p()
    status = shell32.SHGetKnownFolderPath(
        ctypes.byref(folder), 0, None, ctypes.byref(pointer)
    )
    try:
        if status != 0 or not pointer.value:
            raise Refused(f"cannot resolve LocalAppData (HRESULT {status})")
        return Path(ctypes.wstring_at(pointer.value)) / "NamiSync"
    finally:
        ole32.CoTaskMemFree(pointer)


def lies_within(path: Path, forbidden: Path) -> bool:
    """Whether ``path`` is or lies inside ``forbidden``, by spelling or identity.

    The identity check compares ``path`` and each existing ancestor with
    ``forbidden`` through ``os.path.samefile``, which catches verbatim, UNC and
    junction aliases; it needs ``forbidden`` to exist.
    """

    candidates = {Path(os.path.abspath(path)), path.resolve()}
    target = forbidden.resolve()
    for candidate in candidates:
        if candidate == target or candidate.is_relative_to(target):
            return True
    if not forbidden.exists():
        return False
    for candidate in candidates:
        for ancestor in (candidate, *candidate.parents):
            try:
                if ancestor.exists() and os.path.samefile(ancestor, forbidden):
                    return True
            except OSError:
                continue
    return False


def admit_output(output: Path, live: Path | None = None) -> Path:
    """Refuse an OUTPUT inside the live root or ``tests/assets``, or not empty.

    ``live`` defaults to the live data root; tests pass a stand-in.
    """

    resolved = output.resolve()
    for forbidden, label in (
        (live_root() if live is None else live, "the live data root"),
        (REPOSITORY / "tests" / "assets", "tests/assets"),
    ):
        if lies_within(output, forbidden):
            raise Refused(f"OUTPUT {resolved} is or lies inside {label}")
    if resolved.exists() and any(resolved.iterdir()):
        raise Refused(f"OUTPUT {resolved} is not empty; choose a fresh folder")
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def extract(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            name = PurePosixPath(member.filename)
            if name.is_absolute() or ".." in name.parts or ":" in member.filename:
                raise Refused(f"unsafe archive member {member.filename!r}")
        bundle.extractall(destination)


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def rewrite_same_size(path: Path) -> None:
    """Change content while keeping size and modification time."""

    before = path.stat()
    data = path.read_bytes()
    changed = data.swapcase()
    if len(changed) != len(data) or changed == data:
        raise Refused(f"cannot make a same-size change to {path.name}")
    path.write_bytes(changed)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))


@contextmanager
def byte_locked(path: Path) -> Iterator[None]:
    """Hold a byte-range lock so another process cannot read the file."""

    size = path.stat().st_size
    with path.open("rb+") as handle:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, size)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, size)


class Run:
    """Contained invocations of one extracted release executable."""

    def __init__(
        self, output: Path, executable: Path, launcher: tuple[str, ...] = ()
    ) -> None:
        self.output = output
        self.executable = executable
        self.launcher = launcher  # tests run a stub script through an interpreter
        self.ledger = output / "data" / "ledger.db"
        self.history = output / "data" / "history.db"
        self.sandbox = output / "localappdata"
        self.logs = output / "logs"
        for folder in (self.ledger.parent, self.sandbox, self.logs):
            folder.mkdir(parents=True)
        self.environment = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith("PYTHON")
        }
        self.environment["LOCALAPPDATA"] = str(self.sandbox)
        self.environment["PYTHONIOENCODING"] = "utf-8"
        self.steps: list[dict] = []

    def relative(self, value: str) -> str:
        if value == str(self.executable):
            return "namisync.exe"
        return value.replace(str(self.output), "<OUTPUT>")

    def invoke(
        self,
        name: str,
        arguments: list[str | Path],
        *,
        expected: int,
        answer: str | None = None,
        before_answer: Callable[[], None] | None = None,
        databases: bool = True,
    ) -> int:
        argv = [str(self.executable), *map(str, arguments)]
        if databases:
            argv += ["--database", str(self.ledger)]
            argv += ["--history-database", str(self.history)]
        process = subprocess.Popen(
            [*self.launcher, *argv],
            cwd=self.output,
            env=self.environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        captured = bytearray()
        prompted = False
        if answer is not None:
            while PROMPT_MARKER not in captured:
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    break
                captured += chunk
            prompted = PROMPT_MARKER in captured
            if prompted:
                if before_answer is not None:
                    before_answer()
                process.stdin.write(answer.encode() + b"\n")
                process.stdin.flush()
        rest = b""
        try:
            rest, _ = process.communicate(timeout=STEP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            rest, _ = process.communicate()
            raise Refused(f"step {name} exceeded {STEP_TIMEOUT_SECONDS} s")
        finally:
            log = self.logs / f"{len(self.steps) + 1:02d}-{name}.txt"
            log.write_bytes(bytes(captured) + (rest or b""))
        step = {
            "step": name,
            "command": [self.relative(value) for value in argv],
            "exit": process.returncode,
            "expected": expected,
        }
        if answer is not None:
            step["answer"] = answer if prompted else None
        self.steps.append(step)
        leaked = sorted(entry.name for entry in self.sandbox.iterdir())
        if leaked:
            raise Refused(
                f"step {name} wrote {leaked} under the substitute LOCALAPPDATA; "
                "the binary resolved a default path"
            )
        return process.returncode


def scenario(run: Run) -> None:
    roots = run.output / "roots"
    alpha_source, alpha_target = roots / "alpha-source", roots / "alpha-target"
    beta_source, beta_target = roots / "beta-source", roots / "beta-target"
    gamma = roots / "gamma"
    alpha_target.mkdir(parents=True)
    beta_target.mkdir(parents=True)
    write(alpha_source / "readme.txt", b"NamiSync v0.1.0 fixture\r\n")
    write(alpha_source / "Ünïcødé ファイル.txt", "非ASCII name with a space\n".encode())
    write(alpha_source / "empty.dat", b"")
    write(alpha_source / "nested" / "note with space.md", b"# note\n")
    write(alpha_source / "nested" / "deep" / "leaf.bin", bytes(range(256)))
    write(alpha_source / "photos" / "a.txt", b"a\n")
    write(alpha_source / "photos" / "b.txt", b"b\n")
    write(beta_source / "one.txt", b"one\n")
    write(beta_source / "sub" / "two.txt", b"two\n")
    write(gamma / "keep.txt", b"keep\n")
    write(gamma / "empty.txt", b"")
    write(gamma / "data" / "same-size.txt", b"same size content\n")
    write(gamma / "gone.txt", b"gone\n")

    run.invoke("help", ["--help"], expected=0, databases=False)
    run.invoke("sync-help", ["sync", "--help"], expected=0, databases=False)
    run.invoke("inventory-help", ["inventory", "--help"], expected=0, databases=False)

    alpha = ["sync", alpha_source, alpha_target, "--deletion-policy", "trash"]
    run.invoke("alpha-copy", [*alpha, "--verify-after-copy"], expected=0, answer="execute")
    write(alpha_source / "readme.txt", b"NamiSync v0.1.0 fixture, updated\r\n")
    (alpha_source / "nested" / "note with space.md").rename(
        alpha_source / "nested" / "deep" / "moved note.md"
    )
    (alpha_source / "photos" / "b.txt").unlink()
    run.invoke(
        "alpha-update-move-trash",
        [*alpha, "--verify-after-copy"],
        expected=0,
        answer="execute",
    )
    run.invoke("alpha-noop", alpha, expected=0, answer="execute")

    beta = ["sync", beta_source, beta_target]
    run.invoke("beta-copy", beta, expected=0, answer="execute")
    write(beta_source / "late.txt", b"late\n")
    run.invoke(
        "beta-drift-refused",
        beta,
        expected=3,
        answer="execute",
        before_answer=lambda: write(
            beta_source / "late.txt", b"late, changed after review\n"
        ),
    )
    with byte_locked(beta_source / "late.txt"):
        run.invoke("beta-locked-failed", beta, expected=4, answer="execute")
    run.invoke("beta-recovered", beta, expected=0, answer="execute")

    run.invoke("gamma-inventory", ["inventory", gamma], expected=0)
    run.invoke("gamma-baseline", ["baseline", gamma], expected=0)
    run.invoke("gamma-verify", ["verify", gamma], expected=0)
    rewrite_same_size(gamma / "data" / "same-size.txt")
    (gamma / "gone.txt").unlink()
    run.invoke("gamma-verify-mismatch", ["verify", gamma], expected=8)
    run.invoke("gamma-inventory-missing", ["inventory", gamma], expected=0)
    run.invoke(
        "gamma-rebaseline",
        [
            "rebaseline",
            gamma,
            "--path",
            "data/same-size.txt",
            "--accept-current-evidence",
        ],
        expected=0,
    )
    run.invoke("alpha-target-inventory", ["inventory", alpha_target], expected=0)
    run.invoke("alpha-target-baseline", ["baseline", alpha_target], expected=0)


def table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    ]
    return {
        table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in tables
    }


def inspect_database(main: Path, scratch: Path) -> dict:
    """Describe one written database without opening the written files.

    v0.1.0 exits with its committed rows still in ``-wal``, so the main file
    and its sidecars are hashed in place, then copied: the copy is read through
    a read-only connection (WAL applied) and its main file alone through an
    immutable one.
    """

    files = {}
    for suffix in ("", "-wal", "-shm"):
        path = main.with_name(main.name + suffix)
        if path.exists():
            files[path.name] = {"sha256": sha256_file(path), "size": path.stat().st_size}
            shutil.copyfile(path, scratch / path.name)
    copy = scratch / main.name
    header = copy.read_bytes()[:100]
    connection = sqlite3.connect(f"{copy.as_uri()}?mode=ro", uri=True)
    try:
        view = {
            name: connection.execute(f"PRAGMA {name}").fetchone()[0]
            for name in ("journal_mode", "user_version", "page_size", "page_count")
        }
        view["integrity_check"] = [
            row[0] for row in connection.execute("PRAGMA integrity_check")
        ]
        view["schema_metadata"] = dict(
            connection.execute("SELECT key, value FROM schema_metadata ORDER BY key")
        )
        view["row_counts"] = table_counts(connection)
    finally:
        connection.close()
    main_only = sqlite3.connect(f"{copy.as_uri()}?mode=ro&immutable=1", uri=True)
    try:
        view["main_only_row_counts"] = table_counts(main_only)
    finally:
        main_only.close()
    return {
        "files": files,
        "header_sqlite_version_number": int.from_bytes(header[96:100], "big"),
        "header_write_read_versions": [header[18], header[19]],
        **view,
    }


def live_snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """Stat the live root's top-level entries; never opens them."""

    if not root.is_dir():
        return {}
    return {
        entry.name: (entry.stat().st_size, entry.stat().st_mtime_ns)
        for entry in root.iterdir()
    }


def produce(archive: Path, output: Path) -> tuple[dict, bool]:
    output = admit_output(output)
    if archive.name != ARCHIVE_NAME:
        raise Refused(f"expected {ARCHIVE_NAME}, got {archive.name}")
    archive_sha256 = sha256_file(archive)
    if archive_sha256 != ARCHIVE_SHA256:
        raise Refused(f"{archive.name} SHA-256 {archive_sha256} is not the release")
    live = live_root()
    live_before = live_snapshot(live)
    started = datetime.now(timezone.utc).replace(microsecond=0)
    output.mkdir(parents=True, exist_ok=True)
    release = output / "release"
    extract(archive, release)
    executable = release / EXECUTABLE_MEMBER
    run = Run(output, executable)
    scenario(run)

    data_entries = sorted(entry.name for entry in run.ledger.parent.iterdir())
    journals = [name for name in data_entries if name.endswith("-journal")]
    if journals:
        raise Refused(f"rollback journals remain after the last command: {journals}")
    scratch = output / "inspect"
    scratch.mkdir()
    provenance = {
        "producer": "tools/fixtures/v0_1_0_pair.py",
        "produced_utc": started.isoformat().replace("+00:00", "Z"),
        "release": {
            "archive": ARCHIVE_NAME,
            "archive_sha256": archive_sha256,
            "executable": EXECUTABLE_MEMBER,
            "executable_sha256": sha256_file(executable),
            "sqlite_dll": SQLITE_MEMBER,
            "sqlite_dll_sha256": sha256_file(release / SQLITE_MEMBER),
        },
        "containment": {
            "LOCALAPPDATA": run.relative(str(run.sandbox)),
            "database": run.relative(str(run.ledger)),
            "history_database": run.relative(str(run.history)),
            "substitute_localappdata_entries": [],
        },
        "steps": run.steps,
        "data_folder_entries": data_entries,
        "databases": {
            "ledger": inspect_database(run.ledger, scratch),
            "history": inspect_database(run.history, scratch),
        },
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    live_after = live_snapshot(live)
    changed = sorted(
        name
        for name in set(live_before) | set(live_after)
        if live_before.get(name) != live_after.get(name)
    )
    if changed:
        print(
            f"warning: live root entries changed during the run: {changed}; "
            "check whether your own NamiSync process was running",
            file=sys.stderr,
        )
    else:
        print("live root top-level entries unchanged", file=sys.stderr)
    clean = all(step["exit"] == step["expected"] for step in run.steps)
    return provenance, clean


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.fixtures.v0_1_0_pair",
        description="Write a database pair with the released v0.1.0 CLI.",
    )
    parser.add_argument("archive", type=Path, help=f"path to {ARCHIVE_NAME}")
    parser.add_argument("output", type=Path, help="new or empty working folder")
    namespace = parser.parse_args(argv)
    try:
        provenance, clean = produce(namespace.archive, namespace.output)
    except Refused as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(provenance, indent=2, ensure_ascii=False))
    if not clean:
        print("some steps exited differently than v0.1.0 did", file=sys.stderr)
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
