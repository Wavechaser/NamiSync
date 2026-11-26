# Command-Line Interface

Status: reviewed `sync`, retained `history`, M1 location-centric
`inventory`/`baseline`/`verify`/`rebaseline` and the M2 database maintenance
commands `check`/`backup`/`restore` are implemented through the shared
interface service. Optional execute-to-verify, final typed result
classification, explicit location binding, and isolated ledger/history
overrides are active. Queue release and machine-readable output remain
deferred.

## Entry Points

`namisync` and `python -m namisync` execute the same `main()` and read real
`sys.argv[1:]` when no explicit test argument is supplied. Tests exercise both
real process entry points. No command is reachable only through injected argv.
Before parser construction, the CLI bounds the complete argument vector to
65,536 UTF-8 bytes, including one separator byte between arguments. Non-string
or non-UTF-8 arguments and a first-excess vector receive the same non-reflecting
usage refusal; no rejected argument content enters parser diagnostics.
The GUI launcher uses the same dependency-free admission before constructing
its `--data-dir` path or GUI request, for both separated and equals spellings;
it reports refusal through the native startup dialog with exit `2`.
The CLI delegates process composition, session observation, and typed result
classification to `interfaces/service.py`; it does not construct a dispatcher
or workflow runtime.

No-subcommand `namisync` and `python -m namisync` print usage, point to
`namisync-gui`, and exit nonzero. Nothing runs implicitly. `namisync-gui` is
the GUI-subsystem launcher for the sole
desktop implementation and retains no console window.

## Commands

### M0

- `namisync sync SOURCE TARGET`: run the plan session, render complete review,
  collect explicit commitment between sessions, then submit execution and render
  item/summary results.
- `namisync history [RUN]`: list retained run summaries or render one summary
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
`history` accepts `--limit N` for `1..256` summaries, `--database PATH` and
`--history-database PATH`. For every command, neither database path may be
the other's, or the other's with `.claim`, `-wal`, `-shm` or `-journal` added
(compared ignoring case): such a pair is a `Configuration error:` naming the
overlap, exit `2`, before any file is opened. For `sync`, both
database files must be distinct and outside the managed roots; defaults are
the local
`%LOCALAPPDATA%\NamiSync-Development\ledger.db` and
`%LOCALAPPDATA%\NamiSync-Development\history.db`. Only the packaged
(`sys.frozen`) release defaults to `%LOCALAPPDATA%\NamiSync`; a source run
reaches those files only when `--database` or `--history-database` names them.
Semantic defaults live in `settings.json` beside the selected ledger, so an
explicit `--database` also selects an isolated sibling settings file.

Mutating commands require the coordinated database pair. Standalone history
remains deliberately read-only and may inspect one current history database
without a ledger peer. CLI history
summary/detail output renders a persisted review-fact limit as typed durable
history truth, gives the same narrow-roots or resolve-scan/preflight guidance
as the desktop, and never reconstructs the refusal from diagnostic text or
shows a presentation-only omission as history. `DATABASE.md` and `HISTORY.md`
own the persisted consequence; `BRIDGE.md` owns the shared protocol shape
and `DEFENSE.md` §1.3 owns the scalar wall.

The current databases are ledger v5 and history v9 ([DATABASE](DATABASE.md#persistence-versions)).
Opening any ledger v1-v3 database, any history v1-v7 database, a v4/v8 file
with a pre-release contract id, or a current-version file with missing or
mismatched metadata fails before schema mutation with an instruction to close
NamiSync and manually archive or delete that database main and its SQLite
sidecars, then rerun the command. Beside a database that validates as current
or 0.1.0, the instruction names only the unusable file's path, says to keep the other
database's path as it is, and that the next sync or inventory command creates
a new one, or `namisync restore <role> <backup file>` replaces it; only when
both are unusable does it name **both** mains. A database written by a newer
NamiSync is refused with direction to use that version, never with that
instruction. A ledger given as `--history-database` or a history given as
`--database` is refused with `<role>-wrong-role` and direction to check the two
paths, which look swapped; a file whose role this version does not know is
refused the same way, with direction to check its path. A ledger that is a
backup copied into place by hand is refused with `ledger-is-backup` and
direction to put back the ledger it replaced or restore the backup with
`namisync restore ledger <backup file>` ([Maintenance
commands](#maintenance-commands)), never with that instruction. Commands never
delete either database or rebuild one from the other. If SQLite reports that a
file is damaged or unreadable as a database, the command names the affected
role and directs you to keep both databases and their sidecars for inspection,
to run `namisync check` to see which database is affected, and, given a backup
made by `namisync backup`, to run `namisync restore <role> <backup file>`, which
replaces it and keeps the damaged files beside it. That text names no path and
never advises deleting or resetting.

Before the first sync or location command admission, the CLI calls the shared
read-only database-pair preflight. A pair written by NamiSync 0.1.0 is then
migrated before the command proceeds, but only once the command's roots are
admitted with both databases outside them: a refused root or `--path`, a
nested sync pair or a database inside a root reports its usual input error and migrates
nothing. With `--location-id` the root is known only from the ledger, so the
pair migrates first. Nothing after this point migrates: if the check itself
fails transiently and the command's own admission then succeeds, the command
ends with exit `4` and `<Command> could not start: database pair refused
(pair-older).` followed by the migration direction, and running it again
migrates. One line on standard output names what migrated and its
backups, for example:

```text
Updated the ledger (v4) and history (v8) databases written by NamiSync 0.1.0; backups kept at: <ledger backup>, <history backup>
```

A 0.1.0 history joins a ledger only when the same command updated that
ledger from 0.1.0. Beside a ledger that was already current (a fresh one, a
restored one, one created because it was missing, or one an interrupted
update already finished) its runs are left as an earlier ledger's; `history`
marks them `(earlier ledger)` ([DATABASE](DATABASE.md#ledger-instance-and-ids)).
The update line does not say which case applied.

A pair with one database missing (the other present with no stray sidecar of
the missing one, which stays `inconsistent-pair`) is completed at the same
point and under the same placement rule: the missing database is created new,
after the present one is updated if NamiSync 0.1.0 wrote it
([DATABASE](DATABASE.md#one-database-missing)). A lone 0.1.0 history keeps its
runs unstamped, so they belong to an earlier ledger. Unlike migration, a
command given `--location-id` never completes the pair, because no root is
given to check the new database's path against, even when a database goes
missing while its update is starting: it exits `3` with `Database
pair refused: <role>-missing.`, directs you to run the
command with its ROOT, run a sync, or start NamiSync once, and changes
nothing. One line on standard output per created database follows any
migration line:

```text
Created a new history database at <path> because it was missing; the existing ledger is kept.
Created a new ledger at <path> because it was missing. The existing history is kept; its runs are shown as belonging to an earlier ledger.
```

If the check fails transiently and admission then meets the incomplete pair,
the command ends with exit `4` and `<Command> could not start: database pair
refused (ledger-missing).` or `(history-missing).` with the completion
direction, and running it again completes the pair.

A refused pair returns exit `3` with `Database pair refused: <reason>.` and
its guidance, then, for custom database paths, the line naming them
([Maintenance Commands](#maintenance-commands)). While database maintenance holds either database of the pair, sync execution and the
four location commands are refused at admission: they print
`Execution refused:` (sync) or `<Command> refused:` with the maintenance
message (new work is refused, not queued; wait, then start again), exit `3`
and start no run. Planning and review still run, since they write neither
database. The same holds when neither database exists yet and the command
would create them: it prints the claim's in-use message, which ends `then
retry.`, exits `3` and leaves no database file. A refusal at admission or
because another NamiSync process, of any version, has either database open or
holds its claim leaves every existing main and sidecar byte unchanged. A migration that fails after its backup was
published (`migration-failed`) normally leaves the old main file, the published
backup, and a WAL grown by a discarded tail. When the failure was in the final
commit itself, the update could not be confirmed and the database may already
be the new one; the message says so, and the next start checks again.
`backup-failed` changes nothing: when the backup failed verification, the
database itself failed SQLite's integrity check and the message says to keep
its files for inspection (migration's message for a database from NamiSync
0.1.0 stops there, since no backup made by this version can exist for it);
otherwise it says to check write access and free space. A ledger
that had already migrated when History's own step failed stays migrated, and
the next command finishes the history, with its runs as an earlier ledger's. A v0.1.0 main file copied without its
`-wal` migrates as the empty database it is, since v0.1.0 keeps its committed
rows in the `-wal`. A fresh sync pair remains
absent through planning and declined review, then is initialized together only
after explicit execution commitment. Inventory and integrity initialize a fresh
pair during workflow preparation, before their audit observer can open history.
The standalone `history` command is read-only and deliberately exempt, so an
existing history database remains inspectable when its ledger peer is missing.
It never migrates or completes a pair: a history written by NamiSync 0.1.0
exits `3` with `History admission refused:` and direction to start NamiSync,
or run a sync or inventory command, once, which also creates its ledger if it
is missing. With only a ledger present it prints `No retained history runs.`
and creates nothing. When database options were given, a `History admission
refused:` refusal ends with a line naming them. With `--database`, or both,
it is `This command was run with <options>. Add the same options to any
NamiSync command above.` With `--history-database` alone it names that option,
says no `--database` was given, and says any command above must also name this
History's own ledger with `--database`, since otherwise it pairs the History
with the default ledger; it suggests no ledger path.

`history` reads the ledger only to mark which runs belong to it, by the read
rule in [DATABASE](DATABASE.md#ledger-instance-and-ids), and never refuses or
blocks History over it. It reads the ledger named by `--database`, or the
default ledger when neither database is named; with `--history-database`
alone it opens and probes no ledger. A listed run recorded against an earlier
ledger ends with `(earlier ledger)`. When membership is unknown, one line on
standard error precedes the list: `Ledger membership is unknown: no ledger was
given, only --history-database.` or `Ledger membership is unknown: no usable
ledger at <path>.` Run detail adds `Ledger: current`, `Ledger: earlier
(recorded against an earlier ledger; its ids are not looked up)` or
`Ledger: unknown (no usable ledger)`.

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

### Maintenance Commands

```text
namisync check
namisync backup
namisync restore {ledger,history} BACKUP
```

Each accepts `--database PATH` and `--history-database PATH` and defaults to the
same pair as every other command. They go through the same argument bound and
`main` dispatch, and the CLI only parses, calls the maintenance workflow
through the service ([DATABASE](DATABASE.md#data-protection)), renders and maps
exit codes. Each holds both exclusive maintenance claims for its whole run
([DATABASE](DATABASE.md#maintenance-claim)), so it is refused with
`database-in-use` while any NamiSync window, command or run holds either
database, and new work is refused at admission while it runs.

They work on the pair **as found**. None migrates a 0.1.0 database, completes a
pair with one database missing, or creates a fresh pair, and none opens a
database before the workflow runs. They create no folder: when the folder of
either database does not exist, every one of them exits `2` and says which,
except that `check` with both folders missing says there are no databases and
exits `0`. A database path that cannot name a local file (for example one
with `?`, in its name or in a folder name) is an input error too: exit `2` with
`Input error: a database path is not valid: <reason>` before any claim is
taken, nothing changed. It is checked before the folders, so such a path is
never reported as a missing folder. The claim files
(`<database>.claim`) are the one thing a command leaves behind on a pair
without databases. `check` never writes a database; `backup` writes only new
backup files and, as any read of a live database does, may leave SQLite's own
`-wal` and `-shm` sidecars beside the live databases: a `-wal` it creates
stays empty, and it never changes a main file or an existing `-wal`
([DATABASE](DATABASE.md#data-protection)); `restore` always keeps what it
replaces and has no confirmation prompt or flag.

When `--database` or `--history-database` is given, every outcome that prints
guidance and is not a success (a refusal or failure, `check` with any role or
the pair not `ok`, a restore's `Note:`, and the `Database pair refused` output
of the commands that change files) ends with
`These databases were selected with --database '<ledger>' --history-database
'<history>'. Add the same options to any NamiSync command above.`, naming the
paths in effect, because a command in the guidance run without them would
reach the default pair. The paths are single-quoted for pasting into
PowerShell, with every quote PowerShell reads as a single quote (`'` and
U+2018-U+201B) doubled. A path holding characters NamiSync shows as `[U+XXXX]`
markers (controls, soft hyphen, zero-width, bidi and similar) is shown with
those markers, which never run but do not name that path.

- `check` reports each role on its own line, `ledger: ok`, then every problem
  as `  - <text>` (at most 20 in all, as the workflow returns them) and, for a
  state that is not `ok`, one sentence of what it means and the next step. States:
  `ok`, `foreign-key-violations`, `missing`, `damaged`, `older`, `newer`,
  `wrong-role`, `unsupported`, `is-backup`, `unavailable`
  ([DATABASE](DATABASE.md#data-protection)). When every role reads fine alone
  but the pair is not ready, or the pair needs a reset (`unsupported`), a
  `Pair: <reason>.` line with the workflow's guidance follows; for a reset it
  says what to archive or delete: both databases, each by path, when both are
  unsupported; otherwise only the unsupported one, by path, with direction to keep the
  other present one or, if the other is missing, where it was looked for. A pair
  with no databases at all prints `No NamiSync
  databases were found at <ledger> and <history>.` and a note on how they are
  created. Exit `0` for `ok` and `ok`, and for a pair with no databases; exit
  `4` when any role is anything else, `older`, `missing` and
  `foreign-key-violations` included. `4` means check found something that
  needs attention, or could not finish; a state NamiSync still opens
  (`foreign-key-violations`) and one it cannot use (`damaged`) share the code,
  and the output, not the code, tells them apart and says what to do. For
  `foreign-key-violations` it says that `backup` refuses such a database, so
  a copy of it cannot displace a backup that restores, and that with an
  earlier backup `namisync restore <role> <backup file>` replaces it and keeps
  its files beside it. Exit
  `3`, with the guidance on standard error, when the check was refused before
  it started because another process holds a database.
- `backup` needs a ready pair. It prints `Backed up the ledger to <path>` and
  `Backed up the history to <path>`, then `Removed N older backup(s): <paths>`
  when rotation kept three per database and removed any. A removal that failed
  is a warning on standard error naming the file and its error; the file is
  kept and the command still exits `0`. Exit `3` when a database is in use or
  the pair is not ready (`Database pair refused: <reason>.` and the guidance:
  an older pair gets the update direction, an incomplete pair the creation
  direction, a damaged one the pointers above; a pair with no databases says
  there is nothing to back up); exit `4` on `backup-failed` (from `restore`
  the same reason exits `3`), which prints any backup already published first
  and says it was kept. A database with foreign key violations is
  `backup-failed`: no copy of it is published or rotated in. A refusal ends
  with one line decided from the result: `The backups listed above were
  kept.` when a backup was published first, `Nothing was changed.` for
  `database-in-use` and `backup-failed`, and `No backup was written.` after
  the pair's own refusal, whose guidance is printed as every command prints
  it.
- `restore ROLE BACKUP` replaces the ledger or the history with a backup this
  version wrote. A `BACKUP` that is not an existing file exits `2` before any
  claim is taken. On success it prints `Restored the <role> from <backup>.`;
  for a ledger, the cut time of the backup and that History runs recorded after
  it are now shown as belonging to an earlier ledger; and where the replaced
  database went: `was backed up to <path>` when it checked `ok` (restored in
  place, beside an idle window), or `files were kept at <path>` when it had
  foreign key violations, was damaged or was otherwise unusable and was renamed
  aside with its sidecars, which needs it closed in every NamiSync process, or that there was
  no database to replace. A restored database beside a missing, older or
  refused peer adds a `Note:` that the pair is not ready yet, with its
  direction. Exit `0` on success.
  Exit `3`, leaving the databases unchanged, for `database-in-use` (an
  in-place restore that meets a lock mid-copy restores nothing but leaves the
  pre-restore backup it made, which the output names), the backup refusals
  (`backup-unavailable`, `backup-damaged`, `backup-wrong-role`, `backup-newer`,
  `backup-unsupported`, `backup-older` (a v4 or v8 migration backup is the way
  back to 0.1.0, not a restore source), `backup-unstamped`), `target-wrong-role`,
  `target-inconsistent`, `backup-failed` (the pre-restore backup could not be
  made) and the ledger pair rule (`history-newer`, `history-wrong-role`, and
  `pair-older`, which directs you to update a healthy 0.1.0 pair before
  replacing its readable ledger). A ledger is otherwise restored beside a
  damaged, unreadable or 0.1.0 history, so with both damaged either can be
  restored first.
  Exit `4` for `restore-failed` and `restore-unconfirmed`. Every refusal prints
  the workflow's own guidance, then one line decided from the result, never
  from the text: `Kept: <path>, the database as it was before this restore
  (with any -wal and -shm files beside it).` when the call kept a file, or
  `Nothing was changed.` when it changed nothing; `restore-unconfirmed`
  without a kept file prints neither.
- Beside an open NamiSync window a restore works only when the database it
  replaces checks `ok`: it is copied in place,
  the window keeps its connections and reads the restored content at its next
  read, and a sync plan reviewed before the restore is refused at start
  (`The ledger was replaced (restored or reset) after this plan was made...`,
  exit `3`). A database with foreign key violations, a damaged or an otherwise
  unusable one needs every other process closed and is refused with
  `database-in-use` while any holds it.
- A restore that was started but could not be confirmed (`restore-unconfirmed`)
  may already have replaced the database or moved it only in part. The output
  says the result could not be confirmed, names the file kept, and says to run
  `namisync check` before using NamiSync and to keep every file beside the
  databases. When only sidecars were moved aside before the stop, no file is
  kept: the guidance names their new paths and says the database itself is
  still at its path. Nothing is deleted.

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
| `3` | commitment, fresh-preflight or admission refusal with no managed-data mutation |
| `4` | planning/execution/runtime failure |
| `5` | cooperative cancellation |
| `6` | selected safe work completed, but blocked or deferred items remain |
| `7` | degraded ledger or audit durability |
| `8` | integrity mismatch |
| `9` | verification incomplete (including modified, missing, unsupported, error, or newly baselined during verify) |

`check`, `backup` and `restore` use only `0`, `2`, `3` and `4`, as listed under
[Maintenance Commands](#maintenance-commands); they have no headline.

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
the desktop's defended C0/C1, bidirectional, line and invisible layout controls
as ASCII `[U+XXXX]` markers in review, progress, results, history and diagnostics,
including parser errors. Literal `[` becomes `[[`, so a filename containing
`[U+0085]` remains distinguishable from an actual U+0085 control. Marker output
also works with redirected Windows code-page streams; ordinary Unicode and
Windows path separators retain their spelling when the selected output encoding
can represent them. Unencodable characters use the same ASCII `[U+XXXX]`
markers, including in parser diagnostics, so redirected output remains complete.
The CLI preserves the stream's encoding and ownership; real write or flush
failures retain their existing handling. Rendering does not alter filesystem
paths or operation identity.
Runtime validation names missing/nonexistent/unusable paths
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
