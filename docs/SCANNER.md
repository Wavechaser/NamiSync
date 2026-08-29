# Scanner Module

Status: M0 walking and exact-path scanning plus M1 Stage 5.5 recursive subtree
scanning are implemented. Stage 6's pre-model plan-source admission is active
for workflow-supplied scans. Incremental and network-aware sources remain
later implementations of the same contract.

## Purpose

The scanner observes one filesystem root and returns a deterministic,
reviewable metadata snapshot. It never plans changes, writes inventory, hashes
ordinary file content, follows policy beyond scan ignores, or decides whether a
warning is executable. It implements `ChangeSource` and imports only core.

## Contract

```python
scan(
    root: Root,
    ignores: IgnoreSet,
    ctx: RunContext,
    scope: ScanScope | None = None,
    *,
    trusted_anchor: str | None = None,
    review_admission: PlanReviewAdmission | None = None,
    population_admission: ScanPopulationAdmission | None = None,
) -> ScanResult
```

The two optional population admissions are workflow-owned, exact-type-only,
and mutually exclusive; ordinary scanner callers may omit both. Planning uses
a fresh `PlanReviewAdmission`, while inventory supplies the narrower
`ScanPopulationAdmission` protocol. Either gate checks the combined
file/directory/unsupported population and the warning population independently
before each first-excess append. Workflow then validates and adopts the exact
immutable `ScanResult` once and charges only the shallow slots that its final
artifact retains.
A first excess raises the owning typed signal and no partial `ScanResult` is
published. Checkpoint 4P.22 replaces this transitional pair with one protocol-
typed admission parameter without changing either workflow's outcome.

This admission closes the planning-source owner boundary. It is not the
checkpoint-4 complete-object reservation model. Scanner admission neither
prices construction/sort/index storage nor sums a whole scan's logical bytes;
text/codec/native copies, container capacity, complete graph validation, and
task/result retention remain governed by that later model and validator.

## Implemented M0 Surface

`namisync.modules.scanner` provides the module-level `scan()` entry point and
an injectable `WalkingScanner`. Its native backend uses metadata-only Windows
enumeration and volume capability observation; tests replace that backend to
fault disappearing entries, permission errors, placeholder attributes,
identity cycles, case collisions, coarse filesystems, and partial enumeration
without opening file content.

The native backend delegates current-anchor discovery, native volume facts,
configured-root-chain admission, and no-follow stat classification to core.
Scanner still owns capability interpretation, scan warning vocabulary, probe
timing, traversal, and the exact FULL folder-mount exception.

On a volume that advertises stable file identity, Windows directory-entry
metadata may still omit the inode for an extended-path enumeration. In that
case only, the walker repeats the metadata-only stat through its backend for the
exact entry path. This preserves correspondence-qualified move detection
without opening content or fabricating identity.

`ScanScope` has three explicit shapes. `FULL` retains the location root plus
every reachable directory. `PATHS` performs only named-path stats and never
recurses. `SUBTREES` recursively walks canonical roots and may carry additional
exact paths outside those roots. Mixed scopes minimize overlapping roots by
path-segment ancestry, remove covered exact paths, and become `FULL` when the
location root is selected. Core normalization walks canonical parent keys, so
many sibling roots do not create a quadratic admission-time scan before the
dispatcher starts work.

Full and subtree recursion use the same parameterized walk over an absolute
start plus its location-relative prefix. This keeps nested records keyed as
`PHOTOS\2024\IMG.JPG`, not relative to the nested start. One visited-directory
identity set spans all roots in a scan. The exact-path branch remains separate
and retains its existing named-subject completeness rules.

The result contains the lexically normalized, admitted root, `VolumeId` plus
corroborating `VolumeEvidence`, `CapabilityProfile`, `FileRecord` values, every
walked directory as `DirRecord`, typed `UnsupportedRecord` values, warnings, and
`complete`. Unsupported records live in their own collection so planner and
inventory consumers must handle them explicitly; warning text is not their
state.

Results are sorted by normalized relative key with a deterministic tie-breaker.
The scanner returns partial observations instead of raising for ordinary access
failures. Fatal root/volume errors are typed and still produce a session result.
Raw directory-entry names are validated before canonical sorting, ignore
matching, metadata access, or record construction. A name that the filesystem
can expose but the root-relative path contract cannot represent is skipped,
reported as `PATH_UNREPRESENTABLE` with an escaped display spelling and nearest
valid parent, and makes the scan incomplete; safe siblings remain reviewable.
Valid Unicode filenames are retained byte-for-code-point as observed. Scanner
does not normalize NFC/NFD spelling; planner may annotate a one-to-one
canonically equivalent source/target pair without changing either name.
`ScanWarning` also prevents malformed optional exception detail from blocking
otherwise valid inventory observations: it omits that entire detail to the
existing empty string, retaining the warning code and valid parent path. This
does not remove a warning or make an incomplete scan complete. Already escaped
display spellings remain unchanged. Valid-Unicode detail is retained unchanged
through 1,024 UTF-8 bytes; a larger complete value is omitted rather than
truncated.

`WalkingScanner.scan()` freshly re-admits the exact root, canonical scope, and
bounded trusted anchor before its first backend call. Every backend
`VolumeSnapshot` is an exact typed value whose identity, evidence, and
capability fields are revalidated before anchor or filesystem policy consumes
them, including the second binding probe. Workflow consumers independently
adopt each returned exact `ScanResult` once, require its root and scope to match
the request, and share that immutable identity with first-party read-only
consumers. Inventory performs the same adoption before ledger registration;
later recorder validation uses the shared nonconstructing exact-shape check.

## Walking Rules

1. Lexically normalize the root without following links, then no-follow reject
   a file, placeholder, junction, symlink, or other reparse component below the
   trusted native volume root (or inventory's reviewed mount). The anchor itself
   is the trust boundary: a FULL root may carry its folder-mount reparse tag only
   when the resolved root, reviewed/current anchor, and volume-evidence mount
   agree exactly. No configured-root-chain component, exact scoped start, or
   enumerated descendant inherits that exception.
2. Resolve volume/capability evidence once for the scan, then revalidate the
   trusted anchor, full volume identity, and lexical root before enumeration. An
   authorized folder-mount root is first classified without following and then
   metadata-statted through the mount so its root record and visited identity
   describe the mounted volume rather than the host reparse entry.
3. Enumerate entries without following reparse points by default.
4. Apply location ignores before descending into an ignored subtree.
5. Check `ctx.checkpoint()` between entries/directories.
6. Record size, mtime, stable identity when supported, link count, and
   `MetadataSnapshot(attributes, created_ns)`. Every `DirRecord` carries the
   same metadata shape plus optional identity. The scanner never enumerates
   ADS and receives no preservation policy.
7. Track visited directory identity across every recursive root so junctions,
   cross-root aliases, and mount loops terminate.
8. Classify cloud/offline placeholders from attributes/reparse tags without
   hydrating or reading them.
9. Revalidate the trusted anchor, full volume identity, and lexical root before
   returning. If they changed, discard the accumulated observations rather
   than attribute them to the original root.
10. Record access/type/collision/hardlink warnings and set `complete=False` for
   any uncertainty that could make one side appear absent.
11. Reject Windows-ambiguous suffixes, device spellings, stream qualifiers,
    traversal, NUL, and unpaired surrogates at the path boundary. Diagnostic
    text escapes hostile code units rather than inserting them into path-bearing
    records, serialized plans, or terminal output.

Root identity and scan evidence always use ordinary absolute drive or UNC
spelling. The native backend adds the Windows extended-length prefix only for
root probes, volume calls, stat, and enumeration, and strips it before returning
the lexical `Root` or `VolumeEvidence`; it never resolves a configured root
through an unclassified link in its root chain. The followed root stat is added
only for an exact authorized folder mount; ordinary roots and scoped scans add
no filesystem call. Non-filesystem device
namespaces are refused rather than reinterpreted as managed roots. Extended
roots whose
components cannot be represented stably without the prefix—including trailing
dot/space and reserved DOS device names—are also refused, preventing a reviewed
root from normalizing onto a different sibling. Native error filename fields
are converted back to logical spelling before entering scan warnings.

The three scan-level authority brackets retain their established order: a
chain-only admission precedes the reviewed volume snapshot; immediately before
enumeration and again after it, chain admission precedes the fresh anchor and
volume comparison. A chain failure remains `ROOT_UNAVAILABLE` and stops the
later binding probes; a binding failure remains `VOLUME_UNAVAILABLE`.

Built-in ignores use exact names or exact generated-name grammar. `.synctrash`
is excluded as an owned root; a user filename merely containing `.synctmp-`,
ending in `.db`, or resembling a checksum sidecar is not excluded.

## Completeness And Scope

A full scan is complete only modulo its supplied scan ignores. An unreadable or
unrepresentable entry, case collision, uncertain reparse traversal, or root
identity change makes the scan reviewable but non-executable where absence
could drive mutation.

Exact-path and recursive-subtree refresh are distinct scoped observation modes.
A complete exact result may classify a conclusively absent named key as
missing, but never implies descendant absence. A complete subtree result covers
each retained root, all of its descendants, and any additional exact paths.
`ScanResult.is_full_scan` remains true only for `FULL`; the recorder branches
explicitly on all three kinds after checking completeness.

Subtree roots use the full-walk ignore contract: ignored descendants do not
make the scan incomplete. A missing subtree root is a conclusive empty
observation. A denied or otherwise unreadable root emits `ROOT_UNAVAILABLE`
with that root's relative path and makes the whole mixed result incomplete. A
former directory that is now a file is recorded as that file. File
placeholders and file reparse points are conclusive unsupported observations;
directory placeholders, directory reparse points, and repeated directory
identity remain incomplete because descendants could not be observed. Any
incomplete root withholds missing inference for the entire mixed scope.
Directory reparse classification uses both stat mode and Windows'
`FILE_ATTRIBUTE_DIRECTORY`, because no-follow directory-entry probes may
report a directory link as non-directory. A provisional file-only owned-temp
ignore therefore confirms that attribute before skipping the entry; exact-name
and `.synctrash` ignores remain unconditional. Every `FULL`, `PATHS`, and
`SUBTREES` scan first requires the location root chain below its trusted mount
to remain ordinary non-reparse directories or the result is `ROOT_UNAVAILABLE`
and incomplete. A FULL root equal to that exact trusted folder mount remains
admissible only when it is a non-placeholder directory, its followed state is
ordinary, and the existing before/after anchor plus `VolumeId` brackets hold.

PATHS subjects and SUBTREES starts no-follow admit every existing ancestor
below the managed root before touching their final subject. A missing ancestor
is conclusive selected absence. A placeholder, reparse, nondirectory, or
unavailable ancestor records the selected subject as unsupported, makes the
scope incomplete, and prevents the final stat or subtree enumeration. This
relative walk begins below the managed root: scoped descendants cannot inherit
FULL's exact folder-mount exception, while a scoped scan beneath that reviewed
mount still does not follow the mount root itself. These pathname probes do not
close component replacement after admission; handle-relative traversal remains
the stronger future boundary.

An offline/unmounted volume is not an empty complete scan. It yields a typed
offline result and cannot trigger missing marking or target-only planning.

## Capability Profile

At minimum record filesystem type, timestamp granularity, stable file-identity
support, seek-penalty knowledge, maximum path behavior, ADS support, and
`supports_hardlinks` read from `FILE_SUPPORTS_HARD_LINKS` rather than a probe or
filesystem-name table. ADS support is one volume-capability bit only; collecting
it does not inspect any file's streams.
Unknowns degrade conservatively: unknown seek penalty behaves like HDD for any
future parallelism decision; absent stable identity disables identity moves;
coarse timestamps control planner comparison tolerance.

At the active checkpoint-3.2 scalar cutover, scanner projects unsupported numeric and native
identity observations through the exact typed outcomes in
[M1_BRIDGE.md](M1_BRIDGE.md) and [DEFENSE.md](DEFENSE.md) §1.3; it defines no
local numeric domain or fallback. Stable NTFS/ReFS identity comes from the
shared complete-file-id adapter, and a path-local
`scalar_unrepresentable` warning marks an otherwise observable entry whose
size or timestamp cannot enter the signed-64 domain.

The stable volume key is `(serial, fs_type)`; labels are mutable corroborating
evidence. Relabeling does not rebind, a changed filesystem type does, and
simultaneous duplicate keys require explicit user choice.

## Expectations Of Other Modules

- Core supplies path, identity, warning, capability, and result types.
- Workflow supplies the scan ignore policy and session/error handling.
- Planner preserves incomplete-scan evidence and warnings in the full reviewed
  plan. Workflow permits only the evidence-positive additive/noop subset and
  withholds destructive/identity work; scanner itself decides neither.
- Inventory reconciles full, exact-path, and subtree scans through distinct
  branches and never writes from the scanner itself.
- Dispatcher supplies checkpoint behavior and holds required custody where the
  scan participates in a mutating workflow.

## Latent Implementations

The future USN `ChangeSource` must produce the same `ScanResult` semantics,
including a defensible completeness boundary and fallback to a full walk after
journal gaps, wrap, identity change, or unsupported volumes. Network scanning
must declare weaker identity and coordination guarantees rather than imitating
NTFS. Neither implementation changes planner or inventory contracts.

## PoC Hardening

- Exact built-in matching avoids the PoC user-`.db` data-loss bug; live database
  placement guards keep NamiSync databases outside managed roots.
- Per-entry error capture prevents permission errors from aborting the walk.
- Contract-invalid NTFS/SMB names produce typed escaped evidence instead of
  aborting enumeration or contaminating safe relative-path contracts.
- Checkpoints restore cooperative cancellation.
- Visited identity and reparse classification close the open junction-cycle
  gap.
- Scanner never refreshes stored baselined metadata directly; that PoC bug is
  prevented by inventory/recorder conditional rules.
