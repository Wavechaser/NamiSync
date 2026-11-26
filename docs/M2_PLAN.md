# M2 Plan

M2 started on 2026-11-23, and this is its plan and delivery register: the
checkpoint register first, then the feature specification it draws on, then
detail sections for features that need them. The register's rows are a proposed
shape. No implementation checkpoint is active until the user accepts its row;
until then listing an outcome does not authorize implementation or change
current limits.
[FEATURES](FEATURES.md) owns product behavior and accepted future boundaries;
[ARCHITECTURE](ARCHITECTURE.md#m2--durable-sessions-and-queue-ownership) owns M2
direction. Accepted future outcomes remain binding; unrealized representation
and implementation recipes are reconsidered at first use under [AGENTS](../AGENTS.md).
Completed M1 decisions, exclusions and unresolved observations are in the
archived [M1 register](obsolete/M1_REGISTER.md).

## Checkpoint Register

**Thesis** (user decision, 2026-11-21): M2 makes NamiSync lasting and legible.
What it did, what it knows and what it was doing survive time (restarts,
crashes, restores, retries and schema changes) without anything acting on stale
authority, and are shown to the user honestly. Items that serve neither half
ride along and never block M2.

M2 ends in a release (user decision, 2026-11-23), so databases written by
v0.1.0 must really migrate, and doing so is part of M2's exit gate. Because the
user now runs the released product, development also needs a stronger guarantee
that work from the source tree, including tests, tools and the CLI, cannot
casually change the live production databases (M2-A1).

### How The Register Works

- **Segments.** M2 is delivered in larger segments (user direction,
  2026-11-20), lettered so a checkpoint reads as M2-A1 (user direction,
  2026-11-23). Each has an aim under the thesis, an entry condition, an exit
  condition and non-goals. Segment A carries mostly backend work with little
  immediate user value; to keep its contracts from being designed for imagined
  needs, each foundation piece ships with its first real consumer, even a thin one.
- **Rows.** Each checkpoint names its outcome, what it includes, its first
  consumer, what it depends on and what kind of gate closes it. That is a shape,
  not a specification: exact populations, tests, gates and stops are fixed when
  the user accepts the row at its start, under [SCOPE](procedures/SCOPE.md).
  Rows are in dependency order; a row may be reordered within its dependencies
  or split (M2-B5a, M2-B5b), and an id is never reused.
- **Status.** Proposed, accepted, active or complete. Every row is proposed
  until the user accepts it, and a proposed row authorizes nothing.
- **Where requirements go.** A checkpoint's first commit moves the decisions it
  relies on from the feature specification into the owning documents (FEATURES,
  ARCHITECTURE, DATABASE and the component documents), makes any pending
  FEATURES or WORKFLOWS reconciliation, and leaves a pointer in the
  specification. Contracts several checkpoints share (session progress and hold
  reason, the ledger instance id, ids never reused, the maintenance gate, the
  queue contract) move into ARCHITECTURE or DATABASE at the start of the
  checkpoint that first implements them.
- **Completion.** A complete row shrinks to its outcome, its evidence record and
  any accepted residuals. The specification shrinks as rows start, so this plan
  becomes a register as M2 proceeds, without separate compaction passes.
- **Ride-alongs.** Items outside the thesis become rows only when the user
  accepts them; until then each keeps the ordering constraint listed for it.

### Segment A — Safe To Change The Databases

- **Aim:** released data survives schema changes, development cannot casually
  damage the user's live data, and the foundations B and C build on exist.
- **Entry:** none.
- **Exit:** the v0.1.0 fixture databases migrate to the current schema;
  maintenance refuses under any writer in any process; session progress and
  hold reason are core contracts; Plan and Inventory share one review surface.
- **Non-goals:** the History and Data pages (B); anything surviving a restart (C).

Checkpoints:

- **M2-A1 Live-data guard** (complete, 2026-11-24, `9bb58fa9`). Source-tree
  work cannot change the live production databases unless told to by an
  explicit path. Only the PyInstaller release defaults to
  `%LOCALAPPDATA%\NamiSync`; source runs and the development shell share
  `%LOCALAPPDATA%\NamiSync-Development`, and the desktop identity follows the
  resolved root, revising SH-G-10 (user decisions, 2026-11-24;
  [INTERFACES](INTERFACES.md), [COMMANDLINE](COMMANDLINE.md)). A session-wide
  audit hook fails any test that tries to change the live root, even when the
  refusal is swallowed ([TESTS](TESTS.md#live-data-guard)). Gate: the guard's
  own tests prove refusal on the real live root without creating anything, and
  a source CLI subprocess resolves to the development root; two adversarial
  review rounds, 6675 ordinary tests passing except the seven known
  interpreter-bound failures, headed SH-G-2 3/3. Residuals: native `ctypes`
  calls, SQL `ATTACH` on open connections, UNC aliases, 8.3 names and links are
  not seen by the hook; a GUI launched with a gallery data root keeps the
  production identity.
- **M2-A2 Spikes** (complete, 2026-11-24). Window framing, drag-and-drop paths,
  completion notification, volume overview queries and Stop's
  cancel-to-release time were checked live, and each result is recorded in its
  feature's entry, with [EV-0040](../evidence/EV-0040/README.md), the desktop
  checks in [EV-0041](../evidence/EV-0041/README.md) and the framing fixes in
  [EV-0042](../evidence/EV-0042/README.md). The user's
  decisions on the results are recorded there too: toasts as a user-enabled
  setting, and a stoppable planner by B6. The maximized-caption follow-up
  ([EV-0043](../evidence/EV-0043/README.md)) restores native hover with zero
  non-client top inset and client-side padding; the user confirmed the visual
  behavior. The prototype's pre-existing restore-size growth is traced to
  WinForms with a demonstrated remedy ([EV-0044](../evidence/EV-0044/README.md)).
  UNC drops, a cold sleeping-disk scan and USB disks remain unchecked;
  the `J:\NamiSyncSpike\stop-latency` fixture kept for a few days
  at the user's request.
- **M2-A3 Maintenance claim and schema migration** (complete, 2026-11-25).
  A database written by v0.1.0 migrates to ledger schema 5 and history schema 9
  when the desktop starts or a mutating CLI command runs, with every row and id
  kept and a verified backup published first; anything else is refused, never
  half-migrated and never under a writer. The gate came first, with migration
  as its first consumer (user decision, 2026-11-24). Behavior and reasons live
  in [DATABASE](DATABASE.md#schema-evolution),
  [ARCHITECTURE](ARCHITECTURE.md#38-persistence-boundary) and
  [CORE](CORE.md); the gate record is
  [EV-0045](../evidence/EV-0045/README.md).
  - **Delivered as four reviewed commits:** the v0.1.0 fixture, the format
    constants and vectors, the maintenance claim, and the schema with its
    migrator and admission. The accepted row listed schema and admission as two
    outcomes; they landed together because a schema change without admission
    would have refused every released pair.
  - **Gate, passed:** the fixture migrates and reopens as ready; a migration
    killed during backup, copy, commit or close left the old or the new
    database in 15 of 15 trials and the next call finished it; a newer database
    is refused without reset guidance; a format changed without its constant
    and vector fails tests; migration refuses under another process's claim or
    open handle; a killed process releases its claim; 7079 ordinary tests pass
    apart from the seven known interpreter-bound failures, and 13 import
    contracts hold. A follow-up CLI regression covers SQLite damage to either
    role and verifies that refusal preserves the pair and advises keeping it.
  - **Design decisions** (2026-11-25, made in the row's design and open to the
    user's revision). The signal for a v0.1.0 process is the database files
    themselves, not `Local\NamiSync.Desktop`, which cannot see a CLI run and
    names every newer desktop. Migration is one transaction per database with
    no automatic restore. `locations`, `mappings` and `inventory` get
    `AUTOINCREMENT`. A history run's ledger instance is nullable, because
    direct history writers in tests and tools have no ledger. The CLI announces
    a migration on standard output; the desktop only in its log.
  - **Accepted residuals:** migration limits are listed once in
    [DATABASE](DATABASE.md#migration-limits) and decided by
    [DEFENSE §2.5.4](DEFENSE.md#254-migrating-a-released-database). Outside
    migration: path keys follow the release interpreter's Unicode case tables;
    no vector can detect a change there ([CORE](CORE.md)).
  - **Found outside scope, not fixed:** the copied-dispatcher pause, resume and
    cancel cases in `tests/interfaces/web/test_drain.py` miss their fixed
    deadlines under heavy parallel load, also on the commit before this row's
    work (EV-0045).
  - **Handed to A4:** refusal at admission when maintenance holds the claim
    (in the A4 row), the read rule for runs with no or another ledger
    instance, backup rotation, and a way forward for a damaged database.
- **M2-A4 Maintenance commands** (complete, closed 2026-11-27; `650110fd` to
  `78246b75`, review fixes and the stamp revision to `e1f40f63`, review
  rounds to `1c940e60`). Check, backup and restore run as
  maintenance sessions under A3's claim, with restore issuing a new ledger
  instance id and its lineage. Every plan, held in memory or stored, records the
  ledger instance it was planned against, and preflight refuses a mismatch, so a
  plan reviewed in the GUI before a CLI restore is refused at start rather than
  executed (user decision, 2026-11-24). Consumer: CLI maintenance commands
  (check, backup, restore); the Data page follows in B3. Depends on A3. Closes
  on: maintenance refuses while a GUI or CLI run holds a claim, new runs are
  refused while maintenance holds it, and a plan reviewed before a restore is
  refused at start. Input from A3 (2026-11-25): the dispatcher admitted a
  session whose history observer was refused the claim with audit degraded.
  Outcome 1 turned that into a refusal at admission
  ([DATABASE](DATABASE.md#maintenance-claim)).
  - **User decisions (2026-11-25).** Lineage storage amends the unreleased
    ledger schema 5 in place, with no new migration step; a schema-5 pair made
    by a source-tree run since A3 is refused with reset guidance. The CLI runs
    maintenance directly under both exclusive claims, as migration does; the
    dispatcher-session form waits for the Data page (B3). `restore` replaces
    the ledger or History, one per command, from a backup at the current
    schema version; v4 and v8 migration backups are refused. Backup rotation,
    a way forward for a damaged database, the missing-database policy and the
    run read rule are all in this row. After the design lane (inspected at
    `315d1d90`), the same day: a start refused under maintenance reaches the
    desktop as a new definitive fixed bridge error, never an uncertain start.
    Restore backs up the database it replaces and copies the image in place
    when that database still backs up cleanly (this runs beside an idle
    desktop); otherwise it renames the damaged files aside, kept and never
    deleted, and moves the image in, which needs the database closed in every
    NamiSync process. This is the reading of "no backup, no change". A live
    ledger whose lineage names its own instance, a backup copied into place by
    hand, is refused at admission with direction to `restore`. The read rule
    is an ancestor chain: a run is current if it matches the ledger's
    instance, or any ledger in the restored backup's ancestry before that
    ledger's cut. The predecessor is the ledger the backup was cut from, not
    the one replaced.
  - **Design (open to the user's revision).** A backup records its own cut
    time in the copy, read under both exclusive claims, because content proves
    the instance but not the time. A restore image is prepared beside the
    database with the new instance id written and the backup's lineage kept.
    Rotation keeps three backups per database and leaves migration backups
    alone, since they are the only way back to 0.1.0. A ledger copy with no
    backup stamp is refused as a restore source. A lone v0.1.0 History
    migrates with no ledger stamp, so its runs never join the new ledger.
  - **Outcomes, one reviewed commit each, in order:**
    1. A session whose History claim is refused because maintenance holds it
       is refused at admission, with nothing stored; every other audit-factory
       failure still degrades audit.
    2. A plan records the ledger instance it was planned against, and
       execution start refuses a mismatch before any filesystem change.
    3. The ledger stores restore lineage (each ancestor's instance and
       cut-off), and History readers mark a run with no instance, or one
       outside the ancestor chain, as belonging to an earlier ledger.
    4. Check, backup, restore and count-based backup rotation in `db`, met in
       one workflow under both exclusive claims. Restore also replaces a
       database that fails admission.
    5. One-present pairs: a lone ledger gains a History; a lone History gains
       a new ledger with a recorded lineage boundary.
    6. CLI `check`, `backup` and `restore`, and damage refusals that point to
       them.
  - **Preserved:** read-only classification writes nothing; no backup, no
    change; a refusal leaves both databases as found; rotation never deletes
    the newest good backup or a file it does not recognize; the dispatcher
    stays domain-blind.
  - **Non-goals:** the Data page, archive-and-reset, History pruning, purge,
    scheduled maintenance, export and import, a second-volume backup
    destination, and refusal of restore by naming in-process waiting work
    (B3, where restore first runs inside the desktop).
  - **Stamp rule (user decisions, 2026-11-25 and 2026-11-26).** Pair
    migration stamped a v0.1.0 History's runs with whichever current ledger
    sat beside it; two unplanned cases reached the reviews and a recurrence
    pause was taken. Its first rule, a `migrated-released` marker in the
    ledger's lineage, was withdrawn the next day as residue that outlives the
    import ([DEFENSE §2.5.4](DEFENSE.md#254-migrating-a-released-database)).
    Current rule: a v0.1.0 History is stamped only when the same upgrade
    operation, under the same held claims, migrated its ledger in that call;
    otherwise it migrates unstamped and its runs show as an earlier ledger.
    Ledger schema 5 was amended back in place, and a source-tree ledger made
    with the marker kind is refused with the reset direction. Accepted
    residual: an interruption between the ledger's migration and History's
    leaves a genuine pair's 0.1.0 runs shown as an earlier ledger.
  - **After the review at `48ab4718` (user decisions, 2026-11-26).** Six
    defects were fixed (`41e020b7`, `c29ebe18`): the list is in
    [CHANGELOG](../CHANGELOG.md). Two policies changed with them. A database
    with foreign key violations is not backed up, and restore renames it
    aside instead of overwriting it in place, so every maintenance backup
    restores. A ledger restore is refused only beside a History of another
    role or a newer one, and, as advice, over a healthy older pair
    (`pair-older`); beside a damaged, unreadable or 0.1.0 History it
    proceeds, so either damaged role can be repaired first. The CLI and the
    desktop upgrade or complete a pair through one operation,
    `upgrade_database_pair`.
  - **Deferred to B3 (user decision, 2026-11-25):** a plan refused because
    its ledger was replaced shows the desktop's generic commitment refusal.
    A bridge refusal that names the cause should exist, and waits for B3,
    where restore first has a desktop consumer.
  - **Accepted (user decision, 2026-11-25):** a plan made while no ledger
    exists records no instance and runs against the ledger execution creates
    or finds.
  - **Gate:** the three closing conditions above with real child processes;
    restore killed during image preparation and during the copy leaves the old
    or the new database; the ordinary suite apart from the seven known
    interpreter-bound failures; `lint-imports`.
  - **Gate result (2026-11-26, `78246b75`):** met. The closing conditions run
    through the real command with child processes
    (`tests/test_cli_maintenance.py`), and the kill trials are in
    `tests/test_database_maintenance.py`. 7310 ordinary tests passed, 4
    skipped, 35 deselected, with the seven known failures; 13 import contracts
    kept. Each outcome had an independent adversarial review. On `e1f40f63`,
    after the review fixes and the stamp revision, each independently
    reviewed: 7326 passed, 4 skipped, 35 deselected, with the same seven
    failures; 13 contracts kept.
  - **Second review round (user decisions, 2026-11-26).** Eight findings
    were fixed in `4993a244` to `72176b46`; the list is in
    [CHANGELOG](../CHANGELOG.md). The decisions behind them:
    - An admitted run holds shared claims on both databases, ledger first,
      until its observer closes; the stamp is read once under the ledger's
      claim. This replaces the re-read in outcome 1's follow-up.
    - An integrity continuation keeps the ledger instance read under the
      recorder claim that saved its progress, and a resume that finds another
      instance is refused before the scan. No claim is added across the
      pause.
    - Creating a missing database needs the caller's permission, enforced
      under both claims. A `--location-id` command never grants it.
    - A reset direction names only the database that needs it and says to
      keep one that validates.
    - The v0.1.0 History stamp and its exact verification belong to the v8
      step, so removing that step removes them.
    - A `history` refusal repeats only the options given; with
      `--history-database` alone it tells the user to name that History's
      ledger for other commands.
    - A desktop startup refusal keeps its message, with paths and the
      recovery direction, in the GUI log.
  - **Gate result (2026-11-26, `72176b46`):** 7366 ordinary tests passed, 4
    skipped, 35 deselected, with the same seven failures; 13 contracts kept.
    Each of the six commits was independently reviewed, and the two claim
    defects were reproduced with real child processes before and after.
  - **Third review round (2026-11-26).** Five findings and the four items
    the second round left open were fixed in `d07cb246` to `0ce55b6f`; the
    list is in [CHANGELOG](../CHANGELOG.md). The decisions behind them:
    - A session record keeps the items an integrity run reported before a
      refused resume (user decision: they are the run's account). A view
      that shows one as the row's current state is the defect.
    - The inventory review labels a row from the ledger whenever the run
      ended failed, canceled or refused, not only after a replaced ledger:
      the page has no ledger identity, so the run's outcome is the rule. The
      integrity context gained `outcome` for it
      ([BRIDGE](BRIDGE.md) owns the shape).
    - A first-use sync run is bound to the ledger its first recorder opened,
      kept in the runtime for as long as the run can resume.
    - The path check covers the other database's SQLite sidecar paths as
      well as its claim path, because a History at the ledger's `-wal` path
      damaged the pair in a child-process run.
    - A role's `check` states what was found; only the pair decision
      directs a discard.
  - **User decisions (2026-11-27):**
    - Creating a first pair holds both exclusive claims throughout, and
      admission checks for a held claim before it reports a pair as
      unusable. Three commands started at once on a fresh pair had left the
      losers with `inconsistent-pair` or `database-unavailable` and exit `4`;
      they now exit `3` with the claim's retry message. The same check
      covers a restore caught mid-copy.
    - The inventory review has two sources for a row, the run's live items
      and the ledger. Two consequences are accepted until B3: a canceled or
      failed verify whose mismatch could not be recorded shows it only in
      Details, and rows keep a run's labels after a CLI restore until the
      run is resumed or canceled, or until Refresh.
  - **Gate result (2026-11-26, `0ce55b6f`):** 7392 ordinary tests passed, 4
    skipped, 35 deselected, with the same seven failures; 13 contracts kept.
    Each of the five commits was independently reviewed. The claim change
    of 2026-11-27: 7397 passed with the same seven failures, 13 contracts
    kept, independently reviewed.
  - **Closure (user decision, 2026-11-27).** The closure review at
    `9bfc6792` found a session admitted with degraded audit when a History
    restore began after preparation. `1c940e60` takes both shared claims
    before the observer opens either database, so it is refused at
    admission: 7399 passed with the same seven failures, 13 contracts kept,
    independently reviewed. Two findings stay open in
    [BUGS](BUGS.md#database-artifact-ownership-and-rollback) and do not hold
    the row: the cold validation beside a live writer (BUG-0320, accepted as
    bounded and harmless) and nested custom database paths (BUG-0321).
  - At the first post-M2 schema step, the stamp condition ("the ledger
    migrated in this call") must be narrowed to the 0.1.0 step.
  - **Left open, with owners:** the integrity page shows no run-level
    status when item recording or audit degraded, though the result carries
    both, and no session reports audit degradation before it ends (B3, one
    fix family: the page needs the status lines sync has, then a live audit
    signal on the session); the desktop refusal that names a replaced
    ledger, restore inside the desktop and its refusal naming waiting work
    (B3); inventory acknowledge and restore by row id are not covered by the
    plan's instance check (B3); stored plans and paused continuations record
    the instance when they first exist (B2). Not exercised by a real fault:
    an unconfirmed or failed restore through the CLI, an in-place restore
    stopped mid-copy by a lock, and a backup-removal failure. A cold probe
    still reports `database-unavailable` during any WAL write transaction,
    which predates this row (BUG-0320). Limits are in
    [DATABASE](DATABASE.md#data-protection).
- **M2-A5 Session progress and hold reason** (proposed). Sessions carry progress
  and hold reason, and the server derives every capability from them. Includes
  the `PENDING`-to-held edge. Consumer: Pause all and Resume all, pulled forward
  from Task rail batch actions so the contract ships with a real user. Holds act
  on today's in-process queue; nothing is persisted, and queue ownership is
  B2's. Closes on: transition tests (a held session never starts), Pause all
  atomic against the scheduler, and Resume all's admission order.
- **M2-A6 Shared review surface** (proposed). Plan and Inventory render through
  one review component on the windowed table substrate, settling the switcher
  label drift. Includes the parity test against documented allowed differences,
  the static check and the gallery. Must land before any new table. Closes on:
  the parity test, and no page assembling shared parts directly.
- **M2-A7 One table component** (proposed). Recent pairs and the batch table move
  onto the same component, so one table family remains. Depends on A6. Closes on:
  no native-table family left, with row-action behavior tested once in the component.
- **M2-A8 Physical-disk scheduling** (proposed). Sessions on one spinning disk run
  one at a time. Includes the per-start key callback, the unreadable-key
  fallback and the seek-penalty read; drive-type notices and estimates ride
  along. Depends on A2's volume query spike. Closes on: two partitions of the HDD
  fixture serialize, SSD concurrency is unchanged, and unreadable keys fall back.
- **M2-A9 Capacity decision** (proposed; rides along except where durable work
  forces it). Profile large tasks, then choose the task and start-response
  bounds (at most 256) and add the README and in-app notices. The profile
  includes planning time, which A2 found growing faster than the trees; it
  starts from a clean reproducer, since that fixture's target overlapped its
  source on a loaded machine (user direction, 2026-11-24: investigate, then
  optimize). Optimizations the profile justifies become rows of their own. Closes on: the profile in
  PERFORMANCE, the bounds and notices shipped, and a decision on optimization rows.

### Segment B — See And Act On What Happened

- **Aim:** the user can see what NamiSync did and knows, manage its data, retry
  or change a task in place, and act on many tasks at once.
- **Entry:** A3 and A4 for anything that reads or changes the databases in a new
  way; A5 for retry and rail actions; A7 for new tables.
- **Exit:** the History and Data pages, in-place retry and Edit setup, the
  recorded queue contract, rail actions and CLI parity's decided parts.
- **Non-goals:** anything surviving a restart beyond M1's behavior (C).

Checkpoints:

- **M2-B1 History page** (proposed). Run list, paged run detail and an
  activity-kind filter over the existing readers, entered above Settings, with
  Open in Setup carrying paths only. Reconciles FEATURES' Restorable Task Setup.
  Closes on: [INTERFACES](INTERFACES.md) SH-G-9, and pruned or degraded runs
  shown as what History holds.
- **M2-B2 Queue ownership and policy** (proposed). Settled in early-mid B, before
  rail actions and durability build on the queue, so B and C never fight over
  queue policy (user direction, 2026-11-23). Records one contract: the desktop
  process owns the queue under one owner lock; every queue respects holds; the
  queue may clear an entry, never create one; launch policy; CLI awareness.
  Implements only what B's own rows need; persistence is C4. Reconciles
  FEATURES' Queue Launch Policy and WORKFLOWS' queue-replay rule. Depends on A5.
  Closes on: the contract accepted by the user and recorded in its owners, with
  any in-process change tested.
- **M2-B3 Data page** (proposed). Location management (counts, purge of
  acknowledged-missing rows, forget) and the A4 maintenance sessions in the GUI,
  adding history pruning and a guided archive-and-reset. Reconciles FEATURES'
  Soft-Deleted Mappings. Depends on A3 and A4. Closes on: counted confirmations,
  restore refusing while the desktop's reviewed or queued work exists and naming
  it (a courtesy on top of A4's instance check, which already covers work it
  cannot see), and
  History showing forgotten locations as forgotten.
- **M2-B4 Task annotations** (proposed). Notes on History runs, first in run
  detail. Decides whether the table moves to History through A3's migration.
  Depends on B1.
- **M2-B5 Same-task retry and Edit setup** (proposed). In-place replacement with
  its routing, close-at-admission and reserved slot; Verification retries; task-
  owned admitted bindings. Replacing a paused run (the predecessor wait) may
  split off as B5b. Reconciles FEATURES' Plan Again. Depends on A5 and B1. Closes
  on: routing tests for unrun, ran, degraded and unknown attempts, retry on a full
  rail, and two tasks never running together.
- **M2-B6 Rail actions** (proposed). Stop all, batch Close, the rail filter, the
  batch runner's pause, and Stop while checking, scanning or planning, with a
  stoppable planner (user decision, 2026-11-24). Depends on A5, B2 and B5.
  Closes on: the late-stop-is-harmless test, a full rail within the bridge's
  64-exchange bound, stop latency against A2's measurement, and a stop during
  planning ending canceled with volume custody released.
- **M2-B7 CLI parity** (proposed). JSON output, plan-only and commit tokens,
  per-run options, operation selection, settings, ledger browsing, acknowledge
  and restore, history filters, `verify --run`, `recent` and agent-usable review
  output. Tokens and run-scoped refusals serve the thesis; the rest rides along.
  Independent of other B rows. Closes on: token mismatch refusals naming the
  difference, and run-scoped commands never silently widening.
- **M2-B8 Presets and the user config file** (proposed; presets ride along, the
  ownership decision does not). Presets live in a small db-owned config file of
  their own beside `settings.json`, outside the ledger and History (user
  direction, 2026-11-23), so it has its own format, migration and backup and
  never mixes with durable evidence. Whether recent locations move into it is
  decided before presets go live. Depends on A3's version discipline and A7.
  Closes on: the file versioned, migrated and backed up on its own; a corrupt
  file losing only presets; and presets conferring no admission authority.

### Segment C — Work Survives The App

- **Aim:** tabs, reviewed plans, paused runs and the queue survive closing,
  crashes and restarts, and nothing acts on stale authority.
- **Entry:** the B2 contract, B5 and B6.
- **Exit:** launch restores by the recorded rules, the crash rules are tested,
  and `INTERRUPTED` has its first production use.
- **Non-goals:** scheduling; resuming anything that was running when the process died.

Checkpoints:

- **M2-C1 Recovery store and stored plans** (proposed). A separate SQLite store
  with one writer, reached through a core protocol that db implements. Commits
  settings and admitted bindings at admission and keeps reviewed plans with
  their selection and used mark; preflight checks the ledger instance. Consumer:
  reviewed plans restored after a restart; held and queued sessions are C4's
  (user decision, 2026-11-24). Depends on A3 and A5;
  B3's restore refusal extends to stored plans here. Closes on: restore after restart, a corrupt or mismatched store losing only
  tabs, and a used plan returning as needing attention.
- **M2-C2 Paused continuations and crash rules** (proposed). Paused state saved
  once at pause and marked resuming before filesystem work; launch reads the
  most specific evidence first; interrupted runs offer Retry. Depends on C1 and
  B5. Closes on: process-kill tests at each mark, with no resumed run behind the files.
- **M2-C4 Durable queue** (proposed). Held, pending and queued sessions survive
  closing, crashes and restarts from what the store records at admission and at
  each transition: the queue-owner lock and persisted holds under B2's contract;
  queued executions return held; CLI runs show as waiting. Depends on B2 and C1.
  Closes on: queued and held tasks come back held and in order after a close or
  a process kill, and none starts by itself.
- **M2-C3 Closing the app** (proposed). The close flow only: Close applies
  Pause all, confirms with counts and shows what it waits for; sign-out and
  shutdown pause best effort. It saves nothing of its own, since paused state
  is saved at pause (C2) and pending and held sessions at admission (C4) (user
  decision, 2026-11-24). Depends on B6, C2 and C4.
- **M2-C5 Lazy restore and lineage** (proposed). Light launch restore, the
  opening mark that prevents launch loops, and the History lineage link. Depends
  on C1 and B5. Closes on: a task killed while opening returning without its
  heavy data, and Task-Grouped History whole across replacements.

### Segment D — Look Before Syncing

- **Aim:** answer what exists where, what takes the space and how two places
  differ, without planning a sync. Part of late M2 (user decision, 2026-11-23):
  much of each page is GUI work over reads the backend already serves.
- **Entry:** A7, A8 and B5's Setup prefill. D may overlap C; restored D tasks
  keep only their paths once C5 lands.
- **Exit:** the Browse page with both cards, disk usage, the volume overview and
  shell actions.
- **Non-goals:** any mutation; ledger writes with the switch off; recents from
  read-only use.

Checkpoints:

- **M2-D1 Browse page and volume overview** (proposed). One page with the Browse
  and Storage cards, the volume list from A2's queries, and its tasks on the rail.
- **M2-D2 Disk usage view** (proposed). The Storage card's view; the open
  questions in its detail section are settled at its start. Depends on D1.
- **M2-D3 Comparison** (proposed). The merged comparison table over the
  planner's comparison as a pure function, the ledger switch, and Send to Sync.
  Depends on D1.
- **M2-D4 Shell actions** (proposed). Copy Path, Open in Explorer and Properties
  for rows on every page. Depends on A6, not on D1–D3.

### Release

- **M2-R1 Release** (proposed). M2 ships as a release. Includes migration of
  real v0.1.0 data, proven on the fixture and rehearsed on a copy of the user's
  live databases, never on the live files, plus release evidence under
  [TOOLS](TOOLS.md). Depends on every accepted row that does not ride along.
  Closes on: the release gates and the migration rehearsal.

### Ride-Alongs And Later

Ride-alongs never block M2. In priority order:

1. The performance items come first. They do not fit the thesis and are not
   easy, but they touch the backend and recording stack M2 already opens, so
   later they could be harder or costlier: Verification open lookahead; Small-file
   copy batching, after A3 because grouped commits move when a writer's claim
   ends, with settlement rules that C2 must accept; Unbuffered source reads.
2. The rest, unordered (user decision, 2026-11-21): Window (Custom title bar and
   Native Fluent overlay scrollbars, after A2's framing spike and A6's label
   settlement); Recent locations, after B8's ownership decision; Verify-only
   batches; Drag-and-drop Setup, after A2's drop spike; Easier exclusions;
   Progress chart; Completion notification, as a user-enabled setting after
   A2's spike; Specific I/O errors; Session cleanup;
   Command-result retention, the lasting capacity fix that also allows D's
   in-task snapshots; drive-type notices and estimates, after A8.

Checksum adoption stays unassigned; it needs A3, and its Browse home needs D3.
Later: MCP adapter (postponed, after B7); Hydration-proof scanning (postponed,
low priority); Scheduling (beyond M2).

## Feature Specification

Design review here is bounded (user decision, 2026-11-20). This plan
settles only contracts between features, safety and durability rules, and what
the user sees and what it means. Field shapes, mechanisms and exact wording are
decided in each segment's design, where implementation can still choose.
Remaining smaller issues get one triage pass: those that cross features or touch
safety are settled here, and the rest are deferred to the owning segment.

- **Execution retries.** Folded into Same-task retry: retrying a run is a fresh attempt. Retrying a reviewed subset of the same plan is dropped, because idempotent replanning after a partial run already yields only the remaining work for a small new review. Revisit only if rescanning large HDD trees measures as a real cost.
- **Verification retries.** Let users retry terminal verification or verify remaining files, including standalone verification. Same-task retry's routing and close-at-admission rules apply. “Remaining” means what the new attempt finds; the old attempt's candidates and progress do not carry over (user decision, 2026-11-20), which is the simplest model to implement.
- **Same-task retry.** User decisions (2026-11-18, refined 2026-11-19). A retry is a fresh attempt: new scans, plan, review and sessions, with no selection, commitment or authorization carried over. To the user it happens in the same tab, as Inventory Refresh does.
  - **Model.** The in-place model is the priority. It is built from new-task parts: Retry and Edit setup create a new task from the old task's settings, which takes the old task's place in the rail, and the old task closes through the ordinary task Close when the new task's first session is admitted. Old and new are different tasks, so no attempt identity, per-attempt start-response retirement or finished-to-planning transition is needed, and a late control aimed at the closed task gets `not-found`, reported as “already finished”. The three-button alternative (Retry, Plan again in a new task and Edit setup in a new task, always offered and never closing the old task) stays available if the in-place rules prove unworkable: it is that same mechanism without the close, always predictable, but grows tabs and resident plans with every rerun. In place is the default (user decision, 2026-11-20); FEATURES' [Plan Again](FEATURES.md) fresh-task outcome survives only as the secondary “Plan again in a new task” and is reconciled when this design is accepted. Durable task recovery's lineage link keeps Task-Grouped History whole across replacements.
  - **Where it runs.** Every result already says whether the attempt ran. An unrun attempt (a reviewed plan never started, an execution refused at preflight, a canceled scan or plan) changed no files and is rebuilt by planning again, so it always closes at admission; history is irrelevant to it. An attempt that ran closes only while its history is reliable. When its audit degraded, history holds only a committed prefix and the old page holds the only complete per-item account ([HISTORY](HISTORY.md)), so the old task is kept and the new task says why. While any outcome of the old attempt is unknown (lost updates, an unknown control or close result), no retry is offered, because it could overlap work whose result is not yet known. The user does not choose: one Retry, routed by these rules. Plan again in a new task, which never closes the old one, stays as a secondary action for comparing two setups side by side.
  - **When the old task closes.** At admission of the new task's first session. An opened but unsent Edit setup draft, a submitted start awaiting its answer, and a refused start all keep the old task; an unknown start answer keeps it behind the existing recovery fence until resolved. The old plan is closed before the new scan can produce one, so memory stays at one plan per tab.
  - **Availability.** Edit setup is offered while no session of the task is running, pausing or canceling: on finished, paused and held tasks. Otherwise it is disabled with guidance (“Pause or stop the run to change its setup”); scans and plans cannot pause, and use Stop. Opening the draft has no side effect: NamiSync never pauses a run because a form opened. For a paused run (user decision, 2026-11-20): the new task's session is admitted waiting on its predecessor (Session progress and hold reason), so a refused start still costs nothing; then the paused run is canceled. No user action releases that wait: not Resume, Resume all or a relaunch. When the cancel settles, its terminal is recorded in History, the new session becomes an ordinary pending session and the old task closes under the routing above. If the cancel fails, its outcome is unknown or it passes its deadline, the new pending session is canceled instead, which affects no files, and the old task stays. The same applies when the paused run is waiting to resume. The two tasks never both run, and the old one is never left beside a running replacement. Replacing a held or queued committed execution is intended: it was unrun, so it closes at admission like any unrun attempt, after Edit setup's confirmation, and History keeps its admission record (FEATURES' Queue Discard Audit).
  - **Confirmation and notice.** Admission happens server-side after submit, so any confirmation is on submit, and only when something would be lost: when the old task is not safe to close (Task rail batch actions), such as a paused run that could still resume, a reviewed plan whose selection a new plan does not carry, or a held or queued committed execution. Otherwise the new task shows a quiet notice (“Replaced the previous attempt”) with the “Previous run” link when the old attempt ran.
  - **Full rail.** One task slot and its start-response slot are reserved for replacements (user decision, 2026-11-20), so Retry and Edit setup still work on a full rail. Only a replacement may use them; a second replacement submitted while one is still being admitted gets a brief busy refusal. The reserved slot is lent once (user decision, 2026-11-20). If both tasks stay (the old one kept for a degraded audit, or the new one canceled because the old run's cancel failed), the rail is over its bound by one until the user closes a task. Meanwhile new tasks and further replacements are refused with “Rail full: close a finished task”; existing tasks are unaffected.
  - **Back.** The Edit setup draft is page state on the old tab; nothing exists server-side until submit, and the old review stays intact behind it. Back means leaving the draft, or returning after a refused start. After admission there is no back: stopping the new scan leaves a canceled task, and the user edits Setup again from there. An attempt that ran is reached from the new task's “Previous run” link into History.
  - **Dependencies.** The History page, only for attempts that ran, since the app would be closing their only GUI view. Editing Setup before starting needs nothing from History.
  - **Batch actions.** Each task has at most one live session at a time, and Pause all, Stop all and the rail filter act on those sessions. Which tasks a batch action or filter group covers comes from the task's status, not from whether a session is live (user decision, 2026-11-20; see Task rail batch actions): a reviewed plan waiting to start has no live session but is not finished.
- **Edit setup.** Opportunistic, bundled with Same-task retry. Opens a new Setup draft in the same tab, prefilled from the task, so the user can adjust some settings before planning. Nothing is reverted: the draft becomes a new task that replaces the old one at admission, under Same-task retry's rules. Settings are already available: every started plan task keeps a frozen Setup snapshot with the complete options, including filters and the linked-verification choice, in the editable form's shape, even when canceled before an artifact exists. Paths need work: the snapshot keeps only display text and a `location_id`, and the reviewed volume binding lives only in the plan artifact, which a canceled scan or plan never produces. Display text is not authority after drive-letter reassignment ([BUGS](BUGS.md#bug-0167)), and admission by `location_id` fails for locations never executed, which is exactly the first-setup case. The task therefore keeps its admitted bindings on its own process-live record, and one new admission candidate naming a task and side resolves them server-side (the resolution Plan again already uses) into an ordinary choice slot, with the existing offline, ambiguous and changed states. That is one ingress grammar addition under [BRIDGE](BRIDGE.md), one service method and page wiring; inventory roots work the same way. Plan again is then Edit setup followed by an immediate start.
- **Verification open lookahead.** Investigate bounded concurrent first opens within automatic post-copy Verify before changing scheduling. Current serial fresh-file measurements do not establish a concurrency benefit. Preserve ordered classification/recording, honest native readback, bounded handle/buffer ownership and full worker settlement on control; review earlier observation and sharing-lock timing explicitly. Keep Execute→Verify sequential unless a separate workflow redesign is accepted. [PERFORMANCE](PERFORMANCE.md#verification-overlap-scope) owns the scope investigation. This proposal is not implementation authorization.
- **Session cleanup.** Let users explicitly clean up NamiSync-owned session temporary files and trash. Holding volume custody shows that nothing is using the volume now, not that a saved run has given up its artifacts (user decision, 2026-11-20). Cleanup therefore touches only artifacts of runs whose History record is terminal. Artifacts of paused, held, unknown or unrecorded runs are kept and counted (“Kept 3 folders from runs that haven't finished”). Pruned runs keep their summary, so their terminal status survives pruning, and the rule holds before and after Durable work. `.synctrash/<run-id>` is the artifact that clearly needs this. M1's preflight temp recovery already deletes other runs' temps in the touched target folders ([EXECUTOR](EXECUTOR.md)); that stays safe under durable pause only if a paused run owns no temps, which M1's pause at an operation boundary suggests but the design must confirm.
- **Small-file copy batching.** Design grouped parent-directory flushes and grouped ledger commits together. Preserve durability before acknowledging an item, and define how to settle published files after interruption, pause, cancellation or retry. The historical measured-volume saving for directory flushes alone was about 0.22 ms per 4 KiB file. [PERFORMANCE](PERFORMANCE.md) owns the measurement.
- **Unbuffered source reads.** Compare with buffered sequential reads on controlled cold-source workloads; implement only if end-to-end throughput or cache-pressure benefits justify it. Preserve small-file behavior, source admission, exact tail/hash semantics and bounded buffers; reconcile source/target alignment and capability fallback. M1 keeps buffered reads: its repeated-source results and standalone probes do not establish an integrated cold-read gain. [PERFORMANCE](PERFORMANCE.md) owns those observations.
- **Specific I/O errors.** Explain filesystem failures with specific typed causes beyond the generic `IO_ERROR` classification.
- **Hydration-proof scanning.** Postponed, low priority (user decision, 2026-11-20); moved here from [SCANNER](SCANNER.md). The stronger guarantee is that scanning downloads no file content bytes from any cloud provider. Scans already request metadata only and do not trigger OneDrive rehydration in ordinary cases, but directory listing, extra metadata reads and other providers are not covered, and the recall advisory makes no such claim. The study defines the boundary as no file-content hydration attributable to scan access, separately from namespace population and network traffic. It evaluates a metadata-only, no-recall backend across root and ancestor admission, scoped observations, identity fallback and folder mounts, preserving errors, identity, sharing and containment, and verifies online, partially local, local, recall-on-open, virtual-directory, failure and changing-residency cases with provider fetch evidence as well as allocation observations. Adding the no-recall flag to single calls is not partial hardening worth doing alone: it would not cover enumeration, and no recall by scan has been observed. See Microsoft's [attribute definitions](https://learn.microsoft.com/windows/win32/fileio/file-attribute-constants) and [placeholder guidance](https://learn.microsoft.com/windows-hardware/drivers/ifs/placeholders_guidance).
- **Durable task recovery.** Preserve tasks and recoverable session state across application closure or restart. User decisions (2026-11-20):
  - **Recovery store.** A separate SQLite database, the protected recovery-store contract [ARCHITECTURE](ARCHITECTURE.md#m2--durable-sessions-and-queue-ownership) requires. Only the single-instance desktop process writes it. It commits each task's settings and admitted bindings at admission, and records later state transitions as they happen, so holds come back held. It also keeps every reviewed plan, committed or not, with the user's selection, so closing the app loses no review work (user decision, 2026-11-20). Startup reconciliation and the preflight that always runs before the executor acts detect a stale plan. The dispatcher reaches the store through a core protocol that db implements, as with the recorder. A corrupt store or a schema mismatch is rejected; that loses tabs and queue, never evidence, which History keeps.
  - **Paused executions.** A paused execution's continuation (plan, selection, per-operation status, published copy evidence and, during linked Verify, its candidates and progress; [ARCHITECTURE](ARCHITECTURE.md#25-workflow-continuation)) is saved once when it pauses, never per file, and resumes after a restart through the ordinary resume preflight. Resuming keeps linked post-copy verification for files copied before the pause, which Retry's new attempt would not cover. An unstarted execution's continuation is its plan with nothing done, so stored plans and paused state share one versioned format with a bounded check on load. A rejected or mismatched continuation, or a run that crashed while running, comes back interrupted, and Retry continues from there. Before filesystem work resumes, the saved paused state is marked resuming rather than deleted, and it is removed when the run settles (user decision, 2026-11-20); a stored reviewed plan is likewise marked used before execution's first effect. Otherwise a crash after resuming would leave a paused state, or a ready plan, that is behind the files.
  - **Crash, process kill and power loss** (user decisions, 2026-11-20). M1 already keeps files and the ledger never wrong, only behind: the executor flushes file data before publishing, the databases keep SQLite's durable default, custody accepts a mutex abandoned by a dead process, and orphaned temp files are removed. M2's new records each need a launch rule. The rule throughout is that work that was running when the process died is planned again and never resumed; only a deliberate pause resumes. Launch reads the most specific evidence first (user decision, 2026-11-21): the recovery store explains a run before History's missing terminal does, because every valid paused run also has no terminal.
    - A paused state still marked paused: resumable, after the ledger-instance check (Database maintenance gate).
    - A paused state marked resuming, or a stored plan marked used: needs attention with an unknown outcome, offering Retry.
    - A History run with no terminal is only the fallback: it means interrupted, as above, only when nothing in the recovery store explains it, as when the run has no saved record or the store was rejected or lost.
    - Nothing can still be running for an interrupted run once its process is gone, so Same-task retry's unknown-outcome guard, which protects against overlapping live work, does not block Retry. A run counts as interrupted only once its writer is shown to be gone, never merely because the desktop launched: a CLI run may still be writing.
    - A replacement still waiting on its predecessor: dropped; the old task's saved state wins.
    - A restore or migration cut short: each swap is all or nothing, so launch finds either the old database or the new one.

    Process kill and power loss behave alike. Only Windows sign-out and shutdown get the best-effort save under Closing the app.
  - **Launch.** Nothing runs at launch. A committed execution that was queued when the app closed comes back held, as held ones do. Scans, including Browse comparisons, do not start at launch or when the user switches to their tab: a restored task whose content came from a scan shows that it has not been scanned since the restart, with a Scan button. This replaces FEATURES' [Queue Launch Policy](FEATURES.md) CLI flag, reconciled when this design is accepted.
  - **Closing the app.** Today a window close cancels every session and closes only after they settle, without saying so ([DISPATCHER](DISPATCHER.md)). Instead, a close attempt while anything is running reuses Stop all's path: it immediately applies Pause all, then asks for confirmation with counts. On regret nothing further happens, and everything stays paused or held. On confirm, paused and pending sessions keep what the recovery store already holds for them (paused state saved at pause, pending sessions recorded at admission; user decision, 2026-11-24), everything else (running scans and plans) is canceled as today, and the window closes once all have settled, showing what it is waiting for (“Closing: waiting for 3 tasks to stop”). Saved sessions are not canceled. With nothing running, close saves and closes without asking. Windows sign-out and shutdown, including Windows Update restarts (user decision, 2026-11-20), allow no dialog and kill the app after a short grace period: NamiSync pauses and saves what it can in that time, and anything unsettled comes back interrupted. Nothing more can be done there.
  - **Bindings.** On relaunch, Edit setup re-resolves the stored bindings into its existing offline, ambiguous and changed states. Stored bindings are evidence for a new admission, never authority ([BUGS](BUGS.md#bug-0167)). A removable drive that comes back under a different letter is matched by volume identity, never by the letter; one that cannot be matched shows as offline or changed (user decision, 2026-11-20).
  - **Lazy restore.** Launch restores only the light parts: rail tabs, state, paths, settings and pointers. A task's heavy data loads when its tab opens. Before loading it, the store records that the task is opening, and clears that after success. A task whose record is still set at the next launch comes back without its heavy data and says NamiSync closed while opening it, with Open anyway and Close; other tasks restore normally. A process killed for memory cannot clear the record, so one bad task cannot cause a launch loop.
  - **Lineage.** Each task records the task it replaced, under Same-task retry. History holds the link, so Task-Grouped History survives losing the recovery store; the store only refers to it. Every attempt is linked, including attempts that never ran.
- **Command-result retention independent of task lifetime.** Allow routine repeated inventory Refresh, acknowledge and restore without eventually requiring task closure to reclaim command capacity. M1 shares 48 retained start/visibility-response slots across the desktop; task-owned entries survive until Close, so a long-lived inventory task can exhaust capacity for other tasks too. Design bounded retirement of settled results while preserving unresolved original-outcome recovery and preventing retired commands from executing again. Coordinate adapter replay and application receipt ownership; increasing the cap alone does not resolve the lifetime issue. The M1 limit and clean refusal remain unchanged until this design is accepted.
- **Durable queue.** Retain queued work across application restarts. M1's queue has no hold: a pending session starts as soon as its volumes are free. From M2, every queue, durable or not, respects holds. User decisions (2026-11-18):
  - Everything in the queue is visible and acted on without distinction: a task created this session and a durable task inherited from an earlier run both look like pending sessions to Pause all, Stop all and the rail.
  - Held is persisted like any other state and comes back held after a restart. A held pending execution must never return wanting to start.
  - Ownership (2026-11-19): the GUI owns the queue. Queue logic stays in the dispatcher, where FEATURES already places it; the desktop process holds the single queue-owner lock while it runs. CLI runs stay foreground runs outside the queue, still kept off busy disks by the cross-process volume locks, and the GUI shows “Waiting for another NamiSync process” while a CLI run holds a volume it needs. The CLI may be aware of the queue in the same way (user decision, 2026-11-20), but never owns it. FEATURES' [Queue Launch Policy](FEATURES.md) CLI flag is reconciled to this when the design is accepted.
  - Nothing in the queue starts an execution through a path that bypasses or takes over a hold. Every execution is created up front, when the user commits, and waits as a visible, holdable entry. The queue may clear an existing entry to run; it never creates one. [WORKFLOWS](WORKFLOWS.md)' “queue releases may replay” a commitment is read this way and is reconciled when this design is accepted.

  This is a precaution: nothing in M1 starts execution or verification without a confirmation behind it (post-copy Verify runs inside the execution session's continuation), and no planned design requires an exception. Scheduled, conditional and recurring runs are deferred beyond M2 (see Scheduling); any later design must fit these rules or be an explicit, separately reviewed exception.
- **Session progress and hold reason.** User decisions (2026-11-20). A session's lifecycle state alone stood in for two other facts, which produced three gaps: a replacement's hold that Resume could release, a paused run waiting in pending to resume that Pause all, closing the app or Edit setup could take for never started and discard, and a saved paused state left behind the files after a crash. Each session therefore also carries:
  - **Progress:** none, a saved continuation, or unknown.
  - **Hold reason:** none, held by the user (Pause all), or waiting on a predecessor (Same-task retry's Edit setup on a paused run).

  The server derives can pause, can stop and safe to close (Task rail batch actions), and Pause all, Stop all, closing the app and Edit setup classify sessions, from progress and hold reason, never from the state name. A paused execution waiting for custody to resume keeps its continuation: Pause all returns it to paused, not held; closing the app saves it as paused; Edit setup treats it as a paused run; and it is not safe to close. Resume and Resume all release only user holds, and a relaunch restores them as held; only the predecessor's settlement ends a wait on it, and the predecessor's cancel has a deadline after which it counts as unknown. A durable claim that the next effect would make false is withdrawn before that effect (Durable task recovery's resuming and used marks). This includes the new edge from `PENDING` to held that Pause all needs, so it is one core contract change in `namisync/core/session.py`, and the foundation for Same-task retry, Task rail batch actions and Durable work.
- **Completion notification.** Investigate in M2 and deliver opportunistically; it implements FEATURES' [Completion Notification](FEATURES.md). NamiSync has no toasts or tray today. Windows toasts for an unpackaged portable app likely need registration (a Start menu shortcut carrying the AppUserModelID, or Windows App SDK registration), which conflicts with the current no-shortcut, no-registry stance ([INTERFACES](INTERFACES.md)); a spike confirms the requirement and the stance is a user decision. Taskbar flash and taskbar progress need no registration and are the cheaper signal while the app is open.
  - **Spike result** (M2-A2, 2026-11-24; [EV-0040](../evidence/EV-0040/README.md) `notify/`). For an unregistered AUMID, with or without a process AUMID, `CreateToastNotifier` and `Show()` succeed, the notifier reports Enabled and Windows keeps the toast in that AUMID's history across processes. A short-lived per-user `AppUserModelId` registry key (user-approved, removed afterwards) behaves the same at the API level. In a watched test with Do Not Disturb off, the user saw no banner for the unregistered AUMID. A banner did appear for a control under Windows PowerShell's registered AUMID and for the registry-only registration. So toasts need a registration, and a per-user `HKCU\Software\Classes\AppUserModelId\<id>` key with a display name is enough without any shortcut; the user's decision on it follows. Taskbar progress (`ITaskbarList3`, all states S_OK) and `FlashWindowEx` work for an unregistered window at the call level. Clicking a toast after the app has exited still needs a COM activator or a shortcut's launch arguments.
  - **Registration** (user decision, 2026-11-24). The user chooses. A Settings item turns toasts on and writes the per-user key; turning them off removes the key, and the user can do that at any time from the app. With toasts off, NamiSync writes nothing to the registry and still uses taskbar flash and progress. Accepted residual: deleting the portable app while toasts are on leaves the key behind. A note in the release instructions and a CLI equivalent are welcome but cannot guarantee removal either, so the in-app control is the commitment. Delivery reconciles INTERFACES' no-registry stance and FEATURES' Completion Notification.
- **Scheduling.** User decision (2026-11-19): deferred beyond M2, kept as an available future feature. A reviewed plan scheduled for later is usually refused by drift by the time it runs; a conditional run (“when this disk appears”) needs preauthorizing an unreviewed plan; recurring runs need a process that outlives the window, starts itself or lives in the tray. A planning-only reminder avoids all three, because planning changes nothing and still ends in review. Its smallest form needs no scheduler: show how long ago each recent pair or preset last synced, and let presets carry an optional “remind after N days” checked at launch and while the app runs. Due pairs are highlighted; plan tasks are not created unasked.
- **Native Fluent overlay scrollbars.** Integrate WebView2's environment option through the Windows host when the backend work is justified. The current pywebview path needs coordinated startup, early navigation/HTML-loading and rendering-test changes; retain the CSS approximation for M1.
- **Verify-only batches.** Batch standalone verification directories. The current Setup runner admits source/target pairs; extending it to single-directory tasks belongs with a reviewed M2 Setup change.
- **Disk usage view.** Answer “what exists here, and what is taking up space?” for a folder or volume, including target capacity shortfalls and `.synctrash` growth. It is the Storage card's view on the Browse page: an icicle navigator beside a flat one-level table of logical sizes, built from a retained directory-aggregate tree and a listing-only walk. It is read-only, makes no ledger writes, and has no mutation path. [Disk Usage View Detail](#disk-usage-view-detail) records the user's direction, constraints and remaining questions. It is not implementation authorization.
- **Volume overview.** User direction (2026-11-19): the Storage card shows something like Explorer's “This PC” below its path box. Each lettered volume shows its letter and label, space, disk type (SSD, HDD, optical, removable, network, RAM disk), connection (SATA, NVMe, USB, SAS, virtual) and filesystem. Space reads “120 GB free of 1 TB” beside a used-space bar in the progress bar's style, exposed as a meter rather than progress, with the warning color when nearly full. Reusing the progress bar also reuses its indeterminate animation while a drive is still being read, and while a disk usage scan is running. Clicking a row starts a volume-wide disk usage scan. It reads volume metadata only: no scan, no ledger.
  - **Sources.** Already read: `GetDriveTypeW` (drive class), `GetVolumeInformationW` (label, serial and filesystem; root authority keeps the label as evidence) and `shutil.disk_usage` (preflight keeps only free space, but total and used arrive with it). New: `GetLogicalDrives` for the list, and `IOCTL_STORAGE_QUERY_PROPERTY` on a volume handle opened without data access: the device property gives the bus type and removability, and the seek-penalty property separates HDD from SSD. Pulling these through is cheap; the rest is GUI work.
  - **Honest unknowns.** An optical drive without media shows “No disc”. A volume spanning several disks (Storage Spaces, dynamic volumes), or a driver that does not answer, shows “Unknown” rather than a guess. Scheduling treats unknown and USB disks as spinning (Physical-disk scheduling); the label shows only what Windows reports. RAM disks often report themselves as fixed disks and are labelled only when Windows says so.
  - **Bounds.** Each drive is queried independently, off the UI thread, with a deadline: a disconnected network mapping can block for seconds, so it shows “Not responding” while the others render. Network drives are listed, but Disk usage still refuses remote roots and says so. The list refreshes on open and on request.
  - **Spike.** Confirm the queries need no elevation, whether any of them spins up a sleeping HDD, and the per-drive deadline. Result (M2-A2, 2026-11-24; [EV-0040](../evidence/EV-0040/README.md) `volume/`):
    - **No elevation needed.** Every source query, including zero-access opens of `\\.\X:` and `\\.\PhysicalDriveN` and both IOCTLs, works unelevated on all 12 lettered volumes. A removable drive with no media fails the path queries with error 21 and the seek-penalty IOCTL with error 1. So it shows "No disc" when GetDriveTypeW says removable or optical and GetVolumeInformationW fails with 21, and "Not ready" when a fixed drive returns 21.
    - **No spin-up.** A SATA HDD was put in standby with `openSeaChest` and left untouched for 45 s. Every query then answered in under 0.1 ms while an unbuffered read took 8.3 s to spin it up, so none of the queries wakes a sleeping SATA disk. A USB HDD behind a bridge never entered standby, so USB disks remain untested.
    - **Deadline.** Local queries take microseconds (worst single call 0.11 ms; 1.5 ms for a drive with no media), so 3 s per drive is ample. An unreachable network path blocks GetDriveTypeW, GetVolumeInformationW and GetDiskFreeSpaceExW for 13 s to over 120 s, and the call cannot be cancelled. Queries therefore run on daemon threads (a pool worker would hold process exit), with at most one outstanding query per drive and a late answer allowed to replace "Not responding".
    - **Disk type.** The seek-penalty property correctly separated the reference machine's HDDs (SATA, and one on USB) from its NVMe and USB SSDs. USB device strings name the bridge, not the media.
    - **Input to M2-A8.** Every volume on the reference machine has one extent, and no HDD carries two lettered partitions. A8's gate needs such a fixture to be created.
- **New browse page.** User decisions (2026-11-19). One page with two cards:
  - **Browse card.** Answers “what exists in A and B, and how do they differ?” without planning a sync: a title, two path boxes and a row with the button and options, so it stays shorter than Sync's Setup. Difference means existence and metadata only: a file on one side only, a possibly modified version of the same file, or the same. Comparison data always comes from fresh scans, subject to the row limits. The verdict comes from the planner's own comparison, called as a pure function (user decision, 2026-11-20), so Browse never says “same” where Send to Sync would plan an update.
  - **Storage card.** A path box with Scan on one row, then the Volume overview. A path scans that folder; a volume row scans the whole volume (Disk usage view).
  - **Moving between them.** A folder shown on the Storage card can be compared with another on the same page. A comparison can send its paths to a new Sync task's Setup draft, the same prefill Edit setup uses; it never closes the Browse task.
  - **Tasks and pages** (user decision, 2026-11-20). Every started comparison or disk usage scan is a rail task, beside Sync and Integrity tasks, and counts toward the task bound. Pause all and Stop all treat a running one as a scan and leave a finished one alone. Open Browse and Storage tasks are restored after a restart; for them that means only their paths and the ledger switch, under Durable task recovery's Scan button. History and Data are not tasks: like Settings, they are mostly static pages, with their own entry points at the bottom of the rail above Settings.
  - **Ledger access.** An on/off switch on comparisons, off by default. Off, both scans stay in memory and the ledger is never touched. On, the two scans run as ordinary Inventory scans, so last-observed times, last-used paths, evidence status beside each file and checksum adoption come with them. There is no read-only ledger mode: showing evidence against a fresh scan needs Inventory's stale and missing reconciliation, which would be duplicated without its writes. Volume-wide disk usage scans never record.
  - **Row limits.** Display is allowed up to 150,000 rows with an advisory past 120,000: before the scan only when a count is known from a previous recorded scan, and during the scan when the count passes 120,000 (“approaching the limit; a narrower folder avoids a refusal”), without stopping it.
  - **Same disk.** Two scans on one spinning disk queue one after the other under Physical-disk scheduling.
  - **Navigation and new snapshots** (user decisions, 2026-11-22). Inside one snapshot, movement is free: Back, Forward and the breadcrumb move between focused folders of a tree already in memory, and nothing is rescanned. Browse home (the two cards, prefilled with the current paths) acts as the task's setup; Back from it without submitting returns to the current snapshot unchanged, as Edit setup's Back does. Submitting a new snapshot (a rescan, another folder, another volume or another comparison) replaces the task under Edit setup's model, invisibly and without confirmation, since only a rebuildable snapshot is lost. It is a replacement rather than a new session inside the task because each start holds a response slot until its task closes, so repeated glances in one tab would exhaust the slots; the in-task model becomes possible once Command-result retention lands. Each tab keeps one snapshot, released when the new scan is admitted. There is no Back across snapshots: it would either hold up to 150,000 rows per step or start long scans from one click. A canceled new scan leaves “Canceled: Rescan, or go back to Browse”. Two rules differ from Sync's, because stopping a read-only scan loses nothing: Browse home stays available while a scan runs, and submitting from it cancels that scan without confirmation, where Sync's Edit setup stays disabled while anything runs; and a restored task keeps only its paths, under the Scan button above.
  - **Comparison table** (user decisions, 2026-11-22). One merged tree table, not two side by side: two tables compare only when their rows line up, which already makes them one table with a gap, and the merged form needs no scroll syncing and fits Plan's shape through the shared review surface. Rows match by relative path. Columns: Name, Status, A size, B size, A modified, B modified. Status is Same, Differs, Only in A, Only in B, a file-versus-folder mismatch, a name differing only in case, or unreadable. It is a column because color cannot carry it alone, and folder rows show a count such as “3 differences”. A folder present on one side only is one row (“Only in A, 12,345 items”) whose contents appear when expanded. One-sided rows follow the active sort rather than collecting at the bottom; a Status filter (All, Differences, Only in A, Only in B) handles large one-sided sets. Checksums are not a column, since the verdict is the planner's metadata comparison: with the ledger switch on, the collapsible details pane says whether a pair's checksums agree or differ. Column order and row styling are layout choices that stay cheap to change at or after implementation.
  - **Sorting** (user decisions, 2026-11-21 and 2026-11-22). Every table on the page supports sorting, through the shared table component. Which columns sort depends on server and bridge support, as in Plan and Inventory today, where sizes sort and checksums do not. Disk usage's flat table ranks folders by their subtree total, which today's sibling sort cannot do ([What Exists Today](#what-exists-today)). Rows with no value in the sorted column, such as B size on an Only in A row, sort last in both directions.
  - **Snapshots and custody** (user decisions, 2026-11-20). Both cards show snapshots, so the filesystem can change under them; that is intended and harmless because they are read-only, and Rescan gives the current census. A comparison is a snapshot in full: nothing is read again until Rescan. Disk usage keeps only the folder tree and its totals, and lists the focused folder's files from disk, showing “Changed since scan” on a mismatch ([Size](#size)). Full walks, including a rescan of one folder's subtree, wait for volume custody. Listing one focused folder does not: it is a read-only glance bounded by the per-folder entry wall and a deadline, still admitted against the scanned root like any other read, and its drift is already reported. Waiting would hang a finished view for the length of an unrelated sync without preventing any harm. When the filesystem changes under a snapshot (user decisions, 2026-11-22), the view never follows a replaced path: every live listing goes through the scanned root's admission and descendant guards, so a folder replaced by a junction or a file is refused, not entered. It never mixes silently: snapshot totals and live names stay apart under “Changed since scan”. It never rescans by itself, since a rescan is a full walk under custody. It never strands the view: a missing, unreadable or refused folder, including a vanished Back target, keeps its snapshot sizes and shows “This folder no longer exists or can't be read” with Rescan and a way to the parent folder, never an error dialog or an endless spinner. Shell actions on vanished items say the item was not found. Comparisons read nothing live, so only their shell actions are affected, and Send to Sync rescans anyway.
- **Physical-disk scheduling.** User decisions (2026-11-19). Volume custody and the scheduler key on volume serial ([DISPATCHER](DISPATCHER.md#admission-and-volume-scheduling)), so two partitions of one HDD count as different disks and their sessions run at once, fighting over the drive head. That costs speed, not safety: each volume keeps its exclusive lock unchanged. Add a scheduling key per physical disk for spinning disks only, from `IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS`; a volume spanning several disks takes all of them, and SSD and NVMe sessions keep today's concurrency. Disk numbers change across restarts and device changes, including within one session, so they are never stored and are read again at every start attempt, fresh, resumed or restored (user decision, 2026-11-20). Whether a disk spins is stable per volume in practice but is re-read each time, because the query is cheap. User decisions (2026-11-20):
  - **Reading.** The scheduler needs the key before it decides to start a session, which is before preflight. Each session supplies a key-reading callback at admission, and the dispatcher calls it at each start attempt, just before custody, so the dispatcher stays domain-blind.
  - **Unreadable keys.** A volume whose disk extents cannot be read (RAM disks, encrypted containers, some virtual volumes) falls back to today's per-volume custody with a quiet advisory (“Couldn't tell which physical disk this is; it may share the disk with other work”). It is not refused: the key affects speed only, and volume custody still protects every volume.
  - **Spinning or not.** Whatever Windows does not answer, or answers unreliably, counts as spinning: a failed or unanswered seek-penalty query, and every USB disk regardless of what it reports, since many USB bridges do not pass the drive's rotation through. No guessing and no further checks. The worst a wrong answer does is serialize SSD work, thrash a disk or show a wrong label.
- **Drive-type awareness.** The same seek-penalty query, under Physical-disk scheduling's rule that unknown and USB disks count as spinning, informs scans elsewhere: a notice when a scan runs on a spinning disk, separate HDD and SSD time estimates, and possibly parallel folder listing on SSDs, only after measurement shows it helps. HDD scans stay serial.
- **Shell actions.** Copy Path, Open in Explorer and Properties for rows on every page, with optional click-through. Each action resolves a server-owned node id to a path on the host side; the browser never supplies path text. No file is ever launched, and NamiSync performs no mutation. On Plan, side-labelled Source and Target actions avoid an implicit side choice. Missing items keep only Copy Path and Open containing folder. [Shell Actions Detail](#shell-actions-detail) holds the policy and cost notes.
- **Checksum adoption.** Copy content evidence from one location to another for metadata-equal pairs (no-op pairs), so existing duplicate backups gain checksums without hashing. The next Verify confirms or mismatches them. Sync execution is the natural first home: each selected paired no-op already re-checks both live stats against the review and calls `record_noop` ([RECORDER](RECORDER.md)), so adoption would extend that recording as a reviewed, fingerprinted plan option, with the adoptable count shown in review. The Browse card is a second home when its ledger switch is on, behind a counted confirmation because it writes evidence, possibly in either direction. The origin's evidence must be current: its attested stats match its current observation and carry no invalidation. The receiving row must have no evidence; a different existing digest is never overwritten and is reported as disagreement. Recording uses the conditional primitive. Adopted evidence gets a new provenance naming its origin. It never advances `last_verified_at`, and the state stays unverified. Baseline skips it, so Verify is the check, and a later mismatch is labelled as differing from the adopted origin. The row then states what was observed (a metadata match plus the origin's evidence), not that target bytes were read, which preserves never-wrong-only-behind. Adoption may chain (user decision, 2026-11-20): evidence adopted from A into B may be adopted again from B into C, because metadata sameness is already the premise and each step stays unverified until Verify. The provenance names the original origin, the row whose bytes were actually read, plus how many adoption steps the evidence went through, never the intermediate row. Adoption rides on its pair's no-op (user decision, 2026-11-21): it is recorded only as part of a no-op that succeeded, so any filesystem failure or race that fails the no-op's checks (preflight, and the live-stat re-check against review) takes the adoption down with it. Plan and execution already largely enforce this. No change to adoption may relax, bypass or reinterpret those checks, or carry other changes in under them; in Browse, the same live-stat re-check is the prerequisite. Eligibility that changes after review (user decisions, 2026-11-21) covers only ledger evidence changing while the filesystem side still matches, and is rejected in both directions, because adoption acts only on what was reviewed or confirmed and only while it still holds. Each pair's evidence is checked again as it is written, through the conditional primitive: the origin's evidence is still current with the reviewed digest, and the receiving row still has no evidence. Any change skips that pair, including the receiving row gaining any checksum, same or different. A skip is not a failure, because adoption only adds evidence: the no-op is still recorded and the result says “12 adoptions skipped because evidence changed since review”. A pair that becomes eligible after review, such as an origin gaining a checksum, is never adopted, since the reviewed count and the fingerprint cover it. Disagreement found at review is still reported. Both homes call one workflow operation over the db layer's conditional primitive, so they cannot diverge: Browse re-checks live stats as execution already does, its counted confirmation plays review's role, and its write takes the Database maintenance gate's shared claim like any writer. A new `Provenance` value is a core, ledger and history contract change, carried by Schema migration's format versions; data epochs are dropped.
- **User-defined presets.** Create, customize and persist reusable sync pairs and inventory roots that otherwise populate Setup and use availability checks like ledger-derived recent pairs. Persistent records and bridge commands are new work; presets do not retain admission or execution authority. Presets live in a small db-owned config file of their own, beside `settings.json` and outside the ledger and History, with its own format, migration and backup (user direction, 2026-11-23). Whether Recent locations move into it is settled before presets go live (M2-B8).
- **Schema migration.** Delivered by M2-A3: the migration order, format constants, per-database metadata, the open rule, the ledger instance id and the never-reused-id rule with its inventory are now in [DATABASE → Schema Evolution](DATABASE.md#schema-evolution). What remains here is not A3's:
  - **Restore lineage.** Delivered by M2-A4 (user decisions, 2026-11-20 and 2026-11-25): a restored ledger gets a new instance id and keeps the backup's ancestry, and a run is current only inside that ancestor chain ([DATABASE → Ledger instance and ids](DATABASE.md#ledger-instance-and-ids)).
  - **Stale references fail cleanly.** History, the recovery store's bindings, stored plans and, if they stay in the ledger, annotations get not-found instead of a wrong match, and History shows a forgotten location as such, never as another path.

  Missing databases: delivered by M2-A4 ([DATABASE → One database missing](DATABASE.md#one-database-missing)); the History page's display of the boundary follows in B3. The old history is kept and never treated as describing the new ledger, and ledger records are never rebuilt from history. More history than ledger is acceptable, including after a ledger restore. Less history than ledger, after a History restore, is equivalent to History pruning, which the ledger already tolerates. Policy refinements with no open decision: an invalidating step for values that cannot be converted keeps observations and marks attestations unverified instead of resetting; `settings.json` and UI state carry their own versions; and a fixture database saved from every released version (today only v0.1.0) is migrated in tests.
- **Database maintenance gate.** Delivered by M2-A3: the owner, the cross-process mechanism, who holds the claim and what stays outside it are now in [DATABASE → Maintenance Claim](DATABASE.md#maintenance-claim). The earlier accepted residual, that the first migration is unprotected against processes released before the gate, is superseded: migration refuses while any process has either database open (M2-A3). M2-A4 delivered the instance check for plans held in memory and refusal at admission under maintenance. What remains here is for B2 (stored plans and paused continuations) and B3 (refusal that names waiting work):
  - **Waiting work.** Every plan, held in memory or stored, and every paused continuation records the ledger instance it was planned against, and preflight refuses a mismatch (user decisions, 2026-11-20 and 2026-11-24, the in-memory case from M2-A4). Because restore and archive-and-reset give the ledger a new instance id (Schema migration), work planned before them can never record against reused ids. On top of that, restore and archive-and-reset refuse while any reviewed plan, held or queued execution or paused run exists, and name them (“3 queued syncs were reviewed against the current ledger; stop them first”), so the user is not surprised later. The gate alone does not see this work because it is not writing.
  - Maintenance that touches files still takes volume custody through the dispatcher.
- **History page.** The desktop form of the [History Dialog](FEATURES.md) feature: a run list and paged run detail over the existing history readers, with an activity-kind filter, so inventory and later pages need no history page of their own. [INTERFACES](INTERFACES.md) SH-G-9 applies. User decisions (2026-11-19): History storage stays as it is. A reopened run is a static record page, not a revived task: it shows the summary and per-item outcomes it retains (history keeps outcomes, not the plan's review tree), and only the summary once detail retention prunes items. It offers no Retry. “Open in Setup” opens a new task's Setup draft with the run's paths entered as typed paths, admitted by the ordinary checks, and settings at the current defaults, which the page says. Run settings are not stored: storing them would need a schema change and compatibility rules for every later settings change, to save a few clicks. History is permanent, so it would carry those rules forever, unlike the recovery store, which may discard a mismatch. FEATURES' [Restorable Task Setup](FEATURES.md) is narrowed to paths when this design is accepted. Recording location ids for the paths stays negotiable; sync runs already share a `run_token` with the ledger's run row.
- **Task annotations.** Implements FEATURES' [Task Annotations](FEATURES.md#history) over [Generic Annotations](FEATURES.md#files-ledger) (added 2026-11-20). A note attaches to a History run, so replacing a task in place strands nothing, and the lineage link shows the chain. Only the ledger's `annotations` table exists today (`namisync/db/schema.py`); there is no repository, writer path, workflow or bridge command. Because the table is in the ledger while runs live in History, a ledger restore or archive-and-reset would roll back or lose notes on runs History keeps, and after a History restore, reused History run ids could attach notes to the wrong runs. Both favor moving the table to History through Schema migration; decide at design. Where the note box goes is open; History's run detail is the likely first home.
- **Data page.** Location-level ledger management plus database maintenance, without per-record browsing. Each tracked location shows its row count, last scan and verified, unverified, stale, missing and acknowledged counts. Actions: purge acknowledged-missing rows, forget a location (refused or paired with forgetting its mappings while one uses it), and the [Data Protection](DATABASE.md#data-protection) maintenance sessions: check, backup, restore, history pruning and a guided archive-and-reset. Purging is irreversible evidence loss. User decisions (2026-11-19): it asks for confirmation in a modal with the count, like destructive confirmations; the modal need not offer a backup, since Backup is a separate action beside it. It runs as an ordinary maintenance session holding the location's volume custody, so it never overlaps a scan, plan or execution there, and deletes in bounded batched recorder transactions. Forgetting is the user's explicit choice: a later scan that includes the folder records it again, and a preset's filters are the way to keep it out, since exclusions belong to one run. Forgetting is an immediate, non-restorable delete behind the same counted confirmation modal as purge, since it loses more evidence than a purge (user decisions, 2026-11-20); FEATURES' [Soft-Deleted Mappings](FEATURES.md#data-protection) is reconciled to that when this design is accepted. History keeps referring to forgotten locations, by ids that are never reused (Schema migration). Maintenance sessions are not rail tasks: their progress shows on the Data page. Pause all leaves them alone, and a restore never stops mid-swap, so Stop all and closing the app wait for it (user decision, 2026-11-20). Reclaiming file space, purging and pruning take the Database maintenance gate. Restore returns the ledger to the backup's state (user decision, 2026-11-20): evidence recorded after the backup, including mismatches and missing files, is gone until the next scan or Verify finds it again, as with any restored file. The restored ledger gets a new instance id with a lineage link to the one it replaced (Schema migration), so History never resolves later runs against reused ids. That is behind, not wrong, because every attestation is a dated claim. Evidence is therefore shown with its date: Inventory's details already show Last observed and Last verified, which stays as is.
- **Recent locations.** Sync recents are a bounded ledger query (five each) over sync runs that started execution on active mappings; they are not a stored list and do not use history. History is the wrong source, because it stores path text instead of volume identity and has its own retention. Inventory roots have no ledger run row. To study: one ledger-owned last-used record per location and purpose (sync source or target, inventory root, browse), written only by runs, as FEATURES' Run-Derived Recent Locations requires. Planned pairs that never executed are not recorded (user decision, 2026-11-20): Durable task recovery already keeps their reviewed plans across restarts. It is a schema change, so it follows Schema migration. Read-only use of the Browse page (disk usage scans, and comparisons with the ledger switch off) keeps no recents (user decision, 2026-11-19), as the disk usage [Non-Goals](#non-goals) already state; a comparison with the switch on records last-used paths as Inventory does. The write itself would be harmless (one small upsert behind SQLite's single writer, invisible to WAL readers), but it would make a read-only page create and write the ledger, and tie it to Schema migration and the Data page's forget and purge. If they are wanted later, they belong in UI state, not the ledger.
- **Shared review surface.** Plan and Inventory each build their own header, view switcher, status card, table and details pane (Plan composes the table controller directly, Inventory through `tree.js`), and they drifted repeatedly in M1. Examples: switcher labels Plan/Verify versus Sync/Integrity, and differing details empty-state and missing-value text. Build one review component that owns the shared chrome, the table and the details fact list and its states. Pages supply columns, cells, facts, a data source and actions; any deviation is an explicit option. Guard it with a parity test that renders both pages from one fixture against a documented list of allowed differences, plus a static check that pages do not assemble shared parts directly. The gallery shows the real component. It lands before any new M2 table.
  - **One table component** (user decision, 2026-11-19). Two table families exist today and share only base scroll and layout classes: Recent pairs and the batch table are native tables with 56 px two-line rows, five fixed slots and about 40 Setup-specific style rules; the review tables are windowed `div` rows of 24 px with sorting, selection and details. Having two families is itself the defect. Every table becomes one component built on the windowed review substrate, which can also render a few rows; the review chrome is a layer above it. Each instance configures row height and line count, wrapping, columns, sorting (available to small tables too), growth (fixed slots that scroll, or filling the page) and row interaction (a click runs an action, or selects and shows details). The row-action hover and press behavior Recent pairs needed many fixes to get right is solved once in the component. Recent pairs and the batch table move onto it before the Volume overview lands.
- **Custom title bar.** Extend content into the caption area while keeping the native frame (pywebview's `frameless` mode removes it), and move the task view switcher into a SelectorBar-style control beside the title. A framing spike comes before the GUI change and must keep Snap Layouts, resizing from every edge, double-click maximize, Alt+Space, high contrast, mixed-DPI monitors and Mica. The selector itself is small; settle the switcher label drift first.
  - **Spike result** (M2-A2, 2026-11-24; [EV-0040](../evidence/EV-0040/README.md) `framing/`). Feasible on pywebview 6.2.1 with WebView2 SDK 1.0.3856.49, and it needs three host pieces together. First, a `WM_NCCALCSIZE` subclass on the form keeps the frame styles, DWM caption buttons and Mica while content starts at the window top. Second, WebView2's `IsNonClientRegionSupportEnabled` with CSS `app-region: drag` gives drag, double-click maximize and the system menu. Third, a window-region hole in the WebView2 host over the top resize band and the caption buttons lets the form answer HTTOP and HTMAXBUTTON, because over web content the form never receives `WM_NCHITTEST`. With all three, real input moved, maximized, restored and resized the window from every edge and corner, and hovering maximize opened Snap Layouts. Neither WebView2 regions nor the carve alone works. Costs: a Win32 subclass outside pywebview that must recompute the carve on size and DPI changes; WebView2 settings set before the first navigation, which touches pywebview startup as the overlay scrollbars entry also does; DWM buttons that follow the form's dark/light attribute rather than the page; caption-button positions computed by NamiSync because `DwmDefWindowProc` misreports them. Hand checks ([EV-0041](../evidence/EV-0041/README.md), PowerToys quit): Win+Up and Win+Left, Alt+Space from the page and the bar, keyboard Move and Size, and Tab staying inside the page all work, and the user saw no problem with mixed DPI, high contrast or the taskbar. Two defects were traced and fixed in the prototype ([EV-0042](../evidence/EV-0042/README.md)). Switching Windows from dark to light lost Mica because pywebview's own theme handler sets the backdrop to none in light mode; reapplying dark mode and Mica after it on every change fixes it, as M1's appearance observer already does. The caption buttons showed no hover because the host answered their hit tests without passing `WM_NCHITTEST` to `DwmDefWindowProc`, which draws hover; calling it first while keeping the host's own answer restores hover on restored and snapped windows. EV-0042 still had no maximized hover; the follow-up below supersedes its proposed choice between losing hover and drawing replacement buttons.
  - **Maximized-caption follow-up** (2026-11-24; [EV-0043](../evidence/EV-0043/README.md)). Native buttons work with a smaller geometry correction. The maximized `WM_NCCALCSIZE` top inset suppresses DWM hit handling on the reference machine, even at one physical pixel. Keep the client top at the window top instead, and put the off-screen resize-border compensation in WinForms client padding so the WebView starts at the visible work area. Use `WM_GETTITLEBARINFOEX` screen rectangles for the maximized WebView cutouts and honor DWM's handled hit result; the old aggregate-bounds conversion cuts off the lower part of the button region. Recompute padding and carving on size/DPI changes, remove padding on restore, and retain non-client mouse/leave forwarding. The user confirmed all three highlights, lower button edges, Snap Layouts and title-bar alignment through restore/maximize. The refined exact-rectangle carve then passed 15/15 corner/center hit-code and real-input-receiver checks. This supports retaining native drawing; custom caption rendering is not required by the maximized-hover result. It is spike evidence on the named profile, not fresh mixed-DPI/high-contrast/snapped acceptance. A separate existing prototype defect was exposed: two restore cycles grow the height by 52 physical pixels each in both baseline and candidate, including native system-command transitions. Cause ([EV-0044](../evidence/EV-0044/README.md)): WinForms saves the restored bounds as the client size on maximize and converts them back with the stock frame on restore, so every cycle adds the caption and top border that `WM_NCCALCSIZE` removed. It reproduces in a bare WinForms form without WebView2. Clearing the form's private `restoredWindowBoundsSpecified` after `WM_SIZE` maximized lets Windows' own placement stand, and removed the growth in the bare form and in the pywebview prototype. The field is private but stable on the pinned .NET Framework 4.8 runtime; the host design adopts it with a guard or picks a public alternative.
- **Easier exclusions.** Extends FEATURES' [Filter Rule Editor and Filter Exclusion Explanation](FEATURES.md#filters). Plan and Inventory row menus offer “Exclude this folder”, “Exclude this file” and “Exclude files like this”. Each composes a pattern, shows the pattern and its effect before applying it, and starts a fresh plan or scan; a reviewed plan's frozen filters never change. Patterns get plain-language explanations while typing, and presets carry their filters. Inventory has no user exclusions today. Exclusions are temporary and belong to one run, as in Sync, and Inventory's work the same way (user decision, 2026-11-20): during a filtered scan an excluded subtree gets no coverage and is never marked missing; its rows simply fall behind until a scan includes it again. Nothing is stored per location, and a sync recording rows inside a subtree that an earlier Inventory scan excluded is ordinary. Keeping a folder out every time is a preset's job, since presets carry their filters.
- **Drag-and-drop Setup.** Refines FEATURES' [Drag-and-Drop Setup](FEATURES.md#desktop-ui). Each path field is its own drop target, with no guessing of source or target order. One dropped folder fills that field and goes through the same admission as a picker choice. A dropped file shows the existing “not a folder” refusal, and several items are refused with guidance. The paths come from WebView2's native dropped-file objects, received by the host; the page only forwards the drop. pywebview's own drop helper matches paths by bare file name, so NamiSync needs its own bounded host handler instead. A spike confirms folder paths and the elevation boundary.
  - **Spike result** (M2-A2, 2026-11-24; [EV-0040](../evidence/EV-0040/README.md) `drop/`). With drops simulated through DevTools (not yet a real Explorer drag), the page forwards `dataTransfer.files` with `postMessageWithAdditionalObjects`. The host then receives `CoreWebView2File` objects whose `Path` is the full path, for folders, files, Unicode names and a 437-character path. `FileSystemHandle` objects arrive as null through pythonnet. The host can read the item count and message length before parsing, so the bound belongs there. A folder and a file look alike, so the host decides by its own stat before admission, and page-reported names and kinds are untrusted. pywebview reads dropped files only for its own `FilesDropped` message, which NamiSync never sends. Its handler does see every web message, so NamiSync's drop message must be an object, never a three-element list. Real Explorer drags ([EV-0041](../evidence/EV-0041/README.md), runtime 158.0.4370.33) match for folders, a file, two folders, another drive and Unicode names, and change three conclusions. Paths longer than about 260 characters arrive as an empty drop (251 arrived, 312 did not), elevated or not, so an empty drop needs guidance toward Browse. An unprevented drop never reaches `NavigationStarting`: WebView2 hands the item to Windows, which opens it in its default app, so the page must prevent dragover and drop on the whole window, not only on the fields. And an elevated window accepted drops from unelevated Explorer, so the expected elevation limitation did not appear on this machine (cause not investigated). pywebview's handler logs a caught `ValueError` for every NamiSync message, as predicted, which NamiSync must keep out of its log. UNC paths remain unchecked.
- **Task rail filter.** The rail holds up to the task bound (48 today, at most 256 under Task capacity), and batches can fill it. A presentation-only filter by state group (active, ready for review, needs attention, finished), using existing snapshot facts. Each task status maps to exactly one group, by the precedence in Task rail batch actions. It never hides the current task, shows how many tasks are hidden, and resets for newly created tasks. Durable tasks make it more valuable.
- **Task rail batch actions.** A rail context menu first: Close finished tasks, Close other finished tasks, Pause all, Resume all paused and Stop all. Batch Close acts only on tasks in the finished group; closing a running task stays a deliberate single-task cancel-then-close. A finished task whose page holds the only complete per-item account (degraded audit) closes like any other, as it does individually; Batch Close's count names such tasks (“2 of these have item details that History doesn't”) (user decision, 2026-11-20).
  - **Eligibility** (user decisions, 2026-11-20). Bulk eligibility and filter groups come from the task's status, which every task already has, never from whether a session is live: a reviewed but uncommitted plan has no live session and is not finished. Each status maps to exactly one group, with the precedence needs attention, ready for review, active, finished, so Close finished tasks never reaches a plan awaiting review. The server derives three capabilities from status in the interface layer, never in page code: can pause, can stop, and safe to close. Safe to close is false while a task holds a resumable paused run, a reviewed plan (committed or not), a held or queued execution, a page with a degraded audit, or an unknown outcome. It does not change a task's group; it feeds Batch Close's count, the app-close dialog's counts and Edit setup's confirmation.

  User decisions (2026-11-18):
  - **Pause all** stops everything that can stop and starts nothing new. Running execution, Verify and Baseline pause as today. Running scans and plans are left alone: they are usually done in seconds, and pause is not stop. Every session that has not started, of any kind, is held and does not start. Holding is not pausing, so FEATURES' per-kind pause capability still governs running sessions only. This needs a new edge from `PENDING` to held in core's session transitions (Session progress and hold reason): a never-started held session has no custody and no continuation, so resuming it starts it fresh, and the UI labels it as not started rather than implying progress. A paused run waiting in pending to resume has a continuation and returns to paused instead. Pause all is one atomic dispatcher operation. Pausing running sessions one at a time would release their volumes and let the scheduler start queued sessions before they are held. The result reports paused, held, already pausing and still-running counts.
  - **Resume all paused** re-queues paused and held sessions in their original admission order (`admission_order` is already kept on each record). Sessions started while everything was held stay ahead of them. Resume still never preempts. It also resumes runs the user paused individually before Pause all; that is intended (user decision, 2026-11-20).
  - **Stop all** applies Pause all first, then asks for confirmation with a count, like destructive confirmations. Confirm cancels every unfinished session; regret leaves everything paused for an explicit resume. Pausing includes tasks with an Edit setup draft open: Edit setup's rule only means that opening the draft is not itself a reason to pause (user decision, 2026-11-20). Pausing first closes the race window for everything except running scans and plans: if they finish, they are harmless; if not, they receive the blanket stop. No preflight or fingerprint is needed. A late stop must be harmless by contract, not by accident. Finished states have no outgoing transitions and cancel on them returns `illegal-state` without a change; a released session returns `not-found`. Both are reported as “already finished”, and a test names this guarantee. Batch admissions (user decisions, 2026-11-20): a batch only ever starts scans, which are read-only, cost nothing to rerun and are canceled on confirmation if still running; no batch row starts execution or verification. The preferred design pauses the batch runner too, best-effort and page-side: the runner is a serial page loop that already checks before each row whether it may still submit, so Pause all sets a page flag before sending its command, the loop stops before its next row, and unstarted rows stay queued. Resume all restarts the runner for a batch it stopped, and Stop all's confirmation leaves queued rows queued, since they are not sessions. One row already being submitted can still start a scan, which confirmation cancels, and a close dialog the page does not own falls back to the plain race. That plain race is also an acceptable fallback if pausing the runner proves costly: the batch was started before the pause, scans it starts during the dialog are covered by the blanket stop, and the worst case is a count race (the dialog counts x and x+n are stopped). Harm would lie only where execution or verification could start without user confirmation; Durable queue rules that out.

  Same-task retry defines “finished” and which session a batch action targets. A server-side bulk command keeps a full rail within the bridge's 64-exchange bound. Ctrl/Shift multi-select, like browser tabs, is optional later; it needs listbox keyboard and screen-reader semantics, and a selected set distinct from the current task.
- **Stop while checking, scanning or planning.** The review shell shows Checking, Scanning and Planning with no Stop control; Stop exists only for execution, so stopping a scan today means closing the task. Add the existing Stop control there. The scanner already checks cancellation between directory entries, and cancellation releases volume custody at settlement, so stopping should take well under a second. A single blocking Windows call cannot be interrupted, so a sleeping HDD's spin-up or an unresponsive network share can take longer. Planning computation after the scan has no checkpoints, but it does not use the scanned volumes. To measure: cancel-to-release latency on the HDD fixture ([PERFORMANCE](PERFORMANCE.md)). Spike result (M2-A2, 2026-11-24; [EV-0040](../evidence/EV-0040/README.md) `stop-latency/`, CPython 3.13.17 on a loaded machine). On NVMe a cancelled scan raised within 0.4 ms, and volume custody was free 3.6–11 ms at p50 and at most 23 ms after the cancel request (30 warm samples each for inventory, plan source and plan target scans). On the `J:` HDD fixture (130,000 files under `J:\NamiSyncSpike\stop-latency`) custody was free 4.2–11.4 ms at p50 and at most 17.5 ms, with directory metadata already cached. A cold scan of a sleeping disk needs a reboot first and was not measured. Two findings change this entry. Planning has no checkpoints, so a plan cancelled after its scans keeps volume custody until planning finishes and then ends completed with a plan. Planning time also grows faster than the trees: 10 s at 10k/3k files and 41 s at 30k/9k. User decision (2026-11-24): planning is stoppable no later than B6. The planner checks for cancellation in its loops, as the scanner does, so even a pathological stall can be interrupted without taking the session down with it; a plan stopped while planning ends canceled with no artifact and releases custody. The superlinear planning time was not expected; it is investigated, then optimized, under A9. A stopped scan or plan has no artifact, but the task keeps its setup and admitted bindings, so Retry and Edit setup rebuild it in place under Same-task retry.
- **Task capacity and resource policy.** User direction (2026-11-17): NamiSync bounds what it promises, not what users may attempt. Twenty 100k-file syncs are allowed. Keep a task count only as a transport-safety bound, raised from 48 to at most 256 (user preference, 2026-11-19; the value is chosen after profiling) together with the start-response slots, which each open task holds until Close ([INTERFACES](INTERFACES.md)). Raising one without the other only moves the refusal; Command-result retention is the lasting fix. Do not refuse on memory. Instead, inform: the README notes that open tasks keep their plans in memory, and the app shows a quiet notice when open tasks hold many rows, suggesting closing finished ones. Optimize large tasks first. The measured roughly 2.4 GB whole-application peak at 100k entries is about 23 KB per entry, browser included. Profile the plan, presentation projections, view windows and renderer before choosing compact row storage or releasing execution-only state after settlement. [PERFORMANCE](PERFORMANCE.md) owns the measurements.
- **CLI parity.** Make the CLI good by M2. Anything with shell access may commit; NamiSync is not a barrier against file operations that other tools can perform anyway. A plan must still be reviewed, by a person or an agent. Additions:
  - `--json` on every command: event lines and one final result object.
  - `sync --plan-only` prints the plan and one commitment token; `sync --commit <token>` plans again and executes only on a match. The interactive prompt remains for people, and no flag plans and executes unreviewed. User decisions (2026-11-20): the token reuses the existing `Commitment` (`namisync/core/execution.py`), covering both the plan fingerprint and the selection digest, so a commit binds which operations were approved, not only the plan. `--commit` repeats the selection flags, and they must reproduce the token. The digest is taken after dependency closure, so different spellings of the same selection match. No selection flags means every operation, which is also a digest. A mismatch is refused with the difference named (“The plan matches, but this command selects 1,310 operations and you reviewed 1,204”).
  - Per-run plan options matching Setup (`--exclude`, `--preserve-created`, `--preserve-acl`, `--propagate-casing`, `--trash-on-update`), never saved as settings.
  - Partial runs by exact operation id. Ids are deterministic hashes of operation intent, so a fingerprint-matched replan reproduces them. Use `--select-op` and `--exclude-op`, or a file of ids for long lists, with dependency closure applied as in the GUI and the result shown before commit. Kind and path filters cover broader selections.
  - A `settings` command (`show`, `set`); ledger browsing by location without rescanning; acknowledge and restore missing files; the Data page maintenance actions; history filters (`--kind`, `--since`); `verify --run <token>` for a past run's copies; `recent` locations. A command scoped to a run refuses when History can no longer define that scope, and never silently widens it (user decision, 2026-11-20): after pruning, `verify --run` names the reason and the wider command (“Run X's file details were pruned on <date>; to verify the whole destination, run `namisync verify <target>`”). After a degraded audit, History holds only a prefix of the run, so it says how much it covers (“History has 1,204 of this run's 1,310 copies”) or refuses rather than silently verifying less. The History page's run detail follows the same rule.
  - Review output an agent can use. A 100k-operation plan is tens of megabytes, far beyond any model context, so output leads with a sufficient summary (counts and bytes per kind, the destructive breakdown, refusals, filters and options), lists destructive operations in full up to a bound, and writes the complete operation list as JSON lines to a file that tools can query. A harnessed agent reviews the summary and destructive subset, then searches the file as needed.

  Not ported: tree browsing, search and sort (query the JSON instead), batches (shell loops and exit codes), the folder picker, appearance, Plan Again (run the command again) and Pause/Resume (Ctrl+C cancels a foreground run).
- **MCP adapter.** Postponed; study and deliver opportunistically after CLI parity. It would be a thin adapter over the same service and commands, subject to [BRIDGE](BRIDGE.md)'s ingress contract. Read-only and planning tools come first; commitment follows the CLI's fingerprint rule.
- **Progress chart.** Implements FEATURES' [Throughput Graph](FEATURES.md#desktop-ui) together with Status Layout Refinement. The compact bar expands into an Explorer-style chart of transfer rate against progress. The Python adapter already keeps a monotonic sample history for estimates. It would add a bounded, progress-bucketed rate series to the task snapshot (a new internal snapshot version), so a page reload keeps the chart. Pause, a new phase and Gap show as breaks rather than invented rates. Execution and post-copy Verify are separate series.

No further Settings are planned. A setting arrives only with a feature that brings a user choice.

## Disk Usage View Detail

Study detail for the Disk usage view, the Storage card's view on the Browse page.
Merged from the former disk usage study (2026-11-19); its inspected revision was
`ebf72fbe`. Nothing here authorizes implementation or changes a current limit.

### Prompt

Spaceketeer was a Windows disk-usage viewer. It is no longer distributed: its
Store listing is gone, and its website remains without its web apps or contact
links. It scanned a drive or folder and showed a sunburst chart next to a flat,
Explorer-like table with Name / Contents (“N files, M folders”) / Size columns.
The table lists one level only. The sunburst goes a few rings deep, shows
folders but not individual files, and caps how many segments it draws. It
offered Pause / Resume / Rescan, Copy Path, Open in Explorer and Properties.
NamiSync's scanner and inventory already compute most of that data. The
question is whether NamiSync should present it the same way.

### User Goal

The view answers **“what exists here, and what is taking up space?”** Each
view answers a different question:

| View | Question |
| --- | --- |
| Plan / execution | What will change on the target? Rows describe operations, mostly from the target's side, so it is a poor view of what simply exists. |
| Inventory | What evidence do we hold for a tracked location? |
| **Disk usage (Storage card)** | What exists in one folder or volume, and how big is it? |
| Browse card | What exists in A and B, and how do they differ? |

Inside NamiSync the question also comes up without being asked:

- Plan review reports a capacity shortfall on the target, and the user needs to
  know what to clear.
- `.synctrash` and displaced update versions grow on the target. Nothing shows
  how much space they use until a trash retention policy exists
  ([FEATURES → Trash Retention Policy](FEATURES.md#data-protection)).
- Before a first sync, the user wants to see the shape of a source tree.

### Decisions (2026-11-15)

| Question | User direction | Consequence |
| --- | --- | --- |
| Placement | Revised 2026-11-19: one Browse page with two cards. The Storage card (a path box with Scan, then the Volume overview) opens this view; the Browse card compares two locations. | See [Page](#page) and New browse page above. The cards share a page but not their scans, so neither feature blocks the other. |
| Size meaning | Logical (end-of-file) size from `os.scandir`. The small difference from allocated size is tolerated; Properties shows the exact on-disk figure. Probe the known divergent cases before implementation, for rigor. | No new enumeration backend; see [Size](#size). |
| Shape and scale | Spaceketeer-like: one flat level of files and folders, and a few-level chart of folders. | The whole tree is still walked, but only directory aggregates are retained; see [Scale](#scale). |
| Volume custody | Wait. Say so visibly, so the user can choose to pause a sync on that volume. | No new dispatcher custody mode; see [Session behavior](#session-behavior). |
| Chart | Revised 2026-11-22: a partition chart drawn as an icicle; treemap rejected. Each level shows only the largest few child folders above a size threshold, so it stays readable. | Parent totals come from the aggregate tree, so no separate slice-merging pass is needed; see [Chart](#chart). |
| Copy Path, Open in Explorer, Properties | Wanted on every page regardless of this feature. Click-through is nice to have. Plan prefers the target side, but copies and updates point naturally at the source. Missing items get no item actions; their folder can still open if it exists. | Separate proposal (Shell actions above). Side policy is under [Shell actions detail](#shell-actions-detail). |

### What Exists Today

| Spaceketeer capability | NamiSync now | Gap |
| --- | --- | --- |
| Recursive walk of a folder or whole drive | Scanner FULL scan. Volume roots are admissible locations (displayed as “Volume root”). | The sync scanner opens every entry on NTFS to read file identity; see [Size](#size). |
| Per-folder total size | Inventory projection rolls up complete file bytes. Overflow and unknown bytes are explicit, never clamped ([INVENTORY](INVENTORY.md#stage-6-desktop-contracts-protocol-subset-active)). | Requires a ledger-backed inventory. |
| Contents (“N files, M folders”) | Rollup counters already include descendant row and file counts (`inventory_projection._row_counters`). | No column. |
| Largest-first table | Server-owned sibling sort on Size ([PRESENTATION](PRESENTATION.md#search-filters-sorting-and-follow)). | **Folders cannot be ranked by total.** `sibling_order.sorted_siblings` sorts files first, then folders by their own size, not their aggregate bytes. |
| Flat one-level list with drill-down | Bounded tree with expand and collapse. | No flat “focus folder” list or breadcrumb. |
| Chart | None. | New. |
| Rescan | Whole, exact or recursive-folder Refresh. This is already finer than Spaceketeer's. | None. |
| Pause / Resume | Inventory scan is cancel-only (pause unsupported). | Not needed. |
| Copy Path, Open in Explorer, Properties | Copy Path is listed as a future Inventory action. The host already exposes one native call, the folder picker (`interfaces/web/host.py`). | Separate proposal. |

### Why Inventory Is Not the Engine

Pointing the current Inventory at a drive would fail for four reasons:

1. **Population wall.** Inventory admits at most 150,000 rows per population
   ([DEFENSE](DEFENSE.md) capacity policy). The screenshot's `F:` holds about
   422,000 files in about 46,000 folders, more than three times that limit, so
   the scan refuses.
2. **Ledger side effect.** Inventory is durable evidence. A casual space check
   would register a location and write every row. Disk usage belongs outside
   the ledger (feature orthogonality). Untracked ingest sources set the
   precedent: they are scanned in memory, used, and forgotten
   ([FEATURES → Untracked Ingest Sources](FEATURES.md#ingest)).
3. **Ignored artifacts are exactly what eats target space.** The default
   `IgnoreSet` hides `.synctrash`, owned temporary files, `DESKTOP.INI` and
   `THUMBS.DB`. A space scan turns off the trash and temp exclusions (both are
   flags on `IgnoreSet`) and labels those entries as NamiSync-owned.
4. **Unreadable areas are normal at drive scope.** System Volume Information,
   other users' `$RECYCLE.BIN` and `WindowsApps` deny access. The host refuses
   elevated launch, so these areas stay unreadable. They become an explicit
   “unreadable” entry with unknown size, not a failed scan.

The space view therefore gets its own read-only workflow: a new entry point that
uses the scanner module and a pure projection, with no recorder or ledger. The
shared `visible_sequence.py`, sibling ordering and windowed table renderer are
reused. A folder-total sort and Contents column could later be added to
Inventory too, but that is a separate change to the DR-BR-15 sort contract.

### Page

The view puts a chart beside a table (user decisions, 2026-11-22), because
height is what browsing needs most and the table is narrow. The layout is
cheap to change at or after implementation.

- **Chart:** a vertical icicle rooted at the focused folder, with depth
  running left to right and sizes top to bottom, about 4 levels of roughly
  90 px each. Folder names run horizontally inside each block; blocks too short
  for a line rely on hover. Clicking a block focuses that folder. Below a width
  threshold the chart collapses behind a toggle rather than switching
  orientation.
- **Table:** a flat table of the focused folder's direct children. Columns:
  Name, Size (with a “% of parent” bar) and Modified, plus Contents while the
  width allows; Contents is the first to drop. Folders are listed first by
  default, or mixed with files when sorted by size. Double-clicking a folder
  focuses it, as Explorer does.

A breadcrumb above both re-roots the view, and Back and Forward move between
focused folders (New browse page's Navigation). Hovering a block highlights its
table row, and the reverse. The table is the accessible source of truth; the
chart is a navigator.

### Size

Size is logical (end-of-file) size, the figure Explorer's Properties dialog
shows as “Size”. The Properties action gives the exact “Size on disk” when a
user needs it.

- **No per-file opens.** On Windows, `os.scandir` returns size, modification
  time and attributes from the directory listing itself; `DirEntry.stat()`
  needs no extra call for them. File identity and link count are not in the
  listing. On NTFS the sync scanner therefore calls `lstat` for every entry,
  which opens each one (`modules/scanner.py`, the `entry.stat` /
  `self._backend.lstat` fallback). A space walk needs no file identity, so it
  reads listing data only. Directories still get identity for loop defense:
  about 46,000 opens on `F:` instead of about 468,000. Skipping file opens also
  avoids the per-file cloud-recall question
  ([SCANNER → Cloud availability](SCANNER.md#cloud-availability-and-hydration-boundary)).
  Whether this is a scanner mode or a separate walk is an implementation
  choice. The sync scanner's behavior does not change.
- **Accepted consequences:**
  - Hard links are counted once per path, as in Explorer's “Size”.
  - Online-only cloud files show their full logical size. Their row already
    carries the cloud indicator.
- **Probe before implementation.** For rigor, measure logical size against
  allocated size, and check that directory-listing sizes match `lstat`, on
  these cases:
  - a file being written (NTFS updates directory-entry sizes lazily);
  - NTFS- and WOF-compressed files;
  - sparse files;
  - block-cloned (ReFS) or deduplicated files;
  - tiny files stored inside the MFT;
  - hard links;
  - online-only cloud placeholders.

  Record results in PERFORMANCE. A surprising divergence reopens this decision.
- **Volume summary.** For a volume root, the view shows used space from
  `GetDiskFreeSpaceExW` next to the scanned total. Used space minus the walked
  total is shown as one “Not scanned” entry (user decision, 2026-11-20): it
  covers what cannot be walked (`WindowsApps`, other users' recycle bins, page
  and hibernation files that deny access) and what NamiSync chooses not to
  walk. The two figures use different units (allocated versus logical), so the
  entry's details say it also includes the difference between file sizes and
  space on disk, and a negative remainder shows no size instead of a number.

### Scale

No Windows API returns a folder's recursive size. Explorer's Properties dialog
walks the tree itself, and reading the MFT directly needs elevation, which a
Store app would not have had. Spaceketeer almost certainly walked too. The walk
is unavoidable; what matters is what gets retained.

- **Retain directories only.** Keep a compact aggregate tree: one entry per
  directory with its parent, name, and subtree totals for files, folders and
  bytes. Also keep each directory's direct-file count and bytes. Memory then
  grows with the number of directories (about 46,000 on `F:`), not the number
  of files. The chart needs only this tree.
- **Read files when a folder is focused.** The flat table re-enumerates the
  focused directory's direct entries. Its folder rows come from the aggregate
  tree. If the fresh direct-file total differs from the scanned one, the header
  says “Changed since scan” and offers Rescan for that folder, instead of
  silently mixing two snapshots.
- **Bounds.** Directory count and direct entries per directory each need a
  wall, sized from measurement (directory-heavy shapes such as `node_modules`
  matter). The table still serves 1..256-row windows over a server-sorted
  directory. A single folder holding more than 150,000 entries is realistic
  (machine-learning datasets, one-file-per-message mail stores, log dumps), so
  the per-folder wall is not a refusal (user decision, 2026-11-19): past it,
  the listing keeps only the largest few thousand files, in memory bounded by
  that count, plus a summary row (“and 1,170,000 smaller files, 40 GB”). Size
  order stays correct; name order is unavailable past the wall, and the header
  says why.
- **System volume** (user decision, 2026-11-20). A volume-wide scan never reads
  the Windows folder (resolved with `GetWindowsDirectoryW`, not a fixed path);
  its space falls into the volume summary's “Not scanned”. Walking it would
  cost about as much as `AppData` on a typical installation; it is skipped for
  its low utility, since acting on its contents is generally a bad idea.
  Program Files is walked. Everything else is walked too, including large `AppData`
  trees, which many users will want sized: a long walk the user chose and can
  stop, within the display policies above.
- **Measurement first.** PERFORMANCE should record walk time and peak memory on
  a large real volume (the screenshot's `F:` is a good profile), comparing the
  listing-only walk with the sync scanner's per-entry `lstat`.

### Chart

The chart is a partition of the focused folder's subtree (user decisions,
2026-11-22). A sunburst and an icicle draw the same partition and differ only
in layout: the icicle compares lengths on a common baseline, keeps labels
horizontal and has no thin outer wedges, so it is the shape drawn. A treemap is
rejected: it needs another layout algorithm, its areas are hard to compare, and
its one strength, showing files, is the table's job. Drawing is cheap:
hand-written SVG rectangles, with no third-party chart library. That keeps the
packaged-document and closed-asset rules intact.

- **Server layout, top children only.** Lay the chart out on the server from
  the focus folder, about 4 levels deep.
  - In each level, draw only the largest *N* child folders (about 5) whose share
    passes a threshold (for example 2% of the focus folder).
  - Each parent's total comes from the aggregate tree, so everything not drawn
    is simply parent total minus drawn children. That remainder includes the
    parent's direct files and every small or unranked folder, and it appears as
    a neutral block, much as Spaceketeer left it unfilled.

  No separate merge pass exists, and the payload size is fixed by
  *N* × depth.
- **Accessibility.** The chart is `aria-hidden` and supplementary. The table,
  breadcrumb and keyboard focus carry the same navigation. Forced colors use
  system colors with outlines.
- **Palette (open).** Spaceketeer gave each top-level branch its own hue. That
  conflicts with NamiSync's reserved semantic hues
  ([FEATURES → Semantic Color Channels](FEATURES.md#desktop-ui)). The proposed
  default is a single accent or neutral lightness ramp by depth, with the
  hovered or focused path emphasized. A categorical palette needs an explicit
  product-author decision.

### Session Behavior

- **Waiting for a volume.** A space scan, being a full walk, takes ordinary
  volume custody and queues behind any session that holds the volume. Listing
  one focused folder takes none (the Browse page's Snapshots and custody). While waiting, the view
  names the blocking task (with a link) and says: “Waiting for *task* to finish
  on F:. Pausing it lets this scan run now; it resumes after the scan.” This
  matches existing behavior: pausing releases custody, and a resumed session
  re-enters the back of its volumes' queue
  ([FEATURES → Resume Never Preempts](FEATURES.md#dispatcher)). The dispatcher
  stays domain-blind; the adapter maps the blocking session to its task.
- **Cancel and Rescan, no Pause.** A read-only scan has no continuation worth
  keeping.
- **Settled-only first.** The chart appears when the scan completes, matching
  inventory's no-partial publication; until then the progress bar's
  indeterminate animation shows the scan is running. A progressive chart is a
  later option.

### Shell Actions Detail

The cross-page Shell actions proposal above is consumed by this view. The
remaining work is mostly policy. The plumbing is modest.

- **Plumbing.** The folder picker is already a host-side callable injected into
  the web adapter. Each action follows the same pattern: a bridge command
  carries a server-owned node id, the server resolves it to a path, and a host
  callable acts. The browser never supplies path text. Primitives:
  - Copy Path: host clipboard.
  - Open in Explorer: `SHOpenFolderAndSelectItems`.
  - Properties: `SHObjectProperties` on a COM-initialized (STA) host thread.
  - Never `ShellExecute` “open” on a file: that would launch it.

  Each command needs BRIDGE ingress bounds and a DEFENSE note for the new
  external effect.
- **Plan side policy (proposed).** Plan rows can describe two paths. A silent
  default makes copies point at the source and everything else at the target,
  and that is the confusion to avoid. The proposal is to never choose
  implicitly:
  - The row menu shows explicitly labelled actions, “Source: Open in Explorer”
    and “Target: Open in Explorer”.
  - Each label is offered only when that side's path exists now. For example,
    a planned copy has no target file yet, so it gets “Target: Open folder” if
    the parent exists.
  - Move rows label the previous and new paths the same way.
  - Plan has no double-click shell default, and neither has the Browse card's
    merged comparison table, which labels its A and B actions the same way.
    One-sided views (Inventory, Disk usage) may use double-click, because the
    side is unambiguous.
  - Disk usage is the exception for folders (user decision, 2026-11-22),
    because it is the only flat table: double-clicking a folder focuses it
    inside the view, and opening the folder in Explorer lives in the context
    menu. Its files keep the same double-click as other one-sided views.
- **Changed drive letters** (user decision, 2026-11-20). Open in Explorer and
  Properties first compare the drive's current volume identity with the scanned
  root's, one Windows call. On a mismatch they use the volume's current letter
  if it can be found, and otherwise say the drive is not connected. Otherwise,
  after a USB letter swap, they would open the same path on whichever drive now
  has that letter. This is a check, not Edit setup's full re-resolution. Copy
  Path keeps the cached text, which is harmless and works offline.
- **Missing items.** Missing items get no Open or Properties actions; “Open
  containing folder” appears when the parent exists. Copy Path stays available,
  because the text is harmless and useful for finding the file. This is a
  proposed refinement of the user's rule.
- **Mutation boundary.** Explorer and the Properties dialog let the user change
  files outside NamiSync. That is the user's own action, as with any Explorer
  use. NamiSync performs none itself and adds no delete, move or cleanup path.

### Non-Goals

- No delete, move, or cleanup from this view. Mutation inside a managed root
  stays pipeline-only (plan → preflight → execute).
- No ledger writes, recents, history runs or background or scheduled scans.
  Checksum adoption belongs to sync execution and to the Browse card with
  ledger recording on, not to this view.
- No elevation and no MFT or USN reading. The future
  [Change-Journal Scanning](FEATURES.md#scanner) protocol is the lawful route
  to faster rescans.
- No duplicate finder (content dedup belongs to ingest) and no network shares
  (remote roots are refused by admission).

### Open Questions

1. Chart palette: depth ramp (proposed) or a categorical palette.
2. Whether the Plan capacity link (“See what's using target space”, opening
   this view on the target with `.synctrash` highlighted) belongs in the first
   slice or later.
3. Level count, *N*, the threshold and the chart's collapse width. Tune these
   on real volumes.
4. Wall values, after measurement.

### Suggested Slices (Not Commitments)

1. Size-case probes and the walk measurement (listing-only versus per-entry
   `lstat`), recorded in PERFORMANCE.
2. Read-only space workflow, aggregate tree and view:
   - flat table and breadcrumb;
   - trash and temps visible and labelled;
   - unreadable and not-accounted-for entries;
   - visible wait-for-volume notice.
3. Icicle navigator.
4. Shell actions on every page (separate proposal; can ship before slices 1–3).
5. Plan capacity link.
