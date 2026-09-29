"""Executor native filesystem acceptance and regression tests."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from contextvars import copy_context
from dataclasses import replace
import ctypes
import getpass
import os
from pathlib import Path
import stat as stat_module
import struct
import subprocess
import sys
import textwrap
from types import SimpleNamespace

import pytest
from xxhash import xxh3_128

import _executor_fixtures as executor_fixtures
import namisync.modules.executor.native as executor_module
import namisync.modules.executor.pipeline as executor_pipeline
import namisync.modules.executor.runtime as executor_runtime
import namisync.core.root_authority as root_authority_module
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.events import ItemOutcome
from namisync.core.execution import (
    CopyDigest,
    RecordedCopyIdentity,
    validated_run_id,
)
from namisync.core.models import (
    EntryKind,
    FileStat,
    IgnoreSet,
    Root,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import PathValidationError, to_extended_length_path
from namisync.core.planning import (
    OpId,
    OperationKind,
    PreservationPolicy,
)
from namisync.core.root_authority import FILE_ATTRIBUTE_OFFLINE, RootAuthority, RootHold
from namisync.core.session import Canceled, PauseRequested, RunContext, SessionState
from namisync.modules.executor import (
    NativeCopyBackend,
    NativeFileSystem,
    UnsafeExecutionPath,
    execute,
)
from namisync.modules.executor.pipeline import (
    _PREALLOCATION_THRESHOLD,
)
from namisync.modules.scanner import scan

from _executor_fixtures import (
    RUN_ID,
    FakeRecorder,
    _create_directory_reparse,
    _item_outcome,
    _operation,
    _plan,
    _policies,
    _recorder_names,
    _require_directory_reparse,
    _roots,
    _run,
    _sharing_violation,
    _xset,
)


def _create_probe_for_cache_test(link: Path, target: Path) -> None:
    if os.name == "nt":
        link.mkdir()
    else:
        link.symlink_to(target, target_is_directory=True)


def test_directory_reparse_capability_success_is_cached_per_volume_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target"
    first = tmp_path / "first"
    second = tmp_path / "second"
    target.mkdir()
    first.mkdir()
    second.mkdir()
    calls: list[tuple[Path, Path]] = []
    monkeypatch.setattr(
        executor_fixtures,
        "_DIRECTORY_REPARSE_CAPABLE_VOLUMES",
        set(),
    )
    monkeypatch.setattr(
        executor_fixtures,
        "_directory_reparse_volume_pair",
        lambda _link_parent, _target: (1, 2),
    )

    def create(link: Path, redirected: Path) -> None:
        calls.append((link, redirected))
        _create_probe_for_cache_test(link, redirected)

    monkeypatch.setattr(executor_fixtures, "_create_directory_reparse", create)

    executor_fixtures._require_directory_reparse(first, target)
    executor_fixtures._require_directory_reparse(second, target)

    assert calls == [(first / "directory-reparse-probe", target)]


def test_directory_reparse_capability_distinguishes_volume_pairs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target"
    first = tmp_path / "first"
    second = tmp_path / "second"
    target.mkdir()
    first.mkdir()
    second.mkdir()
    calls: list[Path] = []
    monkeypatch.setattr(
        executor_fixtures,
        "_DIRECTORY_REPARSE_CAPABLE_VOLUMES",
        set(),
    )
    monkeypatch.setattr(
        executor_fixtures,
        "_directory_reparse_volume_pair",
        lambda link_parent, _target: (hash(link_parent.name), 2),
    )

    def create(link: Path, redirected: Path) -> None:
        calls.append(link)
        _create_probe_for_cache_test(link, redirected)

    monkeypatch.setattr(executor_fixtures, "_create_directory_reparse", create)

    executor_fixtures._require_directory_reparse(first, target)
    executor_fixtures._require_directory_reparse(second, target)

    assert calls == [
        first / "directory-reparse-probe",
        second / "directory-reparse-probe",
    ]


def test_directory_reparse_capability_failure_is_not_cached(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target"
    first = tmp_path / "first"
    second = tmp_path / "second"
    target.mkdir()
    first.mkdir()
    second.mkdir()
    calls: list[Path] = []
    monkeypatch.setattr(
        executor_fixtures,
        "_DIRECTORY_REPARSE_CAPABLE_VOLUMES",
        set(),
    )
    monkeypatch.setattr(
        executor_fixtures,
        "_directory_reparse_volume_pair",
        lambda _link_parent, _target: (1, 2),
    )

    def fail(link: Path, _redirected: Path) -> None:
        calls.append(link)
        raise OSError("unavailable")

    monkeypatch.setattr(executor_fixtures, "_create_directory_reparse", fail)

    with pytest.raises(pytest.skip.Exception, match="unavailable"):
        executor_fixtures._require_directory_reparse(first, target)
    with pytest.raises(pytest.skip.Exception, match="unavailable"):
        executor_fixtures._require_directory_reparse(second, target)

    assert calls == [
        first / "directory-reparse-probe",
        second / "directory-reparse-probe",
    ]


def test_native_filesystem_rejects_lexical_root_before_resolving_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = tmp_path / "configured-root"
    fs = NativeFileSystem()
    observed: list[Path] = []
    reject_reparse = fs._reject_reparse

    def fail_if_followed(_path: Path, *, strict: bool) -> Path:
        raise AssertionError("configured root was followed before rejection")

    def reject_root(path: Path) -> os.stat_result:
        observed.append(path)
        if path == configured:
            raise UnsafeExecutionPath("reparse points are not executable")
        return reject_reparse(path)

    monkeypatch.setattr(executor_module, "_resolved_logical_path", fail_if_followed)
    monkeypatch.setattr(fs, "_reject_reparse", reject_root)

    with pytest.raises(UnsafeExecutionPath, match="reparse points"):
        fs.resolve(configured, "file.bin", must_exist=False)

    assert observed[-1] == configured


@pytest.mark.parametrize(
    "custom_validation",
    ["none", "revalidate", "descendant-walk", "reparse-guard", "class-patched-guard"],
)
def test_native_resolve_keeps_physical_checks_without_default_confirmed_hold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    custom_validation: str,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    candidate = root / "missing.bin"

    class CustomValidationFileSystem(NativeFileSystem):
        def revalidate_root(self, root, *, trusted_anchor=None, expected_volume=None):
            return super().revalidate_root(
                root,
                trusted_anchor=trusted_anchor,
                expected_volume=expected_volume,
            )

    fs = (
        CustomValidationFileSystem()
        if custom_validation == "revalidate"
        else NativeFileSystem()
    )
    if custom_validation == "descendant-walk":
        original_walk = fs._validate_existing_chain
        monkeypatch.setattr(
            fs,
            "_validate_existing_chain",
            lambda root, path: original_walk(root, path),
        )
    elif custom_validation == "reparse-guard":
        original_guard = fs._reject_reparse
        monkeypatch.setattr(fs, "_reject_reparse", lambda path: original_guard(path))
    elif custom_validation == "class-patched-guard":
        original_guard = NativeFileSystem._reject_reparse
        monkeypatch.setattr(
            NativeFileSystem,
            "_reject_reparse",
            lambda self, path: original_guard(self, path),
        )
    resolutions: list[tuple[Path, bool]] = []
    original_resolve = executor_module._resolved_logical_path

    def resolve(path, *, strict):
        resolutions.append((Path(path), strict))
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(executor_module, "_resolved_logical_path", resolve)
    assert fs.resolve(root, "missing.bin", must_exist=False) == candidate
    assert resolutions == [(root, True), (candidate, False)]


def test_native_filesystem_revalidates_an_empty_chain_mount_anchor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = tmp_path / "mounted-root"
    configured.mkdir()
    fs = NativeFileSystem()
    monkeypatch.setattr(
        fs,
        "_observe_root_anchor",
        lambda _path: str(tmp_path),
    )
    monkeypatch.setattr(
        fs,
        "_observe_root_component",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("mismatched reviewed anchor must stop chain admission")
        ),
    )

    with pytest.raises(UnsafeExecutionPath, match="volume anchor changed"):
        fs.revalidate_root(configured, trusted_anchor=configured)


@pytest.mark.skipif(os.name != "nt", reason="native Windows root hold")
def test_native_invocation_hold_skips_physical_resolution_and_releases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "managed"
    root.mkdir()
    child = root / "child"
    child.mkdir()
    fs = NativeFileSystem()
    volume = fs._observe_root_volume(str(root))
    authority = RootAuthority(str(root), volume.evidence.device_id, volume.volume_id)
    state = executor_module._InvocationRoot("target", authority)
    diagnostics = []
    resolutions: list[Path] = []
    original_resolve = executor_module._resolved_logical_path

    def resolve(path, *, strict):
        resolutions.append(Path(path))
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(executor_module, "_resolved_logical_path", resolve)
    assert executor_module._WINDOWS is not None
    original_probe = executor_module._WINDOWS.get_volume_path
    probes = []

    def probe(*args):
        probes.append(args[0])
        return original_probe(*args)

    monkeypatch.setattr(executor_module._WINDOWS, "get_volume_path", probe)
    with executor_module._root_invocation_scope(fs, object(), (state,), diagnostics):
        for _ in range(2):
            fs.revalidate_root(root, trusted_anchor=Path(authority.reviewed_anchor),
                               expected_volume=volume.volume_id)
        assert state.held
        assert len(probes) == 1
        assert fs.resolve(root, "child", must_exist=True) == child
        assert resolutions == []
        with pytest.raises(FileNotFoundError):
            fs.resolve(root, "missing.bin", must_exist=True)
        assert resolutions == []
        original_lstat = Path.lstat
        native_child = to_extended_length_path(str(child))

        def lstat(path, *args, **kwargs):
            if str(path) == native_child:
                return SimpleNamespace(
                    st_mode=stat_module.S_IFLNK,
                    st_file_attributes=0,
                )
            return original_lstat(path, *args, **kwargs)

        monkeypatch.setattr(Path, "lstat", lstat)
        with pytest.raises(UnsafeExecutionPath, match="reparse points"):
            fs.resolve(root, "child", must_exist=True)
        assert resolutions == []
        monkeypatch.setattr(Path, "lstat", original_lstat)
        original_guard = NativeFileSystem._reject_reparse
        monkeypatch.setattr(
            NativeFileSystem,
            "_reject_reparse",
            lambda self, path: original_guard(self, path),
        )
        assert fs.resolve(root, "child", must_exist=True) == child
        assert resolutions == [root, child]
        resolutions.clear()
        monkeypatch.setattr(NativeFileSystem, "_reject_reparse", original_guard)
        fs._reject_reparse_chain(child)
        with pytest.raises(OSError) as refused:
            root.rename(tmp_path / "renamed")
        assert refused.value.winerror == 32
        (child / "allowed.bin").write_bytes(b"inside")
        (child / "allowed.bin").unlink()
        # Leaf volume evidence is still fresh; only the exact held root reuses it.
        assert fs._volume_id(child) == volume.volume_id
        assert len(probes) == 2
        assert fs._volume_id(root) == volume.volume_id
        assert len(probes) == 2
    assert not state.held
    assert len(diagnostics) == 1
    assert diagnostics[0].held and diagnostics[0].fallback_reason is None
    root.rename(tmp_path / "renamed")
    assert executor_module._ROOT_INVOCATION.get() is None


@pytest.mark.skipif(os.name != "nt", reason="native Windows held-root stat fast path")
def test_native_stat_composes_held_root_and_leaf_volume_fast_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "managed"
    root.mkdir()
    leaf = root / "leaf.bin"
    leaf.write_bytes(b"native held-root stat")
    fs = NativeFileSystem()
    expected = fs.stat_path(leaf)
    assert expected is not None and expected.kind is EntryKind.FILE
    assert expected.size == len(b"native held-root stat")
    volume = root_authority_module.observe_native_volume(root)
    if volume.volume_id.fs_type != "NTFS":
        pytest.skip("held leaf-volume stat witness requires NTFS")
    assert leaf.lstat().st_dev & 0xFFFFFFFF == int(volume.volume_id.serial, 16)
    scoped = executor_module._InvocationRoot(
        "target",
        RootAuthority(str(root), volume.evidence.device_id, volume.volume_id),
    )
    assert executor_module._WINDOWS is not None
    resolved_paths: list[Path] = []
    volume_paths: list[str] = []
    volume_information: list[str] = []
    original_resolve = executor_module._resolved_logical_path
    original_get_volume_path = executor_module._WINDOWS.get_volume_path
    original_get_volume_information = executor_module._WINDOWS.get_volume_information

    def resolve(path, *, strict):
        resolved_paths.append(Path(path))
        return original_resolve(path, strict=strict)

    def get_volume_path(path, *args):
        volume_paths.append(str(path))
        return original_get_volume_path(path, *args)

    def get_volume_information(path, *args):
        volume_information.append(str(path))
        return original_get_volume_information(path, *args)

    with executor_module._root_invocation_scope(fs, object(), (scoped,), None):
        fs.revalidate_root(root, expected_volume=volume.volume_id)
        assert scoped.held
        monkeypatch.setattr(executor_module, "_resolved_logical_path", resolve)
        monkeypatch.setattr(
            executor_module._WINDOWS, "get_volume_path", get_volume_path
        )
        monkeypatch.setattr(
            executor_module._WINDOWS,
            "get_volume_information",
            get_volume_information,
        )

        assert fs.stat(root, leaf.name) == expected
        assert resolved_paths == []
        assert volume_paths == []
        assert volume_information == []


def _reuse_held_root(fs, root, volume, selector):
    if selector == "revalidate":
        return fs.revalidate_root(root, expected_volume=volume.volume_id)
    if selector == "parent-chain":
        return fs._reject_reparse_chain(root)
    if selector == "leaf-stat":
        return fs.stat_path(root / "untouched.bin")
    if selector == "resolve":
        return fs.resolve(root, "untouched.bin", must_exist=False)
    return fs._volume_id(root)


@pytest.mark.skipif(os.name != "nt", reason="native Windows current root attributes")
@pytest.mark.parametrize(
    "selector", ("revalidate", "parent-chain", "volume", "leaf-stat", "resolve")
)
@pytest.mark.parametrize("state", ("ordinary", "placeholder", "query-failure"))
def test_held_root_reuse_requires_current_attributes_without_diagnostic_queries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selector: str,
    state: str,
) -> None:
    if selector == "leaf-stat":
        (tmp_path / "untouched.bin").write_bytes(b"checked leaf")
    volume = root_authority_module.observe_native_volume(tmp_path)
    authority = RootAuthority(str(tmp_path), volume.evidence.device_id, volume.volume_id)
    scoped = executor_module._InvocationRoot("target", authority)
    diagnostics = []
    fs = NativeFileSystem()
    assert root_authority_module._WINDOWS is not None
    original_query = root_authority_module._WINDOWS.get_file_information_ex
    queries: list[int] = []

    def query(handle, kind, output, size):
        queries.append(kind)
        assert kind == 0
        if state == "query-failure":
            ctypes.set_last_error(5)
            return False
        if state == "placeholder":
            info = ctypes.cast(output, ctypes.POINTER(root_authority_module._FileBasicInfo)).contents
            info.FileAttributes = 0x10 | 0x400 | FILE_ATTRIBUTE_OFFLINE
            return True
        return original_query(handle, kind, output, size)

    monkeypatch.setattr(root_authority_module._WINDOWS, "get_file_information_ex", query)
    with executor_module._root_invocation_scope(fs, object(), (scoped,), diagnostics):
        fs.revalidate_root(tmp_path, expected_volume=volume.volume_id)
        assert scoped.held
        assert len(diagnostics) == 1 and diagnostics[0].held
        assert queries == []
        descendants: list[Path] = []
        original_lstat = Path.lstat
        native_leaf = to_extended_length_path(str(tmp_path / "untouched.bin"))

        def observe_lstat(path, *args, **kwargs):
            if str(path) == native_leaf:
                descendants.append(tmp_path / "untouched.bin")
            return original_lstat(path, *args, **kwargs)

        monkeypatch.setattr(Path, "lstat", observe_lstat)
        if state == "ordinary":
            _reuse_held_root(fs, tmp_path, volume, selector)
            expected_descendants = (
                [tmp_path / "untouched.bin"]
                if selector in {"leaf-stat", "resolve"}
                else []
            )
            assert descendants == expected_descendants
        else:
            expected = (
                UnsafeExecutionPath if state == "placeholder" or selector == "parent-chain"
                else PermissionError
            )
            with pytest.raises(expected):
                _reuse_held_root(fs, tmp_path, volume, selector)
            if selector == "resolve":
                assert descendants == []
        assert queries == [0]
        assert scoped.held and len(diagnostics) == 1


@pytest.mark.skipif(os.name != "nt", reason="native NTFS in-place root conversion")
@pytest.mark.parametrize(
    "selector", ("revalidate", "parent-chain", "volume", "leaf-stat", "resolve")
)
def test_held_root_reuse_refuses_inplace_attribute_only_junction_conversion(
    tmp_path: Path,
    selector: str,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    sibling = tmp_path / "owned-sibling"
    sibling.mkdir()
    marker = sibling / "untouched.bin"
    marker.write_bytes(b"owned sibling unchanged")
    volume = root_authority_module.observe_native_volume(root)
    if volume.volume_id.fs_type != "NTFS":
        pytest.skip("native junction conversion witness requires NTFS")
    authority = RootAuthority(str(root), volume.evidence.device_id, volume.volume_id)
    scoped = executor_module._InvocationRoot("target", authority)
    fs = NativeFileSystem()
    ioctl = ctypes.WinDLL("kernel32", use_last_error=True).DeviceIoControl
    ioctl.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                      ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32),
                      ctypes.c_void_p]
    ioctl.restype = ctypes.c_int
    substitute = ("\\??\\" + str(sibling)).encode("utf-16-le")
    printed = str(sibling).encode("utf-16-le")
    paths = substitute + b"\0\0" + printed + b"\0\0"
    data = struct.pack("<LHHHHHH", 0xA0000003, 8 + len(paths), 0,
                       0, len(substitute), len(substitute) + 2, len(printed)) + paths
    assert executor_module._WINDOWS is not None
    with executor_module._root_invocation_scope(fs, object(), (scoped,), None):
        fs.revalidate_root(root, expected_volume=volume.volume_id)
        assert scoped.held
        handle = executor_module._WINDOWS.create_file(
            to_extended_length_path(str(root)), 0x100, 7, None, 3, 0x02200000, None
        )
        assert handle != executor_module._INVALID_HANDLE_VALUE
        converted = False
        try:
            buffer = ctypes.create_string_buffer(data)
            returned = ctypes.c_uint32()
            converted = bool(ioctl(handle, 0x900A4, buffer, len(data), None, 0,
                                   ctypes.byref(returned), None))
            assert converted, ctypes.get_last_error()
            assert root.lstat().st_file_attributes & 0x400
            with pytest.raises(UnsafeExecutionPath, match="reparse"):
                _reuse_held_root(fs, root, volume, selector)
            assert marker.read_bytes() == b"owned sibling unchanged"
        finally:
            try:
                if converted:
                    delete = ctypes.create_string_buffer(struct.pack("<LHH", 0xA0000003, 0, 0))
                    returned = ctypes.c_uint32()
                    assert ioctl(handle, 0x900AC, delete, 8, None, 0,
                                 ctypes.byref(returned), None), ctypes.get_last_error()
            finally:
                executor_module._WINDOWS.close_handle(handle)
        assert not root.lstat().st_file_attributes & 0x400
        assert fs.flush_directory(root)
    root.rename(tmp_path / "released-root")


@pytest.mark.skipif(os.name != "nt", reason="native Windows reparse guard")
@pytest.mark.parametrize("depth", (0, 1))
def test_held_root_parent_guard_refuses_first_and_deeper_descendant_reparse(
    tmp_path: Path,
    depth: int,
) -> None:
    root = tmp_path / "managed"
    root.mkdir()
    redirected = tmp_path / "redirected"
    redirected.mkdir()
    (redirected / "child").mkdir()
    marker = redirected / "child" / "untouched.bin"
    marker.write_bytes(b"no effects")
    _require_directory_reparse(tmp_path, redirected)
    parent = root
    if depth:
        parent = root / "ordinary"
        parent.mkdir()
    junction = parent / "link"
    _create_directory_reparse(junction, redirected)
    fs = NativeFileSystem()
    volume = fs._observe_root_volume(str(root))
    authority = RootAuthority(str(root), volume.evidence.device_id, volume.volume_id)
    state = executor_module._InvocationRoot("target", authority)
    with executor_module._root_invocation_scope(fs, object(), (state,), None):
        fs.revalidate_root(root, trusted_anchor=Path(authority.reviewed_anchor),
                           expected_volume=volume.volume_id)
        assert state.held
        # Invoke only the parent guard; no cleanup or filesystem effect is run.
        with pytest.raises(UnsafeExecutionPath, match="reparse points"):
            fs._reject_reparse_chain(junction / "child")
        assert marker.read_bytes() == b"no effects"


@contextmanager
def _path_cache_scope(monkeypatch: pytest.MonkeyPatch, fs=None):
    @contextmanager
    def unavailable_hold(authority):
        try:
            yield RootHold(authority, None, "unavailable")
        finally:
            invocation = executor_module._ROOT_INVOCATION.get()
            assert invocation is not None and not invocation.active
            assert invocation.root_paths == {} and invocation.last_win32_path is None

    monkeypatch.setattr(executor_module, "hold_root", unavailable_hold)
    roots = tuple(
        executor_module._InvocationRoot(role, RootAuthority(root, anchor))
        for role, root, anchor in (
            ("source", r"F:\Source", "F:\\"),
            ("target", r"G:\Target", "G:\\"),
        )
    )
    with executor_module._root_invocation_scope(
        NativeFileSystem() if fs is None else fs, object(), roots, None
    ):
        yield executor_module._ROOT_INVOCATION.get()


@pytest.mark.skipif(os.name != "nt", reason="native Windows pure path cache")
def test_native_path_cache_bounds_exact_spellings_and_keeps_last_nonroot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    win32_calls, lexical_calls = [], []
    original_win32 = executor_module.to_extended_length_path
    original_lexical = executor_module.lexical_absolute_path

    def win32(raw):
        win32_calls.append(raw)
        return original_win32(raw)

    def lexical(raw):
        lexical_calls.append(str(raw))
        return original_lexical(raw)

    monkeypatch.setattr(executor_module, "to_extended_length_path", win32)
    monkeypatch.setattr(executor_module, "lexical_absolute_path", lexical)
    pinned = (r"F:\Source", "F:\\", r"G:\Target", "G:\\")
    with _path_cache_scope(monkeypatch) as invocation:
        assert invocation.root_paths == {} and invocation.last_win32_path is None
        for raw in pinned:
            for _ in range(2):
                assert executor_module._win32_path(raw) == original_win32(raw)
                assert str(executor_module._lexical_logical_path(raw)) == original_lexical(raw)
        assert win32_calls == list(pinned) and lexical_calls == list(pinned)
        assert set(invocation.root_paths) == set(pinned)

        leaves = (
            r"\\server\share\leaf", r"\\?\F:\Source\leaf", r"f:\Source",
            "F:/Source", "F:\\" + "\\".join(["long-component"] * 24),
            *(f"F:\\Source\\leaf-{number}" for number in range(40)),
        )
        for raw in leaves:
            before = len(win32_calls)
            assert executor_module._win32_path(raw) == original_win32(raw)
            for root in pinned:
                executor_module._win32_path(root)
                executor_module._lexical_logical_path(root)
            assert executor_module._win32_path(raw) == original_win32(raw)
            assert len(win32_calls) == before + 1
            assert invocation.last_win32_path == (raw, original_win32(raw))
            assert len(invocation.root_paths) == 4
        raw = leaves[-1]
        before = len(lexical_calls)
        executor_module._lexical_logical_path(raw)
        executor_module._lexical_logical_path(raw)
        assert len(lexical_calls) == before + 2
        assert invocation.last_win32_path[0] == raw


def test_absolute_windows_cache_eligibility_is_a_plain_string_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        executor_module,
        "PureWindowsPath",
        lambda *_args, **_kwargs: pytest.fail("eligibility parsed a Windows path"),
    )
    for spelling in (
        r"F:\root", "F:/root", r"\\server\share", "//server/share",
        r"\\?\F:\root", r"\\?\UNC\server\share\root",
    ):
        assert executor_module._is_absolute_windows_spelling(spelling)
    for spelling in (
        "leaf", r"F:leaf", "F:", r"\root", r"\\server", "\\\\server\\",
    ):
        assert not executor_module._is_absolute_windows_spelling(spelling)


@pytest.mark.skipif(os.name != "nt", reason="Windows relative path/CWD policy")
@pytest.mark.parametrize("raw", ["leaf", "F:leaf", "\\leaf"])
def test_native_path_cache_bypasses_relative_forms_and_tracks_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    calls = []
    original = executor_module.to_extended_length_path
    monkeypatch.setattr(
        executor_module, "to_extended_length_path",
        lambda spelling: calls.append(spelling) or original(spelling),
    )
    with _path_cache_scope(monkeypatch) as invocation:
        for name in ("first", "second"):
            directory = tmp_path / name
            directory.mkdir()
            monkeypatch.chdir(directory)
            expected = original(raw)
            assert executor_module._win32_path(raw) == expected
            assert executor_module._win32_path(raw) == expected
        assert calls == [raw] * 4
        assert invocation.root_paths == {} and invocation.last_win32_path is None


@pytest.mark.skipif(os.name != "nt", reason="Windows success-only path cache")
def test_native_path_cache_does_not_store_failed_conversions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = executor_module.to_extended_length_path
    calls = []
    retry = r"F:\retry"

    def convert(raw):
        calls.append(raw)
        if raw == retry and calls.count(retry) == 1:
            raise PathValidationError("transient conversion fault")
        return original(raw)

    monkeypatch.setattr(executor_module, "to_extended_length_path", convert)
    with _path_cache_scope(monkeypatch) as invocation:
        previous = r"F:\previous"
        executor_module._win32_path(previous)
        stored = invocation.last_win32_path
        for _ in range(2):
            with pytest.raises(PathValidationError):
                executor_module._win32_path("F:\\bad\x00leaf")
            assert invocation.last_win32_path == stored
        with pytest.raises(PathValidationError, match="transient"):
            executor_module._win32_path(retry)
        assert invocation.last_win32_path == stored
        assert executor_module._win32_path(retry) == original(retry)
        assert executor_module._win32_path(retry) == original(retry)
        assert calls.count(retry) == 2 and calls.count("F:\\bad\x00leaf") == 2
        assert invocation.root_paths == {}


@pytest.mark.skipif(os.name != "nt", reason="native path cache lifetime")
def test_native_path_cache_restores_nested_scope_and_bypasses_retained_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    original = executor_module.to_extended_length_path
    monkeypatch.setattr(
        executor_module, "to_extended_length_path",
        lambda raw: calls.append(raw) or original(raw),
    )
    root, leaf = r"F:\Source", r"F:\Source\leaf"
    with _path_cache_scope(monkeypatch) as outer:
        outer_path = executor_module._lexical_logical_path(root)
        executor_module._win32_path(root)
        executor_module._win32_path(leaf)
        retained = copy_context()
        with _path_cache_scope(monkeypatch) as inner:
            assert inner is not outer and inner.root_paths == {}
            executor_module._win32_path(root)
            executor_module._win32_path(leaf)
        assert not inner.active and inner.root_paths == {} and inner.last_win32_path is None
        assert executor_module._ROOT_INVOCATION.get() is outer
        assert executor_module._lexical_logical_path(root) is outer_path
        before = len(calls)
        executor_module._win32_path(leaf)
        assert len(calls) == before
    assert not outer.active and outer.root_paths == {} and outer.last_win32_path is None
    before = len(calls)
    assert retained.run(executor_module._win32_path, root) == original(root)
    assert retained.run(executor_module._win32_path, root) == original(root)
    assert len(calls) == before + 2
    assert outer.root_paths == {} and outer.last_win32_path is None
    assert executor_module._ROOT_INVOCATION.get() is None


@pytest.mark.skipif(os.name != "nt", reason="native activation path cache")
def test_custom_adapter_without_native_activation_keeps_original_conversions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    original = executor_module.to_extended_length_path
    monkeypatch.setattr(
        executor_module, "to_extended_length_path",
        lambda raw: calls.append(raw) or original(raw),
    )
    with _path_cache_scope(monkeypatch, fs=object()) as invocation:
        for _ in range(2):
            executor_module._win32_path(r"F:\Source")
        assert calls == [r"F:\Source"] * 2
        assert invocation.root_paths == {} and invocation.last_win32_path is None


@pytest.mark.skipif(os.name != "nt", reason="native Windows root hold")
def test_native_invocation_mixes_held_and_fallback_without_sharing_adapter_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    source_volume = fs._observe_root_volume(str(source))
    target_volume = fs._observe_root_volume(str(target))
    roots = tuple(
        executor_module._InvocationRoot(
            role, RootAuthority(str(path), volume.evidence.device_id, volume.volume_id)
        )
        for role, path, volume in (
            ("source", source, source_volume), ("target", target, target_volume)
        )
    )
    original_hold = executor_module.hold_root

    @contextmanager
    def mixed_hold(authority):
        if authority.logical_root == str(target):
            yield RootHold(authority, None, "case_mismatch")
        else:
            with original_hold(authority) as hold:
                yield hold

    monkeypatch.setattr(executor_module, "hold_root", mixed_hold)
    admissions = []
    original_admit = fs._admit_reviewed_root

    def admit(authority):
        admissions.append(authority.logical_root)
        return original_admit(authority)

    monkeypatch.setattr(fs, "_admit_reviewed_root", admit)
    diagnostics = []
    with executor_module._root_invocation_scope(fs, object(), roots, diagnostics):
        for _ in range(2):
            for state in roots:
                authority = state.require_authority()
                fs.revalidate_root(Path(authority.logical_root),
                                   trusted_anchor=Path(authority.reviewed_anchor),
                                   expected_volume=authority.expected_volume_id)
        assert admissions == [str(source), str(target), str(target)]
        assert roots[0].held and not roots[1].held
        invocation = executor_module._ROOT_INVOCATION.get()
        assert {str(source), str(target)} <= set(invocation.root_paths)
        other = NativeFileSystem()
        # A different adapter still performs its own admission inside this scope.
        monkeypatch.setattr(other, "_admit_reviewed_root", admit)
        other.revalidate_root(source, expected_volume=source_volume.volume_id)
        assert admissions[-1] == str(source)
        assert len(admissions) == 4
    assert [(item.role, item.held, item.fallback_reason) for item in diagnostics] == [
        ("source", True, None), ("target", False, "case_mismatch")
    ]
    assert not roots[0].held
    assert executor_module._ROOT_INVOCATION.get() is None
    fs.revalidate_root(source, expected_volume=source_volume.volume_id)
    assert len(admissions) == 5


def test_native_filesystem_refuses_same_serial_with_different_filesystem(
    tmp_path: Path,
) -> None:
    fs = NativeFileSystem()
    actual = fs._volume_id(tmp_path)
    expected = VolumeId(
        actual.serial,
        "DIFFERENT" if actual.fs_type != "DIFFERENT" else "OTHER",
    )

    with pytest.raises(UnsafeExecutionPath, match="volume changed"):
        fs.revalidate_root(tmp_path, expected_volume=expected)


def test_native_filesystem_preserves_root_probe_order_and_volume_elision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fs = NativeFileSystem()
    reviewed_anchor = Path(fs._observe_root_anchor(str(tmp_path)))
    reviewed_volume = fs._observe_root_volume(str(tmp_path)).volume_id
    events: list[str] = []
    observe_anchor = fs._observe_root_anchor
    observe_component = fs._observe_root_component
    observe_volume = fs._observe_root_volume

    def anchor(path: str) -> str:
        events.append("anchor")
        return observe_anchor(path)

    def component(path: str) -> os.stat_result:
        events.append("component")
        return observe_component(path)

    def volume(path: str):
        events.append("volume")
        return observe_volume(path)

    monkeypatch.setattr(fs, "_observe_root_anchor", anchor)
    monkeypatch.setattr(fs, "_observe_root_component", component)
    monkeypatch.setattr(fs, "_observe_root_volume", volume)

    fs.revalidate_root(tmp_path, trusted_anchor=reviewed_anchor)

    assert events[0] == "anchor"
    assert events.count("anchor") == 1
    assert events.count("component") >= 1
    assert "volume" not in events

    events.clear()
    fs.revalidate_root(
        tmp_path,
        trusted_anchor=reviewed_anchor,
        expected_volume=reviewed_volume,
    )

    assert events[0] == "anchor"
    assert events.count("volume") == 1
    volume_index = events.index("volume")
    assert "component" in events[1:volume_index]
    if os.name == "nt":
        assert events[-1] == "volume"
        assert events.count("anchor") == 1


def test_native_filesystem_refuses_anchor_change_during_volume_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fs = NativeFileSystem()
    reviewed_anchor = Path(fs._observe_root_anchor(str(tmp_path)))
    reviewed_volume = fs._observe_root_volume(str(tmp_path))
    changed = replace(
        reviewed_volume,
        evidence=VolumeEvidence(device_id=str(tmp_path / "changed-anchor")),
    )
    monkeypatch.setattr(fs, "_observe_root_volume", lambda _path: changed)

    with pytest.raises(
        UnsafeExecutionPath,
        match="volume anchor changed before filesystem access",
    ):
        fs.revalidate_root(
            tmp_path,
            trusted_anchor=reviewed_anchor,
            expected_volume=reviewed_volume.volume_id,
        )


def test_native_filesystem_maps_invalid_reviewed_anchor_to_unsafe_path(
    tmp_path: Path,
) -> None:
    configured = tmp_path / "configured"
    unrelated = tmp_path / "unrelated"
    configured.mkdir()
    unrelated.mkdir()

    with pytest.raises(
        UnsafeExecutionPath,
        match="volume anchor changed before filesystem access",
    ):
        NativeFileSystem().revalidate_root(
            configured,
            trusted_anchor=unrelated,
        )


@pytest.mark.parametrize(
    ("mode", "attributes", "reparse_tag"),
    (
        pytest.param(
            stat_module.S_IFDIR,
            FILE_ATTRIBUTE_OFFLINE,
            0,
            id="offline-only",
        ),
        pytest.param(
            stat_module.S_IFDIR,
            0,
            0xA000000C,
            id="tag-only",
        ),
        pytest.param(
            stat_module.S_IFREG,
            0,
            0,
            id="regular-first-directory-second",
        ),
    ),
)
def test_native_filesystem_keeps_legacy_root_component_classification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: int,
    attributes: int,
    reparse_tag: int,
) -> None:
    fs = NativeFileSystem()
    reviewed_anchor = Path(fs._observe_root_anchor(str(tmp_path)))
    observed = SimpleNamespace(
        st_mode=mode,
        st_file_attributes=attributes,
        st_reparse_tag=reparse_tag,
    )
    monkeypatch.setattr(fs, "_reject_reparse", lambda _path: observed)

    fs.revalidate_root(tmp_path, trusted_anchor=reviewed_anchor)


def test_native_directory_flush_succeeds_on_target_ntfs(tmp_path: Path) -> None:
    _, target = _roots(tmp_path)

    assert NativeFileSystem().flush_directory(target)


@pytest.mark.skipif(os.name != "nt", reason="requires FileAllocationInfo")
def test_native_preallocation_keeps_logical_eof_and_exclusive_temp(
    tmp_path: Path,
) -> None:
    path = tmp_path / "allocated.tmp"
    fs = NativeFileSystem()

    with fs.create_temp(path, allocation_size=8 * 1024 * 1024) as stream:
        assert path.stat().st_size == 0
        stream.write(b"x")

    assert path.read_bytes() == b"x"
    with pytest.raises(FileExistsError):
        fs.create_temp(path, allocation_size=None)


@pytest.mark.skipif(os.name != "nt", reason="requires FileAllocationInfo")
@pytest.mark.parametrize(
    ("winerror", "falls_back"),
    [
        (1, True),
        (50, True),
        (87, False),
        (120, True),
        (5, False),
        (112, False),
        (1816, False),
        (9999, False),
    ],
)
def test_preallocation_falls_back_only_for_explicitly_unsupported_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    winerror: int,
    falls_back: bool,
) -> None:
    bindings = executor_module._WINDOWS
    assert bindings is not None
    monkeypatch.setattr(bindings, "set_file_information", lambda *_args: 0)
    monkeypatch.setattr(executor_module.ctypes, "get_last_error", lambda: winerror)
    path = tmp_path / f"allocation-{winerror}.tmp"
    fs = NativeFileSystem()

    if falls_back:
        with fs.create_temp(path, allocation_size=1024) as stream:
            stream.write(b"payload")
        assert path.read_bytes() == b"payload"
    else:
        with pytest.raises(OSError) as caught:
            fs.create_temp(path, allocation_size=1024)
        assert getattr(caught.value, "winerror", None) == winerror


@pytest.mark.skipif(os.name != "nt", reason="requires FileAllocationInfo")
@pytest.mark.parametrize(
    ("winerror", "expected_reason"),
    [
        (5, "io-error"),
        (87, "io-error"),
        (112, "disk-capacity"),
        (1816, "io-error"),
        (9999, "io-error"),
    ],
)
def test_substantive_preallocation_failure_cleans_temp_before_copying(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    winerror: int,
    expected_reason: str,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    source_path.write_bytes(b"")
    with source_path.open("r+b") as stream:
        stream.truncate(_PREALLOCATION_THRESHOLD)
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    backend = CountingCopyBackend()
    bindings = executor_module._WINDOWS
    assert bindings is not None
    monkeypatch.setattr(bindings, "set_file_information", lambda *_args: 0)
    monkeypatch.setattr(
        executor_module.ctypes, "get_last_error", lambda: winerror
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(
            copy_backend=backend,
            max_chunk_size=4 * 1024 * 1024,
        ),
    )

    assert result.status is SessionState.FAILED
    item = _item_outcome(_)
    assert item.reason == expected_reason
    assert backend.calls == 0
    assert recorder.calls == []
    assert not (target / "file.bin").exists()
    assert not list(target.glob("*.synctmp-*"))


@pytest.mark.skipif(os.name != "nt", reason="requires FileAllocationInfo")
@pytest.mark.parametrize("winerror", [1, 50, 120])
def test_unsupported_preallocation_falls_back_through_real_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    winerror: int,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    with source_path.open("wb") as stream:
        stream.truncate(_PREALLOCATION_THRESHOLD)
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    backend = CountingCopyBackend()
    bindings = executor_module._WINDOWS
    assert bindings is not None
    set_file_information = bindings.set_file_information

    def fail_allocation_only(
        handle,
        information_class,
        information,
        information_size,
    ):
        if information_class == executor_module._FILE_ALLOCATION_INFO_CLASS:
            return 0
        return set_file_information(
            handle,
            information_class,
            information,
            information_size,
        )

    monkeypatch.setattr(bindings, "set_file_information", fail_allocation_only)
    monkeypatch.setattr(
        executor_module.ctypes, "get_last_error", lambda: winerror
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(
            copy_backend=backend,
            max_chunk_size=4 * 1024 * 1024,
        ),
    )

    assert result.status is SessionState.COMPLETED
    assert backend.calls == 1
    assert (target / "file.bin").stat().st_size == _PREALLOCATION_THRESHOLD
    assert _recorder_names(recorder) == ["copied"]
    assert not list(target.glob("*.synctmp-*"))


@pytest.mark.skipif(os.name != "nt", reason="requires O_SEQUENTIAL")
def test_cached_source_open_uses_the_sequential_hint_and_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "source.bin"
    path.write_bytes(b"payload")
    observed_flags: list[int] = []
    real_open = executor_module.os.open

    def recording_open(path_value, flags, *args):
        observed_flags.append(flags)
        return real_open(path_value, flags, *args)

    monkeypatch.setattr(executor_module.os, "open", recording_open)
    with NativeFileSystem().open_source(path) as stream:
        descriptor = stream.fileno()
        assert stream.read() == b"payload"

    assert observed_flags[0] & os.O_SEQUENTIAL
    with pytest.raises(OSError):
        os.fstat(descriptor)


class FinalizationOrderFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.last_access_values: list[int] = []
        self.acl_applied = False
        self.writer_flushes = 0
        self.copied_descriptor: int | None = None

    def create_temp(self, path: Path, *, allocation_size: int | None):
        stream = super().create_temp(path, allocation_size=allocation_size)
        self.copied_descriptor = stream.fileno()
        self.calls.append("create")
        return stream

    def flush_file(self, stream) -> None:
        self.writer_flushes += 1
        super().flush_file(stream)

    def _open_metadata_handle(self, path: Path) -> int:
        if self.acl_applied:
            raise PermissionError("restrictive ACL would deny a later reopen")
        self.calls.append("open")
        return super()._open_metadata_handle(path)

    def copy_security(self, source: Path, target: Path) -> None:
        self.calls.append("acl")
        self.acl_applied = True

    def _set_basic_info(self, handle, basic) -> None:
        self.calls.append("basic")
        self.last_access_values.append(basic.LastAccessTime)
        super()._set_basic_info(handle, basic)

    def _flush_handle(self, handle) -> None:
        self.calls.append("flush")
        super()._flush_handle(handle)

    def _close_handle(self, handle) -> None:
        self.calls.append("close")
        super()._close_handle(handle)


@pytest.mark.skipif(os.name != "nt", reason="requires native copied-file handles")
@pytest.mark.parametrize("replace_existing", (False, True), ids=("copy", "update"))
@pytest.mark.parametrize("readonly", (False, True), ids=("ordinary", "readonly"))
def test_retained_copy_handle_publishes_and_closes_with_stable_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replace_existing: bool,
    readonly: bool,
) -> None:
    source = tmp_path / "source.bin"
    temp = tmp_path / "temp.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"payload")
    fs = NativeFileSystem()
    intended = fs.stat_path(source)
    assert intended is not None
    intended = replace(
        intended,
        mtime_ns=intended.mtime_ns - 4_000_000_000,
        metadata=replace(intended.metadata, attributes=1 if readonly else 0),
    )
    if replace_existing:
        target.write_bytes(b"displaced")
    with executor_module._root_invocation_scope(fs, object(), (), None):
        with fs.create_temp(temp, allocation_size=None) as writer:
            descriptor = writer.fileno()
            writer.write(b"payload")
        assert os.fstat(descriptor).st_size == len(b"payload")
        files = fs._copied_files()
        assert files is not None
        copied = files[temp]
        monkeypatch.setattr(
            fs, "_open_metadata_handle",
            lambda _path: pytest.fail("copied file reopened for metadata"),
        )
        monkeypatch.setattr(
            fs, "_stat_path",
            lambda _path: pytest.fail("copied file observed through its name"),
        )
        finalized = fs.finalize_temp(
            temp, intended, preserve_created=True, acl_source=None
        )
        publish = fs.replace if replace_existing else fs.publish_new
        publish(temp, target)
        assert files[target] is copied and temp not in files
        published = fs.ensure_published_metadata(
            target, finalized, intended,
            preserve_created=True, apply_readonly=True,
        )
        assert published.file_identity == finalized.file_identity
        assert files == {}
        with pytest.raises(OSError):
            os.fstat(descriptor)
    after_close = NativeFileSystem().stat_path(target)
    assert after_close == published
    assert target.read_bytes() == b"payload"
    if readonly:
        NativeFileSystem().clear_readonly(target)


@pytest.mark.skipif(os.name != "nt", reason="requires native copied-file handles")
def test_retained_copy_collision_preserves_handle_for_conditional_retry(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    temp = tmp_path / "temp.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"new")
    target.write_bytes(b"old")
    fs = NativeFileSystem()
    intended = fs.stat_path(source)
    assert intended is not None
    with executor_module._root_invocation_scope(fs, object(), (), None):
        with fs.create_temp(temp, allocation_size=None) as writer:
            descriptor = writer.fileno()
            writer.write(b"new")
        finalized = fs.finalize_temp(
            temp, intended, preserve_created=True, acl_source=None
        )
        files = fs._copied_files()
        assert files is not None
        copied = files[temp]
        with pytest.raises(FileExistsError):
            fs.publish_new(temp, target)
        assert files == {temp: copied}
        assert target.read_bytes() == b"old"
        with pytest.raises(PermissionError):
            temp.read_bytes()
        os.lseek(descriptor, 0, os.SEEK_SET)
        assert os.read(descriptor, 3) == b"new"
        fs.replace(temp, target)
        fs.ensure_published_metadata(
            target, finalized, intended, preserve_created=True, apply_readonly=True
        )
        with pytest.raises(OSError):
            os.fstat(descriptor)
    assert target.read_bytes() == b"new"


@pytest.mark.skipif(os.name != "nt", reason="requires native copied-file handles")
@pytest.mark.parametrize(
    "interruption", ("complete", "finalize", "publish", "observe", "pause", "cancel", "escape")
)
def test_native_copy_descriptors_retire_before_next_operation_or_invocation_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interruption: str,
) -> None:
    source, target = _roots(tmp_path)
    descriptors: list[list[object]] = []
    native_close = os.close

    def observe_close(descriptor: int) -> None:
        native_close(descriptor)
        for record in reversed(descriptors):
            if record == [descriptor, False]:
                with pytest.raises(OSError):
                    os.fstat(descriptor)
                record[1] = True
                break

    monkeypatch.setattr(os, "close", observe_close)

    class LifecycleFileSystem(NativeFileSystem):
        interrupt_stream = False
        failed = False

        def create_temp(self, path: Path, *, allocation_size: int | None):
            assert self._copied_files() == {}
            stream = super().create_temp(path, allocation_size=allocation_size)
            descriptors.append([stream.fileno(), False])
            self.interrupt_stream = interruption in {"pause", "cancel"}
            return stream

        def fail(self, stage: str) -> None:
            selected = "observe" if interruption == "escape" else interruption
            if not self.failed and selected == stage:
                self.failed = True
                raise OSError(f"injected {stage} failure")

        def finalize_temp(self, path: Path, *args, **kwargs) -> FileStat:
            self.fail("finalize")
            return super().finalize_temp(path, *args, **kwargs)

        def publish_new(self, temp: Path, target: Path) -> None:
            self.fail("publish")
            super().publish_new(temp, target)

        def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
            self.fail("observe")
            return super().ensure_published_metadata(path, *args, **kwargs)

    fs = LifecycleFileSystem()
    operations = []
    for index in (1, 2):
        name = f"file-{index}.bin"
        (source / name).write_bytes(b"payload")
        intended = fs.stat(source, name)
        assert intended is not None
        operations.append(_operation(
            index, OperationKind.COPY, source_rel_path=name, target_rel_path=name,
            source_expected=intended, target_expected=None, intended=intended,
        ))

    def checkpoint() -> None:
        if fs.interrupt_stream:
            fs.interrupt_stream = False
            raise PauseRequested() if interruption == "pause" else Canceled()

    class EscapingPolicy:
        def on_item_failed(self, *args):
            raise RuntimeError("injected policy escape")

    def run() -> None:
        _run(
            _xset(_plan(source, target, tuple(operations))), fs=fs,
            checkpoint=checkpoint,
            policies=_policies(failure=EscapingPolicy())
            if interruption == "escape" else _policies(),
        )

    if interruption in {"pause", "cancel", "escape"}:
        expected = {"pause": PauseRequested, "cancel": Canceled, "escape": RuntimeError}
        with pytest.raises(expected[interruption]):
            run()
        assert len(descriptors) == 1
    else:
        run()
        assert len(descriptors) == 2
    assert all(closed for _, closed in descriptors)


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_temp_finalization_holds_one_handle_before_acl_and_flushes_once(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    temp = tmp_path / "temp.bin"
    source.write_bytes(b"payload")
    temp.write_bytes(b"payload")
    fs = FinalizationOrderFileSystem()
    intended = fs.stat_path(source)
    assert intended is not None
    initial_temp = temp.stat(follow_symlinks=False)
    requested_access_ns = max(
        0, initial_temp.st_mtime_ns - 2_000_000_000
    )
    os.utime(
        temp,
        ns=(requested_access_ns, initial_temp.st_mtime_ns),
    )
    preserved_access_ns = temp.stat(follow_symlinks=False).st_atime_ns

    finalized = fs.finalize_temp(
        temp,
        intended,
        preserve_created=True,
        acl_source=source,
    )

    assert finalized.size == len(b"payload")
    assert fs.calls == ["open", "acl", "basic", "flush", "close"]
    assert fs.last_access_values == [0]
    assert temp.stat(follow_symlinks=False).st_atime_ns == preserved_access_ns


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_apply_metadata_changes_mtime_without_managing_atime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "metadata.bin"
    path.write_bytes(b"payload")
    fs = NativeFileSystem()
    observed = fs.stat_path(path)
    assert observed is not None
    requested_access_ns = max(0, observed.mtime_ns - 3_000_000_000)
    requested_mtime_ns = max(0, observed.mtime_ns - 1_000_000_000)
    os.utime(path, ns=(requested_access_ns, observed.mtime_ns))
    preserved_access_ns = path.stat(follow_symlinks=False).st_atime_ns
    bindings = executor_module._WINDOWS
    assert bindings is not None
    native_set_file_time = bindings.set_file_time
    access_arguments: list[object] = []

    def recording_set_file_time(
        handle,
        created,
        accessed,
        modified,
    ):
        access_arguments.append(accessed)
        return native_set_file_time(handle, created, accessed, modified)

    monkeypatch.setattr(
        bindings,
        "set_file_time",
        recording_set_file_time,
    )

    fs.apply_metadata(
        path,
        replace(observed, mtime_ns=requested_mtime_ns),
        preserve_created=False,
        apply_readonly=False,
    )

    after = path.stat(follow_symlinks=False)
    assert access_arguments == [None]
    assert after.st_atime_ns == preserved_access_ns
    assert after.st_mtime_ns == requested_mtime_ns


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_full_copy_has_no_writer_flush_and_finalizes_before_restrictive_acl(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"payload")
    fs = FinalizationOrderFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, _, recorder = _run(
        _xset(
            _plan(
                source,
                target,
                (operation,),
                preservation=PreservationPolicy(preserve_acl=True),
            )
        ),
        fs=fs,
    )

    assert result.status is SessionState.COMPLETED
    assert (target / "file.bin").read_bytes() == b"payload"
    assert fs.writer_flushes == 0
    assert fs.calls == ["create", "acl", "basic", "flush"]
    assert fs.copied_descriptor is not None
    with pytest.raises(OSError):
        os.fstat(fs.copied_descriptor)
    assert _recorder_names(recorder) == ["copied"]


class PublishedMetadataSpyFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.stat_calls = 0
        self.open_calls = 0
        self.flush_calls = 0

    def _stat_path(self, path: Path) -> FileStat | None:
        self.stat_calls += 1
        return super()._stat_path(path)

    def _open_metadata_handle(self, path: Path) -> int:
        self.open_calls += 1
        return super()._open_metadata_handle(path)

    def _flush_handle(self, handle) -> None:
        self.flush_calls += 1
        super()._flush_handle(handle)

    def reset_counts(self) -> None:
        self.stat_calls = 0
        self.open_calls = 0
        self.flush_calls = 0


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_atime_change_does_not_trigger_publish_repair_or_target_flush(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    temp = tmp_path / "temp.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"payload")
    temp.write_bytes(b"payload")
    fs = PublishedMetadataSpyFileSystem()
    intended = fs.stat_path(source)
    assert intended is not None
    finalized = fs.finalize_temp(
        temp, intended, preserve_created=True, acl_source=None
    )
    fs.publish_new(temp, target)
    changed_access_ns = max(0, finalized.mtime_ns - 1_000_000_000)
    os.utime(target, ns=(changed_access_ns, finalized.mtime_ns))
    before_access_ns = target.stat(follow_symlinks=False).st_atime_ns
    assert before_access_ns != finalized.mtime_ns
    fs.reset_counts()

    published = fs.ensure_published_metadata(
        target,
        finalized,
        intended,
        preserve_created=True,
        apply_readonly=True,
    )

    assert published.size == len(b"payload")
    assert fs.stat_calls == 1
    assert fs.open_calls == 0
    assert fs.flush_calls == 0
    assert target.stat(follow_symlinks=False).st_atime_ns == before_access_ns


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_deferred_readonly_repairs_once_and_returns_the_final_handle_stat(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    temp = tmp_path / "temp.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"payload")
    temp.write_bytes(b"payload")
    fs = PublishedMetadataSpyFileSystem()
    intended = fs.stat_path(source)
    assert intended is not None
    intended = replace(
        intended,
        metadata=replace(
            intended.metadata,
            attributes=intended.metadata.attributes | 0x1,
        ),
    )
    finalized = fs.finalize_temp(
        temp, intended, preserve_created=True, acl_source=None
    )
    assert not finalized.metadata.attributes & 0x1
    fs.publish_new(temp, target)
    fs.reset_counts()

    try:
        published = fs.ensure_published_metadata(
            target,
            finalized,
            intended,
            preserve_created=True,
            apply_readonly=True,
        )

        assert published.metadata.attributes & 0x1
        assert fs.stat_calls == 1
        assert fs.open_calls == 1
        assert fs.flush_calls == 1
    finally:
        fs.clear_readonly(target)


class PublishedRepairResultFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.returned_stat: FileStat | None = None
        self.repairs = 0

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        self.repairs += 1
        self.returned_stat = super().ensure_published_metadata(
            path, *args, **kwargs
        )
        return self.returned_stat


class NoRepairReuseFileSystem(NativeFileSystem):
    def __init__(self, published_path: Path) -> None:
        self.published_path = published_path
        self.comparison_stat: FileStat | None = None
        self.returned_stat: FileStat | None = None
        self.target_comparisons = 0
        self.target_metadata_opens = 0

    def _stat_path(self, path: Path) -> FileStat | None:
        result = super()._stat_path(path)
        if path == self.published_path and result is not None:
            self.target_comparisons += 1
            self.comparison_stat = result
        return result

    def _stat_handle(self, handle: int, basic=None) -> FileStat:
        result = super()._stat_handle(handle, basic)
        files = self._copied_files()
        copied = None if files is None else files.get(self.published_path)
        if copied is not None and copied.handle == handle:
            self.target_comparisons += 1
            self.comparison_stat = result
        return result

    def _open_metadata_handle(self, path: Path) -> int:
        if path == self.published_path:
            self.target_metadata_opens += 1
        return super()._open_metadata_handle(path)

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        result = super().ensure_published_metadata(path, *args, **kwargs)
        if path == self.published_path:
            assert result is self.comparison_stat
            self.returned_stat = result
        return result


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_clean_copy_reuses_exact_postpublish_comparison_stat_for_attestation(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    published_path = target / "file.bin"
    (source / "file.bin").write_bytes(b"clean-publish")
    fs = NoRepairReuseFileSystem(published_path)
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
    )

    _, _, attestation = recorder.calls[0]
    assert result.status is SessionState.COMPLETED
    assert fs.target_comparisons == 1
    assert fs.target_metadata_opens == 0
    assert fs.comparison_stat is fs.returned_stat
    assert attestation.subject is fs.returned_stat


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_copy_attests_to_exact_postpublish_repair_stat(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"post-repair")
    fs = PublishedRepairResultFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    intended = replace(
        source_stat,
        metadata=replace(
            source_stat.metadata,
            attributes=source_stat.metadata.attributes | 0x1,
        ),
    )
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=intended,
    )

    try:
        result, _, recorder = _run(
            _xset(_plan(source, target, (operation,))),
            fs=fs,
        )

        _, _, attestation = recorder.calls[0]
        assert result.status is SessionState.COMPLETED
        assert fs.repairs == 1
        assert fs.returned_stat is not None
        assert fs.returned_stat.metadata.attributes & 0x1
        assert attestation.subject is fs.returned_stat
    finally:
        published = target / "file.bin"
        if published.exists():
            fs.clear_readonly(published)


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_attribute_repair_preserves_atime_and_source_attributes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    temp = tmp_path / "temp.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"payload")
    temp.write_bytes(b"payload")
    fs = PublishedMetadataSpyFileSystem()
    intended = fs.stat_path(source)
    assert intended is not None
    intended = replace(
        intended,
        metadata=replace(
            intended.metadata,
            attributes=(
                intended.metadata.attributes
                | 0x1  # readonly
                | 0x2  # hidden
                | 0x4  # system
                | 0x2000  # not-content-indexed
            ),
            created_ns=None,
        ),
    )
    temp_created = fs.stat_path(temp)
    assert temp_created is not None
    finalized = fs.finalize_temp(
        temp, intended, preserve_created=True, acl_source=None
    )
    assert finalized.metadata.created_ns == temp_created.metadata.created_ns
    assert finalized.metadata.attributes & 0x2000
    assert not finalized.metadata.attributes & 0x1
    fs.publish_new(temp, target)
    before_repair = fs.stat_path(target)
    assert before_repair is not None
    wrong_access = max(0, finalized.mtime_ns - 1_000_000_000)
    os.utime(target, ns=(wrong_access, finalized.mtime_ns))
    before_access_ns = target.stat(follow_symlinks=False).st_atime_ns
    fs.reset_counts()

    try:
        published = fs.ensure_published_metadata(
            target,
            finalized,
            intended,
            preserve_created=True,
            apply_readonly=True,
        )
        target_info = target.stat(follow_symlinks=False)

        assert target_info.st_atime_ns == before_access_ns
        assert published.metadata.created_ns == before_repair.metadata.created_ns
        assert published.metadata.attributes & 0x1
        assert published.metadata.attributes & 0x2
        assert published.metadata.attributes & 0x4
        assert published.metadata.attributes & 0x2000
        assert fs.stat_calls == 1
        assert fs.open_calls == 1
        assert fs.flush_calls == 1
    finally:
        fs.clear_readonly(target)


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_name_tunneled_creation_and_readonly_repair_only_changed_fields(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    temp = tmp_path / "temp.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"payload")
    temp.write_bytes(b"payload")
    fs = PublishedMetadataSpyFileSystem()
    intended = fs.stat_path(source)
    assert intended is not None and intended.metadata.created_ns is not None
    intended = replace(
        intended,
        metadata=replace(
            intended.metadata,
            attributes=intended.metadata.attributes | 0x1,
        ),
    )
    finalized = fs.finalize_temp(
        temp, intended, preserve_created=True, acl_source=None
    )
    assert finalized.metadata.created_ns is not None
    assert not finalized.metadata.attributes & 0x1
    fs.publish_new(temp, target)
    fs._set_creation_time(
        target, max(0, finalized.metadata.created_ns - 1_000_000_000)
    )
    before = target.stat(follow_symlinks=False)
    before_attributes = fs._get_attributes(target)
    fs.reset_counts()

    try:
        published = fs.ensure_published_metadata(
            target,
            finalized,
            intended,
            preserve_created=True,
            apply_readonly=True,
        )
        after = target.stat(follow_symlinks=False)

        assert published.metadata.created_ns == finalized.metadata.created_ns
        assert published.metadata.attributes & 0x1
        assert after.st_mtime_ns == before.st_mtime_ns
        assert after.st_atime_ns == before.st_atime_ns
        assert (
            fs._get_attributes(target)
            == before_attributes | 0x1
        )
        assert fs.stat_calls == 1
        assert fs.open_calls == 1
        assert fs.flush_calls == 1
    finally:
        fs.clear_readonly(target)


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_normalized_timestamp_rounding_does_not_trigger_publish_repair(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    temp = tmp_path / "temp.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"payload")
    temp.write_bytes(b"payload")
    fs = PublishedMetadataSpyFileSystem()
    intended = fs.stat_path(source)
    assert intended is not None
    intended = replace(intended, mtime_ns=intended.mtime_ns + 37)
    finalized = fs.finalize_temp(
        temp, intended, preserve_created=True, acl_source=None
    )
    assert finalized.mtime_ns != intended.mtime_ns
    fs.publish_new(temp, target)
    fs.reset_counts()

    published = fs.ensure_published_metadata(
        target,
        finalized,
        intended,
        preserve_created=True,
        apply_readonly=True,
    )

    assert published.mtime_ns == finalized.mtime_ns
    assert fs.stat_calls == 1
    assert fs.open_calls == 0
    assert fs.flush_calls == 0


@pytest.mark.skipif(os.name != "nt", reason="requires Windows filename casing")
def test_native_atomic_replace_uses_requested_destination_casing(tmp_path: Path) -> None:
    _, target = _roots(tmp_path)
    existing = target / "keep.txt"
    replacement = target / "replacement.tmp"
    existing.write_bytes(b"old")
    replacement.write_bytes(b"new")

    NativeFileSystem().replace(replacement, target / "KEEP.txt")

    assert [path.name for path in target.iterdir()] == ["KEEP.txt"]
    assert (target / "KEEP.txt").read_bytes() == b"new"


class UnavailableDirectoryFlushFileSystem(NativeFileSystem):
    def flush_directory(self, path: Path) -> bool:
        return False


def test_unavailable_directory_flush_remains_an_honest_warning(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"content")
    fs = UnavailableDirectoryFlushFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, events, _ = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    item = _item_outcome(events)
    assert result.status is SessionState.COMPLETED
    assert item.detail["durability_warnings"] == (
        f"parent directory flush unsupported: {target}",
    )


@pytest.mark.skipif(os.name != "nt", reason="requires native durability handles")
def test_published_copy_metadata_survives_process_exit_after_record(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    payload = b"durable-before-record"
    source_path = source / "file.bin"
    source_path.write_bytes(payload)
    parent_fs = NativeFileSystem()
    source_stat = parent_fs.stat_path(source_path)
    assert source_stat is not None
    intended_mask = 0x1 | 0x2 | 0x2000
    parent_fs.apply_metadata(
        source_path,
        replace(
            source_stat,
            metadata=replace(
                source_stat.metadata,
                attributes=source_stat.metadata.attributes | intended_mask,
            ),
        ),
        preserve_created=True,
        apply_readonly=True,
    )
    source_stat = parent_fs.stat_path(source_path)
    assert source_stat is not None
    marker = tmp_path / "recorded.marker"
    child = textwrap.dedent(
        """
        import os
        from pathlib import Path
        import runpy
        import sys

        sys.path.insert(0, str(Path(sys.argv[1]).parent))
        ns = runpy.run_path(sys.argv[1])
        source = Path(sys.argv[2])
        target = Path(sys.argv[3])
        marker = Path(sys.argv[4])
        windows = ns["executor_module"]._WINDOWS
        if windows is None:
            os._exit(90)
        native_flush = windows.flush_file_buffers
        native_close = os.close
        handle_events = []
        copied_descriptors = {}

        def observe_native_flush(handle):
            handle_events.append(("native-flush", None, handle))
            return native_flush(handle)

        windows.flush_file_buffers = observe_native_flush

        def observe_descriptor_close(descriptor):
            native_close(descriptor)
            handle = copied_descriptors.pop(descriptor, None)
            if handle is not None:
                handle_events.append(("close", None, handle))

        os.close = observe_descriptor_close

        class FlushObservedFileSystem(ns["NativeFileSystem"]):
            def __init__(self):
                self.directory_flushed = False

            def create_temp(self, path, *, allocation_size):
                import msvcrt
                stream = super().create_temp(path, allocation_size=allocation_size)
                descriptor = stream.fileno()
                handle = msvcrt.get_osfhandle(descriptor)
                copied_descriptors[descriptor] = handle
                handle_events.append(("open", path, handle))
                return stream

            def publish_new(self, temp, target):
                files = self._copied_files()
                handle = files[temp].handle
                super().publish_new(temp, target)
                handle_events.append(("publish", target, handle))

            def _set_basic_info(self, handle, basic):
                handle_events.append(("basic", None, handle))
                return super()._set_basic_info(handle, basic)

            def flush_directory(self, path):
                result = super().flush_directory(path)
                self.directory_flushed = True
                return result

        fs = FlushObservedFileSystem()
        source_stat = fs.stat(source, "file.bin")
        if source_stat is None:
            os._exit(90)
        operation = ns["_operation"](
            1,
            ns["OperationKind"].COPY,
            source_rel_path="file.bin",
            target_rel_path="file.bin",
            source_expected=source_stat,
            target_expected=None,
            intended=source_stat,
        )

        class ExitAtRecord(ns["FakeRecorder"]):
            def record_copied(self, op, attestation):
                if not fs.directory_flushed:
                    os._exit(24)
                temp_open_indexes = [
                    index
                    for index, (kind, path, _handle) in enumerate(handle_events)
                    if kind == "open" and ".synctmp-" in path.name
                ]
                if len(temp_open_indexes) != 1:
                    os._exit(25)
                open_index = temp_open_indexes[0]
                temp_handle = handle_events[open_index][2]
                close_index = next(
                    (
                        index
                        for index in range(open_index + 1, len(handle_events))
                        if handle_events[index]
                        == ("close", None, temp_handle)
                    ),
                    None,
                )
                if close_index is None:
                    os._exit(25)
                lifecycle = [
                    (kind, handle)
                    for kind, _path, handle in handle_events[
                        open_index : close_index + 1
                    ]
                ]
                if lifecycle != [
                    ("open", temp_handle),
                    ("basic", temp_handle),
                    ("native-flush", temp_handle),
                    ("publish", temp_handle),
                    ("basic", temp_handle),
                    ("native-flush", temp_handle),
                    ("close", temp_handle),
                ]:
                    os._exit(25)
                observed = fs.stat(target, "file.bin")
                if (observed.mtime_ns != attestation.subject.mtime_ns
                        or observed.file_identity != attestation.subject.file_identity
                        or observed.metadata != source_stat.metadata):
                    os._exit(26)
                with marker.open("wb", buffering=0) as stream:
                    stream.write(attestation.content.digest.hex().encode("ascii"))
                    os.fsync(stream.fileno())
                return super().record_copied(op, attestation)

        def emit(event):
            if isinstance(event, ns["ItemOutcome"]) and event.outcome is ns["Outcome"].SUCCEEDED:
                if not fs.directory_flushed or not marker.exists():
                    os._exit(24)
                os._exit(23)

        ns["execute"](
            ns["_xset"](ns["_plan"](source, target, (operation,))),
            ns["RunContext"](emit, lambda: None),
            ExitAtRecord(),
            ns["_policies"](),
            fs,
        )
        os._exit(99)
        """
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            child,
            str(Path(__file__).resolve()),
            str(source),
            str(target),
            str(marker),
        ],
        check=False,
        timeout=30,
    )

    published = target / "file.bin"
    try:
        published_stat = parent_fs.stat_path(published)
        assert completed.returncode == 23
        assert marker.read_text(encoding="ascii") == xxh3_128(payload).hexdigest()
        assert published.read_bytes() == payload
        assert published_stat is not None
        assert published_stat.mtime_ns == source_stat.mtime_ns
        assert (
            published_stat.metadata.created_ns
            == source_stat.metadata.created_ns
        )
        assert (
            published_stat.metadata.attributes & intended_mask
            == source_stat.metadata.attributes & intended_mask
        )
        assert not list(target.glob("*.synctmp-*"))
    finally:
        parent_fs.clear_readonly(source_path)
        if published.exists():
            parent_fs.clear_readonly(published)


def test_executor_descendant_walk_observes_each_component_once_in_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first"
    second = first / "second"
    second.mkdir(parents=True)
    leaf = second / "leaf"
    leaf.write_bytes(b"leaf")
    components = (first, second, leaf)
    native_components = {to_extended_length_path(str(path)): path for path in components}
    observations, dispatched = [], []
    original_stat, original_lstat = os.stat, os.lstat

    def stat(current, *args, **kwargs):
        if str(current) in native_components:
            observations.append((native_components[str(current)], kwargs.get("follow_symlinks", True)))
        return original_stat(current, *args, **kwargs)

    def lstat(current, *args, **kwargs):
        if str(current) in native_components:
            observations.append((native_components[str(current)], False))
        return original_lstat(current, *args, **kwargs)

    class _ObservedFileSystem(NativeFileSystem):
        def _reject_reparse(self, path):
            dispatched.append(path)
            return super()._reject_reparse(path)

    monkeypatch.setattr(os, "stat", stat)
    monkeypatch.setattr(os, "lstat", lstat)
    _ObservedFileSystem()._validate_existing_chain(tmp_path, leaf)
    assert dispatched == list(components)
    assert observations == [(path, False) for path in components]


@pytest.mark.skipif(os.name != "nt", reason="native Windows stat-volume serial")
@pytest.mark.parametrize("kind", [EntryKind.FILE, EntryKind.DIRECTORY])
def test_executor_leaf_stat_native_serial_reuses_guarded_held_volume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: EntryKind,
) -> None:
    leaf = tmp_path / "leaf"
    if kind is EntryKind.FILE:
        leaf.write_bytes(b"native serial")
    else:
        leaf.mkdir()
    fs = NativeFileSystem()
    volume = root_authority_module.observe_native_volume(tmp_path)
    if volume.volume_id.fs_type != "NTFS":
        pytest.skip("native leaf identity witness requires NTFS")
    info = leaf.lstat()
    assert info.st_dev & 0xFFFFFFFF == int(volume.volume_id.serial, 16)
    expected = fs.stat_path(leaf)
    scoped = executor_module._InvocationRoot("target", RootAuthority(
        str(tmp_path), volume.evidence.device_id, volume.volume_id,
    ))
    assert executor_module._WINDOWS is not None
    assert root_authority_module._WINDOWS is not None
    original_query = root_authority_module._WINDOWS.get_file_information_ex
    queries = []

    def query(handle, kind, output, size):
        queries.append(kind)
        return original_query(handle, kind, output, size)

    with executor_module._root_invocation_scope(fs, object(), (scoped,), None):
        fs.revalidate_root(tmp_path, expected_volume=volume.volume_id)
        assert scoped.held
        monkeypatch.setattr(root_authority_module._WINDOWS, "get_file_information_ex", query)
        for name in ("get_volume_path", "get_volume_information"):
            monkeypatch.setattr(executor_module._WINDOWS, name,
                                lambda *_args: pytest.fail("matching stat reached volume probe"))
        assert fs.stat_path(leaf) == expected
        assert queries == [0]


@pytest.mark.skipif(os.name != "nt", reason="native Windows stat-volume selection")
@pytest.mark.parametrize("device", ["upper-match", "mismatch", "upper-only", "missing", "negative", "bool", "text"])
def test_executor_leaf_stat_serial_match_and_unavailable_evidence_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    device: str,
) -> None:
    leaf = tmp_path / "leaf"
    leaf.write_bytes(b"checked snapshot")
    fs = NativeFileSystem()
    volume = root_authority_module.observe_native_volume(tmp_path)
    serial = int(volume.volume_id.serial, 16)
    expected = fs.stat_path(leaf)
    observed = leaf.lstat()
    snapshot = SimpleNamespace(**{
        name: getattr(observed, name) for name in (
            "st_mode", "st_size", "st_mtime_ns", "st_ino", "st_nlink",
            "st_file_attributes", "st_birthtime_ns",
        )
    })
    devices = {
        "upper-match": (0x12345678 << 32) | serial,
        "mismatch": serial ^ 1,
        "upper-only": (serial << 32) | (serial ^ 1),
        "negative": -1,
        "bool": True,
        "text": str(serial),
    }
    if device != "missing":
        snapshot.st_dev = devices[device]
    scoped = executor_module._InvocationRoot("target", RootAuthority(
        str(tmp_path), volume.evidence.device_id, volume.volume_id,
    ))
    assert executor_module._WINDOWS is not None
    original_probe = executor_module._WINDOWS.get_volume_path
    probes = []

    def probe(*args):
        probes.append(args[0])
        return original_probe(*args)

    with executor_module._root_invocation_scope(fs, object(), (scoped,), None):
        fs.revalidate_root(tmp_path, expected_volume=volume.volume_id)
        assert scoped.held
        monkeypatch.setattr(fs, "_reject_reparse", lambda path: snapshot)
        monkeypatch.setattr(executor_module._WINDOWS, "get_volume_path", probe)
        assert fs.stat_path(leaf) == expected
        assert len(probes) == (0 if device == "upper-match" else 1)


@pytest.mark.skipif(os.name != "nt", reason="native Windows custom volume probes")
@pytest.mark.parametrize("probe_name", ["_volume_id", "_observe_root_volume"])
@pytest.mark.parametrize("failure", [None, OSError(1117, "custom volume unavailable"), ValueError("custom volume refusal")])
def test_executor_leaf_stat_preserves_custom_volume_probe_dispatch_and_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    probe_name: str,
    failure: Exception | None,
) -> None:
    leaf = tmp_path / "leaf"
    leaf.write_bytes(b"custom volume evidence")
    fs = NativeFileSystem()
    volume = root_authority_module.observe_native_volume(tmp_path)
    scoped = executor_module._InvocationRoot("target", RootAuthority(
        str(tmp_path), volume.evidence.device_id, volume.volume_id,
    ))
    custom_volume = VolumeId("1234ABCD", "NTFS")
    calls = []

    def probe(path):
        calls.append(path)
        if failure is not None:
            raise failure
        return custom_volume if probe_name == "_volume_id" else replace(volume, volume_id=custom_volume)

    with executor_module._root_invocation_scope(fs, object(), (scoped,), None):
        fs.revalidate_root(tmp_path, expected_volume=volume.volume_id)
        assert scoped.held
        monkeypatch.setattr(fs, probe_name, probe)
        if failure is None:
            result = fs.stat_path(leaf)
            assert result is not None and result.file_identity is not None
            assert result.file_identity.volume_serial == custom_volume.serial
        else:
            with pytest.raises(type(failure)) as refused:
                fs.stat_path(leaf)
            assert refused.value is failure
        assert calls == [leaf if probe_name == "_volume_id" else str(leaf)]


@pytest.mark.skipif(os.name != "nt", reason="native Windows junction ACL refusal")
@pytest.mark.parametrize("held", [False, True])
def test_executor_resolve_refuses_unreadable_junction_without_following_it(
    tmp_path: Path,
    held: bool,
) -> None:
    root = tmp_path / "root"
    parent = root / "parent"
    parent.mkdir(parents=True)
    sibling = tmp_path / "owned-sibling"
    sibling.mkdir()
    marker = sibling / "untouched.bin"
    marker.write_bytes(b"owned sibling unchanged")
    volume = root_authority_module.observe_native_volume(root)
    if volume.volume_id.fs_type != "NTFS":
        pytest.skip("unreadable junction witness requires NTFS ACLs")
    link = parent / "link"
    user = getpass.getuser()

    def acl(path, *args):
        subprocess.run(
            ["icacls", str(path), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )

    fs = NativeFileSystem()
    scoped = executor_module._InvocationRoot("target", RootAuthority(
        str(root), volume.evidence.device_id, volume.volume_id,
    ))
    _create_directory_reparse(link, sibling)
    try:
        acl(parent, "/deny", f"{user}:(RD)")
        acl(link, "/deny", f"{user}:(RA)")
        with pytest.raises(PermissionError) as denied:
            link.lstat()
        assert denied.value.winerror == 5
        scope = (
            executor_module._root_invocation_scope(fs, object(), (scoped,), None)
            if held else nullcontext()
        )
        with scope:
            if held:
                fs.revalidate_root(root, expected_volume=volume.volume_id)
                assert scoped.held
            with pytest.raises(PermissionError) as refused:
                fs.resolve(root, "parent\\link\\escape.bin", must_exist=False)
            assert refused.value.winerror == 5
    finally:
        acl(parent, "/remove:d", user)
        acl(link, "/remove:d", user)
        link.rmdir()
        assert not os.path.lexists(link)
        assert marker.read_bytes() == b"owned sibling unchanged"
        assert list(sibling.iterdir()) == [marker]


@pytest.mark.parametrize("failure", [FileNotFoundError(2, "missing"), PermissionError(5, "denied"), OSError(1117, "unavailable")])
def test_executor_descendant_walk_stops_only_at_first_missing_component(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: OSError,
) -> None:
    first = tmp_path / "first"
    second = first / "second"
    first.mkdir()
    fs = NativeFileSystem()
    original = fs._reject_reparse
    visited = []

    def observe(path):
        visited.append(path)
        if path == second:
            raise failure
        return original(path)

    monkeypatch.setattr(fs, "_reject_reparse", observe)
    if isinstance(failure, FileNotFoundError):
        fs._validate_existing_chain(tmp_path, second / "unvisited-leaf")
    else:
        with pytest.raises(type(failure)) as refused:
            fs._validate_existing_chain(tmp_path, second / "unvisited-leaf")
        assert refused.value is failure
    assert visited == [first, second]


@pytest.mark.parametrize("method", ["trash_destination", "revalidate_trash_destination"])
def test_executor_trash_consumers_refuse_unreadable_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
) -> None:
    destination = tmp_path / ".synctrash" / str(RUN_ID) / "parent" / "unreadable.bin"
    destination.parent.mkdir(parents=True)
    fs = NativeFileSystem()
    original = Path.lstat
    denied = PermissionError(5, "denied")
    visited = []

    def observe(path, *args, **kwargs):
        if str(path) == executor_module._win32_path(destination):
            visited.append(path)
            raise denied
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", observe)
    with pytest.raises(PermissionError) as refused:
        if method == "trash_destination":
            fs.trash_destination(tmp_path, RUN_ID, "parent\\unreadable.bin")
        else:
            fs.revalidate_trash_destination(
                tmp_path, RUN_ID, "parent\\unreadable.bin", destination,
            )
    assert refused.value is denied
    assert len(visited) == 1
    assert not destination.exists()


@pytest.mark.parametrize("mode,attributes", [(stat_module.S_IFLNK, 0), (stat_module.S_IFREG, 0x400)])
def test_executor_descendant_walk_propagates_checked_leaf_reparse_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: int,
    attributes: int,
) -> None:
    first = tmp_path / "first"
    leaf = first / "leaf"
    native_leaf = to_extended_length_path(str(leaf))
    observed = []

    def lstat(path):
        observed.append(str(path))
        return SimpleNamespace(
            st_mode=mode if str(path) == native_leaf else stat_module.S_IFDIR,
            st_file_attributes=attributes if str(path) == native_leaf else 0,
        )

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(UnsafeExecutionPath, match="reparse points"):
        NativeFileSystem()._validate_existing_chain(tmp_path, leaf)
    assert observed == [to_extended_length_path(str(first)), native_leaf]


@pytest.mark.parametrize("boundary", ["equal-root", "outside-root", "invalid-conversion", "guard-value"])
def test_executor_descendant_walk_keeps_containment_conversion_and_error_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    fs = NativeFileSystem()
    visited = []
    failure = ValueError("owning guard failure")

    def observe(path):
        visited.append(path)
        raise failure

    monkeypatch.setattr(fs, "_reject_reparse", observe)
    if boundary == "equal-root":
        monkeypatch.setattr(executor_module, "_win32_path", lambda _path: pytest.fail("root equality reached a descendant conversion"))
        fs._validate_existing_chain(tmp_path, tmp_path)
    else:
        candidate = (
            tmp_path.parent / "outside" / "leaf" if boundary == "outside-root" else
            tmp_path / "bad\x00component" / "leaf" if boundary == "invalid-conversion"
            else tmp_path / "first" / "leaf"
        )
        expected = UnsafeExecutionPath if boundary == "outside-root" else PathValidationError if boundary == "invalid-conversion" else ValueError
        with pytest.raises(expected) as refused:
            fs._validate_existing_chain(tmp_path, candidate)
        if boundary == "guard-value":
            assert refused.value is failure
    assert visited == ([tmp_path / "first"] if boundary == "guard-value" else [])


@pytest.mark.skipif(os.name != "nt", reason="native Windows leaf observations")
@pytest.mark.parametrize("kind", [EntryKind.FILE, EntryKind.DIRECTORY])
def test_executor_leaf_stat_uses_one_checked_snapshot_for_all_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: EntryKind,
) -> None:
    path = tmp_path / "leaf"
    if kind is EntryKind.FILE:
        path.write_bytes(b"leaf evidence")
    else:
        path.mkdir()
    info = path.lstat()
    native_path = to_extended_length_path(str(path))
    observations: list[tuple[str, bool]] = []
    original_stat, original_lstat = os.stat, os.lstat
    fs = NativeFileSystem()

    def observe_stat(current, *args, **kwargs):
        if str(current) == native_path:
            observations.append(("stat", kwargs.get("follow_symlinks", True)))
        return original_stat(current, *args, **kwargs)

    def observe_lstat(current, *args, **kwargs):
        if str(current) == native_path:
            observations.append(("lstat", False))
        return original_lstat(current, *args, **kwargs)

    monkeypatch.setattr(os, "stat", observe_stat)
    monkeypatch.setattr(os, "lstat", observe_lstat)
    actual = fs.stat_path(path)

    assert observations == [("stat", False)]
    assert actual is not None and actual.kind is kind
    assert actual.size == (info.st_size if kind is EntryKind.FILE else 0)
    assert actual.mtime_ns == info.st_mtime_ns and actual.nlink == info.st_nlink
    assert actual.metadata.attributes == info.st_file_attributes
    assert actual.metadata.created_ns == info.st_birthtime_ns
    if actual.file_identity is not None:
        assert actual.file_identity.file_index == info.st_ino


@pytest.mark.parametrize("failure", [FileNotFoundError(2, "missing"), PermissionError(5, "denied"), OSError(1117, "unavailable")])
def test_executor_leaf_initial_unavailable_observation_returns_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: OSError,
) -> None:
    fs = NativeFileSystem()
    calls: list[Path] = []
    path = tmp_path / "leaf"

    def unavailable(observed: Path):
        calls.append(observed)
        raise failure

    monkeypatch.setattr(fs, "_reject_reparse", unavailable)
    monkeypatch.setattr(fs, "_volume_id", lambda _path: pytest.fail("unavailable leaf reached volume probe"))
    assert fs.stat_path(path) is None
    assert calls == [path]


@pytest.mark.parametrize("mode,attributes", [(stat_module.S_IFLNK, 0), (stat_module.S_IFREG, 0x400), (stat_module.S_IFIFO, 0)])
def test_executor_leaf_unsafe_type_and_reparse_refusals_propagate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: int,
    attributes: int,
) -> None:
    fs = NativeFileSystem()
    monkeypatch.setattr(Path, "lstat", lambda _path: SimpleNamespace(st_mode=mode, st_file_attributes=attributes))
    monkeypatch.setattr(fs, "_volume_id", lambda _path: pytest.fail("unsafe leaf reached volume probe"))
    with pytest.raises(UnsafeExecutionPath):
        fs.stat_path(tmp_path / "leaf")


@pytest.mark.skipif(os.name != "nt", reason="Windows path-conversion refusals")
@pytest.mark.parametrize("spelling", ["F:\\bad\x00leaf", "F:\\NUL", "\\\\.\\C:\\bad"])
def test_executor_leaf_conversion_refuses_before_unavailable_policy(
    monkeypatch: pytest.MonkeyPatch,
    spelling: str,
) -> None:
    fs = NativeFileSystem()
    monkeypatch.setattr(fs, "_reject_reparse", lambda _path: pytest.fail("conversion refusal reached leaf observation"))
    with pytest.raises(PathValidationError):
        fs.stat_path(Path(spelling))


@pytest.mark.parametrize("stage", ["observation-value", "volume-os", "volume-value"])
def test_executor_leaf_noninitial_failures_keep_original_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    path = tmp_path / "leaf"
    path.write_bytes(b"leaf")
    fs = NativeFileSystem()
    failure = OSError(1117, "volume failure") if stage == "volume-os" else ValueError("owning failure")

    def fail(_path):
        raise failure

    monkeypatch.setattr(fs, "_reject_reparse" if stage == "observation-value" else "_volume_id", fail)
    with pytest.raises(type(failure)) as refused:
        fs.stat_path(path)
    assert refused.value is failure


def test_executor_leaf_stat_preserves_private_and_public_override_dispatch(
    tmp_path: Path,
) -> None:
    path = tmp_path / "leaf"
    path.write_bytes(b"leaf")
    calls: list[str] = []

    class _ObservedFileSystem(NativeFileSystem):
        def resolve(self, root, relative_path, *, must_exist):
            assert root == tmp_path and relative_path == path.name and not must_exist
            calls.append("resolve")
            return path

        def stat_path(self, observed):
            calls.append("public")
            return super().stat_path(observed)

        def _stat_path(self, observed):
            calls.append("private")
            return super()._stat_path(observed)

        def _reject_reparse(self, observed):
            calls.append("guard")
            return super()._reject_reparse(observed)

    fs = _ObservedFileSystem()
    assert fs.stat(tmp_path, path.name) is not None
    assert calls == ["resolve", "public", "private", "guard"]
    calls.clear()
    assert fs.stat_path(path) is not None
    assert calls == ["public", "private", "guard"]


def test_executor_live_stat_matches_native_scanner_evidence(tmp_path: Path) -> None:
    source, _ = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"evidence")
    scanned = scan(
        Root(str(source), "source"),
        IgnoreSet(),
        RunContext(lambda _: None, lambda: None),
    )

    assert scanned.complete
    assert len(scanned.files) == 1
    actual = NativeFileSystem().stat(source, "file.bin")
    assert actual is not None
    assert replace(actual, file_identity=scanned.files[0].stat.file_identity) == scanned.files[0].stat


def test_exact_temp_recovery_preserves_user_lookalike(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    exact = fs.owned_temp(target / "file.bin", RUN_ID, operation.op_id)
    with fs.create_temp(
        exact, allocation_size=_PREALLOCATION_THRESHOLD
    ) as orphan:
        orphan.write(b"orphan")
    lookalike = target / "notes.synctmp-user.txt"
    lookalike.write_bytes(b"user")

    result, _, _ = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert not exact.exists()
    assert lookalike.read_bytes() == b"user"


def test_orphan_temp_sweep_is_exact_scoped_and_preserves_current_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target"
    touched = target / "touched"
    untouched = target / "untouched"
    trash = target / ".synctrash"
    off_volume = target / "off-volume"
    for directory in (touched, untouched, trash, off_volume):
        directory.mkdir(parents=True)
    fs = NativeFileSystem()
    old_run = validated_run_id("2" * 32)
    old_op = OpId("3" * 32)
    old_preallocated_op = OpId("5" * 32)
    current_op = OpId("4" * 32)
    old_temp = fs.owned_temp(touched / "old.bin", old_run, old_op)
    old_preallocated = fs.owned_temp(
        touched / "preallocated.bin", old_run, old_preallocated_op
    )
    current_temp = fs.owned_temp(touched / "current.bin", RUN_ID, current_op)
    untouched_temp = fs.owned_temp(untouched / "later.bin", old_run, old_op)
    trash_temp = fs.owned_temp(trash / "backup.bin", old_run, old_op)
    off_volume_temp = fs.owned_temp(off_volume / "mounted.bin", old_run, old_op)
    lookalike = touched / "notes.synctmp-user.txt"
    exact_directory = fs.owned_temp(touched / "directory", old_run, old_op)
    old_temp.write_bytes(b"old")
    with fs.create_temp(
        old_preallocated, allocation_size=_PREALLOCATION_THRESHOLD
    ) as stream:
        stream.write(b"preallocated")
    current_temp.write_bytes(b"current")
    untouched_temp.write_bytes(b"untouched")
    trash_temp.write_bytes(b"trash")
    off_volume_temp.write_bytes(b"mounted")
    lookalike.write_bytes(b"user")
    exact_directory.mkdir()
    native_volume = fs._volume_serial
    monkeypatch.setattr(
        fs,
        "_volume_serial",
        lambda path: "off-volume" if path.name == "off-volume" else native_volume(path),
    )

    fs.remove_orphaned_temps(
        target,
        frozenset({"touched", ".synctrash", "off-volume"}),
        RUN_ID,
    )

    assert not old_temp.exists()
    assert not old_preallocated.exists()
    assert current_temp.read_bytes() == b"current"
    assert untouched_temp.read_bytes() == b"untouched"
    assert trash_temp.read_bytes() == b"trash"
    assert off_volume_temp.read_bytes() == b"mounted"
    assert lookalike.read_bytes() == b"user"
    assert exact_directory.is_dir()


class CountingCopyBackend:
    def __init__(self) -> None:
        self.native = NativeCopyBackend(hasher_factory=xxh3_128)
        self.calls = 0

    def copy(self, *args, **kwargs) -> CopyDigest:
        self.calls += 1
        return self.native.copy(*args, **kwargs)


class ReadRecordingStream:
    def __init__(self, stream, requests: list[int]) -> None:
        self.stream = stream
        self.requests = requests

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def read(self, size: int) -> bytes:
        self.requests.append(size)
        return self.stream.read(size)

    def __getattr__(self, name: str):
        return getattr(self.stream, name)


class BackupShapeFileSystem(NativeFileSystem):
    def __init__(self, source_path: Path, old_target: Path) -> None:
        self.source_path = source_path
        self.old_target = old_target
        self.read_requests: dict[Path, list[int]] = {
            source_path: [],
            old_target: [],
        }
        self.temp_requests: list[tuple[Path, int | None]] = []
        self.finalized_paths: list[Path] = []
        self.finalization_flushes: list[tuple[Path, int]] = []
        self.security_pairs: list[tuple[Path, Path]] = []
        self.writer_flushes = 0
        self.handle_flushes = 0
        self.temp_descriptors: dict[Path, int] = {}

    def open_source(self, path: Path):
        stream = super().open_source(path)
        return ReadRecordingStream(stream, self.read_requests[path])

    def create_temp(self, path: Path, *, allocation_size: int | None):
        self.temp_requests.append((path, allocation_size))
        stream = super().create_temp(path, allocation_size=allocation_size)
        self.temp_descriptors[path] = stream.fileno()
        return stream

    def finalize_temp(self, path: Path, *args, **kwargs) -> FileStat:
        before = self.handle_flushes
        self.finalized_paths.append(path)
        result = super().finalize_temp(path, *args, **kwargs)
        self.finalization_flushes.append(
            (path, self.handle_flushes - before)
        )
        return result

    def flush_file(self, stream) -> None:
        self.writer_flushes += 1
        super().flush_file(stream)

    def _flush_handle(self, handle) -> None:
        self.handle_flushes += 1
        super()._flush_handle(handle)

    def copy_security(self, source: Path, target: Path) -> None:
        self.security_pairs.append((source, target))


def test_copied_backup_stays_serial_hashless_fixed_chunk_and_unallocated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    old_target = target / "file.bin"
    source_path.write_bytes(b"n" * (9 * 1024 * 1024))
    old_target.write_bytes(b"o" * (9 * 1024 * 1024))
    fs = BackupShapeFileSystem(source_path, old_target)
    source_stat = fs.stat(source, "file.bin")
    old_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=old_stat,
        intended=source_stat,
    )
    backend = CountingCopyBackend()
    closed_descriptors: set[int] = set()
    native_close = os.close

    def observe_close(descriptor: int) -> None:
        native_close(descriptor)
        if descriptor in fs.temp_descriptors.values():
            with pytest.raises(OSError):
                os.fstat(descriptor)
            closed_descriptors.add(descriptor)

    monkeypatch.setattr(os, "close", observe_close)
    worker_names: list[str | None] = []
    real_thread = executor_pipeline.Thread

    def recording_thread(*args, **kwargs):
        worker_names.append(kwargs.get("name"))
        return real_thread(*args, **kwargs)

    monkeypatch.setattr(executor_pipeline, "Thread", recording_thread)

    result, _, _ = _run(
        _xset(
            _plan(
                source,
                target,
                (operation,),
                hardlinks=False,
                preservation=PreservationPolicy(preserve_acl=True),
            )
        ),
        fs=fs,
        policies=_policies(
            copy_backend=backend,
            max_chunk_size=4 * 1024 * 1024,
        ),
    )

    trash_root = target / ".synctrash"
    backup_temps = [
        (path, allocation)
        for path, allocation in fs.temp_requests
        if trash_root in path.parents
    ]
    assert result.status is SessionState.COMPLETED
    assert backend.calls == 1
    assert set(fs.read_requests[old_target]) == {4 * 1024 * 1024}
    assert set(fs.read_requests[source_path]) == {1024 * 1024}
    assert len(backup_temps) == 1 and backup_temps[0][1] is None
    assert backup_temps[0][0] in fs.finalized_paths
    assert fs.writer_flushes == 0
    assert dict(fs.finalization_flushes)[backup_temps[0][0]] == 1
    if os.name == "nt":
        assert len(fs.temp_descriptors) == 2
        assert set(fs.temp_descriptors.values()) == closed_descriptors
    assert worker_names == [
        "namisync-copy-hasher",
        "namisync-copy-writer",
    ]
    assert fs.security_pairs == [
        (
            source_path,
            next(
                path
                for path, _ in fs.temp_requests
                if trash_root not in path.parents
            ),
        )
    ]


class MutatingBackupStream:
    def __init__(self, stream, path: Path, mutation: str) -> None:
        self.stream = stream
        self.path = path
        self.mutation = mutation
        self.mutated = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def read(self, size: int) -> bytes:
        chunk = self.stream.read(size)
        if chunk and not self.mutated:
            before = self.path.stat(follow_symlinks=False)
            if self.mutation == "grow":
                with self.path.open("ab", buffering=0) as writer:
                    writer.write(b"-external-growth")
            elif self.mutation == "shrink":
                with self.path.open("r+b", buffering=0) as writer:
                    writer.truncate(0)
            else:
                with self.path.open("r+b", buffering=0) as writer:
                    writer.write(b"X" * before.st_size)
                os.utime(
                    self.path,
                    ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000),
                )
            self.mutated = True
        return chunk

    def __getattr__(self, name: str):
        return getattr(self.stream, name)


class MutatingCopiedBackupFileSystem(NativeFileSystem):
    def __init__(self, live: Path, mutation: str) -> None:
        self.live = live
        self.mutation = mutation
        self.backup_publish_calls = 0
        self.replace_calls = 0

    def open_source(self, path: Path):
        stream = super().open_source(path)
        if path != self.live:
            return stream
        return MutatingBackupStream(stream, path, self.mutation)

    def publish_new(self, temp: Path, target: Path) -> None:
        if ".synctrash" in target.parts:
            self.backup_publish_calls += 1
        super().publish_new(temp, target)

    def replace(self, temp: Path, target: Path) -> None:
        self.replace_calls += 1
        super().replace(temp, target)


class CopiedBackupPublicationSpyFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.backup_publish_calls = 0
        self.replace_calls = 0

    def publish_new(self, temp: Path, target: Path) -> None:
        if ".synctrash" in target.parts:
            self.backup_publish_calls += 1
        super().publish_new(temp, target)

    def replace(self, temp: Path, target: Path) -> None:
        self.replace_calls += 1
        super().replace(temp, target)


def _change_incidental_target_metadata(fs: NativeFileSystem, target: Path, expected: FileStat) -> FileStat:
    assert expected.metadata.created_ns is not None
    changed = replace(expected, metadata=replace(
        expected.metadata, created_ns=expected.metadata.created_ns + 2_000_000_000
    ))
    fs.apply_metadata(target, changed, preserve_created=True, apply_readonly=True)
    fs._set_attributes(target, fs._get_attributes(target) ^ 0x100)
    observed = fs.stat_path(target)
    assert observed is not None
    assert observed.metadata.created_ns == changed.metadata.created_ns
    assert observed.metadata.attributes != expected.metadata.attributes
    assert observed.mtime_ns == expected.mtime_ns
    return observed


@pytest.mark.skipif(os.name != "nt", reason="Windows creation-time preservation")
@pytest.mark.parametrize("hardlinks", (True, False), ids=("hardlink", "copy"))
def test_update_backup_preserves_full_admitted_target_after_incidental_drift(tmp_path: Path, hardlinks: bool) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new")
    live = target / "file.bin"
    live.write_bytes(b"old")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    expected = fs.stat(target, "file.bin")
    assert source_stat is not None and expected is not None
    op = _operation(
        1, OperationKind.UPDATE, source_rel_path="file.bin", target_rel_path="file.bin",
        source_expected=source_stat, target_expected=expected, intended=source_stat,
    )
    admitted = _change_incidental_target_metadata(fs, live, expected)
    result, events, recorder = _run(_xset(_plan(source, target, (op,), hardlinks=hardlinks)), fs=fs)
    backup = target / ".synctrash" / str(RUN_ID) / "file.bin"
    backup_stat = fs.stat_path(backup)
    assert result.status is SessionState.COMPLETED, (
        dict(_item_outcome(events).detail), admitted.metadata,
        fs.stat_path(live).metadata, admitted.nlink, fs.stat_path(live).nlink,
    )
    assert backup.read_bytes() == b"old" and live.read_bytes() == b"new"
    assert backup_stat is not None
    assert backup_stat.metadata.created_ns == admitted.metadata.created_ns
    assert backup_stat.mtime_ns == admitted.mtime_ns
    assert _recorder_names(recorder) == ["updated"]


@pytest.mark.skipif(os.name != "nt", reason="Windows creation-time preservation")
@pytest.mark.parametrize("kind", (OperationKind.UPDATE, OperationKind.DELETE))
def test_failed_readonly_effect_restores_full_admitted_creation_time(tmp_path: Path, kind) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new")
    live = target / "file.bin"
    live.write_bytes(b"old")

    class RefusingFileSystem(NativeFileSystem):
        def replace(self, temp, target):
            raise PermissionError("controlled replace refusal")

        def remove_file(self, path):
            raise PermissionError("controlled delete refusal")

    fs = RefusingFileSystem()
    source_stat = fs.stat(source, "file.bin")
    initial = fs.stat(target, "file.bin")
    assert source_stat is not None and initial is not None
    fs.apply_metadata(live, replace(initial, metadata=replace(initial.metadata, attributes=initial.metadata.attributes | 1)), preserve_created=True, apply_readonly=True)
    expected = fs.stat(target, "file.bin")
    assert expected is not None
    op = _operation(
        1, kind, source_rel_path="file.bin" if kind is OperationKind.UPDATE else None,
        target_rel_path="file.bin", source_expected=source_stat if kind is OperationKind.UPDATE else None,
        target_expected=expected, intended=source_stat if kind is OperationKind.UPDATE else None,
    )
    admitted = _change_incidental_target_metadata(fs, live, expected)
    try:
        result, _, recorder = _run(_xset(_plan(source, target, (op,))), fs=fs)
        restored = fs.stat(target, "file.bin")
        assert result.status is SessionState.FAILED and recorder.calls == []
        assert restored is not None and restored.metadata.attributes & 1
        assert restored.metadata.created_ns == admitted.metadata.created_ns
        assert live.read_bytes() == b"old"
    finally:
        fs.clear_readonly(live)
        for backup in target.rglob("file.bin"):
            fs.clear_readonly(backup)


@pytest.mark.skipif(os.name != "nt", reason="Windows creation-time preservation")
@pytest.mark.parametrize("kind", (OperationKind.MOVE, OperationKind.RECASE))
@pytest.mark.parametrize("alter_after_rename", (False, True))
def test_pure_rename_binds_post_effect_to_full_admitted_stat(tmp_path: Path, kind, alter_after_rename) -> None:
    source, target = _roots(tmp_path)
    new_name = "KEEP.bin" if kind is OperationKind.RECASE else "new.bin"
    old_name = "keep.bin" if kind is OperationKind.RECASE else "old.bin"
    (source / new_name).write_bytes(b"same")
    old = target / old_name
    old.write_bytes(b"same")

    class RenameFileSystem(NativeFileSystem):
        def rename_new(self, source, destination):
            super().rename_new(source, destination)
            if alter_after_rename:
                current = self.stat_path(destination)
                assert current is not None
                _change_incidental_target_metadata(self, destination, current)

    fs = RenameFileSystem()
    expected = fs.stat(target, old_name)
    source_stat = fs.stat(source, new_name)
    assert expected is not None and source_stat is not None
    op = _operation(
        1, kind, source_rel_path=new_name, target_rel_path=new_name,
        source_expected=source_stat, target_expected=expected if kind is OperationKind.RECASE else None,
        intended=expected, prior_target_rel_path=old_name, prior_target_expected=expected,
    )
    _change_incidental_target_metadata(fs, old, expected)
    if kind is OperationKind.RECASE:
        os.link(old, target / "alias.bin")
    admitted = fs.stat(target, old_name)
    assert admitted is not None
    result, events, recorder = _run(_xset(_plan(source, target, (op,))), fs=fs)
    if alter_after_rename:
        assert result.status is SessionState.FAILED and recorder.calls == []
    else:
        assert result.status is SessionState.COMPLETED, (
            dict(_item_outcome(events).detail), admitted.metadata,
            fs.stat_path(target / new_name).metadata,
        )
        assert recorder.calls[0][2] == admitted
    assert (target / new_name).read_bytes() == b"same"


@pytest.mark.skipif(os.name != "nt", reason="Windows creation-time preservation")
@pytest.mark.parametrize("alter_trash_after_commit", (False, True))
def test_move_update_refreshes_old_witness_and_keeps_strict_committed_trash_recovery(tmp_path: Path, alter_trash_after_commit) -> None:
    source, target = _roots(tmp_path)
    (source / "new.bin").write_bytes(b"new")
    old = target / "old.bin"
    old.write_bytes(b"old")

    class MoveUpdateFileSystem(NativeFileSystem):
        admitted_old: FileStat | None = None
        trash_attempts = 0

        def ensure_published_metadata(self, path, *args, **kwargs):
            result = super().ensure_published_metadata(path, *args, **kwargs)
            if path == target / "new.bin":
                current = self.stat_path(old)
                assert current is not None
                self.admitted_old = _change_incidental_target_metadata(self, old, current)
            return result

        def rename_new(self, source, destination):
            super().rename_new(source, destination)
            if ".synctrash" in destination.parts:
                self.trash_attempts += 1
                if alter_trash_after_commit:
                    current = self.stat_path(destination)
                    assert current is not None
                    _change_incidental_target_metadata(self, destination, current)
                raise _sharing_violation("controlled committed-trash retry")

    fs = MoveUpdateFileSystem()
    expected = fs.stat(target, "old.bin")
    source_stat = fs.stat(source, "new.bin")
    assert expected is not None and source_stat is not None
    op = _operation(
        1, OperationKind.MOVE_UPDATE, source_rel_path="new.bin", target_rel_path="new.bin",
        source_expected=source_stat, target_expected=None, intended=source_stat,
        prior_target_rel_path="old.bin", prior_target_expected=expected,
    )
    _change_incidental_target_metadata(fs, old, expected)
    result, _, recorder = _run(_xset(_plan(source, target, (op,))), fs=fs)
    assert fs.trash_attempts == 1 and fs.admitted_old is not None
    trash = target / ".synctrash" / str(RUN_ID) / "old.bin"
    assert trash.read_bytes() == b"old" and (target / "new.bin").read_bytes() == b"new"
    if alter_trash_after_commit:
        assert result.status is SessionState.FAILED and recorder.calls == []
    else:
        assert result.status is SessionState.COMPLETED
        assert fs.stat_path(trash) == fs.admitted_old
        assert _recorder_names(recorder) == ["move_updated"]


@pytest.mark.parametrize("kind,subject", (
    (OperationKind.COPY, "source"),
    (OperationKind.MOVE, "source"),
    (OperationKind.MOVE, "prior_target"),
    (OperationKind.MOVE_UPDATE, "source"),
    (OperationKind.MOVE_UPDATE, "prior_target"),
))
def test_executor_link_drift_is_only_a_move_eligibility_fact(tmp_path: Path, kind, subject) -> None:
    source, target = _roots(tmp_path)
    source_file = source / "new.bin"
    source_file.write_bytes(b"new")
    old = target / "old.bin"
    old.write_bytes(b"old")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "new.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    op = _operation(
        1, kind, source_rel_path="new.bin", target_rel_path="new.bin",
        source_expected=source_stat, target_expected=None, intended=source_stat,
        prior_target_rel_path="old.bin" if kind is not OperationKind.COPY else None,
        prior_target_expected=old_stat if kind is not OperationKind.COPY else None,
    )
    selected = source_file if subject == "source" else old
    os.link(selected, selected.with_name("alias.bin"))
    result, events, recorder = _run(_xset(_plan(source, target, (op,))), fs=fs)
    if kind is OperationKind.COPY:
        assert result.status is SessionState.COMPLETED
        assert (target / "new.bin").read_bytes() == b"new"
        assert _recorder_names(recorder) == ["copied"]
    else:
        assert result.status is SessionState.FAILED and recorder.calls == []
        assert _item_outcome(events).reason == ("source-drift" if subject == "source" else "target-drift")
        assert old.read_bytes() == b"old" and not (target / "new.bin").exists()


def test_recase_profiles_the_full_admitted_version_on_identity_weak_plan(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "KEEP.bin").write_bytes(b"same")
    (target / "keep.bin").write_bytes(b"same")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "KEEP.bin")
    target_stat = fs.stat(target, "keep.bin")
    assert source_stat is not None and target_stat is not None
    assert target_stat.file_identity is not None
    op = _operation(
        1, OperationKind.RECASE, source_rel_path="KEEP.bin", target_rel_path="KEEP.bin",
        source_expected=replace(source_stat, file_identity=None),
        target_expected=replace(target_stat, file_identity=None),
        intended=replace(target_stat, file_identity=None), prior_target_rel_path="keep.bin",
        prior_target_expected=replace(target_stat, file_identity=None),
    )
    built = _plan(source, target, (op,))
    built = replace(built,
        source_profile=replace(built.source_profile, stable_file_identity=False),
        target_profile=replace(built.target_profile, stable_file_identity=False),
    )
    result, _, recorder = _run(_xset(built), fs=fs)
    assert result.status is SessionState.COMPLETED
    recorded = recorder.calls[0][2]
    assert recorded.file_identity is None
    assert recorded.metadata == target_stat.metadata
    assert (target / "KEEP.bin").read_bytes() == b"same"


def test_copied_backup_does_not_adopt_target_drift_after_reviewed_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    live = target / "file.bin"
    source_path.write_bytes(b"new-version")
    live.write_bytes(b"old-version")
    fs = CopiedBackupPublicationSpyFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    real_require_stat_path = executor_runtime._require_stat_path
    mutated = False

    def mutate_after_reviewed_guard(filesystem, path: Path) -> FileStat:
        nonlocal mutated
        if not mutated and ".synctmp-" in path.name:
            live.write_bytes(b"external-version-is-different")
            mutated = True
        return real_require_stat_path(filesystem, path)

    monkeypatch.setattr(
        executor_runtime,
        "_require_stat_path",
        mutate_after_reviewed_guard,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)),
        fs=fs,
    )

    item = _item_outcome(events)
    backup = target / ".synctrash" / str(RUN_ID) / "file.bin"
    assert mutated
    assert result.status is SessionState.FAILED
    assert item.reason == "target-drift"
    assert item.detail["message"] == (
        "live update target drifted before its backup was copied"
    )
    assert live.read_bytes() == b"external-version-is-different"
    assert fs.backup_publish_calls == 0
    assert fs.replace_calls == 0
    assert not backup.exists()
    assert not list(target.rglob("*.synctmp-*"))
    assert recorder.calls == []


@pytest.mark.parametrize(
    ("mutation", "expected_live"),
    [
        ("grow", b"old-version-external-growth"),
        ("shrink", b""),
        ("rewrite", b"X" * len(b"old-version")),
    ],
)
def test_copied_backup_rejects_live_drift_before_backup_or_update_publish(
    tmp_path: Path,
    mutation: str,
    expected_live: bytes,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    live = target / "file.bin"
    source_path.write_bytes(b"new-version")
    live.write_bytes(b"old-version")
    fs = MutatingCopiedBackupFileSystem(live, mutation)
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)),
        fs=fs,
    )

    item = _item_outcome(events)
    backup = target / ".synctrash" / str(RUN_ID) / "file.bin"
    assert result.status is SessionState.FAILED
    assert item.reason == "target-drift"
    assert item.detail["message"] == (
        "live update target drifted while its backup was copied"
    )
    assert live.read_bytes() == expected_live
    assert fs.backup_publish_calls == 0
    assert fs.replace_calls == 0
    assert not backup.exists()
    assert not list(target.rglob("*.synctmp-*"))
    assert recorder.calls == []


class FailingBackupWriter:
    def __init__(self, stream) -> None:
        self.stream = stream

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def write(self, _data) -> int:
        raise OSError("injected backup write failure")

    def __getattr__(self, name: str):
        return getattr(self.stream, name)


class BackupFailureFileSystem(NativeFileSystem):
    def __init__(self, failure: str) -> None:
        self.failure = failure

    def create_temp(self, path: Path, *, allocation_size: int | None):
        stream = super().create_temp(path, allocation_size=allocation_size)
        if self.failure == "write":
            return FailingBackupWriter(stream)
        return stream

    def finalize_temp(self, path: Path, *args, **kwargs) -> FileStat:
        if self.failure == "finalize":
            raise OSError("injected backup finalization failure")
        return super().finalize_temp(path, *args, **kwargs)


class BackupCleanupDiagnosticFileSystem(BackupFailureFileSystem):
    def __init__(self) -> None:
        super().__init__("write")

    def remove_owned_temp(self, path: Path) -> None:
        native = to_extended_length_path(str(path))
        raise PermissionError(13, "cleanup denied", native)


class BackupFinalizationSpyFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.finalize_calls = 0

    def finalize_temp(self, path: Path, *args, **kwargs) -> FileStat:
        self.finalize_calls += 1
        return super().finalize_temp(path, *args, **kwargs)


class BackupTempCreationSpyFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.source_opened = False
        self.create_calls = 0

    def open_source(self, path: Path):
        stream = super().open_source(path)
        self.source_opened = True
        return stream

    def create_temp(self, path: Path, *, allocation_size: int | None):
        self.create_calls += 1
        return super().create_temp(path, allocation_size=allocation_size)


class UpdateSourceGuardTrashSwapFileSystem(NativeFileSystem):
    def __init__(
        self,
        source_root: Path,
        target_root: Path,
        redirected_root: Path,
    ) -> None:
        self.source_root = source_root
        self.target_root = target_root
        self.redirected_root = redirected_root
        self.detached_root = target_root / f".detached-trash-{RUN_ID}"
        self.backup_created = False
        self.swapped = False
        self.replace_calls = 0

    def hardlink(self, source: Path, target: Path) -> None:
        super().hardlink(source, target)
        if ".synctrash" in target.parts:
            self.backup_created = True

    def copy_backup(
        self,
        source,
        temp,
        target,
        source_expected,
        checkpoint,
        validate_destination,
    ) -> None:
        super().copy_backup(
            source,
            temp,
            target,
            source_expected,
            checkpoint,
            validate_destination,
        )
        self.backup_created = True

    def stat(self, root: Path, relative_path: str) -> FileStat | None:
        actual = super().stat(root, relative_path)
        if root == self.source_root and self.backup_created and not self.swapped:
            run_root = self.target_root / ".synctrash" / str(RUN_ID)
            run_root.rename(self.detached_root)
            _create_directory_reparse(run_root, self.redirected_root)
            self.swapped = True
        return actual

    def replace(self, temp: Path, target: Path) -> None:
        self.replace_calls += 1
        super().replace(temp, target)


@pytest.mark.parametrize("failure", ["cancel", "write", "finalize"])
def test_copied_backup_removes_its_temp_on_every_prepublish_failure(
    tmp_path: Path, failure: str
) -> None:
    target = tmp_path / "target"
    trash = target / ".synctrash" / str(RUN_ID)
    trash.mkdir(parents=True)
    live = target / "file.bin"
    live.write_bytes(b"old-version")
    backup = trash / "file.bin"
    fs = BackupFailureFileSystem(failure)
    temp = fs.owned_temp(backup, RUN_ID, OpId("2" * 32))
    live_stat = fs.stat_path(live)
    assert live_stat is not None

    def checkpoint() -> None:
        if failure == "cancel":
            raise Canceled()

    expected_error = Canceled if failure == "cancel" else OSError
    with pytest.raises(expected_error):
        fs.copy_backup(
            live,
            temp,
            backup,
            live_stat,
            checkpoint,
            lambda: None,
        )

    assert live.read_bytes() == b"old-version"
    assert not backup.exists()
    assert not list(target.rglob("*.synctmp-*"))


def test_copied_backup_cleanup_note_sanitizes_native_filename(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    trash = target / ".synctrash" / str(RUN_ID)
    trash.mkdir(parents=True)
    live = target / "file.bin"
    live.write_bytes(b"old-version")
    backup = trash / "file.bin"
    fs = BackupCleanupDiagnosticFileSystem()
    temp = fs.owned_temp(backup, RUN_ID, OpId("2" * 32))
    live_stat = fs.stat_path(live)
    assert live_stat is not None

    with pytest.raises(OSError) as captured:
        fs.copy_backup(
            live,
            temp,
            backup,
            live_stat,
            lambda: None,
            lambda: None,
        )

    notes = captured.value.__notes__
    assert len(notes) == 1
    assert r"file.bin.synctmp-" in notes[0]
    assert "\\\\?\\" not in notes[0]


def test_copied_backup_revalidates_parent_before_temp_finalization(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    trash = target / ".synctrash" / str(RUN_ID)
    trash.mkdir(parents=True)
    live = target / "file.bin"
    live.write_bytes(b"old-version")
    backup = trash / "file.bin"
    fs = BackupFinalizationSpyFileSystem()
    temp = fs.owned_temp(backup, RUN_ID, OpId("2" * 32))
    live_stat = fs.stat_path(live)
    assert live_stat is not None
    validations = 0

    def reject_redirected_parent() -> None:
        nonlocal validations
        validations += 1
        if validations >= 2:
            raise UnsafeExecutionPath("injected redirected trash parent")

    with pytest.raises(UnsafeExecutionPath, match="redirected trash parent"):
        fs.copy_backup(
            live,
            temp,
            backup,
            live_stat,
            lambda: None,
            reject_redirected_parent,
        )

    assert validations == 3
    assert fs.finalize_calls == 0
    assert temp.exists()
    assert not backup.exists()


def test_copied_backup_revalidates_parent_after_source_open_before_temp_create(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    trash = target / ".synctrash" / str(RUN_ID)
    trash.mkdir(parents=True)
    live = target / "file.bin"
    live.write_bytes(b"old-version")
    backup = trash / "file.bin"
    fs = BackupTempCreationSpyFileSystem()
    temp = fs.owned_temp(backup, RUN_ID, OpId("2" * 32))
    live_stat = fs.stat_path(live)
    assert live_stat is not None
    validations = 0

    def reject_redirect_after_source_open() -> None:
        nonlocal validations
        validations += 1
        if fs.source_opened:
            raise UnsafeExecutionPath("injected source-open parent redirect")

    with pytest.raises(UnsafeExecutionPath, match="source-open parent redirect"):
        fs.copy_backup(
            live,
            temp,
            backup,
            live_stat,
            lambda: None,
            reject_redirect_after_source_open,
        )

    assert validations == 2
    assert fs.create_calls == 0
    assert not temp.exists()
    assert not backup.exists()


@pytest.mark.parametrize("hardlinks", [True, False], ids=("hardlink", "copy"))
def test_update_revalidates_trash_parent_after_guards_before_replace(
    tmp_path: Path,
    hardlinks: bool,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    live = target / "file.bin"
    source_path.write_bytes(b"new-version")
    live.write_bytes(b"old-version")
    redirected = tmp_path / "redirected-trash"
    redirected.mkdir()
    _require_directory_reparse(tmp_path, redirected)
    fs = UpdateSourceGuardTrashSwapFileSystem(source, target, redirected)
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=hardlinks)),
        fs=fs,
    )

    item = _item_outcome(events)
    assert fs.swapped
    assert fs.replace_calls == 0
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.OK
    assert item.outcome is Outcome.FAILED
    assert item.reason == "unsafe-path"
    assert "publish_state" not in item.detail
    assert live.read_bytes() == b"old-version"
    assert (fs.detached_root / "file.bin").read_bytes() == b"old-version"
    assert not list(redirected.iterdir())
    assert recorder.calls == []


def test_no_hardlink_update_flushes_readonly_backup_before_readonly(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new")
    live = target / "file.bin"
    live.write_bytes(b"old")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    old = fs.stat(target, "file.bin")
    assert source_stat is not None and old is not None
    fs.apply_metadata(
        live,
        replace(old, metadata=replace(old.metadata, attributes=old.metadata.attributes | 1)),
        preserve_created=True,
        apply_readonly=True,
    )
    old = fs.stat(target, "file.bin")
    assert old is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=old,
        intended=source_stat,
    )

    result, _, _ = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)), fs=fs
    )

    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    trash_stat = fs.stat_path(trash)
    assert result.status is SessionState.COMPLETED
    assert trash.read_bytes() == b"old"
    assert trash_stat is not None and trash_stat.metadata.attributes & 1


class HardlinkRepairFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.flushes = 0
        self.repairs: list[tuple[Path, int, FileStat]] = []

    def _flush_handle(self, handle) -> None:
        self.flushes += 1
        super()._flush_handle(handle)

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        before = self.flushes
        result = super().ensure_published_metadata(path, *args, **kwargs)
        self.repairs.append((path, self.flushes - before, result))
        return result


class RepairAwareRecorder(FakeRecorder):
    def __init__(self, fs: HardlinkRepairFileSystem, trash: Path) -> None:
        super().__init__()
        self.fs = fs
        self.trash = trash

    def record_updated(self, op, attestation) -> RecordedCopyIdentity:
        trash_repairs = [
            (flushes, stat)
            for path, flushes, stat in self.fs.repairs
            if path == self.trash
        ]
        assert trash_repairs
        assert trash_repairs[-1][0] == 1
        assert trash_repairs[-1][1].metadata.attributes & 1
        return super().record_updated(op, attestation)


@pytest.mark.skipif(os.name != "nt", reason="requires NTFS hardlinks and readonly")
def test_hardlink_backup_restores_and_flushes_displaced_readonly_inode_before_record(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new")
    live = target / "file.bin"
    live.write_bytes(b"old")
    fs = HardlinkRepairFileSystem()
    source_stat = fs.stat(source, "file.bin")
    old = fs.stat(target, "file.bin")
    assert source_stat is not None and old is not None
    fs.apply_metadata(
        live,
        replace(
            old,
            metadata=replace(old.metadata, attributes=old.metadata.attributes | 1),
        ),
        preserve_created=True,
        apply_readonly=True,
    )
    old = fs.stat(target, "file.bin")
    assert old is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=old,
        intended=source_stat,
    )
    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    recorder = RepairAwareRecorder(fs, trash)

    result, _, _ = _run(
        _xset(_plan(source, target, (operation,), hardlinks=True)),
        fs=fs,
        recorder=recorder,
    )

    assert result.status is SessionState.COMPLETED
    assert trash.read_bytes() == b"old"
    live_stat = fs.stat_path(live)
    trash_stat = fs.stat_path(trash)
    assert live_stat is not None
    assert not live_stat.metadata.attributes & 0x1
    assert trash_stat is not None
    assert trash_stat.metadata.attributes & 0x1
    fs.clear_readonly(trash)


class HardlinkCompletionOrderFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.order: list[str] = []
        self.backup_metadata_completed = False

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        result = super().ensure_published_metadata(path, *args, **kwargs)
        if ".synctrash" in path.parts:
            self.order.append("backup-metadata")
            self.backup_metadata_completed = True
        else:
            self.order.append("target-metadata")
        return result


def test_update_hardlink_backup_metadata_completes_before_attestation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = HardlinkCompletionOrderFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    def fail_attestation(*_args, **_kwargs):
        assert fs.backup_metadata_completed
        fs.order.append("attestation")
        raise RuntimeError("injected attestation failure")

    monkeypatch.setattr(executor_runtime, "_attestation", fail_attestation)
    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=True)),
        fs=fs,
    )

    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    assert result.status is SessionState.FAILED
    assert fs.order == ["target-metadata", "backup-metadata", "attestation"]
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert trash.read_bytes() == b"old-version"
    assert recorder.calls == []


class AclFailureFileSystem(NativeFileSystem):
    def copy_security(self, source: Path, target: Path) -> None:
        raise PermissionError("ACL copy denied")


def test_acl_failure_happens_before_update_publish(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new")
    (target / "file.bin").write_bytes(b"old")
    fs = AclFailureFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    plan = _plan(
        source,
        target,
        (operation,),
        preservation=PreservationPolicy(preserve_acl=True),
    )

    result, events, recorder = _run(_xset(plan), fs=fs)

    assert result.status is SessionState.FAILED
    assert (target / "file.bin").read_bytes() == b"old"
    assert recorder.calls == []
    assert _item_outcome(events).reason == "acl-copy-failed"
