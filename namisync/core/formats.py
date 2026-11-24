"""Version constants for the shared formats that databases persist.

A database stores bytes and text produced by core encoders. Each such shared
format has one version constant here and literal known-answer vectors in
``tests/core/test_format_vectors.py``. An encoding that changes without a new
constant fails its vector; a constant without vectors fails the coverage check.
A persistence layer records ``FORMAT_VERSIONS`` under the ``format.<name>``
metadata rows it declares for each schema version.

Changing a format means a new constant value, new vectors for that version, and
a database migration or an invalidating step in the same change. Vectors for a
superseded version stay in the test table as a record and are not executed.
The vectors pin persisted vocabularies exactly, so adding a member to a
persisted enum fails a test and is decided as a format change.

Scope and owning symbols, one entry per format:

``event`` (the canonical event envelope)
    The exact bytes ``canonical_event_bytes`` and
    ``validate_and_encode_event_v5_envelope`` produce for reliable events: key
    order, separators, raw UTF-8, escapes, decimal-text scalars, the envelope's
    own ``at`` timestamp form, every enum value stored as text in a body, the
    detail-key vocabulary and its leaf bounds (a stored event must stay
    decodable, so removing a key or lowering a bound is a format change), and
    the reliable-event byte ceiling. Owners: ``events.py``
    (``envelope_to_dict``, ``result_item_to_dict``, ``terminal_summary_to_dict``)
    and ``event_v5.py``. The value is the event schema version, so it derives
    from ``EVENT_V5_SCHEMA_VERSION`` and cannot drift from
    ``CORE_EVENT_SCHEMA_VERSION``. The recording fields inside event items
    belong to ``recording``.

``evidence`` (content evidence as persisted)
    The digest algorithm name ``xxh3_128``, the raw 16-byte digest, the
    ``Provenance`` text values, the attested stat leaves that accompany a digest
    (``file_stat_fact``, with sizes and ``mtime_ns`` as raw integers in the
    signed-64 domain), and the ledger inventory evidence vocabulary stored as
    text (``EntryKind``, ``InventoryState``, ``VerificationInvalidationReason``,
    ``UnsupportedReason``). The digest vectors pin the ``xxhash`` XXH3-128
    output and its raw byte order as consumed through
    ``finish_content_hasher``; core has no hasher of its own, and the
    production factory is wired in ``namisync/workflows/runtime.py``. Owners:
    ``evidence.py``, ``models.py`` and ``integrity.py``. Version 2 is the
    released ``m1-ledger-v4-event-v5-evidence-v2`` number. That bump
    (``4b2af386``, data epoch 6) changed the core hash preimages and the db
    recorder's hash projections (now owned by ``preimage`` and ``identity``
    here, and by ``namisync/db``); the digest, provenance and stat encodings it
    names did not change after ``evidence-v1``.

``recording`` (the recording contract)
    The recording-truth vocabulary and facts that history and the ledger run
    persist: ``RecordingStatus``, ``ItemRecordingReason`` and
    ``TaskRecordingIssueReason`` text, the per-item ``recording``,
    ``recording_reason``, ``recording_detail`` and ``detail_omitted_count``
    facts with their 1,024-byte omission rule (``bounded_utf8_text``), the
    terminal ``recording``, ``audit``, ``recording_degraded_items`` and
    ``recording_issues`` facts, and the recorder command vocabulary
    (``InventoryVisibilityAction``, ``ScanWarningCode``, ``ScanScopeKind``;
    the last two enter the recorder's stored payload hashes, not a text
    column). Owners: ``evidence.py``, ``execution.py``, ``events.py``,
    ``models.py``, ``recording.py`` and ``scalars.py``. Version 1 is the
    released ``m1-history-v8-event-v5-recording-v1`` number, introduced with
    event v5 and never bumped.

``preimage`` (the canonical hash preimage)
    ``canonical_json_bytes`` (sorted keys, ``,`` and ``:`` separators, raw
    UTF-8, closed JSON tree) and the explicit core projections that feed plan
    fingerprints, operation ids, policy fingerprints and selection digests:
    ``file_stat_projection``, ``file_identity_projection``,
    ``metadata_projection``, ``root_projection``, ``volume_id_projection``,
    ``volume_evidence_projection``, ``capability_profile_projection`` (all in
    ``models.py``), ``operation_projection``, ``plan_projection``,
    ``assignment_projection``, ``filter_set_projection``,
    ``preservation_policy_projection``, ``deterministic_operation_id``,
    ``policy_fingerprint``, ``plan_fingerprint`` and ``selection_digest`` (in
    ``planning.py``), with the enum text they embed. Projections and hashes that
    the database layer builds itself (the ledger recorder's payload hashes, the
    history receipt hashes, ``timestamps.py``) are owned by ``namisync/db``.

``identity`` (file identity text)
    ``file_index_128_to_text`` and ``file_index_128_from_text`` (canonical
    unsigned decimal ``FileIndex128``, ``0`` to ``2**128 - 1``), the
    little-endian decoding in ``file_index_128_from_bytes``, and the volume
    serial normalization (low 32 bits, eight uppercase hexadecimal digits) in
    ``file_identity_from_windows_parts``. Owners: ``scalars.py`` and
    ``file_identity.py``.

``numeric`` (numeric text)
    ``scalar_64_to_text`` and ``scalar_64_from_text`` (canonical decimal text,
    ``0`` to ``2**63 - 1``) and the ``MAX_SAFE_INTEGER`` (``2**53 - 1``) and
    ``MAX_SIGNED_64`` bounds with ``require_safe_int`` and
    ``require_signed_64``. Owner: ``scalars.py``.

``path-key`` (canonical path keys)
    ``validate_relative_path`` (canonical ``\\`` separators and refusals) and
    ``normalize_relative_path`` / ``fold_validated_path`` (one-codepoint
    uppercase folding, never ``casefold``, expanding mappings left as they
    are, no Unicode normalization). Owner: ``pathing.py``. Named limit: keys
    follow the release interpreter's Unicode case tables, so changing the
    release interpreter (``docs/TOOLS.md`` owns its selection) is a possible
    ``path-key`` format change that the vectors cannot detect.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from namisync.core.event_v5 import EVENT_V5_SCHEMA_VERSION


EVENT_FORMAT_VERSION = EVENT_V5_SCHEMA_VERSION
EVIDENCE_FORMAT_VERSION = 2
RECORDING_FORMAT_VERSION = 1
PREIMAGE_FORMAT_VERSION = 1
IDENTITY_FORMAT_VERSION = 1
NUMERIC_FORMAT_VERSION = 1
PATH_KEY_FORMAT_VERSION = 1

# Metadata name (the suffix of a ``format.<name>`` row) to current version.
FORMAT_VERSIONS: Mapping[str, int] = MappingProxyType(
    {
        "event": EVENT_FORMAT_VERSION,
        "evidence": EVIDENCE_FORMAT_VERSION,
        "recording": RECORDING_FORMAT_VERSION,
        "preimage": PREIMAGE_FORMAT_VERSION,
        "identity": IDENTITY_FORMAT_VERSION,
        "numeric": NUMERIC_FORMAT_VERSION,
        "path-key": PATH_KEY_FORMAT_VERSION,
    }
)
