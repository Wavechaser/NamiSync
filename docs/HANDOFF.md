# NamiSync Session Handoff

Date: 2026-07-25

## Session Outcome

M1 Stages 1 through 5 are complete on `milestone1`. This session finished the
shared facade and CLI on top of:

- Stage 5 Track A facade extraction:
  `4db4a4741197c96ce686d0ef40c7f1a6f785cc35`
- Track A compatibility correction:
  `89c6351778864389e3abc2b2b67539f8e2331b33`
- Stage 4 compound execute/verify base:
  `6414e9f0966c575f541a9e2433146148c130c050`

The final Stage 5 release adds the four standalone location commands, final
typed result classification and exits, mode-aware integrity admission,
semantic-settings access and immutable plan snapshots, complete primitive
views, and production entry-point coverage. Stage 6 remains unimplemented.

No database schema, version, contract marker, migration, or reset behavior
changed. Ledger v2 and history v3 remain the final M1 database boundary.

## Commands And Exit Contract

The production CLI now exposes:

```text
nami-sync sync SOURCE TARGET [--deletion-policy trash|additive]
               [--verify-after-copy] [--database PATH]
               [--history-database PATH]
nami-sync history [RUN] [--limit N] [--history-database PATH]
nami-sync inventory ROOT|--location-id ID [--path PATH]... [--mount MOUNT]
                    [--database PATH] [--history-database PATH]
nami-sync baseline ROOT|--location-id ID [--path PATH]... [--mount MOUNT]
                   [--database PATH] [--history-database PATH]
nami-sync verify ROOT|--location-id ID [--path PATH]... [--mount MOUNT]
                 [--database PATH] [--history-database PATH]
nami-sync rebaseline ROOT|--location-id ID --path PATH [--path PATH]...
                     --accept-current-evidence [--mount MOUNT]
                     [--database PATH] [--history-database PATH]
```

`ROOT` and `--location-id` are mutually exclusive and exactly one is required.
A numeric positional root remains a root; it is never guessed to be a retained
ID. `--mount` is an explicit mount selection and is required to choose among
ambiguous candidates; a noncandidate value is refused.
`rebaseline` always requires a selected scope and explicit acceptance of the
current bytes.

Final headline precedence is:

```text
failed > partial > refused > mismatch > canceled
       > verification-incomplete > degraded > all-noop > success
```

The CLI derives numeric status only from that typed headline:

| Exit | Meaning |
| ---: | --- |
| 0 | `success` or `all-noop` |
| 2 | usage, path, location-binding, or database/settings configuration error |
| 3 | `refused` |
| 4 | `failed` |
| 5 | `canceled` |
| 6 | `partial` |
| 7 | recording or audit `degraded` |
| 8 | integrity `mismatch` |
| 9 | `verification-incomplete` |

Filesystem, integrity, ledger-recording, and audit axes remain independently
renderable even when a higher headline wins. Mixed operation/integrity items
and compound phase summaries preserve producer order. The CLI does not
reconstruct domain objects, parse diagnostics, or dispatch by attribute shape.

## Facade And Lifecycle

`NamiSyncService` is the sole production composition root for CLI and future
web/desktop adapters:

```python
NamiSyncService(
    ledger_path,
    history_path,
    *,
    settings_path=None,
)

service.start_plan(source, target, *, deletion_policy=None)
service.start_execution(request_id, *, verify_after_execute=False)
service.start_inventory(
    *, root_path=None, location_id=None, selected_paths=(), selected_mount=None
)
service.start_baseline(
    *, root_path=None, location_id=None, selected_paths=(), selected_mount=None
)
service.start_verify(
    *, root_path=None, location_id=None, selected_paths=(), selected_mount=None
)
service.start_rebaseline(
    *, root_path=None, location_id=None, selected_paths=(), selected_mount=None
)
service.read_semantic_settings()
service.commit_semantic_settings(patch)
```

The facade exposes only primitive frozen views, IDs, strings, integers,
booleans, tuples, and nullable values. It imports neither `core`, `modules`,
nor `db`; adapters import the service rather than each other. Location
resolution happens during dispatcher preparation before admission. The five
visible states are `resolved`, `offline`, `ambiguous`, `root_missing`, and
`root_unavailable`, with candidate mounts and actionable retry guidance that
do not claim a provisional mount was selected.

Track A lifecycle invariants remain intact: dispatcher shutdown precedes
runtime close on success, failure, or interrupt; observation uses a blocking
stream with get-before-subscribe terminal-race recovery; Gap replacement
does not duplicate reliable sequence numbers; every opened stream is retained
and closed before its worker is joined; unsubscribe and close are idempotent;
sink failures return to the waiting CLI thread; and shutdown is bounded without
self-join deadlocks. Public observation remains sink-only.

Named `save_plan`, `get_plan`, and `drop_plan` forward to the existing
process-local dictionary. They are not a durable `PlanStore` contract.

## Semantic Settings

`LocalWorkflowRuntime` owns `SemanticSettingsStore`; the service never imports
the database layer. Unless an explicit `settings_path` is supplied to the
service/runtime, settings live at `settings.json` beside the selected ledger.
Therefore a CLI `--database` override automatically uses its sibling settings
file; `--history-database` remains an independent override. Ledger, history,
and settings paths must be distinct, and settings cannot live inside a managed
sync root.

With no settings file, the semantic defaults are:

- no filter patterns;
- deletion policy `trash`;
- trash-on-update enabled;
- preserve ADS disabled, creation time enabled, ACL disabled; and
- source-casing propagation disabled.

The primitive full view and all-optional patch validate at construction:
filters must be a tuple of strings, booleans must be exact `bool` values,
deletion is only `trash` or `additive`, and preservation must be the matching
primitive view. Invalid input is rejected before the atomic store commit and
cannot create or corrupt `settings.json`. Partial commits preserve untouched
keys under the existing named-mutex store. There is intentionally no settings
CLI command in M1.

Planning reads exactly one settings snapshot. Omitting
`--deletion-policy` uses every stored semantic default; an explicit `trash` or
`additive` replaces only deletion for that plan and never commits settings.
Review renders the captured filters, deletion, trash-on-update, preservation,
and casing values. Commit and execution use that immutable plan snapshot and
never reread live settings, even if every stored field changes afterward.
Malformed settings refuse planning before dispatcher submission.

## Inventory And Integrity Semantics

Every standalone command performs fresh location binding before session
admission. Inventory refreshes the requested full or exact selected scope and
records role-free location truth. Both database overrides reach the same
runtime, dispatcher, workflows, history observer, and retained inventory.

When a new integrity selection is frozen:

- `baseline` admits eligible non-directory rows only when no attestation
  exists. A repeat full baseline still refreshes and records inventory but
  hashes and records zero integrity attestations, yielding a clean no-work
  success.
- `rebaseline` admits only rows that already have an attestation and the CLI
  requires an explicit selected scope plus `--accept-current-evidence`.
- `verify` admits both attested and unattested rows. Unattested rows receive
  initial evidence and make the run `verification-incomplete`, rather than
  being silently reported as verified.

Once a selection has `selection_item_ids`, resume uses that immutable ordered
set without reapplying the fresh-mode filters. Completed IDs, completed bytes,
processed bytes, and plan order survive evidence changes between attempts.

## Verification And Adversarial Evidence

- Full suite: `699 passed in 22.39s`; no skips reported.
- Focused Stage 5 service/CLI/classification/settings/inventory suite:
  `121 passed in 7.18s`.
- Original CLI E2E gate: `13 passed` unchanged.
- New real-entry-point gate: both `python -m namisync` and
  `nami-sync.exe` ran `inventory`, `baseline`, `rebaseline`, and `verify`;
  `1 passed` covering eight subprocess command runs.
- Import Linter: 48 files, 175 dependencies, 8 contracts kept, 0 broken.
- `python -m compileall -q namisync tests`: clean.
- `git diff --check`: no whitespace errors; only expected LF-to-CRLF notices.

The literal XV-10 matrix removes each higher adjacent condition and proves the
headline flips to the lower one. It also pins the all-noop/success fallback,
compound partial+mismatch+both degradation axes, headline-only CLI numeric
mapping, and zero-byte `RAN` versus `UNRUN`. XV-11 creates, reviews, and commits
a plan from stored defaults, changes every semantic setting, executes, and
proves the original full snapshot still controls behavior. Static coverage
also proves execution and preflight do not import or read settings.

Separate adversarial review found and fixed:

- queued/wakeup location errors that omitted five-state recovery guidance;
- provisional ambiguous and unmounted values exposed as selected mounts;
- plan review that did not expose the complete captured semantic snapshot;
- heterogeneous result rendering that grouped and reordered item types;
- recording-degradation guidance that incorrectly prescribed a rescan;
- permissive primitive settings values that could write an unreadable file;
- service-constructor path-alias errors escaping as CLI tracebacks; and
- missing regressions for sink self-unsubscribe, retained primitive history,
  audit-only degradation, override isolation, and primitive JSON surfaces.

Release mutations proved the tests fail if either baseline/rebaseline filter is
removed, frozen-resume bypass is removed, numeric positional input is guessed
as an ID, admission precedes resolution, candidate or provisional mount
projection lies, mixed items are reordered, or a degradation axis is
suppressed. A separate positive VERIFY regression pins unattested rows as
baselined plus verification-incomplete. Every mutation was restored and its
target passed afterward.

Static release checks found no interface import of `core`, `modules`, or `db`;
no workflow SQL; no `worker_count`; no live-settings read in executor,
preflight, or execution workflow; and no Stage 6 implementation. The sole
concrete production `xxhash` import remains
`namisync/workflows/runtime.py`. No `db/`, schema, payload-version,
contract-marker, migration, or reset file changed in Stage 5.

## Immediate Next Context

1. M1 is ready for Stage 6, the headed local desktop/web adapter and bridge
   security spike. Stage 6 must consume only `NamiSyncService` and primitive
   views; it must not import `core`, `modules`, `db`, CLI internals, or
   duplicate workflow classification and location policy.
2. Preserve mandatory sync review and exact-plan confirmation. Do not add a
   one-shot sync shortcut, infer a location from another argument, or make
   rebaseline implicit.
3. The dispatcher session store, named plan dictionary, and strict workflow
   payload v3 are process-local only. Pause/resume survives within the current
   service process, not an application restart. Do not advertise durable
   restart resume without a separately designed persistence boundary.
4. `settings.json` is durable semantic configuration, but Stage 6 must use the
   primitive read/partial-commit facade rather than the database-owned store or
   types. UI-only state and bridge protocol state remain separate future
   concerns.
5. Pre-switch development databases must still be reset together: close
   NamiSync, delete or explicitly reset both the ledger and history database
   files, then rerun. Do not migrate/backfill one database, change the frozen
   markers, bump a schema, or add a second M1 reset.
6. Hidden `mirror` deletion, general migrations, backups, retention policy,
   settings CLI, Stage 6 authorization/origin/CSRF handling, and durable plan
   resume remain outside this completed stage.
