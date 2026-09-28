# Latest session — verifier invocation holds

2026-09-28, `milestone1-adelbert`. Preflight is integrated as `4263b12`, after
core/executor attribute correction `8cdd669`, executor `90b57646` and core
`6536c04`. The verifier hold outcome is verified and independently approved for
its atomic commit. No geometry implementation has started.

## Changes and evidence

One invocation record binds exact authority, native/dispatched reader and live
scope. Engine receives it explicitly; the rig tap forwards activation. Admission
stays lazy, both engine/native reuse query current held attributes, and every
exit invalidates before release. Fallback, custom dispatch, descendant/final-path
checks, four file snapshots, opened-volume identity, alignment and recording stay.

Evidence root: `build/root-admission-optimization-20260928/`.

- `verifier/holds-frozen-inputs.json`: eight product/test/component-doc hashes;
  native `119BA0C0`, engine `0A5A5002`, tap `41670E93`. Focused 132 pass; direct
  consumers 479 pass/two skip. Old tests remain; failed helper/fixture receipts
  are retained. Native empty-root conversion is refused at both reuse owners.
- `resume/verifier-held-*`: 5,502 ordinary passes, four skips, 34 headed
  deselections; 12 imports, unchanged oracle 30 × three and guard scan 70 rows/
  391 effects/zero missing admissions. Gate input/output hashes match.
- `differential/runs/candidate-verifier-held-frozen-065ab42763334875a86e21b569d2b2c7`:
  67 groups, zero unexpected differences. Three verifier swaps blocked with 32
  match complete unswapped controls. Actual case fallback swaps between items
  and matches baseline. Native/tap all-mode and custom remount/identity-weak/
  undurable controls pass, as do the old 46 groups. Producer `e7ba9b8d` has two
  matching baseline captures, old-projection parity and 24 qualification checks.
  All eight frozen hashes match after capture.
- `verifier/{baseline,candidate}-verify-timing.json`: three serialized samples
  each, median 3.885→1.998 seconds on the preserved F: 1,000 × 4 KiB corpus.
  Same driver, real untimed prime, native tap, all verified/applied, complete
  read bytes and matching source/product observations. Separate `*-verify-counts`
  reduce anchor/volume calls 4,000/1,000→1,001/1, add 1,999 current root queries
  and preserve 12,000 file-information queries. PERFORMANCE owns limits.
- Independent whole-outcome review approves source, tests, gates, measurements
  and documentation: `verifier/independent-review-holds-20260928.md`.

## Immediate continuation

Commit the approved hold outcome. Then activate geometry from
`verifier/next-geometry-refresh.md` against that integrated predecessor. Its
finite population is native.py, native/engine verifier tests and VERIFIER docs;
preserve old pathname capability fallback, dual-failure precedence and all close
paths. Existing NTFS/exFAT FileStorageInfo16 receipts show positive 512-byte
logical sectors matching old queries; no new API probe is needed. These receipts
do not establish exFAT verifier support. Return to executor work afterward.

Preflight's approval is `preflight/independent-review-guarded-preflight-20260928.md`:
5,480 ordinary passes and 46 differential groups; median observation 2.722→0.551
seconds versus `b8baf42d`, including earlier core changes. K: observation-only
runs pass independently of the deferred executor compatibility issue.

## Preservation and exclusions

The corrected executor median remains 15.271 seconds / 0.256 MiB/s, below the
1 MiB/s goal. Earlier unchecked-hold timing is historical. Held attributes
preserve sharing/root flushes; DEFENSE quiescence covers check/use. Retiring
descendant checks still requires a concrete decision. Stored identity, wire,
settlement and supported-filesystem policy have not changed.

Retain recovery refs `7eb8c19d`, `cfcc6ef` and `0a04921` until final accounting;
never merge/cherry-pick WIPs as-is. Preserve ignored receipts/fixtures, the F:
corpus and managed baseline worktree
`C:\Users\Spectrum\.codex\worktrees\root-admission-baseline\NamiSync` at
`b8baf42df91e9aeed1402cd029c86ca9ae287b1b`. No remote, unrelated stash/branch or
user work changed. The separate exFAT FileIdInfo issue remains deferred in BUGS.
