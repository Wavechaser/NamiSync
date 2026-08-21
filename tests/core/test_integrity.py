"""Pure verifier contract tests."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from namisync.core.integrity import VerifierContext, matches_expected_stat
from namisync.core.models import (
    EntryKind,
    FileIdentity,
    FileStat,
    MetadataSnapshot,
)
from namisync.core.session import RunContext


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


def _verifier_context(**changes: object) -> VerifierContext:
    values = {
        "run": RunContext(lambda _body: None, lambda: None),
        "clock": SimpleNamespace(now=lambda: None),
        "hasher_factory": lambda: None,
        **changes,
    }
    return VerifierContext(**values)


def test_post_copy_progress_admission_is_paired() -> None:
    with pytest.raises(ValueError, match="admission must be paired"):
        _verifier_context(post_copy_items_total=1)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    (
        ("post_copy_items_total", True, TypeError),
        ("post_copy_bytes_total", True, TypeError),
        ("post_copy_items_total", -1, ValueError),
        ("post_copy_bytes_total", -1, ValueError),
        ("post_copy_items_total", 1 << 53, ValueError),
        ("post_copy_bytes_total", 1 << 53, ValueError),
    ),
)
def test_post_copy_progress_admission_uses_wire_safe_counters(
    field: str,
    value: object,
    error: type[Exception],
) -> None:
    values = {
        "post_copy_items_total": 1,
        "post_copy_bytes_total": 1,
        field: value,
    }
    with pytest.raises(error):
        _verifier_context(**values)
