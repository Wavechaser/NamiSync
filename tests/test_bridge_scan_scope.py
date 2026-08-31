from __future__ import annotations

import stat as stat_module
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import namisync.core.models as models_module
import namisync.modules.scanner as scanner_module
from namisync.core.integrity import IntegrityMode
from namisync.core.models import (
    CapabilityProfile,
    DirRecord,
    EntryKind,
    FileIdentity,
    FileRecord,
    IgnoreSet,
    MetadataSnapshot,
    Root,
    ScanResult,
    ScanScope,
    ScanScopeKind,
    ScanWarning,
    ScanWarningCode,
    UnsupportedReason,
    UnsupportedRecord,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.recording import InventoryCommand
from namisync.core.session import RunContext
from namisync.db.connections import connect_ledger_reader
from namisync.db.recorder import (
    _SUBTREE_DESCENDANT_PREDICATE,
)
from namisync.db.repositories import InventoryPresence, LedgerRepository
from namisync.db.writer import TokenConflictError
from namisync.modules.scanner import (
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_OFFLINE,
    FILE_ATTRIBUTE_REPARSE_POINT,
    VolumeSnapshot,
    WalkingScanner,
)
from namisync.workflows.inventory import (
    IntegrityRequest,
    IntegrityWorkflowRequest,
    InventoryRequest,
    InventoryWorkflowRequest,
)
from namisync.workflows.runtime import LocalWorkflowRuntime

from _db_fixtures import NOW, file_stat, plan, setup_recorder
from _inventory_fixtures import (
    _Resolver as _InventoryResolver,
    _Scanner as _InventoryScanner,
    _runtime as _inventory_runtime,
)


_VOLUME_ID = VolumeId("source-serial", "NTFS")
_PROFILE = CapabilityProfile("NTFS", 100, True, False, 32_767, True, True)
_EVIDENCE = VolumeEvidence("Source", "C:")


def _context() -> RunContext:
    return RunContext(lambda _event: None, lambda: None)


def _fake_stat(
    *,
    ino: int,
    directory: bool = False,
    attributes: int = 0,
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
        st_nlink=1,
    )


@dataclass
class _FakeEntry:
    name: str
    path: str
    directory: bool
    observed: object

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        assert not follow_symlinks
        return self.directory

    def is_file(self, *, follow_symlinks: bool = True) -> bool:
        assert not follow_symlinks
        return not self.directory

    def stat(self, *, follow_symlinks: bool = True) -> object:
        assert not follow_symlinks
        if isinstance(self.observed, BaseException):
            raise self.observed
        return self.observed


class _FakeBackend:
    def __init__(
        self,
        *,
        entries: dict[str, list[_FakeEntry]] | None = None,
        stats: dict[str, object] | None = None,
    ) -> None:
        self.entries = entries or {}
        self.stats = stats or {}
        self.scandir_calls: list[str] = []

    def resolve_root(self, path: str) -> str:
        return path

    def volume_snapshot(self, root: str) -> VolumeSnapshot:
        return VolumeSnapshot(_VOLUME_ID, _EVIDENCE, _PROFILE)

    def lstat(self, path: str) -> object:
        value = self.stats.get(path, _fake_stat(ino=1, directory=True))
        if isinstance(value, BaseException):
            raise value
        return value

    @contextmanager
    def scandir(self, path: str):
        self.scandir_calls.append(path)
        yield iter(self.entries.get(path, ()))


def _file(path: str, index: int) -> FileRecord:
    observed = file_stat(identity_index=index)
    return FileRecord(
        path,
        normalize_relative_path(path),
        observed.size,
        observed.mtime_ns,
        observed.file_identity,
        observed.nlink,
        observed.metadata,
    )


def _unsupported(path: str) -> UnsupportedRecord:
    return UnsupportedRecord(
        path,
        normalize_relative_path(path),
        UnsupportedReason.ACCESS_DENIED,
    )


def _directory(path: str, index: int) -> DirRecord:
    return DirRecord(
        path,
        normalize_relative_path(path),
        11,
        MetadataSnapshot(0, 3),
        FileIdentity(_VOLUME_ID.serial, index),
        1,
    )


def _scan(
    files: tuple[FileRecord, ...] = (),
    *,
    directories: tuple[DirRecord, ...] = (),
    unsupported: tuple[UnsupportedRecord, ...] = (),
    warnings: tuple[ScanWarning, ...] = (),
    scope: ScanScope | None = None,
    complete: bool = True,
) -> ScanResult:
    sync_plan = plan(())
    return ScanResult(
        root=sync_plan.source_root,
        volume_id=sync_plan.source_volume_id,
        volume_evidence=_EVIDENCE,
        profile=sync_plan.source_profile,
        files=files,
        directories=directories,
        unsupported=unsupported,
        warnings=warnings,
        scope=scope or ScanScope.full(),
        complete=complete,
    )


def _record(setup, scan: ScanResult, token: str):
    return setup.recorder.record_inventory(
        InventoryCommand(
            setup.source_location_id,
            setup.host_id,
            scan,
            token,
            NOW,
        )
    )


def _rows(setup) -> dict[str, object]:
    with LedgerRepository(setup.recorder.path) as repository:
        return {
            row.rel_path: row
            for row in repository.get_inventory(setup.source_location_id)
        }


def test_br_g_4_nested_subtree_root_records_location_relative_keys(
    tmp_path: Path,
) -> None:
    nested = tmp_path / "Photos" / "2024"
    nested.mkdir(parents=True)
    (nested / "img.jpg").write_bytes(b"image")
    (tmp_path / "outside.jpg").write_bytes(b"outside")

    result = WalkingScanner().scan(
        Root(str(tmp_path), "location"),
        IgnoreSet(),
        _context(),
        ScanScope.subtrees(("Photos/2024",)),
    )

    assert result.complete, result.warnings
    assert tuple(record.rel_path_key for record in result.files) == (
        r"PHOTOS\2024\IMG.JPG",
    )
    assert {record.rel_path_key for record in result.directories} == {
        r"PHOTOS\2024"
    }
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    try:
        _record(
            setup,
            replace(result, volume_id=_VOLUME_ID),
            "nested-root",
        )
        with LedgerRepository(setup.recorder.path) as repository:
            stored_keys = {
                row.rel_path: row.rel_path_key
                for row in repository.get_inventory(
                    setup.source_location_id
                )
            }
        assert stored_keys[r"Photos\2024\img.jpg"] == (
            r"PHOTOS\2024\IMG.JPG"
        )
    finally:
        setup.recorder.close()


def test_br_g_5_completed_subtree_reconciliation_is_bounded_to_that_root(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    try:
        seeded = (
            _file(r"A\gone.bin", 1),
            _file(r"B\stay.bin", 2),
            _file(r"C\already-missing.bin", 3),
        )
        _record(setup, _scan(seeded), "seed")
        _record(
            setup,
            _scan(
                scope=ScanScope.selected((r"C\already-missing.bin",)),
            ),
            "mark-c-missing",
        )
        before = _rows(setup)

        result = _record(
            setup,
            _scan(scope=ScanScope.subtrees(("A",))),
            "refresh-a",
        )
        after = _rows(setup)

        assert result.missing_count == 1
        assert after[r"A\gone.bin"].presence is InventoryPresence.MISSING
        assert after[r"B\stay.bin"] == before[r"B\stay.bin"]
        assert after[r"C\already-missing.bin"] == before[
            r"C\already-missing.bin"
        ]
    finally:
        setup.recorder.close()


@pytest.mark.parametrize(
    ("root", "sibling"),
    [
        ("100%", r"100X\sibling.bin"),
        ("a_b", r"axb\sibling.bin"),
        ("bracket]", r"bracket^\sibling.bin"),
    ],
)
def test_br_g_6_hostile_subtree_roots_are_literal(
    tmp_path: Path,
    root: str,
    sibling: str,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    scoped_path = f"{root}\\gone.bin"
    try:
        _record(
            setup,
            _scan((_file(scoped_path, 1), _file(sibling, 2))),
            "seed",
        )

        _record(
            setup,
            _scan(scope=ScanScope.subtrees((root,))),
            "hostile-refresh",
        )
        rows = _rows(setup)

        assert rows[scoped_path].presence is InventoryPresence.MISSING
        assert rows[sibling].presence is InventoryPresence.PRESENT
    finally:
        setup.recorder.close()


def test_br_g_7_recursive_scope_uses_the_shared_full_walk_helper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subtree = tmp_path / "subtree"
    subtree.mkdir()
    calls: list[tuple[tuple[str, str], ...]] = []
    original = WalkingScanner._scan_full

    def observe(self, *args, **kwargs):
        calls.append(kwargs["starting_points"])
        return original(self, *args, **kwargs)

    monkeypatch.setattr(WalkingScanner, "_scan_full", observe)
    result = WalkingScanner().scan(
        Root(str(tmp_path), "location"),
        IgnoreSet(),
        _context(),
        ScanScope.subtrees(("subtree",)),
    )

    assert result.complete
    assert calls == [((str(subtree), "subtree"),)]


def test_br_g_7_recursive_scope_inherits_full_walk_ignore_completeness(
    tmp_path: Path,
) -> None:
    subtree = tmp_path / "subtree"
    subtree.mkdir()
    for name in (
        "THUMBS.DB",
        "desktop.ini",
        "asset.bin.synctmp-" + "a" * 32 + "-" + "b" * 32,
    ):
        (subtree / name).write_bytes(b"ignored")
    (subtree / "kept.bin").write_bytes(b"kept")

    result = WalkingScanner().scan(
        Root(str(tmp_path), "location"),
        IgnoreSet(),
        _context(),
        ScanScope.subtrees(("subtree",)),
    )

    assert result.complete, result.warnings
    assert tuple(record.rel_path for record in result.files) == (
        r"subtree\kept.bin",
    )


@pytest.mark.parametrize(
    ("directory", "attributes", "expected_complete"),
    [
        (
            False,
            FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_OFFLINE,
            True,
        ),
        (False, FILE_ATTRIBUTE_REPARSE_POINT, True),
        (
            True,
            FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_OFFLINE,
            False,
        ),
        (True, FILE_ATTRIBUTE_REPARSE_POINT, False),
    ],
)
def test_br_g_7_recursive_scope_preserves_file_directory_uncertainty(
    directory: bool,
    attributes: int,
    expected_complete: bool,
) -> None:
    root = r"C:\location"
    subtree = root + r"\A"
    child = subtree + r"\item"
    entry = _FakeEntry(
        "item",
        child,
        directory,
        _fake_stat(ino=2, directory=directory, attributes=attributes),
    )
    backend = _FakeBackend(
        entries={subtree: [entry]},
        stats={subtree: _fake_stat(ino=1, directory=True)},
    )

    result = WalkingScanner(backend).scan(
        Root(root, "location"),
        IgnoreSet(),
        _context(),
        ScanScope.subtrees(("A",)),
    )

    assert result.complete is expected_complete
    assert result.unsupported[0].kind is (
        EntryKind.DIRECTORY if directory else EntryKind.FILE
    )


def test_br_g_7_subtree_root_reparse_uses_windows_directory_attribute() -> None:
    root = r"C:\location"
    subtree = root + r"\A"
    observed = _fake_stat(
        ino=1,
        attributes=(
            FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT
        ),
    )
    observed.st_mode = stat_module.S_IFLNK | 0o777
    backend = _FakeBackend(stats={subtree: observed})

    result = WalkingScanner(backend).scan(
        Root(root, "location"),
        IgnoreSet(),
        _context(),
        ScanScope.subtrees(("A",)),
    )

    assert not result.complete
    assert result.unsupported[0].kind is EntryKind.DIRECTORY
    assert backend.scandir_calls == []


@pytest.mark.parametrize(
    "cause",
    (
        "directory-placeholder",
        "directory-reparse",
        "directory-reparse-owned-temp",
        "duplicate-identity",
    ),
)
def test_br_g_7_recursive_incompleteness_withholds_missing_inference(
    tmp_path: Path,
    cause: str,
) -> None:
    root = r"C:\location"
    subtree = root + r"\A"
    name = (
        "asset.bin.synctmp-" + "a" * 32 + "-" + "b" * 32
        if cause == "directory-reparse-owned-temp"
        else "item"
    )
    child = subtree + "\\" + name
    if cause == "duplicate-identity":
        entry = _FakeEntry(
            name,
            child,
            True,
            _fake_stat(ino=1, directory=True),
        )
    else:
        attributes = FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT
        if cause == "directory-placeholder":
            attributes |= FILE_ATTRIBUTE_OFFLINE
        observed = _fake_stat(ino=2, attributes=attributes)
        observed.st_mode = stat_module.S_IFLNK | 0o777
        entry = _FakeEntry(name, child, False, observed)
    backend = _FakeBackend(
        entries={subtree: [entry]},
        stats={subtree: _fake_stat(ino=1, directory=True)},
    )
    result = WalkingScanner(backend).scan(
        Root(root, "location"),
        IgnoreSet(),
        _context(),
        ScanScope.subtrees(("A",)),
    )

    assert not result.complete
    if cause != "duplicate-identity":
        assert result.unsupported[0].kind is EntryKind.DIRECTORY

    stale_path = f"A\\{name}\\stale.bin"
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    try:
        _record(
            setup,
            _scan((_file(stale_path, 90),)),
            "seed-incomplete",
        )
        before = _rows(setup)
        _record(setup, result, f"incomplete-{cause}")
        after = _rows(setup)
        assert after[stale_path] == before[stale_path]
    finally:
        setup.recorder.close()


def test_br_g_7_requested_roots_share_one_directory_identity_guard() -> None:
    root = r"C:\location"
    first = root + r"\A"
    second = root + r"\B"
    crossing = first + r"\junction-to-b"
    backend = _FakeBackend(
        entries={
            first: [
                _FakeEntry(
                    "junction-to-b",
                    crossing,
                    True,
                    _fake_stat(ino=20, directory=True),
                )
            ],
            second: [],
        },
        stats={
            first: _fake_stat(ino=10, directory=True),
            second: _fake_stat(ino=20, directory=True),
        },
    )

    result = WalkingScanner(backend).scan(
        Root(root, "location"),
        IgnoreSet(),
        _context(),
        ScanScope.subtrees(("A", "B")),
    )

    assert not result.complete
    assert any(
        warning.code is ScanWarningCode.DUPLICATE_IDENTITY
        for warning in result.warnings
    )
    assert crossing not in backend.scandir_calls


def test_br_g_8_absent_subtree_root_is_a_complete_empty_observation() -> None:
    root = r"C:\location"
    missing = root + r"\gone"
    result = WalkingScanner(
        _FakeBackend(stats={missing: FileNotFoundError("gone")})
    ).scan(
        Root(root, "location"),
        IgnoreSet(),
        _context(),
        ScanScope.subtrees(("gone",)),
    )

    assert result.complete
    assert result.files == ()
    assert result.directories == ()
    assert any(
        warning.code is ScanWarningCode.DISAPPEARED
        and warning.rel_path == "gone"
        for warning in result.warnings
    )


@pytest.mark.parametrize("error", [PermissionError("denied"), OSError("io")])
def test_br_g_8_unavailable_subtree_root_is_incomplete_and_names_root(
    error: OSError,
) -> None:
    root = r"C:\location"
    unavailable = root + r"\private"
    result = WalkingScanner(_FakeBackend(stats={unavailable: error})).scan(
        Root(root, "location"),
        IgnoreSet(),
        _context(),
        ScanScope.subtrees(("private",)),
    )

    assert not result.complete
    assert result.files == ()
    warning = next(
        item
        for item in result.warnings
        if item.code is ScanWarningCode.ROOT_UNAVAILABLE
    )
    assert warning.rel_path == "private"


def test_br_g_8_subtree_root_that_became_a_file_is_recorded_as_file() -> None:
    root = r"C:\location"
    former_folder = root + r"\former"
    result = WalkingScanner(
        _FakeBackend(stats={former_folder: _fake_stat(ino=4)})
    ).scan(
        Root(root, "location"),
        IgnoreSet(),
        _context(),
        ScanScope.subtrees(("former",)),
    )

    assert result.complete, result.warnings
    assert tuple(record.rel_path for record in result.files) == ("former",)
    assert result.directories == ()


def test_br_g_8_root_observations_drive_only_conclusive_missing_inference(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    root = r"C:\location"
    gone = root + r"\gone"
    private = root + r"\private"
    former = root + r"\former"
    try:
        _record(
            setup,
            _scan(
                (
                    _file(r"gone\child.bin", 11),
                    _file(r"private\child.bin", 12),
                    _file(r"former\child.bin", 13),
                ),
                directories=(
                    _directory("gone", 1),
                    _directory("private", 2),
                    _directory("former", 3),
                ),
            ),
            "seed-roots",
        )
        before = _rows(setup)

        absent_scan = WalkingScanner(
            _FakeBackend(stats={gone: FileNotFoundError("gone")})
        ).scan(
            Root(root, "location"),
            IgnoreSet(),
            _context(),
            ScanScope.subtrees(("gone",)),
        )
        _record(setup, absent_scan, "gone-root")

        unavailable_scan = WalkingScanner(
            _FakeBackend(stats={private: PermissionError("denied")})
        ).scan(
            Root(root, "location"),
            IgnoreSet(),
            _context(),
            ScanScope.subtrees(("private",)),
        )
        _record(setup, unavailable_scan, "private-root")

        file_scan = WalkingScanner(
            _FakeBackend(stats={former: _fake_stat(ino=30)})
        ).scan(
            Root(root, "location"),
            IgnoreSet(),
            _context(),
            ScanScope.subtrees(("former",)),
        )
        _record(setup, file_scan, "former-file")
        after = _rows(setup)

        assert after["gone"].presence is InventoryPresence.MISSING
        assert after[r"gone\child.bin"].presence is InventoryPresence.MISSING
        assert after["private"] == before["private"]
        assert after[r"private\child.bin"] == before[r"private\child.bin"]
        assert after["former"].presence is InventoryPresence.PRESENT
        assert after["former"].entry_kind is EntryKind.FILE
        assert after[r"former\child.bin"].presence is InventoryPresence.MISSING
    finally:
        setup.recorder.close()


def test_br_g_9_inventory_receipt_hash_binds_subtree_roots(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    try:
        _record(
            setup,
            _scan(scope=ScanScope.subtrees(("A",))),
            "same-token",
        )

        with pytest.raises(TokenConflictError):
            _record(
                setup,
                _scan(scope=ScanScope.subtrees(("B",))),
                "same-token",
            )
    finally:
        setup.recorder.close()


def test_br_g_25_scope_normalization_preserves_mixed_union_meaning() -> None:
    scope = ScanScope.scoped(
        selected_paths=(
            r"A\covered.bin",
            r"Exact\File.bin",
            "ExactDir",
            r"exact\file.bin",
        ),
        subtree_roots=(
            r"A\Nested",
            "A",
            r"a\nested\deeper",
            "B",
            r"B\Child",
        ),
    )

    assert scope.kind is ScanScopeKind.SUBTREES
    assert scope.subtree_roots == ("A", "B")
    assert scope.selected_paths == ("ExactDir", r"Exact\File.bin")
    assert ScanScope.scoped(subtree_roots=("", "A")) == ScanScope.full()
    assert ScanScope.scoped() == ScanScope.full()
    with pytest.raises(ValueError):
        ScanScope(ScanScopeKind.FULL, ("file.bin",))
    with pytest.raises(ValueError):
        ScanScope(ScanScopeKind.PATHS)
    with pytest.raises(ValueError):
        ScanScope(ScanScopeKind.SUBTREES)
    with pytest.raises(ValueError, match="non-root subtree"):
        ScanScope(
            ScanScopeKind.SUBTREES,
            subtree_roots=("", "A"),
        )


def test_br_g_25_scope_normalization_calls_stay_linear_in_declared_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    normalize = models_module.normalize_relative_path
    calls = 0

    def counted(value: str, *, allow_root: bool = False) -> str:
        nonlocal calls
        calls += 1
        return normalize(value, allow_root=allow_root)

    monkeypatch.setattr(models_module, "normalize_relative_path", counted)
    roots = tuple(f"Root-{index:04d}" for index in range(400))
    exact = tuple(
        f"Root-{index:04d}\\child.bin" for index in range(400)
    ) + tuple(f"Exact-{index:04d}.bin" for index in range(400))

    scope = ScanScope.scoped(
        selected_paths=exact,
        subtree_roots=roots,
    )

    assert len(scope.subtree_roots) == 400
    assert len(scope.selected_paths) == 400
    assert calls < 10_000


def test_br_g_26_subtree_reconciliation_handles_every_presence_branch(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    try:
        _record(
            setup,
            _scan(
                (
                    _file(r"A\present.bin", 1),
                    _file(r"A\already-missing.bin", 2),
                    _file(r"Exact\present.bin", 3),
                    _file(r"B\outside.bin", 4),
                ),
                unsupported=(
                    _unsupported(r"A\unsupported.bin"),
                    _unsupported(r"Exact\unsupported.bin"),
                ),
            ),
            "seed",
        )
        _record(
            setup,
            _scan(
                scope=ScanScope.selected((r"A\already-missing.bin",)),
            ),
            "seed-missing",
        )
        before = _rows(setup)

        _record(
            setup,
            _scan(
                scope=ScanScope.subtrees(
                    ("A",),
                    selected_paths=(
                        r"Exact\present.bin",
                        r"Exact\unsupported.bin",
                    ),
                )
            ),
            "complete-subtree",
        )
        after = _rows(setup)

        assert after[r"A\present.bin"].presence is InventoryPresence.MISSING
        assert after[r"A\unsupported.bin"].presence is InventoryPresence.MISSING
        assert (
            after[r"Exact\present.bin"].presence
            is InventoryPresence.MISSING
        )
        assert (
            after[r"Exact\unsupported.bin"].presence
            is InventoryPresence.MISSING
        )
        assert after[r"A\already-missing.bin"] == before[
            r"A\already-missing.bin"
        ]
        assert after[r"B\outside.bin"] == before[r"B\outside.bin"]

        _record(
            setup,
            _scan(
                (_file(r"A\still-present.bin", 4),),
                unsupported=(_unsupported(r"A\still-unsupported.bin"),),
                scope=ScanScope.subtrees(
                    ("A",),
                    selected_paths=(r"Exact\present.bin",),
                ),
            ),
            "reseed",
        )
        before_incomplete = _rows(setup)
        _record(
            setup,
            _scan(
                scope=ScanScope.subtrees(
                    ("A",),
                    selected_paths=(r"Exact\present.bin",),
                ),
                complete=False,
            ),
            "incomplete-subtree",
        )
        after_incomplete = _rows(setup)

        assert after_incomplete == before_incomplete
    finally:
        setup.recorder.close()


def test_br_g_26_one_incomplete_root_withholds_all_multi_root_inference(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    try:
        _record(
            setup,
            _scan(
                (
                    _file(r"A\gone.bin", 1),
                    _file(r"B\unreadable.bin", 2),
                )
            ),
            "seed-multi-root",
        )
        before = _rows(setup)

        _record(
            setup,
            _scan(
                warnings=(
                    ScanWarning(
                        ScanWarningCode.ROOT_UNAVAILABLE,
                        "B",
                        "access denied",
                    ),
                ),
                scope=ScanScope.subtrees(("A", "B")),
                complete=False,
            ),
            "incomplete-multi-root",
        )

        assert _rows(setup) == before
    finally:
        setup.recorder.close()


def test_br_g_27_subtree_range_uses_declared_inventory_index(
    tmp_path: Path,
) -> None:
    setup = setup_recorder(tmp_path / "ledger.db", plan(()))
    root_key = normalize_relative_path("A")
    connection = connect_ledger_reader(setup.recorder.path)
    try:
        plan_rows = connection.execute(
            f"""EXPLAIN QUERY PLAN
                SELECT id FROM inventory
                 WHERE location_id = ?
                   AND presence = ?
                   AND {_SUBTREE_DESCENDANT_PREDICATE}""",
            (
                setup.source_location_id,
                "present",
                root_key,
                root_key,
            ),
        ).fetchall()
    finally:
        connection.close()
        setup.recorder.close()

    detail = "\n".join(str(row["detail"]) for row in plan_rows)
    assert "inventory_location_presence_idx" in detail
    assert "location_id=? AND presence=?" in detail
    assert "rel_path_key>? AND rel_path_key<?" in detail
    assert "LIKE" not in _SUBTREE_DESCENDANT_PREDICATE.upper()


def test_br_g_28_inventory_and_integrity_checkpoints_are_detached_and_exact(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mount"
    (mount / "managed").mkdir(parents=True)
    runtime, location_id = _inventory_runtime(
        tmp_path,
        _InventoryResolver(mount),
        _InventoryScanner(mount, ()),
        {},
    )
    inventory = InventoryRequest(
        "inventory",
        location_id=location_id,
        selected_paths=(r"Exact\File.bin",),
        subtree_roots=("Folder",),
    )
    integrity = IntegrityRequest(
        "integrity",
        IntegrityMode.VERIFY,
        location_id=location_id,
        selected_paths=(r"Exact\File.bin",),
    )

    try:
        inventory_checkpoint = runtime.prepare_inventory(inventory).checkpoint
        integrity_checkpoint = runtime.prepare_verify(integrity).checkpoint

        assert type(inventory_checkpoint) is InventoryWorkflowRequest
        assert type(integrity_checkpoint) is IntegrityWorkflowRequest
        assert inventory_checkpoint.request_id == "inventory"
        assert integrity_checkpoint.request_id == "integrity"
        assert integrity_checkpoint.mode is IntegrityMode.VERIFY

        object.__setattr__(inventory, "request_id", "mutated-inventory")
        object.__setattr__(inventory, "selected_paths", ("mutated.txt",))
        object.__setattr__(integrity, "request_id", "mutated-integrity")
        object.__setattr__(integrity, "mode", IntegrityMode.BASELINE)
        assert inventory_checkpoint.request_id == "inventory"
        assert inventory_checkpoint.selected_paths == (r"Exact\File.bin",)
        assert integrity_checkpoint.request_id == "integrity"
        assert integrity_checkpoint.mode is IntegrityMode.VERIFY

        with pytest.raises(TypeError, match="InventoryWorkflowRequest"):
            runtime.open_inventory(integrity_checkpoint)
        with pytest.raises(TypeError, match="IntegrityWorkflowRequest"):
            runtime.open_verify(inventory_checkpoint)
        with pytest.raises(ValueError, match="baseline invocation checkpoint"):
            runtime.open_baseline(integrity_checkpoint)

        first = runtime.open_verify(integrity_checkpoint)
        second = runtime.open_verify(integrity_checkpoint)
        first_snapshot = first.snapshot()
        second_snapshot = second.snapshot()

        assert first is not second
        assert first_snapshot == second_snapshot
        assert first_snapshot is not second_snapshot
        object.__setattr__(first_snapshot, "omitted_detail_count", 3)
        assert first_snapshot.omitted_detail_count == 3
        assert second_snapshot.omitted_detail_count == 0
        assert integrity_checkpoint.omitted_detail_count == 0
    finally:
        runtime.close()
