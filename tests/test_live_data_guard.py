"""M2-A1 suite guard: tests cannot change the live production data root.

End-to-end cases drive the real session hook against the real live root, but
every mutating case targets a path whose parent does not exist, so even a
regressed hook could only fail with ``FileNotFoundError`` and create nothing.
Matching rules are covered against a tmp root so no case depends on the
machine's profile. Refusals the tests expect are acknowledged with
``expected_refusals``; any other recorded refusal fails the test.
"""

from __future__ import annotations

import ast
import os
import shutil
import sqlite3
import threading
from pathlib import Path

import _winapi
import pytest

from namisync.db.claims import acquire_database_claim

import _live_data_guard as guard
from _live_data_guard import (
    LiveDataGuardError,
    check_event,
    expected_refusals,
)


LIVE_ROOT = guard.known_live_root()
PROBE = LIVE_ROOT / "m2-a1-guard-probe"
# Neither PROBE nor its "absent" child exists, so no operation here can succeed.
ABSENT = PROBE / "absent" / "x"


@pytest.fixture
def armed():
    """Run only once the real hook is proven to be wired to the real root."""

    assert guard.installed_root() == LIVE_ROOT, "the M2-A1 session guard is not installed"
    assert not PROBE.exists()
    # Without a working hook this raises FileNotFoundError, never creates.
    with expected_refusals(("open", ABSENT)), pytest.raises(LiveDataGuardError):
        open(ABSENT, "w")
    yield
    assert not PROBE.exists()


def test_live_root_is_the_known_folder_not_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert guard.known_live_root() == LIVE_ROOT
    assert LIVE_ROOT.name == "NamiSync"
    assert not LIVE_ROOT.is_relative_to(tmp_path)


@pytest.mark.parametrize("mode", ["w", "a", "x", "wb", "w+", "r+"])
def test_writing_open_of_a_missing_live_file_is_refused(armed, mode: str) -> None:
    with expected_refusals(("open", ABSENT)):
        with pytest.raises(LiveDataGuardError, match="M2-A1") as raised:
            open(ABSENT, mode)

    assert str(ABSENT) in str(raised.value)
    assert str(LIVE_ROOT) in str(raised.value)


def test_path_open_and_os_open_for_writing_are_refused(armed) -> None:
    for operation in (
        lambda: ABSENT.write_text("{}"),
        lambda: os.open(ABSENT, os.O_CREAT | os.O_WRONLY),
        lambda: os.open(ABSENT, os.O_RDONLY | os.O_TEMPORARY),
    ):
        with expected_refusals(("open", ABSENT)), pytest.raises(LiveDataGuardError):
            operation()


def test_database_claim_file_creation_under_the_live_root_is_refused(armed) -> None:
    claim = Path(f"{ABSENT}.claim")
    for exclusive in (False, True):
        with expected_refusals(("open", claim)), pytest.raises(LiveDataGuardError):
            acquire_database_claim(ABSENT, exclusive=exclusive)
    assert not claim.parent.exists()


def test_sqlite_connect_under_the_live_root_is_refused(armed) -> None:
    for target in (str(ABSENT), ABSENT, ABSENT.as_uri() + "?mode=rwc"):
        with expected_refusals(("sqlite3.connect", target)):
            with pytest.raises(LiveDataGuardError, match="sqlite3"):
                sqlite3.connect(
                    target, uri=isinstance(target, str) and target.startswith("file:")
                )


SOURCE = PROBE / "absent-source"


@pytest.mark.parametrize(
    ("operation", "event", "offender"),
    [
        (lambda: os.mkdir(ABSENT), "os.mkdir", ABSENT),
        (lambda: ABSENT.mkdir(), "os.mkdir", ABSENT),
        (lambda: os.rename(ABSENT, ABSENT.with_name("y")), "os.rename", ABSENT),
        (lambda: os.replace(SOURCE, ABSENT), "os.rename", SOURCE),
        (lambda: os.remove(ABSENT), "os.remove", ABSENT),
        (lambda: os.rmdir(ABSENT), "os.rmdir", ABSENT),
        (lambda: shutil.rmtree(ABSENT), "shutil.rmtree", ABSENT),
        (lambda: os.chmod(ABSENT, 0o666), "os.chmod", ABSENT),
        (lambda: os.utime(ABSENT), "os.utime", ABSENT),
        (lambda: os.truncate(ABSENT, 0), "os.truncate", ABSENT),
        (lambda: os.symlink("anywhere", ABSENT), "os.symlink", ABSENT),
        (lambda: os.link(__file__, ABSENT), "os.link", ABSENT),
        (
            lambda: _winapi.CreateFile(str(ABSENT), 0x40000000, 0, 0, 2, 0x80, 0),
            "_winapi.CreateFile",
            ABSENT,
        ),
        (
            lambda: _winapi.CreateFile(
                str(ABSENT), 0x80000000, 0, 0, 3, 0x80 | 0x04000000, 0
            ),
            "_winapi.CreateFile",
            ABSENT,
        ),
        (
            lambda: _winapi.CreateJunction(__file__, str(ABSENT)),
            "_winapi.CreateJunction",
            ABSENT,
        ),
    ],
    ids=[
        "mkdir",
        "Path.mkdir",
        "rename-source",
        "replace-source",
        "remove",
        "rmdir",
        "rmtree",
        "chmod",
        "utime",
        "truncate",
        "symlink",
        "link",
        "winapi-CreateFile-write",
        "winapi-CreateFile-delete-on-close",
        "winapi-CreateJunction",
    ],
)
def test_changing_an_entry_under_the_live_root_is_refused(
    armed, operation, event: str, offender: Path
) -> None:
    with expected_refusals((event, offender)):
        with pytest.raises(LiveDataGuardError, match="M2-A1"):
            operation()


def test_reads_stats_and_listings_of_the_live_root_stay_allowed(armed) -> None:
    with pytest.raises(FileNotFoundError):
        open(ABSENT, "rb")
    with pytest.raises(FileNotFoundError):
        os.stat(ABSENT)
    with pytest.raises(FileNotFoundError):
        os.listdir(PROBE)
    assert not PROBE.exists()

    try:
        LIVE_ROOT.lstat()
        with open(LIVE_ROOT / "ledger.db", "rb") as stream:
            stream.read(1)
    except FileNotFoundError:
        pass  # a machine without the release's data has nothing to read
    # _winapi read-only access is not a write.
    with pytest.raises(FileNotFoundError):
        _winapi.CreateFile(str(ABSENT), 0x80000000, 0, 0, 3, 0x80, 0)


def test_the_development_root_is_not_the_live_root() -> None:
    development = LIVE_ROOT.with_name("NamiSync-Development")

    for event, args in (
        ("open", (development / "ledger.db", "w", 0)),
        ("sqlite3.connect", (str(development / "history.db"),)),
        ("os.mkdir", (development, 0o777, -1)),
        ("os.rename", (development / "a", development / "b", -1, -1)),
    ):
        check_event(event, args, LIVE_ROOT)


@pytest.fixture
def fake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "Local" / "NamiSync"
    root.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    return root


def _refused(event: str, args: tuple, root: Path, offender: object = None) -> bool:
    """Report whether the pure matcher refuses; ``offender`` defaults to args[0]."""

    expected = (event, args[0] if offender is None else offender)
    try:
        with expected_refusals(expected):
            check_event(event, args, root)
    except LiveDataGuardError:
        return True
    except AssertionError:  # nothing was refused
        return False
    return False


def test_matching_compares_normalized_path_components(
    fake_root: Path, tmp_path: Path
) -> None:
    child = fake_root / "ledger.db"
    spellings = [
        str(child),
        str(child).upper(),
        str(child).lower(),
        str(child).replace("\\", "/"),
        "\\\\?\\" + str(child),
        "\\\\.\\" + str(child),
        str(fake_root / "logs" / ".." / "ledger.db"),
        str(fake_root) + "\\",
        str(fake_root),
        os.fsencode(str(child)),
        child,
    ]
    for spelling in spellings:
        assert _refused("os.mkdir", (spelling, 0o777, -1), fake_root), spelling
        assert _refused("open", (spelling, "wb", 0), fake_root), spelling

    for sibling in (
        fake_root.with_name("NamiSync-Development") / "ledger.db",
        fake_root.with_name("NamiSyncX"),
        fake_root.parent,
        tmp_path / "elsewhere" / "NamiSync-Development",
    ):
        assert not _refused("os.mkdir", (sibling, 0o777, -1), fake_root), sibling


def test_relative_paths_resolve_against_the_working_directory(
    fake_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert not _refused("open", ("ledger.db", "w", 0), fake_root)
    monkeypatch.chdir(fake_root)

    assert _refused("open", ("ledger.db", "w", 0), fake_root)
    assert _refused("os.mkdir", ("logs", 0o777, -1), fake_root)
    assert _refused(
        "os.rename", ("..\\other", "moved", -1, -1), fake_root, offender="moved"
    )
    assert not _refused("open", ("..\\NamiSync-Development\\x", "w", 0), fake_root)


def test_open_is_refused_only_for_writing_modes_or_flags(fake_root: Path) -> None:
    target = str(fake_root / "ledger.db")
    read_flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0)

    assert not _refused("open", (target, "r", read_flags), fake_root)
    assert not _refused("open", (target, "rb", 0), fake_root)
    assert not _refused("open", (target, None, read_flags), fake_root)
    for mode in ("w", "a", "x", "r+", "wb", "ab"):
        assert _refused("open", (target, mode, 0), fake_root), mode
    for flag in (
        os.O_WRONLY,
        os.O_RDWR,
        os.O_APPEND,
        os.O_CREAT,
        os.O_TRUNC,
        os.O_EXCL,
        os.O_TEMPORARY,
    ):
        assert _refused("open", (target, None, flag | read_flags), fake_root), flag


def test_winapi_create_file_is_refused_only_for_writing_access(
    fake_root: Path,
) -> None:
    target = str(fake_root / "ledger.db")
    generic_read, generic_write, delete, write_data = 0x80000000, 0x40000000, 0x10000, 0x2
    open_existing, create_new, truncate_existing = 3, 1, 5

    assert not _refused(
        "_winapi.CreateFile", (target, generic_read, 0, open_existing, 0x80), fake_root
    )
    maximum_allowed, delete_child = 0x02000000, 0x40
    for access in (generic_write, delete, write_data, maximum_allowed, delete_child):
        assert _refused(
            "_winapi.CreateFile", (target, access, 0, open_existing, 0x80), fake_root
        ), access
    for disposition in (create_new, truncate_existing):
        assert _refused(
            "_winapi.CreateFile",
            (target, generic_read, 0, disposition, 0x80),
            fake_root,
        ), disposition
    delete_on_close = 0x04000000
    assert _refused(
        "_winapi.CreateFile",
        (target, generic_read, 0, open_existing, 0x80 | delete_on_close),
        fake_root,
    )
    assert _refused("_winapi.CreateJunction", (__file__, target), fake_root, target)
    assert not _refused("_winapi.CreateJunction", (target, __file__), fake_root)


@pytest.mark.parametrize(
    "database",
    [
        lambda root: str(root / "history.db"),
        lambda root: root / "history.db",
        lambda root: root.as_uri() + "/history.db",
        lambda root: "file:" + str(root / "history.db").replace("\\", "/") + "?mode=ro",
        lambda root: "FILE:///" + str(root / "history.db").replace("\\", "/"),
        lambda root: root.as_uri().replace("NamiSync", "Nami%53ync") + "/history.db",
    ],
)
def test_sqlite_uri_and_path_spellings_resolve_to_the_root(
    fake_root: Path, database
) -> None:
    assert _refused("sqlite3.connect", (database(fake_root),), fake_root)


def test_sqlite_memory_and_foreign_databases_are_not_refused(
    fake_root: Path, tmp_path: Path
) -> None:
    for database in (
        ":memory:",
        "",
        "file::memory:?cache=shared",
        str(tmp_path / "other.db"),
        (tmp_path / "other.db").as_uri(),
        (fake_root.with_name("NamiSync-Development") / "x.db").as_uri(),
        # A host authority is a UNC path, never relative to the working directory.
        "file://host/share/NamiSync/history.db",
    ):
        assert not _refused("sqlite3.connect", (database,), fake_root), database


@pytest.mark.parametrize(
    "event,args",
    [
        ("open", ()),
        ("open", (3, "w", 0)),
        ("open", (None, "w", 0)),
        ("open", (object(), object(), object())),
        ("open", (b"\xff\xfe", "w", 0)),
        ("os.mkdir", ()),
        ("os.rename", (object(),)),
        ("os.remove", (None, -1)),
        ("os.truncate", (7, 0)),
        ("sqlite3.connect", ()),
        ("sqlite3.connect", (object(),)),
        ("_winapi.CreateFile", ()),
        ("_winapi.CreateFile", ("x", object(), 0, object(), 0)),
        ("not.watched", ("anything",)),
    ],
)
def test_odd_arguments_never_raise_from_the_hook(
    fake_root: Path, event: str, args: tuple
) -> None:
    check_event(event, args, fake_root)


def test_installation_is_idempotent_and_reports_the_live_root() -> None:
    assert guard.install() == LIVE_ROOT
    assert guard.installed_root() == LIVE_ROOT


def test_the_refusal_check_runs_after_every_test(
    request: pytest.FixtureRequest,
) -> None:
    assert "_live_data_guard_refusals" in request.fixturenames


@pytest.mark.parametrize("real_hook", (False, True))
def test_a_swallowed_refusal_still_fails_the_test(
    fake_root: Path, real_hook: bool
) -> None:
    """A product ``except BaseException`` cannot hide a refusal from the suite."""

    try:
        if real_hook:
            open(ABSENT, "w")
        else:
            check_event("os.mkdir", (str(fake_root / "x"), 0o777, -1), fake_root)
    except BaseException:
        pass

    with pytest.raises(pytest.fail.Exception, match="even if the code swallowed"):
        guard.fail_on_unacknowledged_refusals()
    guard.fail_on_unacknowledged_refusals()  # drained; the finalizer stays quiet
    assert not PROBE.exists()


def test_expected_refusals_acknowledge_only_the_named_pairs(fake_root: Path) -> None:
    named, other = fake_root / "named", fake_root / "other"

    with expected_refusals(("os.mkdir", named)):
        with pytest.raises(LiveDataGuardError):
            check_event("os.mkdir", (str(named), 0o777, -1), fake_root)
        with pytest.raises(LiveDataGuardError):
            check_event("os.mkdir", (str(other), 0o777, -1), fake_root)
    with expected_refusals(("os.mkdir", named)):
        with pytest.raises(LiveDataGuardError):
            check_event("os.mkdir", (str(named), 0o777, -1), fake_root)
        with pytest.raises(LiveDataGuardError):
            check_event("os.rmdir", (str(named),), fake_root)

    # The unnamed refusals stay recorded, so the finalizer still fails the test.
    with pytest.raises(pytest.fail.Exception, match="os.mkdir .*other"):
        guard.fail_on_unacknowledged_refusals()


def test_expected_refusals_must_occur(fake_root: Path) -> None:
    with pytest.raises(AssertionError, match="did not occur"):
        with expected_refusals(("os.mkdir", fake_root / "x")):
            pass
    with pytest.raises(ValueError):
        with expected_refusals():
            pass


def test_refusals_on_other_threads_are_not_acknowledged(fake_root: Path) -> None:
    target = fake_root / "threaded"

    def refuse() -> None:
        try:
            check_event("os.mkdir", (str(target), 0o777, -1), fake_root)
        except LiveDataGuardError:
            pass

    with pytest.raises(AssertionError, match="did not occur"):
        with expected_refusals(("os.mkdir", target)):
            worker = threading.Thread(target=refuse)
            worker.start()
            worker.join()

    with pytest.raises(pytest.fail.Exception, match="os.mkdir .*threaded"):
        guard.fail_on_unacknowledged_refusals()


def test_refusals_recorded_outside_a_test_are_named_at_setup(fake_root: Path) -> None:
    try:
        check_event("os.mkdir", (str(fake_root / "early"), 0o777, -1), fake_root)
    except LiveDataGuardError:
        pass

    with pytest.raises(pytest.fail.Exception, match="outside this test: os.mkdir .*early"):
        guard.fail_on_unacknowledged_refusals(setup=True)
    assert guard.take_refusals() == []


def test_only_the_guard_tests_use_expected_refusals() -> None:
    tests_root = Path(__file__).parent
    allowed = {
        tests_root / "_live_data_guard.py",
        Path(__file__),
    }
    users = []
    for source in tests_root.rglob("*.py"):
        if source in allowed or "build" in source.parts:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Name):
                names.append(node.id)
            elif isinstance(node, ast.Attribute):
                names.append(node.attr)
            elif isinstance(node, ast.alias):
                names.append(node.name)
            if "expected_refusals" in names:
                users.append(source)
    assert users == []
