# NamiSync Session Handoff

Date: 2026-07-21

## Session Outcome

Filename-form differences are now review advisories rather than execution
blockers. A case-only source/target pair still plans its normal metadata update
or no-op, so changed source content is no longer suppressed. A unique
same-parent file pair whose basenames differ only by NFC/NFD representation is
handled the same way under a distinct advisory without normalizing either name.

Target spelling remains unchanged by default. A fingerprinted
`SyncOptions.propagate_source_casing` seam can opt into source-basename casing
through the existing atomic replacement path, but no config, CLI, or GUI control
exposes it yet. Parent-directory recasing remains out of scope.

## Changes

- Planner emits `case_mismatch` and `unicode_normalization_mismatch` as typed,
  non-blocking operation reasons while preserving ordinary update/no-op kinds,
  target before-state, and content-byte accounting.
- NFC/NFD pairing is conservative: exact parent, canonical-equivalent basename,
  exactly one unmatched candidate on each side, and no reassignment of a target
  already claimed by an exact Windows-key match.
- Default plans use the observed target spelling. Opt-in basename recasing is
  included in the policy fingerprint and plan-request payload; old payloads
  decode it as false.
- The legacy `BlockedReason.CASE_MISMATCH` enum remains decodable for prior plan
  payload compatibility, but new plans do not emit it.
- Native Windows coverage proves atomic replacement can recase an ordinary NTFS
  directory entry. Planner coverage proves changed content continues, default
  spelling stability, opt-in behavior, parent-directory non-propagation, and
  NFC/NFD ambiguity handling. A real reviewed-sync regression proves a changed
  differently cased source updates the target while retaining target spelling.
- Updated scanner, planner, preflight, executor, core, workflow, feature,
  architecture, bug-log, README, and handoff documentation.

## Verification

- Focused regression/planner/payload/executor suite: 90 passed in 1.36s.
- Full suite: 298 passed in 7.90s.
- Import-linter: 7 contracts kept, 0 broken (41 files, 137 dependencies).
- `git diff --check`: clean apart from expected LF-to-CRLF notices.
- Native recasing test ran on Windows as part of both focused and full suites.

## Immediate Next Context

- `propagate_source_casing` is intentionally a latent policy with a false
  default. A future settings/UI task may expose it without changing plan or
  payload shape; review and commitment already bind the value.
- Recasing is basename-only. A directory case difference is non-blocking and
  retains the target directory's observed spelling.
- NFC/NFD advisories do not establish generalized Unicode homograph safety.
  They flag only unique canonical-equivalence pairs and never normalize names;
  ambiguous or non-canonically-equivalent lookalikes remain distinct entries.
