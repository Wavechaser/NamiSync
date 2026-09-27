# Latest session — root admission plan review and sequencing

2026-09-27, `milestone1-adelbert`, inspected source `6a93b038`.
The user requested revisions to the uncommitted plan and a commit. This delivery
contains documentation only; optimization implementation remains unauthorized.
M1_PLAN is the sole scope/decision/register owner; all six rows remain pending.

The revised order is RO-1a (current-contract core primitives), RO-2/3/4
(independent mechanical preflight/executor/verifier changes), measured intermediate
revision, RO-1b (atomic continuity adoption across core and all three consumers),
then RO-5 integration. Mechanical rows depend only on RO-1a, not continuity
bootstrap or AGENTS/DEFENSE ancestry changes. Default completion remains before
M1-9 and mandatory before M1-10; changing the former needs a user scheduling decision.

Review changes now explicit in the plan:

- Single-lstat descendant/existence work and parent st_dev reuse remove redundant
  probes. Candidate and root realpath containment stays, with same-step reuse only.
- Existing reviewed stable_file_identity plus local/non-UNC/non-anchor root
  evidence selects continuity eligibility. No competing runtime detector or new
  durable capability bit. Standalone integrity passes the admitted refresh's
  scan.profile through its currently profile-free verifier context.
- Witnessed full-width lstat identity/attributes/tag may implement per-access
  root probes as well as bootstrap. Query/mismatch errors do not downgrade.
- Verifier gets logical sector geometry from FILE_STORAGE_INFO on its opened
  handle; RO-4 requires alignment/equivalence and unsupported-query witnesses.
  RO-1b adds full64 opened-file versus bound-root volume comparison without
  changing stored low32 identities.
- The retained root handle prevents file-ID recycling but can keep the volume
  busy through long reads and retry waits. Pause/exit releases it after settlement;
  device-in-use guidance belongs with RO-1b. No lock/eject/dismount experiment
  against the user's F:/G: volumes is authorized.
- Baseline, mechanical intermediate and final candidate run in isolated pinned
  checkouts with their own matched Python/dependency environments and explicit
  driver provenance. Preserve the intermediate before continuity implementation.

Continuity retains full initial admission and fresh pathname identity probes,
permits same-object ancestor rerouting within the invocation, and keeps descendant
and final effect guards. Retry retains the baseline; resume fully admits anew
and still reconciles temp/published identities. No live root state is stored on
shared runtime filesystem adapters or in continuation/database/wire values.

Evidence: investigation commit `6a93b038`, PERFORMANCE, and ignored
`build/executor-assessment-20260927/` retain historical benchmark/test receipts.
Planning/review scripts, checks and source-review notes are under
`build/root-admission-plan-20260927/`. Only document checks and read-only source/API
research ran in this revision; no production tests, new benchmarks or disk fixtures.
Original source corpus and prior failed receipts remain unchanged.

Next action after user review is separate implementation authorization, fresh
branch/source/baseline verification and RO-1a. Exact future commands, native gates,
stop rules and benchmark topology are in M1_PLAN. Preserve frozen settlement
baselines, DOC-2, prior incident/AB evidence, stashes and unrelated work. This
documentation commit does not activate implementation, M1-9 or M1-10. No push or
merge was requested or performed.
