"""M0 scanner acceptance and PoC regression tests."""

from __future__ import annotations

import builtins
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from namisync.core.models import (
    CapabilityProfile,
    IgnoreSet,
    Root,
    ScanScope,
    ScanWarningCode,
    UnsupportedReason,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import to_extended_length_path
from namisync.core.session import Canceled, RunContext
from namisync.modules.scanner import (
    FILE_ATTRIBUTE_OFFLINE,
    FILE_ATTRIBUTE_REPARSE_POINT,
    VolumeSnapshot,
    WalkingScanner,
)


def _ctx(checkpoint=lambda: None) -> RunContext:
    return RunContext(lambda event: None, checkpoint)


def test_clean_tree_is_complete_deterministic_and_records_every_directory(tmp_path: Path) -> None:
    (tmp_path / "b").mkdir()
    (tmp_path / "empty").mkdir()
    (tmp_path / "b" / "z.txt").write_text("z", encoding="utf-8")
    (tmp_path / "A.txt").write_text("a", encoding="utf-8")

    scanner = WalkingScanner()
    first = scanner.scan(Root(str(tmp_path), "source"), IgnoreSet(), _ctx())
    second = scanner.scan(Root(str(tmp_path), "source"), IgnoreSet(), _ctx())

    assert first.complete, first.warnings
    assert [record.rel_path for record in first.files] == ["A.txt", r"b\z.txt"]
    assert {record.rel_path for record in first.directories} == {"", "b", "empty"}
    assert [record.rel_path for record in first.files] == [record.rel_path for record in second.files]
    assert [record.rel_path for record in first.directories] == [record.rel_path for record in second.directories]
    assert all(record.metadata.created_ns is None or record.metadata.created_ns >= 0 for record in first.files)


def test_native_walk_recovers_identity_when_directory_entry_omits_it(
    tmp_path: Path,
) -> None:
    (tmp_path / "identity.bin").write_bytes(b"identity")

    result = WalkingScanner().scan(
        Root(str(tmp_path), "source"), IgnoreSet(), _ctx()
    )

    if result.profile.stable_file_identity:
        assert result.files[0].file_identity is not None


def test_scanner_never_opens_file_content_and_exact_ignores_preserve_user_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = tmp_path / ".namisync"
    owned.mkdir()
    for relative in (
        "customer.db",
        "my.synctmp-notes.txt",
        "customer.sha256",
        r".namisync\ledger.db",
        r".namisync\ledger.db-wal",
        r".namisync\history.db-shm",
        "asset.bin.synctmp-" + "a" * 32 + "-" + "b" * 32,
    ):
        path = tmp_path.joinpath(*relative.split("\\"))
        path.write_bytes(b"content")
    trash = tmp_path / ".synctrash"
    trash.mkdir()
    (trash / "hidden.txt").write_bytes(b"hidden")
    ignores = IgnoreSet.for_owned_paths([r".namisync\ledger.db", r".namisync\history.db"])

    monkeypatch.setattr(builtins, "open", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("content opened")))
    result = WalkingScanner().scan(Root(str(tmp_path), "source"), ignores, _ctx())

    retained = {record.rel_path for record in result.files}
    assert retained == {"customer.db", "my.synctmp-notes.txt", "customer.sha256"}
    assert result.complete


def test_offline_root_is_not_a_complete_empty_snapshot(tmp_path: Path) -> None:
    result = WalkingScanner().scan(Root(str(tmp_path / "not-mounted"), "source"), IgnoreSet(), _ctx())
    assert not result.complete
    assert result.volume_id is None
    assert result.files == ()
    assert result.warnings[0].code is ScanWarningCode.ROOT_UNAVAILABLE


def test_selected_refresh_is_complete_for_scope_without_a_full_walk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("one.txt", "two.txt", "third.txt"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    scanner = WalkingScanner()
    monkeypatch.setattr(scanner._backend, "scandir", lambda path: (_ for _ in ()).throw(AssertionError("full walk")))

    result = scanner.scan(
        Root(str(tmp_path), "source"),
        IgnoreSet(),
        _ctx(),
        ScanScope.selected(("one.txt", "two.txt", "missing.txt")),
    )

    assert result.complete
    assert {record.rel_path for record in result.files} == {"one.txt", "two.txt"}
    assert "third.txt" not in {record.rel_path for record in result.files}
    assert any(
        warning.code is ScanWarningCode.DISAPPEARED
        and warning.rel_path == "missing.txt"
        for warning in result.warnings
    )


def test_selected_refresh_access_failure_is_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    denied = tmp_path / "denied.txt"
    denied.write_bytes(b"content")
    scanner = WalkingScanner()
    original = scanner._backend.lstat

    def lstat(path: str):
        if Path(path).name == denied.name:
            raise PermissionError("denied")
        return original(path)

    monkeypatch.setattr(scanner._backend, "lstat", lstat)
    result = scanner.scan(
        Root(str(tmp_path), "source"),
        IgnoreSet(),
        _ctx(),
        ScanScope.selected((denied.name,)),
    )

    assert not result.complete
    assert result.unsupported[0].reason is UnsupportedReason.ACCESS_DENIED


def test_cancellation_is_checked_between_enumerated_entries(tmp_path: Path) -> None:
    for number in range(10):
        (tmp_path / f"{number}.txt").write_bytes(b"x")
    calls = 0

    def checkpoint() -> None:
        nonlocal calls
        calls += 1
        if calls == 4:
            raise Canceled

    with pytest.raises(Canceled):
        WalkingScanner().scan(Root(str(tmp_path), "source"), IgnoreSet(), _ctx(checkpoint))
    assert calls == 4


def _fake_stat(
    *,
    ino: int,
    directory: bool = False,
    attributes: int = 0,
    nlink: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        st_ino=ino,
        st_size=0 if directory else 5,
        st_mtime_ns=1_000,
        st_birthtime_ns=500,
        st_file_attributes=attributes,
        st_nlink=nlink,
    )


@dataclass
class FakeEntry:
    name: str
    path: str
    directory: bool
    observed: object
    file_probe: callable | None = None

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        assert not follow_symlinks
        return self.directory

    def is_file(self, *, follow_symlinks: bool = True) -> bool:
        assert not follow_symlinks
        if self.file_probe:
            self.file_probe()
        return not self.directory

    def stat(self, *, follow_symlinks: bool = True):
        assert not follow_symlinks
        if isinstance(self.observed, BaseException):
            raise self.observed
        return self.observed


class FakeBackend:
    def __init__(self, entries: dict[str, list[FakeEntry]], profile: CapabilityProfile) -> None:
        self.entries = entries
        self.profile = profile
        self.scandir_calls: list[str] = []

    def resolve_root(self, path: str) -> str:
        return path

    def volume_snapshot(self, root: str) -> VolumeSnapshot:
        return VolumeSnapshot(VolumeId("ABCD", self.profile.fs_type), VolumeEvidence(device_id="fake"), self.profile)

    def lstat(self, path: str):
        return _fake_stat(ino=1, directory=True)

    @contextmanager
    def scandir(self, path: str):
        self.scandir_calls.append(path)
        yield iter(self.entries.get(path, ()))


def _profile(fs_type: str = "NTFS", *, identity: bool = True, hardlinks: bool = True) -> CapabilityProfile:
    return CapabilityProfile(fs_type, 100 if fs_type == "NTFS" else 2_000_000_000, identity, None, 32767, False, hardlinks)


def test_placeholder_is_typed_without_file_probe_or_descent() -> None:
    probed = False

    def tripwire() -> None:
        nonlocal probed
        probed = True
        raise AssertionError("placeholder content/type probe")

    placeholder = FakeEntry(
        "cloud.bin",
        r"C:\root\cloud.bin",
        False,
        _fake_stat(ino=2, attributes=FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_OFFLINE),
        tripwire,
    )
    backend = FakeBackend({r"C:\root": [placeholder]}, _profile())
    result = WalkingScanner(backend).scan(Root(r"C:\root", "source"), IgnoreSet(), _ctx())
    assert not probed
    assert result.unsupported[0].reason is UnsupportedReason.PLACEHOLDER
    assert result.complete


def test_junction_identity_cycle_never_recurses_twice() -> None:
    cycle = FakeEntry("again", r"C:\root\again", True, _fake_stat(ino=1, directory=True))
    backend = FakeBackend({r"C:\root": [cycle]}, _profile())
    result = WalkingScanner(backend).scan(Root(r"C:\root", "source"), IgnoreSet(), _ctx())
    assert backend.scandir_calls == [r"C:\root"]
    assert not result.complete
    assert any(warning.code is ScanWarningCode.DUPLICATE_IDENTITY for warning in result.warnings)


def test_case_collision_and_hardlinks_are_warned_without_merging() -> None:
    entries = [
        FakeEntry("Foo.txt", r"C:\root\Foo.txt", False, _fake_stat(ino=2, nlink=2)),
        FakeEntry("foo.TXT", r"C:\root\foo.TXT", False, _fake_stat(ino=2, nlink=2)),
    ]
    result = WalkingScanner(FakeBackend({r"C:\root": entries}, _profile())).scan(
        Root(r"C:\root", "source"), IgnoreSet(), _ctx()
    )
    assert len(result.files) == 2
    assert not result.complete
    codes = {warning.code for warning in result.warnings}
    assert {ScanWarningCode.CASE_COLLISION, ScanWarningCode.DUPLICATE_IDENTITY, ScanWarningCode.MULTI_LINK} <= codes


def test_unrepresentable_names_are_typed_escaped_and_do_not_abort_safe_siblings() -> None:
    surrogate_name = "bad_" + chr(0xDCFF) + ".txt"
    hostile_directory = FakeEntry(
        "blocked.",
        r"C:\root\blocked.",
        True,
        _fake_stat(ino=4, directory=True),
    )
    entries = [
        FakeEntry("safe.txt", r"C:\root\safe.txt", False, _fake_stat(ino=2)),
        FakeEntry("trailingdot.", r"C:\root\trailingdot.", False, _fake_stat(ino=3)),
        FakeEntry(surrogate_name, "C:\\root\\" + surrogate_name, False, _fake_stat(ino=5)),
        hostile_directory,
    ]
    backend = FakeBackend(
        {
            r"C:\root": entries,
            r"C:\root\blocked.": [
                FakeEntry("hidden.txt", r"C:\root\blocked.\hidden.txt", False, _fake_stat(ino=6))
            ],
        },
        _profile(),
    )

    result = WalkingScanner(backend).scan(
        Root(r"C:\root", "source"), IgnoreSet(), _ctx()
    )

    assert [record.rel_path for record in result.files] == ["safe.txt"]
    assert backend.scandir_calls == [r"C:\root"]
    assert not result.complete
    path_warnings = [
        warning
        for warning in result.warnings
        if warning.code is ScanWarningCode.PATH_UNREPRESENTABLE
    ]
    assert len(path_warnings) == 3
    assert all(warning.rel_path is None for warning in path_warnings)
    details = "\n".join(warning.detail for warning in path_warnings)
    assert "trailingdot." in details
    assert "blocked." in details
    assert r"bad_\udcff.txt" in details


@pytest.mark.skipif(os.name != "nt", reason="requires the Windows extended path namespace")
def test_native_extended_path_trailing_dot_is_typed_not_fatal(tmp_path: Path) -> None:
    hostile_path = to_extended_length_path(str(tmp_path)) + r"\trailingdot."
    descriptor = os.open(
        hostile_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_BINARY,
        0o600,
    )
    os.close(descriptor)
    (tmp_path / "safe.txt").write_bytes(b"safe")

    try:
        result = WalkingScanner().scan(
            Root(str(tmp_path), "source"), IgnoreSet(), _ctx()
        )
    finally:
        os.unlink(hostile_path)

    assert [record.rel_path for record in result.files] == ["safe.txt"]
    assert not result.complete
    warning = next(
        item
        for item in result.warnings
        if item.code is ScanWarningCode.PATH_UNREPRESENTABLE
    )
    assert "trailingdot." in warning.detail


@pytest.mark.parametrize(
    ("profile", "expected_identity", "expected_hardlinks"),
    [
        (_profile("exFAT", identity=False, hardlinks=False), False, False),
        (_profile("NTFS", identity=True, hardlinks=False), True, False),
        (_profile("NTFS", identity=True, hardlinks=True), True, True),
    ],
)
def test_capabilities_follow_authoritative_profile(
    profile: CapabilityProfile, expected_identity: bool, expected_hardlinks: bool
) -> None:
    entry = FakeEntry("a.bin", r"C:\root\a.bin", False, _fake_stat(ino=2))
    result = WalkingScanner(FakeBackend({r"C:\root": [entry]}, profile)).scan(
        Root(r"C:\root", "source"), IgnoreSet(), _ctx()
    )
    assert (result.files[0].file_identity is not None) is expected_identity
    assert result.profile.supports_hardlinks is expected_hardlinks


def test_disappearing_entry_is_retained_as_warning_and_forces_incomplete() -> None:
    entry = FakeEntry("gone.bin", r"C:\root\gone.bin", False, FileNotFoundError("gone"))
    result = WalkingScanner(FakeBackend({r"C:\root": [entry]}, _profile())).scan(
        Root(r"C:\root", "source"), IgnoreSet(), _ctx()
    )
    assert not result.complete
    assert result.unsupported[0].reason is UnsupportedReason.DISAPPEARED
    assert result.warnings[0].code is ScanWarningCode.DISAPPEARED


def test_permission_denial_is_retained_and_forces_incomplete() -> None:
    entry = FakeEntry("private.bin", r"C:\root\private.bin", False, PermissionError("denied"))
    result = WalkingScanner(FakeBackend({r"C:\root": [entry]}, _profile())).scan(
        Root(r"C:\root", "source"), IgnoreSet(), _ctx()
    )
    assert not result.complete
    assert result.unsupported[0].reason is UnsupportedReason.ACCESS_DENIED
    assert result.warnings[0].code is ScanWarningCode.ACCESS_DENIED


def test_mid_enumeration_failure_keeps_already_reached_records() -> None:
    reached = FakeEntry("reached.bin", r"C:\root\reached.bin", False, _fake_stat(ino=2))

    class PartialBackend(FakeBackend):
        @contextmanager
        def scandir(self, path: str):
            def entries():
                yield reached
                raise PermissionError("enumeration denied")

            yield entries()

    result = WalkingScanner(PartialBackend({}, _profile())).scan(
        Root(r"C:\root", "source"), IgnoreSet(), _ctx()
    )
    assert [record.rel_path for record in result.files] == ["reached.bin"]
    assert not result.complete
    assert any(warning.code is ScanWarningCode.ENUMERATION_ERROR for warning in result.warnings)


def test_fake_long_path_walk_is_not_truncated() -> None:
    components = ["directory" * 10 for _ in range(4)]
    entries: dict[str, list[FakeEntry]] = {}
    absolute = r"C:\root"
    relative_parts: list[str] = []
    for index, component in enumerate(components, start=2):
        child_absolute = absolute + "\\" + component
        entries[absolute] = [FakeEntry(component, child_absolute, True, _fake_stat(ino=index, directory=True))]
        absolute = child_absolute
        relative_parts.append(component)
    file_absolute = absolute + r"\file.bin"
    entries[absolute] = [FakeEntry("file.bin", file_absolute, False, _fake_stat(ino=99))]
    result = WalkingScanner(FakeBackend(entries, _profile())).scan(
        Root(r"C:\root", "source"), IgnoreSet(), _ctx()
    )
    expected = "\\".join((*relative_parts, "file.bin"))
    assert len(expected) > 260
    assert [record.rel_path for record in result.files] == [expected]
    assert result.complete
