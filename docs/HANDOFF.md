# Latest session — approved root-hold resumption

2026-09-28. The user approved replacing identity confirmation with one strict
normalized DOS final-path query on the original held handle. Delete the second
open and FILE_ID_INFO comparison. Make one-swap and two-swap cases passing
regressions, retain cheap case/unavailable fallback witnesses, and expose
internal fallback reasons through executor diagnostics and the rig in the
consumer step. No Setup spelling canonicalization is authorized.

Work resumes on `milestone1-adelbert` from
`3c8b4b413d4ce509f4a639f21f03b7302cb1b970`. Task-owned changes from recovery
`cfcc6efd495b36cfcf47e9dc700f69ec598b4ce8` were restored as uncommitted files;
the WIP was not merged or cherry-picked. Keep
`codex/wip-20260928-1158-root-hold-binding` until all saved work is accounted
for. The shared core outcome is verified for atomic integration; consumer
migration remains the next outcome.

## Current work and verification

M1_PLAN owns the accepted scope, atomic core outcome and gate. The core builder
owns `root_authority.py`, its focused tests and narrow contract documentation.
Executor, preflight and verifier consumers remain unchanged. Independent review
approved the frozen correction. The gate passed: 134 focused seam cases, 5,430
ordinary tests (four skips, 34 headed deselections), 12 import contracts and the
unchanged settlement oracle, 30 scenarios x three. Input/output source, test,
oracle and driver hashes match in `resume/bound-gate-*.json`.
No oracle re-pin has been used.

New receipts belong in `build/root-admission-optimization-20260928/resume/`.
Prior `core/` receipts, including the rejected identity candidate's 5,425-pass
ordinary run and native two-swap reproducer, remain historical evidence only.
They do not accept the corrected implementation. The recovery evidence manifest
records the preserved earlier population.

The replacement K: reports exFAT, serial `BA1F1F45`, label `New Volume` through
the native volume adapter. Both native lifetime cases passed there using the
new owned scratch path recorded in `resume/exfat-invocation.txt`; they require
confirmed holds. The earlier write-protection failure was a different volume.
A non-admin subst fixture failed full volume admission with native error 144,
before confirmation; exact owned mapping cleanup was verified. Strict alias
comparison is covered without claiming a native held transition.

## Consumer continuation

The evidence-only differential lane established zero repeat differences across
32 baseline groups, final driver SHA-256
`7e69cce69537a28096bd15be6f67876fbdda6cec73658c2d949c6d2a50c1f2fa`.
Receipts are `differential/runs/baseline-fixed-input-*`. Only named unfinished
temp clocks and generated trash-session directory mtime are excluded; managed
timestamps and all must-match outcomes, recorder commands, trees and artifacts
remain exact. No candidate comparison is accepted yet. Its baseline checkout is
`C:\Users\Spectrum\.codex\worktrees\root-admission-baseline\NamiSync` at
`b8baf42df91e9aeed1402cd029c86ca9ae287b1b`.
Keep that managed worktree until differential closeout.

After the core gate and atomic commit, migrate executor with invocation-owned
holds and fallback diagnostics. Preserve custom filesystem dispatch and lazy
admission/error precedence. Retain descendant physical containment and second
directory observations initially: removing them changed concurrent refusal
observations in read-only probes. Preflight/verifier follow with their own
finite gates. The existing F: 1,000 x 4 KiB corpus remains; throughput samples
need fresh owned G: targets and manifest-validated cleanup.

Pre-existing same-volume pre-invocation replacement and identity-less
DELETE/TRASH findings remain excluded. No remote, unrelated recovery, stash or
user work was changed.
