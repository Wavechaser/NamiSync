"""Shared path and immutable evidence contract tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from namisync.core.models import IgnoreSet
from namisync.core.pathing import (
    PathValidationError,
    from_extended_length_path,
    lexical_absolute_path,
    lexical_path_chain,
    logical_error_text,
    normalize_relative_path,
    to_extended_length_path,
    validate_relative_path,
)
from namisync.core.planning import canonical_json_bytes


@pytest.mark.parametrize(
    "value",
    [
        r"C:\escape.txt",
        r"\\server\share\escape.txt",
        r"\\?\C:\escape.txt",
        r"\\.\C:\escape.txt",
        r"..\escape.txt",
        r"folder\..\escape.txt",
        r"folder\\file.txt",
        r"folder\file.txt.",
        r"folder\NUL.txt",
        "folder\x00file.txt",
        "bad_" + chr(0xDCFF) + ".txt",
    ],
)
def test_relative_path_validation_rejects_windows_escape_and_ambiguity(value: str) -> None:
    with pytest.raises(PathValidationError):
        validate_relative_path(value)


@pytest.mark.parametrize(
    "basename",
    [
        "conin$",
        "ConOut$",
        "cOm¹",
        "COM²",
        "com³",
        "lPt¹",
        "LPT²",
        "lpt³",
    ],
)
@pytest.mark.parametrize("suffix", ["", ".txt"])
def test_relative_path_validation_rejects_additional_documented_windows_devices(
    basename: str,
    suffix: str,
) -> None:
    with pytest.raises(PathValidationError, match="Windows device"):
        validate_relative_path(f"folder\\{basename}{suffix}")


def test_relative_path_key_normalizes_separator_and_ordinary_case_without_casefold_expansion() -> None:
    assert normalize_relative_path("Folder/file.txt") == normalize_relative_path(r"folder\FILE.TXT")
    assert normalize_relative_path("Straße.txt") != normalize_relative_path("strasse.txt")


def test_long_relative_path_is_valid() -> None:
    path = "\\".join(["directory" * 10] * 4 + ["file.bin"])
    assert len(path) > 260
    assert validate_relative_path(path) == path


@pytest.mark.skipif(os.name != "nt", reason="Windows native path spelling")
@pytest.mark.parametrize(
    ("logical", "native"),
    [
        (r"C:\folder\file.bin", r"\\?\C:\folder\file.bin"),
        (
            r"\\server\share\folder\file.bin",
            r"\\?\UNC\server\share\folder\file.bin",
        ),
    ],
)
def test_extended_length_path_round_trips_without_changing_logical_identity(
    logical: str,
    native: str,
) -> None:
    assert to_extended_length_path(logical) == native
    assert to_extended_length_path(native) == native
    assert from_extended_length_path(native) == logical
    assert from_extended_length_path(logical) == logical


def test_lexical_absolute_path_normalizes_without_requiring_an_existing_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    assert lexical_absolute_path("configured-root") == str(
        tmp_path / "configured-root"
    )


def test_lexical_path_chain_excludes_a_trusted_mount_but_includes_every_child(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mounted-volume"
    root = mount / "parent" / "managed"

    assert lexical_path_chain(root, trusted_anchor=mount) == (
        str(mount / "parent"),
        str(root),
    )
    assert lexical_path_chain(mount, trusted_anchor=mount) == ()


def test_lexical_path_chain_refuses_a_path_outside_its_trusted_anchor(
    tmp_path: Path,
) -> None:
    with pytest.raises(PathValidationError, match="trusted anchor"):
        lexical_path_chain(
            tmp_path / "other" / "managed",
            trusted_anchor=tmp_path / "mounted-volume",
        )


@pytest.mark.skipif(os.name != "nt", reason="requires Windows reparse points")
def test_lexical_absolute_path_does_not_follow_a_final_root_reparse(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    configured = tmp_path / "configured-root"
    try:
        configured.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory reparse creation is unavailable: {error}")

    assert lexical_absolute_path(configured) == str(configured)
    assert lexical_absolute_path(configured) != str(target)


@pytest.mark.parametrize(
    "path",
    [
        r"\\.\C:\folder\file.bin",
        r"\??\C:\folder\file.bin",
        r"\\??\C:\folder\file.bin",
        r"\\?\GLOBALROOT\Device\HarddiskVolume1\file.bin",
        r"\\?\UNC\server",
    ],
)
def test_extended_length_conversion_refuses_non_filesystem_device_namespaces(
    path: str,
) -> None:
    with pytest.raises(PathValidationError):
        to_extended_length_path(path)


def test_os_error_rendering_rewrites_only_exact_extended_filename_fields() -> None:
    native = r"\\?\C:\deep\payload.bin"
    error = FileNotFoundError(2, "missing", native)
    rendered = logical_error_text(error)
    assert repr(r"C:\deep\payload.bin") in rendered
    assert "\\\\?\\" not in rendered

    arbitrary = RuntimeError(r"documentation mentions \\?\C:\deep\payload.bin")
    assert logical_error_text(arbitrary) == str(arbitrary)


@pytest.mark.parametrize(
    "path",
    [
        r"\\?\C:\safe\root.",
        r"\\?\UNC\.\C$\folder",
        r"\\?\UNC\?\C$\folder",
        r"\\?\C:\safe/folder",
        r"\\?\UNC\server/share\folder",
    ],
)
def test_extended_conversion_refuses_ambiguous_absolute_components(
    path: str,
) -> None:
    with pytest.raises(PathValidationError):
        to_extended_length_path(path)
    if path.startswith("\\\\?\\"):
        with pytest.raises(PathValidationError):
            from_extended_length_path(path)


@pytest.mark.skipif(os.name != "nt", reason="Windows absolute path rules")
@pytest.mark.parametrize(
    "path",
    [r"C:\safe\root.", r"C:\safe\root ", r"C:\safe\CON"],
)
def test_native_conversion_refuses_ambiguous_ordinary_absolute_components(
    path: str,
) -> None:
    with pytest.raises(PathValidationError):
        to_extended_length_path(path)


def test_canonical_json_preserves_valid_unicode_and_safely_escapes_lone_surrogates() -> None:
    valid = {"path": "caf\u00e9.txt"}
    assert canonical_json_bytes(valid) == json.dumps(
        valid,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    hostile = {"path": "bad_" + chr(0xDCFF) + ".txt"}
    encoded = canonical_json_bytes(hostile)
    assert b"bad_\\udcff.txt" in encoded
    assert json.loads(encoded.decode("utf-8")) == hostile
    assert encoded != canonical_json_bytes({"path": r"bad_\udcff.txt"})


def test_ignore_set_matches_only_built_in_shapes() -> None:
    ignores = IgnoreSet()
    assert ignores.excludes("desktop.ini", is_directory=False)
    assert ignores.excludes("THUMBS.DB", is_directory=False)
    assert ignores.excludes(".synctrash", is_directory=True)
    assert ignores.excludes("movie.bin.synctmp-" + "a" * 32 + "-" + "b" * 32, is_directory=False)
    assert not ignores.excludes(r".namisync\ledger.db", is_directory=False)
    assert not ignores.excludes("customer.db", is_directory=False)
    assert not ignores.excludes("my.synctmp-notes.txt", is_directory=False)
    assert not ignores.excludes("customer.sha256", is_directory=False)
