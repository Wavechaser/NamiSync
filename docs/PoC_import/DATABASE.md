# NamiSync Database

## Current scope

Phase 2 uses main ledger schema version 3. It is a fresh schema only: an
existing version 1 or 2 `nami-sync.db` is refused with a reset instruction.
Development v3 databases created before the acknowledgement/reappearance cut
must also be reset; temporal proximity deliberately keeps this fresh schema at
version 3 rather than adding an unreleased migration.
NamiSync never deletes a database automatically. To reset unreleased
development storage, first close all NamiSync processes, then remove only the
main database file and its `-wal` and `-shm` companions. This is a database-only
action and never touches selected roots, `.synctrash`, sidecars, or history.

Every SQLite connection enables foreign keys, WAL, and a bounded busy timeout.
Repository methods do not commit; workflows commit after a completed filesystem
observation or mutation.

## Main v3 model

- `hosts` identifies the local computer.
- `locations(host_id, path, path_key)` describes one physical directory with no
  source/target role. `path_key` uses the shared Windows normalization helper;
  SQLite `NOCASE` is not identity policy. The helper uses a one-code-point
  Windows-style uppercase key, so Unicode expansions such as `ß` to `SS` do not
  collapse distinct NTFS names.
- `files(location_id, rel_path, rel_path_key, ...)` is one retained physical
  inventory. Its state is only `present` or `missing`. `last_seen_at` is the
  last positive observation. Hash, algorithm, and hash-observed timestamp are
  constrained as a unit; only SHA-256 is stored. Nullable
  `missing_acknowledged_at` and `reappeared_at` retain review evidence without
  expanding physical state.
- `mappings(source_location_id, target_location_id, deletion_policy)` supplies
  paired sync roles. It does not own either inventory.
- `mapping_file_state` stores mapping-specific source file identity and last
  correspondence. Composite foreign keys prove that a target file belongs to
  the mapping target and that a linked run belongs to the mapping.
- `runs(mapping_id, run_token, status, started_at, ended_at)` contains only
  final `done`, `failed`, `canceled`, or `refused` outcomes. The executor token
  is unique and also correlates history and trash paths.

Deleting a mapping discards only its runs and mapping evidence. Phase 2 has no
location-forgetting workflow; development storage is reset only by the explicit
closed-database reset procedure.

## Inventory reconciliation and retention

Scanner observations update current metadata only for unhashed rows. Once a
digest exists, its size, mtime, and file identity remain the atomic observation
that digest attests; later scans update spelling, presence, and `last_seen_at`
without converting an ordinary edit into a hash mismatch. A complete error-free
scan stamps all positive sightings with one microsecond-resolution UTC marker,
then marks other present rows missing with a constant-size update. A partial
scan does not infer absence. Missing rows retain their last positive-sighting
time and can be pruned explicitly with an age cutoff. Pruning cascades only
discardable mapping evidence.

Acknowledging a missing row sets `missing_acknowledged_at`, hides it from the
default inventory view, retains the row/hash, and invalidates every mapping
correspondence that referenced it. Reverting sets only that timestamp to null.
A positive observation always clears the acknowledgement. A `missing` to
`present` transition sets `reappeared_at` and invalidates mapping evidence;
matching metadata remains evidence, not identity proof. A stable matching hash
reread or successful first-hash backfill clears `reappeared_at`; mismatch or
modification does not. Database checks keep acknowledgement on missing rows and
reappearance on present rows while `state` remains strictly
`present`/`missing`.

Case-only paths update their display spelling without a second file row. A
file-id rename is never accepted from metadata alone. It requires one retained
missing SHA-256 row, one unambiguous present candidate with corroborating size
and mtime, and a direct matching hash reread.

## Paired execution

Paired scan reconciliation creates locations and inventory but not a mapping or
run. Successful execution then creates or updates the mapping, a mapping-scoped
run, the physical target inventory, and correspondence. Copy/update/move/trash/
delete invalidate stale evidence from other mappings that reference the affected
target file. Executor-confirmed target moves rekey the existing physical row,
preserving its id, retained digest, and integrity timestamps. A retained missing
row at the move destination is removed first, so its unique path key cannot
roll back the whole run's bookkeeping.

Multiple mappings may share one target location and therefore one physical
inventory row. Each mapping keeps independent source identity/correspondence;
the source and target explicitly selected for the current session supply
authority. A material target mutation through one mapping removes stale
correspondence from the others without duplicating or deleting the target hash.

## One-location integrity

Baseline creation first performs the same complete one-location inventory scan
and reconciliation used by the explicit Inventory action. It then hashes only
present unhashed records and sets
`hash_observed_at`; it never sets `last_verified_at`. Verification rereads the
same inventory and updates `last_verified_at` only after stable matching stats
and digest. A null hash encountered during verify is a baseline outcome, not a
verified outcome. Conditional writes protect every per-file hash result from
concurrent metadata or hash changes.

TeraCopy sidecar import requires an existing scanned location and existing,
present, unchanged, unhashed file row. The update is conditional on row id,
state, null hash, size, and mtime; matching or conflicting stored hashes always
win. Import creates no location, file row, mapping, mapping state, or run.

## One-location access surfaces

`namisync/app/inventory.py` is the non-Qt inventory workflow. It scans and
reconciles one selected location, then returns its retained file rows and a
read-only mapping-context summary. It creates a location/file inventory only;
it never creates, selects, or promotes a mapping.

`load_location_mappings()` reports zero, one, or many stored relationships for
display. One mapping identifies the location role and counterpart. More than
one is deliberately escalation guidance: callers must supply an explicit source
and destination for a paired action rather than choosing a counterpart.

The CLI and GUI use this same location workflow. Baseline, verify, and sidecar
import read the selected location inventory after their completed writes so
their callers can render current hash and verification status without a fake
sync plan.
