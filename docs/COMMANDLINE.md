# Command-Line Interface

Status: reviewed `sync`, retained `history`, and M1 location-centric
`inventory`/`baseline`/`verify`/`rebaseline` are implemented through the shared
interface service. Optional execute-to-verify, final typed result
classification, explicit location binding, and isolated ledger/history
overrides are active. Queue release and machine-readable output remain
deferred.

## Entry Points

`nami-sync` and `python -m namisync` execute the same `main()` and read real
`sys.argv[1:]` when no explicit test argument is supplied. Tests exercise both
real process entry points. No command is reachable only through injected argv.
Before parser construction, the CLI bounds the complete argument vector to
65,536 UTF-8 bytes, including one separator byte between arguments. Non-string
or non-UTF-8 arguments and a first-excess vector receive the same non-reflecting
usage refusal; no rejected argument content enters parser diagnostics.
The CLI delegates process composition, session observation, and typed result
classification to `interfaces/service.py`; it does not construct a dispatcher
or workflow runtime.

No-subcommand `nami-sync` and `python -m namisync` print usage, point to
`nami-sync-gui`, and exit nonzero. Nothing runs implicitly. `nami-sync-gui` is
the GUI-subsystem launcher for the sole
desktop implementation and retains no console window.

## Commands

### M0

- `nami-sync sync SOURCE TARGET`: run the plan session, render complete review,
  collect explicit commitment between sessions, then submit execution and render
  item/summary results.
- `nami-sync history [RUN]`: list retained run summaries or render one summary
  and stream its typed item detail in bounded database pages.

Recent-run listings include blocked/deferred exception counts and history
duplicate/rejected receipt counts, so a filesystem-completed safe subset or a
degraded audit is not mistaken for a clean full sync; run detail shows each
canonical item path and reason.

`sync` accepts a one-plan `--deletion-policy trash|additive` override,
`--verify-after-copy`, `--database PATH`, and `--history-database PATH`.
Omitting deletion policy uses the complete saved semantic snapshot; an
explicit override replaces only that plan's deletion policy and does not
change its filters, trash-on-update, preservation, or casing settings.
`--verify-after-copy` keeps successfully published copy/update/move-update
files under the same session and volume custody for immediate readback.
`history` accepts `--limit N` for `1..256` summaries and
`--history-database PATH`. For `sync`, both
database files must be distinct and outside the managed roots; defaults are
the local
`%LOCALAPPDATA%\NamiSync\ledger.db` and
`%LOCALAPPDATA%\NamiSync\history.db`.
Semantic defaults live in `settings.json` beside the selected ledger, so an
explicit `--database` also selects an isolated sibling settings file.

At the active Stage 6 database cutover, mutating commands require the
coordinated database pair. Standalone history remains deliberately read-only
and may inspect one exact history-v7 database without a ledger peer. CLI history
summary/detail output renders a persisted review-fact limit as typed durable
history truth, gives the same narrow-roots or resolve-scan/preflight guidance
as the desktop, and never reconstructs the refusal from diagnostic text or
shows a presentation-only omission as history. `DATABASE.md` and `HISTORY.md`
own the persisted consequence; `BRIDGE.md` owns the shared protocol shape
and `DEFENSE.md` §1.3 owns the scalar wall.

At the current M1 pre-migrator boundary, ledger v4 and receipt-aware history v7
require their exact contract markers. Opening any ledger v1-v3 database, any
history v1-v6 database, or a current-version file with a missing/mismatched
marker fails
before schema mutation with an instruction to close NamiSync and manually
archive or delete **both** local database mains and all SQLite sidecars, then
rerun the command. Startup does not
delete, migrate, or backfill either database automatically. This is
development-state recovery, not a migration or preservation promise.

Before the first sync or location command admission, the CLI calls the shared
read-only database-pair preflight. A refused pair returns exit `3`, prints the
coordinated reset direction, and leaves every existing main and sidecar byte
unchanged. A fresh sync pair remains absent through planning and declined
review, then is initialized together only after explicit execution commitment.
Inventory and integrity initialize a fresh pair during workflow preparation,
before their audit observer can open history. The standalone `history` command
is read-only and deliberately exempt, so an existing history database remains
inspectable when its ledger peer is missing.

History listing reads summary rows without decoding event detail. `history RUN`
prints terminal axes when finalized or an explicit incomplete state/phase and
committed watermark when no terminal row exists, then requests
item pages of at most 256 rows through the summary's fixed item-count watermark.
Detail memory remains page-bounded, and an incomplete history row does not
claim that filesystem execution can resume.

Live event-v5 terminal summaries carry no item array. After a healthy sync or
integrity terminal, the CLI therefore reads the same fixed finalized item
watermark for canonical itemized output; if audit is degraded it uses only the
item events actually observed live.

For noninteractive use, mandatory review cannot be waived by a casual `--yes`.
The command surface may expose a separate queue-release flag that executes only
already committed sets. A commitment binds plan fingerprint plus exact selection
digest; no flag combination plans and executes in one unreviewed invocation.

### M1 Location And Integrity Commands

All four commands require exactly one location selector: positional `ROOT` or
`--location-id ID`. A numeric positional value remains a path; only the named
option denotes a retained location id. They accept repeatable
`--path RELATIVE_PATH` values as an exact root-relative selected scope,
`--mount MOUNT` to resolve one candidate from an ambiguous cloned-volume
identity, and both `--database PATH` and `--history-database PATH`.

- `inventory [ROOT | --location-id ID]`: refresh and print role-free inventory,
  its derived `unverified`/`verified`/`modified`/`mismatched` state,
  plus zero/one/many mapping guidance.
- `baseline [ROOT | --location-id ID]`: refresh inventory and create evidence
  only for eligible non-directory rows that do not already have an
  attestation.
- `verify [ROOT | --location-id ID]`: refresh and compare eligible rows with
  retained evidence. A row without evidence is baselined but receives the
  verification-incomplete exit because no comparison occurred.
- `rebaseline [ROOT | --location-id ID] --path RELATIVE_PATH
  --accept-current-evidence`: accept current evidence only for explicitly
  selected eligible rows that already have an attestation. At least one
  `--path` and the intent flag are mandatory.

Those are the current admission rules. The accepted but unrealized change also
admits explicitly selected eligible files without evidence to rebaseline, using
the same flags and confirmation. It always hashes and conditionally replaces or
creates evidence, even for matching content; verification freshness is cleared
rather than advanced. See the
[accepted three-operation policy](VERIFIER.md#accepted-standalone-operation-policy).

Omitting `--path` means full-location scope for inventory, baseline, and verify.
Paths are exact values, not globs. Location resolution distinguishes resolved,
offline, ambiguous, missing-root, and unavailable-root states before dispatcher
admission. Offline/missing/unavailable refusals explain the corrective action
and perform no missing reconciliation; ambiguity prints candidates for an
explicit `--mount` retry. A selected location is never inferred from another
argument or a mapping role.

## Review Rendering

Print roots/volume evidence, policy, filter/policy snapshot, operation counts and
content bytes, runnable/blocked/deferred selection counts, per-item exclusion
reasons, required/free capacity for the selected subset, trash behavior,
computed ingest destinations when applicable, and a stable plan fingerprint.
The semantic snapshot is the one frozen into this plan: filters,
trash-on-update, all preservation booleans, and source-casing propagation remain
reviewable even if saved defaults change later.
Rename-shaped operations render the observed prior target path on the left and
the planned target path on the right. This makes a case-only `recase` visible as
`keep.txt -> KEEP.txt` and also exposes the actual old-to-new path for `move`
and `move_update` review rows.
Commitment occurs only after the plan session has terminated and released
custody. Execution output discloses fresh-preflight refusal/material drift.
When an effective `update` will overwrite target bytes while trash-on-update is
disabled, review prints the exact count and an irreversible-risk warning. The
typed `execute` response acknowledges that same reviewed risk and is forwarded
as the service's destructive acknowledgement; no implicit or `--yes` bypass is
available.
Successful safe-subset execution says `completed with exceptions`, itemizes the
blocked/deferred paths, and tells the user to resolve them and re-plan.

## Output And Exit Status

Human output goes to stdout/stderr with actionable reasons and no ambiguous
green-success wording. A future machine format is versioned and writes progress
separately from the final structured result.

Implemented exit categories:

| Code | Meaning |
| ---: | --- |
| `0` | success, including declined review and explicit no-op |
| `2` | usage, path, or configuration input error |
| `3` | commitment or fresh-preflight refusal with no managed-data mutation |
| `4` | planning/execution/runtime failure |
| `5` | cooperative cancellation |
| `6` | selected safe work completed, but blocked or deferred items remain |
| `7` | degraded ledger or audit durability |
| `8` | integrity mismatch |
| `9` | verification incomplete (including modified, missing, unsupported, error, or newly baselined during verify) |

One workflow-owned headline determines the numeric exit with this exact
precedence:
`failed > partial > refused > mismatch > canceled >
verification-incomplete > recording/audit degradation > all-noop > success`.
The filesystem, integrity, recording, audit, disposition, and cancellation
values remain printed even when a higher-priority headline supplies the exit.

`OperationResult.recording` and `.audit` independently carry
`RecordingStatus.OK|DEGRADED`, so CLI can identify which store is behind without
parsing diagnostics. `Disposition` distinguishes refused/discarded unrun work
from an activity that ran but transferred zero bytes.

Exit status derives from typed result, not log text or byte count.
Ledger degradation tells the user to fix ledger path/access and rerun the
activity; an inventory-only rescan is not presented as evidence repair.

Terminal session cleanup is best-effort and never rewrites an already-settled
workflow result or its exit classification. A timeout says that terminal
result and history outcome are already settled, identifies cleanup as the only
pending work, and notes that final service shutdown will retry. Unexpected
per-session cleanup errors are printed rather than swallowed. Every command
inspects final service shutdown; an incomplete shutdown prints the unfinished
session ids and whether resource custody remains held while preserving the
command's domain result.

## Concurrency And Control

Mutating commands submit to dispatcher and obey cross-process physical-volume
custody. Read-only history can run with GUI or other sessions. Interactive
Ctrl+C requests cooperative cancel, continues rendering terminal cleanup, and
exits only after custody/result state is known. A second interrupt may follow
an explicit hard-abort policy but never reports clean cancellation prematurely.

## Safety

Paths are ordinary arguments, never interpolated into a shell. Output escapes
control characters. Runtime validation names missing/nonexistent/unusable paths
and the corrective action. Mirror deletion is not exposed. Database defaults
remain local and outside managed roots.

## Expectations Of Other Modules

- Dispatcher supplies admission, control, state, and events; CLI does not start
  modules directly.
- Workflow adapters own plan/inventory/integrity/history sequencing.
- Typed results supply exit classification and reason codes; CLI does not parse
  log strings.
- Database/history overrides are passed through composition to every relevant
  repository, recorder, and observer.
- Desktop availability is discovered at the composition root, not inferred by
  swallowing an unknown subcommand.

## Latent Features

Machine-readable output, durable plan files, service/client transport, replay,
and queue control reuse versioned request/result/event schemas. They do not add
direct module calls or a no-review shortcut. A local-pipe client becomes a
transport replacement behind the same command adapter in M2.

## PoC Hardening

- Real invocation tests prevent the dead-subcommand `argv=None` defect.
- Both database overrides prevent tests/invocations from writing real user
  history.
- Activity-kind rendering prevents subject workflows showing `None → None`.
- Refusal/partial/no-op exit categories prevent zero-operation false success.
- Shared workflow sequencing automatically inventories before baseline/verify.
- Explicit root/id and mount choices prevent a location command from borrowing
  identity or role from another argument.
- Required selected scope plus `--accept-current-evidence` prevents accidental
  full-location rebaseline.
