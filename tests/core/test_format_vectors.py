"""Known-answer vectors for the shared formats in ``namisync.core.formats``.

Every entry of ``FORMAT_VERSIONS`` needs vectors for its current version, and
every current vector must still produce its pasted literal. The expected values
below are literals; none is recomputed by the encoder under test or by an
equivalent helper. A vector may call the encoder to produce the actual value,
never the expected one.

Changing an encoding without a new constant fails its vector. Adding or bumping
a constant without vectors fails ``test_every_format_has_current_vectors``.

Policy: the vectors pin persisted vocabularies exactly. Every enum value set,
the event detail-key vocabulary and the stored-event bounds are literal, so
adding a member to a persisted enum fails a test and is decided as a format
change (a new constant value, new vectors and a database step), never as a
silent extension. Vectors for a superseded version stay in ``VECTORS`` as a
record and are not executed; none exist yet.

Known limit: path keys follow the release interpreter's Unicode case tables.
Changing that interpreter can change a ``path-key`` result without any code
change, and these vectors cannot detect it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json

import pytest
import xxhash

import namisync.core.formats as formats_module
from namisync.core.event_v5 import (
    _DETAIL_KEYS,
    _EXCLUSION_REASONS,
    EVENT_V5_SCHEMA_VERSION,
    MAX_DETAIL_LEAVES,
    MAX_DETAIL_PATH_LEAVES,
    MAX_RELIABLE_EVENT_CANONICAL_BYTES,
    validate_and_encode_event_v5_envelope,
)
from namisync.core.events import (
    CORE_EVENT_SCHEMA_VERSION,
    Envelope,
    Gap,
    ItemOutcome,
    PhaseChanged,
    Progress,
    StateChanged,
    Terminal,
    TerminalSummary,
    canonical_event_bytes,
    envelope_from_dict,
    result_item_to_dict,
    terminal_summary_to_dict,
)
from namisync.core.evidence import (
    ContentEvidence,
    HasherContractError,
    Outcome,
    Provenance,
    RecordingStatus,
    finish_content_hasher,
    new_content_hasher,
    require_content_digest,
    update_content_hasher,
)
from namisync.core.execution import (
    ExecutionReason,
    ItemRecordingReason,
    TaskRecordingIssue,
    TaskRecordingIssueReason,
)
from namisync.core.file_identity import (
    file_identity_from_stat,
    file_identity_from_windows_parts,
    file_index_128_from_bytes,
)
from namisync.core.formats import FORMAT_VERSIONS
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityOutcome,
    IntegrityReason,
    IntegrityResult,
    InventoryState,
    ReadStrategy,
    RecordDisposition,
    VerificationInvalidationReason,
)
from namisync.core.models import (
    CapabilityProfile,
    EntryKind,
    FileIdentity,
    FileStat,
    MetadataSnapshot,
    Root,
    ScanScopeKind,
    ScanWarningCode,
    UnsupportedReason,
    VolumeEvidence,
    VolumeId,
    capability_profile_projection,
    file_identity_projection,
    file_stat_fact,
    file_stat_projection,
    metadata_projection,
    root_projection,
    volume_evidence_projection,
    volume_id_projection,
)
from namisync.core.pathing import (
    PathValidationError,
    normalize_relative_path,
    validate_relative_path,
)
from namisync.core.planning import (
    Assignment,
    BlockedReason,
    DeletionPolicy,
    DestinationAssignment,
    FilterSet,
    OpId,
    OperationKind,
    OperationReason,
    Plan,
    PlanFingerprint,
    PlanOperation,
    PreservationPolicy,
    SyncOptions,
    assignment_projection,
    canonical_json_bytes,
    deterministic_operation_id,
    filter_set_projection,
    operation_projection,
    plan_fingerprint,
    policy_fingerprint,
    preservation_policy_projection,
    selection_digest,
)
from namisync.core.recording import InventoryVisibilityAction
from namisync.core.review import (
    ReviewFactLimitExceeded,
    ReviewLimitAxis,
    ReviewPopulation,
    ReviewTreeKind,
)
from namisync.core.scalars import (
    MAX_SAFE_INTEGER,
    MAX_SIGNED_64,
    ScalarDomainError,
    file_index_128_from_text,
    file_index_128_to_text,
    require_safe_int,
    require_signed_64,
    scalar_64_from_text,
    scalar_64_to_text,
)
from namisync.core.session import (
    Disposition,
    FailureDetail,
    PhaseResult,
    PhaseStatus,
    SessionId,
    SessionState,
)


@dataclass(frozen=True, slots=True)
class Refused:
    """The vector's input must be refused with this exception type."""

    error: type[BaseException]


@dataclass(frozen=True, slots=True)
class Vector:
    label: str
    produce: Callable[[], object]
    expected: object


def _v(label: str, produce: Callable[[], object], expected: object) -> Vector:
    return Vector(label, produce, expected)


# --------------------------------------------------------------------------
# Shared inputs.

SESSION = SessionId("0123456789abcdef0123456789abcdef")
ITEM_ID = "fedcba9876543210fedcba9876543210"
ATTEMPT_ID = "00112233445566778899aabbccddeeff"
T0 = datetime(2026, 8, 25, tzinfo=timezone.utc)
T1 = datetime(2026, 8, 25, 12, 34, 56, 500000, tzinfo=timezone.utc)
T_MAX = datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)
T_ZERO_US = datetime(2026, 8, 25, 0, 0, 0, 0, tzinfo=timezone.utc)

MAX_128 = (1 << 128) - 1
IDENTITY_MAX = FileIdentity("FFFFFFFF", MAX_128)


def _stat(
    kind: EntryKind = EntryKind.FILE,
    size: int = 7,
    mtime_ns: int = 11,
    identity: FileIdentity | None = IDENTITY_MAX,
    nlink: int = 1,
    attributes: int = 1,
    created_ns: int | None = 3,
) -> FileStat:
    return FileStat(
        kind,
        size,
        mtime_ns,
        identity,
        nlink,
        MetadataSnapshot(attributes, created_ns),
    )


def _event(seq: int, at: datetime, body: object) -> bytes:
    return canonical_event_bytes(Envelope(SESSION, seq, at, 5, body))


def _terminal(**changes: object) -> TerminalSummary:
    fields: dict[str, object] = dict(
        status=SessionState.COMPLETED,
        recording=RecordingStatus.OK,
        audit=RecordingStatus.OK,
        disposition=Disposition.RAN,
        canceled=False,
        phases=(),
        bytes_done=0,
        bytes_total=0,
        error=None,
        recording_degraded_items=0,
        recording_issues=(),
        omitted_detail_count=0,
        review_fact_limit=None,
    )
    fields.update(changes)
    return TerminalSummary(**fields)


def _refused_terminal(fact: ReviewFactLimitExceeded) -> TerminalSummary:
    return _terminal(
        status=SessionState.REFUSED,
        disposition=Disposition.UNRUN,
        review_fact_limit=fact,
    )


def _item(**changes: object) -> ItemOutcome:
    fields: dict[str, object] = dict(
        item_id="item-1",
        kind=OperationKind.COPY,
        path="a",
        outcome=Outcome.SUCCEEDED,
    )
    fields.update(changes)
    return ItemOutcome(**fields)


def _recording_facts(item: ItemOutcome) -> dict[str, object]:
    wire = result_item_to_dict(item)
    return {
        key: wire[key]
        for key in (
            "recording",
            "recording_reason",
            "recording_detail",
            "detail_omitted_count",
        )
    }


def _digest(*chunks: bytes) -> bytes:
    hasher = new_content_hasher(xxhash.xxh3_128)
    for chunk in chunks:
        update_content_hasher(hasher, chunk)
    return finish_content_hasher(hasher)


def _values(enum_type: type) -> frozenset[str]:
    return frozenset(member.value for member in enum_type)


def _identity_leaves(value: FileIdentity | None) -> object:
    return None if value is None else (value.volume_serial, value.file_index)


def _operation_id(*args: object) -> str:
    return str(deterministic_operation_id(*args))


VOLUME_SOURCE = VolumeId("FFFFFFFF", "NTFS")
VOLUME_TARGET = VolumeId("00000001", "REFS")
PROFILE_SOURCE = CapabilityProfile("NTFS", 100, True, None, 32767, True, True)
PROFILE_TARGET = CapabilityProfile("REFS", 100, True, False, 32767, False, False)


def _plan() -> Plan:
    source = _stat()
    intended = _stat(identity=FileIdentity("00000001", MAX_128 - 2))
    return Plan(
        source_root=Root("C:\\vec-source", "source-root"),
        target_root=Root("D:\\vec-target", "target-root"),
        source_volume_id=VOLUME_SOURCE,
        target_volume_id=VOLUME_TARGET,
        source_volume_evidence=VolumeEvidence("source-\u00e9", "device-source", False),
        target_volume_evidence=VolumeEvidence(None, None, True),
        source_profile=PROFILE_SOURCE,
        target_profile=PROFILE_TARGET,
        source_complete=True,
        target_complete=False,
        operations=(
            PlanOperation(
                op_id=OpId("ed4f7861d052e725b4b9326eca315251"),
                kind=OperationKind.COPY,
                source_rel_path="a.txt",
                target_rel_path="a.txt",
                source_expected=source,
                target_expected=None,
                intended=intended,
                metadata=MetadataSnapshot(1, 3),
                content_bytes=7,
            ),
        ),
        assignment=Assignment(
            "identity",
            "1",
            (DestinationAssignment("a.txt", "A.TXT", "a.txt", "A.TXT"),),
        ),
        preservation=PreservationPolicy(),
        filter_snapshot=FilterSet(("*.tmp",)),
        deletion_policy=DeletionPolicy.TRASH,
        trash_on_update=True,
        policy_fingerprint="0" * 64,
        required_volumes=frozenset({VOLUME_SOURCE, VOLUME_TARGET}),
        required_bytes=7,
        fingerprint=PlanFingerprint("ignored"),
    )


def _fingerprint_of_plan_variant(**changes: object) -> str:
    plan = _plan()
    values = {
        name: getattr(plan, name)
        for name in plan.__dataclass_fields__
    }
    values.update(changes)
    return str(plan_fingerprint(Plan(**values)))


# --------------------------------------------------------------------------
# numeric v1

NUMERIC_V1 = (
    _v("to-text-zero", lambda: scalar_64_to_text(0, "n"), "0"),
    _v("to-text-one", lambda: scalar_64_to_text(1, "n"), "1"),
    _v(
        "to-text-max-safe",
        lambda: scalar_64_to_text(9007199254740991, "n"),
        "9007199254740991",
    ),
    _v(
        "to-text-above-safe",
        lambda: scalar_64_to_text(9007199254740992, "n"),
        "9007199254740992",
    ),
    _v(
        "to-text-max-signed-64",
        lambda: scalar_64_to_text(9223372036854775807, "n"),
        "9223372036854775807",
    ),
    _v(
        "to-text-refuses-2-pow-63",
        lambda: scalar_64_to_text(9223372036854775808, "n"),
        Refused(ScalarDomainError),
    ),
    _v("to-text-refuses-negative", lambda: scalar_64_to_text(-1, "n"), Refused(ScalarDomainError)),
    _v("from-text-zero", lambda: scalar_64_from_text("0", "n"), 0),
    _v(
        "from-text-max-safe",
        lambda: scalar_64_from_text("9007199254740991", "n"),
        9007199254740991,
    ),
    _v(
        "from-text-above-safe",
        lambda: scalar_64_from_text("9007199254740993", "n"),
        9007199254740993,
    ),
    _v(
        "from-text-max-signed-64",
        lambda: scalar_64_from_text("9223372036854775807", "n"),
        9223372036854775807,
    ),
    _v(
        "from-text-refuses-2-pow-63",
        lambda: scalar_64_from_text("9223372036854775808", "n"),
        Refused(ScalarDomainError),
    ),
    _v(
        "from-text-refuses-twenty-digits",
        lambda: scalar_64_from_text("10000000000000000000", "n"),
        Refused(ScalarDomainError),
    ),
    _v(
        "from-text-refuses-leading-zero",
        lambda: scalar_64_from_text("01", "n"),
        Refused(ValueError),
    ),
    _v(
        "from-text-refuses-double-zero",
        lambda: scalar_64_from_text("00", "n"),
        Refused(ValueError),
    ),
    _v(
        "from-text-refuses-negative-zero",
        lambda: scalar_64_from_text("-0", "n"),
        Refused(ValueError),
    ),
    _v("from-text-refuses-negative", lambda: scalar_64_from_text("-1", "n"), Refused(ValueError)),
    _v("from-text-refuses-plus", lambda: scalar_64_from_text("+1", "n"), Refused(ValueError)),
    _v("from-text-refuses-fraction", lambda: scalar_64_from_text("1.0", "n"), Refused(ValueError)),
    _v("from-text-refuses-exponent", lambda: scalar_64_from_text("1e3", "n"), Refused(ValueError)),
    _v(
        "from-text-refuses-leading-space",
        lambda: scalar_64_from_text(" 1", "n"),
        Refused(ValueError),
    ),
    _v(
        "from-text-refuses-trailing-space",
        lambda: scalar_64_from_text("1 ", "n"),
        Refused(ValueError),
    ),
    _v(
        "from-text-refuses-trailing-newline",
        lambda: scalar_64_from_text("1\n", "n"),
        Refused(ValueError),
    ),
    _v(
        "from-text-refuses-arabic-indic-digit",
        lambda: scalar_64_from_text("\u0661", "n"),
        Refused(ValueError),
    ),
    _v(
        "from-text-refuses-fullwidth-digit",
        lambda: scalar_64_from_text("\uff11", "n"),
        Refused(ValueError),
    ),
    _v("from-text-refuses-empty", lambda: scalar_64_from_text("", "n"), Refused(ValueError)),
    _v("safe-int-max", lambda: require_safe_int(9007199254740991, "n"), 9007199254740991),
    _v(
        "safe-int-refuses-2-pow-53",
        lambda: require_safe_int(9007199254740992, "n"),
        Refused(ValueError),
    ),
    _v("safe-int-refuses-negative", lambda: require_safe_int(-1, "n"), Refused(ValueError)),
    _v(
        "signed-64-max",
        lambda: require_signed_64(9223372036854775807, "n"),
        9223372036854775807,
    ),
    _v(
        "bounds",
        lambda: (MAX_SAFE_INTEGER, MAX_SIGNED_64),
        (9007199254740991, 9223372036854775807),
    ),
)

# --------------------------------------------------------------------------
# identity v1

_ONE_THEN_ZEROS = b"\x01" + b"\x00" * 15

IDENTITY_V1 = (
    _v("to-text-zero", lambda: file_index_128_to_text(0), "0"),
    _v("to-text-above-safe", lambda: file_index_128_to_text(1 << 53), "9007199254740992"),
    _v(
        "to-text-max-64",
        lambda: file_index_128_to_text((1 << 64) - 1),
        "18446744073709551615",
    ),
    _v(
        "to-text-2-pow-64",
        lambda: file_index_128_to_text(1 << 64),
        "18446744073709551616",
    ),
    _v(
        "to-text-2-pow-127",
        lambda: file_index_128_to_text(1 << 127),
        "170141183460469231731687303715884105728",
    ),
    _v(
        "to-text-max-128",
        lambda: file_index_128_to_text((1 << 128) - 1),
        "340282366920938463463374607431768211455",
    ),
    _v("to-text-refuses-2-pow-128", lambda: file_index_128_to_text(1 << 128), Refused(ValueError)),
    _v("to-text-refuses-negative", lambda: file_index_128_to_text(-1), Refused(ValueError)),
    _v("from-text-zero", lambda: file_index_128_from_text("0"), 0),
    _v(
        "from-text-max-64",
        lambda: file_index_128_from_text("18446744073709551615"),
        (1 << 64) - 1,
    ),
    _v(
        "from-text-max-128",
        lambda: file_index_128_from_text("340282366920938463463374607431768211455"),
        340282366920938463463374607431768211455,
    ),
    _v(
        "from-text-refuses-2-pow-128",
        lambda: file_index_128_from_text("340282366920938463463374607431768211456"),
        Refused(ValueError),
    ),
    _v(
        "from-text-refuses-all-nines",
        lambda: file_index_128_from_text("9" * 39),
        Refused(ValueError),
    ),
    _v(
        "from-text-refuses-forty-digits",
        lambda: file_index_128_from_text("1" * 40),
        Refused(ValueError),
    ),
    _v(
        "from-text-refuses-leading-zero",
        lambda: file_index_128_from_text("0001"),
        Refused(ValueError),
    ),
    _v("from-text-refuses-negative", lambda: file_index_128_from_text("-1"), Refused(ValueError)),
    _v("from-text-refuses-empty", lambda: file_index_128_from_text(""), Refused(ValueError)),
    _v(
        "bytes-ascending-is-little-endian",
        lambda: file_index_128_from_bytes(bytes(range(16))),
        20011376718272490338853433276725592320,
    ),
    _v("bytes-low-byte-first", lambda: file_index_128_from_bytes(_ONE_THEN_ZEROS), 1),
    _v(
        "bytes-high-bit",
        lambda: file_index_128_from_bytes(b"\x00" * 15 + b"\x80"),
        170141183460469231731687303715884105728,
    ),
    _v(
        "bytes-all-ones",
        lambda: file_index_128_from_bytes(b"\xff" * 16),
        340282366920938463463374607431768211455,
    ),
    _v("bytes-bytearray", lambda: file_index_128_from_bytes(bytearray(_ONE_THEN_ZEROS)), 1),
    _v("bytes-memoryview", lambda: file_index_128_from_bytes(memoryview(_ONE_THEN_ZEROS)), 1),
    _v(
        "bytes-refuses-fifteen",
        lambda: file_index_128_from_bytes(b"\x00" * 15),
        Refused(ValueError),
    ),
    _v(
        "bytes-refuses-seventeen",
        lambda: file_index_128_from_bytes(b"\x00" * 17),
        Refused(ValueError),
    ),
    _v(
        "windows-parts-low-32-bits-uppercase",
        lambda: _identity_leaves(
            file_identity_from_windows_parts(0x0123456789ABCDEF, _ONE_THEN_ZEROS)
        ),
        ("89ABCDEF", 1),
    ),
    _v(
        "windows-parts-serial-zero-padded",
        lambda: _identity_leaves(file_identity_from_windows_parts(0xABC, _ONE_THEN_ZEROS)),
        ("00000ABC", 1),
    ),
    _v(
        "windows-parts-serial-max",
        lambda: _identity_leaves(
            file_identity_from_windows_parts((1 << 64) - 1, b"\xff" * 16)
        ),
        ("FFFFFFFF", 340282366920938463463374607431768211455),
    ),
    _v(
        "windows-parts-refuses-2-pow-64-serial",
        lambda: file_identity_from_windows_parts(1 << 64, _ONE_THEN_ZEROS),
        Refused(ValueError),
    ),
    _v(
        "windows-parts-refuses-negative-serial",
        lambda: file_identity_from_windows_parts(-1, _ONE_THEN_ZEROS),
        Refused(ValueError),
    ),
    _v(
        "stat-ntfs-max-index",
        lambda: _identity_leaves(file_identity_from_stat("0000ABCD", "NTFS", MAX_128)),
        ("0000ABCD", 340282366920938463463374607431768211455),
    ),
    _v(
        "stat-refs-lowercase-name",
        lambda: _identity_leaves(file_identity_from_stat("00000001", "refs", 0)),
        ("00000001", 0),
    ),
    _v("stat-fat-has-no-identity", lambda: file_identity_from_stat("00000001", "FAT32", 5), None),
    _v("stat-exfat-has-no-identity", lambda: file_identity_from_stat("00000001", "exFAT", 5), None),
    _v(
        "stat-refuses-2-pow-128",
        lambda: file_identity_from_stat("00000001", "NTFS", 1 << 128),
        None,
    ),
    _v("stat-refuses-negative", lambda: file_identity_from_stat("00000001", "NTFS", -1), None),
)

# --------------------------------------------------------------------------
# path-key v1

PATH_KEY_V1 = (
    _v("key-ascii-upper", lambda: normalize_relative_path("a.txt"), "A.TXT"),
    _v(
        "key-separators-and-case",
        lambda: normalize_relative_path("Dir/Sub\\File.Txt"),
        "DIR\\SUB\\FILE.TXT",
    ),
    _v("key-keeps-eszett", lambda: normalize_relative_path("Stra\u00dfe.txt"), "STRA\u00dfE.TXT"),
    _v("key-double-s-is-distinct", lambda: normalize_relative_path("strasse.txt"), "STRASSE.TXT"),
    _v(
        "key-expansion-leaves-only-that-character",
        lambda: normalize_relative_path("a\u00df.txt"),
        "A\u00df.TXT",
    ),
    _v("key-capital-eszett-stays", lambda: normalize_relative_path("\u1e9e"), "\u1e9e"),
    _v("key-latin-dz-small", lambda: normalize_relative_path("\u01c6.txt"), "\u01c4.TXT"),
    _v("key-latin-dz-title", lambda: normalize_relative_path("\u01c5"), "\u01c4"),
    _v(
        "key-n-apostrophe-expands-so-stays",
        lambda: normalize_relative_path("\u0149.txt"),
        "\u0149.TXT",
    ),
    _v("key-ligature-fi-stays", lambda: normalize_relative_path("\ufb01le.txt"), "\ufb01LE.TXT"),
    _v("key-iota-subscript-expands-so-stays", lambda: normalize_relative_path("\u1fb3"), "\u1fb3"),
    _v("key-greek-three-way-expansion-stays", lambda: normalize_relative_path("\u0390"), "\u0390"),
    _v("key-dotless-i-maps-to-ascii-i", lambda: normalize_relative_path("\u0131"), "I"),
    _v("key-long-s-maps-to-ascii-s", lambda: normalize_relative_path("\u017f"), "S"),
    _v("key-micro-sign-maps-to-greek-mu", lambda: normalize_relative_path("\u00b5"), "\u039c"),
    _v("key-final-sigma", lambda: normalize_relative_path("\u03c2"), "\u03a3"),
    _v("key-dotted-capital-i-stays", lambda: normalize_relative_path("\u0130"), "\u0130"),
    _v("key-ascii-i-is-not-turkish", lambda: normalize_relative_path("i"), "I"),
    _v("key-nfc-precomposed", lambda: normalize_relative_path("\u00e9.txt"), "\u00c9.TXT"),
    _v(
        "key-nfd-is-not-normalized",
        lambda: normalize_relative_path("e\u0301.txt"),
        "E\u0301.TXT",
    ),
    _v("key-non-bmp-deseret", lambda: normalize_relative_path("\U00010428.txt"), "\U00010400.TXT"),
    _v("key-non-bmp-uncased", lambda: normalize_relative_path("a\U0001f642"), "A\U0001f642"),
    _v("key-fullwidth", lambda: normalize_relative_path("\uff41"), "\uff21"),
    _v("key-leading-space-kept", lambda: normalize_relative_path(" a"), " A"),
    _v("key-root-allowed", lambda: normalize_relative_path("", allow_root=True), ""),
    _v("path-canonical-separators", lambda: validate_relative_path("A/b\\C"), "A\\b\\C"),
    _v("path-case-kept", lambda: validate_relative_path("Dir/File.TXT"), "Dir\\File.TXT"),
    _v("path-root-allowed", lambda: validate_relative_path("", allow_root=True), ""),
    _v(
        "path-utf16-bound-ascii",
        lambda: len(validate_relative_path("a" * 32767)),
        32767,
    ),
    _v(
        "path-utf16-bound-refuses-next",
        lambda: validate_relative_path("a" * 32768),
        Refused(PathValidationError),
    ),
    _v(
        "path-utf16-bound-counts-surrogate-pairs",
        lambda: len(validate_relative_path("\U0001f600" * 16383 + "a")),
        16384,
    ),
    _v(
        "path-utf16-bound-refuses-pair-overflow",
        lambda: validate_relative_path("\U0001f600" * 16384),
        Refused(PathValidationError),
    ),
    _v("path-refuses-empty", lambda: validate_relative_path(""), Refused(PathValidationError)),
    _v(
        "path-refuses-leading-backslash",
        lambda: validate_relative_path("\\a"),
        Refused(PathValidationError),
    ),
    _v(
        "path-refuses-leading-slash",
        lambda: validate_relative_path("/a"),
        Refused(PathValidationError),
    ),
    _v("path-refuses-drive", lambda: validate_relative_path("C:\\a"), Refused(PathValidationError)),
    _v(
        "path-refuses-drive-relative",
        lambda: validate_relative_path("C:a"),
        Refused(PathValidationError),
    ),
    _v(
        "path-refuses-dot-dot",
        lambda: validate_relative_path("a\\..\\b"),
        Refused(PathValidationError),
    ),
    _v("path-refuses-dot", lambda: validate_relative_path("a\\.\\b"), Refused(PathValidationError)),
    _v(
        "path-refuses-empty-component",
        lambda: validate_relative_path("a\\\\b"),
        Refused(PathValidationError),
    ),
    _v(
        "path-refuses-trailing-separator",
        lambda: validate_relative_path("a\\"),
        Refused(PathValidationError),
    ),
    _v(
        "path-refuses-trailing-dot",
        lambda: validate_relative_path("a."),
        Refused(PathValidationError),
    ),
    _v(
        "path-refuses-trailing-space",
        lambda: validate_relative_path("a "),
        Refused(PathValidationError),
    ),
    _v("path-refuses-stream", lambda: validate_relative_path("a:b"), Refused(PathValidationError)),
    _v(
        "path-refuses-device-namespace",
        lambda: validate_relative_path("\\\\?\\C:\\a"),
        Refused(PathValidationError),
    ),
    _v("path-refuses-nul", lambda: validate_relative_path("a\x00b"), Refused(ValueError)),
    _v(
        "path-refuses-lone-surrogate",
        lambda: validate_relative_path("\ud800"),
        Refused(ValueError),
    ),
)

# --------------------------------------------------------------------------
# preimage v1

_ID_ZERO = OpId("0" * 32)
_ID_F = OpId("f" * 32)

PREIMAGE_V1 = (
    _v(
        "json-sorts-keys-recursively",
        lambda: canonical_json_bytes({"b": 1, "a": 2}),
        b'{"a":2,"b":1}',
    ),
    _v(
        "json-nesting-and-literals",
        lambda: canonical_json_bytes({"z": {"y": [3, 2, 1], "x": None}, "a": True, "m": False}),
        b'{"a":true,"m":false,"z":{"x":null,"y":[3,2,1]}}',
    ),
    _v(
        "json-empty-containers",
        lambda: canonical_json_bytes({"a": [], "b": {}}),
        b'{"a":[],"b":{}}',
    ),
    _v("json-empty-list", lambda: canonical_json_bytes([]), b"[]"),
    _v(
        "json-bmp-text-is-raw-utf8",
        lambda: canonical_json_bytes("\u00e9\u6d77"),
        b'"\xc3\xa9\xe6\xb5\xb7"',
    ),
    _v(
        "json-non-bmp-text-is-raw-utf8",
        lambda: canonical_json_bytes("\U0001f642"),
        b'"\xf0\x9f\x99\x82"',
    ),
    _v(
        "json-escapes",
        lambda: canonical_json_bytes('a"b\\c\nd\te\rf\x01g\x1fh/i\x7f\x00'),
        b'"a\\"b\\\\c\\nd\\te\\rf\\u0001g\\u001fh/i\x7f\\u0000"',
    ),
    _v("json-backspace-and-formfeed", lambda: canonical_json_bytes("\b\f"), b'"\\b\\f"'),
    _v("json-line-separator-is-raw", lambda: canonical_json_bytes("\u2028"), b'"\xe2\x80\xa8"'),
    _v(
        "json-integers-are-numbers",
        lambda: canonical_json_bytes(
            [0, 9007199254740991, 9223372036854775807, (1 << 64) - 1, MAX_128, -1]
        ),
        b"[0,9007199254740991,9223372036854775807,18446744073709551615,"
        b"340282366920938463463374607431768211455,-1]",
    ),
    _v(
        "json-floats",
        lambda: canonical_json_bytes([0.5, 1e16, -0.0, 1e-07]),
        b"[0.5,1e+16,-0.0,1e-07]",
    ),
    _v(
        "json-keys-sort-by-code-point",
        lambda: canonical_json_bytes(
            {"\U00010000": 1, "\uffff": 2, "\u00e9": 3, "z": 4, "Z": 5, "": 6}
        ),
        b'{"":6,"Z":5,"z":4,"\xc3\xa9":3,"\xef\xbf\xbf":2,"\xf0\x90\x80\x80":1}',
    ),
    _v("json-refuses-nan", lambda: canonical_json_bytes(float("nan")), Refused(ValueError)),
    _v("json-refuses-infinity", lambda: canonical_json_bytes([float("inf")]), Refused(ValueError)),
    _v("json-refuses-tuple", lambda: canonical_json_bytes((1, 2)), Refused(TypeError)),
    _v("json-refuses-integer-key", lambda: canonical_json_bytes({1: 2}), Refused(TypeError)),
    _v("json-refuses-set", lambda: canonical_json_bytes(frozenset({1})), Refused(TypeError)),
    _v(
        "json-refuses-enum-member",
        lambda: canonical_json_bytes({"a": Provenance.COPY_ATTESTED}),
        Refused(TypeError),
    ),
    _v("json-refuses-lone-surrogate", lambda: canonical_json_bytes("\ud800"), Refused(ValueError)),
    _v(
        "json-refuses-lone-surrogate-key",
        lambda: canonical_json_bytes({"\ud800": 1}),
        Refused(ValueError),
    ),
    _v(
        "identity-projection-max-quotes-index",
        lambda: canonical_json_bytes(file_identity_projection(IDENTITY_MAX)),
        b'{"file_index":"340282366920938463463374607431768211455","volume_serial":"FFFFFFFF"}',
    ),
    _v(
        "identity-projection-zero-index",
        lambda: canonical_json_bytes(file_identity_projection(FileIdentity("00000001", 0))),
        b'{"file_index":"0","volume_serial":"00000001"}',
    ),
    _v(
        "identity-projection-absent",
        lambda: canonical_json_bytes(file_identity_projection(None)),
        b"null",
    ),
    _v(
        "metadata-projection",
        lambda: canonical_json_bytes(
            metadata_projection(MetadataSnapshot(4294967295, 9223372036854775807))
        ),
        b'{"attributes":4294967295,"created_ns":9223372036854775807}',
    ),
    _v(
        "metadata-projection-no-creation-time",
        lambda: canonical_json_bytes(metadata_projection(MetadataSnapshot(0, None))),
        b'{"attributes":0,"created_ns":null}',
    ),
    _v(
        "stat-projection-file",
        lambda: canonical_json_bytes(file_stat_projection(_stat())),
        b'{"file_identity":{"file_index":"340282366920938463463374607431768211455",'
        b'"volume_serial":"FFFFFFFF"},"kind":"file","metadata":{"attributes":1,'
        b'"created_ns":3},"mtime_ns":11,"nlink":1,"size":7}',
    ),
    _v(
        "stat-projection-directory-without-identity",
        lambda: canonical_json_bytes(
            file_stat_projection(
                _stat(EntryKind.DIRECTORY, 0, 9223372036854775807, None, 2, 16, None)
            )
        ),
        b'{"file_identity":null,"kind":"directory","metadata":{"attributes":16,'
        b'"created_ns":null},"mtime_ns":9223372036854775807,"nlink":2,"size":0}',
    ),
    _v(
        "stat-projection-absent",
        lambda: canonical_json_bytes(file_stat_projection(None)),
        b"null",
    ),
    _v(
        "root-projection-non-ascii",
        lambda: canonical_json_bytes(
            root_projection(Root("C:\\r\u00e9sum\u00e9\\\U0001f642", "root-\u6d77"))
        ),
        b'{"path":"C:\\\\r\xc3\xa9sum\xc3\xa9\\\\\xf0\x9f\x99\x82","root_id":"root-\xe6\xb5\xb7"}',
    ),
    _v(
        "volume-id-projection",
        lambda: canonical_json_bytes(volume_id_projection(VolumeId("0000ABCD", "ReFS"))),
        b'{"fs_type":"ReFS","serial":"0000ABCD"}',
    ),
    _v(
        "volume-id-projection-absent",
        lambda: canonical_json_bytes(volume_id_projection(None)),
        b"null",
    ),
    _v(
        "volume-evidence-projection",
        lambda: canonical_json_bytes(
            volume_evidence_projection(
                VolumeEvidence("L\u00e9", "\\\\?\\Volume{1}\\", True)
            )
        ),
        b'{"clone_ambiguous":true,"device_id":"\\\\\\\\?\\\\Volume{1}\\\\","label":"L\xc3\xa9"}',
    ),
    _v(
        "volume-evidence-projection-defaults",
        lambda: canonical_json_bytes(volume_evidence_projection(VolumeEvidence())),
        b'{"clone_ambiguous":false,"device_id":null,"label":null}',
    ),
    _v(
        "capability-projection-unknown-seek-penalty",
        lambda: canonical_json_bytes(capability_profile_projection(PROFILE_SOURCE)),
        b'{"fs_type":"NTFS","incurs_seek_penalty":null,"max_path":32767,'
        b'"mtime_granularity_ns":100,"stable_file_identity":true,'
        b'"supports_ads":true,"supports_hardlinks":true}',
    ),
    _v(
        "capability-projection-no-seek-penalty",
        lambda: canonical_json_bytes(capability_profile_projection(PROFILE_TARGET)),
        b'{"fs_type":"REFS","incurs_seek_penalty":false,"max_path":32767,'
        b'"mtime_granularity_ns":100,"stable_file_identity":true,'
        b'"supports_ads":false,"supports_hardlinks":false}',
    ),
    _v(
        "preservation-projection",
        lambda: canonical_json_bytes(
            preservation_policy_projection(PreservationPolicy(True, False, True))
        ),
        b'{"preserve_acl":true,"preserve_ads":true,"preserve_created":false}',
    ),
    _v(
        "filter-projection-canonical-order",
        lambda: canonical_json_bytes(filter_set_projection(FilterSet(("a*", "B/c", "a*")))),
        b'{"patterns":["B\\\\c","a*"]}',
    ),
    _v(
        "assignment-projection",
        lambda: canonical_json_bytes(
            assignment_projection(
                Assignment(
                    "identity",
                    "1",
                    (
                        DestinationAssignment(
                            "d\\\u00c9.txt", "D\\\u00c9.TXT", "d\\\u00c9.txt", "D\\\u00c9.TXT"
                        ),
                        DestinationAssignment("a", "A", "b", "B", "group", "conflict"),
                    ),
                )
            )
        ),
        b'{"items":[{"conflict":null,"group_id":null,"source_rel_path":"d\\\\\xc3\x89.txt",'
        b'"source_rel_path_key":"D\\\\\xc3\x89.TXT","target_rel_path":"d\\\\\xc3\x89.txt",'
        b'"target_rel_path_key":"D\\\\\xc3\x89.TXT"},{"conflict":"conflict",'
        b'"group_id":"group","source_rel_path":"a","source_rel_path_key":"A",'
        b'"target_rel_path":"b","target_rel_path_key":"B"}],'
        b'"policy_name":"identity","policy_version":"1"}',
    ),
    _v(
        "operation-projection-copy",
        lambda: canonical_json_bytes(operation_projection(_plan().operations[0])),
        b'{"blocked_reason":null,"content_bytes":7,"dependencies":[],'
        b'"intended":{"file_identity":{"file_index":"340282366920938463463374607431768211453",'
        b'"volume_serial":"00000001"},"kind":"file",'
        b'"metadata":{"attributes":1,"created_ns":3},"mtime_ns":11,"nlink":1,'
        b'"size":7},"kind":"copy","metadata":{"attributes":1,"created_ns":3},'
        b'"op_id":"ed4f7861d052e725b4b9326eca315251",'
        b'"prior_target_expected":null,"prior_target_rel_path":null,'
        b'"reason":"source_only",'
        b'"source_expected":{"file_identity":'
        b'{"file_index":"340282366920938463463374607431768211455",'
        b'"volume_serial":"FFFFFFFF"},"kind":"file",'
        b'"metadata":{"attributes":1,"created_ns":3},"mtime_ns":11,"nlink":1,'
        b'"size":7},"source_rel_path":"a.txt","target_expected":null,'
        b'"target_rel_path":"a.txt"}',
    ),
    _v(
        "operation-projection-move-blocked",
        lambda: canonical_json_bytes(
            operation_projection(
                PlanOperation(
                    op_id=OpId("0123456789abcdef0123456789abcdef"),
                    kind=OperationKind.MOVE_UPDATE,
                    source_rel_path="s\\\u00e9",
                    target_rel_path="t\\\u00e9",
                    source_expected=_stat(identity=None, created_ns=None),
                    target_expected=_stat(
                        EntryKind.FILE, 0, 0, FileIdentity("00000001", 0), 3, 0, 0
                    ),
                    intended=None,
                    prior_target_rel_path="p\\\u00e9",
                    prior_target_expected=_stat(EntryKind.DIRECTORY, 0, 5, None, 1, 16, 9),
                    metadata=MetadataSnapshot(0, None),
                    content_bytes=9223372036854775807,
                    dependencies=(OpId("f" * 32), OpId("e" * 32)),
                    reason=OperationReason.IDENTITY_RENAME_CHANGED,
                    blocked_reason=BlockedReason.DESTINATION_COLLISION,
                )
            )
        ),
        b'{"blocked_reason":"destination_collision",'
        b'"content_bytes":9223372036854775807,'
        b'"dependencies":["ffffffffffffffffffffffffffffffff",'
        b'"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"],"intended":null,'
        b'"kind":"move_update","metadata":{"attributes":0,"created_ns":null},'
        b'"op_id":"0123456789abcdef0123456789abcdef",'
        b'"prior_target_expected":{"file_identity":null,"kind":"directory",'
        b'"metadata":{"attributes":16,"created_ns":9},"mtime_ns":5,"nlink":1,'
        b'"size":0},"prior_target_rel_path":"p\\\\\xc3\xa9",'
        b'"reason":"identity_rename_changed",'
        b'"source_expected":{"file_identity":null,"kind":"file",'
        b'"metadata":{"attributes":1,"created_ns":null},"mtime_ns":11,'
        b'"nlink":1,"size":7},"source_rel_path":"s\\\\\xc3\xa9",'
        b'"target_expected":{"file_identity":{"file_index":"0",'
        b'"volume_serial":"00000001"},"kind":"file",'
        b'"metadata":{"attributes":0,"created_ns":0},"mtime_ns":0,"nlink":3,'
        b'"size":0},"target_rel_path":"t\\\\\xc3\xa9"}',
    ),
    _v(
        "selection-digest-empty",
        lambda: selection_digest(frozenset()).hex(),
        "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
    ),
    _v(
        "selection-digest-two-ids",
        lambda: selection_digest(frozenset({_ID_ZERO, _ID_F})).hex(),
        "d9342093bcb74d1506e36b230763b53c4a04cc6a374fa23bfaa0c7c1d78a8f38",
    ),
    _v(
        "selection-digest-ignores-input-order",
        lambda: selection_digest([_ID_F, _ID_ZERO]).hex(),
        "d9342093bcb74d1506e36b230763b53c4a04cc6a374fa23bfaa0c7c1d78a8f38",
    ),
    _v(
        "selection-digest-one-id",
        lambda: selection_digest(frozenset({_ID_F})).hex(),
        "4bb8b33bec477a8a3993fcc2f21e8c5ff063d48f1fa1ab31671764b6a3ccf267",
    ),
    _v(
        "operation-id-copy",
        lambda: _operation_id(
            OperationKind.COPY, "a.txt", "a.txt", None, OperationReason.SOURCE_ONLY
        ),
        "ed4f7861d052e725b4b9326eca315251",
    ),
    _v(
        "operation-id-move-non-ascii",
        lambda: _operation_id(
            OperationKind.MOVE,
            "s\\\u00e9\U0001f642",
            "t\\\u00e9\U0001f642",
            "p\\\u00e9",
            OperationReason.IDENTITY_RENAME,
        ),
        "6fb450556a4bc2ee3adbb2277b127389",
    ),
    _v(
        "operation-id-mkdir-without-source",
        lambda: _operation_id(
            OperationKind.MKDIR, None, "d", None, OperationReason.REQUIRED_DIRECTORY
        ),
        "aca838919b8af4ca4e875f1bf9ae31a4",
    ),
    _v(
        "operation-id-distinguishes-case",
        lambda: _operation_id(OperationKind.RECASE, "A", "a", None, OperationReason.CASE_MISMATCH),
        "b17be19aec06270a894fcf5ed34f0365",
    ),
    _v(
        "operation-reason-values",
        lambda: _values(OperationReason),
        frozenset(
            {
                "source_only", "metadata_changed", "metadata_match", "identity_rename",
                "identity_rename_changed", "required_directory", "target_only",
                "directory_cleanup", "unsupported", "case_mismatch",
                "unicode_normalization_mismatch", "case_collision", "type_collision",
                "policy_collision",
            }
        ),
    ),
    _v(
        "deletion-policy-values",
        lambda: _values(DeletionPolicy),
        frozenset({"trash", "additive", "mirror"}),
    ),
    _v(
        "policy-fingerprint-default",
        lambda: policy_fingerprint(SyncOptions()),
        "49affee346359eb0ff8670f883e1ef6db9b96bf39a7afb01f1246e065d20dee3",
    ),
    _v(
        "policy-fingerprint-additive-and-filters",
        lambda: policy_fingerprint(
            SyncOptions(
                deletion_policy=DeletionPolicy.ADDITIVE,
                filters=FilterSet(("*.tmp", "Dir/Sub")),
            )
        ),
        "ae49bb7480411bf5e255e9224f99a250ce5ab55d3711639dfc8f54d532f42afd",
    ),
    _v(
        "policy-fingerprint-mirror-and-flags",
        lambda: policy_fingerprint(
            SyncOptions(
                deletion_policy=DeletionPolicy.MIRROR,
                preservation=PreservationPolicy(True, False, True),
                trash_on_update=False,
                propagate_source_casing=True,
                internal_mirror_authorized=True,
            )
        ),
        "f730bbe0c30b9f3535e521ef597a43b5c1b1f7a6fda3aa138df20a2efbcc5f50",
    ),
    _v(
        "plan-fingerprint-single-copy",
        lambda: str(plan_fingerprint(_plan())),
        "5a600ec1f972b81749ffd8e61bb57db21d5c68245a4ff322e50b77581f0d7699",
    ),
    _v(
        "plan-fingerprint-ignores-its-own-field",
        lambda: _fingerprint_of_plan_variant(fingerprint=PlanFingerprint("another")),
        "5a600ec1f972b81749ffd8e61bb57db21d5c68245a4ff322e50b77581f0d7699",
    ),
)

# --------------------------------------------------------------------------
# evidence v2

_CONTENT_DIGEST = bytes(range(16))
_ATTESTED_STAT = _stat(
    EntryKind.FILE,
    9223372036854775807,
    9223372036854775807,
    IDENTITY_MAX,
    1,
    4294967295,
    9223372036854775807,
)

EVIDENCE_V2 = (
    _v("digest-empty-input", lambda: _digest().hex(), "99aa06d3014798d86001c324468d497f"),
    _v(
        "digest-abc",
        lambda: _digest(b"abc").hex(),
        "06b05ab6733a618578af5f94892f3950",
    ),
    _v(
        "digest-chunking-does-not-change-it",
        lambda: _digest(b"a", b"b", b"c").hex(),
        "06b05ab6733a618578af5f94892f3950",
    ),
    _v(
        "digest-memoryview-chunk",
        lambda: _digest(b"a", memoryview(b"bc")).hex(),
        "06b05ab6733a618578af5f94892f3950",
    ),
    _v(
        "digest-long-input",
        lambda: _digest(b"\x00" * 4096).hex(),
        "3ee8dc4f9e7ee49593d76fe148c689ba",
    ),
    _v(
        "digest-accepts-sixteen-bytes",
        lambda: require_content_digest(_CONTENT_DIGEST),
        _CONTENT_DIGEST,
    ),
    _v(
        "digest-refuses-fifteen-bytes",
        lambda: require_content_digest(b"\x00" * 15),
        Refused(HasherContractError),
    ),
    _v(
        "digest-refuses-seventeen-bytes",
        lambda: require_content_digest(b"\x00" * 17),
        Refused(HasherContractError),
    ),
    _v(
        "digest-refuses-bytearray",
        lambda: require_content_digest(bytearray(16)),
        Refused(HasherContractError),
    ),
    _v(
        "evidence-refuses-other-algorithm",
        lambda: ContentEvidence("sha256", _CONTENT_DIGEST, 1, Provenance.COPY_ATTESTED, T0),
        Refused(ValueError),
    ),
    _v(
        "evidence-refuses-short-digest",
        lambda: ContentEvidence("xxh3_128", b"\x00" * 15, 1, Provenance.COPY_ATTESTED, T0),
        Refused(ValueError),
    ),
    _v(
        "evidence-refuses-size-2-pow-63",
        lambda: ContentEvidence(
            "xxh3_128", _CONTENT_DIGEST, 9223372036854775808, Provenance.COPY_ATTESTED, T0
        ),
        Refused(ScalarDomainError),
    ),
    _v(
        "evidence-refuses-naive-time",
        lambda: ContentEvidence(
            "xxh3_128", _CONTENT_DIGEST, 1, Provenance.COPY_ATTESTED, datetime(2026, 8, 25)
        ),
        Refused(ValueError),
    ),
    _v(
        "evidence-refuses-offset-time",
        lambda: ContentEvidence(
            "xxh3_128",
            _CONTENT_DIGEST,
            1,
            Provenance.COPY_ATTESTED,
            datetime(2026, 8, 25, tzinfo=timezone(timedelta(hours=8))),
        ),
        Refused(ValueError),
    ),
    _v("provenance-values", lambda: _values(Provenance), frozenset({"copy", "readback", "verify"})),
    _v("entry-kind-values", lambda: _values(EntryKind), frozenset({"file", "directory"})),
    _v(
        "inventory-state-values",
        lambda: _values(InventoryState),
        frozenset({"present", "missing", "unsupported"}),
    ),
    _v(
        "invalidation-reason-values",
        lambda: _values(VerificationInvalidationReason),
        frozenset({"metadata-drift", "hash-mismatch"}),
    ),
    _v(
        "unsupported-reason-values",
        lambda: _values(UnsupportedReason),
        frozenset(
            {"placeholder", "reparse_point", "access_denied", "disappeared", "unknown_type"}
        ),
    ),
    _v(
        "attested-stat-leaves-at-bounds",
        lambda: file_stat_fact(_ATTESTED_STAT),
        (
            "file",
            9223372036854775807,
            9223372036854775807,
            "FFFFFFFF",
            340282366920938463463374607431768211455,
            1,
            4294967295,
            9223372036854775807,
        ),
    ),
    _v(
        "attested-stat-leaves-directory-without-identity",
        lambda: file_stat_fact(_stat(EntryKind.DIRECTORY, 0, 0, None, 2, 16, None)),
        ("directory", 0, 0, None, None, 2, 16, None),
    ),
    _v(
        "attested-stat-keeps-nanosecond-resolution",
        lambda: file_stat_fact(_stat(mtime_ns=1700000000123456789))[2],
        1700000000123456789,
    ),
    _v(
        "attested-stat-refuses-size-2-pow-63",
        lambda: _stat(size=9223372036854775808),
        Refused(ScalarDomainError),
    ),
    _v(
        "attested-stat-refuses-mtime-2-pow-63",
        lambda: _stat(mtime_ns=9223372036854775808),
        Refused(ScalarDomainError),
    ),
    _v(
        "attested-stat-refuses-negative-mtime",
        lambda: _stat(mtime_ns=-1),
        Refused(ScalarDomainError),
    ),
)

# --------------------------------------------------------------------------
# recording v1

RECORDING_V1 = (
    _v("status-values", lambda: _values(RecordingStatus), frozenset({"ok", "degraded"})),
    _v(
        "item-reason-values",
        lambda: _values(ItemRecordingReason),
        frozenset({"record-write-failed", "unrecorded-mutation", "recording-prerequisite-failed"}),
    ),
    _v(
        "task-issue-reason-values",
        lambda: _values(TaskRecordingIssueReason),
        frozenset(
            {
                "recording-open-failed",
                "final-flush-failed",
                "finish-failed",
                "recording-close-failed",
                "post-settlement-state-diverged",
            }
        ),
    ),
    _v(
        "scan-warning-code-values",
        lambda: _values(ScanWarningCode),
        frozenset(
            {
                "root_unavailable", "volume_unavailable", "access_denied", "disappeared",
                "enumeration_error", "path_unrepresentable", "case_collision",
                "duplicate_identity", "multi_link", "placeholder", "reparse_point",
                "unknown_type", "scalar_unrepresentable",
            }
        ),
    ),
    _v(
        "scan-scope-kind-values",
        lambda: _values(ScanScopeKind),
        frozenset({"full", "paths", "subtrees"}),
    ),
    _v(
        "visibility-action-values",
        lambda: _values(InventoryVisibilityAction),
        frozenset({"acknowledge", "restore"}),
    ),
    _v(
        "item-ok",
        lambda: _recording_facts(_item()),
        {
            "recording": "ok",
            "recording_reason": None,
            "recording_detail": None,
            "detail_omitted_count": 0,
        },
    ),
    _v(
        "item-write-failed-keeps-success",
        lambda: _recording_facts(
            _item(
                recording=RecordingStatus.DEGRADED,
                recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
                recording_detail="OSError: disk \u00e9 \U0001f642",
            )
        ),
        {
            "recording": "degraded",
            "recording_reason": "record-write-failed",
            "recording_detail": "OSError: disk \u00e9 \U0001f642",
            "detail_omitted_count": 0,
        },
    ),
    _v(
        "item-unrecorded-mutation",
        lambda: _recording_facts(
            _item(
                outcome=Outcome.FAILED,
                recording=RecordingStatus.DEGRADED,
                recording_reason=ItemRecordingReason.UNRECORDED_MUTATION,
            )
        ),
        {
            "recording": "degraded",
            "recording_reason": "unrecorded-mutation",
            "recording_detail": None,
            "detail_omitted_count": 0,
        },
    ),
    _v(
        "item-prerequisite-failed",
        lambda: _recording_facts(
            _item(
                outcome=Outcome.FAILED,
                recording=RecordingStatus.DEGRADED,
                recording_reason=ItemRecordingReason.RECORDING_PREREQUISITE_FAILED,
                recording_detail="x",
            )
        ),
        {
            "recording": "degraded",
            "recording_reason": "recording-prerequisite-failed",
            "recording_detail": "x",
            "detail_omitted_count": 0,
        },
    ),
    _v(
        "item-detail-at-1024-bytes-is-kept",
        lambda: len(
            _recording_facts(
                _item(
                    recording=RecordingStatus.DEGRADED,
                    recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
                    recording_detail="\u00e9" * 512,
                )
            )["recording_detail"].encode("utf-8")
        ),
        1024,
    ),
    _v(
        "item-detail-over-1024-bytes-is-omitted-not-truncated",
        lambda: _recording_facts(
            _item(
                recording=RecordingStatus.DEGRADED,
                recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
                recording_detail="\u00e9" * 512 + "a",
            )
        ),
        {
            "recording": "degraded",
            "recording_reason": "record-write-failed",
            "recording_detail": None,
            "detail_omitted_count": 1,
        },
    ),
    _v(
        "item-detail-with-lone-surrogate-is-omitted",
        lambda: _recording_facts(
            _item(
                recording=RecordingStatus.DEGRADED,
                recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
                recording_detail="a\ud800",
                detail_omitted_count=3,
            )
        ),
        {
            "recording": "degraded",
            "recording_reason": "record-write-failed",
            "recording_detail": None,
            "detail_omitted_count": 4,
        },
    ),
    _v(
        "item-refuses-ok-with-reason",
        lambda: _item(recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED),
        Refused(ValueError),
    ),
    _v(
        "item-refuses-degraded-without-reason",
        lambda: _item(recording=RecordingStatus.DEGRADED),
        Refused(ValueError),
    ),
    _v(
        "item-refuses-write-failed-on-failed-outcome",
        lambda: _item(
            outcome=Outcome.FAILED,
            recording=RecordingStatus.DEGRADED,
            recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
        ),
        Refused(ValueError),
    ),
    _v(
        "item-refuses-unrecorded-mutation-on-success",
        lambda: _item(
            recording=RecordingStatus.DEGRADED,
            recording_reason=ItemRecordingReason.UNRECORDED_MUTATION,
        ),
        Refused(ValueError),
    ),
    _v(
        "integrity-item-recording",
        lambda: {
            key: result_item_to_dict(
                IntegrityOutcome(
                    item_id="7:42",
                    row_id="42",
                    location_id="7",
                    path="a",
                    result=IntegrityResult.VERIFIED,
                    recording=RecordingStatus.DEGRADED,
                    detail="a\ud800",
                    detail_omitted_count=1,
                )
            )[key]
            for key in ("recording", "detail", "detail_omitted_count")
        },
        {"recording": "degraded", "detail": None, "detail_omitted_count": 2},
    ),
    _v(
        "terminal-ok",
        lambda: {
            key: terminal_summary_to_dict(_terminal())[key]
            for key in ("recording", "audit", "recording_degraded_items", "recording_issues")
        },
        {"recording": "ok", "audit": "ok", "recording_degraded_items": 0, "recording_issues": []},
    ),
    _v(
        "terminal-degraded-recording-and-audit",
        lambda: {
            key: terminal_summary_to_dict(
                _terminal(
                    recording=RecordingStatus.DEGRADED,
                    audit=RecordingStatus.DEGRADED,
                    recording_degraded_items=2,
                    recording_issues=(
                        TaskRecordingIssue(
                            TaskRecordingIssueReason.FINAL_FLUSH_FAILED, "flush \u00e9"
                        ),
                        TaskRecordingIssue(TaskRecordingIssueReason.POST_SETTLEMENT_STATE_DIVERGED),
                    ),
                )
            )[key]
            for key in ("recording", "audit", "recording_degraded_items", "recording_issues")
        },
        {
            "recording": "degraded",
            "audit": "degraded",
            "recording_degraded_items": 2,
            "recording_issues": [
                {"reason": "final-flush-failed", "detail": "flush \u00e9"},
                {"reason": "post-settlement-state-diverged", "detail": None},
            ],
        },
    ),
    _v(
        "terminal-refuses-ok-with-degraded-witness",
        lambda: _terminal(recording_degraded_items=1),
        Refused(ValueError),
    ),
)

# --------------------------------------------------------------------------
# event v5

_PROGRESS_FULL = Progress(
    phase="execute",
    items_done=2,
    items_total=4,
    bytes_done=9223372036854775806,
    bytes_total=9223372036854775807,
    current_path="folder\\f\u00efle.bin",
    item_id=ITEM_ID,
    item_type="operation",
    item_attempt_id=ATTEMPT_ID,
    item_bytes_done=7,
    item_bytes_total=8,
)
_PROGRESS_EMPTY = Progress("scan", 0, None, 0, None, None)
_DETAIL_ITEM = ItemOutcome(
    item_id=ITEM_ID,
    kind=OperationKind.UPDATE,
    path="d\u00e9\u6d77\\\U0001f642.bin",
    outcome=Outcome.SKIPPED,
    reason="user-deselected",
    detail={
        "published_path": "d\u00e9\u6d77\\\U0001f642.bin",
        "publish_state": "published",
        "durability_warnings": ("w\u00e9", "w2"),
        "continued": True,
        "excluded_dependencies": (ITEM_ID,),
        "message": 'say "hi"\n',
    },
)
_DEGRADED_ITEM = ItemOutcome(
    item_id=ITEM_ID,
    kind=OperationKind.COPY,
    path="folder\\file.bin",
    outcome=Outcome.SUCCEEDED,
    detail={"published_path": "folder\\file.bin", "publish_state": "published"},
    recording=RecordingStatus.DEGRADED,
    recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
    recording_detail="RecordingError: durable row unavailable",
    detail_omitted_count=1,
)
_INTEGRITY_ITEM = IntegrityOutcome(
    item_id="7:42",
    row_id="42",
    location_id="7",
    path="folder\\file.bin",
    result=IntegrityResult.MISMATCHED,
    reason=IntegrityReason.HASH_MISMATCH,
    detail="digest differs",
    read_strategy=ReadStrategy.WINDOWS_UNBUFFERED,
    recording=RecordingStatus.OK,
    record_disposition=RecordDisposition.APPLIED,
    phase=IntegrityMode.VERIFY.value,
)
_INTEGRITY_SPARSE = IntegrityOutcome(
    item_id="7:43",
    row_id=None,
    location_id=None,
    path="a",
    result=IntegrityResult.CANCELED,
    phase=IntegrityMode.BASELINE.value,
)
_TERMINAL_FULL = _terminal(
    status=SessionState.FAILED,
    recording=RecordingStatus.DEGRADED,
    audit=RecordingStatus.DEGRADED,
    disposition=Disposition.RAN,
    phases=(
        PhaseResult(
            "execute", PhaseStatus.FAILED, 2, 4, 9223372036854775806, 9223372036854775807, "boom"
        ),
        PhaseResult("verify", PhaseStatus.INCOMPLETE, 0, None, 0, None, None),
    ),
    bytes_done=9223372036854775806,
    bytes_total=9223372036854775807,
    error=FailureDetail("OSError", "boom \u00e9 \U0001f642"),
    recording_degraded_items=1,
    recording_issues=(TaskRecordingIssue(TaskRecordingIssueReason.FINISH_FAILED, "finish"),),
    omitted_detail_count=5,
)
_TERMINAL_REFUSED = _refused_terminal(ReviewFactLimitExceeded.plan_logical_bytes())
_ENVELOPE_DICT = {
    "body": {"state": "running"},
    "body_type": "StateChanged",
    "schema_version": 5,
    "at": "2026-08-25T00:00:00+00:00",
    "seq": 1,
    "session_id": "0123456789abcdef0123456789abcdef",
}

EVENT_V5 = (
    _v(
        "envelope-state-changed",
        lambda: _event(1, T0, StateChanged(SessionState.RUNNING)),
        b'{"at":"2026-08-25T00:00:00+00:00","body":{"state":"running"},'
        b'"body_type":"StateChanged","schema_version":5,"seq":1,'
        b'"session_id":"0123456789abcdef0123456789abcdef"}',
    ),
    _v(
        "envelope-phase-changed-with-microseconds",
        lambda: _event(2, T1, PhaseChanged("execute")),
        b'{"at":"2026-08-25T12:34:56.500000+00:00",'
        b'"body":{"phase":"execute"},"body_type":"PhaseChanged",'
        b'"schema_version":5,"seq":2,'
        b'"session_id":"0123456789abcdef0123456789abcdef"}',
    ),
    _v(
        "envelope-zero-microseconds-omitted",
        lambda: _event(3, T_ZERO_US, PhaseChanged("verify")),
        b'{"at":"2026-08-25T00:00:00+00:00","body":{"phase":"verify"},'
        b'"body_type":"PhaseChanged","schema_version":5,"seq":3,'
        b'"session_id":"0123456789abcdef0123456789abcdef"}',
    ),
    _v(
        "envelope-maximum-timestamp-and-sequence",
        lambda: _event(9007199254740991, T_MAX, Gap(9007199254740991)),
        b'{"at":"9999-12-31T23:59:59.999999+00:00",'
        b'"body":{"first_missed_seq":9007199254740991},"body_type":"Gap",'
        b'"schema_version":5,"seq":9007199254740991,'
        b'"session_id":"0123456789abcdef0123456789abcdef"}',
    ),
    _v(
        "envelope-progress-full",
        lambda: _event(4, T0, _PROGRESS_FULL),
        b'{"at":"2026-08-25T00:00:00+00:00",'
        b'"body":{"bytes_done":"9223372036854775806",'
        b'"bytes_total":"9223372036854775807",'
        b'"current_path":"folder\\\\f\xc3\xafle.bin",'
        b'"item_attempt_id":"00112233445566778899aabbccddeeff",'
        b'"item_bytes_done":"7","item_bytes_total":"8",'
        b'"item_id":"fedcba9876543210fedcba9876543210",'
        b'"item_type":"operation","items_done":2,"items_total":4,'
        b'"phase":"execute"},"body_type":"Progress","schema_version":5,'
        b'"seq":4,"session_id":"0123456789abcdef0123456789abcdef"}',
    ),
    _v(
        "envelope-progress-empty",
        lambda: _event(5, T0, _PROGRESS_EMPTY),
        b'{"at":"2026-08-25T00:00:00+00:00","body":{"bytes_done":"0",'
        b'"bytes_total":null,"current_path":null,"item_attempt_id":null,'
        b'"item_bytes_done":null,"item_bytes_total":null,"item_id":null,'
        b'"item_type":null,"items_done":0,"items_total":null,"phase":"scan"},'
        b'"body_type":"Progress","schema_version":5,"seq":5,'
        b'"session_id":"0123456789abcdef0123456789abcdef"}',
    ),
    _v(
        "envelope-item-details",
        lambda: _event(6, T0, _DETAIL_ITEM),
        b'{"at":"2026-08-25T00:00:00+00:00",'
        b'"body":{"detail":{"continued":true,'
        b'"durability_warnings":["w\xc3\xa9","w2"],'
        b'"excluded_dependencies":["fedcba9876543210fedcba9876543210"],'
        b'"message":"say \\"hi\\"\\n","publish_state":"published",'
        b'"published_path":"d\xc3\xa9\xe6\xb5\xb7\\\\\xf0\x9f\x99\x82.bin"},'
        b'"detail_omitted_count":0,'
        b'"item_id":"fedcba9876543210fedcba9876543210",'
        b'"item_type":"operation","kind":"update",'
        b'"path":"d\xc3\xa9\xe6\xb5\xb7\\\\\xf0\x9f\x99\x82.bin",'
        b'"phase":"execute","reason":"user-deselected","recording":"ok",'
        b'"recording_detail":null,"recording_reason":null,'
        b'"result":"skipped"},"body_type":"ItemOutcome","schema_version":5,'
        b'"seq":6,"session_id":"0123456789abcdef0123456789abcdef"}',
    ),
    _v(
        "envelope-item-degraded-recording",
        lambda: _event(7, T0, _DEGRADED_ITEM),
        b'{"at":"2026-08-25T00:00:00+00:00",'
        b'"body":{"detail":{"publish_state":"published",'
        b'"published_path":"folder\\\\file.bin"},"detail_omitted_count":1,'
        b'"item_id":"fedcba9876543210fedcba9876543210",'
        b'"item_type":"operation","kind":"copy","path":"folder\\\\file.bin",'
        b'"phase":"execute","reason":null,"recording":"degraded",'
        b'"recording_detail":"RecordingError: durable row unavailable",'
        b'"recording_reason":"record-write-failed","result":"succeeded"},'
        b'"body_type":"ItemOutcome","schema_version":5,"seq":7,'
        b'"session_id":"0123456789abcdef0123456789abcdef"}',
    ),
    _v(
        "envelope-integrity-item",
        lambda: _event(8, T0, _INTEGRITY_ITEM),
        b'{"at":"2026-08-25T00:00:00+00:00",'
        b'"body":{"detail":"digest differs","detail_omitted_count":0,'
        b'"item_id":"7:42","item_type":"integrity","kind":"integrity",'
        b'"location_id":"7","path":"folder\\\\file.bin","phase":"verify",'
        b'"read_strategy":"windows-unbuffered","reason":"hash-mismatch",'
        b'"record_disposition":"applied","recording":"ok",'
        b'"result":"mismatched","row_id":"42"},'
        b'"body_type":"IntegrityOutcome","schema_version":5,"seq":8,'
        b'"session_id":"0123456789abcdef0123456789abcdef"}',
    ),
    _v(
        "envelope-integrity-item-sparse",
        lambda: _event(9, T0, _INTEGRITY_SPARSE),
        b'{"at":"2026-08-25T00:00:00+00:00","body":{"detail":null,'
        b'"detail_omitted_count":0,"item_id":"7:43","item_type":"integrity",'
        b'"kind":"integrity","location_id":null,"path":"a",'
        b'"phase":"baseline","read_strategy":null,"reason":null,'
        b'"record_disposition":null,"recording":"ok","result":"canceled",'
        b'"row_id":null},"body_type":"IntegrityOutcome","schema_version":5,'
        b'"seq":9,"session_id":"0123456789abcdef0123456789abcdef"}',
    ),
    _v(
        "envelope-terminal-full",
        lambda: _event(10, T0, Terminal(_TERMINAL_FULL)),
        b'{"at":"2026-08-25T00:00:00+00:00",'
        b'"body":{"result":{"audit":"degraded",'
        b'"bytes_done":"9223372036854775806",'
        b'"bytes_total":"9223372036854775807","canceled":false,'
        b'"disposition":"ran",'
        b'"error":{"message":"boom \xc3\xa9 \xf0\x9f\x99\x82",'
        b'"type_name":"OSError"},"omitted_detail_count":5,'
        b'"phases":[{"bytes_done":"9223372036854775806",'
        b'"bytes_total":"9223372036854775807","error":"boom","items_done":2,'
        b'"items_total":4,"phase":"execute","status":"failed"},'
        b'{"bytes_done":"0","bytes_total":null,"error":null,"items_done":0,'
        b'"items_total":null,"phase":"verify","status":"incomplete"}],'
        b'"recording":"degraded","recording_degraded_items":1,'
        b'"recording_issues":[{"detail":"finish","reason":"finish-failed"}],'
        b'"review_fact_limit":null,"status":"failed"}},'
        b'"body_type":"Terminal","schema_version":5,"seq":10,'
        b'"session_id":"0123456789abcdef0123456789abcdef"}',
    ),
    _v(
        "envelope-terminal-review-limit",
        lambda: _event(11, T0, Terminal(_TERMINAL_REFUSED)),
        b'{"at":"2026-08-25T00:00:00+00:00","body":{"result":{"audit":"ok",'
        b'"bytes_done":"0","bytes_total":"0","canceled":false,'
        b'"disposition":"unrun","error":null,"omitted_detail_count":0,'
        b'"phases":[],"recording":"ok","recording_degraded_items":0,'
        b'"recording_issues":[],"review_fact_limit":{"axis":"logical-bytes",'
        b'"byte_limit":"9223372036854775807","population":"domain",'
        b'"reason":"review_fact_limit_exceeded","row_limit":null,'
        b'"tree_kind":"plan"},"status":"refused"}},"body_type":"Terminal",'
        b'"schema_version":5,"seq":11,'
        b'"session_id":"0123456789abcdef0123456789abcdef"}',
    ),
    _v(
        "envelope-terminal-review-limit-rows-150000",
        lambda: _event(
            12, T0, Terminal(_refused_terminal(ReviewFactLimitExceeded.plan_domain_rows()))
        ),
        b'{"at":"2026-08-25T00:00:00+00:00","body":{"result":{"audit":"ok",'
        b'"bytes_done":"0","bytes_total":"0","canceled":false,'
        b'"disposition":"unrun","error":null,"omitted_detail_count":0,'
        b'"phases":[],"recording":"ok","recording_degraded_items":0,'
        b'"recording_issues":[],"review_fact_limit":{"axis":"rows",'
        b'"byte_limit":null,"population":"domain",'
        b'"reason":"review_fact_limit_exceeded","row_limit":150000,'
        b'"tree_kind":"plan"},"status":"refused"}},"body_type":"Terminal",'
        b'"schema_version":5,"seq":12,'
        b'"session_id":"0123456789abcdef0123456789abcdef"}',
    ),
    _v(
        "envelope-terminal-review-limit-rows-120000",
        lambda: _event(
            12,
            T0,
            Terminal(
                _refused_terminal(
                    ReviewFactLimitExceeded(
                        "review_fact_limit_exceeded",
                        ReviewTreeKind.INVENTORY,
                        ReviewPopulation.INFORMATIONAL,
                        ReviewLimitAxis.ROWS,
                        120000,
                        None,
                    )
                )
            ),
        ),
        b'{"at":"2026-08-25T00:00:00+00:00","body":{"result":{"audit":"ok",'
        b'"bytes_done":"0","bytes_total":"0","canceled":false,'
        b'"disposition":"unrun","error":null,"omitted_detail_count":0,'
        b'"phases":[],"recording":"ok","recording_degraded_items":0,'
        b'"recording_issues":[],"review_fact_limit":{"axis":"rows",'
        b'"byte_limit":null,"population":"informational",'
        b'"reason":"review_fact_limit_exceeded","row_limit":120000,'
        b'"tree_kind":"inventory"},"status":"refused"}},"body_type":"Terminal",'
        b'"schema_version":5,"seq":12,'
        b'"session_id":"0123456789abcdef0123456789abcdef"}',
    ),
    _v(
        "dict-route-sorts-and-matches",
        lambda: validate_and_encode_event_v5_envelope(_ENVELOPE_DICT),
        b'{"at":"2026-08-25T00:00:00+00:00","body":{"state":"running"},'
        b'"body_type":"StateChanged","schema_version":5,"seq":1,'
        b'"session_id":"0123456789abcdef0123456789abcdef"}',
    ),
    _v(
        "dict-route-refuses-other-version",
        lambda: validate_and_encode_event_v5_envelope({**_ENVELOPE_DICT, "schema_version": 6}),
        Refused(ValueError),
    ),
    _v(
        "dict-route-refuses-offset-timestamp",
        lambda: validate_and_encode_event_v5_envelope(
            {**_ENVELOPE_DICT, "at": "2026-08-25T08:00:00+08:00"}
        ),
        Refused(ValueError),
    ),
    _v(
        "dict-route-refuses-zulu-timestamp",
        lambda: validate_and_encode_event_v5_envelope(
            {**_ENVELOPE_DICT, "at": "2026-08-25T00:00:00Z"}
        ),
        Refused(ValueError),
    ),
    _v(
        "dict-route-refuses-three-digit-fraction",
        lambda: validate_and_encode_event_v5_envelope(
            {**_ENVELOPE_DICT, "at": "2026-08-25T00:00:00.123+00:00"}
        ),
        Refused(ValueError),
    ),
    _v(
        "dict-route-refuses-extra-key",
        lambda: validate_and_encode_event_v5_envelope({**_ENVELOPE_DICT, "extra": 1}),
        Refused(ValueError),
    ),
    _v("reliable-event-byte-ceiling", lambda: MAX_RELIABLE_EVENT_CANONICAL_BYTES, 1048576),
    _v("detail-leaf-bounds", lambda: (MAX_DETAIL_LEAVES, MAX_DETAIL_PATH_LEAVES), (32, 8)),
    _v(
        "detail-key-vocabulary",
        lambda: frozenset(_DETAIL_KEYS),
        frozenset(
            {
                "backup", "backup_metadata", "backup_state", "backup_state_error",
                "blocked_reason", "cleanup_error", "destination_state", "durable_state",
                "error_type", "message", "mutation_durable_state", "mutation_state",
                "mutation_state_error", "old_state_error", "publish_state", "retry_error",
                "retry_error_type", "source_state", "state_error", "state_error_type",
                "target_state", "target_state_error", "temp_state", "trash_state_error",
                "backup_path", "mutation_destination", "prior_path", "published_path",
                "trash_path", "continued", "durability_warnings", "incomplete_sides",
                "excluded_dependencies",
            }
        ),
    ),
    _v(
        "exclusion-reason-values",
        lambda: frozenset(_EXCLUSION_REASONS),
        frozenset(
            {
                "blocked-correspondence", "blocked-dependency", "incomplete-scan",
                "user-deselected",
            }
        ),
    ),
    _v(
        "session-state-values",
        lambda: _values(SessionState),
        frozenset(
            {
                "pending", "running", "pausing", "paused", "canceling", "completed",
                "failed", "canceled", "refused", "interrupted",
            }
        ),
    ),
    _v(
        "phase-status-values",
        lambda: _values(PhaseStatus),
        frozenset({"completed", "failed", "canceled", "incomplete"}),
    ),
    _v("disposition-values", lambda: _values(Disposition), frozenset({"ran", "unrun"})),
    _v(
        "outcome-values",
        lambda: _values(Outcome),
        frozenset({"succeeded", "skipped", "failed", "canceled", "deferred", "blocked"}),
    ),
    _v(
        "operation-kind-values",
        lambda: _values(OperationKind),
        frozenset(
            {
                "copy", "update", "move", "move_update", "recase", "mkdir", "trash",
                "delete", "noop",
            }
        ),
    ),
    _v(
        "execution-reason-values",
        lambda: _values(ExecutionReason),
        frozenset(
            {
                "noop", "blocked", "dependency-failed", "source-drift", "target-drift",
                "destination-occupied", "wrong-type", "source-missing", "target-missing",
                "trash-collision", "unsafe-path", "sharing-violation", "acl-copy-failed",
                "cleanup-failed", "published-size-mismatch", "disk-capacity", "io-error",
                "policy-stop", "canceled", "canceled-after-publish", "canceled-after-mutation",
                "recorder-failed",
            }
        ),
    ),
    _v(
        "blocked-reason-values",
        lambda: _values(BlockedReason),
        frozenset(
            {
                "unsupported", "case_mismatch", "case_collision", "type_collision",
                "destination_collision", "blocked_dependency",
            }
        ),
    ),
    _v(
        "integrity-result-values",
        lambda: _values(IntegrityResult),
        frozenset(
            {
                "verified", "baselined", "mismatched", "modified", "missing",
                "unsupported", "canceled", "error",
            }
        ),
    ),
    _v(
        "integrity-reason-values",
        lambda: _values(IntegrityReason),
        frozenset(
            {
                "path-invalid", "inventory-missing", "inventory-unsupported", "not-found",
                "unsupported-read", "stat-changed", "read-drift", "hash-mismatch",
                "baseline-exists", "read-error", "recording-stale", "recording-conflict",
                "recording-error", "canceled",
            }
        ),
    ),
    _v(
        "integrity-mode-values",
        lambda: _values(IntegrityMode),
        frozenset({"baseline", "verify", "rebaseline"}),
    ),
    _v("read-strategy-values", lambda: _values(ReadStrategy), frozenset({"windows-unbuffered"})),
    _v(
        "record-disposition-values",
        lambda: _values(RecordDisposition),
        frozenset({"applied", "noop", "stale", "conflict"}),
    ),
    _v(
        "review-tree-kind-values",
        lambda: _values(ReviewTreeKind),
        frozenset({"plan", "inventory"}),
    ),
    _v(
        "review-population-values",
        lambda: _values(ReviewPopulation),
        frozenset({"domain", "informational"}),
    ),
    _v(
        "review-limit-axis-values",
        lambda: _values(ReviewLimitAxis),
        frozenset({"rows", "retained-bytes", "logical-bytes"}),
    ),
)

# --------------------------------------------------------------------------
# The table.

VECTORS: dict[tuple[str, int], tuple[Vector, ...]] = {
    ("event", 5): EVENT_V5,
    ("evidence", 2): EVIDENCE_V2,
    ("recording", 1): RECORDING_V1,
    ("preimage", 1): PREIMAGE_V1,
    ("identity", 1): IDENTITY_V1,
    ("numeric", 1): NUMERIC_V1,
    ("path-key", 1): PATH_KEY_V1,
}

# The seven formats the persistence layer may name, and the versions released
# in v0.1.0 (or first defined here). Released versions keep their vectors.
FORMAT_NAMES = frozenset(
    {"event", "evidence", "recording", "preimage", "identity", "numeric", "path-key"}
)
BASELINE_VERSIONS = {
    "event": 5,
    "evidence": 2,
    "recording": 1,
    "preimage": 1,
    "identity": 1,
    "numeric": 1,
    "path-key": 1,
}

_EXPECTED_TYPES = (bytes, str, int, bool, tuple, dict, frozenset, type(None), Refused)


def _current_vector_params() -> list[object]:
    params: list[object] = []
    for (name, version), vectors in VECTORS.items():
        if FORMAT_VERSIONS.get(name) != version:
            continue
        for vector in vectors:
            params.append(pytest.param(vector, id=f"{name}-v{version}-{vector.label}"))
    return params


@pytest.mark.parametrize("vector", _current_vector_params())
def test_current_format_vector(vector: Vector) -> None:
    expected = vector.expected
    if isinstance(expected, Refused):
        with pytest.raises(expected.error):
            vector.produce()
        return
    actual = vector.produce()
    assert type(actual) is type(expected)
    assert actual == expected


def test_every_format_has_current_vectors() -> None:
    for name, version in FORMAT_VERSIONS.items():
        assert VECTORS.get((name, version)), (
            f"format {name!r} version {version} has no known-answer vectors"
        )


def test_format_names_are_the_seven_persisted_formats() -> None:
    assert frozenset(FORMAT_VERSIONS) == FORMAT_NAMES
    assert frozenset(name for name, _version in VECTORS) == FORMAT_NAMES


def test_released_versions_keep_their_vectors() -> None:
    for name, version in BASELINE_VERSIONS.items():
        assert VECTORS.get((name, version)), (name, version)
        assert FORMAT_VERSIONS[name] >= version


def test_vector_table_is_well_formed() -> None:
    for (name, version), vectors in VECTORS.items():
        assert name in FORMAT_VERSIONS
        assert type(version) is int and 1 <= version <= FORMAT_VERSIONS[name]
        labels = [vector.label for vector in vectors]
        assert len(labels) == len(set(labels)), (name, version)
        for vector in vectors:
            assert type(vector) is Vector
            assert callable(vector.produce)
            assert type(vector.expected) in _EXPECTED_TYPES, (name, vector.label)


def test_every_format_constant_is_mapped_exactly_once() -> None:
    constants = {
        name: value
        for name, value in vars(formats_module).items()
        if name.endswith("_FORMAT_VERSION")
    }
    assert len(constants) == len(FORMAT_VERSIONS)
    assert sorted(constants.values()) == sorted(FORMAT_VERSIONS.values())
    for name, version in FORMAT_VERSIONS.items():
        constant = f"{name.upper().replace('-', '_')}_FORMAT_VERSION"
        assert constants[constant] == version
        assert type(version) is int and version >= 1


def test_format_mapping_is_immutable() -> None:
    with pytest.raises(TypeError):
        FORMAT_VERSIONS["event"] = 6  # type: ignore[index]
    with pytest.raises(TypeError):
        del FORMAT_VERSIONS["event"]  # type: ignore[attr-defined]


def test_event_format_is_the_core_event_schema_version() -> None:
    assert FORMAT_VERSIONS["event"] == CORE_EVENT_SCHEMA_VERSION
    assert FORMAT_VERSIONS["event"] == EVENT_V5_SCHEMA_VERSION


def test_current_event_envelopes_decode_and_encode_to_the_same_bytes() -> None:
    envelopes = [
        vector
        for vector in VECTORS[("event", FORMAT_VERSIONS["event"])]
        if vector.label.startswith("envelope-")
    ]
    assert envelopes
    for vector in envelopes:
        wire = vector.expected
        assert type(wire) is bytes
        decoded = envelope_from_dict(json.loads(wire))
        assert canonical_event_bytes(decoded) == wire, vector.label
