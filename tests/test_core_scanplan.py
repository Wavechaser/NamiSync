"""Shared path and immutable evidence contract tests."""

from __future__ import annotations

import pytest

from namisync.core.models import IgnoreSet
from namisync.core.pathing import PathValidationError, normalize_relative_path, validate_relative_path


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
