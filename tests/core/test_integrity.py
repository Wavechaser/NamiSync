"""Pure verifier contract tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields, replace
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from namisync.core.evidence import Attestation, ContentEvidence, Provenance
from namisync.core.integrity import (
    INTEGRITY_CANDIDATE_RETAINED_BYTE_LIMIT,
    INTEGRITY_CANDIDATE_ROW_LIMIT,
    INTEGRITY_CANDIDATE_RETAINED_BYTES_MESSAGE,
    INTEGRITY_CANDIDATE_ROWS_MESSAGE,
    MAX_VERIFIER_CHUNK_SIZE,
    IntegrityCandidateLimitAxis,
    IntegrityCandidateLimitError,
    IntegrityCandidateLimitExceeded,
    IntegrityMode,
    IntegrityOutcome,
    IntegrityRecordCommand,
    IntegrityResult,
    IntegritySelection,
    IntegritySelectionItem,
    InventoryState,
    PostCopyCandidate,
    PostCopySelection,
    VerifierContext,
    matches_expected_stat,
    revalidate_integrity_selection_authority,
    revalidate_post_copy_selection_authority,
    snapshot_integrity_selection_authority,
    snapshot_post_copy_selection_authority,
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
_OBSERVED_AT = datetime(2026, 8, 30, tzinfo=timezone.utc)


def _selection_subject(
    kind: str,
    number: int,
) -> IntegritySelectionItem | PostCopyCandidate:
    item_id = f"{kind}-{number}"
    display_path = f"folder\\file-{number}.bin"
    if kind == "integrity":
        return IntegritySelectionItem(
            item_id=item_id,
            row_id=f"row-{number}",
            location_id="location",
            root=Path("C:/selection-root"),
            rel_path_key=display_path,
            display_path=display_path,
            expected_state=InventoryState.PRESENT,
            expected_stat=_SUBJECT,
            baseline=None,
            scope_token="scope",
        )
    return PostCopyCandidate(
        item_id=item_id,
        root=Path("C:/selection-root"),
        display_path=display_path,
        expected_stat=_SUBJECT,
        copy_attestation=Attestation(
            ContentEvidence(
                "xxh3_128",
                bytes(16),
                _SUBJECT.size,
                Provenance.COPY_ATTESTED,
                _OBSERVED_AT,
            ),
            _SUBJECT,
        ),
        recorded_identity=None,
    )



def _selection_contract(
    kind: str,
    subjects: tuple[IntegritySelectionItem | PostCopyCandidate, ...],
) -> tuple[
    IntegritySelection | PostCopySelection,
    Callable[[object], object],
    Callable[..., None],
]:
    if kind == "integrity":
        return (
            IntegritySelection(subjects),  # type: ignore[arg-type]
            snapshot_integrity_selection_authority,
            revalidate_integrity_selection_authority,
        )
    return (
        PostCopySelection(subjects),  # type: ignore[arg-type]
        snapshot_post_copy_selection_authority,
        revalidate_post_copy_selection_authority,
    )


class _MembershipWorkWitness:
    """Tests-only seam that records membership work after construction."""

    def __init__(self, item_ids: object) -> None:
        self._item_ids = frozenset(item_ids)  # type: ignore[arg-type]
        self.iterated_item_ids = 0

    def __contains__(self, item_id: object) -> bool:
        return item_id in self._item_ids

    def __iter__(self):
        for item_id in self._item_ids:
            self.iterated_item_ids += 1
            yield item_id


def _install_membership_work_witness(
    selection: IntegritySelection | PostCopySelection,
) -> _MembershipWorkWitness:
    """Install an owner-specific test adapter after construction has completed."""

    witness = _MembershipWorkWitness(selection.known_item_ids)
    selection._known_item_ids = witness  # type: ignore[assignment]
    return witness


@pytest.mark.parametrize("size", (0, 1, 16, 256, 4096))
@pytest.mark.parametrize("kind", ("post-copy", "integrity"))
def test_selection_completion_preserves_admitted_membership_and_refusal(
    size: int,
    kind: str,
) -> None:
    subjects = tuple(_selection_subject(kind, number) for number in range(size))
    selected_ids = tuple(subject.item_id for subject in subjects)
    selection, _, _ = _selection_contract(kind, subjects)

    assert set(selection.known_item_ids) == set(selected_ids)
    assert tuple(selection.pending) == subjects
    for item_id in selected_ids:
        selection.mark_completed(item_id, 0)
    with pytest.raises(ValueError, match="unknown .* item"):
        selection.mark_completed("unknown", 0)

    assert selection.completed_count == size
    assert tuple(selection.pending) == ()
    if selected_ids:
        with pytest.raises(ValueError, match="already completed"):
            selection.mark_completed(selected_ids[0], 0)


@pytest.mark.parametrize("size", (0, 1, 16, 256, 4096))
@pytest.mark.parametrize("kind", ("post-copy", "integrity"))
def test_selection_exposes_stable_construction_admitted_membership(
    kind: str,
    size: int,
) -> None:
    subjects = tuple(_selection_subject(kind, number) for number in range(size))
    selection, _, _ = _selection_contract(kind, subjects)
    admitted = set(selection.known_item_ids)

    if subjects:
        selection.mark_completed(subjects[-1].item_id, 0)

    assert admitted == {subject.item_id for subject in subjects}
    assert set(selection.known_item_ids) == admitted


@pytest.mark.parametrize("kind", ("post-copy", "integrity"))
def test_selection_completion_work_is_population_independent(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    item_id_accesses_by_size: list[int] = []
    membership_iterations_by_size: list[int] = []
    unknown_item_id_accesses_by_size: list[int] = []
    unknown_membership_iterations_by_size: list[int] = []
    subject_type = (
        IntegritySelectionItem if kind == "integrity" else PostCopyCandidate
    )
    original_getattribute = subject_type.__getattribute__
    armed = False
    item_id_accesses: list[str] = []

    def observe_getattribute(value: object, name: str) -> object:
        if armed and name == "item_id":
            item_id_accesses.append(name)
        return original_getattribute(value, name)

    monkeypatch.setattr(subject_type, "__getattribute__", observe_getattribute)
    for size in (1, 16, 256, 4096):
        subjects = tuple(_selection_subject(kind, number) for number in range(size))
        selection, _, _ = _selection_contract(kind, subjects)
        witness = _install_membership_work_witness(selection)
        last_id = subjects[-1].item_id
        item_id_accesses.clear()
        armed = True
        selection.mark_completed(last_id, 0)
        armed = False
        item_id_accesses_by_size.append(len(item_id_accesses))
        membership_iterations_by_size.append(witness.iterated_item_ids)

    for size in (0, 1, 16, 256, 4096):
        subjects = tuple(_selection_subject(kind, number) for number in range(size))
        selection, _, _ = _selection_contract(kind, subjects)
        witness = _install_membership_work_witness(selection)
        item_id_accesses.clear()
        armed = True
        with pytest.raises(ValueError, match="unknown .* item"):
            selection.mark_completed("unknown", 0)
        armed = False
        unknown_item_id_accesses_by_size.append(len(item_id_accesses))
        unknown_membership_iterations_by_size.append(witness.iterated_item_ids)

    assert len(set(item_id_accesses_by_size)) == 1
    assert len(set(membership_iterations_by_size)) == 1
    assert len(set(unknown_item_id_accesses_by_size)) == 1
    assert len(set(unknown_membership_iterations_by_size)) == 1


@pytest.mark.parametrize("kind", ("post-copy", "integrity"))
def test_selection_authority_preserves_detached_completion_snapshot(
    kind: str,
) -> None:
    subject = _selection_subject(kind, 0)
    selection, snapshot, revalidate = _selection_contract(kind, (subject,))
    authority = snapshot(selection)

    if kind == "post-copy":
        assert authority.candidates == (subject,)
        assert authority.candidates is not selection.candidates
        assert authority.candidates[0] is not subject
        assert type(authority.candidates[0]) is PostCopyCandidate
        assert authority.candidates[0].copy_attestation is not subject.copy_attestation
        assert type(authority.completed_bytes) is MappingProxyType
        selection._completed_bytes[subject.item_id] = 1
        assert dict(authority.completed_bytes) == {}
        selection._completed_bytes.clear()

    selection.note_bytes_processed(3)
    selection.mark_completed(subject.item_id, 3)

    assert dict(authority.completed_bytes) == {}
    revalidate(selection, authority, allow_progress=True)
    with pytest.raises(ValueError, match="selection changed during capture"):
        revalidate(selection, authority, allow_progress=False)


@pytest.mark.parametrize(
    ("kind", "expected_message"),
    (
        ("post-copy", "post-copy candidate changed during collaboration"),
        ("integrity", "integrity selection item changed during collaboration"),
    ),
)
def test_selection_authority_reports_changed_item_before_completion_delta(
    kind: str,
    expected_message: str,
) -> None:
    subject = _selection_subject(kind, 0)
    selection, snapshot, revalidate = _selection_contract(kind, (subject,))
    authority = snapshot(selection)
    selection.note_bytes_processed(1)
    selection.mark_completed(subject.item_id, 1)
    if kind == "integrity":
        selection.items = (replace(subject, item_id="integrity-1"),)
    else:
        selection.candidates = (replace(subject, item_id="post-copy-1"),)

    with pytest.raises(ValueError, match=f"^{expected_message}$"):
        revalidate(selection, authority, allow_progress=False)


@pytest.mark.parametrize("kind", ("post-copy", "integrity"))
def test_selection_authority_rejects_public_population_replacement(
    kind: str,
) -> None:
    subject = _selection_subject(kind, 0)
    selection, snapshot, revalidate = _selection_contract(kind, (subject,))
    authority = snapshot(selection)
    if kind == "integrity":
        selection.items = ()
    else:
        selection.candidates = ()

    with pytest.raises((TypeError, ValueError)):
        snapshot(selection)
    with pytest.raises((TypeError, ValueError)):
        revalidate(selection, authority, allow_progress=False)

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


def test_integrity_outcome_has_an_exact_slotted_shape() -> None:
    class Text(str):
        pass

    outcome = IntegrityOutcome(
        item_id="item",
        row_id="row",
        location_id="location",
        path="file.bin",
        result=IntegrityResult.VERIFIED,
    )

    assert not hasattr(outcome, "__dict__")
    with pytest.raises(TypeError, match="item id must be text"):
        IntegrityOutcome(
            Text("item"),
            "row",
            "location",
            "file.bin",
            IntegrityResult.VERIFIED,
        )
    with pytest.raises(TypeError, match="result has the wrong type"):
        IntegrityOutcome(
            "item",
            "row",
            "location",
            "file.bin",
            "verified",  # type: ignore[arg-type]
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


def _assert_declared_slots(value: object) -> None:
    assert not hasattr(value, "__dict__")
    assert type(value).__slots__ == tuple(field.name for field in fields(value))
    with pytest.raises(AttributeError):
        object.__setattr__(value, "_undeclared", object())


def test_integrity_command_and_context_are_exactly_slotted() -> None:
    observed_at = datetime(2026, 8, 29, tzinfo=timezone.utc)
    attestation = Attestation(
        ContentEvidence(
            "xxh3_128",
            bytes(16),
            _SUBJECT.size,
            Provenance.VERIFY_ATTESTED,
            observed_at,
        ),
        _SUBJECT,
    )
    command = IntegrityRecordCommand(
        IntegrityMode.BASELINE,
        "item",
        "row",
        "location",
        "FILE.BIN",
        "scope",
        InventoryState.PRESENT,
        _SUBJECT,
        None,
        attestation,
        False,
        False,
    )
    context = _verifier_context()

    assert tuple(type(value).__name__ for value in (command, context)) == (
        "IntegrityRecordCommand",
        "VerifierContext",
    )
    for value in (command, context):
        _assert_declared_slots(value)


def test_post_copy_progress_admission_is_paired() -> None:
    with pytest.raises(ValueError, match="admission must be paired"):
        _verifier_context(post_copy_items_total=1)


def test_verifier_chunk_size_has_one_public_allocation_ceiling() -> None:
    assert MAX_VERIFIER_CHUNK_SIZE == 4 * 1024 * 1024
    assert (
        _verifier_context(chunk_size=MAX_VERIFIER_CHUNK_SIZE).chunk_size
        == MAX_VERIFIER_CHUNK_SIZE
    )

    for value in (True, 1.0, 0, -1, MAX_VERIFIER_CHUNK_SIZE + 1):
        with pytest.raises(
            (TypeError, ValueError),
            match="verification chunk size",
        ):
            _verifier_context(chunk_size=value)


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
