# Bug Log

Substantive defects with real behavioral consequences. Cosmetic and style-only
issues are excluded.

Each entry records `SEVERITY - STATUS (YYYY-MM-DD)`, then a failure-specific
category, the observed behavior and consequence, `Cause: why`, and, when fixed,
the corrective change. The behavior and fix are written in natural prose rather
than as separate labels.

- **Severity:** SEVERE (data loss, hangs, crashes, or a core feature dead) ·
  MODERATE (disruptive but bounded, or actively misleading) · MINOR (cosmetic
  or no functional harm).
- **Status** reflects the last direct verification of the entry.
- **Category** names the failure boundary, not a broad outcome such as
  availability or convergence.

Entries are module/function-first, not a project-wide timeline: `##` headings
are owning modules or feature boundaries, and `###` headings are their
functional scope or delivery phase. Add an entry under the module/function that
owns the behavior, retain its relevant subheading, and keep entries newest first
within that section. Do not add date-based sections or append unrelated entries
to a global chronological list.

---

## EXECUTOR

### M1 executor refactor

- MODERATE - FIXED (2026-07-25). Post-publish metadata repair. On volumes with
  last-access updates enabled, observing a renamed file could change its access
  time and force the otherwise conditional second metadata rewrite and flush on
  every copy. Cause: executor normalized and compared access time as managed
  metadata; fixed by removing access time from executor policy while retaining
  mtime, creation-time, and standard-attribute repair.

### M0 hardening

- MODERATE - FIXED (2026-07-20). Orphaned temporary-file recovery. Temps left
  by killed or crashed runs accumulated permanently while preflight counted
  their bytes as reclaimable, leaking target capacity and potentially stranding
  a nearly-full sync. Cause: executor removed only the current run's exact
  per-operation temp, while every rerun has a new run id and scanner correctly
  ignores owned temps; fixed with one post-preflight, pre-copy exact-grammar
  sweep over preflight's touched target parents, excluding current-run files and
  `.synctrash`.
- MODERATE - FIXED (2026-07-20). Metadata state validation. Cleanup of a
  directory emptied by same-run moves or trash operations was rejected as target
  drift, preventing folder rename/removal in one run. Cause: the final guard
  compared scan-time mtime and link count that planned child removal changes;
  fixed with a cleanup matcher that validates stable metadata and treats absent
  reviewed identity as absent evidence before atomic empty-directory removal.
- MODERATE - FIXED (2026-07-20). Platform API permission. Every Windows
  parent-directory flush failed and warned despite successful mutations. Cause:
  `CreateFileW` requested `GENERIC_READ`, while `FlushFileBuffers` requires
  write access; fixed by requesting `GENERIC_WRITE` on the existing directory
  handle.
- MODERATE - FIXED (2026-07-19). Idempotency failure. A transient sharing
  violation after update backup or publish restarted against the operation's own
  mutation, causing false target drift or destination occupancy. Cause: generic
  retry assumed every operation could restart; fixed by validated continuation
  from the last durable sub-step.

## WORKFLOW AND CLI

### M1 Stage 5.5 adversarial closure

- SEVERE - FIXED (2026-07-30). Resumed-run ledger settlement. A coherently
  tampered execute/verify continuation was correctly refused before domain work,
  but the refusal tried to reopen recording from the tampered selection. The
  recorder raised a run-token input conflict and left the original ledger run
  unfinished. Cause: resume-failure settlement reused the fresh/open recording
  path even though an earlier continuation had already established the run;
  fixed with a custody-bound finish-existing-run dependency, strict
  same-runtime start-token validation, and real dispatcher plus real-ledger
  pause/resume regressions.
- SEVERE - FIXED (2026-07-30). Replan intent ABA. Replacing a plan reset its
  selection revision to zero and discarded mutation receipts, so a lost
  checkbox response, Execute, or destructive confirmation formed against the
  old artifact could apply to a new artifact with identical deterministic
  operation ids. A mutation racing replacement could also report that stale
  state as applied. Cause: artifact identity changed but its concurrency epoch
  did not survive replacement; fixed by monotonically advancing revisions,
  retaining recognized gesture tombstones, checking the current artifact after
  mutation, and returning the new preview as a conflict.
- SEVERE - FIXED (2026-07-30). Irreversible-update CLI admission. With
  trash-on-update disabled, typing `execute` returned a
  `confirmation-required` view that the CLI treated as an execution session,
  then crashed with `AttributeError` without updating the target. Cause: the
  facade added a two-step risk handshake without adapting the existing typed
  CLI confirmation; fixed by rendering the exact irreversible-update warning,
  forwarding the typed response as an exact boolean acknowledgement, and
  handling every named admission view defensively.
- MODERATE - FIXED (2026-07-30). Concurrent retry admission. Two simultaneous
  first deliveries with one plan/inventory/integrity command id could both pass
  receipt lookup and submit separate sessions; ID-based retries also reread
  mutable inventory before finding their receipt. Cause: lookup and receipt
  publication were separately locked around an unguarded admission; fixed with
  bounded command-id single-flight guards, raw canonical ID-gesture signatures,
  and shutdown-safe receipt publication.
- MODERATE - FIXED (2026-07-30). Mixed folder selection. A single
  safety-disabled operation beneath a folder made the entire folder toggle
  raise, leaving otherwise selectable siblings inert. Cause: node expansion
  passed every descendant into the direct-operation safety validator; fixed by
  expanding folder gestures to toggleable descendants while retaining refusal
  for a disabled operation named directly.
- MODERATE - FIXED (2026-07-30). Inventory workflow version strictness.
  Inventory `2.9` and integrity `"1"` payload versions were accepted as current
  schemas. Cause: the shared decoder coerced version values with `int()`; fixed
  by requiring an exact JSON integer and the exact kind-specific version,
  including float, string, and boolean rejection coverage.

### M1 post-execution integration

- SEVERE - FIXED (2026-07-25). Compound ledger-run settlement. Exceptions
  during execute-result projection, continuation publication, verify phase
  entry/context creation, or verifier-result aggregation could escape after the
  recorder opened, leaving the logical ledger run unfinished; a resumed
  execute preflight refusal could also be mislabeled as fresh
  `REFUSED+UNRUN`. Cause: only the executor/verifier call itself was guarded and
  runtime discarded whether `started_at` came from a resumed payload; fixed
  with an explicit resumed bit, phase-aware exception results, and one guarded
  finish-once path for every post-entry terminal.
- MODERATE - FIXED (2026-07-25). Retained compound history projection. Reading
  a retained phase passed its `HistoryPhaseSnapshot` wrapper to the phase view
  and raised `AttributeError`; even without phases, the view omitted persisted
  cancellation and derived integrity/headline truth. Cause: the runtime
  projected repository wrappers as domain values and exposed an incomplete run
  view; fixed by unwrapping ordered snapshots, reconstructing the typed result,
  and routing retained classification through the same live result classifier.
- MODERATE - FIXED (2026-07-25). Canceled-settlement adapter failure. A malformed
  registration callback could be converted into a clean canceled terminal.
  Cause: dispatcher checked the already-requested cancel checkpoint before
  raising the captured adapter failure; fixed by giving the detected failure
  precedence and pinning PAUSING-drain/callback-failure races.

### M0 integration

- MODERATE - FIXED (2026-07-21). Rename plan presentation. Recase rows rendered
  the source and destination as the same spelling, and move/move-update rows
  likewise omitted the old target path, so review hid the filesystem rename a
  user was approving. Cause: `PlanOperationView` discarded
  `prior_target_rel_path` and the CLI always used the source path as the
  displayed origin; fixed by retaining `prior_target_path` in the workflow read
  model and preferring it as the left side for rename-shaped operations.
- MODERATE - FIXED (2026-07-21). Fingerprinted option decoding. A plan-request
  payload that omitted `propagate_source_casing` decoded as false and then
  re-encoded with the field present, so one accepted payload did not have a
  byte-stable semantic round trip for an input to `policy_fingerprint`. Cause:
  the newly added flag alone used `.get(..., False)` while every neighboring
  semantic option was required; fixed by requiring the field during decode and
  retaining explicit round-trip coverage.
- SEVERE - FIXED (2026-07-20). Safe partial execution. One blocked item or an
  incomplete scan refused the whole sync, while simply omitting blockers could
  expose target-only deletion from incomplete source evidence. Cause: workflow
  selected every operation and preflight gated the whole run; fixed with
  commitment-bound safe-subset selection, dependency quarantine, additive-only
  incomplete-scan fallback, and preflight enforcement.
- MODERATE - FIXED (2026-07-20). Execution outcome reporting. Blocked plan
  items were absent from results and history because only selected operations
  emitted outcomes. Cause: the outcome model had no blocker state and workflow
  emitted no exclusions; fixed with `BLOCKED`, reasoned `DEFERRED` exclusions,
  itemized history rows, and a version-2 blocked summary count.
- SEVERE - FIXED (2026-07-19). Result presentation crash. Every real execution
  crashed while presenting fresh-preflight results, before mutation began.
  Cause: local `refusal_views` shadowed the formatter; fixed by using a distinct
  result variable.
- MODERATE - FIXED (2026-07-19). Plan integrity validation. A decoded plan's
  carried fingerprint was compared with its commitment without recomputing the
  content hash, allowing altered payloads to appear authorized. Cause: two
  transported fields were treated as independently derived; fixed by recomputing
  the fingerprint before commitment validation.
- MODERATE - FIXED (2026-07-19). Configuration preflight validation. Identical
  database paths or overrides inside a managed root were rejected only after
  planning and confirmation. Cause: location validation lived only on the
  execution adapter; fixed by applying it before plan admission.

## SCANNER AND PREFLIGHT

### M1 Stage 5.5 recursive scope

- SEVERE - FIXED (2026-07-30). Multi-root scope admission cost. Normalizing
  sibling recursive roots compared every root with every retained root and then
  every exact path with every root; 1,000 sibling roots took about 17 seconds
  and 2,000 took about 69 seconds before dispatcher admission. Cause: repeated
  normalization inside quadratic ancestry scans; fixed with canonical-key
  ancestor-set walks whose normalization count scales with declared path depth,
  plus a deterministic complexity regression and a multi-root global
  incompleteness composition test.

### M0 integration

- MINOR - FIXED (2026-07-21). Defensive JSON encoding consistency. Path
  validation prevented unpaired surrogates from reaching ledger/history
  records, but ledger idempotency hashing, history hashing/detail storage, and
  opaque workflow payload encoding would still raise if a malformed code unit
  arrived through free-form detail or a future relaxed boundary. Cause: only
  canonical plan JSON used the defensive final UTF-8 encoding rule; fixed by
  applying the same valid-Unicode-compatible backslash escaping at all three
  module boundaries and round-tripping hostile history detail in tests.
- SEVERE - FIXED (2026-07-20). Unsafe filename isolation. One NTFS, SMB,
  archive, or WSL-originated name outside NamiSync's relative-path contract
  could abort planning; an unpaired surrogate could later crash ID or fingerprint
  encoding. Cause: the walker normalized untrusted names too early, validation
  admitted surrogates, and canonical JSON required UTF-8; fixed with pre-use
  validation, typed escaped evidence, incomplete-scan isolation, surrogate
  rejection, and compatible serializer hardening.
- SEVERE - FIXED (2026-07-19). File identity acquisition. Windows scan evidence
  could omit an NTFS file identity while fresh observation supplied one, falsely
  refusing sync and disabling correspondence moves. Cause: extended-path
  `DirEntry.stat()` could report inode zero; fixed with an exact-path fallback
  on stable-ID volumes and absent-identity-as-absent-evidence matching.

## PLANNER

### M0 hardening

- MODERATE - FIXED (2026-07-21). Opt-in casing propagation cost. A
  metadata-equal case-only filename change was represented as `update`, causing
  a full source-content rewrite, capacity charge, and trash backup merely to
  change directory-entry spelling. Cause: the first propagation seam reused the
  only operation that could publish a requested spelling; fixed with an
  explicit zero-byte `recase` operation that carries old/new spellings, uses a
  same-volume non-replacing rename, preserves identity/metadata, records updated
  correspondence, and creates no trash entry.
- MODERATE - FIXED (2026-07-21). Filename-form advisory execution. A
  case-only source/target filename pair blocked even when source metadata had
  changed, suppressing the required update; canonically equivalent NFC/NFD
  spellings were instead misclassified as unrelated copy/removal work with no
  warning. Cause: the initial casing fix made spelling visibility a conflict
  gate, and planning compared only Windows case keys without a conservative
  canonical-equivalence advisory pass; fixed by retaining normal update/no-op
  semantics under typed non-blocking reasons, preserving target spelling by
  default, adding a fingerprinted source-basename recasing option (available
  through the semantic-settings facade, with no dedicated CLI/UI control), and
  pairing only unique same-parent NFC-equivalent files that are not already
  exact matches.
- MODERATE - FIXED (2026-07-20). Case-sensitive name reconciliation. A pair
  such as `KEEP.txt` and `keep.txt` was reported as a metadata no-op forever,
  hiding unconverged target casing. Cause: Windows-key grouping discarded target
  spelling before no-op classification; initially made visible with a typed
  `case_mismatch` blocker. The 2026-07-21 follow-up above retains that typed
  visibility without suppressing content work.
- MODERATE - FIXED (2026-07-19). File attribute reconciliation. A readonly,
  hidden, or system attribute change with unchanged size and mtime planned as
  `noop`, leaving the target stale. Cause: equality checked only size and
  timestamp; fixed by including standard attributes and verifying native
  readonly propagation through the CLI workflow.
