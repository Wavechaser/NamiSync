# Test Refinement Delivery Register

## Purpose and authority

This delivery simplifies four bounded test families at source revision
`10265417174e9e9e32b564e73f2527f34b3696d2`: source-owner guards, repository
SQL checks, integrity-selection checks, and visual/headed-harness checks. It is
strictly test-only. Product behavior is the ground truth, but a green product
run is only a control; each rewritten test must also retain its declared fault
detection.

This register is the completion denominator. The exact initial population is
listed in Appendix A. Supporting edits are limited to helpers, fixtures,
constants and imports used by that population; the two additional database
snapshot tests in Appendix A; existing ordinary behavioral witnesses in the
same modules when they absorb a removed assertion; and department ownership
only if a test module disappears. Consumer tests may be run but are not cleanup
targets.

The implementation does not change production code, public interfaces,
dependencies, current batching or index mechanisms, visual behavior, transport
policy, headed runtime control flow, scenario scripts, evidence schemas, or
evidence publishers. ST-H is the sole exception: it removes two test-child
fixed waits without changing the installed host or page choreography. It
preserves the settlement oracle and baseline, all
SH-G-8 protected artifacts, source-owner AST guards, import and patch
allowlists, prohibited-native-API guards, and every current hard-wall or
protected property in `DEFENSE.md`. Detection currently owned by the ordinary
suite may not be moved solely to a headed test.

The prior ablation study remains discovery evidence, not acceptance evidence.
Its working artifacts live under `build/test-ablation/cab2259/`. At delivery
start, `CHANGELOG.md`, `README.md`, and `docs/HANDOFF.md` contain pre-existing
study changes and `docs/TEST_ABLATION.md` was pre-existing and untracked at
entry; it is now staged and remains preserved. They are outside checkpoint
edits until the final documentation closeout. User-owned
`PRODUCTION_ABLATION.md` is ignored and excluded without inspection.

## Checkpoint register

| ID | Accepted outcome | Depends on | Named verification | Status |
| --- | --- | --- | --- | --- |
| ST-H | Synchronize the native-live delayed-return receipt with observed WebView reinjection under the existing scenario deadline | — | Focused handshake fault gates, paired page/harness tests, installed native-live BR-G-30/31 | complete |
| ST-0 | Freeze this population and establish a reproducible green baseline | ST-H | Source/runtime identity, complete suite, import contracts, capability accounting, independent review | complete |
| ST-1 | Simplify fixtures and assertion presentation around the retained source-owner AST guards | ST-0 | Exact guard-output differential, declared inventory mutations, core department | complete |
| ST-2 | Consolidate repository query/result machinery without changing database mechanisms | ST-0 | Declared SQLite behavior and fault probes, database department | complete |
| ST-3 | Consolidate integrity-selection machinery without changing its representation contract | ST-0 | Both selection types, declared behavior/mechanism probes, core/verifier/workflows neighborhood | complete |
| ST-4 | Consolidate visual assertions without changing their verification tier | ST-0 | Declared ordinary visual probes, interfaces department, relevant installed headed witnesses | pending |
| ST-5 | Remove redundant harness spelling assertions only where a same-level detector survives | ST-4 | Declared ordinary harness probes, all interface headed tests | pending |
| ST-6 | Reconcile the combined result, retire temporary machinery, and close documentation | ST-1–ST-5 | Combined fault replay, complete suite, imports, protected-file identity, independent adversarial review | pending |

Checkpoint order is fixed and sequential: ST-1, ST-2, ST-3, ST-4, then ST-5.
The user resumed the remaining checkpoints after reviewing ST-2. Continue
ST-3 through ST-6 in order. Do not begin ST-6 until every earlier row is
complete or explicitly reported unresolved.

## ST-H — Native-live reinjection handshake

ST-H is a separate test-only prerequisite to ST-0. Its bounded population is
`tests/interfaces/web/_native_gate_child.py` and the existing paired
page/harness tests only where needed to verify the handshake. The native-live
delayed-return handler and its return-transport observer must wait for the
already observed second `pywebviewready` event and the resulting
transport under the existing 60-second whole-scenario deadline; neither may
impose a shorter independent latency assumption. The separate
`delayed_handler_started` admission wait remains bounded at 10 seconds because
it precedes navigation and proves dispatch admission rather than reinjection.
Preserve proof that the stale native return is suppressed, `get_current_url()`
is read on the
off-UI handler thread after cancellation, ready and final receipts remain
canonical, missing reinjection fails closed at the scenario deadline, and the
real installed host and its control flow are unchanged.

The predeclared finite fault gates are: `H-F1` delay the second-ready signal
for at least 12.7 seconds before setting the real reinjection event; the old
fixed waits must fail and the repaired handshake must pass within the shared
60-second deadline. `H-F2` suppress that signal; the child must publish no
ready success, exhaust the parent deadline, and be reaped with no live process.
The existing BR-G-30/31 installed-host run must preserve navigation, second
readiness, delayed transport and post-navigation ordering, the off-UI-thread
URL read, stale-return suppression, and canonical ready/final receipts.
Existing headed parent deadline and cleanup tests remain corroboration. A
missing event may consume the shared scenario budget but must never produce
ready success. Discovery is limited to this handshake and its
paired page/harness witnesses; evidence of a broader shared mechanism stops
ST-H for adjudication rather than expanding the checkpoint.

## Current qualification (2026-09-07)

ST-H is complete. Its delayed-ready old/new discriminator, missing-signal
parent-deadline and Job-reaping probe, unchanged installed BR-G-30/31 control,
and independent review all passed. Focused artifacts remain under
`build/test-refinement/1026541/st-h/`, including the retained negative and
capture-driver failures; later success does not erase them.

The broad ST-0 requalification under
`build/test-refinement/1026541/st-0/requalification-01/` passed 4,670 tests in
354.88 seconds with the same four WinError 1314 capability skips. Pytest and
import-linter both exited zero, and all 12 import contracts were kept. The
protected-input check verified all 123 declared files: raw bytes in the
qualified checkout matched the frozen authority. The authorized child repair
was recorded separately; live Git content remained the canonical comparison. Independent ST-0 review confirmed all 123 files, eight protected
function source/AST identities and the exact owner inventory. This completed
ST-0; baseline success alone does not prove later rewritten-test detection.

## ST-1 outcome (2026-09-07)

ST-1 now presents the fixture corpus as five named full-result rows. The
original nested.py and qualified.py sources, relative paths and scope counters
remain separate and exact. Imports and aliases remain one fixture.py row;
async/class/annotation coverage has independent extended.py scopes; the
star-import case remains separate. This preserves observation partitions even
when two analyzer mistakes would conserve an aggregate count.

The frozen v3 manifest and exact disposable sources are under
build/test-refinement/1026541/st-1/. All 18 old/v3 A-F1 through A-F7 and
A-V1/A-V2 runs reached their declared source and matched their declared result.
Raw failures attribute A-F1 through A-F4 to their expected Counter differences,
A-F5 to the added rebindings member, A-F6 to the added star-import path, and
A-F7 to the renamed exact owner. A reviewer regression independently misses
one direct Detail call and duplicates one qualified FailureDetail visit: old
and v3 reject it in distinct fixture assertions, while merged v2 passes because
the two errors cancel in its shared outer bucket.

The final focused selection passed six tests in 0.53 seconds. The one final
core department run passed 911 tests with one unchanged WinError 1314
capability skip and 3,766 deselections in 17.88 seconds; both runs have exit
records and JUnit. Earlier v1/v2 evidence, driver failures, the failed basetemp
run and unnecessary repeat remain append-only and are superseded rather than
erased. The analyzer and exact-owner test retain identical normalized function source
and ASTs; their raw source differs only by CRLF-to-LF line endings in the
editable containing module. The test diff is 99 insertions and 52
deletions, a diagnostic net increase of 47 lines from explicit accepted
coverage; the five policy invocations equal the original count. Line and case
counts are not acceptance evidence. Independent review passed the v3 fixture partitions, all declared probes, and the compensating-fault regression; ST-1 is complete.

## ST-2 outcome (2026-09-07)

ST-2 now shares one exact synthetic mapping-row factory, one query-plan reader
and three narrow SQL-role classifiers. Mapping-pair reads, requested-identity
reads and top-level inventory selections remain independent observations. All
seven Appendix B tests remain separate, and their scoped-result, ordering,
400-subject, index, empty-scope and snapshot assertions remain. The unchanged
alias and stale-target consumers also pass. The large-history fixture now
contains the predeclared target-present/source-absent discriminator.

The immutable v3 manifest, disposable sources, raw logs and JUnit are under
build/test-refinement/1026541/st-2/. Its 15 independent cases detect source and
target filter removal; per-subject and unbounded mapping, identity and inventory
queries; loss of each required index role; empty-scope querying; and each split
snapshot after the second-batch callback runs. Formatting-only B-V1 fails the
old spelling assertion and passes the rewritten classifier.

The first matrix is retained but rejected because rapid source swaps reused
cached bytecode. The numbered rerun uses isolated per-run caches. Its initial
F6 mutation is also retained as an ineffective probe; the v4 supplement
bypasses the outer empty-key guard, reaches one empty-scope query and is
detected by both populations. The raw F1 fixture reproduces its known masked
pass; the corrected target-present/source-absent fixture detects the fault in
both populations.

The combined checkout passed nine focused tests in 1.19 seconds. The database
department passed 365 tests with 4,313 deselections in 30.67 seconds. Exact
commands and results are under st-2/final-verification/. Counts and runtimes are
diagnostic. Independent adversarial review passed all retained assertions,
role-specific probes and the final formatting-only revision. The final test
diff is 73 insertions and 89 deletions, a diagnostic net reduction of 16 lines.
All 123 fully protected files still match their frozen raw hashes. All eight
protected functions retain exact normalized source and AST identity, and the
owner inventory is unchanged; see st-2/final-protected-reconciliation.json
for the two ST-1 newline-only differences. ST-2 is complete. The user reviewed
this pause and then resumed ST-3 through ST-6. Earlier read-only ST-3 notes
remain in st-3/preparation.md.

## ST-3 outcome (2026-09-07)

ST-3 now uses one narrow constructor/authority helper for both public selection types. It preserves the exact shared `frozenset`, detached authority snapshots, immutable completion snapshots, sizes 1/4/16, replay order, unknown and duplicate rejection, replaced/deleted-index refusal, authority-error precedence, and the unchanged private-reader AST fence. Successful, duplicate and unknown lookup observations remain separate copied windows; behavioral operations execute before their mechanism assertions. Replaced-index type/content and deleted-index revalidation/snapshot are independent cases.

The independently reviewed v4 corpus under `build/test-refinement/1026541/st-3/` scopes all 18 mutations to an AST class/function owner, requires one exact owner-fragment match, confines every diff to that owner, and uses exact pytest parameter nodes. All 18 old and 18 rewritten selectors exited one with one failure at the selected node. Old C-F1/C-F2 detect their faults at the earlier mechanism counters, so they are not credited as behavioral-branch reach; rewritten C-F1/C-F2 reach the duplicate/unknown operations and fail their `raises` assertions. The attribution supplement records that distinction. Earlier manifests and runs remain preserved and noncredit after exposing unscoped-replacement and whole-module-attribution weaknesses.

The final focused run passed 42 tests in 1.58 seconds. The single core/verifier/workflows neighborhood passed 1,754 tests with one unchanged skip and 2,927 deselections in 52.79 seconds. Raw output, JUnit, commands, exits, interpreter identity and hashes are in `final-verification-01/`. The qualified product returned to frozen SHA-256 `cf1a58668b40f81fa754b82bbd7f482b61165e6e88856fb165ffb69e57512de6`; the protected reader and AST fence retain identical normalized function source. ST-6 can replay the scoped mutations against its final current test population through the archived v4 runner. Independent review approved the corrected corpus and execution; ST-3 is complete.
## Historical ST-0 recovery state (2026-09-07)

This section records the exact state at the prior stop, when no test code had
changed and no further implementation was authorized. The user has since
authorized the bounded ST-H prerequisite and work through ST-2; read-only ST-3
preparation remains for later. The useful recovery contents were reconstructed
on `milestone1-anthony` in `6c2dc6e` and independently confirmed superseded.
After reviewed ST-0 commit `728f21f`, the superseded recovery branch
`codex/wip-20260907-0015-test-refinement` was pruned. Its commit id `c79aead`
remains here for provenance; the recovery commit was not merged or cherry-picked.

At that stop, ST-0 was blocked and ST-1 through ST-6 were pending. No product
or test code had changed. The original complete baseline passed 4,670 tests
with four WinError 1314 capability skips; all 12 import contracts passed. A repeat unnecessarily
started for skip provenance then produced 4,668 passes, four skips and two setup
errors from one shared native-host fixture. The authorized focused rerun yielded
one pass and one failure: BR-G-30 lacked `off_thread_current_url_after_cancel`.
Both failed observations are retained; the original pass does not erase them.

| Observation | Consequence | Owner and common choke point |
| --- | --- | --- |
| Complete repeat, pytest-5347 | No initial native-live receipt before the 60-second scenario deadline; BR-G-30/31 setup errors | `_native_gate_child.py`: test-only delayed-return handler waits at most 10 seconds for navigation reinjection |
| Focused BR-G-30/31, pytest-5348 | Reinjection arrived 12.696 seconds after delayed-return dispatch; ready/final receipts existed but the delayed-handler measurement was absent | Same fixed reinjection wait; the page can finish after that handler failed |

This is one repeated harness synchronization mechanism with two consequences.
Underlying WebView/scheduler latency remains unclassified. No supported product
safety defect is evidenced. Do not patch the two symptoms separately, increase
deadlines, change production, or resume simplification without adjudicating the
shared test synchronization assumption. The issue is logged in BUGS.md.

The qualified isolated checkout is
`build/test-refinement/1026541/baseline/checkout`, at full-history commit
`10265417174e9e9e32b564e73f2527f34b3696d2`. It uses its own Python 3.13.14 venv,
editable installation and the explicit bundled Node executable. Exact commands,
versions/import origins and the initial complete/import passes are in
`baseline/evidence/00-commands.txt` through `06-lint-imports.txt`; the complete
repeat and skip reasons are in `07-pytest-skip-provenance.txt`. The focused
command, output, failed-run logs, receipt inventories and hashes are preserved
under `st-0/timeout-review`. These paths are relative to the artifact source root
`build/test-refinement/1026541/`.

Protected manifest v2 is `st-0/protected-inputs.json`, with append-only evidence
copy `baseline/evidence/12-protected-inputs-v2.json` and SHA-256
`8b17e9c22555a4c70bf668461b87edea316ae6feb16e6829c0ad531fdd70953d`.
It contains all 123 declared protected files, eight function identities and the
exact owner inventory. Root verification confirmed the complete declared path
set and every live Git blob identity. Raw hashes describe the isolated checkout;
13 live files have different newline bytes but identical Git content. Preserve
that distinction in any future reconciliation. Provisional v1 remains evidence
of the corrected manifest omission and is not the frozen authority.

Recovery is planned on `codex/wip-20260907-0015-test-refinement`, based on
1026541. Only this register and the new BUGS entry are task-owned recovery files.
Pre-existing dirty CHANGELOG, README and HANDOFF remain excluded and are
snapshotted under `st-0-inputs`. TEST_ABLATION was untracked at entry and is now
staged but preserved. That recovery commit was not a mergeable checkpoint; its
useful documentation had to be rebuilt into coherent commits after review. At
that stop, the next action required a separate bounded harness-synchronization
decision before ST-0 could be requalified.

## Common acceptance method

For each implementation checkpoint:

1. Characterize each affected guarantee and its current owner before editing,
   then run the focused control.
2. Before rewriting that checkpoint, freeze one immutable
   `build/test-refinement/1026541/<checkpoint>/probe-manifest.json`. For every
   declared probe it records the exact source mutation and hash, expected
   detector/node and verification tier, selected tests, expected exit, and
   artifact paths. Inject only into disposable source copies. A later manifest
   correction uses a new numbered directory and preserves the failed attempt.
3. Run unchanged-product controls and each injection against both the old and
   rewritten test population. Record that the injection reached the intended
   path.
4. Attribute each failure. Collection errors, missing private attributes,
   malformed fixtures, timeouts and unrelated earlier assertions do not count
   as behavioral detection. A static-policy failure counts only for its stated
   static-policy obligation.
5. Remove an assertion only when it is redundant, constrains spelling outside
   the retained contract, or has a verified same-level replacement. Preserve
   every unmatched assertion and all source-owner AST semantics.
6. Remove support made exclusive by the accepted simplification. Do not replace
   it with a larger generic parser, AST framework, browser harness or mutation
   framework. Case-count reduction is not itself an objective.
7. Pass focused and named broader verification, update applicable delivery
   evidence, obtain a context-independent adversarial review, and commit one
   atomic checkpoint.

Quantitative line, case and runtime figures are diagnostic measurements under
`DEFENSE.md` section 7. They are not coverage authority. Temporary artifacts
use append-only numbered run directories under
`build/test-refinement/1026541/<checkpoint>/`, with a manifest containing the
source identity, interpreter and Node identity, exact selections, injection
hashes, commands, exits, durations and result paths. Never overwrite a failed
run. At ST-0, write an immutable protected-input manifest with full-file SHA-256
hashes for production, dependency declarations, tools, the settlement oracle
and baseline, and every SH-G-8 protected artifact. Record separate source and
semantic hashes for the editable AST analyzer and exact expected owner
inventory; do not protect the whole editable test module. At ST-6, archive
driver sources and their SHA-256 manifest, retain evidence logs as ignored
build artifacts, and remove no unrelated build output.

## Family contracts and predeclared probes

### ST-1 — Source-owner AST guards

Simplify repeated fixture invocation and expected-result scaffolding into a
small named table. Preserve the analyzer algorithm, complete package scan,
exact owner-and-scope inventory, call-site multiplicity, alias/rebinding and
star-import findings. The guard remains the explicit `CORE.md` owner of
accidental direct-`FailureDetail` construction drift.

The frozen fixture corpus covers direct, qualified and relative imports;
annotated and transitive aliases; nested functions, async functions, classes
and lambdas; decorators, defaults and annotations. The finite families are:
`A-F1` add a construction, `A-F2` remove one, `A-F3` duplicate one,
`A-F4` move one to another scope, `A-F5` introduce an alias, `A-F6`
introduce a star import, and `A-F7` rename an approved helper. Each must
change its count, owner/scope or prohibited-import result. `A-V1` changes only
whitespace/comments and `A-V2` only quotation; both preserve the full analyzer
result. Runtime exception-lifetime tests are consumers, not replacements.

### ST-2 — Repository SQL checks

Consolidate repeated repository setup and query classification across Appendix
A's seven database tests. Remove dependencies on incidental SQL whitespace,
aliases and verbose plan text only where scoped observations retain the same
requirement. Preserve ordered complete results, the 400-subject bound, required
index use, empty-target behavior, current source and target identity filtering,
alias disqualification, no irrelevant-history materialization, and one read
snapshot across batches.

Keep the existing 801- and 1,001-subject axes. The finite families are:
`B-F1` remove source filtering, `B-F2` remove target filtering, `B-F3`
introduce per-path querying, `B-F4` introduce one unbounded query, `B-F5`
prevent required index use, `B-F6` query an empty scope, and `B-F7` split
the read snapshot. Each must fail its named filter/result, work-bound, index,
empty-scope or snapshot detector. The source/target fixture leaves a target
identity present while its source identity is absent. Concurrent-write probes
count only when their callback runs across a batch boundary. `B-V1` changes
only incidental SQL formatting at a rewritten assertion site and must pass.

### ST-3 — Integrity selection

Consolidate construction and authority-validation setup across both public
selection types. Preserve constructor snapshot contents and identity, detached
candidates and attestations, immutable completion snapshots, successful
completion, unknown-ID and duplicate rejection, replaced/deleted private-index
refusal, the shared exact `frozenset`, completion replay order and no-copy/
no-rescan contract. Keep the private-reader AST fence. A mechanism assertion
must not prevent the paired behavioral assertion from executing.

The finite families are: `C-F1` remove duplicate rejection, `C-F2` admit an
unknown ID, `C-F3` copy the construction-admitted index, `C-F4` rescan
tuples, `C-F5` replace the private index, `C-F6` delete it, and `C-F7`
reverse authority-error precedence. Run every applicable fault for both
selection types and retain the existing lookup-size axis. Each must fail its
corresponding behavioral or mechanism detector.

### ST-4 — Visual contracts

Use existing token/rule helpers and compact, independently authored expected
tables to consolidate palette, semantic-channel and control-state checks.
Preserve the four excluded provenance/raw-color/icon-foundation tests named in
Appendix A, plus semantic mappings, forced-colors behavior, non-color cues,
control states, stylesheet order, reduced motion, dialog closing and
nonanimated virtual-row lifecycle. Do not add a CSS parser or globally
normalize selectors, strings or nested media blocks.

The finite families are: `D-F1` introduce a wrong semantic mapping, `D-F2`
remove a forced-color override, `D-F3` remove a non-color cue, `D-F4`
reorder stylesheets, `D-F5` break reduced-motion behavior, `D-F6` break the
dialog-closing rule, and `D-F7` animate virtual rows. Each needs an ordinary
detector. `D-V1` changes formatting only at a rewritten incidental assertion
site and must pass while preserving selector/media scope. Headed evidence is
corroboration, never the replacement for an ordinary detector.

### ST-5 — Headed-harness spelling

Within Appendix A's ten functions, remove source-string assertions only when
an existing ordinary behavioral witness catches the same fault. Reuse current
picker/native-call fakes, immutable command composition and recorder/reader
tests. Preserve AST patch allowlists, forbidden native-input/foreground API
guards, real media/scenario mappings, installed-source and production-stack
fidelity, and pre-ready privacy assertions embedded in these tests.

The finite families are: `E-F1` admit an invalid picker target, `E-F2`
post through the wrong native path, `E-F3` delegate another native call
incorrectly, `E-F4` make command composition mutable, `E-F5` allow a
collision, `E-F6` disclose private text before readiness, `E-F7` disclose it
after readiness, `E-F8` omit scenario/media coverage, `E-F9` lose deadline
or cleanup behavior, and `E-F10` publish an invalid milestone. Each must fail
an existing same-level owner before its spelling assertion is removed. `E-V1`
changes only quotation/comments at the proposed removed assertion and preserves
the Python AST. Fake-native coverage cannot justify removing global
forbidden-API guards; the two privacy branches remain separate.

## Incident, deferral and escalation register

| Class | Required disposition |
| --- | --- |
| Rewritten test fails against unchanged product | Diagnose against the old test and stated contract; correct a test defect inside the checkpoint. Do not weaken the guarantee, add a skip or regenerate authority. |
| Rewritten test exposes a credible latent product defect | Preserve a minimal reproducer and exact evidence, log and report the defect, and do not fix production in this pass. If the defect prevents the checkpoint guarantee, stop that checkpoint for adjudication. |
| Product simplification opportunity | Record owner, proposed seam and affected guarantees for future work; do not change production here. |
| First bounded pre-existing test defect | A separate test-only fix commit is permitted only inside Appendix A and only when necessary to preserve a named detector; otherwise log and defer it. |
| Second unplanned instance of one mechanism, or third substantive defect in a checkpoint/pass | Finish only the current safety-preserving atomic outcome; start no further fix. Produce a consequence/owner/common-choke-point table and obtain review before resuming. |
| Checkpoint cannot preserve a declared detector | Retain the original check and report that simplification as unresolved; do not redefine the checkpoint. |
| Hard-wall consequence or inability to preserve/recover work | Apply `AGENTS.md` mandatory stop and recovery rules immediately. |

Repeated similar reports must be analyzed as an upstream fixture, helper,
contract-boundary or product-seam weakness before further local fixes. Findings
do not expand this register.

## ST-6 closure

Replay every declared fault against the combined rewritten suite so no detector
removed by a later checkpoint is credited. Run the complete suite, ordinary
suite and import contracts in the qualified checkout. Reconcile production,
dependencies, settlement oracle/baseline and all protected artifacts byte-for-
byte with ST-0. Account for removed functions, helpers, fixtures, imports and
constants, and separately report support that remains necessary.

Review the combined diff for weakened expectations, added skips, shared wrong
expectations, hidden verification-tier moves, scope expansion and needless new
abstractions. The headed corroboration selection is exactly
`pytest -q --dept interfaces -o "addopts=" -m headed`; its success is never
credited as the detector for an ordinary assertion. Update this register, the ablation disposition, `CHANGELOG.md` and
the latest `HANDOFF.md` only at closeout, while preserving and incorporating
the pre-existing study edits deliberately. The final commit is documentation-
only after the atomic ST-1 through ST-5 commits.

## Protected-input manifest

ST-0 writes
`build/test-refinement/1026541/st-0/protected-inputs.json`. It expands and
sorts every tracked path returned by `git ls-files namisync tools
pyproject.toml`, then adds these protected tests explicitly:

- `tests/bridge_transport_custody.py`
- `tests/interfaces/web/_bridge_transport_custody.py`
- `tests/interfaces/web/_bridge_retained_memory.py`
- `tests/interfaces/web/sh_g_8_transport_calibration.json`
- `tests/interfaces/web/sh_g_8_transport_ceiling.json`
- `tests/interfaces/web/sh_g_8_transport_holdout.json`
- `tests/interfaces/web/test_bridge_transport_custody.py`
- `tests/interfaces/web/test_bridge_transport_custody_holdout.py`
- `tests/interfaces/web/test_bridge_transport_custody_live.py`
- `tests/test_tools_executor_settlement_audit.py`

The tools selection includes the separately reported protected oracle
`tools/executor_settlement_audit.py` and baseline
`tools/executor_settlement_baseline.json`. Each manifest row contains the
repository-relative path, Git blob ID and SHA-256. The manifest also contains
the HEAD and tree IDs, `pyproject.toml` dependency hash, and sorted path-list
hash. ST-6 requires the same protected path set, file/blob/content hashes and
function hashes. The current HEAD/tree are recorded separately as provenance;
they necessarily change as the approved test commits land.

Because ST-1 edits its containing test module, ST-0 separately records source
and AST-normalized semantic hashes for `_failure_detail_policy` and the exact
owner-inventory literal asserted by
`test_direct_failure_detail_construction_has_exact_static_owners`. ST-1 must
preserve both semantic hashes while allowing only the planned surrounding
fixture/presentation changes. The same source and semantic identity record
covers `_known_item_index_reads`, its private-reader guard, and the four
protected visual-consumer functions listed in Appendix A. Shared helper changes
still require behavioral review; unchanged function text alone is not proof
that a consumer retains its meaning.

The pre-existing study-document snapshots are already preserved under
`build/test-refinement/1026541/st-0-inputs/`; these copies prevent closeout
from confusing prior study edits with this delivery.

## Appendix A — Exact initial population

The names below are copied from
`build/test-ablation/cab2259/cohorts.json`. Cohort F is deliberately excluded.

### A — source-owner checks

`tests/core/test_exception_graph.py`

- `test_failure_detail_call_guard_detects_import_and_assignment_aliases`
- `test_direct_failure_detail_construction_has_exact_static_owners`

### B — repository SQL checks

`tests/test_db_repositories.py`

- `test_current_mapping_queries_use_target_and_identity_indexes`
- `test_current_mapping_read_chunks_keys_and_identities_at_four_hundred`
- `test_current_mapping_read_ignores_large_irrelevant_history_and_keeps_pair_order`
- `test_current_mapping_read_skips_pair_query_for_an_empty_target_scope`
- `test_large_inventory_selection_uses_bounded_queries`
- `test_current_mapping_read_uses_one_snapshot_across_query_batches` (related snapshot test added by the accepted plan)
- `test_large_inventory_selection_is_one_read_snapshot` (related snapshot test added by the accepted plan)

### C — integrity private-index checks

`tests/core/test_integrity.py`

- `test_selection_completion_uses_one_index_lookup_without_tuple_scan`
- `test_selection_exposes_its_construction_admitted_item_ids`
- `test_known_item_index_has_no_reader_outside_its_core_contract`
- `test_selection_revalidation_rejects_a_replaced_known_id_index`
- `test_selection_authority_reports_changed_item_before_derived_index`
- `test_selection_authority_rejects_a_deleted_known_id_index`

### D — visual checks

`tests/interfaces/web/test_motion.py`

- `test_sh_g_13_motion_tokens_and_reduced_motion_override_are_owned`
- `test_sh_g_13_disclosure_and_dialog_use_css_motion_with_real_exit`
- `test_sh_g_13_no_motion_is_bound_to_virtualized_row_lifecycle`

`tests/interfaces/web/test_design_tokens.py`

- `test_sh_g_11_tokens_route_authored_lights_only_to_new_semantic_roles`
- `test_sh_g_11_channel_semantic_aliases_are_complete_and_disjoint`
- `test_sh_g_11_channel_mappings_use_theme_secondary_badges`
- `test_sh_g_11_forced_colors_replaces_semantics_with_system_colors`
- `test_sh_g_11_channel_selectors_keep_hue_and_form_semantics_scoped`
- `test_sh_g_11_components_cover_controls_states_and_non_color_cues`
- `test_sh_g_11_solid_controls_and_operation_filters_follow_tuned_states`
- `test_sh_g_11_shipped_page_loads_tokens_components_then_layout`

The following tests in `test_design_tokens.py` remain protected consumers and
are expressly outside the cleanup population:

- `test_sh_g_11_fluent_table_matches_pinned_source_transcription`
- `test_sh_g_11_only_tokens_owns_raw_colors_and_palette_consumption`
- `test_sh_g_11_raw_color_scanner_catches_literal_and_mixed_css_escapes`
- `test_sh_g_11_icon_foundation_uses_shared_sizes_and_fixed_local_masks`

### E — headed-harness spelling checks

- `tests/interfaces/web/test_shell_headed.py::test_shell_gate_child_preserves_the_production_stack_and_is_bounded`
- `tests/interfaces/web/test_component_gallery_headed.py::test_component_gallery_script_declares_exact_required_matrix`
- `tests/interfaces/web/test_component_gallery_headed.py::test_component_gallery_media_modes_are_exact_and_scenario_bounded`
- `tests/interfaces/web/test_materials_headed.py::test_materials_gate_child_is_test_owned_and_preserves_production_stack`
- `tests/interfaces/web/test_materials_headed.py::test_materials_gate_report_and_page_probe_are_bounded_and_sanitized`
- `tests/interfaces/web/test_materials_headed.py::test_materials_gate_faults_are_exact_and_delegate_other_native_calls`
- `tests/interfaces/web/test_transport_headed.py::test_transport_gate_uses_shared_immutable_command_composition`
- `tests/interfaces/web/test_transport_headed.py::test_transport_gate_native_picker_automation_is_exact_and_fail_closed`
- `tests/interfaces/web/test_native_host_gates.py::test_native_host_gate_page_keeps_the_probe_in_inert_page_data`
- `tests/interfaces/web/test_headed_evidence.py::test_headed_evidence_protocol_stays_test_only_and_owns_milestone_paths`
