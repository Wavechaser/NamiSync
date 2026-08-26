"""Pure verifier contract tests."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from namisync.core.integrity import (
    INTEGRITY_CANDIDATE_RETAINED_BYTE_LIMIT,
    INTEGRITY_CANDIDATE_ROW_LIMIT,
    INTEGRITY_CANDIDATE_RETAINED_BYTES_MESSAGE,
    INTEGRITY_CANDIDATE_ROWS_MESSAGE,
    IntegrityCandidateLimitAxis,
    IntegrityCandidateLimitError,
    IntegrityCandidateLimitExceeded,
    IntegritySelection,
    PostCopySelection,
    VerifierContext,
    matches_expected_stat,
)
from namisync.core.models import (
    EntryKind,
    FileIdentity,
    FileStat,
    MetadataSnapshot,
)
from namisync.core.session import RunContext
from namisync.core.scalars import MAX_SAFE_INTEGER, MAX_SIGNED_64, ScalarDomainError


_IDENTITY = FileIdentity("A1B2C3D4", 7)
_SUBJECT = FileStat(
    kind=EntryKind.FILE,
    size=3,
    mtime_ns=100,
    file_identity=_IDENTITY,
    nlink=1,
    metadata=MetadataSnapshot(attributes=0, created_ns=50),
)


def test_integrity_candidate_limit_facts_are_exact_and_typed() -> None:
    rows = IntegrityCandidateLimitExceeded.rows()
    retained_bytes = IntegrityCandidateLimitExceeded.retained_bytes()

    assert rows == IntegrityCandidateLimitExceeded(
        reason="integrity_candidate_limit_exceeded",
        axis=IntegrityCandidateLimitAxis.ROWS,
        row_limit=INTEGRITY_CANDIDATE_ROW_LIMIT,
        byte_limit=None,
    )
    assert retained_bytes == IntegrityCandidateLimitExceeded(
        reason="integrity_candidate_limit_exceeded",
        axis=IntegrityCandidateLimitAxis.RETAINED_BYTES,
        row_limit=None,
        byte_limit=INTEGRITY_CANDIDATE_RETAINED_BYTE_LIMIT,
    )
    assert IntegrityCandidateLimitError(rows).args == (
        INTEGRITY_CANDIDATE_ROWS_MESSAGE,
    )
    assert IntegrityCandidateLimitError(retained_bytes).args == (
        INTEGRITY_CANDIDATE_RETAINED_BYTES_MESSAGE,
    )


@pytest.mark.parametrize(
    "fact",
    (
        IntegrityCandidateLimitExceeded(
            "integrity_candidate_limit_exceeded",
            IntegrityCandidateLimitAxis.ROWS,
            INTEGRITY_CANDIDATE_ROW_LIMIT,
            None,
        ),
        IntegrityCandidateLimitExceeded(
            "integrity_candidate_limit_exceeded",
            IntegrityCandidateLimitAxis.RETAINED_BYTES,
            None,
            INTEGRITY_CANDIDATE_RETAINED_BYTE_LIMIT,
        ),
    ),
)
def test_integrity_candidate_limit_fact_rejects_mutated_closed_shape(
    fact: IntegrityCandidateLimitExceeded,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        replace(fact, axis=fact.axis.value)
    with pytest.raises(ValueError):
        replace(fact, row_limit=1)
    with pytest.raises(ValueError):
        replace(fact, byte_limit=1)


def test_integrity_candidate_limit_fact_rejects_hidden_graph_subclasses() -> None:
    class HiddenReason(str):
        pass

    class HiddenFact(IntegrityCandidateLimitExceeded):
        pass

    reason = HiddenReason("integrity_candidate_limit_exceeded")
    reason.hidden = object()
    with pytest.raises(TypeError, match="reason has the wrong type"):
        IntegrityCandidateLimitExceeded(
            reason,
            IntegrityCandidateLimitAxis.ROWS,
            INTEGRITY_CANDIDATE_ROW_LIMIT,
            None,
        )

    hidden_fact = HiddenFact(
        "integrity_candidate_limit_exceeded",
        IntegrityCandidateLimitAxis.ROWS,
        INTEGRITY_CANDIDATE_ROW_LIMIT,
        None,
    )
    hidden_fact.hidden = object()
    with pytest.raises(TypeError, match="requires its typed fact"):
        IntegrityCandidateLimitError(hidden_fact)

    source = IntegrityCandidateLimitExceeded.rows()
    owned = IntegrityCandidateLimitError(source).fact
    assert owned == source
    assert owned is not source

    corrupted = IntegrityCandidateLimitExceeded.rows()
    object.__setattr__(corrupted, "reason", reason)
    with pytest.raises(TypeError, match="reason has the wrong type"):
        IntegrityCandidateLimitError(corrupted)


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
        ("post_copy_items_total", MAX_SAFE_INTEGER + 1, ValueError),
        ("post_copy_bytes_total", MAX_SIGNED_64 + 1, ValueError),
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


def test_post_copy_byte_admission_uses_scalar64_not_safeint() -> None:
    value = MAX_SAFE_INTEGER + 1

    context = _verifier_context(
        post_copy_items_total=1,
        post_copy_bytes_total=value,
    )

    assert context.post_copy_bytes_total == value


@pytest.mark.parametrize(
    "selection",
    (
        IntegritySelection(
            (),
            _processed_bytes=MAX_SIGNED_64,
            _bytes_total_high_water=MAX_SIGNED_64,
        ),
        PostCopySelection((), _processed_bytes=MAX_SIGNED_64),
    ),
)
def test_selection_byte_counters_fail_closed_on_post_admission_overflow(
    selection: IntegritySelection | PostCopySelection,
) -> None:
    with pytest.raises(ScalarDomainError, match="exceeds"):
        selection.note_bytes_processed(1)
