"""Pure verifier contract tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from namisync.core.integrity import matches_expected_stat
from namisync.core.models import (
    EntryKind,
    FileIdentity,
    FileStat,
    MetadataSnapshot,
)


_IDENTITY = FileIdentity("A1B2C3D4", 7)
_SUBJECT = FileStat(
    kind=EntryKind.FILE,
    size=3,
    mtime_ns=100,
    file_identity=_IDENTITY,
    nlink=1,
    metadata=MetadataSnapshot(attributes=0, created_ns=50),
)


@pytest.mark.parametrize(
    ("expected", "actual", "matches"),
    (
        (_SUBJECT, _SUBJECT, True),
        (
            replace(_SUBJECT, file_identity=None),
            replace(_SUBJECT, file_identity=FileIdentity("DEADBEEF", 9)),
            True,
        ),
        (_SUBJECT, replace(_SUBJECT, file_identity=None), False),
        (_SUBJECT, replace(_SUBJECT, kind=EntryKind.DIRECTORY), False),
        (_SUBJECT, replace(_SUBJECT, size=4), False),
        (_SUBJECT, replace(_SUBJECT, mtime_ns=101), False),
    ),
)
def test_expected_stat_match_contract(
    expected: FileStat,
    actual: FileStat,
    matches: bool,
) -> None:
    assert matches_expected_stat(expected, actual) is matches
