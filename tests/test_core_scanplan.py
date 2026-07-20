"""Shared path and immutable evidence contract tests."""

from __future__ import annotations

import json

import pytest

from namisync.core.models import IgnoreSet
from namisync.core.pathing import PathValidationError, normalize_relative_path, validate_relative_path
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


def test_relative_path_key_normalizes_separator_and_ordinary_case_without_casefold_expansion() -> None:
    assert normalize_relative_path("Folder/file.txt") == normalize_relative_path(r"folder\FILE.TXT")
    assert normalize_relative_path("Straße.txt") != normalize_relative_path("strasse.txt")


def test_long_relative_path_is_valid() -> None:
    path = "\\".join(["directory" * 10] * 4 + ["file.bin"])
    assert len(path) > 260
    assert validate_relative_path(path) == path


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


def test_ignore_set_matches_only_owned_exact_shapes() -> None:
    ignores = IgnoreSet.for_owned_paths([r".namisync\ledger.db", r".namisync\history.db"])
    assert ignores.excludes(r".namisync\ledger.db", is_directory=False)
    assert ignores.excludes(r".namisync\ledger.db-wal", is_directory=False)
    assert ignores.excludes(r".namisync\history.db-shm", is_directory=False)
    assert ignores.excludes(".synctrash", is_directory=True)
    assert ignores.excludes("movie.bin.synctmp-" + "a" * 32 + "-" + "b" * 32, is_directory=False)
    assert not ignores.excludes("customer.db", is_directory=False)
    assert not ignores.excludes("my.synctmp-notes.txt", is_directory=False)
    assert not ignores.excludes("customer.sha256", is_directory=False)
