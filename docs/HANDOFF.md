# Latest session — oracle v2 and verification-first sequencing

2026-09-28, `milestone1-adelbert`, starting from `85ceecea`. The user reviewed the
settlement oracle's fitness for the root admission refactor, chose oracle format
v2, and requested plan updates plus a commit. This delivery contains
documentation only; implementation remains unauthorized. M1_PLAN is the sole
scope/decision/register owner; all nine rows remain pending.

Findings behind the revision:

- `TracingFileSystem` records every public `ExecutorFileSystem` call with its
  arguments and results. The pinned v1 baseline therefore freezes probe
  multiplicity: 1,155 `revalidate_root`, 527 `resolve`, 352 `stat` and 305
  `stat_path` entries, plus their `fs:` timeline tokens and first-seen label
  ordinals. Runtime-level probe consolidation cannot pass it unchanged.
- The tracer wraps only the outer object, so native-internal changes are
  invisible to it. RO-1a and RO-3a keep the byte layer identical; RO-3b does not.
- Independent oracle expectations reference only effect tokens and effect counts,
  so v2 can drop successful probes without touching them.
- `second_settlement_probe` matches by occurrence count; removing an earlier
  probe would silently retarget it.
- Oracle plans carry no volume id or evidence, so only chain-only admission runs
  there. Root-swap witnesses exist only as name-hooked spy subclasses in
  `tests/test_executor_runtime.py`.
- Production plans lack volume facts only for offline scans, whose `UNKNOWN`
  profile is already continuity-ineligible.

Plan changes: decision 8 records v2 (effects, errors, fault-injected calls and
collaborator tokens stay pinned; successful probes move to diagnostics; labels
are canonicalized after projection; there is a reviewed probe list and a
guard-before-effect invariant) and the user's one-time EXECUTOR override. RO-0a
(oracle v2) and RO-0b (production-shaped root-swap sweep, preflight/verifier
differentials, baseline checkout) land first against the unchanged product. RO-3
splits into RO-3a and RO-3b. Decision 4 makes plans without reviewed volume
facts ineligible for continuity. RO-1b flips only the same-object alias sweep
expectation.

Checks this session: read-only source inspection of the audit tool, baseline,
fault rules, expectations, native `trash_destination` and scanner offline
results; `git diff --check` and heading/row-reference consistency on M1_PLAN.
No product tests, oracle runs, benchmarks or fixtures ran. The previous planning
evidence remains under `build/root-admission-plan-20260927/`, with the
investigation receipts under `build/executor-assessment-20260927/`.

Next action after user review: separate implementation authorization, a fresh
starting suite and oracle run, then RO-0a and RO-0b. The v1 baseline stays
untouched until RO-0a's projection proof. Preserve DOC-2, prior incident/AB
evidence, stashes and unrelated work. No push or merge was requested.
