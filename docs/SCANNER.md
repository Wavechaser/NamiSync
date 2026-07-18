# Scanner Module

Status: draft contract. Priority: walking scanner in M0; incremental and
network-aware sources are later implementations of the same contract.

## Purpose

The scanner observes one filesystem root and returns a deterministic,
reviewable metadata snapshot. It never plans changes, writes inventory, hashes
ordinary file content, follows policy beyond scan ignores, or decides whether a
warning is executable. It implements `ChangeSource` and imports only core.

## Contract

```python
scan(root: Root, ignores: IgnoreSet, ctx: RunContext) -> ScanResult
```

The result contains the resolved root, `VolumeId` plus corroborating
`VolumeEvidence`, `CapabilityProfile`, `FileRecord` values, every walked
directory as `DirRecord`, typed `UnsupportedRecord` values, warnings, ignore
snapshot, and `complete`. Unsupported records live in their own collection so
planner and inventory consumers must handle them explicitly; warning text is
not their state.

Results are sorted by normalized relative key with a deterministic tie-breaker.
The scanner returns partial observations instead of raising for ordinary access
failures. Fatal root/volume errors are typed and still produce a session result.

## Walking Rules

1. Validate and open the root using long-path-safe Windows handling.
2. Resolve volume/capability evidence once for the scan.
3. Enumerate entries without following reparse points by default.
4. Apply location ignores before descending into an ignored subtree.
5. Check `ctx.checkpoint()` between entries/directories.
6. Record size, mtime, stable identity when supported, link count, and
   `MetadataSnapshot(attributes, created_ns)`. Every `DirRecord` carries the
   same metadata shape plus optional identity. The scanner never enumerates
   ADS and receives no preservation policy.
7. Track visited directory identity so junctions and mount loops terminate.
8. Classify cloud/offline placeholders from attributes/reparse tags without
   hydrating or reading them.
9. Record access/type/collision/hardlink warnings and set `complete=False` for
   any uncertainty that could make one side appear absent.

Application-owned ignores use exact qualified names or exact generated-name
grammar. `.synctrash` is excluded as an owned root; a user filename merely
containing `.synctmp-`, ending in `.db`, or resembling a checksum sidecar is not
excluded unless it is the exact configured artifact.

## Completeness And Scope

A full scan is complete only modulo its recorded location ignores. Mapping
filters do not affect completeness; workflows apply them symmetrically after
both scans. An unreadable entry, case collision, uncertain reparse traversal, or
root identity change makes the scan reviewable but non-executable where absence
could drive mutation.

Selected inventory refresh is a separate scoped observation mode. It may update
named paths but must never infer that unselected rows are missing. The workflow
and inventory repository own that distinction; the scanner exposes scope and
completeness clearly enough to enforce it.

An offline/unmounted volume is not an empty complete scan. It yields a typed
offline result and cannot trigger missing marking or target-only planning.

## Capability Profile

At minimum record filesystem type, timestamp granularity, stable file-identity
support, seek-penalty knowledge, maximum path behavior, ADS support, and
`supports_hardlinks` read from `FILE_SUPPORTS_HARD_LINKS` rather than a probe or
filesystem-name table. ADS support is one volume-capability bit only; collecting
it does not inspect any file's streams.
Unknowns degrade conservatively: unknown seek penalty behaves like HDD for
worker policy; absent stable identity disables identity moves; coarse timestamps
control planner comparison tolerance.

The stable volume key is `(serial, fs_type)`; labels are mutable corroborating
evidence. Relabeling does not rebind, a changed filesystem type does, and
simultaneous duplicate keys require explicit user choice.

## Expectations Of Other Modules

- Core supplies path, identity, warning, capability, and result types.
- Workflow supplies the exact ignore snapshot and session/error handling.
- Planner treats incomplete scans as non-executable and does not reinterpret
  warnings.
- Inventory reconciles full and scoped scans differently and never writes from
  the scanner itself.
- Dispatcher supplies checkpoint behavior and holds required custody where the
  scan participates in a mutating workflow.

## Latent Implementations

The future USN `ChangeSource` must produce the same `ScanResult` semantics,
including a defensible completeness boundary and fallback to a full walk after
journal gaps, wrap, identity change, or unsupported volumes. Network scanning
must declare weaker identity and coordination guarantees rather than imitating
NTFS. Neither implementation changes planner or inventory contracts.

## PoC Hardening

- Exact ignore matching covers the PoC user-`.db` data-loss bug and missing
  history database sidecars.
- Per-entry error capture prevents permission errors from aborting the walk.
- Checkpoints restore cooperative cancellation.
- Visited identity and reparse classification close the open junction-cycle
  gap.
- Scanner never refreshes stored baselined metadata directly; that PoC bug is
  prevented by inventory/recorder conditional rules.

## Acceptance Criteria

- A clean tree returns `complete=True`, stable deterministic ordering, all
  regular files, every walked directory as `DirRecord`, and every unsupported
  entry as `UnsupportedRecord`.
- Permission denial, disappearing entries, and enumeration errors are retained
  as warnings, return the reachable snapshot, and force `complete=False`.
- A junction to an ancestor, sibling, or another volume never recurses twice or
  escapes the root; cycle tests terminate within the entry-step bound.
- Placeholder tripwire tests prove no content handle is opened and no hydration
  occurs.
- Exact-ignore regression tests retain `customer.db`, `my.synctmp-notes.txt`,
  and sidecar-like user files while excluding configured ledger/history/WAL/SHM,
  exact temp grammar, and `.synctrash` artifacts.
- Cancellation is observed within one directory/file enumeration step. Scanner
  registration refuses pause cleanly because scan has no continuation.
- Case-collision and multi-link/duplicate-identity cases are reported without
  merging records.
- exFAT/FAT fixtures report coarse timestamp granularity and no stable identity;
  NTFS fixtures report usable identity when the OS supplies it.
- Every file/directory carries attributes and creation-time metadata; scans do
  not vary by mapping role or preservation policy and never enumerate ADS.
- Capability fixtures prove `supports_hardlinks` follows the authoritative
  volume flag independently of filesystem-name assumptions.
- Long paths above legacy `MAX_PATH` scan successfully without truncation.
- An offline volume never returns a complete empty snapshot and never causes a
  missing sweep.
- A scoped refresh of two paths performs no full walk and cannot mark a third
  row missing.
- Import-linter proves scanner code imports core but no sibling module.
