"""Verifier classification, continuation, and cache-honesty tests."""

from __future__ import annotations

import ast
import inspect
import os
import stat as stat_module
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

import pytest
from xxhash import xxh3_128

import namisync.modules.verifier as verifier_facade
import namisync.modules.verifier.engine as verifier_engine
import namisync.modules.verifier.native as verifier_native
from namisync.core.evidence import (
    Attestation,
    HasherContractError,
    Provenance,
    RecordingStatus,
)
from namisync.core.events import Progress
from namisync.core.integrity import (
    AuthorityBoundVerificationReader,
    IntegrityMode,
    IntegrityOutcome,
    IntegrityReason,
    IntegrityResult,
    IntegritySelection,
    InventoryState,
    PostCopySelection,
    ReadStrategy,
    RecordDisposition,
    UnsupportedVerification,
    VerificationInvalidationReason,
    VerifierContext,
)
from namisync.core.models import (
    FileIdentity,
    FileStat,
    VolumeId,
)
from namisync.core.pathing import (
    normalize_relative_path,
)
from namisync.core.root_authority import (
    RootAuthority,
    RootAuthorityError,
    RootAuthorityIssue,
)
from namisync.core.session import (
    Canceled,
    OperationResult,
    PauseRequested,
    RunContext,
    SessionState,
    run_session,
)
from namisync.modules.verifier import (
    WindowsUnbufferedReader,
    baseline,
    rebaseline,
    verify,
    verify_post_copy,
)

from _verifier_fixtures import (
    _Clock,
    _FakeReader,
    _Recorder,
    _StreamSpec,
    _attestation,
    _context,
    _integrity_events,
    _item,
    _post_copy_candidate,
    _stat,
)


def test_verifier_package_boundaries_match_component_ownership() -> None:
    package = Path(__file__).parents[2] / "namisync" / "modules" / "verifier"
    sources = {
        path.name: path.read_text(encoding="utf-8")
        for path in package.glob("*.py")
    }
    assert set(sources) == {"__init__.py", "engine.py", "native.py"}

    forbidden_components = (
        "namisync.modules.executor",
        "namisync.modules.planner",
        "namisync.modules.preflight",
        "namisync.modules.scanner",
    )
    assert all(
        component not in text
        for text in sources.values()
        for component in forbidden_components
    )

    def relative_imports(name: str) -> set[str]:
        tree = ast.parse(sources[name])
        return {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level
        }

    def project_imports(name: str) -> set[str]:
        tree = ast.parse(sources[name])
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and not node.level and node.module:
                if node.module.startswith("namisync."):
                    imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(
                    alias.name
                    for alias in node.names
                    if alias.name.startswith("namisync.")
                )
        return imported

    assert relative_imports("__init__.py") == {"engine", "native"}
    assert relative_imports("engine.py") == {"native"}
    assert relative_imports("native.py") == set()
    for name in ("engine.py", "native.py"):
        assert project_imports(name)
        assert all(
            module.startswith("namisync.core.")
            for module in project_imports(name)
        )


def test_verifier_public_facade_preserves_exact_exports_and_signatures() -> None:
    assert verifier_facade.__all__ == [
        "WindowsUnbufferedReader",
        "baseline",
        "rebaseline",
        "verify",
        "verify_post_copy",
    ]
    assert (
        verifier_facade.WindowsUnbufferedReader
        is verifier_native.WindowsUnbufferedReader
    )
    assert verifier_facade.baseline is verifier_engine.baseline
    assert verifier_facade.rebaseline is verifier_engine.rebaseline
    assert verifier_facade.verify is verifier_engine.verify
    assert verifier_facade.verify_post_copy is verifier_engine.verify_post_copy

    signatures = {
        name: str(inspect.signature(getattr(verifier_facade, name)))
        for name in verifier_facade.__all__
    }
    assert signatures == {
        "WindowsUnbufferedReader": (
            "(root_authority: 'RootAuthority | None' = None) -> 'None'"
        ),
        "baseline": (
            "(selection: 'IntegritySelection', ctx: 'VerifierContext', "
            "recorder: 'IntegrityRecorder', reader: 'VerificationReader | None' "
            "= None) -> 'IntegrityRunResult'"
        ),
        "rebaseline": (
            "(selection: 'IntegritySelection', ctx: 'VerifierContext', "
            "recorder: 'IntegrityRecorder', reader: 'VerificationReader | None' "
            "= None) -> 'IntegrityRunResult'"
        ),
        "verify": (
            "(selection: 'IntegritySelection', ctx: 'VerifierContext', "
            "recorder: 'IntegrityRecorder', reader: 'VerificationReader | None' "
            "= None) -> 'IntegrityRunResult'"
        ),
        "verify_post_copy": (
            "(selection: 'PostCopySelection', ctx: 'VerifierContext', "
            "recorder: 'IntegrityRecorder', reader: 'VerificationReader | None' "
            "= None) -> 'IntegrityRunResult'"
        ),
    }


def test_xxh3_128_digest_encoding_is_raw_canonical_big_endian() -> None:
    hasher = xxh3_128()

    assert hasher.digest().hex() == "99aa06d3014798d86001c324468d497f"
    assert hasher.digest() == hasher.intdigest().to_bytes(16, "big")


@pytest.mark.parametrize(
    ("live_stat", "content", "expected_result"),
    [
        (_stat(size=4), b"abcd", IntegrityResult.MODIFIED),
        (_stat(mtime_ns=101), b"abc", IntegrityResult.MODIFIED),
        (
            _stat(identity=FileIdentity("A1B2C3D4", 8)),
            b"abc",
            IntegrityResult.MODIFIED,
        ),
        (_stat(), b"abd", IntegrityResult.MISMATCHED),
        (_stat(), b"abc", IntegrityResult.VERIFIED),
    ],
)
def test_verify_classifies_stat_drift_before_digest_mismatch(
    tmp_path: Path,
    live_stat: FileStat,
    content: bytes,
    expected_result: IntegrityResult,
) -> None:
    item = _item(tmp_path)
    selection = IntegritySelection((item,))
    reader = _FakeReader(
        {item.display_path: _StreamSpec(live_stat, (content,), live_stat)}
    )
    recorder = _Recorder()
    events: list[object] = []

    result = verify(
        selection,
        replace(_context(events), progress_interval_seconds=0),
        recorder,
        reader,
    )

    assert result.outcomes[0].result is expected_result
    assert len(_integrity_events(events)) == 1
    assert len(recorder.commands) == (1 if expected_result is IntegrityResult.VERIFIED else 0)
    assert len(recorder.invalidation_commands) == (
        0 if expected_result is IntegrityResult.VERIFIED else 1
    )
    active_progress = [
        event
        for event in events
        if isinstance(event, Progress) and event.item_id == item.item_id
    ]
    assert active_progress
    if live_stat != item.expected_stat:
        assert all(
            event.item_bytes_done is None and event.item_bytes_total is None
            for event in active_progress
        )
    else:
        assert any(
            event.item_bytes_done is not None
            and event.item_bytes_total == item.expected_stat.size
            for event in active_progress
        )


def _reviewed_context(
    events: list[object],
    root: Path,
    anchor: Path | None,
    volume_id: VolumeId,
) -> VerifierContext:
    return replace(
        _context(events),
        root_authority=RootAuthority(
            logical_root=str(root),
            reviewed_anchor=None if anchor is None else str(anchor),
            expected_volume_id=volume_id,
        ),
    )


def _mock_reviewed_root_state(
    monkeypatch: pytest.MonkeyPatch,
    state: dict[str, object],
) -> None:
    admissions: list[RootAuthority] = []
    state["admissions"] = admissions

    def admit(authority: RootAuthority) -> None:
        admissions.append(authority)
        if (
            authority.reviewed_anchor is not None
            and os.path.normcase(os.path.normpath(str(state["anchor"])))
            != os.path.normcase(os.path.normpath(authority.reviewed_anchor))
        ):
            raise RootAuthorityError(
                RootAuthorityIssue.ANCHOR_CHANGED,
                authority.logical_root,
                "reviewed root volume anchor changed",
            )
        if (
            authority.expected_volume_id is not None
            and state["volume_id"] != authority.expected_volume_id
        ):
            raise RootAuthorityError(
                RootAuthorityIssue.VOLUME_CHANGED,
                authority.logical_root,
                "reviewed root volume identity changed",
            )

    monkeypatch.setattr(verifier_engine, "admit_root", admit)


def test_verifier_refuses_remount_before_first_native_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewed_anchor = tmp_path / "reviewed-mount"
    foreign_anchor = tmp_path / "foreign-mount"
    reviewed_volume = VolumeId("A1B2C3D4", "NTFS")
    state: dict[str, object] = {
        "anchor": foreign_anchor,
        "volume_id": VolumeId("DEADBEEF", "NTFS"),
    }
    _mock_reviewed_root_state(monkeypatch, state)
    root = reviewed_anchor / "managed"
    item = _item(root, expected_stat=_stat(identity=None))
    reader = _FakeReader(
        {
            item.display_path: _StreamSpec(
                _stat(identity=FileIdentity(reviewed_volume.serial, 7)),
                (b"foreign-bytes",),
            )
        }
    )
    recorder = _Recorder()

    result = verify(
        IntegritySelection((item,)),
        _reviewed_context([], root, reviewed_anchor, reviewed_volume),
        recorder,
        reader,
    )

    assert result.outcomes[0].result is IntegrityResult.UNSUPPORTED
    assert reader.opened == []
    assert recorder.commands == []


def test_verifier_revalidates_reviewed_mount_between_items(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewed_anchor = tmp_path / "reviewed-mount"
    foreign_anchor = tmp_path / "foreign-mount"
    reviewed_volume = VolumeId("A1B2C3D4", "NTFS")
    state: dict[str, object] = {
        "anchor": reviewed_anchor,
        "volume_id": reviewed_volume,
    }
    _mock_reviewed_root_state(monkeypatch, state)
    root = reviewed_anchor / "managed"
    first = _item(root, number=1, expected_stat=_stat(identity=None))
    second = _item(root, number=2, expected_stat=_stat(identity=None))
    live = _stat(identity=FileIdentity(reviewed_volume.serial, 7))

    class RemountAfterFirstReader(_FakeReader):
        @contextmanager
        def open(self, root: Path, relative_path: str):
            with super().open(root, relative_path) as stream:
                yield stream
            if len(self.opened) == 1:
                state["anchor"] = foreign_anchor
                state["volume_id"] = VolumeId("DEADBEEF", "NTFS")

    reader = RemountAfterFirstReader(
        {
            first.display_path: _StreamSpec(live, (b"abc",), live),
            second.display_path: _StreamSpec(
                live,
                (b"foreign-bytes",),
                live,
            ),
        }
    )
    recorder = _Recorder()

    result = verify(
        IntegritySelection((first, second)),
        _reviewed_context([], root, reviewed_anchor, reviewed_volume),
        recorder,
        reader,
    )

    assert [outcome.result for outcome in result.outcomes] == [
        IntegrityResult.VERIFIED,
        IntegrityResult.UNSUPPORTED,
    ]
    assert reader.opened == [(root, first.display_path)]
    assert len(recorder.commands) == 1
    assert len(state["admissions"]) == 2


def test_verifier_refuses_opened_handle_on_foreign_volume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewed_anchor = tmp_path / "reviewed-mount"
    reviewed_volume = VolumeId("A1B2C3D4", "NTFS")
    state: dict[str, object] = {
        "anchor": reviewed_anchor,
        "volume_id": reviewed_volume,
    }
    _mock_reviewed_root_state(monkeypatch, state)
    root = reviewed_anchor / "managed"
    item = _item(root, expected_stat=_stat(identity=None))
    reader = _FakeReader(
        {
            item.display_path: _StreamSpec(
                _stat(identity=FileIdentity("DEADBEEF", 7)),
                (b"foreign-bytes",),
            )
        }
    )
    recorder = _Recorder()

    result = verify(
        IntegritySelection((item,)),
        _reviewed_context([], root, reviewed_anchor, reviewed_volume),
        recorder,
        reader,
    )

    assert result.outcomes[0].result is IntegrityResult.UNSUPPORTED
    assert len(reader.opened) == 1
    assert recorder.commands == []


def test_verifier_binds_volume_when_reviewed_anchor_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewed_volume = VolumeId("A1B2C3D4", "NTFS")
    state: dict[str, object] = {
        "anchor": tmp_path,
        "volume_id": reviewed_volume,
    }
    _mock_reviewed_root_state(monkeypatch, state)
    live = _stat(identity=FileIdentity(reviewed_volume.serial, 7))
    item = _item(tmp_path, expected_stat=live)
    reader = _FakeReader(
        {item.display_path: _StreamSpec(live, (b"abc",), live)}
    )
    recorder = _Recorder()
    context = replace(
        _context([]),
        root_authority=RootAuthority(
            logical_root=str(tmp_path),
            expected_volume_id=reviewed_volume,
        ),
    )

    result = verify(
        IntegritySelection((item,)),
        context,
        recorder,
        reader,
    )

    assert result.outcomes[0].result is IntegrityResult.VERIFIED
    assert reader.opened == [(tmp_path, item.display_path)]
    assert len(recorder.commands) == 1


def test_verifier_refuses_reviewed_open_without_volume_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewed_volume = VolumeId("A1B2C3D4", "NTFS")
    state: dict[str, object] = {
        "anchor": tmp_path,
        "volume_id": reviewed_volume,
    }
    _mock_reviewed_root_state(monkeypatch, state)
    item = _item(tmp_path, expected_stat=_stat(identity=None))
    live = _stat(identity=None)
    reader = _FakeReader(
        {item.display_path: _StreamSpec(live, (b"foreign-bytes",), live)}
    )
    recorder = _Recorder()

    result = verify(
        IntegritySelection((item,)),
        _reviewed_context([], tmp_path, tmp_path, reviewed_volume),
        recorder,
        reader,
    )

    assert result.outcomes[0].result is IntegrityResult.UNSUPPORTED
    assert len(reader.opened) == 1
    assert recorder.commands == []


_ROOT_BOUND_STATE_CASES = (
    (IntegrityMode.VERIFY, InventoryState.PRESENT),
    (IntegrityMode.VERIFY, InventoryState.MISSING),
    (IntegrityMode.VERIFY, InventoryState.UNSUPPORTED),
    (IntegrityMode.BASELINE, InventoryState.PRESENT),
)

_ROOT_ADMISSION_PRECEDENCE_CASES = (
    pytest.param(
        False,
        IntegrityResult.UNSUPPORTED,
        IntegrityReason.UNSUPPORTED_READ,
        "mismatched root must not be admitted",
        id="mismatched-root",
    ),
    pytest.param(
        True,
        IntegrityResult.ERROR,
        IntegrityReason.PATH_INVALID,
        "invalid path must not be admitted",
        id="invalid-path",
    ),
)


@pytest.mark.parametrize(("mode", "expected_state"), _ROOT_BOUND_STATE_CASES)
@pytest.mark.parametrize(
    ("invalid_path", "expected_result", "expected_reason", "admission_message"),
    _ROOT_ADMISSION_PRECEDENCE_CASES,
)
def test_verifier_root_and_path_admission_precede_state_shortcuts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: IntegrityMode,
    expected_state: InventoryState,
    invalid_path: bool,
    expected_result: IntegrityResult,
    expected_reason: IntegrityReason,
    admission_message: str,
) -> None:
    reviewed_root = tmp_path / "reviewed"
    selected_root = tmp_path / "different"
    item = _item(selected_root, expected_state=expected_state)
    if invalid_path:
        item = replace(item, display_path=r"..\escape.bin")
    reader = _FakeReader({})
    recorder = _Recorder()
    events: list[object] = []
    context = replace(
        _context(events),
        root_authority=RootAuthority(str(reviewed_root)),
        progress_interval_seconds=0,
    )
    monkeypatch.setattr(
        verifier_engine,
        "admit_root",
        lambda _authority: pytest.fail(admission_message),
    )

    runner = baseline if mode is IntegrityMode.BASELINE else verify
    result = runner(IntegritySelection((item,)), context, recorder, reader)

    assert result.outcomes[0].result is expected_result
    assert result.outcomes[0].reason is expected_reason
    assert reader.opened == []
    assert recorder.commands == []
    assert recorder.invalidation_commands == []
    active_progress = [
        event
        for event in events
        if isinstance(event, Progress) and event.item_id == item.item_id
    ]
    assert active_progress
    assert all(
        event.item_type == "integrity"
        and event.item_bytes_done is None
        and event.item_bytes_total is None
        for event in active_progress
    )


@pytest.mark.parametrize(
    ("invalid_path", "expected_result", "expected_reason", "admission_message"),
    _ROOT_ADMISSION_PRECEDENCE_CASES,
)
def test_post_copy_root_and_path_admission_precede_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_path: bool,
    expected_result: IntegrityResult,
    expected_reason: IntegrityReason,
    admission_message: str,
) -> None:
    candidate = _post_copy_candidate(tmp_path / "different")
    if invalid_path:
        object.__setattr__(candidate, "display_path", r"..\escape.bin")
    reader = _FakeReader({})
    recorder = _Recorder()
    events: list[object] = []
    context = replace(
        _context(events),
        root_authority=RootAuthority(str(tmp_path / "reviewed")),
        progress_interval_seconds=0,
    )
    monkeypatch.setattr(
        verifier_engine,
        "admit_root",
        lambda _authority: pytest.fail(admission_message),
    )

    result = verify_post_copy(
        PostCopySelection((candidate,)),
        context,
        recorder,
        reader,
    )

    assert result.outcomes[0].result is expected_result
    assert result.outcomes[0].reason is expected_reason
    assert reader.opened == []
    assert recorder.commands == []
    assert recorder.invalidation_commands == []
    active_progress = [
        event
        for event in events
        if isinstance(event, Progress) and event.item_id == candidate.item_id
    ]
    assert active_progress
    assert all(
        event.item_type == "operation"
        and event.item_bytes_done is None
        and event.item_bytes_total is None
        for event in active_progress
    )


def test_default_and_authority_bound_readers_require_root_authority(
    tmp_path: Path,
) -> None:
    selection = IntegritySelection(())
    context = _context([])

    class EmptyNativeReader(WindowsUnbufferedReader):
        pass

    class InstrumentedNativeReader(WindowsUnbufferedReader):
        def __init__(self) -> None:
            super().__init__()
            self.opened: list[tuple[str, RootAuthority]] = []

        @contextmanager
        def open(self, root: Path, relative_path: str) -> Iterator[object]:
            raise AssertionError("bound dispatch must not use the legacy open seam")
            yield object()

        @contextmanager
        def open_with_authority(
            self,
            relative_path: str,
            authority: RootAuthority,
        ) -> Iterator[object]:
            self.opened.append((relative_path, authority))
            yield object()

    instrumented = InstrumentedNativeReader()

    with pytest.raises(ValueError, match="default verification reader"):
        verify(selection, context, _Recorder())
    for reader in (
        WindowsUnbufferedReader(),
        EmptyNativeReader(),
        instrumented,
    ):
        assert isinstance(reader, AuthorityBoundVerificationReader)
        with pytest.raises(ValueError, match="authority-bound verification reader"):
            verify(selection, context, _Recorder(), reader)

    authority = RootAuthority(str(tmp_path))
    bound_context = replace(
        context,
        root_authority=authority,
    )
    selected = verifier_engine._reader_for_context(
        bound_context,
        instrumented,
    )
    assert selected is instrumented
    with verifier_engine._open_reader(
        selected,
        tmp_path,
        "payload.bin",
        bound_context,
    ):
        pass
    assert instrumented.opened == [("payload.bin", authority)]


@pytest.mark.skipif(os.name != "nt", reason="Windows reader admission order")
def test_native_reader_keeps_full_and_final_touch_admissions_distinct(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = RootAuthority(str(tmp_path))
    context = replace(_context([]), root_authority=authority)
    calls: list[str] = []

    def admit_full(observed: RootAuthority) -> None:
        assert observed is authority
        calls.append("full")

    def admit_chain(observed: RootAuthority, *, lstat) -> str:
        assert observed is authority
        assert callable(lstat)
        calls.append("chain")
        return observed.reviewed_anchor or tmp_path.anchor

    def observe_relative(path: str):
        assert Path(path) == tmp_path / "payload.bin"
        calls.append("relative")
        return SimpleNamespace(
            st_mode=stat_module.S_IFREG | 0o644,
            st_file_attributes=0,
            st_reparse_tag=0,
        )

    api = SimpleNamespace(
        sector_size=lambda _candidate: calls.append("sector") or 4096,
        open_file=lambda _candidate: calls.append("open") or 73,
        require_expected_final_path=(
            lambda _root, _relative, _handle: calls.append("final")
        ),
        stat=lambda _handle: calls.append("stat") or _stat(),
        close=lambda _handle: calls.append("close"),
    )

    monkeypatch.setattr(verifier_engine, "admit_root", admit_full)
    monkeypatch.setattr(verifier_native, "admit_root_chain", admit_chain)
    monkeypatch.setattr(
        verifier_native,
        "_verification_lstat",
        observe_relative,
    )
    monkeypatch.setattr(
        verifier_native,
        "_WindowsApi",
        lambda: calls.append("api") or api,
    )

    verifier_engine._admit_verification_root(tmp_path, context)
    explicit_reader = WindowsUnbufferedReader()
    reader = verifier_engine._reader_for_context(
        context,
        explicit_reader,
    )
    assert reader is explicit_reader
    with verifier_engine._open_reader(
        reader,
        tmp_path,
        "payload.bin",
        context,
    ):
        pass

    assert calls == [
        "full",
        "chain",
        "relative",
        "api",
        "sector",
        "open",
        "final",
        "stat",
        "close",
    ]


@pytest.mark.skipif(os.name != "nt", reason="Windows reader admission")
@pytest.mark.parametrize(
    ("relative_state", "expected_result", "expected_reason"),
    (
        (
            "missing",
            IntegrityResult.MISSING,
            IntegrityReason.NOT_FOUND,
        ),
        (
            "nondirectory",
            IntegrityResult.ERROR,
            IntegrityReason.READ_ERROR,
        ),
    ),
)
def test_native_reader_preserves_relative_admission_outcomes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_state: str,
    expected_result: IntegrityResult,
    expected_reason: IntegrityReason,
) -> None:
    authority = RootAuthority(str(tmp_path))
    context = replace(_context([]), root_authority=authority)
    item = _item(
        tmp_path,
        path=r"folder\payload.bin",
        baseline_evidence=None,
    )

    monkeypatch.setattr(verifier_engine, "admit_root", lambda _authority: None)
    monkeypatch.setattr(
        verifier_native,
        "admit_root_chain",
        lambda observed, **_kwargs: observed.reviewed_anchor or tmp_path.anchor,
    )

    relative_calls = 0

    def observe_relative(path: str):
        nonlocal relative_calls
        relative_calls += 1
        if relative_state == "missing":
            raise FileNotFoundError(2, "missing", path)
        if relative_calls == 2:
            raise NotADirectoryError(267, "not a directory", path)
        return SimpleNamespace(
            st_mode=stat_module.S_IFREG | 0o644,
            st_file_attributes=0,
            st_reparse_tag=0,
        )

    monkeypatch.setattr(
        verifier_native,
        "_verification_lstat",
        observe_relative,
    )
    monkeypatch.setattr(
        verifier_native,
        "_WindowsApi",
        lambda: pytest.fail("relative refusal reached Windows API setup"),
    )

    result = verify(
        IntegritySelection((item,)),
        context,
        _Recorder(),
        WindowsUnbufferedReader(),
    )

    assert result.outcomes[0].result is expected_result
    assert result.outcomes[0].reason is expected_reason


def test_valid_different_xxh3_digest_remains_a_hash_mismatch(tmp_path: Path) -> None:
    item = _item(tmp_path)
    recorder = _Recorder()

    result = verify(
        IntegritySelection((item,)),
        _context([]),
        recorder,
        _FakeReader(
            {item.display_path: _StreamSpec(item.expected_stat, (b"abd",))}  # type: ignore[arg-type]
        ),
    )

    assert result.outcomes[0].result is IntegrityResult.MISMATCHED
    assert result.outcomes[0].reason is IntegrityReason.HASH_MISMATCH
    assert recorder.commands == []
    assert len(recorder.invalidation_commands) == 1
    assert (
        recorder.invalidation_commands[0].reason
        is VerificationInvalidationReason.HASH_MISMATCH
    )


def test_wrong_length_hasher_digest_raises_contract_error_before_comparison(
    tmp_path: Path,
) -> None:
    class WrongLengthHasher:
        def update(self, data: bytes) -> None:
            del data

        def digest(self) -> bytes:
            return b"x" * 15

    item = _item(tmp_path)
    recorder = _Recorder()
    events: list[object] = []

    with pytest.raises(HasherContractError, match="exactly 16 bytes"):
        verify(
            IntegritySelection((item,)),
            _context(events, hasher_factory=WrongLengthHasher),
            recorder,
            _FakeReader(
                {item.display_path: _StreamSpec(item.expected_stat, (b"xyz",))}  # type: ignore[arg-type]
            ),
        )

    assert _integrity_events(events) == []
    assert recorder.commands == []


@pytest.mark.parametrize(
    ("mode", "runner", "baseline_evidence"),
    [
        (IntegrityMode.BASELINE, baseline, None),
        (IntegrityMode.VERIFY, verify, ...),
        (IntegrityMode.REBASELINE, rebaseline, ...),
    ],
)
def test_outcomes_carry_the_active_integrity_phase(
    tmp_path: Path,
    mode: IntegrityMode,
    runner,
    baseline_evidence: Attestation | None | object,
) -> None:
    item = _item(tmp_path, baseline_evidence=baseline_evidence)
    events: list[object] = []

    result = runner(
        IntegritySelection((item,)),
        replace(_context(events), progress_interval_seconds=0),
        _Recorder(),
        _FakeReader(
            {item.display_path: _StreamSpec(item.expected_stat, (b"abc",))}  # type: ignore[arg-type]
        ),
    )

    assert result.outcomes[0].phase == mode.value
    progress = [event for event in events if isinstance(event, Progress)]
    assert all(event.phase == mode.value for event in progress)
    assert [
        (
            event.item_id,
            event.item_type,
            event.item_bytes_done,
            event.item_bytes_total,
        )
        for event in progress
    ] == [
        (None, None, None, None),
        (item.item_id, "integrity", None, None),
        (item.item_id, "integrity", 0, item.expected_stat.size),  # type: ignore[union-attr]
        (
            item.item_id,
            "integrity",
            item.expected_stat.size,  # type: ignore[union-attr]
            item.expected_stat.size,  # type: ignore[union-attr]
        ),
        (None, None, None, None),
        (None, None, None, None),
    ]
    assert progress[0].current_path is None
    assert all(event.current_path == item.display_path for event in progress[1:])
    streamed = [
        event for event in progress if event.item_bytes_done is not None
    ]
    assert streamed[0].item_attempt_id is not None
    assert {event.item_attempt_id for event in streamed} == {
        streamed[0].item_attempt_id
    }
    assert progress[1].item_attempt_id is None
    assert progress[-1].item_attempt_id is None
    outcome_index = events.index(result.outcomes[0])
    assert events[outcome_index + 1] is progress[-2]
    assert events[-1] is progress[-1]


@pytest.mark.parametrize("recorded", (False, True))
def test_post_copy_progress_uses_operation_identity_and_clears_after_outcome(
    tmp_path: Path,
    recorded: bool,
) -> None:
    candidate = _post_copy_candidate(tmp_path, recorded=recorded)
    events: list[object] = []

    result = verify_post_copy(
        PostCopySelection((candidate,)),
        replace(_context(events), progress_interval_seconds=0),
        _Recorder(),
        _FakeReader(
            {
                candidate.display_path: _StreamSpec(
                    candidate.expected_stat, (b"abc",)
                )
            }
        ),
    )

    progress = [event for event in events if isinstance(event, Progress)]
    assert all(event.phase == IntegrityMode.VERIFY.value for event in progress)
    assert [
        (
            event.item_id,
            event.item_type,
            event.item_bytes_done,
            event.item_bytes_total,
        )
        for event in progress
    ] == [
        (None, None, None, None),
        (candidate.item_id, "operation", None, None),
        (candidate.item_id, "operation", 0, candidate.expected_stat.size),
        (
            candidate.item_id,
            "operation",
            candidate.expected_stat.size,
            candidate.expected_stat.size,
        ),
        (None, None, None, None),
        (None, None, None, None),
    ]
    assert result.outcomes[0].item_type == "integrity"
    assert progress[1].item_attempt_id is None
    assert progress[2].item_attempt_id is not None
    assert progress[2].item_attempt_id == progress[3].item_attempt_id
    assert progress[-1].item_attempt_id is None
    assert progress[0].current_path is None
    assert all(
        event.current_path == candidate.display_path for event in progress[1:]
    )
    outcome_index = events.index(result.outcomes[0])
    assert events[outcome_index + 1] is progress[-2]
    assert events[-1] is progress[-1]


def test_private_classifier_needs_no_ledger_identity_or_recorder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = _stat(size=8)
    path = "detached.bin"
    stream_totals: list[int] = []
    progress: list[int] = []

    def forbidden_command(*_args, **_kwargs):
        raise AssertionError("ledger command construction is not classification")

    monkeypatch.setattr(
        verifier_engine, "IntegrityRecordCommand", forbidden_command
    )
    classification = verifier_engine._classify_subject(
        root=tmp_path,
        relative_path=path,
        expected_stat=expected,
        baseline=None,
        mode=IntegrityMode.BASELINE,
        ctx=_context([]),
        reader=_FakeReader(
            {path: _StreamSpec(expected, (b"detached",), expected)}
        ),
        on_stream_start=stream_totals.append,
        on_bytes=progress.append,
    )

    assert classification.result is IntegrityResult.BASELINED
    assert classification.reason is None
    assert classification.bytes_read == 8
    assert classification.read_strategy is ReadStrategy.WINDOWS_UNBUFFERED
    assert classification.attestation is not None
    assert (
        classification.attestation.content.digest
        == xxh3_128(b"detached").digest()
    )
    assert stream_totals == [8]
    assert progress == [8]


def test_null_hash_verify_baselines_with_verify_provenance_atomically(
    tmp_path: Path,
) -> None:
    item = _item(tmp_path, baseline_evidence=None, reappeared=True)
    reader = _FakeReader(
        {item.display_path: _StreamSpec(item.expected_stat, (b"abc",))}  # type: ignore[arg-type]
    )
    recorder = _Recorder()

    result = verify(IntegritySelection((item,)), _context([]), recorder, reader)

    assert result.outcomes[0].result is IntegrityResult.BASELINED
    command = recorder.commands[0]
    assert command.mode is IntegrityMode.BASELINE
    assert command.attestation.content.provenance is Provenance.VERIFY_ATTESTED
    assert command.advances_last_verified is False
    assert command.clear_reappeared is True


def test_copy_evidence_advances_verification_only_after_independent_read(
    tmp_path: Path,
) -> None:
    stat = _stat()
    item = _item(
        tmp_path,
        expected_stat=stat,
        baseline_evidence=_attestation(b"abc", stat, Provenance.COPY_ATTESTED),
    )
    recorder = _Recorder()

    verify(
        IntegritySelection((item,)),
        _context([]),
        recorder,
        _FakeReader({item.display_path: _StreamSpec(stat, (b"abc",))}),
    )

    command = recorder.commands[0]
    assert command.expected_baseline.content.provenance is Provenance.COPY_ATTESTED
    assert command.attestation.content.provenance is Provenance.VERIFY_ATTESTED
    assert command.advances_last_verified is True


def test_post_copy_readback_classifies_without_a_ledger_identity(
    tmp_path: Path,
) -> None:
    candidate = _post_copy_candidate(tmp_path, recorded=False)
    selection = PostCopySelection((candidate,))
    recorder = _Recorder()

    result = verify_post_copy(
        selection,
        _context([]),
        recorder,
        _FakeReader(
            {
                candidate.display_path: _StreamSpec(
                    candidate.expected_stat, (b"abc",)
                )
            }
        ),
    )

    outcome = result.outcomes[0]
    assert outcome.result is IntegrityResult.VERIFIED
    assert outcome.row_id is None
    assert outcome.location_id is None
    assert outcome.recording is RecordingStatus.DEGRADED
    assert outcome.reason is IntegrityReason.RECORDING_ERROR
    assert outcome.detail == "copy evidence was not durably recorded"
    assert outcome.record_disposition is None
    assert result.recording is RecordingStatus.DEGRADED
    assert selection.completed_bytes == {candidate.item_id: 3}
    assert recorder.commands == []
    assert recorder.invalidation_commands == []


def test_post_copy_match_uses_readback_provenance_and_degrades_stale_recording(
    tmp_path: Path,
) -> None:
    candidate = _post_copy_candidate(tmp_path)
    recorder = _Recorder(RecordDisposition.STALE)

    result = verify_post_copy(
        PostCopySelection((candidate,)),
        _context([]),
        recorder,
        _FakeReader(
            {
                candidate.display_path: _StreamSpec(
                    candidate.expected_stat, (b"abc",)
                )
            }
        ),
    )

    outcome = result.outcomes[0]
    assert outcome.result is IntegrityResult.VERIFIED
    assert outcome.reason is IntegrityReason.RECORDING_STALE
    assert outcome.recording is RecordingStatus.DEGRADED
    assert outcome.record_disposition is RecordDisposition.STALE
    command = recorder.commands[0]
    assert command.expected_baseline is candidate.copy_attestation
    assert (
        command.attestation.content.provenance
        is Provenance.READBACK_ATTESTED
    )
    assert command.row_id == candidate.recorded_identity.row_id  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("live_stat", "content", "expected_result", "expected_reason"),
    [
        (
            _stat(mtime_ns=101),
            b"abd",
            IntegrityResult.MODIFIED,
            IntegrityReason.STAT_CHANGED,
        ),
        (
            _stat(),
            b"abd",
            IntegrityResult.MISMATCHED,
            IntegrityReason.HASH_MISMATCH,
        ),
    ],
)
def test_post_copy_stat_drift_precedes_stable_digest_mismatch(
    tmp_path: Path,
    live_stat: FileStat,
    content: bytes,
    expected_result: IntegrityResult,
    expected_reason: IntegrityReason,
) -> None:
    candidate = _post_copy_candidate(tmp_path)
    recorder = _Recorder()

    result = verify_post_copy(
        PostCopySelection((candidate,)),
        _context([]),
        recorder,
        _FakeReader(
            {
                candidate.display_path: _StreamSpec(
                    live_stat, (content,), live_stat
                )
            }
        ),
    )

    outcome = result.outcomes[0]
    assert outcome.result is expected_result
    assert outcome.reason is expected_reason
    assert recorder.commands == []
    assert len(recorder.invalidation_commands) == 1
    assert recorder.invalidation_commands[0].reason is (
        VerificationInvalidationReason.HASH_MISMATCH
        if expected_result is IntegrityResult.MISMATCHED
        else VerificationInvalidationReason.METADATA_DRIFT
    )


def test_post_copy_missing_subject_records_verification_invalidation(
    tmp_path: Path,
) -> None:
    candidate = _post_copy_candidate(tmp_path)
    recorder = _Recorder()

    result = verify_post_copy(
        PostCopySelection((candidate,)),
        _context([]),
        recorder,
        _FakeReader({candidate.display_path: FileNotFoundError("gone")}),
    )

    outcome = result.outcomes[0]
    assert outcome.result is IntegrityResult.MISSING
    assert outcome.reason is IntegrityReason.NOT_FOUND
    assert outcome.read_strategy is None
    assert len(recorder.invalidation_commands) == 1
    command = recorder.invalidation_commands[0]
    assert command.reason is VerificationInvalidationReason.METADATA_DRIFT
    assert command.row_id == candidate.recorded_identity.row_id  # type: ignore[union-attr]


def test_post_copy_unexpected_reader_exception_escapes_without_an_outcome(
    tmp_path: Path,
) -> None:
    candidate = _post_copy_candidate(tmp_path)
    selection = PostCopySelection((candidate,))
    events: list[object] = []

    with pytest.raises(RuntimeError, match="reader bug"):
        verify_post_copy(
            selection,
            _context(events),
            _Recorder(),
            _FakeReader({candidate.display_path: RuntimeError("reader bug")}),
        )

    assert _integrity_events(events) == []
    assert selection.completed_count == 0


def test_post_copy_pause_resume_preserves_completed_candidates_without_duplicates(
    tmp_path: Path,
) -> None:
    candidates = tuple(
        _post_copy_candidate(tmp_path, number=number, recorded=False)
        for number in range(1, 4)
    )
    selection = PostCopySelection(candidates)
    events: list[object] = []
    recorder = _Recorder()
    reader = _FakeReader(
        {
            candidate.display_path: _StreamSpec(
                candidate.expected_stat, (b"abc",)
            )
            for candidate in candidates
        }
    )

    def pause_after_one() -> None:
        if len(_integrity_events(events)) >= 1:
            raise PauseRequested

    with pytest.raises(PauseRequested):
        verify_post_copy(
            selection, _context(events, pause_after_one), recorder, reader
        )

    assert selection.completed_count == 1
    assert len(_integrity_events(events)) == 1
    paused_progress = [event for event in events if isinstance(event, Progress)]
    assert (
        paused_progress[-1].items_done,
        paused_progress[-1].item_id,
        paused_progress[-1].item_type,
        paused_progress[-1].item_bytes_done,
        paused_progress[-1].item_bytes_total,
    ) == (1, None, None, None, None)

    resumed = verify_post_copy(selection, _context(events), recorder, reader)

    outcomes = _integrity_events(events)
    assert len(outcomes) == len(candidates)
    assert len({outcome.item_id for outcome in outcomes}) == len(candidates)
    assert len(resumed.outcomes) == 2
    assert selection.completed_count == len(candidates)
    assert selection.processed_bytes == 9
    assert recorder.commands == []


def test_untrusted_filesystem_identity_is_not_promoted_from_reader_handle(
    tmp_path: Path,
) -> None:
    expected = _stat(identity=None)
    handle_stat = _stat(identity=FileIdentity("A1B2C3D4", 99))
    item = _item(
        tmp_path,
        expected_stat=expected,
        baseline_evidence=_attestation(b"abc", expected),
    )
    recorder = _Recorder()

    result = verify(
        IntegritySelection((item,)),
        _context([]),
        recorder,
        _FakeReader({item.display_path: _StreamSpec(handle_stat, (b"abc",))}),
    )

    assert result.outcomes[0].result is IntegrityResult.VERIFIED
    assert recorder.commands[0].attestation.subject.file_identity is None


def test_baseline_refuses_to_overwrite_established_evidence(tmp_path: Path) -> None:
    item = _item(tmp_path)
    reader = _FakeReader({})
    recorder = _Recorder()

    result = baseline(IntegritySelection((item,)), _context([]), recorder, reader)

    assert result.outcomes[0].result is IntegrityResult.ERROR
    assert result.outcomes[0].reason is IntegrityReason.BASELINE_EXISTS
    assert reader.opened == []
    assert recorder.commands == []


def test_rebaseline_accepts_fresh_current_stat_without_calling_it_verified(
    tmp_path: Path,
) -> None:
    old_stat = _stat(mtime_ns=100)
    current_stat = _stat(mtime_ns=200)
    item = _item(
        tmp_path,
        expected_stat=current_stat,
        baseline_evidence=_attestation(b"old", old_stat),
        reappeared=True,
    )
    recorder = _Recorder()

    result = rebaseline(
        IntegritySelection((item,)),
        _context([]),
        recorder,
        _FakeReader({item.display_path: _StreamSpec(current_stat, (b"new",))}),
    )

    assert result.outcomes[0].result is IntegrityResult.BASELINED
    command = recorder.commands[0]
    assert command.mode is IntegrityMode.REBASELINE
    assert command.expected_baseline.content.digest == xxh3_128(b"old").digest()
    assert command.advances_last_verified is False
    assert command.clear_reappeared is True


@pytest.mark.parametrize(
    ("entry", "expected", "reason"),
    [
        (FileNotFoundError("gone"), IntegrityResult.MISSING, IntegrityReason.NOT_FOUND),
        (
            UnsupportedVerification("no honest strategy"),
            IntegrityResult.UNSUPPORTED,
            IntegrityReason.UNSUPPORTED_READ,
        ),
        (OSError("read failed"), IntegrityResult.ERROR, IntegrityReason.READ_ERROR),
    ],
)
def test_missing_invalidates_while_unsupported_and_read_errors_do_not(
    tmp_path: Path,
    entry: BaseException,
    expected: IntegrityResult,
    reason: IntegrityReason,
) -> None:
    item = _item(tmp_path)
    recorder = _Recorder()
    events: list[object] = []

    result = verify(
        IntegritySelection((item,)),
        _context(events),
        recorder,
        _FakeReader({item.display_path: entry}),
    )

    assert result.outcomes[0].result is expected
    assert result.outcomes[0].reason is reason
    assert len(_integrity_events(events)) == 1
    assert recorder.commands == []
    assert len(recorder.invalidation_commands) == (
        1 if expected is IntegrityResult.MISSING else 0
    )
    if expected is IntegrityResult.MISSING:
        command = recorder.invalidation_commands[0]
        assert command.reason is VerificationInvalidationReason.METADATA_DRIFT
        assert command.expected_stat == item.expected_stat
        assert command.expected_baseline == item.baseline


def test_expected_missing_and_unsupported_rows_are_never_opened(tmp_path: Path) -> None:
    missing = _item(tmp_path, number=1, expected_state=InventoryState.MISSING)
    unsupported = _item(tmp_path, number=2, expected_state=InventoryState.UNSUPPORTED)
    reader = _FakeReader({})

    result = verify(
        IntegritySelection((missing, unsupported)),
        _context([]),
        _Recorder(),
        reader,
    )

    assert [outcome.result for outcome in result.outcomes] == [
        IntegrityResult.MISSING,
        IntegrityResult.UNSUPPORTED,
    ]
    assert reader.opened == []


def test_read_drift_records_verification_invalidation(tmp_path: Path) -> None:
    before = _stat()
    after = _stat(mtime_ns=101)
    item = _item(tmp_path, expected_stat=before)
    recorder = _Recorder()

    result = verify(
        IntegritySelection((item,)),
        _context([]),
        recorder,
        _FakeReader({item.display_path: _StreamSpec(before, (b"abc",), after)}),
    )

    assert result.outcomes[0].result is IntegrityResult.MODIFIED
    assert result.outcomes[0].reason is IntegrityReason.READ_DRIFT
    assert recorder.commands == []
    assert len(recorder.invalidation_commands) == 1
    assert (
        recorder.invalidation_commands[0].reason
        is VerificationInvalidationReason.METADATA_DRIFT
    )


def test_empty_subject_reports_a_bounded_zero_byte_stream(tmp_path: Path) -> None:
    stat = _stat(size=0)
    item = _item(
        tmp_path,
        expected_stat=stat,
        baseline_evidence=_attestation(b"", stat),
    )
    events: list[object] = []

    result = verify(
        IntegritySelection((item,)),
        replace(_context(events), progress_interval_seconds=0),
        _Recorder(),
        _FakeReader({item.display_path: _StreamSpec(stat, ())}),
    )

    assert result.outcomes[0].result is IntegrityResult.VERIFIED
    determinate = [
        event
        for event in events
        if isinstance(event, Progress)
        and event.item_id == item.item_id
        and event.item_bytes_done is not None
    ]
    assert [
        (event.item_bytes_done, event.item_bytes_total) for event in determinate
    ] == [(0, 0)]
    assert determinate[0].item_attempt_id is not None


def test_growing_subject_suppresses_item_fraction_and_expands_physical_total(
    tmp_path: Path,
) -> None:
    before = _stat(size=2)
    after = _stat(size=4)
    growing = _item(
        tmp_path,
        expected_stat=before,
        baseline_evidence=_attestation(b"ab", before),
    )
    pending_stat = _stat(size=5, identity=FileIdentity("A1B2C3D4", 8))
    pending = _item(
        tmp_path,
        number=2,
        expected_stat=pending_stat,
        baseline_evidence=_attestation(b"12345", pending_stat),
    )
    events: list[object] = []

    result = verify(
        IntegritySelection((growing, pending)),
        replace(_context(events), progress_interval_seconds=0),
        _Recorder(),
        _FakeReader(
            {
                growing.display_path: _StreamSpec(
                    before, (b"a", b"b", b"c", b"d"), after
                ),
                pending.display_path: _StreamSpec(
                    pending_stat, (b"12345",)
                ),
            }
        ),
    )

    assert [outcome.result for outcome in result.outcomes] == [
        IntegrityResult.MODIFIED,
        IntegrityResult.VERIFIED,
    ]
    assert result.outcomes[0].reason is IntegrityReason.READ_DRIFT
    growing_progress = [
        event
        for event in events
        if isinstance(event, Progress)
        and event.item_id == growing.item_id
    ]
    assert [
        (event.item_bytes_done, event.item_bytes_total)
        for event in growing_progress
    ] == [
        (None, None),
        (0, 2),
        (1, 2),
        (2, 2),
        (None, None),
        (None, None),
    ]
    overshoot = growing_progress[-1]
    streamed_attempt_id = growing_progress[1].item_attempt_id
    assert streamed_attempt_id is not None
    assert all(
        event.item_attempt_id == streamed_attempt_id
        for event in growing_progress[1:]
    )
    assert (
        overshoot.item_type,
        overshoot.bytes_done,
        overshoot.bytes_total,
    ) == ("integrity", 4, 9)

    progress = [event for event in events if isinstance(event, Progress)]
    assert [event.bytes_done for event in progress] == sorted(
        event.bytes_done for event in progress
    )
    assert all(event.bytes_done <= event.bytes_total for event in progress)
    assert (progress[-1].bytes_done, progress[-1].bytes_total) == (9, 9)

    outcome_index = events.index(result.outcomes[0])
    cleared = events[outcome_index + 1]
    assert isinstance(cleared, Progress)
    assert (
        cleared.item_id,
        cleared.item_type,
        cleared.item_attempt_id,
        cleared.item_bytes_done,
        cleared.item_bytes_total,
    ) == (None, None, None, None, None)


def test_resumed_overshoot_does_not_reapply_growth_to_retained_total(
    tmp_path: Path,
) -> None:
    before = _stat(size=2)
    after = _stat(size=4)
    item = _item(
        tmp_path,
        expected_stat=before,
        baseline_evidence=_attestation(b"ab", before),
    )
    selection = IntegritySelection(
        (item,),
        _processed_bytes=1,
        _bytes_total_high_water=100,
    )
    events: list[object] = []

    verify(
        selection,
        replace(_context(events), progress_interval_seconds=0),
        _Recorder(),
        _FakeReader(
            {
                item.display_path: _StreamSpec(
                    before,
                    (b"a", b"b", b"c", b"d"),
                    after,
                )
            }
        ),
    )

    progress = [event for event in events if isinstance(event, Progress)]
    assert progress
    assert all(event.bytes_total == 100 for event in progress)
    assert progress[-1].bytes_done == 5
    assert selection.bytes_total_high_water == 100


def test_integrity_selection_byte_total_high_water_is_monotonic() -> None:
    selection = IntegritySelection(())

    selection.advance_bytes_total_high_water(9)
    selection.advance_bytes_total_high_water(4)
    selection.note_bytes_processed(3)

    assert selection.bytes_total_high_water == 9
    with pytest.raises(ValueError, match="cannot trail processed"):
        selection.advance_bytes_total_high_water(2)
    with pytest.raises(TypeError, match="must be an integer"):
        selection.advance_bytes_total_high_water(True)  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        selection.bytes_total_high_water = 0  # type: ignore[misc]
    with pytest.raises(ValueError, match="cannot trail processed"):
        IntegritySelection(
            (),
            _processed_bytes=2,
            _bytes_total_high_water=1,
        )
    with pytest.raises(TypeError, match="must be an integer"):
        IntegritySelection((), _bytes_total_high_water=True)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    (
        "disposition",
        "error_detail",
        "expected_reason",
        "expected_detail",
        "expected_recording",
        "expected_disposition",
    ),
    (
        (
            RecordDisposition.APPLIED,
            None,
            IntegrityReason.READ_DRIFT,
            "classification detail",
            RecordingStatus.OK,
            RecordDisposition.APPLIED,
        ),
        (
            RecordDisposition.NOOP,
            None,
            IntegrityReason.READ_DRIFT,
            "classification detail",
            RecordingStatus.OK,
            RecordDisposition.NOOP,
        ),
        (
            RecordDisposition.STALE,
            None,
            IntegrityReason.RECORDING_STALE,
            None,
            RecordingStatus.DEGRADED,
            RecordDisposition.STALE,
        ),
        (
            RecordDisposition.CONFLICT,
            None,
            IntegrityReason.RECORDING_CONFLICT,
            None,
            RecordingStatus.DEGRADED,
            RecordDisposition.CONFLICT,
        ),
        (
            None,
            "OSError: sqlite unavailable",
            IntegrityReason.RECORDING_ERROR,
            "OSError: sqlite unavailable",
            RecordingStatus.DEGRADED,
            None,
        ),
    ),
    ids=("applied", "noop", "stale", "conflict", "error"),
)
def test_recording_settlement_reducer_is_pure_policy(
    disposition: RecordDisposition | None,
    error_detail: str | None,
    expected_reason: IntegrityReason,
    expected_detail: str | None,
    expected_recording: RecordingStatus,
    expected_disposition: RecordDisposition | None,
) -> None:
    settlement = verifier_engine._reduce_recording(
        verifier_engine._RecordingObservation(
            disposition=disposition,
            error_detail=error_detail,
        ),
        reason=IntegrityReason.READ_DRIFT,
        detail="classification detail",
    )

    assert settlement == verifier_engine._RecordingSettlement(
        expected_reason,
        expected_detail,
        expected_recording,
        expected_disposition,
    )


def test_negative_recording_error_preserves_modified_truth_and_degrades(
    tmp_path: Path,
) -> None:
    before = _stat()
    after = _stat(mtime_ns=101)
    item = _item(tmp_path, expected_stat=before)
    recorder = _Recorder(error=OSError("sqlite unavailable"))

    result = verify(
        IntegritySelection((item,)),
        _context([]),
        recorder,
        _FakeReader({item.display_path: _StreamSpec(before, (b"abc",), after)}),
    )

    outcome = result.outcomes[0]
    assert outcome.result is IntegrityResult.MODIFIED
    assert outcome.reason is IntegrityReason.RECORDING_ERROR
    assert outcome.detail == "OSError: sqlite unavailable"
    assert outcome.recording is RecordingStatus.DEGRADED
    assert outcome.record_disposition is None
    assert result.recording is RecordingStatus.DEGRADED
    assert len(recorder.invalidation_commands) == 1
    assert recorder.commands == []


def test_conditional_stale_recording_degrades_only_recording_axis(
    tmp_path: Path,
) -> None:
    item = _item(tmp_path)
    recorder = _Recorder(RecordDisposition.STALE)

    result = verify(
        IntegritySelection((item,)),
        _context([]),
        recorder,
        _FakeReader({item.display_path: _StreamSpec(item.expected_stat, (b"abc",))}),  # type: ignore[arg-type]
    )

    outcome = result.outcomes[0]
    assert outcome.result is IntegrityResult.VERIFIED
    assert outcome.recording is RecordingStatus.DEGRADED
    assert outcome.reason is IntegrityReason.RECORDING_STALE
    assert outcome.detail is None
    assert outcome.record_disposition is RecordDisposition.STALE
    assert result.recording is RecordingStatus.DEGRADED
    assert len(recorder.commands) == 1
    assert recorder.invalidation_commands == []


def test_canonical_key_validation_prevents_wrong_target_open(tmp_path: Path) -> None:
    item = replace(
        _item(tmp_path, path="Folder/File.bin"),
        rel_path_key=normalize_relative_path("Other/File.bin"),
    )
    reader = _FakeReader({})

    result = verify(
        IntegritySelection((item,)), _context([]), _Recorder(), reader
    )

    assert result.outcomes[0].reason is IntegrityReason.PATH_INVALID
    assert reader.opened == []


def test_same_canonical_path_in_two_locations_keeps_row_identity(tmp_path: Path) -> None:
    other_root = tmp_path / "other"
    item_1 = _item(tmp_path, number=1, path="Folder/File.bin", location_id="one")
    item_2 = _item(other_root, number=2, path="folder\\file.bin", location_id="two")
    reader = _FakeReader(
        {
            item_1.display_path: _StreamSpec(item_1.expected_stat, (b"abc",)),  # type: ignore[arg-type]
            item_2.display_path: _StreamSpec(item_2.expected_stat, (b"abc",)),  # type: ignore[arg-type]
        }
    )
    recorder = _Recorder()

    verify(
        IntegritySelection((item_1, item_2)), _context([]), recorder, reader
    )

    assert [(command.location_id, command.row_id) for command in recorder.commands] == [
        ("one", "row-1"),
        ("two", "row-2"),
    ]


@pytest.mark.parametrize("completed_before_cancel", [0, 1, 2])
def test_cancellation_emits_exactly_one_outcome_for_every_selected_row(
    tmp_path: Path, completed_before_cancel: int
) -> None:
    items = tuple(_item(tmp_path, number=number) for number in range(1, 4))
    events: list[object] = []

    def checkpoint() -> None:
        if len(_integrity_events(events)) >= completed_before_cancel:
            raise Canceled

    reader = _FakeReader(
        {
            item.display_path: _StreamSpec(item.expected_stat, (b"abc",))  # type: ignore[arg-type]
            for item in items
        }
    )
    selection = IntegritySelection(items)
    recorder = _Recorder()

    with pytest.raises(Canceled):
        verify(selection, _context(events, checkpoint), recorder, reader)

    outcomes = _integrity_events(events)
    assert len(outcomes) == len(items)
    assert len({outcome.item_id for outcome in outcomes}) == len(items)
    assert [outcome.result for outcome in outcomes[:completed_before_cancel]] == [
        IntegrityResult.VERIFIED
    ] * completed_before_cancel
    assert all(
        outcome.result is IntegrityResult.CANCELED
        for outcome in outcomes[completed_before_cancel:]
    )
    assert selection.completed_count == len(items)
    assert len(recorder.commands) == completed_before_cancel


def test_pause_resume_preserves_completed_rows_without_duplicates(tmp_path: Path) -> None:
    items = tuple(_item(tmp_path, number=number) for number in range(1, 4))
    events: list[object] = []

    def pause_after_one() -> None:
        if len(_integrity_events(events)) >= 1:
            raise PauseRequested

    reader = _FakeReader(
        {
            item.display_path: _StreamSpec(item.expected_stat, (b"abc",))  # type: ignore[arg-type]
            for item in items
        }
    )
    selection = IntegritySelection(items)
    recorder = _Recorder()

    with pytest.raises(PauseRequested):
        verify(selection, _context(events, pause_after_one), recorder, reader)
    assert selection.completed_count == 1
    assert len(_integrity_events(events)) == 1
    paused_progress = [event for event in events if isinstance(event, Progress)]
    assert (
        paused_progress[-1].items_done,
        paused_progress[-1].item_id,
        paused_progress[-1].item_type,
        paused_progress[-1].item_bytes_done,
        paused_progress[-1].item_bytes_total,
    ) == (1, None, None, None, None)

    resumed = verify(selection, _context(events), recorder, reader)

    outcomes = _integrity_events(events)
    assert len(outcomes) == len(items)
    assert len({outcome.item_id for outcome in outcomes}) == len(items)
    assert len(resumed.outcomes) == 2
    assert selection.completed_count == len(items)
    assert len(recorder.commands) == len(items)


def test_cancellation_during_hash_marks_in_flight_item_canceled(tmp_path: Path) -> None:
    item = _item(tmp_path)
    calls = 0
    events: list[object] = []

    def checkpoint() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:  # entry, first chunk, then cancel on the second chunk
            raise Canceled

    selection = IntegritySelection((item,))
    recorder = _Recorder()

    with pytest.raises(Canceled):
        verify(
            selection,
            replace(
                _context(events, checkpoint), progress_interval_seconds=0
            ),
            recorder,
            _FakeReader(
                {
                    item.display_path: _StreamSpec(
                        item.expected_stat, (b"a", b"b", b"c")  # type: ignore[arg-type]
                    )
                }
            ),
        )

    outcomes = _integrity_events(events)
    assert [outcome.result for outcome in outcomes] == [IntegrityResult.CANCELED]
    assert selection.completed_count == 1
    assert selection.processed_bytes == 1
    assert recorder.commands == []
    outcome_index = events.index(outcomes[0])
    active_before_outcome = [
        event
        for event in events[:outcome_index]
        if isinstance(event, Progress) and event.item_id == item.item_id
    ]
    assert (
        active_before_outcome[-1].item_bytes_done,
        active_before_outcome[-1].item_bytes_total,
    ) == (1, 3)
    assert outcome_index < len(events) - 1
    final_progress = events[-1]
    assert isinstance(final_progress, Progress)
    assert (
        final_progress.item_id,
        final_progress.item_type,
        final_progress.item_attempt_id,
        final_progress.item_bytes_done,
        final_progress.item_bytes_total,
    ) == (None, None, None, None, None)
    assert final_progress.current_path is None
    assert (final_progress.bytes_done, final_progress.bytes_total) == (1, 3)


def test_post_copy_cancellation_clears_progress_after_reliable_outcome(
    tmp_path: Path,
) -> None:
    candidate = _post_copy_candidate(tmp_path, recorded=False)
    selection = PostCopySelection((candidate,))
    events: list[object] = []
    calls = 0

    def checkpoint() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise Canceled

    with pytest.raises(Canceled):
        verify_post_copy(
            selection,
            replace(
                _context(events, checkpoint), progress_interval_seconds=0
            ),
            _Recorder(),
            _FakeReader(
                {
                    candidate.display_path: _StreamSpec(
                        candidate.expected_stat, (b"a", b"b", b"c")
                    )
                }
            ),
        )

    outcomes = _integrity_events(events)
    assert [outcome.result for outcome in outcomes] == [IntegrityResult.CANCELED]
    final_progress = events[-1]
    assert events.index(outcomes[0]) < len(events) - 1
    assert isinstance(final_progress, Progress)
    assert (
        final_progress.item_id,
        final_progress.item_type,
        final_progress.item_attempt_id,
        final_progress.item_bytes_done,
        final_progress.item_bytes_total,
    ) == (None, None, None, None, None)
    assert final_progress.current_path is None
    assert (final_progress.bytes_done, final_progress.bytes_total) == (1, 3)


def test_pause_during_hash_restarts_pending_item_without_outcome_or_progress_regression(
    tmp_path: Path,
) -> None:
    item = _item(tmp_path)
    calls = 0
    events: list[object] = []

    def checkpoint() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise PauseRequested

    selection = IntegritySelection((item,))
    recorder = _Recorder()
    reader = _FakeReader(
        {
            item.display_path: _StreamSpec(
                item.expected_stat, (b"a", b"b", b"c")  # type: ignore[arg-type]
            )
        }
    )

    with pytest.raises(PauseRequested):
        verify(
            selection,
            replace(
                _context(events, checkpoint), progress_interval_seconds=0
            ),
            recorder,
            reader,
        )

    assert _integrity_events(events) == []
    assert selection.completed_count == 0
    assert selection.processed_bytes == 1
    assert recorder.commands == []
    paused_progress = [event for event in events if isinstance(event, Progress)]
    paused_attempt_id = paused_progress[-1].item_attempt_id
    assert paused_attempt_id is not None
    assert {
        event.item_attempt_id
        for event in paused_progress
        if event.item_attempt_id is not None
    } == {paused_attempt_id}
    assert (
        paused_progress[-1].item_id,
        paused_progress[-1].item_type,
        paused_progress[-1].item_bytes_done,
        paused_progress[-1].item_bytes_total,
    ) == (item.item_id, "integrity", 1, 3)

    resume_start = len(events)
    result = verify(
        selection,
        replace(_context(events), progress_interval_seconds=0),
        recorder,
        reader,
    )

    assert result.outcomes[0].result is IntegrityResult.VERIFIED
    assert len(_integrity_events(events)) == 1
    progress = [event for event in events if isinstance(event, Progress)]
    assert [event.bytes_done for event in progress] == sorted(
        event.bytes_done for event in progress
    )
    resumed_determinate = [
        event
        for event in events[resume_start:]
        if isinstance(event, Progress)
        and event.item_id == item.item_id
        and event.item_bytes_done is not None
    ]
    assert resumed_determinate[0].item_attempt_id != paused_attempt_id
    assert len({event.item_attempt_id for event in resumed_determinate}) == 1
    assert (
        resumed_determinate[0].item_bytes_done,
        resumed_determinate[0].item_bytes_total,
        resumed_determinate[0].bytes_done,
        resumed_determinate[0].bytes_total,
    ) == (0, 3, 1, 4)
    assert [event.item_bytes_done for event in resumed_determinate] == [0, 1, 2, 3]
    assert selection.processed_bytes == 4
    assert len(recorder.commands) == 1


@pytest.mark.parametrize("post_copy", (False, True), ids=("standalone", "post-copy"))
def test_reader_resolution_failure_keeps_resumed_progress_authoritative(
    tmp_path: Path,
    post_copy: bool,
) -> None:
    events: list[object] = []
    if post_copy:
        subject = _post_copy_candidate(tmp_path)
        selection = PostCopySelection((subject,), _processed_bytes=1)
        invoke = lambda: verify_post_copy(
            selection,
            _context(events),
            _Recorder(),
        )
    else:
        subject = _item(tmp_path)
        selection = IntegritySelection(
            (subject,),
            _processed_bytes=1,
            _bytes_total_high_water=1,
        )
        invoke = lambda: verify(
            selection,
            _context(events),
            _Recorder(),
        )

    with pytest.raises(
        ValueError, match="default verification reader requires root authority"
    ):
        invoke()

    progress = [event for event in events if isinstance(event, Progress)]
    assert len(progress) == 2
    assert all(
        (event.items_done, event.items_total, event.bytes_done, event.bytes_total)
        == (0, 1, 1, 4)
        for event in progress
    )
    assert all(
        event.item_id is None and event.current_path is None
        for event in progress
    )


@pytest.mark.parametrize("post_copy", (False, True), ids=("standalone", "post-copy"))
def test_unexpected_failure_forces_live_inactive_progress(
    tmp_path: Path,
    post_copy: bool,
) -> None:
    events: list[object] = []
    calls = 0
    original = RuntimeError("reader pipeline bug")

    def checkpoint() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:  # item entry, first chunk, then fail before chunk two
            raise original

    context = _context(events, checkpoint, monotonic=lambda: 0.0)
    if post_copy:
        subject = _post_copy_candidate(tmp_path)
        selection = PostCopySelection((subject,))
        invoke = lambda: verify_post_copy(
            selection,
            context,
            _Recorder(),
            _FakeReader(
                {
                    subject.display_path: _StreamSpec(
                        subject.expected_stat, (b"a", b"b", b"c")
                    )
                }
            ),
        )
        expected_type = "operation"
    else:
        subject = _item(tmp_path)
        selection = IntegritySelection((subject,))
        invoke = lambda: verify(
            selection,
            context,
            _Recorder(),
            _FakeReader(
                {
                    subject.display_path: _StreamSpec(
                        subject.expected_stat, (b"a", b"b", b"c")  # type: ignore[arg-type]
                    )
                }
            ),
        )
        expected_type = "integrity"

    with pytest.raises(RuntimeError) as raised:
        invoke()

    assert raised.value is original
    assert _integrity_events(events) == []
    assert selection.completed_count == 0
    assert selection.processed_bytes == 1
    active = [
        event
        for event in events
        if isinstance(event, Progress) and event.item_type == expected_type
    ]
    assert active == []  # all ordinary transitions stayed inside the throttle window
    final = events[-1]
    assert isinstance(final, Progress)
    assert final.phase == IntegrityMode.VERIFY.value
    assert (final.items_done, final.items_total) == (0, 1)
    assert (final.bytes_done, final.bytes_total) == (1, 3)
    assert (
        final.current_path,
        final.item_id,
        final.item_type,
        final.item_attempt_id,
        final.item_bytes_done,
        final.item_bytes_total,
    ) == (None, None, None, None, None, None)


@pytest.mark.parametrize("post_copy", (False, True), ids=("standalone", "post-copy"))
def test_unexpected_failure_keeps_terminal_progress_sink_failure_secondary(
    tmp_path: Path,
    post_copy: bool,
) -> None:
    events: list[object] = []
    calls = 0
    failure_started = False
    original = RuntimeError("primary verifier failure")

    def checkpoint() -> None:
        nonlocal calls, failure_started
        calls += 1
        if calls == 3:
            failure_started = True
            raise original

    def emit(body: object) -> None:
        events.append(body)
        if failure_started and isinstance(body, Progress):
            raise OSError("injected terminal progress sink failure")

    context = replace(
        _context(events, checkpoint, monotonic=lambda: 0.0),
        run=RunContext(emit, checkpoint),
    )
    if post_copy:
        subject = _post_copy_candidate(tmp_path)
        selection = PostCopySelection((subject,))
        invoke = lambda: verify_post_copy(
            selection,
            context,
            _Recorder(),
            _FakeReader(
                {
                    subject.display_path: _StreamSpec(
                        subject.expected_stat, (b"a", b"b", b"c")
                    )
                }
            ),
        )
    else:
        subject = _item(tmp_path)
        selection = IntegritySelection((subject,))
        invoke = lambda: verify(
            selection,
            context,
            _Recorder(),
            _FakeReader(
                {
                    subject.display_path: _StreamSpec(
                        subject.expected_stat, (b"a", b"b", b"c")  # type: ignore[arg-type]
                    )
                }
            ),
        )

    with pytest.raises(RuntimeError) as raised:
        invoke()

    assert raised.value is original
    assert any(
        "verifier terminal progress emission also failed" in note
        and "injected terminal progress sink failure" in note
        for note in getattr(original, "__notes__", ())
    )
    final = events[-1]
    assert isinstance(final, Progress)
    assert (final.bytes_done, final.bytes_total) == (1, 3)
    assert (
        final.current_path,
        final.item_id,
        final.item_type,
        final.item_attempt_id,
        final.item_bytes_done,
        final.item_bytes_total,
    ) == (None, None, None, None, None, None)


@pytest.mark.parametrize("post_copy", (False, True), ids=("standalone", "post-copy"))
def test_reliable_outcome_count_survives_continuation_update_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    post_copy: bool,
) -> None:
    events: list[object] = []
    original = RuntimeError("continuation update bug")
    if post_copy:
        subject = _post_copy_candidate(tmp_path)
        selection = PostCopySelection((subject,))
        invoke = lambda: verify_post_copy(
            selection,
            replace(_context(events), progress_interval_seconds=0),
            _Recorder(),
            _FakeReader(
                {
                    subject.display_path: _StreamSpec(
                        subject.expected_stat, (b"abc",)
                    )
                }
            ),
        )
    else:
        subject = _item(tmp_path, expected_state=InventoryState.MISSING)
        selection = IntegritySelection((subject,))
        invoke = lambda: verify(
            selection,
            replace(_context(events), progress_interval_seconds=0),
            _Recorder(),
            _FakeReader({}),
        )

    def fail_continuation_update(*_args) -> None:
        raise original

    monkeypatch.setattr(selection, "mark_completed", fail_continuation_update)

    with pytest.raises(RuntimeError) as raised:
        invoke()

    assert raised.value is original
    outcomes = _integrity_events(events)
    assert len(outcomes) == 1
    assert selection.completed_count == 0
    final = events[-1]
    assert isinstance(final, Progress)
    assert events.index(outcomes[0]) < len(events) - 1
    assert (final.items_done, final.items_total) == (1, 1)
    assert (
        final.current_path,
        final.item_id,
        final.item_type,
        final.item_attempt_id,
        final.item_bytes_done,
        final.item_bytes_total,
    ) == (None, None, None, None, None, None)


def test_failed_reliable_outcome_emit_does_not_advance_items_done(
    tmp_path: Path,
) -> None:
    item = _item(tmp_path, expected_state=InventoryState.MISSING)
    selection = IntegritySelection((item,))
    events: list[object] = []
    original = OSError("reliable outcome sink failure")

    def emit(body: object) -> None:
        events.append(body)
        if isinstance(body, IntegrityOutcome):
            raise original

    context = replace(
        _context(events),
        run=RunContext(emit, lambda: None),
        progress_interval_seconds=0,
    )

    with pytest.raises(OSError) as raised:
        verify(selection, context, _Recorder(), _FakeReader({}))

    assert raised.value is original
    assert selection.completed_count == 0
    final = events[-1]
    assert isinstance(final, Progress)
    assert (final.items_done, final.items_total) == (0, 1)
    assert final.item_id is None
    assert final.current_path is None


@pytest.mark.parametrize("post_copy", (False, True), ids=("standalone", "post-copy"))
@pytest.mark.parametrize("secondary_failure", (False, True), ids=("progress-ok", "progress-fails"))
def test_canceled_outcome_sink_failure_uses_inactive_failure_boundary(
    tmp_path: Path,
    post_copy: bool,
    secondary_failure: bool,
) -> None:
    events: list[object] = []
    calls = 0
    settlement_failed = False
    settlement_error = OSError("canceled outcome sink failure")

    def checkpoint() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise Canceled

    def emit(body: object) -> None:
        nonlocal settlement_failed
        events.append(body)
        if isinstance(body, IntegrityOutcome):
            settlement_failed = True
            raise settlement_error
        if secondary_failure and settlement_failed and isinstance(body, Progress):
            raise RuntimeError("secondary inactive Progress sink failure")

    context = replace(
        _context(events, checkpoint, monotonic=lambda: 0.0),
        run=RunContext(emit, checkpoint),
    )
    if post_copy:
        subject = _post_copy_candidate(tmp_path)
        selection = PostCopySelection((subject,))
        invoke = lambda: verify_post_copy(
            selection,
            context,
            _Recorder(),
            _FakeReader(
                {
                    subject.display_path: _StreamSpec(
                        subject.expected_stat, (b"a", b"b", b"c")
                    )
                }
            ),
        )
    else:
        subject = _item(tmp_path)
        selection = IntegritySelection((subject,))
        invoke = lambda: verify(
            selection,
            context,
            _Recorder(),
            _FakeReader(
                {
                    subject.display_path: _StreamSpec(
                        subject.expected_stat, (b"a", b"b", b"c")  # type: ignore[arg-type]
                    )
                }
            ),
        )

    with pytest.raises(OSError) as raised:
        invoke()

    assert raised.value is settlement_error
    notes = getattr(settlement_error, "__notes__", ())
    assert any(
        "verifier terminal progress emission also failed" in note
        and "secondary inactive Progress sink failure" in note
        for note in notes
    ) is secondary_failure
    assert selection.completed_count == 0
    final = events[-1]
    assert isinstance(final, Progress)
    assert (final.items_done, final.items_total) == (0, 1)
    assert (final.bytes_done, final.bytes_total) == (1, 3)
    assert (
        final.current_path,
        final.item_id,
        final.item_type,
        final.item_attempt_id,
        final.item_bytes_done,
        final.item_bytes_total,
    ) == (None, None, None, None, None, None)


def test_pause_during_hash_forces_latest_active_snapshot_under_throttle(
    tmp_path: Path,
) -> None:
    item = _item(tmp_path)
    selection = IntegritySelection((item,))
    events: list[object] = []
    calls = 0

    def checkpoint() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        verify(
            selection,
            _context(events, checkpoint, monotonic=lambda: 0.0),
            _Recorder(),
            _FakeReader(
                {
                    item.display_path: _StreamSpec(
                        item.expected_stat, (b"a", b"b", b"c")  # type: ignore[arg-type]
                    )
                }
            ),
        )

    progress = [event for event in events if isinstance(event, Progress)]
    assert _integrity_events(events) == []
    assert selection.completed_count == 0
    assert selection.processed_bytes == 1
    assert not any(event.item_bytes_done == 1 for event in progress[:-1])
    assert (
        progress[-1].item_id,
        progress[-1].item_bytes_done,
        progress[-1].item_bytes_total,
        progress[-1].bytes_done,
        progress[-1].bytes_total,
    ) == (item.item_id, 1, 3, 1, 3)
    assert progress[-1].current_path == item.display_path
    assert events[-1] is progress[-1]


def test_post_copy_pause_forces_latest_active_snapshot_under_throttle(
    tmp_path: Path,
) -> None:
    candidate = _post_copy_candidate(tmp_path, recorded=False)
    selection = PostCopySelection((candidate,))
    events: list[object] = []
    calls = 0

    def checkpoint() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        verify_post_copy(
            selection,
            _context(events, checkpoint, monotonic=lambda: 0.0),
            _Recorder(),
            _FakeReader(
                {
                    candidate.display_path: _StreamSpec(
                        candidate.expected_stat, (b"a", b"b", b"c")
                    )
                }
            ),
        )

    progress = [event for event in events if isinstance(event, Progress)]
    assert _integrity_events(events) == []
    assert selection.completed_count == 0
    assert selection.processed_bytes == 1
    assert not any(event.item_bytes_done == 1 for event in progress[:-1])
    assert (
        progress[-1].item_id,
        progress[-1].item_bytes_done,
        progress[-1].item_bytes_total,
        progress[-1].bytes_done,
        progress[-1].bytes_total,
    ) == (candidate.item_id, 1, 3, 1, 3)
    assert progress[-1].current_path == candidate.display_path
    assert events[-1] is progress[-1]


def test_runner_aggregates_typed_integrity_outcomes_on_cancel(tmp_path: Path) -> None:
    items = (_item(tmp_path, number=1), _item(tmp_path, number=2))
    selection = IntegritySelection(items)
    published: list[OperationResult] = []
    emitted: list[object] = []
    settled: list[tuple[SessionState, OperationResult | None]] = []

    def work(run_ctx: RunContext) -> OperationResult:
        verify(
            selection,
            VerifierContext(
                run=run_ctx,
                clock=_Clock(),
                hasher_factory=xxh3_128,
                chunk_size=1,
            ),
            _Recorder(),
            _FakeReader({}),
        )
        raise AssertionError("cancellation must unwind before a workflow result")

    outcome = run_session(
        work,
        emit=emitted.append,
        checkpoint=lambda: (_ for _ in ()).throw(Canceled()),
        settle=lambda state, result: settled.append((state, result)),
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=published.append,
    )

    assert outcome.result is not None
    assert outcome.result.status is SessionState.CANCELED
    assert len(outcome.result.items) == len(items)
    assert all(isinstance(item, IntegrityOutcome) for item in outcome.result.items)
    assert [item.result for item in outcome.result.items] == [
        IntegrityResult.CANCELED,
        IntegrityResult.CANCELED,
    ]
    assert len(published) == 1
    assert settled[-1][0] is SessionState.CANCELED


def test_runner_can_finalize_cancellation_after_partial_byte_progress(
    tmp_path: Path,
) -> None:
    item = _item(tmp_path)
    selection = IntegritySelection((item,))
    calls = 0

    def checkpoint() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise Canceled

    def work(run_ctx: RunContext) -> OperationResult:
        verify(
            selection,
            VerifierContext(
                run=run_ctx,
                clock=_Clock(),
                hasher_factory=xxh3_128,
                chunk_size=1,
                progress_interval_seconds=0,
            ),
            _Recorder(),
            _FakeReader(
                {
                    item.display_path: _StreamSpec(
                        item.expected_stat, (b"a", b"b", b"c")  # type: ignore[arg-type]
                    )
                }
            ),
        )
        raise AssertionError("cancellation must unwind")

    outcome = run_session(
        work,
        emit=lambda event: None,
        checkpoint=checkpoint,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
    )

    assert outcome.result is not None
    assert outcome.result.status is SessionState.CANCELED
    assert outcome.result.bytes_done == 1
    assert outcome.result.bytes_total == 3
    assert len(outcome.result.items) == 1


def test_runner_retains_verifier_outcomes_across_pause_then_cancel(
    tmp_path: Path,
) -> None:
    items = tuple(_item(tmp_path, number=number) for number in range(1, 4))
    selection = IntegritySelection(items)
    emitted: list[object] = []
    accumulated: list[object] = []
    recorder = _Recorder()
    reader = _FakeReader(
        {
            item.display_path: _StreamSpec(item.expected_stat, (b"abc",))  # type: ignore[arg-type]
            for item in items
        }
    )

    def work(run_ctx: RunContext) -> OperationResult:
        integrity = verify(
            selection,
            VerifierContext(
                run=run_ctx,
                clock=_Clock(),
                hasher_factory=xxh3_128,
                chunk_size=1,
            ),
            recorder,
            reader,
        )
        return OperationResult(
            status=SessionState.COMPLETED,
            recording=integrity.recording,
            items=integrity.outcomes,
            bytes_done=selection.processed_bytes,
            bytes_total=selection.processed_bytes,
        )

    def pause_after_one() -> None:
        if len(_integrity_events(emitted)) >= 1:
            raise PauseRequested

    paused = run_session(
        work,
        emit=emitted.append,
        checkpoint=pause_after_one,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
        item_accumulator=accumulated,
    )

    assert paused.paused is True
    assert len(accumulated) == 1
    assert selection.completed_count == 1

    canceled = run_session(
        work,
        emit=emitted.append,
        checkpoint=lambda: (_ for _ in ()).throw(Canceled()),
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
        item_accumulator=accumulated,
    )

    assert canceled.result is not None
    assert canceled.result.status is SessionState.CANCELED
    assert [item.result for item in canceled.result.items] == [
        IntegrityResult.VERIFIED,
        IntegrityResult.CANCELED,
        IntegrityResult.CANCELED,
    ]
    assert len({item.item_id for item in canceled.result.items}) == 3


@pytest.mark.parametrize("streamed", (False, True), ids=("nonstream", "stream"))
def test_fast_items_have_constant_progress_boundaries(
    tmp_path: Path,
    streamed: bool,
) -> None:
    expected_state = (
        InventoryState.PRESENT if streamed else InventoryState.MISSING
    )
    items = tuple(
        _item(tmp_path, number=number, expected_state=expected_state)
        for number in range(1, 21)
    )
    events: list[object] = []
    reader = _FakeReader(
        {
            item.display_path: _StreamSpec(item.expected_stat, (b"abc",))  # type: ignore[arg-type]
            for item in items
            if streamed
        }
    )

    result = verify(
        IntegritySelection(items),
        _context(events, monotonic=lambda: 0.0),
        _Recorder(),
        reader,
    )

    progress = [event for event in events if isinstance(event, Progress)]
    outcomes = _integrity_events(events)
    assert len(progress) == 2
    assert len(outcomes) == len(items)
    assert len(events) == len(items) + 2
    assert result.outcomes == tuple(outcomes)
    assert all(event.item_id is None for event in progress)
    assert (progress[0].items_done, progress[-1].items_done) == (0, len(items))
    assert events[0] is progress[0]
    assert events[-1] is progress[-1]


def test_fast_post_copy_items_have_constant_progress_boundaries(
    tmp_path: Path,
) -> None:
    candidates = tuple(
        _post_copy_candidate(tmp_path, number=number, recorded=False)
        for number in range(1, 21)
    )
    events: list[object] = []

    result = verify_post_copy(
        PostCopySelection(candidates),
        _context(events, monotonic=lambda: 0.0),
        _Recorder(),
        _FakeReader(
            {
                candidate.display_path: _StreamSpec(
                    candidate.expected_stat, (b"abc",)
                )
                for candidate in candidates
            }
        ),
    )

    progress = [event for event in events if isinstance(event, Progress)]
    outcomes = _integrity_events(events)
    assert len(progress) == 2
    assert len(outcomes) == len(candidates)
    assert len(events) == len(candidates) + 2
    assert result.outcomes == tuple(outcomes)
    assert all(event.item_id is None for event in progress)
    assert (progress[0].items_done, progress[-1].items_done) == (
        0,
        len(candidates),
    )
    assert events[0] is progress[0]
    assert events[-1] is progress[-1]


@pytest.mark.parametrize("post_copy", (False, True), ids=("standalone", "post-copy"))
def test_empty_successful_selection_has_two_inactive_progress_boundaries(
    post_copy: bool,
) -> None:
    events: list[object] = []
    context = _context(events, monotonic=lambda: 0.0)
    recorder = _Recorder()
    reader = _FakeReader({})

    if post_copy:
        result = verify_post_copy(
            PostCopySelection(()), context, recorder, reader
        )
    else:
        result = verify(IntegritySelection(()), context, recorder, reader)

    progress = [event for event in events if isinstance(event, Progress)]
    assert result.outcomes == ()
    assert _integrity_events(events) == []
    assert len(progress) == 2
    assert len(events) == 2
    assert all(
        (
            event.items_done,
            event.items_total,
            event.bytes_done,
            event.bytes_total,
            event.current_path,
            event.item_id,
            event.item_type,
            event.item_bytes_done,
            event.item_bytes_total,
        )
        == (0, 0, 0, 0, None, None, None, None, None)
        for event in progress
    )
    assert events[0] is progress[0]
    assert events[-1] is progress[-1]


def test_fast_chunk_flood_has_two_fixed_progress_boundaries(tmp_path: Path) -> None:
    data = b"x" * 100
    stat = _stat(size=len(data))
    item = _item(
        tmp_path,
        expected_stat=stat,
        baseline_evidence=_attestation(data, stat),
    )
    events: list[object] = []

    verify(
        IntegritySelection((item,)),
        _context(events, monotonic=lambda: 0.0),
        _Recorder(),
        _FakeReader(
            {item.display_path: _StreamSpec(stat, tuple(b"x" for _ in range(100)))}
        ),
    )

    progress = [event for event in events if isinstance(event, Progress)]
    assert len(progress) == 2
    assert [event.bytes_done for event in progress] == sorted(
        event.bytes_done for event in progress
    )
    assert progress[-1].bytes_done == len(data)
    assert all(event.item_id is None for event in progress)
    assert (progress[0].items_done, progress[-1].items_done) == (0, 1)
    assert events[0] is progress[0]
    assert events[-1] is progress[-1]


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length paths")
def test_verifier_error_detail_does_not_expose_native_prefix(
    tmp_path: Path,
) -> None:
    logical = tmp_path / ("a" * 90) / ("b" * 90) / ("c" * 90) / "file.bin"
    assert len(str(logical)) > 260
    native = verifier_native._extended_path(logical)
    detail = verifier_engine._error_detail(
        PermissionError(13, "denied", native)
    )

    assert detail.startswith("PermissionError:")
    assert "file.bin" in detail
    assert "\\\\?\\" not in detail
