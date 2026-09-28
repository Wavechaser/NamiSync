# M1 Delivery Register

This is the sole active M1 delivery register. Exact contracts and release criteria
remain with [ARCHITECTURE](ARCHITECTURE.md), [DEFENSE](DEFENSE.md),
[BRIDGE](BRIDGE.md), [PRESENTATION](PRESENTATION.md),
[INTERFACES](INTERFACES.md), [DESKTOP_UI](DESKTOP_UI.md),
[FEATURES](FEATURES.md), [TESTS](TESTS.md) and their component owners.
[M1-8's archived register](obsolete/M1_8_DELIVERY.md) retains its finite
R0–R3 and A1–A6/B1–B6 gates. The [archived post-M1-8 study](obsolete/POST_M1_8_ABLATION.md)
retains investigation, rejected proposals and superseded execution recipes;
the decisions still governing delivery are below. Historical observations
certify their recorded build and dependencies only.

## Root admission optimization — 2026-09-28

**Resumed — held-handle attributes before access.** A native owned-scratch witness
converted a fully admitted, confirmed, held empty directory into a junction
using a separate write handle and `FSCTL_SET_REPARSE_POINT`; no rename was
needed. Resolution then reached the owned sibling outside the logical root.
The script restored the metadata before reporting. No executor mutation or
user-data effect was attempted. The hold's read/write sharing blocks deletion
but does not establish the namespace stability assumed by admission reuse.
This finding affects core `6536c04`, executor `90b57646`, and the uncommitted
preflight candidate. Their prior passing receipts do not close this new seam.
Their acceptance must be renewed after the correction below.

AGENTS requires suspension for changed root-safety mechanisms and recovery
before redesign; this plan also stops on unapproved equivalence differences.
Preflight's ordinary gate was interrupted (no completed broad pass); its
focused/direct/differential passes are retained only as partial evidence.
The user rejected denying write sharing: attribute-only handles may still set
junction metadata, while stronger sharing denial can break executor root flushes.
The approved correction keeps the existing hold and checks current attributes
on its handle before every access that reuses admission, refusing reparse or
placeholder attributes. Confirmation remains one strict final-path query; the
new check does no pathname probing. DEFENSE's existing quiescence rule covers
the check/use interval; this does not promise immunity to concurrent mutation.
Native witnesses must demonstrate attribute visibility after empty-root junction
conversion, nonempty-directory conversion refusal, root-flush compatibility and
ordinary descendant operations. Query failures may never authorize access.

Native selection evidence is under `rootguard/` in the current evidence root:
attribute-only (`FILE_WRITE_ATTRIBUTES`) and generic-write handles both convert
an empty held NTFS root; `FileBasicInfo` on the original handle observes ordinary
attributes becoming reparse attributes. Nonempty root/ancestor conversions fail
with 145, and removing the held child fails with 32. Restoration, root flush and
descendant create/write/rename/delete succeed with unchanged sharing. Confirmed
exFAT K: rejects `FileAttributeTagInfo` with 87 but accepts `FileBasicInfo`; the
implementation therefore uses the latter. These native observations select the
mechanism; product regressions and the full gate still establish acceptance.

The frozen correction passes 541 affected tests, 22 focused guard cases and
two production held-attribute/lifetime cases on K:. The ordinary suite passes
5,462 tests (four skips, 34 headed deselections), all 12 import contracts,
unchanged oracle 30 × three and guard scan 70 rows/391 effects with no missing
admissions; gate input/output hashes match. All 46 differential groups match
the checked baseline or explicit blocked-rename controls. Source/test review
has no unresolved finding. Serialized guarded execution measures median
15.271 seconds / 0.256 MiB/s; anchor/volume queries remain 6,002 each, with
31,998 handle-information calls and two final-path confirmations. All copies
and readbacks pass; the performance goal remains unmet. Final documentation
review approved the atomic correction, recorded in
`rootguard/independent-review-held-attributes-20260928.md`. Receipts are in `rootguard/`, `resume/held-attributes-*`
and `differential/runs/candidate-held-attributes-frozen-7d89ad8690664fc0b808996f1ec8315c`.

First atomic correction: core hold/native bindings and executor admission-reuse
sites, their focused native/runtime/core tests, and CORE/EXECUTOR/ARCHITECTURE/
DEFENSE/AGENTS policy documentation. Parent owns this register, BUGS, PERFORMANCE,
CHANGELOG and HANDOFF. Acceptance: conversion regression and placeholder/query-
failure cases, exact access/share compatibility, full direct-consumer and ordinary
tests, unchanged settlement oracle/imports, differential, measurement and fresh
independent review. Do not weaken descendant or physical-containment checks.
After committing that correction, rebuild preflight from recovery `7eb8c19d`
using the same per-access handle check, complete its gate, then migrate verifier.
The later executor pass may examine cached absolute paths, single-lstat and
redundant root lookup; retiring repeated descendant checks remains a separate
concrete policy decision, not an authorization inferred from low probability.
Raw probe and receipt: `build/root-admission-optimization-20260928/preflight/`
`probe_inplace_root_reparse.py` and `inplace-root-reparse-first-receipt.json`.

This results-oriented plan replaces the nine-row RO register, which never
reached implementation and remains in Git history (last at `c05eea25`).
Details beyond this page are decided per step, against real code.

**Result and target.** Remove repeated root and path work from the executor,
preflight and verifier. The [investigation](PERFORMANCE.md#executor-assessment--2026-09-27)
found:
- A flat 4 KiB COPY performs 27 root admissions and about 48
  `GetVolumePathNameW` calls; 1,000 × 4 KiB F:→G: takes 28.2 s (0.14 MiB/s),
  versus about 1.6 MiB/s before the pathing work.
- Readback verification spends about 70% of its 3.2 ms per file on root and
  volume probing.
- Preflight fully admits the root once per subject.

The target is **above 1 MiB/s for 1,000 × 4 KiB F:→G: execution**. It is a goal,
not a gate: missing it means reporting the measured breakdown and deciding the
next step with the user, not holding back correct improvements.

**Approach: hold the root instead of re-proving it.** Each executor, preflight
and verifier invocation fully admits its roots once, then holds each root open
until the invocation pauses, returns, fails or is canceled. The hold opens the
root with directory access (`FILE_LIST_DIRECTORY`) and without
`FILE_SHARE_DELETE`. While it is held, renaming the root or any ancestor fails
with "in use". Creating, renaming and deleting inside the root still work, so
descendant reparse checks and per-item stat guards remain. Per-access root
admissions are removed from the held path rather than optimized. Resume and every
new invocation admit fully again. Holds live in invocation-owned scope, never on
the runtime's shared filesystem adapters, and never in plans, continuations,
the database or wire values.

Witnessed 2026-09-28 on NTFS (C:) and exFAT (K:):

| While the root is held | Result |
| --- | --- |
| Rename the root: directory-access handle without delete sharing | Blocked (sharing violation, 32) |
| Rename the root: attribute-only handle | **Allowed**: Windows skips share checks for attribute-only access |
| Rename an ancestor | Blocked (access denied, 5) |
| Create, rename or delete files and subdirectories inside the root | Allowed |

The hold implementation pins the access mode with a regression test and adds
root deletion to the witness. Volume mount remapping and mount-point removal
stay outside the supported model. A subst alias does not establish held mode:
its final handle path must pass the same strict spelling rule.

**Fallback.** UNC and mapped network roots keep today's per-access admission.
SMB behavior is unwitnessed. So does any root whose hold cannot be acquired
with the required access. The fallback path, and the one full admission each
invocation still performs, also get the call reductions: one
`GetVolumePathNameW` per admission, volume information queried at the admitted
anchor, immutable facts built once per invocation, reused native bindings,
direct lexical derivation, a single-lstat `_stat_path`, and single-lstat
descendant walks.

**Decisions made (user, 2026-09-28).**
- The "point-of-use evidence" contract in AGENTS, ARCHITECTURE and DEFENSE is
  reconsidered. A held root replaces repeated re-probing for the invocation's
  lifetime. The contract wording changes in the commit that ships the hold.
- Rename, move and Safely Remove failing with "in use" during an active
  invocation is acceptable: the root is in fact in use.
- The per-access fallback stays.
- Commits are atomic: each is one complete, coherent change, however large.
  Split only along genuinely independent boundaries; never land part of a change.

**Equivalence.** The candidate is compared with the baseline on the same inputs.
- *Must match:* per-operation outcome and reason code; recorder commands and the
  evidence they carry; final managed trees (bytes, managed attributes,
  preserved timestamps); owned artifacts (trash contents, recoverable temp
  names); and every refusal the baseline makes on unchanged filesystems.
- *May differ:* the number, order and native API of read-only probes; timing;
  error message text (the reason code stays the same); non-managed metadata
  such as access times. External mutation during an invocation may be refused
  earlier, or prevented by the hold; the external rename then fails and
  execution follows the unswapped path. The candidate must never perform an
  effect the baseline refused.
- *Needs a decision:* any other difference, including dropping a defensive
  check that changes a concurrent-mutation outcome. That is usually a one-line
  question, not a plan change.

**Verification.** Existing department tests and the ordinary suite as the
change's reach requires, `lint-imports`, and the settlement oracle. One re-pin
of the oracle baseline is allowed, with evidence that only successful probe
calls changed and the existing guard scan still passes; EXECUTOR's replacement
rule is waived for that re-pin. Also run a baseline-versus-candidate
differential from the isolated baseline worktree
(`C:\Users\Spectrum\.codex\worktrees\root-admission-baseline\NamiSync`, `b8baf42d`) over
executor, preflight and verifier fixtures, including the preserved root-swap
and identity-weak probes. Build the harness in the first step that changes
consumer behavior, and grow it with the work.

**Needs a decision first.** Changes to stored identity or wire values,
settlement policy, or supported filesystems; holding roots across pause; or any
root-safety change beyond the hold and its fallback.

**Stop** on an equivalence violation that has no decision behind it. AGENTS
mandatory stops still apply.

**Order.** Measure after each step, then choose the next from the numbers.
1. **Core:** hold primitive with its witnesses, plus the admission call
   reductions shared by the fallback.
2. **Executor:** hold per `execute` invocation; drop held-path per-access root
   admissions; single-lstat stat and descendant work; oracle re-pin if needed.
3. **Preflight and verifier:** hold per invocation; the verifier takes its
   sector size from the opened handle.
4. **Review against the target:** optimize only what is still measurably hot.

Implementation activated by the user on 2026-09-28 from `3c8b4b41`, on
`milestone1-adelbert`. Each step receives independent review before its atomic
commit; no changes to unrelated branches, recoveries or stashes are included.

**Core atomic outcome — shared admission and hold primitive.** Product and
test population: `core/root_authority.py` and `tests/core/test_root_authority.py`.
Reuse native bindings, discover the anchor once for default admission and query
volume information at that admitted anchor. Preserve the injected root-based
volume-probe seam and its evidence checks. Add an invocation-local directory
hold acquired before full admission, with UNC/mapped-network/unholdable fallback
and deterministic release. Native witnesses cover root rename/deletion, ancestor
rename, allowed descendant changes, required access/share flags and release.
This step does not migrate consumers or change settlement, stored identity,
wire values, or descendant safety policy. The existing fallback refusal codes
and component checks remain. Documentation population: AGENTS, CORE,
ARCHITECTURE, DEFENSE, this register, PERFORMANCE, CHANGELOG and HANDOFF.
Acceptance: focused native/core cases, ordinary suite, import law, unchanged
settlement oracle, admission call/timing measurement and independent review.
The baseline differential grows at the first consumer migration. Existing
equivalence and mandatory stops apply. Commit this complete core outcome before
executor migration; only the latter can claim executor hold acceleration.

The frozen final-path correction passed 134 focused seam cases, 5,430 ordinary
tests (four privilege skips, 34 headed deselections), all 12 import contracts
and the unchanged 30-scenario settlement oracle over three runs. Input/output
hashes match in `resume/bound-gate-*.json`. Two additional K: exFAT native
lifetime cases passed. Independent source/test review found no actionable
findings. No oracle re-pin was used.
Integrated as `6536c04` on `milestone1-adelbert`.

**Executor atomic outcome — invocation holds and diagnostics.** Revalidate
the core seams at `6536c04`, then migrate `executor/native.py` and `runtime.py`
behind the existing facade. One invocation record owns root authorities,
construction failures, holds and admitted facts. Acquire nonthrowing holds at
entry; retain full admission and invalid-authority failure at the original
guard so blocked/no-op/pause and target/source failure precedence remain.
Scope all settlement and cleanup; release on every exit and reacquire on resume.
Keep original filesystem dispatch, with explicit activation forwarding in the
audit tracing wrapper; custom adapters without activation keep existing behavior.
Default native admission queries the captured anchor directly while overridden
volume-probe callbacks retain their logical-root argument and dispatch.

Add invocation-owned internal diagnostics recording source/target hold decisions
and exact fallback classes, collected by the rig under its existing metrics
toggle. Do not store mutable last-run state on shared adapters or change event,
result, recorder, wire or persistence values. Source population includes the
executor facade if exporting a diagnostic collector, `tools/executor_rig.py`,
`tools/__main__.py` and the settlement audit's tracing adapter. Test population:
executor native/runtime/lifecycle/settlement and direct workflow consumers,
existing facade, rig and CLI tests. Evidence-only differential producer changes
require renewed baseline repeat captures before candidate comparison.

Preserve physical root resolution, the second root-directory observation,
descendant physical containment,
per-item stat behavior and all settlement guards. Single-lstat consolidation is
a later independently reviewable outcome after measurement. Acceptance: existing
native finalization/repair/composition and settlement cases first; held/fallback
mix, pause/resume/exception release, wrapper dispatch and diagnostic isolation;
baseline differential, ordinary suite, import law, settlement oracle, guard scan,
NTFS/exFAT native evidence and serialized F:→G: rig measurement. A probe-only
oracle re-pin remains allowed once under the rule above, not required merely
because a scope exists. Document behavior in EXECUTOR/TOOLS and evidence in
PERFORMANCE; update this register, HANDOFF and CHANGELOG. Independent review
and the equivalence/mandatory stops precede the atomic executor commit.

**Executor admission skip explicitly approved on resumption.** Following an
automatic-review block, the user answered the concrete prompt: "yes, continue
with the admission skip." The implementation uses the existing `confirm()` API;
rejected drafts remain historical evidence only. Frozen source passes 5,442
ordinary tests (four skips, 34 headed deselections), 12 import contracts,
unchanged settlement oracle 30 × three and a 70-row/391-effect guard scan with
zero missing admissions. Gate input/output hashes match. The baseline
differential passes 32 groups with no unexpected differences, including seven
blocked first-checkpoint swaps compared with complete unswapped controls and
seven pre-execution swaps retaining baseline outcomes. No oracle re-pin is used.

Serialized F:→G: samples have median 11.204 seconds / 0.349 MiB/s. Anchor calls
fall from 48,000 to 6,002 and volume-information calls from 20,000 to 6,002;
two final-path queries confirm the two held roots. All copies/readbacks pass.
The goal remains unmet; choose the next bounded reduction from the remaining
cost after closing this atomic step. PERFORMANCE owns methods and receipts.
The K: scope witness passes; its copy witness truthfully fails with error 87.
Read-only queries establish a pre-existing unconditional handle-identity
compatibility blocker, but do not trace the first failing copy API. BUGS records
the deferred finding; this step does not change filesystem support or claim
exFAT copy success. Evidence is under `build/root-admission-optimization-20260928/`
in `executor/`, `resume/` and `differential/`.
Independent whole-outcome review approved source, evidence and documentation;
the receipt is `executor/independent-review-20260928.md` in that evidence root.

The user supplied a replacement writable exFAT volume at K: on resumption.
Its identity was re-probed and the native hold witness passed there and on NTFS.

**Approved binding correction.** The core primitive confirms the acquired
handle only after full admission, using exactly one normalized DOS
`GetFinalPathNameByHandleW` query. It enables held mode only when the returned
path matches the logical root exactly, allowing drive-letter case alone.
Identity confirmation, the second open and `FILE_ID_INFO` queries are removed.
Both intermediate-junction swap cases are passing native regressions. Cheap
case, short-name, mount-alias and unavailable-evidence cases exercise fallback.
Fallback reasons are internal observations; case folding or short-name patterns
never authorize access. Executor integration exposes these reasons in its
diagnostics and rig report. Setup root spelling is not canonicalized here.

NTFS and replacement exFAT K: lifetime witnesses require a confirmed hold and
verify root/ancestor mutation refusal, descendant operations and release.
A non-admin subst fixture was created, but full volume admission failed before
confirmation (native error 144); it does not prove a held transition. Exact
owned mapping cleanup is verified, and the strict comparison rule covers
alias rejection without that native transition claim.

The initial acquire-only and interim endpoint-identity candidates failed the
same namespace-custody mechanism: an intermediate junction could redirect
acquisition away from the later admitted root, or be restored before identity
comparison. The user approved replacing that mechanism on resumption. Raw
probes and failed receipts remain under `core/`; final correction receipts go
under `resume/`. Recovery `cfcc6ef` on
`codex/wip-20260928-1158-root-hold-binding` remains preserved until task
accounting. Useful changes are rebuilt and verified on the original branch;
the WIP is never merged or cherry-picked as-is.

For subsequent executor work, retain the later descendant physical-containment
check and second directory observation initially. Read-only probes showed
that removing them changes concurrent refusal/error observations. Measure
hold integration before seeking a separate decision to remove those checks.
The corrected core gate is complete. Preflight/verifier migration and
single-lstat consolidation remain separate pending outcomes.

**Next outcome — preflight invocation holds.** After executor `90b57646`, the
user chose preflight, then verifier, then further executor optimization. The
required held-attribute correction is integrated as `8cdd669`. Rebuild only the
three preflight files from recovery `7eb8c19d`, and call `require_ordinary()`
before the helper returns cached admission. All five observation families keep
their existing typed refusal policy. Renew the conversion, placeholder and
query-failure evidence and all affected gates; the old partial passes alone
do not accept the rebuilt candidate. The
preflight population is `modules/preflight.py`, its focused tests and direct
workflow/native and tools-preparation consumers; PREFLIGHT owns behavior,
PERFORMANCE measurements, and this register/HANDOFF/CHANGELOG delivery status.
One native invocation scope holds each root before its existing full root
observation and confirms only successful admission. Preserve supplied filesystem
dispatch, fallback, subject/parent/trash no-follow checks, both physical
resolutions, final leaf stat and leaf-volume checks. Hold state stays outside
ObservedWorld, adapters' lasting state and pure judgment; all exits release it.
No single-lstat, stored identity, exFAT compatibility or settlement change.
Acceptance: existing native seams; held/fallback admission counts and rename/
release witnesses, exception/nesting/override isolation; unchanged-world/verdict
baseline differential with explicit prevented-swap controls; focused/direct
consumer and ordinary suites, imports, unchanged oracle, measured preparation
preflight time/calls, and fresh independent review. Commit the complete preflight
outcome before verifier implementation. Existing equivalence and mandatory
stops apply; verifier design remains read-only until this gate closes.

The rebuilt, guarded preflight passes 92 focused and 314 direct-consumer tests.
All old tests remain; five native conversions exercise each observation family,
and typed placeholder/query-failure cases preserve output/refusal boundaries.
An observation-only 1,000-copy plan from F: to empty exFAT K: passes, with source
unchanged and exact-empty teardown. Its counted run confirms three anchor and
volume queries, two holds/final-path confirmations and 2,002 fresh basic-attribute
queries. This is preflight evidence, not an exFAT copy claim or timing result.
The unchanged 46-group differential producer `243d2173` reuses checked baseline
repeats; candidate `candidate-preflight-guarded-de75f6c180eb45979f357bb73a7471a8`
has zero unexpected differences, including three required blocked swaps and
strict case fallback. The ordinary suite passes 5,480 tests (four skips,
34 headed deselections), 12 imports, unchanged oracle 30 × three and guard scan
70 rows/391 effects with zero missing admissions. Input/output hashes match.
Serialized identical-driver observations have median 2.722 seconds on `b8baf42d`
and 0.551 seconds on the candidate; pure judgment is about 0.010 seconds on both.
F:→G: counted observations match the K: counts above. PERFORMANCE owns methods
and limits. Independent whole-outcome review approved the candidate in
`preflight/independent-review-guarded-preflight-20260928.md`; this closes the gate.
Earlier partial receipts remain historical under the same evidence root.
Integrated as `4263b12` after correction `8cdd669`.

**Active outcome — verifier invocation holds.** The user authorized verifier
after preflight. Revalidate the read-only proposal against `4263b12`, then change
`modules/verifier/native.py` and `engine.py`, the authority-bound tap in
`tools/seams.py`, their native/engine/tools verifier tests, and VERIFIER/TOOLS
documentation. Parent owns this register, PERFORMANCE, CHANGELOG and HANDOFF.
Core protocols, facade, result/wire/continuation shapes and workflow policy stay
unchanged. One native invocation record binds exact authority, native reader,
dispatched reader and live lifetime. Explicitly hand it to engine classification;
transparent taps forward activation. Acquire after reporter/reader setup and
before the first checkpoint; fully admit lazily at the existing admission seam.
Only successful native admission and strict confirmation permit reuse. Both
engine admission and native final-touch root-prefix reuse require current
`require_ordinary()` attributes under their existing error mappings. Invalidate
before releasing on every exit; custom/direct/unactivated readers retain fallback.

Preserve selected-root checks, descendant lstat, per-file root/file final-path
containment, all four same-handle snapshots, opened-volume identity, no-buffering
and read-only sharing, alignment, classification and conditional recording.
No geometry change, native-binding cache, stat consolidation, buffer reuse or
new diagnostics in this commit. Existing engine/native seams run first, followed
by held/fallback/tap and all-four-operation cases, first-checkpoint/lazy admission,
release and copied-context/owner isolation, current-attribute refusal at both
owners, direct recorder/workflow/tool consumers, ordinary suite, imports,
unchanged oracle/guard scan, baseline differential retaining custom remount and
identity-weak controls, separate call counts and uninstrumented small-file timing,
and fresh independent review. This complete gate defines one atomic commit.
Existing equivalence and mandatory stops apply. Opened-handle sector geometry
is the next independently gated outcome; its native NTFS/exFAT capability proof
does not claim exFAT verification or fix the deferred FileIdInfo issue.

The frozen hold outcome passes 132 focused, 479 direct-consumer tests (two
skips), and 5,502 ordinary tests (four skips, 34 headed deselections), all 12
imports, unchanged oracle 30 × three and guard scan 70 rows/391 effects/zero
missing admissions. Input/output hashes match. The 67-group differential adds
native/tapped all-mode, blocked first-checkpoint, active case-fallback and custom
remount/identity-weak controls; all match the checked baseline or complete
unswapped controls, with no projection relaxation. All eight frozen hashes match.
Serialized 1,000-file verification median is 3.885→1.998 seconds versus `b8baf42d`,
including earlier core changes. Separate counts reduce anchor queries 4,000→1,001
and volume information 1,000→1, retaining 1,999 current root-attribute checks
and all 12,000 file-information calls. PERFORMANCE owns methods and limits.
Independent whole-outcome review approves the commit in
`verifier/independent-review-holds-20260928.md`.
Integrated as `0b85d88`.

**Active outcome — verifier opened-handle geometry.** Refresh the finite
proposal against `0b85d88`; change only verifier `native.py`, its native and
engine test files, and VERIFIER behavior documentation, plus parent-owned
delivery/performance records. Query FileStorageInfo16's positive logical sector
size on the already opened unbuffered file. On query failure or zero, use the
existing fresh pathname geometry. If file open fails, perform the old pathname
query before re-raising, preserving simultaneous geometry-refusal precedence.
All successful opens close on geometry, containment, stat, read or yield failure.
No shared geometry cache, engine policy, tools behavior, buffering, identity,
supported-filesystem or defensive-check change. Existing F:/K: API receipts
answer capability only; the exFAT FileIdInfo issue remains excluded.

Acceptance: existing native/engine seams first; same-handle positive geometry
without pathname lookup, unavailable/zero fallback, fallback refusal and exact
closure, open-missing/access plus successful/refused geometry precedence,
unchanged final-path/stat/read/selected-subject guards; migrate only the named
owning API fakes and held-mode geometry counter. Then direct recorder/workflow/
tools consumers, ordinary/import/oracle/guard gate, unchanged 67-group baseline
differential, separate native counts and serialized verifier timing, document
checks and fresh independent review. One complete atomic commit; equivalence
and mandatory stops remain unchanged. Further executor work follows this gate.

Geometry's frozen four-file outcome passes 144 focused, 479 direct-consumer
tests (two skips) and 5,514 ordinary tests (four skips, 34 headed deselections),
12 imports, unchanged oracle 30 × three and guard scan 70/391/zero missing
admissions. Gate hashes match. The unchanged qualified 67-group differential
passes without new projection exclusions; post-capture hashes match. Serialized
verifier median is 1.512 seconds (1.267–1.551), with one anchor/volume query each,
1,000 handle-sector queries, zero pathname-sector queries and unchanged file
guards. Independent whole-outcome review approves the commit in
`verifier/independent-review-geometry-20260928.md`.

**Findings outside this result** go to BUGS or HANDOFF as short notes and are
not handled here. Two exist: a same-volume root replacement before execution
accepts creation effects, and identity-less DELETE/TRASH acts on a
metadata-matching replacement file. The hold closes neither case when the
replacement happens before an invocation starts.

**Evidence.** Raw receipts go under `build/root-admission-optimization-<date>/`
(starting baseline, guard scan and probes are already under
`build/root-admission-optimization-20260928/`). PERFORMANCE owns method and
results; HANDOFF owns resumption.

## Incident repairs and closeout — 2026-09-27

### Authorized cold-admission follow-up

From `0e4595e4`, the user authorized two separate commits on `milestone1`:

| ID | Outcome and finite population | Preserved guarantees / verification | Status |
| --- | --- | --- | --- |
| CLI-DRIFT | Distinguish observed cold-file drift from stable incompatibility and unavailable artifacts; bound validation-only retries and give persistent drift non-destructive retry guidance. Owners: db contracts, workflow pair admission, CLI and their direct repository/history/initializer consumers; focused database/CLI tests and DATABASE behavior documentation. | Cold source nonmutation, fresh-pair creation/rollback, live-owner checks, existing CLI refusal exit, no mutex or task replay. Deterministic transient/persistent drift, stable mismatch, I/O/journal controls, CLI pair/history paths, ordinary suite, import law and independent review. One fix commit. | Complete: `5e4bf87`; 5,410 ordinary passes, 4 privilege skips, 34 headed deselections; 571 focused passes, 27 exact-count controls, 12 import contracts, 151 documentation links; independent review approved. |
| DOC-PRECISION | Correct TESTS' unverified already-visible-notice rationale and scope DATABASE's own-snapshot statement to owner-opened connections. No new internal history-reader validation. | Source comparison, documentation links/diff checks and independent review. One separate documentation commit after the fix. | Complete in this documentation commit; source comparison, links/diff checks and independent review. |

Desktop Setup refusal mapping, cross-process exclusion and unrelated CLI tooling
changes remain excluded. Existing safety/recurrence stops apply. Evidence lives
in `build/cold-admission-followup-20260927/`; root serializes shared delivery
documents. Admission retries must not retry task submission or effects, and
inconclusive observations must never acquire reset advice merely by exhausting
the retry policy.

Implementation boundary: schema owns a shared admission-error base with the
existing mismatch exception as a subtype; contracts owns typed observed drift
and a single three-attempt validation policy. Pair admission retries a complete
single-attempt ledger/history/recheck operation, while standalone consumers
apply the same policy to one role. Cleanup failure or control interruption must
not disappear into retries. Schema errors remain provisional until source
stability is rechecked. Three attempts bound repeated work, not total elapsed
time for reading arbitrarily large files.

Workflow-owned non-destructive guidance passes through DatabaseContractView to
CLI and the existing host startup display. Direct facade/view consumers and
their witnesses are in the finite migration. Typed history admission refusals
use the existing CLI refused exit (3); other history read failures retain exit
4. Stable incompatibility alone retains reset advice. No fresh publication,
reservation, task submission or filesystem effect enters a retry body.

The user authorized four separate reviewed outcomes from `a0205c08`.
Implementation boundaries and the original finite populations are retained in
Git history; component documents own the resulting behavior. Evidence is under
`build/admission-bridge-closeout-20260927/`.

| ID | Delivered outcome | Verification | Commit / status |
| --- | --- | --- | --- |
| IR-DB | Separate strict cold file admission from runtime-owned live SQLite validation. Preserve exact schema/pair/journal/placement refusal, independent role reads, fresh noncreating Plan and truthful effects. DATABASE/DEFENSE own the contract. | Deterministic reader/WAL activity and refusal/lifetime controls; 5,379 ordinary passes, 4 privilege skips, 34 headed deselections; installed Setup passed; 12 import contracts; 87 documentation links; independent review. | Complete: `639b2ea`; `db-review.md`, `db-implementation.md`, `db-ordinary-final.xml`, `db-installed-setup.xml`. |
| IR-BRIDGE | Migrate the optional diagnostic to current scalar/terminal shapes, retain exact reliable-item witnesses, preserve the first report failure and raw incomplete streams, and settle synthetic cancellation through normal host cleanup. BRIDGE/PERFORMANCE own behavior and observations. | 35 focused passes and CRLF page probe; 5,380 ordinary passes, 4 privilege skips, 34 headed deselections; complete installed observation on `639b2ea`; injected rejection retains raw evidence and exits normally. | Complete; independent review approved. The commit carrying this row delivers IR-BRIDGE. `bridge-review.md`, `bridge-ordinary-final.xml`, `bridge-full-final.json`, `bridge-injected-report-failure.json`. |
| IR-CLOSE | Remove AB-7 focus loss from BUGS and retain environmental troubleshooting in TESTS. Retain the enabled-button wait for independent asynchronous-filter sequencing. Retire the unrealized DWM sentinel obligation; no new focus/compositor detector. | Source/evidence review, 86 documentation links and diff checks; independent approval. Product/helper unchanged. | Complete: `e8d3613`; `closeout-review.md`, `closeout-docs-check.json`. |
| IR-DEFER | Shelve AB-8 stack/wrap; retain the unconfirmed renderer/check race, historical limitations and recurrence inspection points in TESTS. | Documentation consistency, 84 links, evidence references and diff checks; independent approval. No CSS/helper/assertion change. | Complete: `8f75f75`; `defer-review.md`, `defer-docs-check.json`. |

The database runtime retains two lazy role connections. Later pair checks and
consumer opens validate current SQL, main identity and journal absence; public
standalone constructors retain cold byte-preserving preflight. Reader retirement,
writer placement and retryable runtime shutdown remain intact.

The bridge driver decodes only its finite 1–1,500 byte coordinates, consumes
item-free terminal facts and independently checks 150 ordered reliable outcomes
per task. Reporting stops on the first rejection, queued counters unwind, and
failure metadata is captured before cleanup. Failure/final milestones and
unfinished timing streams survive clean incomplete exits. The current source
population is the bridge diagnostic package, its focused test module and page
probe; production host/transport and frozen custody JSON are unchanged.

Historical advisory `passed`/`event_passed` remain false in the final native
observation; `status=complete` and `measurement_valid=true` establish the
diagnostic endpoint only. No new timing/custody acceptance is claimed.
Original AB-7 Setup and AB-2/AB-10 causal attribution remains qualified.
All original and intermediate failure receipts are retained.

AB-8 implementation, environment monitoring, GUI changes, automatic mutation
replay, broad schema migration and unrelated M1 work remain excluded. A
pre-existing performance-CLI error suggests an unsupported replacement flag;
BUGS records that separate guidance defect, and reruns use fresh report paths.
No CLI change was included.

## Post-M1-8 reduction plan

AB-1–AB-10 are delivered. The batch reduced duplicate presentation and bridge
work while retaining reviewed effects, truthful results, installed desktop
journeys and the current subject contracts. It made Plan/execution UI latency
and empirical representation-memory measurements optional developer tooling;
enforced bounds, counted-work regressions, release resource checks, transport
custody, and executor settlement retain their separate authority. No speed or
memory improvement is claimed. The table is the completed register; Git,
CHANGELOG and the named ignored evidence hold its chronology and failed receipts.

| Closed outcome | Result and current owner | Commit and evidence |
| --- | --- | --- |
| AB-1 | AGENTS small-change default, concise delivery records and PERFORMANCE methods/results ownership; subject contracts and DEFENSE evidence authority stay separate. | `29d9b8f`; `build/post-m1-8-ablation-20260925/ab1-checks.json` and review. |
| AB-2 | Optional selected performance drivers moved to `tools/performance/` with independent fixture/action checks and truthful incomplete reports; required correctness/release gates retained. [PERFORMANCE](PERFORMANCE.md), [TESTS](TESTS.md), [TOOLS](TOOLS.md), [DEFENSE](DEFENSE.md). | `8ba38ced`; `build/post-m1-8-ablation-20260925/ab2-migration.md`. Historical JSON/contract/authority bytes remain unchanged. |
| AB-3 | Unused historical mapping reader removed; current scan correspondence, unique-pair/hardlink refusal and ledger behavior retained. [DATABASE](DATABASE.md), [PLANNER](PLANNER.md). | Reviewed `c5f1de8`, integrated as `dd23c270`; `build/post-m1-8-ablation-20260925/ab3-integration.md`. |
| AB-4 | Desktop Plan open captures one revision-bound summary and workflow-owned membership without building a full public preview; folder derivation is lazy. Public CLI/API preview and selection authority remain. [INTERFACES](INTERFACES.md), [PRESENTATION](PRESENTATION.md). | `9cfd2a0`; AB-4 verification in `build/post-m1-8-ablation-20260925/`. |
| AB-5 | Bridge response adoption combines repeated traversal over one detached value; complete request, byte, type, identity, prefix and custody checks remain. [BRIDGE](BRIDGE.md). | `1cb75fb`; AB-5 verification in the same evidence root. |
| AB-6 | Genuine document replacement retires page authority and presents a contained restart path while admitted work and worker custody continue. Canceled navigation and same-document history retain their distinct behavior. [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md). | Harness prerequisite `f55a7dd`, product `2b4a2214`; AB-6 gesture and verification receipts in the same evidence root. |
| AB-7, AB-7R, AB-7S and corrections | Existing asynchronous admission/completion retains original results for effect/lifecycle commands without elapsed-time mutation abandonment or replay. Bounded observation, late adoption, explicit unavailable/invalid-result feedback, duplicate protection, exact intent fences and pending Close survive. Five revisioned/current-state commands use refresh or fresh choice. One browser attempt/settlement owner replaces duplicate recovery paths. [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md), [DESKTOP_UI](DESKTOP_UI.md). | `6287db0c`, `d4351acd`, `514d71d1`, corrections through `4f1537c2`; `build/post-m1-8-ablation-20260925/ab7-verification.md`, `ab7r-verification.md`, `ab7s-verification.md` and later review receipts. The earlier unexplained Setup/Plan-again observations are not claimed fixed. |
| AB-8 and follow-up | One Python task/session snapshot owns semantic progress and terminal presentation; the page atomically adopts bounded facts. Gap uncertainty, exact scalar identity, item windows/detail, transport replay, local interaction, D4, command recovery and Close remain. A task-list summary can briefly precede snapshot delivery without becoming a second terminal authority; record adoption reconciles them. [BRIDGE](BRIDGE.md), [PRESENTATION](PRESENTATION.md), [INTERFACES](INTERFACES.md). | `7445f70a`, `4ff11a8`; `build/ab8-resume-20260926/` and `build/ab8-followup-20260926/`. Full event-body removal remains a separate protocol decision. The earlier stack/wrap rerun's cause was not established. |
| AB-9 | Duplicate CSS/source/gallery spelling pins retired with behavioral, computed-style, native, accessibility and security witnesses retained; no production asset changed. [TESTS](TESTS.md), [DESKTOP_UI](DESKTOP_UI.md). | `7af07724`; `build/ab9-20260926/verification.md` and `detector-map.md`. |
| AB-10 | Integrated workflow, boundary and evidence sweep; one stale optional execution-UI feedback driver/checker corrected while frozen historical JSON and product semantics stayed unchanged. Required retained gates and final endpoint/installed journeys were accounted by dependency. | `cb57c41a` (first AB-10 commit); `build/ab10-20260926/verification.md`, `reuse-and-raw-evidence.json`, review and link receipts. The bridge-event diagnostic remains incomplete with an unassigned event-v5 fixture migration; it claims no product cause, release gate or performance result. |

Post-closeout consolidation archived the study and pruned the accounted AB-3,
AB-6 gesture, GUI-J and GUI-M2 recovery refs plus the AB-3 worktree. Exact tips
and complete history remain in `build/ab10-20260926/side-recoveries.bundle`;
`preservation.json` and `cleanup.json` record verification and 78 copied evidence
files. All five stashes and the pending DOC-2 branch remain; no remote changed.

The retained user decisions are: unsupported reload with stale-document
containment (D1); no timed mutation-result abandonment or automatic replay, but
recovery of the original result after delivery failure (D2); optional useful
performance measurements without new hard speed targets (D3/E1/D7); unchanged
highlight/focus and range/navigation behavior separate from execution checkboxes
(D4); native Advanced Color mitigation (D5); and the user-owned small-change
classification in [AGENTS](../AGENTS.md) (D7). D6's missing-row
acknowledge/restore desktop capability is accepted and still needs an explicit
delivery allocation when M1-9/10 activates. M1-10's rebaseline confirmation
accepts replacement of content evidence and is a different action. Existing
[FEATURES](FEATURES.md), [INVENTORY](INVENTORY.md),
[PRESENTATION](PRESENTATION.md) and [DESKTOP_UI](DESKTOP_UI.md) own the D6 behavior;
this completed batch neither deletes it nor marks it delivered.

| Rejected or deferred study lead | Current disposition |
| --- | --- |
| L5 producer/retained admission merger | Rejected: independent counter-free populations and cumulative retained charges differ. [DEFENSE](DEFENSE.md) owns bounds. |
| L7 copy diagnostic removal | Rejected: tools consume default-off copy metrics. [TOOLS](TOOLS.md), [EXECUTOR](EXECUTOR.md). |
| L8 continuation/settlement class merger | Rejected: distinct recovery facts and legal states; no safety-equivalent simplification. [EXECUTOR](EXECUTOR.md). |
| L9 CSS replacement for native Advanced Color | Rejected: CSS misses SDR WCG; retain native mitigation. [DESKTOP_UI](DESKTOP_UI.md). |
| L6 Plan-volume/verdict check consolidation; S5 full application-owner merger | Unqualified/deferred. Construction, shape and semantic checks protect different boundaries; lifecycle, service, observer, dispatcher and adapter cleanup have distinct owners. No generic validator, lock or settlement framework is authorized. [ARCHITECTURE](ARCHITECTURE.md), [DEFENSE](DEFENSE.md), [INTERFACES](INTERFACES.md). |
| Full event-body removal; Plan-again tracer retirement; broad projection topology and shared selection-admission/safety cache ideas | Separate deferred decisions, without implementation authority from AB-8 snapshot trimming or the older R7 study. Retain diagnostic/replay consumers, tracer and copy metrics until an activated boundary accounts for them. [BRIDGE](BRIDGE.md), [PRESENTATION](PRESENTATION.md), [TESTS](TESTS.md). |
| Older recording-tail, pause/cancel and mutation-verdict compression ideas | Unscheduled alternatives from the completed narrow-reduction study, not latent checkpoints. Exact mutation/publication/recording order and settlement oracle remain [EXECUTOR](EXECUTOR.md) obligations. |
| Older R7-5–R7-8/R7-G and the blanket AB-7 domain-resend proposal | Old execution denominator retired, not passed. AB-2/4/7 absorb selected outcomes; AB-7R validation rejected blanket receipt equivalence and resend. No old checkpoint or frozen test recipe resumes. Historical detail is in the archived study §13–14. |

Five earlier studies remain historical under `obsolete/`: completed TA/ST/PR/NR
work is accounted in the [archived study §13](obsolete/POST_M1_8_ABLATION.md#13-earlier-studies-absorption-and-archival-accounting).
Their still-supported boundary, selection, lifetime, native, history, database,
workflow and executor guarantees are owned by CORE/TESTS/DESKTOP_UI/INTERFACES,
DATABASE/HISTORY, ARCHITECTURE/WORKFLOWS and EXECUTOR respectively; archived
method prescriptions cannot silently reopen them. The old M1-7 R7-1–R7-4
were delivered, RI-1–RI-4 investigated, and later R7 rows suspended/superseded.
The unproven foreign-task Execute-result concern did not establish a supported
misroute; current [BRIDGE](BRIDGE.md) identity adoption remains binding.
In particular, history write admission precedes pending mutation, persisted
readback checks normalization/hash/columns/receipts, old or mixed database pairs
refuse without automatic migration, and executor publication/settlement ordering
remains guarded. CORE/TESTS retain the FailureDetail lifetime guard;
VERIFIER/ARCHITECTURE retain duplicate/unknown integrity-selection refusal and
detached facts; DESKTOP_UI/INTERFACES/BRIDGE retain real native input,
accessibility, privacy and media checks. Representation-specific frozen lists,
query-count pins and superseded private-index prescriptions are historical.

## Completed preparation and MOVE-1

PA-1–PA-3 reconciled five earlier studies and moved them to `obsolete/` in
`0c74ee7`; the current decisions above and the archived study preserve their
dispositions. MOVE-1 (`549f3b4`) restored repeated source moves through current
unique correspondence while current hardlinks, duplicate identities, ambiguous
pairs and incomplete scans remain ineligible. [DATABASE](DATABASE.md),
[PLANNER](PLANNER.md) and [BUGS](BUGS.md) own its behavior; the native/ordinary
receipts remain in `build/move-history-20260925/`. No schema, recorder or
retained-history rewrite was part of MOVE-1.

## M1-8 execution review closure

M1-8 delivered shared Plan/live/terminal status, bounded rows and Details,
current-ledger distinctions, follow/Go, truthful progress/capacity, action
feedback and same-task Retry observation including pending Close. Retry never
restarts execution. [BRIDGE](BRIDGE.md), [PRESENTATION](PRESENTATION.md),
[INTERFACES](INTERFACES.md) and [EXECUTOR](EXECUTOR.md) own the behavior.
P2/R0–R2/post-R2/RC-1 passed A1–A5 and B1–B6: 5,405 ordinary passes/five
skips, 33 installed GUI obligations and 12 imports. Reviewed commits
`4bbf943`, `8f7555b`, `0fc2f5d`, `9e5b080`, `b1f5a07`, `c974447`,
`96a0212`, `9be2930`, `3ea4e6b`; raw and failed receipts are in
`build/m1-8-archive-20260924/evidence/recovery-close-20260924/`.
[PERFORMANCE](PERFORMANCE.md#source-linked-historical-observations) owns the
fixed U-v2 78-attempt observations.

The A6 integration receipt at `build/m1-8-archive-20260924/integration.json`
records non-squash merge `6c00ec731dd176d201e2a2c3a2a53b47652c544e`,
tree `f7691c518a31a160f888db299faa9342bd9a4349`, candidate
`cd2d44a802c665a4f76331b0a15856ef8102f1ac` and
`postmerge_validation: PASS`. It, not later test color, closes A6. The archived
register owns its finite gate; prior failed R2 attempts remain failed. A page
capture alone does not prove native compositor health. Historical recovery
commits were not merge units.

## Remaining checkpoints

Pending rows record accepted future outcomes. The nine RO rows are authorized;
other pending rows still need user authorization, active scope and finite
verification. A finding does not enlarge a row; [AGENTS](../AGENTS.md) governs
scope changes, stops and recovery.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| Root admission optimization | Hold each admitted root per invocation, keep the per-access fallback for remote or unholdable roots, and reduce admission calls, per the plan above. Target above 1 MiB/s for 1,000 × 4 KiB F:→G: execution (goal, not gate). | Baseline equivalence differential, existing tests, settlement oracle with one allowed probe-only re-pin, hold witnesses and measurements after each step. | Core, corrected executor, preflight and verifier holds committed; geometry gate passed. Measured executor reductions next. |
| M1-9 | Bounded inventory projections, current evidence and the full inventory consumer for sibling sorting. | Complete or prior-complete publication; warnings outside action scope; raw evidence provenance; search/filter/collapse/window/detail, replacement/race and production sort/reset paths; headed witnesses. | Pending. Missing-row acknowledge/restore UI must be explicitly allocated at activation; this row does not silently claim it. |
| M1-10 | Baseline, verify and rebaseline controls plus first same-task manual post-copy verification, without persistent operation-time hashes. Eligible null-evidence files enter rebaseline; every admitted rebaseline hashes and replaces/creates evidence, and a match is not verified. | Confirm acknowledgement admission before claim/native work; all-null/mixed workflow, service/CLI and desktop paths; conditional recording and supersession races; atomic handoff classification; live pause/resume/cancel and unchanged automatic failed-read retries; overlay/result identity. Independently review operation matrix and conditional recording. Terminal Verify-remaining/subset retry remains deferred. | Pending. Rebaseline confirmation is distinct from missing-row acknowledgement. |
| M1-12 | Close integrated lifecycle/retention across activated task surfaces, then complete adversarial, documentation, ordinary and headed verification. This absorbs former M1-11. | Plan-only, execution-only, linked/manual verification, inventory, refused/canceled/degraded/failed tasks across same-document navigation, contained unsupported reload, explicit close and shutdown; admission bounds, stale-response suppression, exact resource release and retained truth. Applicable settlement oracle, ordinary/headed, installed-wheel/product, imports, diff/active-link checks and independent cross-component review. No aggregate-artifact or whole-owner-graph criterion. | Pending. |
| M1-Release | Beta packaging and release closure after delivery rows above. | Installed artifact from clean checkout; frozen specification/dependency/CI, notices and corresponding source; standard-integrity host proof and every applicable BR-G/SH-G gate. [INTERFACES](INTERFACES.md) owns host/package/SH-G; [BRIDGE](BRIDGE.md) owns BR-G. | Pending. |

DOC-2 remains **pending, outside the AB batch**. Its historical branch proposal
removes exactly four superseded compact-plan commits from `milestone1`, preserves
the old tip and opens a draft PR from `milestone1-anthony`. Before any action,
freshly check divergence, remote tip and preservation of all work; unexpected
commits or unaccounted work require adjudication. AB-10 and the documentation
consolidation do not execute, close or authorize DOC-2 history rewriting.

## Delivered product checkpoints

| Closed row | Result and current owner | History/evidence |
| --- | --- | --- |
| M1-4, M1-async | Process-live task creation/navigation/close and bounded asynchronous admission/completion with original effect owners. [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md). | `ab453e1`, `675181a`; `build/m1-async/`. No durable task survival claimed. |
| M1-5, M1-6 | Typed location admission, bounded recents, frozen Setup, serial pair and standalone inventory starts, fresh Plan again. [INTERFACES](INTERFACES.md), [WORKFLOWS](WORKFLOWS.md), [BRIDGE](BRIDGE.md). | `e19ed9d`, `76ba7d0`; `build/m1-5/evidence/`, `build/m1-6/`. Hints grant no authorization; no global default mutation or partial-pair start. |
| M1-7 | Bounded Plan review, sibling sorting, committed selection and same-task execution. [PRESENTATION](PRESENTATION.md), [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md). | Through `5986c57`; `build/m1-7/evidence/p9-full-20260916/`; R7-1–R7-4 later through `95f31e1`, with R7-G retired rather than passed. |
| M1-8-capacity, E, P1, P2, R0–R3 | Stop later operations after recognized capacity failure and current settlement; bounded current-ledger/retained execution review and installed recovery. [EXECUTOR](EXECUTOR.md), [DATABASE](DATABASE.md), [PRESENTATION](PRESENTATION.md), [DESKTOP_UI](DESKTOP_UI.md). | `04947ba`, `7905a1b`, `055325b`, `4bbf943`, exact A6 receipt above and [archived register](obsolete/M1_8_DELIVERY.md). Recorder-only failure remains independent degradation; P2 timing was superseded for final UI by U-v2. |
| GUI-1/S/R/I/D, Plan GUI-P/S/F/H/J/K/L/M/N/O/P, AI-1/2, DOC-1/3 | Task shell, Setup/Settings, bounded batch receipts, Fluent controls/icons, rootless Plan table, server selection/highlighting, search/sort/status and installed polish. [DESKTOP_UI](DESKTOP_UI.md), [PRESENTATION](PRESENTATION.md), [TOOLS](TOOLS.md), [BRIDGE](BRIDGE.md); AGENTS and subject docs own the reconciled rules. | Matching CHANGELOG tasks and commits `27f1a6b` through `2cc0083`. GUI-M2 WIP `af02913` and stash `93414b7` were historical preservation; useful folder-total work was rebuilt in `7cf4448`. |
| GUI-W1/WR1 | Native Advanced Color v3 mitigation for specified dark flyout shadows on WCG/HDR displays. [DESKTOP_UI](DESKTOP_UI.md), [FEATURES](FEATURES.md), [BUGS](BUGS.md). | `c637025`, `build/wcg-review-20260924/`. No Windows compositor fix or WCG-only selector proof claimed; Mica remains required. |

The existing 48-pair bound, serial best effort, per-row options, exact uncertain
retry, keyboard/forced-color and admission guarantees remain active. Clearing
a batch receipt does not close a task. The reported Optics refresh delay remains
unprofiled. No completed row authorizes M1-9 inventory projection, M1-10
integrity controls, M1-12 lifecycle closure or release.

## Accepted behavior carried by the delivery rows

Normally completed tasks retain file lists, item statuses and phase aggregates
for read-only review. Execution-only completion may offer its first eligible
manual verification; linked completion needs no further action. Non-stopping
degradation keeps normal review with visible issues. Canceled/abnormal sessions
retain terminal truth without resume, domain retry or session cleanup. Live
pause/resume remains separate. Busy Close requests best-effort cancellation and
keeps the card until settlement/resource release; it never implies trash purge.
Forced process exit has no durable task/resume guarantee.

Capacity refusal before execution, including queued wakeup, retains the task
without execution, automatic retry or automatic close. Scan/planner admission
refusal may have no plan; review preflight can retain an immutable plan with a
negative verdict. Explicit Plan again resolves reviewed location identities,
creates fresh Setup in a new task, scans again and requires fresh review. It
never carries old selection/authorization or changes the old artifact. Removing
source/target entries affects capacity only through that fresh scan.

Recognized operation, cleanup and destructive-prerequisite capacity failure
stops later admission after current settlement. Recorder-only write failure
remains recording degradation with continuation. Generic I/O retains its typed
reason. Yellow capacity presentation cannot hide independent known failures.
Trash-location text is accepted for M1; exact count needs complete outcome
evidence. Location-only Details never promises a count, existence or purge.

Location admission is workflow-owned for typed, picker and recent Setup/inventory
inputs. A remembered location is not authorization; consumers re-probe at use.
Setup freezes semantic plan options in a backend-derived snapshot without
writing global defaults or granting browser text/filter normalization authority.

Plan review preserves operation, selection, scope and fresh-preflight truth
across view gestures. Canonical path-key order and complete-sibling filename,
raw size and raw mtime sorting in both directions with reset are accepted M1
behavior. Sort is process-live view state and cannot change selection,
commitment, dependency/execution order, risk/counts or action scope; hierarchy
and node identity survive. [BRIDGE](BRIDGE.md) and [PRESENTATION](PRESENTATION.md)
own exact validation and scale criteria.

Execution, inventory and post-copy overlays remain distinct from each other
and ledger-derived state; zero-byte work that ran never looks unrun. Inventory
warnings stay outside path/action scope; publication is complete or keeps the
prior complete generation. Baseline, verify and rebaseline remain distinct.
Rebaseline requires acknowledgement, includes eligible selected null-evidence
files, creates/replaces evidence after fresh hash and clears verification
freshness without becoming compare-and-accept. Manual exact post-copy
verification uses atomic handoff classification on a ready subset, preserves
execution truth and reports ineligible outcomes honestly.

Release remains accepted. [INTERFACES](INTERFACES.md#sh-g-release-criteria)
owns open SH-G-15 cold-start/repeated/long-workload resource policy, still without
a numeric budget or acceptance artifact. Enforced request/population limits and
separate SH-G-8 transport-custody evidence remain unchanged.

## Release completeness

BR-G-43: active docs, README and UI/mockup status describe shipped behavior;
every active DESKTOP_UI acceptance item maps to its subject check or an
explicitly approved deferral. Omission or copied, unmapped checklists do not
close release. BR-G-44: from a clean checkout, run the complete suite including
ordinary-default exclusions, lint-imports and diff checks; collect/pass every
`test_br_g` case without skip/xfail on Windows. Narrow selections do not
substitute for release evidence. [TESTS](TESTS.md) owns commands and routing.
These obligations remain open, with no product release claimed by AB-10.
