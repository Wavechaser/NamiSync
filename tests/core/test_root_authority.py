from __future__ import annotations

import os
import stat as stat_module
from pathlib import Path
from types import SimpleNamespace

import pytest

import namisync.core.root_authority as authority_module
from namisync.core.models import VolumeEvidence, VolumeId
from namisync.core.pathing import PathValidationError, trusted_volume_anchor
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
    is_directory_stat,
    is_placeholder_stat,
    is_reparse_stat,
    observe_native_volume,
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


def test_pathing_trusted_anchor_is_a_live_compatibility_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str] = []

    def anchor(path: str | os.PathLike[str]) -> str:
        observed.append(os.fspath(path))
        return str(tmp_path)

    monkeypatch.setattr(authority_module, "current_volume_anchor", anchor)

    assert trusted_volume_anchor(tmp_path / "managed") == str(tmp_path)
    assert observed == [os.fspath(tmp_path / "managed")]


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
