# Command-Line Interface

Status: draft contract. Priority: architecture assigns reviewed `sync` and
`history` to M0; integrity commands arrive with M1.

## Entry Points

`nami-sync` and `python -m namisync` execute the same `main()` and read real
`sys.argv[1:]` when no explicit test argument is supplied. Tests exercise both
real process entry points. No command is reachable only through injected argv.

Until a desktop exists, no subcommand prints usage and exits nonzero; nothing
runs implicitly. Once the desktop is delivered, `nami-sync`, `nami-sync-gui`,
and `python -m namisync` with no subcommand launch it.

## Commands

### M0

- `nami-sync sync SOURCE TARGET`: run the plan session, render complete review,
  collect explicit commitment between sessions, then submit execution and render
  item/summary results.
- `nami-sync history [RUN]`: list envelopes or render typed retained detail.

For noninteractive use, mandatory review cannot be waived by a casual `--yes`.
The command surface may expose a separate queue-release flag that executes only
already committed sets. A commitment binds plan fingerprint plus exact selection
digest; no flag combination plans and executes in one unreviewed invocation.

### M1

- `inventory LOCATION`: refresh and print role-free inventory/mapping guidance.
- `baseline LOCATION [scope]`: inventory as needed, create missing baselines,
  and report typed counts/issues.
- `verify LOCATION [scope]`: refresh appropriately, verify, and return an
  integrity-issue exit status when needed.
- `import-hashes LOCATION SIDECAR`: explicitly import one TeraCopy sidecar.

Integrity commands accept both `--database` and `--history-database`; tests use
temporary values for both. A selected location is never inferred by falling
back to another argument.

## Review Rendering

Print roots/volume evidence, policy, filter/policy snapshot, operation counts and
content bytes, conflicts/refusals, required/free capacity, trash behavior,
computed ingest destinations when applicable, and a stable plan fingerprint.
Commitment occurs only after the plan session has terminated and released
custody. Execution output discloses fresh-preflight refusal/material drift.

## Output And Exit Status

Human output goes to stdout/stderr with actionable reasons and no ambiguous
green-success wording. A future machine format is versioned and writes progress
separately from the final structured result.

Draft exit categories (numeric assignment may be finalized with implementation):

- success, including explicit no-op;
- usage/input error;
- preflight/volume refusal with no mutation;
- partial or complete activity failure;
- cancellation;
- integrity issues found (`mismatched`, `modified`, `missing`, error);
- filesystem success with ledger/history durability degradation.

`RecordingStatus.DEGRADED` supplies the ledger distinction. The architecture
still needs a typed history/audit result field before the CLI can assign the
history-degradation category without parsing diagnostics.

Exit status derives from typed result, not log text or byte count.

## Concurrency And Control

Mutating commands submit to dispatcher and obey cross-process physical-volume
custody. Read-only history/status can run with GUI or other sessions. Interactive
Ctrl+C requests cooperative cancel, continues rendering terminal cleanup, and
exits only after custody/result state is known. A second interrupt may follow an
explicit hard-abort policy but never reports clean cancellation prematurely.

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

## Acceptance Criteria

- Subprocess tests invoke `nami-sync` and `python -m namisync` with real argv for
  every command and compare dispatch/results.
- M0 exposes reviewed `sync` and `history`; default behavior is defined for both
  pre-desktop and desktop installations.
- Plan command/session mutates no files/ledger configuration and releases locks
  before commitment input.
- Execution cannot proceed without a matching plan-and-selection commitment and
  always freshly preflights; queue release accepts already committed sets only.
- Refusal, no-op, partial failure, cancel, mismatch, and ledger-behind return
  distinct documented exit categories and truthful output.
- Ctrl+C during multi-GiB simulated copy/import reaches cooperative terminal and
  releases custody.
- Integrity commands with temporary DB overrides write neither real ledger nor
  real history; omission uses documented safe local paths.
- Read-only history runs during active writer; contending mutation follows
  dispatcher volume policy.
- Location-only commands require exactly the selected usable location and never
  require/fallback to a paired root.
- History prints sync operations and integrity/import detail by activity kind,
  including pruned-detail explanation.
- Invalid path, permission, volume ambiguity, stale plan, and capacity refusal
  messages each state the next user action.
- `python -O` retains all runtime guards and behavior.
