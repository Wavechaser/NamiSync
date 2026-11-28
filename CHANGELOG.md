# Changelog

This file is the detailed task history. Entries are newest-first and use three
levels: `##` for a milestone or released version, `###` for a phase, and
`#### task (YYYY-MM-DD)` or `#### task (YYYY-MM-DD – YYYY-MM-DD)` for a
task-level delivery. The date or date range covers the summarized delivery;
related sessions and commits stay under one task. Before adding a new task,
first decide whether the session advances an existing one; extend that entry
when it does, and create a new task only when no existing entry accurately fits
the outcome. Put post-delivery work in the relevant hardening phase rather than
appending it to the original feature task. `README.md` repeats only milestone
and phase summaries; update its synopsis only when one of those summaries
changes.

Before named releases, milestone headings use names such as `M1`. After
versioning begins, headings use the version and codename, such as
`v0.1.0 "Gertrud"`.

## M2

M2 makes NamiSync lasting and legible: what it did, knows and was doing survives
restarts, crashes, restores, retries and schema changes, and is shown honestly.

### M2 Segment A

Safe-to-change-the-databases work: guards and foundations that land before the
first schema change. M2_PLAN owns checkpoint scope and gates.

#### Physical-disk scheduling (2026-11-27)

- Delivered M2-A8. Tasks whose folders sit on the same spinning disk now run
  one at a time instead of fighting over the drive head, even on different
  partitions; the next starts as soon as the previous ends. Tasks on SSD and
  NVMe drives still run together. The disk is read again at every start, so a
  changed drive letter is followed.
- When the disk cannot be identified, as for network, mapped and `subst`
  drives, the task is never refused; it is scheduled as before. Ordering
  holds within one NamiSync process; a desktop task and a CLI run on one disk
  can still overlap.
- Fixed BUG-0325: an inventory or integrity task whose drive had moved to a
  new letter ran unordered; it is now ordered by the disk at its current
  letter.
- The drive-letter list now comes from core and is shared with inventory's
  volume resolver. A task still at its recorded letter no longer lists every
  drive letter on each scheduler pass, and its volume is looked up once.

#### Pause all and Resume all (2026-11-27)

- Delivered M2-A5. The task rail header has Pause all and Resume all, with a
  notice counting what each did. Pause all asks every running task that can
  pause to pause and holds every waiting one; tasks that cannot pause keep
  running. Resume all releases every paused task in the order it was admitted,
  behind tasks started meanwhile. Each is a single point-in-time action, not a
  mode.
- A held task is paused before it ever started and reads "Paused, not
  started"; stopping it ends it canceled without having run. Task pages now
  take Pause, Resume and Stop from what the server says the task can do.
- Fixed BUG-0322: a Stop accepted while a run was pausing could be lost if the
  run was resumed before it finished pausing, and the run carried on.
- Fixed after closing review: a resumed run that failed before running again
  said execution did not start, though files had already been copied
  (BUG-0323); Pause all could let a waiting task start while it waited
  (BUG-0324); a resumed run that failed before running again lost the work
  its earlier attempts finished from History, now kept even when its error
  message is too long to show, and a ledger that then refuses to finish the
  run now reads as degraded recording (BUG-0327); Pause all
  now acts at one moment when a task is resumed or added while it waits
  (BUG-0328); and a task waiting to
  start read as scanning or running, now "Waiting to start" (BUG-0326).

#### Database maintenance commands (2026-11-25 – 2026-11-27)

- Delivered M2-A4. `namisync check`, `namisync backup` and
  `namisync restore {ledger,history} BACKUP` work on the database pair as
  found, under both exclusive maintenance claims; they never migrate or create
  a database. Backups keep the newest three per database, and migration
  backups are never rotated.
- Restore backs up the database it replaces and copies the image in place when
  that database is intact. A damaged one is renamed aside, kept, and needs
  every NamiSync process closed. A restored ledger gets a new instance id and
  keeps the backup's ancestry; History marks runs outside that ancestry as
  belonging to an earlier ledger. A ledger backup copied into place by hand is
  refused with direction to `restore`.
- A sync plan records the ledger instance it was planned against, and
  execution refuses a mismatch before any filesystem change.
- A session started while maintenance holds the claim is refused at admission
  with nothing stored. The desktop shows it as the fixed bridge error
  `database_maintenance`; the CLI exits `3`.
- A pair with one database missing is completed by an explicit step at desktop
  startup or a mutating CLI command, with a notice. A lone History gains a new
  ledger with a recorded boundary.
- A v0.1.0 History's runs are stamped with a ledger's instance only when the
  same operation migrated that ledger (user decisions after a recurrence
  pause); otherwise they show as an earlier ledger.
- Damage refusals now point to `namisync check` and, given a backup, to
  `namisync restore`.
- Gate on `78246b75`: maintenance is refused while another process writes, a
  writer is refused during maintenance, and a plan made before a restore is
  refused at start, each through the real command with child processes;
  restore kill trials leave the old or the new database; 7310 ordinary tests
  pass apart from the seven known interpreter-bound failures; 13 import
  contracts hold. Each of the six outcomes had an independent adversarial
  review. What is left for B2 and B3 is in M2_PLAN.

- Fixed six findings from a review of M2-A4.
  - A database with foreign key violations is no longer backed up, so such a
    copy cannot rotate out a backup that restores; restore renames that
    database aside instead of overwriting it.
  - A plan made with no ledger no longer reads one that appears while it
    plans.
  - Rotation never removes a live database, whatever its name.
  - A run's History stamp is read again under History's claim, and admission
    is refused if the ledger was replaced in between.
  - Guidance for a pair selected with `--database` or `--history-database`
    ends with those options.
  - A restore that stops after moving only sidecars names the files it moved.
  - Also: `check` validates paths before looking for folders, and the CLI
    decides its closing lines from the result instead of the guidance text.
- Withdrew the `migrated-released` lineage marker under DEFENSE §2.5.4's
  revised policy for the v0.1.0 import; the same-operation rule above replaces
  it, and ledger schema 5 was amended back in place. The CLI and desktop now
  upgrade or complete a pair through one operation. A ledger can be restored
  beside a damaged, unreadable or v0.1.0 History, so either damaged database
  can be repaired first. The update notice no longer says whether History's
  runs were stamped.
- On `e1f40f63`: 7326 ordinary tests pass apart from the seven known
  failures; 13 import contracts hold. Each change had an independent review.

- Fixed eight further findings from the user's review of M2-A4.
  - A reset direction names only the database that needs it, by path, and
    says to keep the other. An empty History beside a healthy ledger no
    longer brings advice to delete both.
  - A run holds the ledger's shared claim, taken before its stamp is read,
    until its observer closes. Maintenance naming the same ledger with
    another History is refused while the run lives. This replaces the re-read
    above.
  - A paused baseline, verify or rebaseline run refuses to resume after the
    ledger was replaced, with direction to start a new run, instead of
    reporting its earlier items as done.
  - A missing database is created only when the caller permits it, checked
    under both claims. A `--location-id` command never creates one, even
    when the file vanishes after its first read.
  - The v0.1.0 History step owns its stamp and requires every run to carry
    exactly the id given; the generic migration engine no longer knows it.
  - A `history` refusal repeats exactly the database options given. With
    only `--history-database`, it says a sync or inventory command must also
    name that History's ledger.
  - The replaced-ledger refusal tells the CLI user to rerun the same sync
    command.
  - Pasteable database paths double every character PowerShell reads as a
    single quote, tested through the parser of PowerShell 7 and 5.1.
- A desktop startup refusal keeps its message, with database paths and the
  recovery direction, in the GUI log (user decision); an ordinary startup
  logs no paths.

- Fixed five findings from a third review of M2-A4 and the items left open
  by the second.
  - A sync run planned before any ledger existed is bound to the ledger its
    first recorder opened. A resume after that ledger was replaced is refused
    like any other replaced-ledger plan, instead of recreating the run and
    reporting both phases completed.
  - A database path equal to the other database's `.claim`, `-wal`, `-shm` or
    `-journal` path is a configuration error before any file is opened.
    Taking a claim used to create the other main there, and a History at the
    ledger's `-wal` path damaged the pair.
  - A claim refusal met while creating a first pair is reported as a refusal
    with its retry message and exit `3`, not as a failed initialization.
  - `check` states what each database is and leaves the recovery action to
    the pair decision, so swapped paths no longer bring advice to delete an
    empty ledger. An unsupported database beside one that must be repaired
    first is told so.
  - Wrong-role and live-backup refusals no longer say "Nothing was changed.",
    which was false after a successful restore.
  - The direction to discard both databases names each by path.
  - A database path that cannot be written as it is, to the stream in use, is
    described instead of being quoted as an option to paste.
  - The desktop inventory review labels a row from the ledger after a run
    that failed, was canceled or was refused, including a resume refused for
    a replaced ledger. The run's own result stays in Details, marked as the
    run's; per-item errors and cancellations stay on the row. The integrity
    context carries the released run's outcome for this.
  - The dispatcher closes the audit observer when the event hub refuses its
    configuration.
- On `0ce55b6f`: 7392 ordinary tests pass apart from the seven known
  failures; 13 import contracts hold. Each of the five commits had an independent review; two needed corrections, which the
  same reviewer confirmed.

- Creating a first database pair holds both exclusive claims until the pair
  is published, and admission checks for a held claim before it reports a
  pair as unusable (user decision). Three commands started at once on a fresh
  pair used to leave the two that lost with `inconsistent-pair` or
  `database-unavailable` and exit `4`, once with a missing-History message;
  they now exit `3` with the claim's wait-and-retry message, sync planning
  included (`Planning refused:`). A restore caught mid-copy is reported the
  same way instead of as `database-unavailable`.
- A session's observer takes both shared claims before it opens either
  database. A History restore that began after a run was prepared used to
  fail the History open as an ordinary audit failure, so the run was admitted
  with degraded audit and ended with exit `4` or `7`; it is now refused at
  admission with the maintenance retry message and exit `3`.
- Closed M2-A4 (user decision). Two findings from its closure review stay
  open in BUGS and did not hold it: a command's cold database validation can
  fail beside another process writing the ledger (BUG-0320), and a History
  path inside the ledger's own path is refused only after a directory and
  claim files are created (BUG-0321).

#### Maintenance claim and schema migration (2026-11-25)

- Delivered M2-A3. A database written by v0.1.0 now migrates to the M2 schema
  (ledger 5, history 9) the first time the desktop starts or a mutating CLI
  command runs. Every row and id is kept, a verified backup is published beside
  each database first, and one transaction per database makes a failure a
  rollback and a refusal. A newer database, and a swapped or unknown role, are
  refused without reset guidance. The `history` command never migrates.
- Added the cross-process maintenance claim: writers hold it shared, schema
  creation and migration hold it exclusive, and a killed process releases it.
  Migration also refuses while any process has either database open, which is
  how a running v0.1.0 is seen.
- Each database now states its role, schema version and the versions of the
  formats it embeds, replacing the contract id and data epoch. Seven shared
  formats have constants in `namisync/core/formats.py`, pinned by literal
  known-answer vectors. The ledger carries an instance id, each history run
  records the ledger instance it ran against, and `locations`, `mappings` and
  `inventory` never reuse an id.
- Saved a database pair written by the released v0.1.0 binary under
  `tests/assets/v0_1_0/`, with provenance and a rerunnable producer that
  refuses the live data root.
- Gate (EV-0045): the fixture migrates and reopens as ready; a migration killed
  during backup, copy, commit or close left the old or the new database in all
  15 trials, including a 400,000-row ledger, and the next start finished it;
  7079 ordinary tests pass apart from the seven known interpreter-bound
  failures; 13 import contracts hold. Each outcome had an independent
  adversarial review. Limits and what M2-A4 inherits are in M2_PLAN.

- Fixed five findings from a later review of M2-A3. The CLI now checks a
  command's roots, `--path` values and database placement before migrating, so
  a refused input migrates nothing. A newer or wrong-role database is no longer
  answered with the direction to discard both databases. History refuses a run
  reopened under a different ledger instance. The backup temporary is created
  exclusively, and the fixture producer's prompt wait is bounded.

- Fixed two more M2-A3 review findings. Pair admission reads a database that
  needed a reset once more before advising to discard both, so a pair that
  became healthy meanwhile is not told to. Workflow admission no longer
  migrates: only the CLI's and the desktop's explicit step does, so every
  migration is announced.

- Adopted DEFENSE §2.5.4, the policy for findings about migrating a v0.1.0
  database, and gathered the migration limits into one list in DATABASE.
- Cold admission now identifies a database SQLite reports as damaged and
  directs the user to keep both databases and their sidecars for inspection.

#### Spikes for M2 designs (2026-11-24)

- Ran the M2-A2 live checks and recorded each result in its M2_PLAN feature
  entry, with probes, raw samples and reports in EV-0040. Volume overview
  queries need no elevation, answer from memory without waking a sleeping SATA
  HDD, and need a per-drive deadline because unreachable network paths block
  for over a minute. Content in the caption area is feasible with a native
  frame. WebView2 hands the host full paths for dropped folders. Toasts need a
  registration, and a per-user AppUserModelId key is enough. A cancelled scan
  frees volume custody within about 20 ms, but planning cannot be stopped and
  keeps custody.
- Ran the desktop checks with the user (EV-0041). Real Explorer drops deliver
  full paths up to about 260 characters and nothing beyond, reach an elevated
  window, and open in their default app unless the whole page prevents them.
  The framing prototype passes the keyboard, mixed-DPI, high-contrast and
  taskbar checks. Its two defects were traced and fixed in the prototype:
  pywebview's theme handler turns Mica off in light mode, so the host
  reapplies it after every change, and caption-button hover needs each hit
  test passed to `DwmDefWindowProc`, which in that revision still declined
  maximized windows.
  M2-A2 is complete.
- Investigated maximized caption hover and clipping (EV-0043). Keeping the
  non-client top inset at zero restores native DWM handling; client-side
  padding keeps the page visible, and exact native button rectangles correct
  the WebView cutout. The user confirmed hover, Snap Layouts and alignment;
  all 15 final button corner/center checks passed. Native buttons remain
  viable without custom rendering. A separate restore-height growth reproduced
  in both old and new prototypes is recorded for later host work.
- Traced that restore-height growth to WinForms (EV-0044): on maximize it saves
  the client size and on restore converts it back with the stock frame, adding
  the removed caption and top border each cycle. It reproduces without WebView2.
  Clearing the form's saved restore record after maximizing removed the growth
  in a bare form and in the pywebview prototype.
- Recorded the user's decisions on two results: toasts become a user-enabled
  setting whose off state removes the registry key, and planning becomes
  stoppable no later than M2-B6, with planning time profiled under M2-A9.
- Reordered M2 checkpoints: the maintenance claim moves into M2-A3 with
  migration as its first consumer, M2-A4 adds the ledger-instance check for
  plans held in memory, and M2-C1, C3 and C4 each own one restart scenario.

#### Guard live production data from source-tree work (2026-11-24)

- Default to `%LOCALAPPDATA%\NamiSync-Development` for every run except the
  frozen release in both resolvers, `AppPaths.production` (GUI) and
  `default_database_paths` (CLI), which stay separate owners. The opt-in is an
  explicit `--data-dir`, `--database` or `--history-database` path. The
  development GUI launcher's shell profile now uses that root itself instead of
  its `shell` subfolder; existing data is neither moved nor deleted.
- Install a session-wide audit hook in `tests/conftest.py` that refuses any test
  operation able to create or change an entry under the live root, found from
  the Windows known folder rather than `LOCALAPPDATA`. Child processes rely on
  the source-checkout default; `ctypes` calls are not guarded. Every refusal is
  recorded and fails its test even when product code swallowed the exception.
- Give the default development root its own desktop identity
  (`Local\NamiSync.Development.Desktop`, `NamiSync [Development]`, as
  `tools/desktop/gui.ps1` uses), so `namisync-gui` from source and the
  development shell cannot run on one root together. The identity follows the
  resolved root, however reached (default or `--data-dir`, frozen or not); every
  other root, including the live one, keeps the production identity. The headed
  SH-G-2 test now compares both real data roots and refuses to run while a
  desktop mutex exists, while another starts, or before the roots settle.
- Prove both: guard cases against the real hook and a tmp root, resolver
  agreement under frozen and source runs, and a subprocess `inventory` that
  writes only beneath the development root.

### M2 Planning

Documentation servicing and delivery planning before implementation starts.

#### Start M2 documentation (2026-11-23)

- Archive the completed M1 delivery register as `docs/obsolete/M1_REGISTER.md`
  and rename the M2 proposal to `docs/M2_PLAN.md`, the active delivery plan.
- Repoint delivery ownership in AGENTS, procedures, ARCHITECTURE's roadmap and
  subject documents; cite the archive for completed M1 decisions. No product
  change.
- Letter M2's segments A, B and C, and record that M2 ends in a release with
  real v0.1.0 migration, that development gets a guard for live production
  data, and that the new pages are late M2.
- Draft M2_PLAN's checkpoint register: segments A to D with aims, entry and exit
  conditions and non-goals, proposed checkpoints M2-A1 to M2-D4 and the M2-R1
  release, and the rule that requirements move to their owning documents at each
  checkpoint's start. Queue ownership is settled in B before rail actions and
  durability; presets get a db-owned config file of their own. ARCHITECTURE's
  roadmap moves schema migration and data protection from M3+ into M2.

## M1

M1 expands the reviewed-sync runtime into a complete headless integrity,
history, and workflow product while building its secured headed WebView2 shell.

### M1 Release

Portable packaging, exact runtime/native inputs, distribution contents and
final candidate verification prepare the unsigned tester release. M1_PLAN
owns identities and acceptance decisions; external delivery remains separate.

#### Allow hosted CI more terminal-settlement time (2026-11-12)

- Raise the web drain test helper's terminal wait from two to five seconds after
  PR #5 timed out in linked Copy/Verify. Preserve all behavioral assertions and
  product deadlines; runner slowness is suspected, not proven.

#### Build the portable M1 debug package (2026-11-04 – 2026-11-11)

- Deliver the unsigned Windows x64 v0.1.0 Gertrud tester set: app/source ZIPs,
  wheel, identities, dependency/build records, guides, Microsoft recipient terms,
  notices, checksums and short release notes in ignored dist/v0.1.0/.
- Lock exact build inputs and CI Actions; enforce no-ambient-DLL provenance,
  corresponding-source identity and complete collected notices. Local/hosted
  source/wheel/executable repeatability does not claim whole-ZIP equality.
- Repair R5 prerequisites: actual GUI token admission before exposure, serviced
  CPython 3.15.2/native inputs, versioned custody authority and renewed gates.
  Preserve the original calibration/holdout, limits and failed receipts.
- Fix rail attachment so trusted press/release survives repaint. Complete only
  the missing serviced-package idle/payload observations; original timeout
  ordering remains unproven, and the partial aggregate FAIL is not relabeled.
- Close R5 on b0a3fe13 (Package05): 6,575 passes, four capability skips, all
  35 headed obligations and 12 import contracts; exact-package Medium witness
  and reconciliation pass. SH-G-15 retains the user's qualified acceptance of
  the measured R4 schedule despite raw failed predicates. No signing, tagging,
  upload or external delivery. M1_PLAN owns final identities and gate accounting.

#### Exercise the portable package beyond startup (2026-11-04)

- Exercise the real extracted app through reviewed copy, inventory, baseline,
  verification and Close, checking exact filesystem results and owned shutdown.
- Preserve native input/foreground failures and partial attempts independently;
  an installed wheel or startup-only smoke does not certify the portable ZIP.

### M1 Performance

Executor, verifier, Plan and development measurements use the fixtures,
provenance and comparison limits in [PERFORMANCE.md](docs/PERFORMANCE.md).
Observed speed is diagnostic; component acceptance and safety remain with their
owning contracts.

#### Measure and accept current-source BR-G-42 timing (2026-11-09)

- Close R3 on the named reference profile: five-child Inventory cold, History
  release and bridge-event collections pass unchanged limits. Ratify CPython
  3.13.17, later renewed on the serviced release runtime.
- Keep Plan/UI diagnostics advisory. Repair current optional feedback/keyboard
  drivers without weakening fixture/action assertions or frozen authorities.
- Correct projection attribution to existing node IDs; modest equal-string
  sharing reduces measured overlap peak, with no stable cold-time gain.
  [PERFORMANCE](docs/PERFORMANCE.md) owns results, profiles and limits.

#### Reduce renderer memory and copy path overhead (2026-11-07 – 2026-11-09)

- Reuse compatible Plan/Inventory rows and current detail cells; preserve focus,
  selection, exact identity and one bounded window. Plan keeps spacers/scroll;
  passive geometry and unchanged paints avoid redundant DOM work.
- Use independent 250 ms local-paint and 500 ms routine-read clocks. Explicit
  navigation and urgent/control/phase/Gap/terminal feedback remain immediate.
  Extend wakeable 25 ms collection to successful integrity outcomes while
  preserving ordered individual delivery, custody and durable recording.
- Remove redundant response/snapshot copies and collect only at backend-idle
  boundaries, with bounded admission behind maintenance. Add no execute-time
  GC, JS heap cap, durable batching or verification concurrency.
- Diagnostics distinguish allocation, private peaks, retained state, CPU and
  elapsed time. Initial Inventory loaded-target work was deferred, then
  reintroduced under the scheduler; 200 ms collection/ACK changes stay unshipped.
  Exact comparisons, failures and non-causal limits remain in PERFORMANCE.

#### Measure updated-package startup and prepare workload profiles (2026-11-06 – 2026-11-07)

- Establish exact-package startup and full 17-run resource observations,
  separating host/runtime roles, scale, streamed payload, repeated use and long
  idle. Preserve pilot/foreground/input failures and incomplete attempts.
- Diagnose per-response allocation, renderer garbage, first-file-open cost and
  host high-water retention. Same-volume work is serialized; disjoint-volume
  concurrent execution resources were not measured.
- Keep historical yardstick verdicts separate from product acceptance. Earlier
  startup-only/manual studies did not complete their proposed workload matrix;
  the later R4 schedule and serviced follow-up have their own identities.
  PERFORMANCE retains methods, results and unresolved environmental observations.

#### Reduce planning observation work (2026-10-19 – 2026-10-21)

- Reduce repeated lexical path work and omit NOOP direct file checks only in
  review; execution/resume/verification retain their own fresh observations.
- After explicit review, reuse held-root/candidate spelling and one final leaf
  observation under the accepted logical-spelling and timing policy. Preserve
  current held attributes, descendant refusal and unheld fallback.
- Keep native handle-relative compatibility studies diagnostic. No scanner
  admission borrowing or universal path-guard removal; PREFLIGHT/DEFENSE own
  boundaries and PERFORMANCE owns qualified source/native measurements.

#### Deliver bounded direct target writes (2026-09-29 – 2026-09-30)

- Use bounded aligned direct target writes for eligible local copies at or above
  8 MiB, exact EOF and target-volume atomic publication. Keep buffered small-file
  behavior and select capability fallback before streaming.
- Preserve buffered source reads, exact tails/hashes, stable metadata, pause/
  retry/cleanup and durable settlement. Differential/native/readback gates pass.
- Final historical bands reach 1.40 MiB/s for 4 KiB and 4,505 MiB/s for 4 GiB;
  the small-file headroom goal remains unmet. These repeated-source observations
  are not cold-cache/device-ceiling claims. Unbuffered sources remain deferred.

#### Consolidate executor and verifier work without claiming a speed lift (2026-09-29 – 2026-09-30)

- Consolidate planner-used drift facts, adjacent native derivation and copied-
  file handle continuity while preserving fresh safety checks and own-effect
  rerun recognition. Remove equivalent verifier classification duplication.
- Preserve typed settlement, exact readback, source/dependency stability and
  scoped cleanup. Overlapping measured ranges establish no per-commit speed lift;
  PERFORMANCE retains original/contended runs and independent stage medians.

#### Reduce root-admission cost with invocation-scoped holds (2026-09-27 – 2026-09-29)

- Reuse only fully admitted, invocation-held local roots corroborated by exact
  normalized final spelling. Query current held attributes before every reused
  access and refuse reparse/placeholder state or query failure.
- Keep descendant guards, release on pause/exit and per-access fallback for
  remote/unholdable/uncorroborated roots. Core supplies evidence; executor,
  verifier and preflight each own admission. Native swap/differential and
  component gates pass; PERFORMANCE records measured cost separately.

#### Establish current measurement tooling and Plan-scale evidence (2026-09-15 – 2026-09-27)

- Establish deterministic Plan/Inventory fixtures, independent action/fixture
  checks, bounded installed probes and truthful incomplete reports. Keep selected
  Plan/UI diagnostics optional while retaining counted-work, custody and
  Inventory/release gates.
- Complete the historical Plan scale population with source-linked authority;
  do not make old rootful/timing/representation-memory receipts certify new
  rootless inputs or current source. PERFORMANCE owns methods and provenance.

### M1 Consolidation

Product, test and documentation reductions removed repeated machinery while
preserving operational safety, externally visible contracts and independent
behavioral evidence.

#### Shorten the ordinary suite (2026-11-28)

- The Plan review scale tests now build each 120k/240k fixture and its
  projection once per module. Before, they built the fixture 11 times and the
  projection 10 times. The module drops from 57 s to 23 s.
  `make_plan_review_state` accepts an already-built projection. The
  `build_fixture_manifest` helper, which only these tests used, is removed.

#### Split agent procedures and reorganize development tools (2026-11-23 – 2026-11-28)

- Condense AGENTS to always-on rules (269 to 137 lines) with a trigger table
  for new `docs/procedures/` SCOPE, CLOSEOUT and DOCUMENTS. Move evidence
  retention out of PERFORMANCE and merge the ARCHITECTURE/DEFENSE ownership
  lists into DOCUMENTS; BUGS and CHANGELOG keep their header instructions.
  README now indexes every active subject document.
- Group `tools/` into harness, settlement, performance, packaging, repo and
  desktop folders; rename the gate-coded `br_g_42` collector to
  `release_timing`. `python -m tools` commands are unchanged; direct module
  commands follow the new paths. An import-linter contract now enforces the
  harness boundary, and a test pins the corpus repository guard to the checkout.
- Move measurement JSON out of `tests/interfaces/web/`, leaving only the frozen
  `sh_g_8_*` custody files: the Plan contract now sits beside its driver, the
  Plan fixture manifests are a test asset, and EV-0039 keeps the R3 receipts
  and M1-8 results unchanged while listing 1.5 MiB of superseded authorities,
  measurements and receipts by Git commit and hash. The rejected
  pre-compaction M1-7 artifacts were dropped. The execution receipt/UI scale
  tests lost their `m1_8_` prefix.
- AGENTS asks agents to commit as they go, in small self-contained units that
  revert independently; CLAUDE.md counts committing as part of an edit or
  implement request, while push and merge still need their own.
- BUGS categories, which had become one-off titles (314 distinct in 319
  entries), now end in a singular mechanism noun reused from
  `python -m tools.repo.bugs --mechanisms` where one fits. 59 entries whose
  final word named no mechanism were retitled; IDs and bodies are unchanged.
- AGENTS asks agents to mark unsourced claims as inferred and unobserved ones
  as unknown or not run. SCOPE now owns deferred work: the row that will do it
  holds the record, CLOSEOUT moves each session's deferrals there, and the
  row's expansion rechecks, consolidates or returns them to the user.
- Adopted DEFENSE §2.6, fix placement: a warranted fix goes to the owner of the
  invariant the defect broke, counting sibling paths and facets, and takes the
  owner fix when it costs about the same or less over the defect's life.
  BUGS entries name the invariant, owner and level. Reopen triggers are now
  §2.7.

#### Survey and clear post-M1 cleanup candidates (2026-11-11 – 2026-11-17)

- Clear six local codex branches under the user's superseded-recovery disposal
  decision. Delete 61 registered external test roots (21.37 GiB logical),
  keeping the F: benchmark corpus and both H: human-testing directories with
  matching baseline counts/sizes.
- Ratify kind-based retention: `build/` is clearable scratch and validated
  records are promoted to tracked `evidence/` at session closeout. Add
  `python -m tools.evidence` for record IDs, sealed file hashes and citation
  checks; per-run records, differentials, ledgers and Git-reproducible copies
  are not promoted, and records are capped at 1 MiB / 24 files. Remove the
  secondary worktrees, R5 packages, the survey folder and everything outside
  the policy, leaving 1.00 GiB / 18,627 build files of lasting-cited material
  pending review; receipts are [EV-0001](evidence/EV-0001/cleanup.md).
  Define what belongs in `build/` (including unfinished work, which no
  schedule clears), place authored studies in `docs/` and work files nowhere
  else, and give failed or superseded runs failure records apart from acceptance.
  Give the inventory cold collector its own `build/inventory-cold/` root; its
  machine profile and child logs stay unretained beside the committed compact
  JSON.
- Correct evidence-candidate medians and successful-trial aggregation; restore
  compact resource, verifier, source-binding, CLI and descendant-reaping support.
  Preserve absent-source limitations explicitly rather than implying recovered
  raw evidence or renewed acceptance.
- Promote the 36 reviewed study records as EV-0003–EV-0038 (108 files,
  1.09 MiB) and repoint every lasting citation, rewording retention promises to
  what each record keeps.
- Compact M1_PLAN/PERFORMANCE/CHANGELOG by outcome and service DESKTOP_UI's
  structure and stale ownership prose. Preserve methods, qualifications,
  deferrals, unresolved observations and source-linked evidence; repair links.
- Further condense DESKTOP_UI's repeated behavior/implementation/test detail;
  preserve visual specifications and acceptance. Survey BUGS access and sibling
  analysis, then add immutable IDs to all 319 records without altering their
  paragraphs or metadata. Provide validated, full-record Markdown/JSONL export,
  cross-owner filters and explicit batches through `python -m tools.bugs`.
- Reframe README around persistent inventory, reviewed mirroring and integrated
  integrity workflows; condense delivery status, add architecture and recommended
  hardware guidance, and distinguish measured resource use from a hardware floor.

#### Reduce retained build artifacts (2026-10-29 – 2026-11-04)

- Remove generated caches, reconstructible source copies and test payloads under
  reviewed exact manifests; preserve unique source, receipts and required
  reconstruction capsules. Verify deletion and retained-byte accounting.
- Preserve the source bundle/mapping, compact fixture archive, metadata and
  baseline patch needed for historical reconstruction. Later cleanup rounds
  remain separately accounted; logical size is not a measured free-space delta.

#### Consolidate database and history test setup (2026-11-04)

- Share local schema-role and bounded-history-window setup across four schema
  and six history tests, preserving fault SQL, assertions and cleanup order.
- Retain all test identities and parameters: 261 cases pass before and after,
  and all 461 database department tests pass. Independent review approved;
  product code and global test fixtures are unchanged.

#### Pilot Setup journey simplification (2026-11-01)

- Check that the rendered Source and Target path fields align instead of
  requiring a 64px label column. Keep the installed refusal, Clear and
  readmission sequence and the specified option spacing.

#### Consolidate before M1 closeout (2026-10-29 – 2026-10-30)

- Consolidate narrow task/view/lifecycle wrappers and bounded helper catalogs;
  remove unused Scope placeholder plumbing while retaining scoped planning and
  history replay as unrealized outcomes.
- Preserve current result ownership, missing visibility, admission, frozen
  custody authority and consumer fixtures. Reconcile schema/status prose and
  condense completed registers with explicit dispositions and owner links.
- Complete dependency-scoped ordinary/native/installed, cold Inventory,
  import, settlement and independent review gates. Recover useful changes as
  reviewed commits rather than merging WIP; account for branch/worktree cleanup.
  Detailed decisions remain in M1_PLAN and the closeout evidence root.

#### Consolidate review infrastructure and ordinary copied-file verification (2026-10-16 – 2026-10-19)

- Share bounded view/controller infrastructure while retaining Plan/Inventory
  domain policy, current-window identity, stale-response fences and focus.
- Replace the exact-first-manual desktop handoff with repeatable ordinary
  server-derived successful-copy Verify. Keep original execution/automatic
  results separate from current scan/evidence and ordinary activity results.
- Preserve selected Verify, confirmation-gated rebaseline, missing visibility,
  original-outcome recovery and live controls. Retire duplicate wrappers and
  classify helpers/fixtures by direct ownership; installed/ordinary gates pass.

#### Simplify executor ownership and post-M1-8 machinery (2026-09-25 – 2026-09-30)

- Keep native effects behind the executor package and typed reducer, with
  stable settlement/oracle and differential evidence. Consolidate redundant
  continuation/check spelling without changing publication or durability.
- Remove unused historical mapping reads, duplicate preview/traversal and
  browser task reduction; retain public previews, one Python snapshot and
  exact command-result custody. Document replacement retires page authority
  without replaying effects or canceling admitted work.
- Retire recipe pins using behavioral/native/security checks. Keep optional
  Plan/UI metrics separate from enforced bounds, release resources and custody;
  no speed gain, generic owner merger or blanket command resend is claimed.

#### Consolidate product, tests and documentation (2026-09-01 – 2026-09-09)

- Align core contracts, component facades, persistence/workflow boundaries and
  layered tests; remove obsolete wrappers and duplicate source recipes.
- Preserve reviewed effects, atomic publication, result truth and domain-owner
  policies. Use the typed settlement reducer with frozen differential/oracle
  witnesses; keep current documents with historical plans under obsolete/.

#### Align historical criteria and layered verification (2026-08-10 – 2026-08-27)

- Reconcile historical acceptance with current component ownership and test
  departments. Keep diagnostic observations separate from executable bounds,
  frozen authority and actual native/installed witnesses.
- Preserve narrow residual dispositions, failure diagnostics and original
  evidence rather than treating aggregate green tests as complete safety proof.

### M1 Hardening

Safety, settlement and authority work made high-consequence release claims
explicit, reviewable and regression-backed.

#### Separate Inventory page and full-run verification evidence (2026-11-07)

- Correct the installed execution test's fixture-wide comparison against a
  scrolled Inventory page. Check exact verified row/result membership for the
  page and independently check all fixture paths in the retained release result.
- Preserve request/session identity, lifecycle ordering and whole-fixture
  coverage. Fault controls reject missing, extra, duplicate and substituted
  results. Both installed execution window sizes pass; production is unchanged.

#### Preserve Setup actions during folder validation (2026-11-04 – 2026-11-05)

- Keep Create available during ordinary folder validation; one guarded start
  waits for the current admission without replaying a check or using stale choice.
- Add pair captures private options; batch preparation admits that snapshot
  independently. Editing/removal retires pending intent; unresolved outcomes
  retain exact read-only Check. Focused and real Setup/batch journeys pass.

#### Sample Setup action visibility before navigation (2026-11-04)

- Correct the installed Setup fixture's Plan-again visibility observation:
  sample before clicking, because successful navigation may hide the old button.
  Preserve readiness, actual new-task identity and frozen-option assertions.
- The affected installed journey passes; no product behavior changed.

#### Render Unicode filenames on redirected CLI streams (2026-11-04)

- Render characters unsupported by the selected output encoding as visible
  Unicode markers across CLI review, results, history and diagnostics. UTF-8
  retains Japanese text; literal marker filenames remain distinguishable.
- Preserve caller-owned streams, their encoding and existing I/O-error handling.
  Real module/console round trips and the original retained history reproduction
  verify both cp1252 and UTF-8 output without changing file or database identity.

#### Complete the behavioral invariant and sibling sweep (2026-11-04)

- Close all 84 component/invariant cells with bounded evidence or explicit
  applicability: 67 clear, 16 inapplicable, one open redirected-output finding.
- Account for all 311 historical BUGS entries by semantic mechanism and owner;
  add fresh native, persistence, lifecycle, ingress and presentation seam probes.
- Record the cp1252 CLI history rendering defect and UTF-8 reproduction; retain
  fixtures through the later installed-app round and preserve original failures.
- Independently review coverage and recovery evidence. Installed-app and release
  acceptance remain separate; concurrent release preparation is excluded.

#### Bound GUI command-line requests (2026-11-04)

- Share complete-request admission between the console and GUI launchers,
  rejecting oversized or malformed arguments before GUI path/request creation.
- Cover both data-dir spellings, exact and first-excess UTF-8 boundaries and
  real Windows Unicode command lines while retaining lazy desktop imports.

#### Align executable names with the package name (2026-11-04)

- Rename the console and desktop entry points to `namisync` and `namisync-gui`,
  including usage guidance, package metadata, active documentation and tests.
- Keep `python -m namisync`, launcher routing and Windows subsystem choices
  unchanged; retain historical entry-point names in archived documentation and
  earlier changelog entries.

#### Make filenames readable in CLI output (2026-11-04)

- Show Unicode line and direction controls visibly in reviewed paths so a
  filename cannot split an operation row or disguise its suffix.

#### Verify integrated M1 lifecycle and retention (2026-10-30)

- Close M1-12 across admitted, refused, live, terminal, auxiliary and unsupported-
  reload paths. Preserve retained truth, stale-response retirement and exact
  observation/resource release without product changes.
- Pass 6,326 ordinary tests, four skips, all 35 headed obligations, settlement
  and 12 imports. Original foreground failures remain; unchanged resumed native
  cases pass after availability and dependency revalidation. No release claim.

#### Preserve Inventory viewport through refresh (2026-10-24)

- Restore full and selected Refresh around a visible item or folder, retaining
  its partial-row offset. Load the restored window directly and fall back to
  the clamped prior position when the anchor leaves the view.
- Keep viewport restoration separate from active-row identity and focus;
  enabled integrity Follow retains control, and departed task/view reads retire.

#### Avoid repeated notices for known missing Inventory items (2026-10-24)

- Suppress a disappeared notice during refresh or a preliminary integrity scan
  when the named file or folder is already missing under an earlier scope token.
  Retain newly missing and unknown-subject notices and preserve raw scanner
  diagnostics and existing ledger reconciliation.

#### Expose scan-time local availability and clarify cloud behavior (2026-10-22)

- Carry observed recall-required evidence into a plain cloud indicator and
  Remote files filters, independently of operation reasons and unsupported state.
- Explain that access may retrieve provider content; unmarked files are not
  certified local. Aggregate recall facts remain available through the bridge,
  without download-volume predictions, extra confirmation or remote completion
  claims. SCANNER/DEFENSE own supported provider limits.

#### Update local runtimes and verify security-update compatibility (2026-10-22)

- Verify the selected local Python/SQLite security update against ordinary,
  native/installed and cold Inventory dependencies without retuning budgets.
- Keep exact runtime/profile identity on each receipt and original failures;
  historical timing/custody evidence does not silently qualify a different
  interpreter. Later release servicing has its own completed Release record.

#### Repair bridge diagnostic composition receipts (2026-10-04)

- Include the seven pre-existing inventory commands in the optional installed
  bridge-event diagnostic's expected catalog. Generate positive test receipt
  names from real production composition, and reject missing, extra or duplicate
  names in either receipt catalog. Product commands and benchmark authority are
  unchanged.
- Reproduce the old refusal, pass 41 focused and 2,286 tools/interfaces tests,
  and complete the installed diagnostic with four valid sessions. Timing and
  custody acceptance remain separate from receipt compatibility.

#### Correct inventory lifecycle feedback (2026-10-02)

- Keep activity status separate from a view read, scan publication and current
  evidence. Preserve navigation/drafts through background updates and exact
  request/session adoption, Refresh and terminal release.
- Retain current UI facts on stale/failed responses; installed and ordinary
  witnesses cover truthful retained feedback without changing integrity policy.

#### Resolve reviewed open bugs (2026-10-01)

- Resolve the reviewed inventory, lifecycle and presentation defects at their
  owning seams with reproducing controls and component/installed verification.
- Preserve independent execution/integrity/ledger/audit results, current-root
  admission and exact original outcomes. BUGS retains causes, fixes, residuals
  and reopening context; unconfirmed observations remain unconfirmed.

#### Ratify proportional defense and root safety (2026-09-28 – 2026-09-29)

- Classify supported consequences/enforceability before selecting defense tiers;
  distinguish diagnostics from acceptance and retain named residual assumptions.
- Require current held-root attributes and fail-closed descendant observation,
  preserving local-hold/fallback limits and exact logical root corroboration.
  DEFENSE and component owners retain criteria; tests back supported seams.

#### Separate cold and live database admission (2026-09-27)

- Runtime database adoption now validates through a pinned SQLite connection
  and current SQL snapshot, so its own WAL/SHM activity does not look like
  incompatible cold drift. Standalone cold checks keep byte-preserving
  pair/schema/journal refusals; observed database-file drift receives one
  bounded retry, while only confirmed incompatibility receives reset advice.
  Reader lifetime, noncreating planning, recorder placement and retryable
  shutdown remain guarded. Native, installed Setup, ordinary and import checks
  passed with independent review.

#### Classify installed incidents and preserve truthful diagnostics (2026-09-25 – 2026-09-27)

- Separate native foreground/observer failures, unsupported conditions and
  demonstrated product defects. Bound diagnostics and retain original failure
  context without promoting a later passing retry into an earlier diagnosis.
- Preserve actual normal/forced shutdown, source/asset identities and exact
  installed endpoint scope. TESTS/BUGS retain unresolved conditions and triggers.

#### Preserve command outcomes and desktop recovery (2026-09-25 – 2026-09-26)

- Remove timed page-side mutation abandonment/replay. Recover the original
  native-owned outcome through bounded observation while keeping identity,
  duplicate protection, dependent Start/Close fences and explicit unavailable
  feedback. Genuine document replacement retires page authority but preserves
  admitted work and gives close/reopen and fresh-review guidance. Lifecycle
  and resource deadlines, process-loss limits and retryable shutdown remain.
  Ordinary, installed and import gates plus independent review passed; two
  earlier intermittent installed observations remain unexplained.

#### Preserve move detection across repeated renames (2026-09-25)

- Planning correspondence no longer treats retained inventory paths or link
  counts as current aliases. Fresh scans still reject hardlinks and duplicate
  identities; ambiguous correspondence is ineligible. Native rename/no-op
  convergence, repository history, ordinary and import checks passed without
  schema reset or history deletion.

#### Bound task inputs, custody and cross-layer truth (2026-08-26 – 2026-08-30)

- Bound external requests before presentation construction and maintain exact
  event/scalar/opaque-identity validation. Keep original command custody across
  uncertain delivery, settlement and task release without duplicate effects.
- Reconcile task/session/result owners and direct consumers under the import
  law. Preserve durable truth, capacity admission and controlled recovery;
  frozen historical evidence remains distinct from current runtime guarantees.

#### Establish the safety and evidence model (2026-07-30 – 2026-08-18)

- Establish supported assumptions, trust boundaries, hard walls, proportional
  tolerances and evidence authority. Root safety, guarded effects and honest
  durable/terminal results remain independently owned and tested.
- Separate named empirical profiles, calibration and holdout from current
  enforced limits; keep residual dispositions and reopen triggers explicit.
  DEFENSE owns policy, component docs own criteria and PERFORMANCE owns methods.

#### Harden development measurement tooling (2026-08-06 – 2026-08-18)

- Add safe owned workspaces, exact output manifests, deterministic generation,
  source-drift/readback checks, sidecar identity and atomic exclusive reports.
- Keep fake persistence/development commands separate from product surfaces;
  instrumentation and cache/null-hasher profiles remain explicit. Invalid,
  incomplete or cleanup-failed samples cannot publish favorable reports.

### M1 GUI

Stage 6 delivered the secured desktop host, process-live tasks, frozen Setup,
bounded Plan review/selection and execution, and live/retained result review.
Standalone Inventory adds integrity selection, controls and retained results.
Same-task Plan/Verify navigation adds first manual post-copy verification and
explicit ordinary fallback. Final lifecycle acceptance and beta packaging remain open.

#### Refine live execution and verification feedback (2026-11-06 – 2026-11-09)

- Restore Filters during linked verification, phase-specific headlines/counters,
  independent warning axes, retained current verification target and truthful
  copy/verify progress. Preserve control/recovery custody and actual result facts.
- Use icon-only controls with accessible names, compact ETA units and local
  Modified display. Keep Plan Again unavailable during execution/admission and
  let explicit navigation retain its foreground owner; installed gates pass.

#### Add the NamiSync app icon (2026-11-03)

- Add color, two-tone and mono SVG masters for the app icon: a two-sheet copy
  glyph whose front sheet is layered paper waves. The flat renders omit the teal
  wave, leaving negative space, and close the front sheet with a left-edge bar.
- Ship the masters as package data in `namisync/interfaces/branding/`, outside
  the web assets. The app does not load them yet; window, taskbar and installer
  icons remain later work.

#### Refine Inventory and Plan GUI feedback (2026-10-23 – 2026-11-01)

- Align task/status/table cards, path labels, column geometry, Details groups,
  badges and controls across Plan/Inventory. Keep full-path accessibility,
  stable focus/scroll, current result owners and non-color state cues.
- Preserve manual versus automatic Follow intent, anchored Details and
  filter/sort/selection scope. Refine Setup options, Settings navigation/footer,
  current task activity and terminal feedback without changing domain policy.
- Tune shared Fluent tokens/material/control states and icons with installed
  light/dark/forced-color and native checks. Exact visual contracts and named
  contrast/compositor qualifications remain in DESKTOP_UI.

#### Add explicit Setup defaults to Settings (2026-10-29)

- Present Setup defaults, Appearance and About cards in the existing scrollable
  Settings page. Save only changed options, including automatic execution
  verification, while existing task drafts and Plan again retain their choices.
- Preserve unsaved fields across navigation, serialize reads and saves, and
  offer current-default readback after an unconfirmed save without replaying it.
  Keep ADS unavailable and theme persistence independent.
- Keep the ordinary unsaved advisory in the footer's left column and Save
  defaults at the bottom right without changing the card height.

#### Add About license and open source notices (2026-10-29)

- Add separate License and Open source acknowledgements links with
  scrollable, selectable local text, a fixed Close action and shared modal motion.
- Use Windows AccentDark2/AccentLight3 text without underlines. Retain all seven
  Windows accent colors in the native appearance snapshot without changing
  existing accent-filled controls or forced-color behavior.
- Package the existing GPL and reviewed current Windows dependency/asset notices,
  including embedded JavaScript, native compatibility assemblies and Fluent
  assets. Retain source/version attribution without changing navigation or
  claiming final release-license closure.

#### Align Verify table interaction and action consequences (2026-10-15 – 2026-10-16)

- Align server-derived selection, row activation, menus, keyboard highlighting
  and context action targets between Plan and Verify while retaining exact scope.
- Preserve selected/hidden counts, stale-owner refusal, fresh confirmation and
  independent baseline/verify/rebaseline outcomes. Reconcile action labels and
  source/target/result Details without treating baseline creation as verification.
- Correct shared/native witnesses at their owning seams; keep failures and
  original input/focus/geometry guards. PRESENTATION/DESKTOP_UI own the contract.

#### Deliver M1-10 integrity controls and manual verification (2026-10-13 – 2026-10-14)

- Add complete server-owned file selection and confirmation-gated rebaseline,
  including eligible null-evidence files; baseline creation is not verification.
- Deliver standalone integrity controls, exact current request/session adoption,
  partial/live result handling and mounted Plan/Verify panes with original
  execution, automatic verification and ordinary results kept separate.
- Expose existing target ledger reads without inventing scan provenance; preserve
  Refresh/missing visibility, current mutation release and exact Close.
- Correct historical-stat, publication-backstop and foreground-owner defects;
  ordinary/import and all affected installed gates pass by dependency. The
  original exact-manual handoff was later superseded by ordinary copied-file
  Verify. No persisted hashes, terminal subset retry or schema redesign shipped.

#### Align desktop review surfaces and recovery (2026-10-05 – 2026-10-13)

- Use one two-axis viewport and sticky header for Plan/Inventory, preserving
  current-window limits, keyboard reveal, resizing and shared columns. The
  physical wheel/tilt report remains unresolved by browser controls.
- Show truthful Checking/Planning/Scanning shells before complete publication;
  preserve old review through uncertain Plan Again and original-command Check.
- Adopt compatible scroll responses, bound held navigation and directional
  prefetch to one read/current intent, and preserve anchored scroll/focus through
  discarded, hidden, resized and superseded requests.
- Align rootless rows, operation/move labels, selection/highlighting, Filter
  counts/menu focus, Details, controls and neutral/semantic styling. Keep
  server-owned hierarchy, full query scope and independent result axes.
- Repair counted-byte and table-loading observers without relaxing Unicode,
  ingress/custody or action assertions; preserve source/asset restoration.
  PERFORMANCE owns qualified latency/capture comparisons and unresolved controls.

#### Refine Plan refusal messages, move context and controls (2026-10-04)

- Show actionable Plan/preflight refusal without losing the immutable review;
  distinguish recoverable original-outcome observation from a new start.
- Clarify same-parent rename/casing versus cross-parent move and Move + update,
  preserve raw operation identity in Details and make supported risks visible.
- Align Plan search/filter/selection/context controls with server authority,
  native focus and complete query scope; component and installed checks pass.

#### Deliver M1-9 inventory review (2026-10-01 – 2026-10-02)

- Add bounded Inventory browsing, server hierarchy/search/facets/sibling sort,
  exact current evidence and on-demand Details, with keyboard/highlight/selection
  authority independent of execution and ledger facts.
- Add same-task Refresh and conditional missing-item acknowledge/restore,
  original-outcome recovery and truthful complete/partial publication. No hash
  or hidden execution policy follows a view read or visibility change.
- Ordinary/import and all installed obligations pass with source/receipt identity
  accounting. Later M1-10 supplies integrity controls; this checkpoint did not
  deliver terminal subset retry, new performance targets or release acceptance.

#### Mitigate the Advanced Color flyout halo (2026-09-24)

- The dark translucent flyout shadow halo was reproduced in DWM Advanced Color
  composition, including a raw Win32 probe; an 8-bit screenshot cannot prove
  it absent. Native appearance v3 follows the window display's state, and dark
  flyouts suppress CSS elevation shadows on Advanced Color displays. The
  underlying compositor behavior remains deferred. Focused, installed gallery,
  interface and import gates passed. The review captures were not retained;
  BUGS records how to reproduce the halo.

#### Complete M1-8 execution review and task recovery (2026-09-20 – 2026-09-24)

- Deliver bounded live/retained execution review with independent filesystem,
  verification, recording and audit facts, native controls and original-outcome
  recovery. Retain readable terminal truth through non-stopping degradation.
- Recognized capacity failure stops later admission after current settlement;
  recorder-only failure remains degradation. Preserve atomic publication, fresh
  preflight and exact busy Close/release. U-v2 supersedes earlier UI timings;
  terminal retry and durable task survival remain outside M1.

#### Deliver bounded Plan review, selection and execution (2026-09-14 – 2026-09-20)

- Deliver rootless bounded Plan review, search/category facets, sibling sorting,
  complete server-owned selection and exact destructive confirmation.
- Preserve immutable Plan/options, dependency-closed execution membership,
  current preflight/root authority and virtualized keyboard/focus behavior.
  Scale and installed gates pass on their recorded fixtures; retired criteria
  are not relabeled as passes or current-source timing guarantees.

#### Deliver Setup, task navigation and selective icons (2026-09-09 – 2026-09-14)

- Deliver process-live blank tasks, newest-first rail/navigation/Close, typed,
  picker and recent location starts, frozen per-task options and fresh Plan Again.
- Add serial best-effort pair composition and explicit creation results without
  a hidden global queue or lasting admission. Curate fixed local Fluent icons;
  keep accessible input, forced colors and source/license provenance.

#### Establish exact events and presentation semantics (2026-08-19 – 2026-08-25)

- Establish exact versioned progress/result facts, bounded publication and
  coherent selection/search/sort/window identities. Keep unreliable progress
  separate from reliable item/terminal custody and durable outcomes.
- Retain phase-aware truthful feedback, independent filesystem/integrity/
  recording/audit axes and current-owner stale refusal across adapters.

#### Secure the headed desktop foundation (2026-07-31 – 2026-08-18)

- Deliver the lazy GUI-subsystem launcher, per-user paths/logging, fixed desktop
  singleton, strict WebView2 host, same-origin inert assets and bounded bridge.
- Refuse missing prerequisites, off-origin/navigation/popup exposure and unsafe
  documents; preserve attach-before-start observation and ordered shutdown.
- Establish Fluent/material/theme/accessibility, local icon and clean-installed
  native witnesses. No browser fallback, domain policy in UI or durable tasks.

### M1 Features

Stages 1–5.5 delivered the headless reviewed-sync, inventory/integrity, history,
CLI, and reusable workflow product plus its development measurement tooling.

#### Add bounded durable history readback (2026-08-05 – 2026-08-06)

- Added windowed durable reliable-event history, bounded keyset detail pages,
  and incomplete-prefix recovery.
- Hardened replay and close behavior without allowing audit/history failure to
  rewrite sync truth.

#### Add scoped review trees and revisioned selection (2026-07-30)

- Added deterministic review trees, full/path/subtree inventory scopes, and
  folder-level operations.
- Added deselection provenance, dependency closure, authoritative selection
  re-derivation, risk previews, and retry-safe facade admission.

#### Establish M1 contracts and persistence boundaries (2026-07-24 – 2026-07-27)

- Made reviewed plans immutable at execution, separated semantic settings from
  cosmetic UI state, and added the XXH3 hashing seam.
- Established reset-only ledger v2/history v3 contracts and strict bridge/
  UI-state inputs.
- Removed persisted mapping-filter projections: filters stay immutable per-plan
  scan input while the ledger retains role-free inventory and mapping
  correspondence.

#### Complete headless integrity workflows, service, and CLI (2026-07-25)

- Added the bounded XXH3 copy pipeline, role-free inventory,
  baseline/verify/rebaseline, and optional post-copy verification.
- Completed the reusable service facade and typed CLI commands/results for
  sync, history, and integrity work.

## M0

M0 established the reusable headless reviewed-sync baseline and its explicit-
plan safety model.

### M0 Hardening

Filesystem and reporting edge cases were hardened without weakening explicit
review or guarded execution.

#### Make filename-form differences safe and reviewable (2026-07-20 – 2026-07-21)

- Made invalid raw names incomplete-scan evidence without aborting safe sibling
  work; case-only and unique NFC/NFD differences remain visible to reviewers.
- Kept filename-form advisories from suppressing ordinary update/no-op work and
  made review output show the prior target path for move, move-update, and
  recase operations.

#### Recover interrupted work and harden Windows finalization (2026-07-20)

- Made directory cleanup tolerate only same-run child-induced metadata churn
  while preserving replacement and nonempty-directory refusal.
- Corrected directory flush access, restored identity-less FAT-style cleanup
  where identity was never reviewed, and reclaimed only exact prior-run
  temporary files after preflight.

### M0 Features

The first milestone shipped reviewed one-way sync through reusable core,
runtime, persistence, workflow, and CLI layers.

#### Add safe-subset execution (2026-07-20)

- Quarantined blocked and dependent operations while allowing independent safe
  work; incomplete scans use an additive-only subset that withholds moves and
  deletions.
- Added itemized blocked/deferred results, history, and CLI partial-completion
  reporting.

#### Deliver reviewed-sync workflows and CLI (2026-07-19)

- Composed scan, deterministic plan, commitment validation, fresh preflight,
  execution, ledger recording, dispatcher custody, and independent history
  into the reusable workflow layer.
- Added the reviewed two-session `nami-sync sync` flow, read-only `history`
  browsing, real process entry points, and safe retry/admission fixes.

#### Establish the M0 backend foundation (2026-07-18)

- Added core session/event/evidence contracts; scanner, planner, preflight,
  guarded Windows executor, and standalone integrity-verifier primitives.
- Added bounded dispatcher custody/event fan-out plus WAL-backed ledger, typed
  repositories, and independent history persistence.
