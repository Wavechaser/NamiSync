# Session Handoff

Status (2026-08-19): the cosmetic-state bridge thaw is complete and refrozen.
`ui-state.json` now has a strict interface-owned lifecycle, the bridge exposes
its fixed two-row section channel, and the header's persisted System/Light/Dark
choice drives both native window appearance and page tokens. The file-list
surface remains intentionally unbuilt; its eventual treegrid state must extend
the typed document without changing the bridge rows.

## Delivered

- Ratified the cosmetic boundary before implementation. `ui-state.json` is
  separate from semantic `settings.json`, plan fingerprints, service state,
  tasks, sessions, selections, and projection revisions. Schema v1 accepts only
  the versioned `appearance` section.
- Added a bounded typed owner with strict duplicate/shape/size checks,
  pathological-depth rejection, forward-version and unreadable-artifact
  preservation, process-local section revisions, one private whole-document
  generation, 250 ms coalescing, atomic replacement, one-attempt failure
  custody, and guarded close behavior.
- Added `read_cosmetic_section` and `replace_cosmetic_section` as the eighth and
  ninth production bridge commands. Their exact five-second policy, read-only
  uncertainty replay, mutating no-replay rule, guarded read reconciliation,
  origin/phase admission, and hostile-input bounds are frozen in
  `M1_BRIDGE.md`.
- Constructed one cosmetic owner in the desktop host, injected it only into the
  interface command and appearance paths, and closed it after handler
  quiescence and appearance teardown but before logging, path, and mutex
  release. It does not enter `NamiSyncService` or readiness.
- Added the labelled System/Light/Dark selector. It waits for `OPEN`, never
  renders an optimistic choice, serializes replacements, accepts conflict
  authority, reconciles uncertain delivery by guarded read, and suppresses
  stale generations. A same live realm waits prior mutation settlement; a new
  realm converges a late mutation through healthy validated appearance
  publication and a fresh authoritative read.
- Applied the stored choice to the precreate opaque background, native
  material/title-bar policy, and page tokens. Active high contrast continues to
  follow Windows without overwriting the stored choice; accent and reduced
  motion remain system-owned.
- Seeded the real cosmetic owner before component-gallery window creation:
  light/reduced profiles use Light and dark/forced profiles use Dark. The
  installed witness operates the production selector, proves accepted-only
  reconciliation, restores the seed, and checks native/page agreement. The
  editable launcher may reuse an already persisted same-mode seed without
  weakening fresh clean-wheel evidence.
- Corrected one pre-existing dispatcher test synchronization race as its own
  checkpoint. The inventory test now waits for live `PAUSED` publication before
  reading audit history, matching the documented publication barrier without
  changing production ordering.

## Checkpoints

- `9c2fa56 docs(bridge): ratify cosmetic channel thaw`
- `2de4593 feat(interfaces): own cosmetic state lifecycle`
- `3090dfc feat(bridge): expose cosmetic state channel`
- `4e4fd2e test(dispatcher): wait for paused audit publication`
- `5496db2 feat(web): persist effective theme override`

## Adversarial Review

- Independent contract review rejected a speculative synchronous rewrite and
  retained the ratified coalesced writer while separating unsupported-forward,
  unreadable, malformed, and missing-state custody. Older binaries never erase
  state they cannot understand.
- Persistence review exercised concurrent replacement, stale generations,
  failed atomic replacement, encoded-size refusal, subscriber isolation,
  in-flight write plus close, exact-once close flush, and sanitized diagnostics.
- Bridge review checked every exact command-list consumer, retry asymmetry,
  pre-`OPEN` refusal, browser readiness, real authority round trips, host
  quiescence, and shutdown retention on incomplete service settlement.
- Native review found and fixed an attachment rollback leak when both event
  attachment and handler removal failed. Generation gates now prevent reversed
  cosmetic callbacks, callbacks after close, and a superseded native snapshot
  from becoming the published presentation.
- UI review found and fixed a replacement crossing a live bridge-generation
  reset, the missing installed selector witness, stale gallery relaunch
  assumptions, and the old shell expectation that the tree was the first Tab
  stop. The gate now proves the selector first and the tree second without
  weakening tree keyboard or virtualization evidence.
- The final staged audit found no blocker and confirmed that every changed file
  traced to the cosmetic consumer, native/page integration, owning docs, or a
  directly affected witness.

## Verification

- Ordinary repository suite: `2627 passed, 16 skipped, 28 deselected` in
  `123.41s`.
- Affected installed-wheel headed neighborhood: `28 passed, 58 deselected` in
  `104.36s`, covering the four-mode component gallery, materials, native host,
  shell, Slice 1, and transport gates.
- Focused cosmetic/theme neighborhood: `412 passed, 8 skipped, 11 deselected`;
  the later shell-focus adjustment separately passed `40` non-headed/static
  checks and its installed headed gate.
- Bundled Node probes for selector concurrency/reconciliation, startup
  readiness independence, and appearance publication all passed.
- Import boundary lint: `11 kept, 0 broken` across 71 files and 256
  dependencies.
- `git diff --check` was clean apart from the repository's expected LF-to-CRLF
  notices.

## Remaining Work

- Slices 5–7 remain the next product boundary. They may add registered cosmetic
  sections and advance the on-disk schema, but they must not change the two
  refrozen bridge rows or route semantic/session state through them.
- The file-list surface remains pending. Its existing treegrid foundation is
  the intended UI primitive; expansion/grouping, column, sort, and filter state
  need consumer-owned typed keys when that slice is designed. No such keys were
  guessed here.
- A full-document late mutation converges through healthy appearance
  publication. If native observation/publication is degraded, a stored change
  can persist without visually landing until a later authoritative read or
  conflict; there is not yet a selector capability signal.
- Save failure remains a sanitized log event with `dirty` retained for a later
  settings surface. It does not replace the operational status or block bridge
  readiness.
- Precreate background and the first authoritative appearance envelope share
  the override, and settled native/page presentation agrees. There is no
  compositor sentinel and no claim of flash-free first visible paint.
