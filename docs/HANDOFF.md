# NamiSync Handoff

## Changes

- Resolved all `DESIGN_REVIEW.md` findings with the user — the 23 original
  items plus DR-24 (directory operations), found during the sanity pass — and
  recorded a dated **Resolution** note under every item; the review file is
  now the decision log.
- Updated the authoritative sources to match, in the prescribed order
  (`FEATURES.md` first, then `ARCHITECTURE.md`). Headline decisions:
  - **Commit-to-execute** (DR-01): a reviewed plan's explicit commitment,
    bound to the plan's deterministic fingerprint, is the durable
    preauthorization; committed plans queue and run sequentially;
    `run_unattended_sync` removed; no plan-and-execute-without-review path
    exists anywhere.
  - **Session runner** (DR-02/03): new `core/session.py` runner owns
    exactly-one-`Terminal` and pause/cancel resolution; `Checkpoint` never
    blocks — it raises `PauseRequested`/`Canceled`; a paused execution is
    exactly a queued `ExecutionSet`, resumed via the queue-wakeup path.
  - **Planner inputs** (DR-04/05): `plan()` gains an immutable
    `MappingSnapshot` correspondence input; `target_free_space` removed from
    `Plan` (free space is `observe()`'s job).
  - **Displace-then-replace updates** (DR-08): hardlink-to-trash then atomic
    `os.replace`; no crash point leaves the live target absent.
  - **History = audit with guaranteed delivery** (DR-09/16): bounded producer
    backpressure for the history observer, `Gap`-event ejection for other
    reliable subscribers, bounded replay buffer.
  - **Two-axis truth** (DR-15): terminal `SessionState` reports filesystem
    work; a separate `RecordingStatus` reports ledger bookkeeping.
  - **M0 scope additions** (DR-13): real cross-process volume locks before the
    executor's first mutation.
  - Type-level fixes: `VolumeId` reduced to stable key material (DR-10),
    `UnsupportedRecord` collection on `ScanResult` (DR-11), typed
    `Subject`-keyed `ObservedWorld.stats` (DR-21), `ContentEvidence` +
    post-publish subject stat in `Attestation` (DR-07), `MetadataSnapshot` +
    `PreservationPolicy` (DR-22), `current_filters` in `ObservedWorld`
    (DR-06), typed `IntegrityOutcome` event body (DR-14), annotation key
    namespace in the schema freeze (DR-18, partial pull-forward).
  - Doc corrections: CLI sync-command contract and no-subcommand behavior
    (DR-19), latent-protocol rule and fixed §7 reference (DR-20), core-owns-
    contracts wording (DR-23), best-effort directory-flush honesty (DR-12),
    session-record retention (DR-17).

- A sanity-check pass over the updated authoritative docs then caught and
  fixed: a commitment-check-in-preflight contradiction (commitment checking
  lives only at the execution session's entry — preflight also runs at review
  time, pre-commitment); `Commitment` now binds the reviewed selection
  (`selection_digest`) alongside the plan fingerprint; `observe()` gains an
  injected `SettingsReader`; readonly targets are cleared before `os.replace`
  (Windows refuses to rename over readonly); the interrupted-update `nlink=2`
  trash-link interaction is documented as benign; volume matching wording
  corrected (in-place conversion preserves the serial, a true reformat
  regenerates it); `Gap`/`REFUSED` comments clarified.
- Follow-up decisions: **Resume Never Preempts** (a resumed session re-enters
  at the back of its volumes' queue); history backpressure buffer sized to
  absorb inter-checkpoint emissions; **DR-24** directory operations —
  decompose + grouped review, `DirRecord` defined (metadata + optional
  identity), directory metadata applied after children settle.

The 17 per-module drafts have **not** yet been re-synced to these decisions.

## Verification

- `git diff --check`: no whitespace errors.
- `.\.venv\Scripts\python.exe -m pytest`: 1 passed.
- `.\.venv\Scripts\lint-imports.exe`: contracts kept, 0 broken.

## Immediate Next Context

- Propagate the recorded resolutions from `DESIGN_REVIEW.md` into the affected
  module drafts (`CORE`, `PLANNER`, `PREFLIGHT`, `EXECUTOR`, `DISPATCHER`,
  `RECORDER`, `HISTORY`, `WORKFLOWS`, `COMMANDLINE` are the most affected) so
  authoritative and focused docs agree again.
- Then freeze M0 core types and begin the walking skeleton.
- No files were staged or committed.
