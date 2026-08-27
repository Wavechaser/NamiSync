"""M0 scanner acceptance and PoC regression tests."""

from __future__ import annotations

import builtins
import os
import stat as stat_module
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

import namisync.modules.scanner as scanner_module
from namisync.core.models import (
    CapabilityProfile,
    EntryKind,
    IgnoreSet,
    Root,
    ScanScope,
    ScanWarningCode,
    UnsupportedReason,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import PathValidationError, to_extended_length_path
from namisync.core.scalars import MAX_SIGNED_64
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


def test_scan_population_admission_precedes_first_excess_append(
    tmp_path: Path,
) -> None:
    (tmp_path / "subject.bin").write_bytes(b"x")

    class FirstExcess(RuntimeError):
        pass

    class Admission:
        def __init__(self) -> None:
            self.domain_counts: list[int] = []

        def require_source_rows(self, count: int) -> None:
            self.domain_counts.append(count)
            if count > 1:
                raise FirstExcess

        def require_informational_source_rows(self, count: int) -> None:
            raise AssertionError("clean scan admitted an informational row")

    admission = Admission()
    with pytest.raises(FirstExcess):
        WalkingScanner().scan(
            Root(str(tmp_path), "inventory"),
            IgnoreSet(),
            _ctx(),
            population_admission=admission,
        )

    assert admission.domain_counts == [1, 2]


def test_native_walk_recovers_identity_when_directory_entry_omits_it(
    tmp_path: Path,
) -> None:
    (tmp_path / "identity.bin").write_bytes(b"identity")

    result = WalkingScanner().scan(
        Root(str(tmp_path), "source"), IgnoreSet(), _ctx()
    )

    if result.profile.stable_file_identity:
        assert result.files[0].file_identity is not None


@pytest.mark.parametrize(
    ("field", "detail"),
    (
        ("st_size", "file size"),
        ("st_mtime_ns", "file modification time"),
        ("st_birthtime_ns", "creation time"),
    ),
)
def test_path_local_unrepresentable_scalars_become_typed_scan_warnings(
    field: str,
    detail: str,
) -> None:
    values = {
        "st_size": 1,
        "st_mtime_ns": 2,
        "st_birthtime_ns": 3,
        "st_ino": (1 << 64) + 9,
        "st_nlink": 1,
        "st_file_attributes": 0,
    }
    values[field] = MAX_SIGNED_64 + 1
    volume = VolumeSnapshot(
        VolumeId("A1B2C3D4", "NTFS"),
        VolumeEvidence(device_id="fixture"),
        CapabilityProfile("NTFS", 100, True, False, 32_767, True, True),
    )
    warnings = []

    observed = scanner_module._to_stat_or_warning(
        SimpleNamespace(**values),
        EntryKind.FILE,
        volume,
        warnings,
        r"folder\subject.bin",
    )

    assert observed is None
    assert len(warnings) == 1
    assert warnings[0].code is ScanWarningCode.SCALAR_UNREPRESENTABLE
    assert warnings[0].rel_path == r"folder\subject.bin"
    assert detail in (warnings[0].detail or "")


def test_scanner_never_opens_file_content_and_built_in_ignores_preserve_user_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for relative in (
        "customer.db",
        "my.synctmp-notes.txt",
        "customer.sha256",
        "desktop.ini",
        "THUMBS.DB",
        "asset.bin.synctmp-" + "a" * 32 + "-" + "b" * 32,
    ):
        path = tmp_path.joinpath(*relative.split("\\"))
        path.write_bytes(b"content")
    trash = tmp_path / ".synctrash"
    trash.mkdir()
    (trash / "hidden.txt").write_bytes(b"hidden")

    monkeypatch.setattr(builtins, "open", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("content opened")))
    result = WalkingScanner().scan(Root(str(tmp_path), "source"), IgnoreSet(), _ctx())

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
        st_mode=(
            stat_module.S_IFDIR | 0o755
            if directory
            else stat_module.S_IFREG | 0o644
        ),
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


def test_scanner_revalidates_forged_volume_snapshot_before_enumeration() -> None:
    backend = FakeBackend({}, _profile())
    snapshot = backend.volume_snapshot(r"C:\root")
    object.__setattr__(snapshot.profile, "fs_type", "f" * 261)
    backend.volume_snapshot = lambda _root: snapshot  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="UTF-16 text bound"):
        WalkingScanner(backend).scan(
            Root(r"C:\root", "source"),
            IgnoreSet(),
            _ctx(),
        )

    assert backend.scandir_calls == []


class ScopedAdmissionBackend(FakeBackend):
    def __init__(
        self,
        stats: dict[str, object],
        entries: dict[str, list[FakeEntry]] | None = None,
        *,
        root: str = r"C:\root",
    ) -> None:
        super().__init__(entries or {}, _profile())
        self.root = root
        self.stats = stats
        self.lstat_calls: list[str] = []

    def lstat(self, path: str):
        self.lstat_calls.append(path)
        if path == self.root:
            return _fake_stat(ino=1, directory=True)
        if path not in self.stats:
            raise AssertionError(f"unexpected scoped lstat: {path}")
        observed = self.stats[path]
        if isinstance(observed, BaseException):
            raise observed
        return observed


class TrustedMountBackend(FakeBackend):
    def __init__(
        self,
        entries: dict[str, list[FakeEntry]],
        *,
        root: str,
        device_anchor: str,
        root_lstat: object,
        followed_root_stat: object,
        path_lstats: dict[str, object] | None = None,
    ) -> None:
        super().__init__(entries, _profile())
        self.root = root
        self.device_anchor = device_anchor
        self.root_lstat = root_lstat
        self.followed_root_stat = followed_root_stat
        self.path_lstats = path_lstats or {}
        self.lstat_calls: list[str] = []
        self.followed_stat_calls: list[str] = []

    def resolve_root(
        self,
        path: str,
        *,
        trusted_anchor: str | None = None,
    ) -> str:
        assert path == self.root
        assert trusted_anchor in {None, self.root}
        return path

    def trusted_anchor(self, path: str) -> str:
        assert path == self.root
        return self.root

    def volume_snapshot(self, root: str) -> VolumeSnapshot:
        assert root == self.root
        return VolumeSnapshot(
            VolumeId("ABCD", self.profile.fs_type),
            VolumeEvidence(device_id=self.device_anchor),
            self.profile,
        )

    def lstat(self, path: str):
        self.lstat_calls.append(path)
        if path == self.root:
            return self.root_lstat
        assert path in self.path_lstats
        observed = self.path_lstats[path]
        if isinstance(observed, BaseException):
            raise observed
        return observed

    def stat(self, path: str):
        assert path == self.root
        self.followed_stat_calls.append(path)
        if isinstance(self.followed_root_stat, BaseException):
            raise self.followed_root_stat
        return self.followed_root_stat


_SCOPED_ROOT = r"C:\root"


def _nested_scope(scope_kind: str, relative_path: str) -> ScanScope:
    if scope_kind == "paths":
        return ScanScope.selected((relative_path,))
    return ScanScope.subtrees((relative_path,))


def _scan_nested(
    backend: FakeBackend,
    scope_kind: str,
    relative_path: str,
    *,
    root: str = _SCOPED_ROOT,
    trusted_anchor: str | None = None,
):
    return WalkingScanner(backend).scan(
        Root(root, "source"),
        IgnoreSet(),
        _ctx(),
        _nested_scope(scope_kind, relative_path),
        trusted_anchor=trusted_anchor,
    )


@pytest.mark.parametrize("scope_kind", ("paths", "subtrees"))
@pytest.mark.parametrize(
    ("blocked_stat", "warning_code", "unsupported_reason"),
    (
        (
            _fake_stat(
                ino=3,
                directory=True,
                attributes=FILE_ATTRIBUTE_REPARSE_POINT,
            ),
            ScanWarningCode.REPARSE_POINT,
            UnsupportedReason.REPARSE_POINT,
        ),
        (
            _fake_stat(
                ino=3,
                directory=True,
                attributes=(
                    FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_OFFLINE
                ),
            ),
            ScanWarningCode.PLACEHOLDER,
            UnsupportedReason.PLACEHOLDER,
        ),
        (
            _fake_stat(ino=3),
            ScanWarningCode.UNKNOWN_TYPE,
            UnsupportedReason.UNKNOWN_TYPE,
        ),
        (
            PermissionError("denied ancestor"),
            ScanWarningCode.ACCESS_DENIED,
            UnsupportedReason.ACCESS_DENIED,
        ),
        (
            OSError("unavailable ancestor"),
            ScanWarningCode.ENUMERATION_ERROR,
            UnsupportedReason.UNKNOWN_TYPE,
        ),
    ),
    ids=("reparse", "placeholder", "file", "denied", "unavailable"),
)
def test_scoped_scan_stops_at_an_unsafe_intermediate_component(
    scope_kind: str,
    blocked_stat: object,
    warning_code: ScanWarningCode,
    unsupported_reason: UnsupportedReason,
) -> None:
    root = _SCOPED_ROOT
    safe = root + r"\safe"
    blocked = safe + r"\blocked"
    relative = (
        r"safe\blocked\leaf.bin"
        if scope_kind == "paths"
        else r"safe\blocked\start"
    )
    backend = ScopedAdmissionBackend(
        {
            safe: _fake_stat(ino=2, directory=True),
            blocked: blocked_stat,
        }
    )

    result = _scan_nested(backend, scope_kind, relative)

    assert not result.complete
    assert result.files == ()
    assert result.directories == ()
    assert [(item.rel_path, item.reason) for item in result.unsupported] == [
        (relative, unsupported_reason)
    ]
    assert any(
        warning.code is warning_code and warning.rel_path == relative
        for warning in result.warnings
    )
    assert [path for path in backend.lstat_calls if path != root] == [
        safe,
        blocked,
    ]
    assert backend.scandir_calls == []


@pytest.mark.parametrize("scope_kind", ("paths", "subtrees"))
def test_scoped_scan_treats_a_missing_intermediate_as_complete_absence(
    scope_kind: str,
) -> None:
    root = _SCOPED_ROOT
    safe = root + r"\safe"
    missing = safe + r"\missing"
    relative = (
        r"safe\missing\leaf.bin"
        if scope_kind == "paths"
        else r"safe\missing\start"
    )
    backend = ScopedAdmissionBackend(
        {
            safe: _fake_stat(ino=2, directory=True),
            missing: FileNotFoundError("missing ancestor"),
        }
    )

    result = _scan_nested(backend, scope_kind, relative)

    assert result.complete, result.warnings
    assert result.files == ()
    assert result.directories == ()
    assert result.unsupported == ()
    assert any(
        warning.code is ScanWarningCode.DISAPPEARED
        and warning.rel_path == relative
        for warning in result.warnings
    )
    assert [path for path in backend.lstat_calls if path != root] == [
        safe,
        missing,
    ]
    assert backend.scandir_calls == []


@pytest.mark.parametrize("scope_kind", ("paths", "subtrees"))
def test_scoped_scan_preserves_final_classification_after_safe_ancestors(
    scope_kind: str,
) -> None:
    root = _SCOPED_ROOT
    safe = root + r"\safe"
    relative = r"safe\leaf.bin" if scope_kind == "paths" else r"safe\start"
    final = root + "\\" + relative
    entries: dict[str, list[FakeEntry]] = {}
    if scope_kind == "paths":
        final_stat = _fake_stat(ino=3)
        expected_file = relative
        expected_directory: str | None = None
    else:
        final_stat = _fake_stat(ino=3, directory=True)
        child = final + r"\child.bin"
        entries[final] = [
            FakeEntry("child.bin", child, False, _fake_stat(ino=4))
        ]
        expected_file = relative + r"\child.bin"
        expected_directory = relative
    backend = ScopedAdmissionBackend(
        {
            safe: _fake_stat(ino=2, directory=True),
            final: final_stat,
        },
        entries,
    )

    result = _scan_nested(backend, scope_kind, relative)

    assert result.complete, result.warnings
    assert [record.rel_path for record in result.files] == [expected_file]
    assert [record.rel_path for record in result.directories] == (
        [] if expected_directory is None else [expected_directory]
    )
    assert [path for path in backend.lstat_calls if path != root] == [
        safe,
        final,
    ]
    assert backend.scandir_calls == (
        [] if scope_kind == "paths" else [final]
    )


def test_selected_scan_checks_cancellation_before_touching_the_final_leaf() -> None:
    root = _SCOPED_ROOT
    ancestor = root + r"\safe"
    relative = r"safe\leaf.bin"
    final = root + "\\" + relative
    backend = ScopedAdmissionBackend(
        {
            ancestor: _fake_stat(ino=2, directory=True),
            final: _fake_stat(ino=3),
        }
    )
    cancellation_requested = False
    original_lstat = backend.lstat

    def request_cancellation_during_ancestor_lstat(path: str):
        nonlocal cancellation_requested
        observed = original_lstat(path)
        if path == ancestor:
            cancellation_requested = True
        return observed

    def checkpoint() -> None:
        if cancellation_requested:
            raise Canceled

    backend.lstat = request_cancellation_during_ancestor_lstat

    with pytest.raises(Canceled):
        WalkingScanner(backend).scan(
            Root(root, "source"),
            IgnoreSet(),
            _ctx(checkpoint),
            ScanScope.selected((relative,)),
        )

    assert [path for path in backend.lstat_calls if path != root] == [
        ancestor
    ]
    assert final not in backend.lstat_calls


@pytest.mark.parametrize(
    ("scope_kind", "expected_complete", "expected_kind"),
    (
        ("paths", True, None),
        ("subtrees", False, EntryKind.DIRECTORY),
    ),
)
def test_ancestor_admission_leaves_final_reparse_policy_unchanged(
    scope_kind: str,
    expected_complete: bool,
    expected_kind: EntryKind | None,
) -> None:
    safe = _SCOPED_ROOT + r"\safe"
    relative = r"safe\final-junction"
    final = _SCOPED_ROOT + "\\" + relative
    backend = ScopedAdmissionBackend(
        {
            safe: _fake_stat(ino=2, directory=True),
            final: _fake_stat(
                ino=3,
                directory=True,
                attributes=FILE_ATTRIBUTE_REPARSE_POINT,
            ),
        }
    )

    result = _scan_nested(backend, scope_kind, relative)

    assert result.complete is expected_complete
    assert len(result.unsupported) == 1
    assert result.unsupported[0].reason is UnsupportedReason.REPARSE_POINT
    assert result.unsupported[0].kind is expected_kind
    assert [path for path in backend.lstat_calls if path != _SCOPED_ROOT] == [
        safe,
        final,
    ]
    assert backend.scandir_calls == []


def test_unsafe_subtree_start_does_not_prevent_a_safe_sibling_scan() -> None:
    root = _SCOPED_ROOT
    blocked = root + r"\blocked"
    refused = blocked + r"\start"
    safe = root + r"\safe"
    child = safe + r"\child.bin"
    backend = ScopedAdmissionBackend(
        {
            blocked: _fake_stat(
                ino=2,
                directory=True,
                attributes=FILE_ATTRIBUTE_REPARSE_POINT,
            ),
            safe: _fake_stat(ino=3, directory=True),
        },
        {safe: [FakeEntry("child.bin", child, False, _fake_stat(ino=4))]},
    )

    result = WalkingScanner(backend).scan(
        Root(root, "source"),
        IgnoreSet(),
        _ctx(),
        ScanScope.subtrees((r"blocked\start", "safe")),
    )

    assert not result.complete
    assert [record.rel_path for record in result.files] == [r"safe\child.bin"]
    assert [record.rel_path for record in result.directories] == ["safe"]
    assert result.unsupported[0].rel_path == r"blocked\start"
    assert refused not in backend.lstat_calls
    assert backend.scandir_calls == [safe]


@pytest.mark.skipif(os.name != "nt", reason="requires Windows folder mounts")
@pytest.mark.parametrize(
    "explicit_anchor",
    (True, False),
    ids=("inventory-reviewed", "native-derived"),
)
def test_full_scan_admits_exact_trusted_folder_mount_root(
    explicit_anchor: bool,
) -> None:
    root = r"C:\mounted-volume"
    entry = FakeEntry(
        "inside.bin",
        root + r"\inside.bin",
        False,
        _fake_stat(ino=8),
    )
    backend = TrustedMountBackend(
        {root: [entry]},
        root=root,
        device_anchor=root if explicit_anchor else root + "\\",
        root_lstat=_fake_stat(
            ino=91,
            directory=True,
            attributes=FILE_ATTRIBUTE_REPARSE_POINT,
        ),
        followed_root_stat=_fake_stat(ino=7, directory=True),
    )

    result = WalkingScanner(backend).scan(
        Root(root, "source"),
        IgnoreSet(),
        _ctx(),
        trusted_anchor=root if explicit_anchor else None,
    )

    assert result.complete, result.warnings
    assert [record.rel_path for record in result.files] == ["inside.bin"]
    assert [record.rel_path for record in result.directories] == [""]
    assert result.directories[0].file_identity is not None
    assert result.directories[0].file_identity.file_index == 7
    assert result.directories[0].metadata.attributes == 0
    assert backend.followed_stat_calls == [root]
    assert backend.scandir_calls == [root]


@pytest.mark.skipif(os.name != "nt", reason="requires Windows folder mounts")
@pytest.mark.parametrize("scope_kind", ("paths", "subtrees"))
def test_scoped_scan_at_a_trusted_mount_does_not_follow_the_root(
    scope_kind: str,
) -> None:
    root = r"C:\mounted-volume"
    folder = root + r"\folder"
    if scope_kind == "paths":
        absolute = root + r"\inside.bin"
        scope = ScanScope.selected(("inside.bin",))
        entries: dict[str, list[FakeEntry]] = {}
        path_lstats = {absolute: _fake_stat(ino=8)}
        expected_files = ["inside.bin"]
        expected_directories: list[str] = []
        expected_scans: list[str] = []
    else:
        absolute = folder
        scope = ScanScope.subtrees(("folder",))
        entries = {
            folder: [
                FakeEntry(
                    "inside.bin",
                    folder + r"\inside.bin",
                    False,
                    _fake_stat(ino=8),
                )
            ]
        }
        path_lstats = {folder: _fake_stat(ino=9, directory=True)}
        expected_files = [r"folder\inside.bin"]
        expected_directories = ["folder"]
        expected_scans = [folder]
    backend = TrustedMountBackend(
        entries,
        root=root,
        device_anchor=root,
        root_lstat=_fake_stat(
            ino=91,
            directory=True,
            attributes=FILE_ATTRIBUTE_REPARSE_POINT,
        ),
        followed_root_stat=AssertionError("scoped scan followed mount root"),
        path_lstats=path_lstats,
    )

    result = WalkingScanner(backend).scan(
        Root(root, "source"),
        IgnoreSet(),
        _ctx(),
        scope,
        trusted_anchor=root,
    )

    assert result.complete, result.warnings
    assert [record.rel_path for record in result.files] == expected_files
    assert [record.rel_path for record in result.directories] == expected_directories
    assert backend.lstat_calls == [absolute]
    assert backend.followed_stat_calls == []
    assert backend.scandir_calls == expected_scans


@pytest.mark.skipif(os.name != "nt", reason="requires Windows folder mounts")
@pytest.mark.parametrize("scope_kind", ("paths", "subtrees"))
def test_scoped_descendant_cannot_inherit_the_trusted_mount_exception(
    scope_kind: str,
) -> None:
    root = r"C:\mounted-volume"
    safe = root + r"\safe"
    blocked = safe + r"\junction"
    relative = (
        r"safe\junction\leaf.bin"
        if scope_kind == "paths"
        else r"safe\junction\start"
    )
    backend = TrustedMountBackend(
        {},
        root=root,
        device_anchor=root,
        root_lstat=_fake_stat(
            ino=91,
            directory=True,
            attributes=FILE_ATTRIBUTE_REPARSE_POINT,
        ),
        followed_root_stat=AssertionError("scoped scan followed mount root"),
        path_lstats={
            safe: _fake_stat(ino=2, directory=True),
            blocked: _fake_stat(
                ino=3,
                directory=True,
                attributes=FILE_ATTRIBUTE_REPARSE_POINT,
            ),
        },
    )

    result = _scan_nested(
        backend,
        scope_kind,
        relative,
        root=root,
        trusted_anchor=root,
    )

    assert not result.complete
    assert result.unsupported[0].rel_path == relative
    assert result.unsupported[0].reason is UnsupportedReason.REPARSE_POINT
    assert backend.lstat_calls == [safe, blocked]
    assert backend.followed_stat_calls == []
    assert backend.scandir_calls == []


def test_full_scan_does_not_trust_a_claimed_anchor_without_volume_evidence() -> None:
    root = r"C:\claimed-anchor"
    backend = TrustedMountBackend(
        {},
        root=root,
        device_anchor=r"C:\actual-volume",
        root_lstat=_fake_stat(
            ino=91,
            directory=True,
            attributes=FILE_ATTRIBUTE_REPARSE_POINT,
        ),
        followed_root_stat=_fake_stat(ino=7, directory=True),
    )

    result = WalkingScanner(backend).scan(
        Root(root, "source"),
        IgnoreSet(),
        _ctx(),
        trusted_anchor=root,
    )

    assert not result.complete
    assert result.warnings[0].code is ScanWarningCode.ROOT_UNAVAILABLE
    assert backend.followed_stat_calls == []
    assert backend.scandir_calls == []


def test_full_scan_never_follows_a_placeholder_mount_anchor() -> None:
    root = r"C:\placeholder-anchor"
    backend = TrustedMountBackend(
        {},
        root=root,
        device_anchor=root,
        root_lstat=_fake_stat(
            ino=91,
            directory=True,
            attributes=(
                FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_OFFLINE
            ),
        ),
        followed_root_stat=AssertionError("placeholder root was followed"),
    )

    result = WalkingScanner(backend).scan(
        Root(root, "source"),
        IgnoreSet(),
        _ctx(),
        trusted_anchor=root,
    )

    assert not result.complete
    assert result.warnings[0].code is ScanWarningCode.ROOT_UNAVAILABLE
    assert backend.followed_stat_calls == []
    assert backend.scandir_calls == []


@pytest.mark.parametrize(
    "followed_root_stat",
    (
        _fake_stat(ino=7),
        _fake_stat(
            ino=7,
            directory=True,
            attributes=FILE_ATTRIBUTE_REPARSE_POINT,
        ),
        PermissionError("mounted root metadata unavailable"),
    ),
    ids=("file", "reparse", "unavailable"),
)
@pytest.mark.skipif(os.name != "nt", reason="requires Windows folder mounts")
def test_full_scan_requires_an_ordinary_followed_mount_root(
    followed_root_stat: object,
) -> None:
    root = r"C:\mounted-volume"
    backend = TrustedMountBackend(
        {},
        root=root,
        device_anchor=root,
        root_lstat=_fake_stat(
            ino=91,
            directory=True,
            attributes=FILE_ATTRIBUTE_REPARSE_POINT,
        ),
        followed_root_stat=followed_root_stat,
    )

    result = WalkingScanner(backend).scan(
        Root(root, "source"),
        IgnoreSet(),
        _ctx(),
        trusted_anchor=root,
    )

    assert not result.complete
    assert result.warnings[0].code is ScanWarningCode.ROOT_UNAVAILABLE
    assert backend.followed_stat_calls == [root]
    assert backend.scandir_calls == []


@pytest.mark.skipif(os.name != "nt", reason="requires Windows folder mounts")
def test_reparse_child_below_a_trusted_mount_root_is_not_followed() -> None:
    root = r"C:\mounted-volume"
    child = root + r"\junction"
    entry = FakeEntry(
        "junction",
        child,
        True,
        _fake_stat(
            ino=8,
            directory=True,
            attributes=FILE_ATTRIBUTE_REPARSE_POINT,
        ),
    )
    backend = TrustedMountBackend(
        {root: [entry]},
        root=root,
        device_anchor=root,
        root_lstat=_fake_stat(
            ino=91,
            directory=True,
            attributes=FILE_ATTRIBUTE_REPARSE_POINT,
        ),
        followed_root_stat=_fake_stat(ino=7, directory=True),
    )

    result = WalkingScanner(backend).scan(
        Root(root, "source"),
        IgnoreSet(),
        _ctx(),
        trusted_anchor=root,
    )

    assert not result.complete
    assert [record.rel_path for record in result.directories] == [""]
    assert result.unsupported[0].reason is UnsupportedReason.REPARSE_POINT
    assert backend.followed_stat_calls == [root]
    assert backend.scandir_calls == [root]


@pytest.mark.parametrize(
    "root_stat",
    [
        _fake_stat(ino=1),
        _fake_stat(
            ino=1,
            directory=True,
            attributes=(
                FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_OFFLINE
            ),
        ),
        _fake_stat(
            ino=1,
            directory=True,
            attributes=FILE_ATTRIBUTE_REPARSE_POINT,
        ),
    ],
)
@pytest.mark.parametrize(
    "scope",
    [
        ScanScope.full(),
        ScanScope.selected(("file.bin",)),
        ScanScope.subtrees(("folder",)),
    ],
)
def test_every_scan_scope_refuses_nonordinary_location_root(
    root_stat,
    scope: ScanScope,
) -> None:
    backend = FakeBackend({}, _profile())
    backend.lstat = lambda _path: root_stat

    result = WalkingScanner(backend).scan(
        Root(r"C:\root", "source"),
        IgnoreSet(),
        _ctx(),
        scope,
    )

    assert not result.complete
    assert result.files == ()
    assert result.directories == ()
    assert result.unsupported == ()
    assert backend.scandir_calls == []
    assert result.warnings[0].code is ScanWarningCode.ROOT_UNAVAILABLE
    assert result.warnings[0].rel_path is None


@pytest.mark.parametrize(
    "scope",
    [
        ScanScope.full(),
        ScanScope.selected(("file.bin",)),
        ScanScope.subtrees(("folder",)),
    ],
)
def test_every_scan_scope_rechecks_root_after_volume_observation(
    scope: ScanScope,
) -> None:
    backend = FakeBackend({}, _profile())
    observations = iter(
        (
            _fake_stat(ino=1, directory=True),
            _fake_stat(
                ino=2,
                directory=True,
                attributes=FILE_ATTRIBUTE_REPARSE_POINT,
            ),
        )
    )
    backend.lstat = lambda _path: next(observations)

    result = WalkingScanner(backend).scan(
        Root(r"C:\root", "source"),
        IgnoreSet(),
        _ctx(),
        scope,
    )

    assert not result.complete
    assert result.files == ()
    assert result.directories == ()
    assert backend.scandir_calls == []
    assert result.warnings[0].code is ScanWarningCode.ROOT_UNAVAILABLE


def test_scanner_refuses_volume_swap_immediately_after_snapshot() -> None:
    backend = FakeBackend({}, _profile())
    reviewed = backend.volume_snapshot(r"C:\root")
    foreign = VolumeSnapshot(
        VolumeId("DEADBEEF", reviewed.profile.fs_type),
        VolumeEvidence(device_id="foreign"),
        reviewed.profile,
    )
    snapshots = iter((reviewed, foreign))
    backend.volume_snapshot = lambda _root: next(snapshots)

    result = WalkingScanner(backend).scan(
        Root(r"C:\root", "source"),
        IgnoreSet(),
        _ctx(),
    )

    assert not result.complete
    assert result.volume_id is None
    assert result.files == ()
    assert result.directories == ()
    assert backend.scandir_calls == []
    assert result.warnings[0].code is ScanWarningCode.VOLUME_UNAVAILABLE


def test_scanner_discards_observations_if_volume_swaps_during_enumeration() -> None:
    entry = FakeEntry(
        "foreign.bin",
        r"C:\root\foreign.bin",
        False,
        _fake_stat(ino=2),
    )
    backend = FakeBackend({r"C:\root": [entry]}, _profile())
    reviewed = backend.volume_snapshot(r"C:\root")
    foreign = VolumeSnapshot(
        VolumeId("DEADBEEF", reviewed.profile.fs_type),
        VolumeEvidence(device_id="foreign"),
        reviewed.profile,
    )
    state = {"swapped": False}
    backend.volume_snapshot = (
        lambda _root: foreign if state["swapped"] else reviewed
    )

    @contextmanager
    def swap_during_scandir(path: str):
        backend.scandir_calls.append(path)
        state["swapped"] = True
        yield iter(backend.entries.get(path, ()))

    backend.scandir = swap_during_scandir

    result = WalkingScanner(backend).scan(
        Root(r"C:\root", "source"),
        IgnoreSet(),
        _ctx(),
    )

    assert not result.complete
    assert result.volume_id is None
    assert result.files == ()
    assert result.directories == ()
    assert backend.scandir_calls == [r"C:\root"]
    assert result.warnings[0].code is ScanWarningCode.VOLUME_UNAVAILABLE


def test_scanner_discards_observations_if_root_chain_swaps_after_enumeration() -> None:
    root = r"C:\root"
    entry = FakeEntry(
        "observed.bin",
        root + r"\observed.bin",
        False,
        _fake_stat(ino=2, nlink=2),
    )
    backend = FakeBackend({root: [entry]}, _profile())
    state = {"swapped": False}
    volume_calls: list[str] = []
    original_volume_snapshot = backend.volume_snapshot

    backend.lstat = lambda _path: _fake_stat(
        ino=1,
        directory=True,
        attributes=(
            FILE_ATTRIBUTE_REPARSE_POINT if state["swapped"] else 0
        ),
    )

    def volume_snapshot(path: str) -> VolumeSnapshot:
        volume_calls.append(path)
        return original_volume_snapshot(path)

    @contextmanager
    def swap_during_scandir(path: str):
        backend.scandir_calls.append(path)
        state["swapped"] = True
        yield iter(backend.entries.get(path, ()))

    backend.volume_snapshot = volume_snapshot
    backend.scandir = swap_during_scandir

    result = WalkingScanner(backend).scan(
        Root(root, "source"),
        IgnoreSet(),
        _ctx(),
    )

    assert not result.complete
    assert result.volume_id is None
    assert result.files == ()
    assert result.directories == ()
    assert result.unsupported == ()
    assert [warning.code for warning in result.warnings] == [
        ScanWarningCode.ROOT_UNAVAILABLE
    ]
    assert backend.scandir_calls == [root]
    assert volume_calls == [root, root]


@pytest.mark.parametrize(
    "scope",
    [
        ScanScope.full(),
        ScanScope.selected(("file.bin",)),
        ScanScope.subtrees(("folder",)),
    ],
)
def test_every_scan_scope_stops_at_an_intermediate_root_reparse(
    scope: ScanScope,
) -> None:
    backend = FakeBackend({}, _profile())

    def root_chain_stat(path: str):
        if path == r"C:\parent":
            return _fake_stat(
                ino=2,
                directory=True,
                attributes=FILE_ATTRIBUTE_REPARSE_POINT,
            )
        raise AssertionError("scanner probed through an intermediate reparse")

    backend.lstat = root_chain_stat

    result = WalkingScanner(backend).scan(
        Root(r"C:\parent\root", "source"),
        IgnoreSet(),
        _ctx(),
        scope,
    )

    assert not result.complete
    assert result.files == ()
    assert result.directories == ()
    assert backend.scandir_calls == []
    assert result.warnings[0].code is ScanWarningCode.ROOT_UNAVAILABLE


@pytest.mark.skipif(os.name != "nt", reason="requires Windows reparse points")
@pytest.mark.parametrize(
    "scope",
    [
        ScanScope.full(),
        ScanScope.selected(("redirected.bin",)),
        ScanScope.subtrees(("folder",)),
    ],
)
def test_native_scanner_refuses_a_final_root_reparse_before_every_scope(
    tmp_path: Path,
    scope: ScanScope,
) -> None:
    redirected = tmp_path / "redirected"
    redirected.mkdir()
    (redirected / "redirected.bin").write_bytes(b"outside reviewed root")
    (redirected / "folder").mkdir()
    root = tmp_path / "configured-root"
    environment = os.environ.copy()
    environment["NAMISYNC_TEST_LINK"] = str(root)
    environment["NAMISYNC_TEST_TARGET"] = str(redirected)
    completed = subprocess.run(
        (
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "New-Item -ItemType Junction -Path $env:NAMISYNC_TEST_LINK "
            "-Target $env:NAMISYNC_TEST_TARGET -ErrorAction Stop | Out-Null",
        ),
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    if completed.returncode:
        pytest.skip(
            "directory junction creation is unavailable: "
            f"{completed.stderr.strip()}"
        )

    try:
        result = WalkingScanner().scan(
            Root(str(root), "source"),
            IgnoreSet(),
            _ctx(),
            scope,
        )
    finally:
        root.rmdir()

    assert not result.complete
    assert result.root.path == str(root)
    assert result.files == ()
    assert result.directories == ()
    assert result.warnings[0].code is ScanWarningCode.ROOT_UNAVAILABLE


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


@pytest.mark.skipif(os.name != "nt", reason="requires the Windows extended path namespace")
def test_ambiguous_extended_root_is_refused_before_scanning_sibling(
    tmp_path: Path,
) -> None:
    ordinary = tmp_path / "root"
    ordinary.mkdir()
    (ordinary / "ordinary.txt").write_bytes(b"ordinary")
    ambiguous = to_extended_length_path(str(tmp_path)) + r"\root."
    os.mkdir(ambiguous)
    try:
        assert os.path.isdir(ambiguous)
        with pytest.raises(PathValidationError):
            WalkingScanner().scan(
                Root(ambiguous, "source"), IgnoreSet(), _ctx()
            )
        assert (ordinary / "ordinary.txt").read_bytes() == b"ordinary"
    finally:
        os.rmdir(ambiguous)


@pytest.mark.skipif(os.name != "nt", reason="requires Windows native errors")
def test_deep_selected_path_failure_warning_uses_logical_spelling(
    tmp_path: Path,
) -> None:
    root_path = tmp_path / ("a" * 90) / ("b" * 90) / ("c" * 90)
    assert len(str(root_path)) > 260
    os.makedirs(to_extended_length_path(str(root_path)))

    result = WalkingScanner().scan(
        Root(str(root_path), "source"),
        IgnoreSet(),
        _ctx(),
        ScanScope.selected(("missing.bin",)),
    )

    warning = next(
        item
        for item in result.warnings
        if item.code is ScanWarningCode.DISAPPEARED
    )
    assert "missing.bin" in warning.detail
    assert "\\\\?\\" not in warning.detail


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length paths")
def test_native_root_resolution_error_is_sanitized_for_direct_callers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logical = r"C:\deep\root"
    native = to_extended_length_path(r"C:\deep")
    def denied_stat(path: str, *, follow_symlinks: bool):
        assert path == native
        assert not follow_symlinks
        raise PermissionError(13, "denied", native)

    monkeypatch.setattr(scanner_module.os, "stat", denied_stat)
    with pytest.raises(OSError) as captured:
        scanner_module.NativeScannerBackend().resolve_root(logical)

    assert "deep" in str(captured.value)
    assert "\\\\?\\" not in str(captured.value)


def test_native_root_resolution_revalidates_an_empty_chain_mount_anchor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = tmp_path / "mounted-root"
    configured.mkdir()
    backend = scanner_module.NativeScannerBackend()
    monkeypatch.setattr(
        backend,
        "trusted_anchor",
        lambda _path: str(tmp_path),
    )
    monkeypatch.setattr(
        scanner_module.os,
        "stat",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("mismatched reviewed anchor must stop component probes")
        ),
    )

    with pytest.raises(OSError, match="volume anchor changed"):
        backend.resolve_root(
            str(configured),
            trusted_anchor=str(configured),
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows volume anchors")
def test_native_root_resolution_maps_an_outside_reviewed_anchor_to_legacy_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = scanner_module.NativeScannerBackend()
    monkeypatch.setattr(
        backend,
        "trusted_anchor",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("invalid reviewed anchor reached native probing")
        ),
    )

    with pytest.raises(
        OSError,
        match="location volume anchor changed after binding review",
    ) as raised:
        backend.resolve_root(r"C:\managed", trusted_anchor="D:\\")

    assert not isinstance(raised.value, PathValidationError)


@pytest.mark.skipif(os.name != "nt", reason="Windows volume anchors")
def test_scanner_reports_an_outside_reviewed_anchor_as_root_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = scanner_module.NativeScannerBackend()
    monkeypatch.setattr(
        backend,
        "trusted_anchor",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("invalid reviewed anchor reached native probing")
        ),
    )
    monkeypatch.setattr(
        backend,
        "volume_snapshot",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("invalid reviewed anchor reached volume probing")
        ),
    )

    result = WalkingScanner(backend).scan(
        Root(r"C:\managed", "source"),
        IgnoreSet(),
        _ctx(),
        trusted_anchor="D:\\",
    )

    assert not result.complete
    assert result.volume_id is None
    assert result.warnings[0].code is ScanWarningCode.ROOT_UNAVAILABLE
    assert (
        result.warnings[0].detail
        == "location volume anchor changed after binding review"
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows root admission order")
@pytest.mark.parametrize("explicit_anchor", (True, False))
def test_native_scan_preserves_root_authority_probe_order(
    explicit_anchor: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = r"C:\root"
    anchor = "C:\\"
    calls: list[tuple[str, str]] = []
    backend = scanner_module.NativeScannerBackend()

    def trusted_anchor(path: str) -> str:
        calls.append(("anchor", path))
        return anchor

    def lstat(path: str):
        calls.append(("lstat", path))
        return _fake_stat(ino=1, directory=True)

    def volume_snapshot(path: str) -> VolumeSnapshot:
        calls.append(("volume", path))
        return VolumeSnapshot(
            VolumeId("ABCD", "NTFS"),
            VolumeEvidence(device_id=anchor),
            _profile(),
        )

    @contextmanager
    def scandir(path: str):
        calls.append(("scandir", path))
        yield iter(())

    monkeypatch.setattr(backend, "trusted_anchor", trusted_anchor)
    monkeypatch.setattr(backend, "lstat", lstat)
    monkeypatch.setattr(backend, "volume_snapshot", volume_snapshot)
    monkeypatch.setattr(backend, "scandir", scandir)

    result = WalkingScanner(backend).scan(
        Root(root, "source"),
        IgnoreSet(),
        _ctx(),
        trusted_anchor=anchor if explicit_anchor else None,
    )

    expected_calls = [
        ("anchor", root),
        ("lstat", root),
        ("lstat", root),
        ("volume", root),
        ("lstat", root),
        ("anchor", root),
        ("volume", root),
        ("lstat", root),
        ("scandir", root),
        ("lstat", root),
        ("anchor", root),
        ("volume", root),
    ]
    if not explicit_anchor:
        expected_calls.insert(2, ("anchor", root))

    assert result.complete, result.warnings
    assert calls == expected_calls


def test_native_followed_root_stat_uses_the_extended_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logical = r"C:\mounted-volume"
    native = to_extended_length_path(logical)
    observed = _fake_stat(ino=7, directory=True)

    def followed_stat(path: str, *, follow_symlinks: bool):
        assert path == native
        assert follow_symlinks
        return observed

    monkeypatch.setattr(scanner_module.os, "stat", followed_stat)

    assert scanner_module.NativeScannerBackend().stat(logical) is observed


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


def test_enumeration_error_detail_sanitizes_native_filename() -> None:
    native = r"\\?\C:\root\private.bin"

    class DeniedBackend(FakeBackend):
        @contextmanager
        def scandir(self, path: str):
            del path

            def entries():
                raise PermissionError(13, "enumeration denied", native)
                yield

            yield entries()

    result = WalkingScanner(DeniedBackend({}, _profile())).scan(
        Root(r"C:\root", "source"), IgnoreSet(), _ctx()
    )

    warning = next(
        warning
        for warning in result.warnings
        if warning.code is ScanWarningCode.ENUMERATION_ERROR
    )
    assert warning.detail is not None
    assert repr(r"C:\root\private.bin") in warning.detail
    assert "\\\\?\\" not in warning.detail


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
