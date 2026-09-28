from __future__ import annotations

import os
import ctypes
import stat as stat_module
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import namisync.core.root_authority as root_authority
from namisync.core.models import VolumeEvidence, VolumeId
from namisync.core.pathing import PathValidationError, to_extended_length_path
from namisync.core.root_authority import (
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_OFFLINE,
    FILE_ATTRIBUTE_REPARSE_POINT,
    NativeVolumeInfo,
    RootAuthority,
    RootAuthorityError,
    RootAuthorityIssue,
    admit_existing_relative_chain,
    admit_root,
    admit_root_chain,
    current_volume_anchor,
    hold_root,
    is_directory_stat,
    is_placeholder_stat,
    is_reparse_stat,
    observe_native_volume,
    observe_native_volume_at_anchor,
)


VOLUME = VolumeId("A1B2C3D4", "NTFS")


def _stat(
    *,
    directory: bool = False,
    attributes: int = 0,
    reparse_tag: int = 0,
) -> SimpleNamespace:
    mode = stat_module.S_IFDIR if directory else stat_module.S_IFREG
    return SimpleNamespace(
        st_mode=mode | 0o755,
        st_file_attributes=attributes,
        st_reparse_tag=reparse_tag,
    )


def _volume(
    anchor: str,
    volume_id: VolumeId = VOLUME,
) -> NativeVolumeInfo:
    return NativeVolumeInfo(
        volume_id,
        VolumeEvidence("Reviewed", anchor),
        255,
        0,
    )


def test_root_authority_normalizes_and_requires_anchor_containment(
    tmp_path: Path,
) -> None:
    anchor = tmp_path / "mount"
    root = anchor / "managed"

    authority = RootAuthority(str(root), str(anchor), VOLUME)

    assert authority.logical_root == str(root)
    assert authority.reviewed_anchor == str(anchor)
    with pytest.raises(PathValidationError, match="reviewed volume anchor"):
        RootAuthority(str(root), str(tmp_path / "other"), VOLUME)


def test_native_volume_info_accepts_dword_boundary_and_rejects_n_plus_one() -> None:
    evidence = VolumeEvidence("Reviewed", r"C:\\")

    NativeVolumeInfo(VOLUME, evidence, (1 << 32) - 1, (1 << 32) - 1)
    with pytest.raises(ValueError, match="exceeds DWORD"):
        NativeVolumeInfo(VOLUME, evidence, 1 << 32, 0)
    with pytest.raises(ValueError, match="exceed DWORD"):
        NativeVolumeInfo(VOLUME, evidence, 0, 1 << 32)


def test_admit_root_revalidates_forged_native_volume_fields(
    tmp_path: Path,
) -> None:
    anchor = tmp_path / "mount"
    root = anchor / "managed"
    evidence = VolumeEvidence("Reviewed", str(anchor))
    observed = NativeVolumeInfo(VOLUME, evidence, 255, 0)
    object.__setattr__(evidence, "device_id", "p" * 32_768)

    with pytest.raises(RootAuthorityError, match="invalid fields") as raised:
        admit_root(
            RootAuthority(str(root), str(anchor), VOLUME),
            lstat=lambda _path: _stat(directory=True),
            anchor_probe=lambda _path: str(anchor),
            volume_probe=lambda _path: observed,
        )

    assert raised.value.issue is RootAuthorityIssue.VOLUME_UNAVAILABLE


def test_admit_root_checks_anchor_chain_then_volume(tmp_path: Path) -> None:
    anchor = tmp_path / "mount"
    parent = anchor / "parent"
    root = parent / "managed"
    calls: list[tuple[str, str]] = []

    def find_anchor(path: str) -> str:
        calls.append(("anchor", path))
        return str(anchor)

    def lstat(path: str) -> SimpleNamespace:
        calls.append(("lstat", path))
        return _stat(directory=True)

    def find_volume(path: str) -> NativeVolumeInfo:
        calls.append(("volume", path))
        return _volume(str(anchor))

    authority = RootAuthority(str(root), str(anchor), VOLUME)

    assert admit_root(
        authority,
        anchor_probe=find_anchor,
        lstat=lstat,
        volume_probe=find_volume,
    ).volume_id == VOLUME
    assert calls == [
        ("anchor", str(root)),
        ("lstat", str(parent)),
        ("lstat", str(root)),
        ("volume", str(root)),
    ]


def test_admit_root_chain_checks_anchor_and_components_without_volume(
    tmp_path: Path,
) -> None:
    anchor = tmp_path / "mount"
    root = anchor / "managed"
    calls: list[tuple[str, str]] = []
    authority = RootAuthority(str(root), str(anchor), VOLUME)

    admitted_anchor = admit_root_chain(
        authority,
        anchor_probe=lambda path: calls.append(("anchor", path)) or str(anchor),
        lstat=lambda path: calls.append(("lstat", path))
        or _stat(directory=True),
    )

    assert admitted_anchor == str(anchor)
    assert calls == [
        ("anchor", str(root)),
        ("lstat", str(root)),
    ]


def test_admit_root_accepts_an_empty_chain_mount_anchor(
    tmp_path: Path,
) -> None:
    lstat_calls: list[str] = []
    authority = RootAuthority(str(tmp_path), str(tmp_path), VOLUME)

    admit_root(
        authority,
        anchor_probe=lambda _path: str(tmp_path),
        lstat=lambda path: lstat_calls.append(path) or _stat(directory=True),
        volume_probe=lambda _path: _volume(str(tmp_path)),
    )

    assert lstat_calls == []


def test_anchor_change_stops_before_chain_or_volume(tmp_path: Path) -> None:
    root = tmp_path / "reviewed" / "managed"
    authority = RootAuthority(str(root), str(tmp_path / "reviewed"), VOLUME)

    with pytest.raises(RootAuthorityError) as raised:
        admit_root(
            authority,
            anchor_probe=lambda _path: str(tmp_path / "foreign"),
            lstat=lambda _path: (_ for _ in ()).throw(
                AssertionError("changed anchor reached root stat")
            ),
            volume_probe=lambda _path: (_ for _ in ()).throw(
                AssertionError("changed anchor reached volume probe")
            ),
        )

    assert raised.value.issue is RootAuthorityIssue.ANCHOR_CHANGED


@pytest.mark.parametrize(
    ("observed", "issue"),
    (
        (
            _stat(
                directory=True,
                attributes=(
                    FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_OFFLINE
                ),
            ),
            RootAuthorityIssue.PLACEHOLDER_COMPONENT,
        ),
        (
            _stat(
                directory=True,
                attributes=FILE_ATTRIBUTE_REPARSE_POINT,
            ),
            RootAuthorityIssue.REPARSE_COMPONENT,
        ),
        (_stat(), RootAuthorityIssue.NON_DIRECTORY_COMPONENT),
    ),
)
def test_unsafe_root_component_stops_before_volume(
    tmp_path: Path,
    observed: SimpleNamespace,
    issue: RootAuthorityIssue,
) -> None:
    authority = RootAuthority(str(tmp_path / "managed"), str(tmp_path), VOLUME)

    with pytest.raises(RootAuthorityError) as raised:
        admit_root(
            authority,
            anchor_probe=lambda _path: str(tmp_path),
            lstat=lambda _path: observed,
            volume_probe=lambda _path: (_ for _ in ()).throw(
                AssertionError("unsafe root reached volume probe")
            ),
        )

    assert raised.value.issue is issue


def test_volume_change_is_typed_after_safe_chain(tmp_path: Path) -> None:
    authority = RootAuthority(str(tmp_path / "managed"), str(tmp_path), VOLUME)

    with pytest.raises(RootAuthorityError) as raised:
        admit_root(
            authority,
            anchor_probe=lambda _path: str(tmp_path),
            lstat=lambda _path: _stat(directory=True),
            volume_probe=lambda _path: _volume(
                str(tmp_path),
                VolumeId("DEADBEEF", "NTFS"),
            ),
        )

    assert raised.value.issue is RootAuthorityIssue.VOLUME_CHANGED


@pytest.mark.parametrize(
    ("failure_stage", "issue"),
    (
        ("anchor", RootAuthorityIssue.ANCHOR_UNAVAILABLE),
        ("component", RootAuthorityIssue.COMPONENT_UNAVAILABLE),
        ("volume", RootAuthorityIssue.VOLUME_UNAVAILABLE),
    ),
)
def test_native_probe_failures_retain_their_authority_stage(
    tmp_path: Path,
    failure_stage: str,
    issue: RootAuthorityIssue,
) -> None:
    authority = RootAuthority(str(tmp_path / "managed"), str(tmp_path), VOLUME)

    def find_anchor(_path: str) -> str:
        if failure_stage == "anchor":
            raise OSError("anchor unavailable")
        return str(tmp_path)

    def lstat(_path: str) -> SimpleNamespace:
        if failure_stage == "component":
            raise PermissionError("component unavailable")
        return _stat(directory=True)

    def find_volume(_path: str) -> NativeVolumeInfo:
        if failure_stage == "volume":
            raise OSError("volume unavailable")
        return _volume(str(tmp_path))

    with pytest.raises(RootAuthorityError) as raised:
        admit_root(
            authority,
            anchor_probe=find_anchor,
            lstat=lstat,
            volume_probe=find_volume,
        )

    assert raised.value.issue is issue


def test_second_anchor_change_precedes_volume_identity_acceptance(
    tmp_path: Path,
) -> None:
    authority = RootAuthority(str(tmp_path / "managed"), str(tmp_path), VOLUME)

    with pytest.raises(RootAuthorityError) as raised:
        admit_root(
            authority,
            anchor_probe=lambda _path: str(tmp_path),
            lstat=lambda _path: _stat(directory=True),
            volume_probe=lambda _path: _volume(
                str(tmp_path / "foreign"),
                VolumeId("DEADBEEF", "NTFS"),
            ),
        )

    assert raised.value.issue is RootAuthorityIssue.ANCHOR_CHANGED


@pytest.mark.parametrize(
    "device_id",
    (None, r"\\.\C:\device-namespace"),
    ids=("missing", "invalid"),
)
def test_missing_or_invalid_second_anchor_is_unavailable(
    tmp_path: Path,
    device_id: str | None,
) -> None:
    authority = RootAuthority(str(tmp_path / "managed"), str(tmp_path), VOLUME)
    observed = NativeVolumeInfo(
        VOLUME,
        VolumeEvidence("Reviewed", device_id),
        255,
        0,
    )

    with pytest.raises(RootAuthorityError) as raised:
        admit_root(
            authority,
            anchor_probe=lambda _path: str(tmp_path),
            lstat=lambda _path: _stat(directory=True),
            volume_probe=lambda _path: observed,
        )

    assert raised.value.issue is RootAuthorityIssue.ANCHOR_UNAVAILABLE


@pytest.mark.skipif(os.name != "nt", reason="Windows lexical root shapes")
@pytest.mark.parametrize(
    ("root", "anchor", "expected_component_count"),
    (
        (r"C:\managed", "C:\\", 1),
        (r"\\server\share\managed", "\\\\server\\share\\", 1),
        (r"C:\mounted-volume", r"C:\mounted-volume", 0),
    ),
    ids=("drive", "unc", "folder-mount"),
)
def test_injected_windows_root_shapes_preserve_their_anchor_boundary(
    root: str,
    anchor: str,
    expected_component_count: int,
) -> None:
    authority = RootAuthority(root, anchor, VOLUME)
    components: list[str] = []

    admit_root(
        authority,
        anchor_probe=lambda _path: anchor,
        lstat=lambda path: components.append(path) or _stat(directory=True),
        volume_probe=lambda _path: _volume(
            authority.reviewed_anchor or anchor
        ),
    )

    assert len(components) == expected_component_count
    if components:
        assert os.path.normcase(
            os.path.normpath(components[-1])
        ) == os.path.normcase(os.path.normpath(authority.logical_root))


def test_injected_long_total_root_path_is_admitted_without_native_resolution(
    tmp_path: Path,
) -> None:
    anchor = tmp_path / "mount"
    root = anchor.joinpath(*(character * 90 for character in "abc"))
    authority = RootAuthority(str(root), str(anchor), VOLUME)
    components: list[str] = []

    assert len(authority.logical_root) > 260
    admit_root(
        authority,
        anchor_probe=lambda _path: str(anchor),
        lstat=lambda path: components.append(path) or _stat(directory=True),
        volume_probe=lambda _path: _volume(str(anchor)),
    )

    assert components[-1] == authority.logical_root


def test_existing_relative_chain_admits_directories_and_an_ordinary_leaf(
    tmp_path: Path,
) -> None:
    authority = RootAuthority(str(tmp_path))
    expected = [
        str(tmp_path / "folder"),
        str(tmp_path / "folder" / "payload.bin"),
    ]
    observed: list[str] = []

    def lstat(path: str) -> SimpleNamespace:
        observed.append(path)
        return _stat(directory=path == expected[0])

    assert admit_existing_relative_chain(
        authority,
        r"folder\payload.bin",
        lstat=lstat,
    )

    assert observed == expected


def test_existing_relative_chain_stops_at_first_missing_component(
    tmp_path: Path,
) -> None:
    authority = RootAuthority(str(tmp_path))
    observed: list[str] = []

    def lstat(path: str) -> SimpleNamespace:
        observed.append(path)
        if len(observed) == 2:
            raise FileNotFoundError(path)
        return _stat(directory=True)

    assert not admit_existing_relative_chain(
        authority,
        r"one\missing\untouched.bin",
        lstat=lstat,
    )

    assert observed == [
        str(tmp_path / "one"),
        str(tmp_path / "one" / "missing"),
    ]


def test_existing_relative_chain_reports_a_missing_final_leaf(
    tmp_path: Path,
) -> None:
    authority = RootAuthority(str(tmp_path))
    observed: list[str] = []

    def lstat(path: str) -> SimpleNamespace:
        observed.append(path)
        if len(observed) == 2:
            raise FileNotFoundError(path)
        return _stat(directory=True)

    assert not admit_existing_relative_chain(
        authority,
        r"folder\missing.bin",
        lstat=lstat,
    )
    assert observed == [
        str(tmp_path / "folder"),
        str(tmp_path / "folder" / "missing.bin"),
    ]


def test_existing_relative_chain_can_admit_only_subject_ancestors(
    tmp_path: Path,
) -> None:
    authority = RootAuthority(str(tmp_path))
    observed: list[str] = []

    assert admit_existing_relative_chain(
        authority,
        r"folder\payload.bin",
        lstat=lambda path: observed.append(path) or _stat(directory=True),
        include_leaf=False,
    )

    assert observed == [str(tmp_path / "folder")]


@pytest.mark.parametrize(
    ("observed", "issue"),
    (
        (
            _stat(
                directory=True,
                attributes=FILE_ATTRIBUTE_REPARSE_POINT,
            ),
            RootAuthorityIssue.REPARSE_COMPONENT,
        ),
        (_stat(), RootAuthorityIssue.NON_DIRECTORY_COMPONENT),
    ),
)
def test_existing_relative_chain_refuses_an_unsafe_intermediate(
    tmp_path: Path,
    observed: SimpleNamespace,
    issue: RootAuthorityIssue,
) -> None:
    authority = RootAuthority(str(tmp_path))

    with pytest.raises(RootAuthorityError) as raised:
        admit_existing_relative_chain(
            authority,
            r"unsafe\payload.bin",
            lstat=lambda _path: observed,
        )

    assert raised.value.issue is issue


@pytest.mark.parametrize(
    ("leaf", "issue"),
    (
        (
            _stat(
                attributes=(
                    FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_OFFLINE
                ),
            ),
            RootAuthorityIssue.PLACEHOLDER_COMPONENT,
        ),
        (
            _stat(attributes=FILE_ATTRIBUTE_REPARSE_POINT),
            RootAuthorityIssue.REPARSE_COMPONENT,
        ),
    ),
)
def test_existing_relative_chain_refuses_an_unsafe_final_leaf(
    tmp_path: Path,
    leaf: SimpleNamespace,
    issue: RootAuthorityIssue,
) -> None:
    authority = RootAuthority(str(tmp_path))
    final_leaf = str(tmp_path / "folder" / "payload.bin")

    with pytest.raises(RootAuthorityError) as raised:
        admit_existing_relative_chain(
            authority,
            r"folder\payload.bin",
            lstat=lambda path: leaf
            if path == final_leaf
            else _stat(directory=True),
        )

    assert raised.value.issue is issue


def test_existing_relative_chain_rejects_unsafe_relative_spelling(
    tmp_path: Path,
) -> None:
    with pytest.raises(PathValidationError, match="unsafe component"):
        admit_existing_relative_chain(
            RootAuthority(str(tmp_path)),
            r"..\escape.bin",
            lstat=lambda _path: _stat(),
        )


def test_shared_stat_classifiers_cover_windows_attribute_evidence() -> None:
    directory = _stat(attributes=FILE_ATTRIBUTE_DIRECTORY)
    reparse = _stat(attributes=FILE_ATTRIBUTE_REPARSE_POINT)
    placeholder = _stat(
        attributes=FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_OFFLINE
    )

    assert is_directory_stat(directory)
    assert is_reparse_stat(reparse)
    assert is_placeholder_stat(placeholder)


@pytest.mark.skipif(os.name != "nt", reason="Windows native volume probe")
def test_windows_native_anchor_and_volume_evidence_agree(
    tmp_path: Path,
) -> None:
    anchor = current_volume_anchor(tmp_path)
    evidence_anchor = observe_native_volume(tmp_path).evidence.device_id

    assert evidence_anchor is not None
    assert os.path.normcase(os.path.normpath(evidence_anchor)) == os.path.normcase(
        os.path.normpath(anchor)
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows native admission bindings")
@pytest.mark.parametrize("lowercase_reviewed_anchor", (False, True))
def test_default_admission_resolves_anchor_once_and_queries_it_directly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lowercase_reviewed_anchor: bool,
) -> None:
    calls: list[tuple[str, str]] = []
    anchor = str(tmp_path.anchor)

    def get_volume_path(path: str, output, _length: int) -> bool:
        calls.append(("anchor", path))
        output.value = to_extended_length_path(anchor)
        return True

    def get_volume_information(
        path: str, label, _label_length: int, serial, max_component,
        flags, filesystem, _filesystem_length: int,
    ) -> bool:
        calls.append(("volume", path))
        label.value = "Reviewed"
        serial._obj.value = int(VOLUME.serial, 16)
        max_component._obj.value = 255
        flags._obj.value = 0
        filesystem.value = "NTFS"
        return True

    monkeypatch.setattr(
        root_authority,
        "_WINDOWS",
        SimpleNamespace(
            get_volume_path=get_volume_path,
            get_volume_information=get_volume_information,
        ),
    )
    authority = RootAuthority(
        str(tmp_path),
        anchor.lower() if lowercase_reviewed_anchor else anchor,
        VOLUME,
    )

    admitted = admit_root(authority, lstat=lambda _path: _stat(directory=True))

    assert admitted == _volume(anchor)
    assert calls == [
        ("anchor", to_extended_length_path(str(tmp_path))),
        ("volume", to_extended_length_path(anchor)),
    ]


@pytest.mark.skipif(os.name != "nt", reason="Windows folder mount spelling")
def test_volume_at_admitted_folder_anchor_retains_required_separator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    anchor = str(tmp_path / "mounted-volume")

    def get_volume_information(
        path: str, label, _label_length: int, serial, max_component,
        flags, filesystem, _filesystem_length: int,
    ) -> bool:
        calls.append(path)
        label.value = "Reviewed"
        serial._obj.value = int(VOLUME.serial, 16)
        max_component._obj.value = 255
        filesystem.value = "NTFS"
        return True

    monkeypatch.setattr(
        root_authority,
        "_WINDOWS",
        SimpleNamespace(get_volume_information=get_volume_information),
    )

    admitted = observe_native_volume_at_anchor(anchor)

    assert calls == [to_extended_length_path(anchor) + "\\"]
    assert admitted.evidence.device_id == anchor + "\\"


@pytest.mark.skipif(os.name != "nt", reason="Windows root hold bindings")
@pytest.mark.parametrize("fail_inside", (False, True))
def test_root_hold_uses_directory_access_and_releases_on_every_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fail_inside: bool,
) -> None:
    calls: list[tuple] = []

    def create_file(*args):
        calls.append(("open", *args))
        return 122 + sum(call[0] == "open" for call in calls)

    def get_final_path(handle, output, _size, flags):
        calls.append(("final", handle, flags))
        output.value = to_extended_length_path(str(tmp_path))
        return len(output.value)

    monkeypatch.setattr(
        root_authority,
        "_WINDOWS",
        SimpleNamespace(
            get_drive_type=lambda _path: 3,
            create_file=create_file,
            close_handle=lambda handle: calls.append(("close", handle)),
            get_final_path=get_final_path,
        ),
    )
    authority = RootAuthority(str(tmp_path))

    def run_hold() -> None:
        with hold_root(authority) as hold:
            assert len(calls) == 1
            if fail_inside:
                raise OSError("admission or invocation failed")
            assert hold.confirm()
            assert hold.confirm()
            assert hold.fallback_reason is None
        assert not hold.confirm()

    if fail_inside:
        with pytest.raises(OSError, match="invocation failed"):
            run_hold()
    else:
        run_hold()

    opened = (
        "open", to_extended_length_path(str(tmp_path)),
        0x00000001, 0x00000003, None, 3, 0x02200000, None,
    )
    expected = [opened]
    if not fail_inside:
        expected.append(("final", 123, 0))
    assert calls == [*expected, ("close", 123)]


@pytest.mark.skipif(os.name != "nt", reason="Windows root hold bindings")
@pytest.mark.parametrize("surface", ("unc", "mapped", "unholdable"))
def test_root_hold_falls_back_for_remote_or_unholdable_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    surface: str,
) -> None:
    calls: list[str] = []

    def get_drive_type(_path: str) -> int:
        calls.append("drive")
        return 4 if surface == "mapped" else 3

    def create_file(*_args):
        calls.append("open")
        return root_authority._INVALID_HANDLE_VALUE

    monkeypatch.setattr(
        root_authority,
        "_WINDOWS",
        SimpleNamespace(
            get_drive_type=get_drive_type,
            create_file=create_file,
            close_handle=lambda _handle: calls.append("close"),
        ),
    )
    authority = RootAuthority(
        r"\\server\share\managed" if surface == "unc" else str(tmp_path)
    )

    with hold_root(authority) as hold:
        assert not hold.confirm()
        assert hold.fallback_reason == (
            "acquisition_failed" if surface == "unholdable" else "remote_root"
        )

    assert calls == {
        "unc": [], "mapped": ["drive"], "unholdable": ["drive", "open"],
    }[surface]


@pytest.mark.skipif(os.name != "nt", reason="Windows native root hold witness")
@pytest.mark.parametrize(
    ("attributes", "query_ok", "issue"),
    (
        (FILE_ATTRIBUTE_DIRECTORY, True, None),
        (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_OFFLINE, True, None),
        (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT, True,
         RootAuthorityIssue.REPARSE_COMPONENT),
        (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_OFFLINE,
         True, RootAuthorityIssue.PLACEHOLDER_COMPONENT),
        (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT | 0x00040000,
         True, RootAuthorityIssue.PLACEHOLDER_COMPONENT),
        (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT | 0x00400000,
         True, RootAuthorityIssue.PLACEHOLDER_COMPONENT),
        (0, True, RootAuthorityIssue.NON_DIRECTORY_COMPONENT),
        (FILE_ATTRIBUTE_DIRECTORY, False, RootAuthorityIssue.COMPONENT_UNAVAILABLE),
    ),
)
def test_root_hold_requires_fresh_attributes_without_reconfirming_or_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attributes: int,
    query_ok: bool,
    issue: RootAuthorityIssue | None,
) -> None:
    calls: list[str] = []

    def final_path(_handle, output, _size, _flags):
        calls.append("final")
        output.value = to_extended_length_path(str(tmp_path))
        return len(output.value)

    def query(handle, kind, output, size):
        calls.append("attributes")
        assert handle == 73 and kind == 0 and size == 40
        ctypes.cast(output, ctypes.POINTER(root_authority._FileBasicInfo)).contents.FileAttributes = attributes
        if not query_ok:
            ctypes.set_last_error(5)
        return query_ok

    monkeypatch.setattr(
        root_authority, "_WINDOWS",
        SimpleNamespace(
            get_drive_type=lambda _path: 3,
            create_file=lambda *_args: 73,
            get_final_path=final_path,
            get_file_information_ex=query,
            close_handle=lambda _handle: calls.append("close"),
        ),
    )
    with hold_root(RootAuthority(str(tmp_path))) as hold:
        with pytest.raises(RootAuthorityError) as unconfirmed:
            hold.require_ordinary()
        assert unconfirmed.value.issue is RootAuthorityIssue.COMPONENT_UNAVAILABLE
        assert calls == []
        assert hold.confirm()
        for _ in range(2):
            if issue is None:
                hold.require_ordinary()
            else:
                with pytest.raises(RootAuthorityError) as refused:
                    hold.require_ordinary()
                assert refused.value.issue is issue
                if not query_ok:
                    assert refused.value.__cause__.winerror == 5
            assert hold.confirm()
            assert hold.fallback_reason is None
    with pytest.raises(RootAuthorityError):
        hold.require_ordinary()
    assert calls == ["final", "attributes", "attributes", "close"]


@pytest.mark.skipif(os.name != "nt", reason="Windows native root hold witness")
@pytest.mark.parametrize("fail_inside", (False, True))
def test_native_root_hold_blocks_root_and_ancestor_mutations_and_releases(
    tmp_path: Path,
    fail_inside: bool,
) -> None:
    parent = tmp_path / "parent"
    root = parent / "managed"
    root.mkdir(parents=True)
    moved_root = parent / "moved"

    def run_hold() -> None:
        with hold_root(RootAuthority(str(root))) as hold:
            volume = admit_root(RootAuthority(str(root)))
            confirmed = hold.confirm()
            if volume.volume_id.fs_type in {"NTFS", "EXFAT"}:
                assert confirmed
            if not confirmed:
                root.rename(moved_root)
                moved_root.rename(root)
                if fail_inside:
                    raise OSError("invocation failed")
                return
            hold.require_ordinary()
            with pytest.raises(OSError) as rename_error:
                root.rename(moved_root)
            assert rename_error.value.winerror == 32
            with pytest.raises(OSError) as ancestor_error:
                parent.rename(tmp_path / "moved-parent")
            assert ancestor_error.value.winerror == 5
            with pytest.raises(OSError) as deletion_error:
                root.rmdir()
            assert deletion_error.value.winerror == 32

            child = root / "child"
            child.mkdir()
            payload = child / "payload.bin"
            payload.write_bytes(b"held-root payload")
            renamed = child / "renamed.bin"
            payload.rename(renamed)
            renamed.unlink()
            child.rename(root / "renamed-child")
            (root / "renamed-child").rmdir()
            if fail_inside:
                raise OSError("invocation failed")

    if fail_inside:
        with pytest.raises(OSError, match="invocation failed"):
            run_hold()
    else:
        run_hold()
    root.rename(moved_root)
    moved_root.rmdir()
    parent.rmdir()


@pytest.mark.skipif(os.name != "nt", reason="Windows root hold corroboration")
@pytest.mark.parametrize(
    ("variation", "reason"),
    (
        ("drive-case", None),
        ("case", "case_mismatch"),
        ("short-name", "possible_short_name_alias"),
        ("mount", "mount_alias"),
        ("namespace", "namespace_mismatch"),
        ("unavailable", "final_path_unavailable"),
        ("oversized", "final_path_unavailable"),
        ("invalid", "final_path_unavailable"),
    ),
)
def test_root_hold_confirmation_requires_exact_namespace_and_classifies_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    variation: str,
    reason: str | None,
) -> None:
    opened: list[int] = []
    closed: list[int] = []
    final_calls: list[tuple[int, int]] = []
    root = tmp_path / ("MANAGE~1" if variation == "short-name" else "managed")
    authority = RootAuthority(str(root))

    def create_file(*_args):
        handle = 123 + len(opened)
        opened.append(handle)
        return handle

    def get_final_path(handle, output, size, flags):
        final_calls.append((handle, flags))
        if variation == "unavailable":
            return 0
        if variation == "oversized":
            return size + 1
        final = authority.logical_root
        if variation == "drive-case":
            final = final[:1].swapcase() + final[1:]
        elif variation == "case":
            final = final.swapcase()
        elif variation == "short-name":
            final = str(tmp_path / "managed-directory")
        elif variation == "mount":
            final = ("E" if final[0].upper() != "E" else "F") + final[1:]
        elif variation == "namespace":
            final = str(tmp_path / "other")
        output.value = (
            r"\\.\unsupported-device" if variation == "invalid"
            else to_extended_length_path(final)
        )
        return len(output.value)

    monkeypatch.setattr(
        root_authority,
        "_WINDOWS",
        SimpleNamespace(
            get_drive_type=lambda _path: 3,
            create_file=create_file,
            close_handle=closed.append,
            get_final_path=get_final_path,
        ),
    )

    with hold_root(authority) as hold:
        assert hold.confirm() is (reason is None)
        assert closed == ([] if reason is None else [123])
        assert hold.confirm() is (reason is None)
        assert hold.fallback_reason == reason
    assert not hold.confirm()
    assert final_calls == [(123, 0)]
    assert opened == [123]
    assert closed == [123]


@pytest.mark.skipif(os.name != "nt", reason="Windows junction hold regression")
@pytest.mark.parametrize("swaps", (1, 2))
def test_native_root_hold_refuses_binding_after_intermediate_junction_replacement(
    tmp_path: Path,
    swaps: int,
) -> None:
    old_target = tmp_path / "old-target"
    old_root = old_target / "managed"
    old_root.mkdir(parents=True)
    if observe_native_volume(old_target).volume_id.fs_type != "NTFS":
        pytest.skip("intermediate junction fixture requires NTFS")
    link = tmp_path / "link"
    environment = os.environ.copy()
    environment["NAMISYNC_TEST_LINK"] = str(link)
    environment["NAMISYNC_TEST_TARGET"] = str(old_target)
    def create_junction() -> None:
        created = subprocess.run(
            (
                "pwsh", "-NoProfile", "-NonInteractive", "-Command",
                "New-Item -ItemType Junction -Path $env:NAMISYNC_TEST_LINK "
                "-Target $env:NAMISYNC_TEST_TARGET -ErrorAction Stop | Out-Null",
            ),
            capture_output=True, text=True, env=environment, check=False,
        )
        assert created.returncode == 0, created.stderr

    create_junction()
    logical_root = link / "managed"
    authority = RootAuthority(str(logical_root))

    with hold_root(authority) as hold:
        link.rmdir()
        link.mkdir()
        logical_root.mkdir()
        admit_root(authority)
        if swaps == 2:
            logical_root.rmdir()
            link.rmdir()
            create_junction()
        assert not hold.confirm()
        assert not hold.confirm()
        assert hold.fallback_reason == "namespace_mismatch"
        old_root.rename(old_target / "released-managed")
        if swaps == 2:
            link.rmdir()
            link.mkdir()
            logical_root.mkdir()
        logical_root.rename(link / "moved-managed")
