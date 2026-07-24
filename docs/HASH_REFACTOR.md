# Hash Pipeline, XXH3, and Executor IO Refactor

Status: investigation and planning last revised 2026-07-24. M1 Stage 1
prerequisites are implemented: the standard-library-only streaming hasher
protocol, compatible `xxhash>=3.8.1,<4` project dependency,
ledger-v2/history-v3 schema/reset boundary, and removal of the fingerprinted
`worker_count` setting. Neither performance track below is implemented. This
document records two independent M1 performance tracks:
an adaptive single-file copy backend with cheaper finalization, and the
wholesale replacement of SHA-256 content hashing with XXH3-128.

**Standing.** This document governs the unimplemented hash-throughput work
until each decision is promoted into the active documents. `FEATURES.md` owns
behavior, `ARCHITECTURE.md` owns contracts, and module documents are
subordinate to both. Where this plan changes a settled contract, the active
document is updated as that track lands. Once promoted, the active document
wins and this file becomes history.

**Destructive boundary.** This refactor carries no hash-import feature and no
database compatibility path. M1 deletes and recreates both the main ledger and
history databases so every retained content-evidence row starts under the
single XXH3-128 contract.

---

## 1. What Prompted This

Benchmarking showed two independent limits in the current
`NativeCopyBackend.copy` loop:

1. `read -> write -> hash` is serialized in one thread, leaving substantial
   source and target throughput unused even without hashing.
2. SHA-256 caps a pipelined copy at roughly 2 GiB/s per hashing thread on the
   development machine.

Static inspection also found fixed per-file costs that throughput-only
microbenchmarks did not measure: starting two workers for tiny files,
preallocating temps too small to benefit, rebuilding Win32 bindings, flushing
the temp twice, reopening it after metadata, and replaying all metadata after
publish even when publication preserved it.

The first problem therefore calls for one bounded three-stage pipeline used by
every copied file, with its chunk size derived from the reviewed source size.
The second calls for a faster content hash. The remaining fixed costs call for
fewer native setup calls, conditional preallocation, one pre-publish file
durability barrier, and conditional post-publish metadata repair. These
changes complement one another but solve different problems: XXH3-128 removes
hashing as the reason to execute multiple files concurrently; it does not
remove the need to overlap reads, writes, and hashing or to reduce per-file
executor overhead.

---

## 2. Measurements

### 2.1 Bench Environment

- CPU: Intel Core i7-13700K, 16C/24T, SHA-NI present
- RAM: 64 GB
- Python 3.13.14, `xxhash` 3.8.1
- Source: `F:` - WD_BLACK SN850X 4 TB
- Target: `G:` - WD_BLACK SN850X 4 TB (separate physical disk)
- 8 GiB workload, 4 MiB chunks (the `chunk_size` default in
  `executor.py` and `integrity.py`)
- Two IO regimes: an unbuffered ceiling (`FILE_FLAG_NO_BUFFERING`,
  sector-aligned buffers) and the buffered production shape
  (`open(buffering=0)` FileIO with immutable `read()`), which is what the
  design ships
- All throughput figures are Python microbenchmarks, harness-bound rather than
  storage-bound (see the caveat at the end of 2.4)

The unbuffered ceiling is a reference bound, not the shipped path. A first pass
using ordinary buffered IO with a 1 GiB file on a 64 GB machine measured a
fully page-cached read leg on the slower `C:` volume and understated the hash
cost by roughly half. Any cache-cold re-measurement must defeat the page cache
and must not silently copy within one volume when the intent is cross-volume.

### 2.2 Hash Throughput, Single Thread, No IO

| Algorithm | MiB/s |
|---|---:|
| xxh3_128 | 35 433 |
| xxh3_64 | 34 491 |
| xxh64 | 19 616 |
| sha256 | 2 441 |
| blake2b | 1 067 |

SHA-256 is hardware-accelerated on this CPU and is consequently faster than
BLAKE2b and MD5. XXH3-128 is nevertheless roughly 14.5 times faster than
SHA-256 and fast enough to leave storage or the copy loop as the bottleneck.

### 2.3 IO Ceilings

| Operation | MiB/s |
|---|---:|
| read-only, unbuffered | 5 433 |
| write-only, unbuffered | 5 316 |

### 2.4 Copy Loop: Serial vs Pipelined

Two IO regimes were measured. The unbuffered numbers establish a storage
ceiling and are not the shipped path; the buffered numbers are the production
shape the design implements (DR-HASH-06).

Serial is the exact current `NativeCopyBackend.copy` shape: `read -> write ->
update` in one thread. The original pipelined prototype used separate
reader/coordinator, writer, and hasher stages over a forked recycled-buffer
pool. Digests were asserted identical between the two shapes for every
measured algorithm.

**Unbuffered ceiling** (`FILE_FLAG_NO_BUFFERING`, sector-aligned buffers):

| Algorithm | Serial MiB/s | Pipelined MiB/s | Gain |
|---|---:|---:|---:|
| none (hashless) | 2 637 | 5 254 | +99.2% |
| xxh3_128 | 2 118 | 5 318 | +151.1% |
| sha256 | 1 261 | 1 910 | +51.5% |
| blake2b | 591 | 971 | +64.1% |

**Buffered production shape** (`open(buffering=0)` FileIO, immutable `read()`,
linear `reader -> hasher -> writer`, target temp preallocated), XXH3-128:

| Configuration | MiB/s | vs serial |
|---|---:|---:|
| serial read() (today) | ~1 234 | - |
| pipelined read() + preallocation (measured large-file shape) | ~2 700-3 100 | +120% to +150% |

The buffered path reaches roughly half the unbuffered ceiling because cached
writes cross memory twice and the cache manager schedules writeback. The design
accepts that in exchange for no alignment constraint, no partial-tail handling,
and no volume-rejection fallback; the unbuffered ceiling is recorded as a
deferred option, not a plan.

Run-to-run variance across passes was roughly 5% (unbuffered hashless serial
measured 2 680 and 2 637; SHA-256 serial 1 189 and 1 261). Treat all figures as
approximate; the ratios, not the absolute rates, are the finding.

**These absolute figures are harness-bound, not storage-bound.**
CrystalDiskMark reports the same SN850X target sustaining about 5 475 MiB/s
sequential write at QD1 and 6 530 at QD8, above every pipelined figure here.
GIL contention, per-chunk queue handoff, and syscall overhead cap the Python
prototype below device speed, so a native implementation would post higher
absolute rates. What transfers to production is the structure, that overlapping
the stages roughly doubles serial throughput, not the specific MiB/s.

Follow-up microbenchmarks compared that fork with a linear
`reader -> hasher -> writer` pipeline using immutable `read()` chunks. Their
throughput difference was within measurement noise. `readinto()` with
recycled mutable buffers was about 10% faster in isolation, but requires the
lease and reuse protocol rejected by DR-HASH-06. Preallocating the target temp
improved both shapes by about 10% (measured with `truncate()`; the shipped
`FileAllocationInfo` request is expected to match or exceed it).

A controlled contention pass ran both topologies at shallow (two-slot) and
deep (eight-slot) queue depth under an 8-16 thread external optimizer,
interleaved to equalize load exposure and hold execution order fixed:

| Depth | line/fork ratio |
|---|---:|
| 2 (shallow) | ~0.95-1.01 |
| 8 (deep) | ~1.04-1.10 |

The line's disadvantage under load is small (single-digit percent) and shifts
in the direction deep queues predict: a deeper write queue lets the writer coast
through hasher preemption, so line at depth 8 matches or slightly beats fork.
An earlier run had shown a much larger line-specific dip, but that ran line last
on a write-thrashed drive; once order and drive state are controlled, the
pure CPU-contention effect is minor. This is the second reason to size the
queue near eight chunks rather than two (2.4 memory paragraph and 4.1).

Starting two workers per file cost about 10% at 4 KiB and became negligible
by 4 MiB. That isolated result does not establish the production crossover:
filesystem open, metadata, flush, publish, and recording costs dominate tiny
files, so avoiding worker startup has no demonstrated user-visible benefit.
Track 1 accepts that bounded cost and uses the same pipeline for every size.
A lazy worker-spin-up fast exit remains documented only as a deferred option
gated by a directory-level workload, not the isolated 4 KiB result.

### 2.5 What the Numbers Mean

The rates in this subsection are the unbuffered-ceiling figures; they isolate
where hash cost sits relative to IO cost. The shipped buffered path lands lower
in absolute terms (2.4) but the hash-versus-IO decomposition below holds, and
the harness caveat applies.

**The serial loop wastes roughly half the available IO throughput before
hashing enters the picture.** Hashless serial reaches 2 637 MiB/s against
disks that sustain 5 300+ MiB/s because the stages run consecutively.
Pipelining recovers the hashless path to 5 254 MiB/s.

**SHA-256 currently costs 52% of achievable serial throughput** (2 637 to
1 261 MiB/s). In the pipeline it becomes the slowest stage and caps the path
at roughly 1 900-2 400 MiB/s.

**XXH3-128 makes hashing negligible but does not replace pipelining.** Serial
XXH3-128 reaches only 2 118 MiB/s; pipelined XXH3-128 reaches 5 318 MiB/s.

| Configuration | MiB/s | vs today |
|---|---:|---:|
| Serial + SHA-256 (today) | 1 261 | - |
| Pipeline only, keep SHA-256 | 1 910 | +51% |
| Algorithm only, stay serial | 2 118 | +68% |
| Pipeline + XXH3-128 | 5 318 | +322% |

These are unbuffered-ceiling rates; the shipped buffered path scales down
proportionally (2.4). The point is the decomposition: neither change alone
clears ~2 GiB/s, and only both together remove hashing as a limit.

### 2.6 Where the Algorithm Change Matters

Pipelined SHA-256 saturates at roughly 1 900-2 400 MiB/s. Below that, the copy
path is already storage-bound and changing the hash does not improve transfer
speed. The algorithm replacement is therefore a fast-path optimization for
high-throughput storage, while the pipeline addresses structural
serialization on every medium.

That threshold assumes SHA-NI. The measured 2 441 MiB/s SHA-256 rate depends on
those extensions, absent from mainstream Intel desktop parts from roughly 2015
to 2020 (Skylake through Comet Lake). Without them a portable software SHA-256
runs closer to 600-800 MiB/s, below every SSD in the test set, so on those
machines SHA-256 would bottleneck nearly every copy rather than only the
fastest, while XXH3-128 stays memory-bound at tens of GiB/s regardless. The
replacement therefore helps more on weaker or older CPUs, not less; the
fast-path framing above is the SHA-NI best case for the retired algorithm.

The replacement still has a broader architectural benefit: a single XXH3-128
stream is fast enough that NamiSync does not need concurrent file execution or
parallel verification merely to overcome content-hash CPU throughput.

### 2.7 Bench Reproduction

The bench scripts are session scratch artifacts and are not committed. A
reproduction must:

1. Use unbuffered handles and correctly aligned buffers, or otherwise prove
   that reads are cache-cold.
2. Use a workload comfortably larger than plausible cache effects.
3. Copy across two physical volumes and record which volumes.
4. Assert digest equality between serial and pipelined shapes.
5. Report a hashless baseline alongside hashed measurements.
6. Also benchmark the actual buffered executor path before treating the
   unbuffered throughput as a production guarantee.
7. Sweep realistic file-size distributions, not only one large file, and
   validate the fixed adaptive chunk bands, find the preallocation crossover,
   and report total operations per second and fixed finalization time
   separately. The standard synthetic distribution is 1,000×4 KiB,
   512×128 KiB, 64×4 MiB, 4×128 MiB, and 1×4 GiB, run cross-volume. Parts may
   be re-run in isolation, but the small-file band is mandatory: it is the only
   measurement that validates pipelining every size (2.4), and its per-size
   operations/second is the number M1 gates on (`M1_PLAN.md` §5).
8. Record reader-blocked time, writer-starved time, and resident-payload
   high-water bytes so queue tuning is based on stage starvation rather than
   throughput alone.

Figures re-derived on other hardware should be recorded with their own
environment block rather than overwriting these results.

---

## 3. Decision Log

### DR-HASH-01 - Keep the pipeline and algorithm tracks independent

**Tension.** Both changes improve throughput, but they address different
limits and have different failure surfaces.

**Resolution.** Implement the all-size adaptive-chunk pipeline and its executor
IO/finalization reductions as an independent track. The XXH3-128 replacement
neither absorbs nor weakens that work.

**Why.** The pipeline changes concurrency and cancellation inside the byte
loop but no evidence format. The hash replacement changes the content-evidence
contract and dependency but requires no concurrent file execution. Either can
be implemented and verified without making the other partially present.

The tracks are independent in semantics, not in diff surface: both edit
`NativeCopyBackend`. Land Track 1 first using whichever canonical content
hasher exists in that revision, then let Track 2 replace construction of the
hasher stage with the fixed XXH3-128 factory seam. This keeps Track 1
independently shippable and minimizes merge/conflict churn.

### DR-HASH-02 - Use one canonical content algorithm: XXH3-128

**Tension.** Supporting SHA-256 alongside XXH3-128 would retain a
cryptographic option but would introduce algorithm selection, per-item
dispatch, configuration, mixed-algorithm behavior, and a larger test matrix.

**Resolution.** Replace SHA-256 content hashing wholesale with XXH3-128.
NamiSync exposes no content-hash setting and supports no alternative canonical
content algorithm in M1.

**Why.** NamiSync's integrity promise covers accidental corruption and media
defects, not deliberate adversarial modification. XXH3-128 supplies a
128-bit content fingerprint at throughput well above the measured IO ceiling.
Keeping SHA-256 would add product semantics without serving a current product
requirement.

The algorithm identifier remains part of stored content evidence so evidence
is self-describing. Its only accepted value is `xxh3_128`, and its digest is
exactly 16 bytes.

A required `hasher_factory` collaborator does not weaken this decision. It is
dependency inversion for the concrete package, not algorithm selection: the
factory takes no algorithm name, core accepts only the `xxh3_128` identifier,
and `ContentEvidence`/`CopyDigest` reject any digest that is not exactly 16
bytes. Verifier validates the produced digest length before baseline
comparison, so a bad factory is an internal contract failure rather than a
false `HASH_MISMATCH`. There is no registry, lookup, or configurable branch to
generalize.

### DR-HASH-03 - Limit the replacement to content evidence

**Tension.** NamiSync also uses SHA-256 for plan fingerprints, selection
digests, custody keys, history chaining, and recorder identity. Those hashes
protect canonical internal contracts rather than bulk file throughput.

**Resolution.** Replace SHA-256 only in the copy-attestation and integrity
verification paths. Internal control-plane and database identity hashes remain
SHA-256.

**Why.** Those inputs are small, so changing them provides no measurable
performance benefit and needlessly changes stable identifiers and custody
contracts.

### DR-HASH-04 - Defer cross-file parallelism until measurements require it

**Tension.** Concurrent file execution and verification can improve some
multi-device or small-file workloads, but they add scheduling, memory,
progress, cancellation, and device-contention complexity.

**Resolution.** M1 uses one file operation at a time. Every normal content
copy pipelines that file's read, write, and hash stages. The separate hashless
trash-backup loop remains serial as specified in 4.1. Verification remains
single-stream. Parallel file execution or verification requires a later
benchmark showing a real workload that remains underutilized after XXH3-128.

**Why.** The measured XXH3-128 stage is not the bottleneck. Concurrency should
solve observed device utilization, not compensate for the retired SHA-256
ceiling.

### DR-HASH-05 - Drop hash import and reset both databases

**Tension.** Existing development ledger evidence is SHA-256-bound, while the
new core contract accepts only `xxh3_128`. Preserving old rows would require
multi-algorithm semantics or a conversion path that this refactor explicitly
rejects.

**Resolution.** Hash import is not part of M1 or the active product scope.
NamiSync does not parse or import checksum sidecars and does not provide an
`import-hashes` workflow, command, recorder path, or history activity.

The refactor is a destructive unreleased boundary: delete and recreate both
the main ledger and history databases. No ledger rows, content evidence,
history rows, or run details are carried across it, and no database converter
is implemented. Settings files are not databases and are not part of this
reset.

Both schema versions are bumped and every older version is refused. The
existing history v1→v2 shortcut is removed or disabled before raising
`HISTORY_SCHEMA_VERSION`: its current implementation writes the current
constant and would otherwise mislabel a v1 database as v3 after applying only
the v2 shape. Ledger v1, history v1, and history v2 all take the same
actionable reset path.

The new schema *shapes* this reset materializes are owned by `M1_PLAN.md`
Stage 1, not by this document. The history-v3 shape in particular includes the
generic-item and phase-summary storage that DR-M1-10 reserves at this single
boundary so Stage 4 needs no second bump. Recreating a hash-only history schema
that omits that reserved storage is a defect against M1, not a smaller-scope
convenience: the coordinated reset here must land the full Stage 1 shapes.

**Why.** There is no production database liability. A clean reset is cheaper
and safer than retaining SHA-256 evidence that the new fixed contract cannot
validate. Runtime handling remains explicit rather than silently interpreting
old bytes: an old schema/version is refused with an actionable reset message;
development/test upgrade steps remove the old local database files and let
NamiSync create fresh ones.

### DR-HASH-06 - Use immutable reads and a linear pipeline

**Tension.** A forked `readinto()` design can reuse mutable buffers and was
about 10% faster in a microbenchmark, but `CopyBackend` accepts `BinaryIO`,
whose required read operation is `read()`. Safely sharing and recycling a
mutable buffer between independent writer and hasher consumers requires
leases, a dual-acknowledgement join, discard state, and careful teardown.

**Resolution.** Retain `source.read(chunk_size)` and pass each immutable
`bytes` object through a bounded `reader -> hasher -> writer` pipeline. The
caller performs reads, one worker hashes each chunk before forwarding the
same object, and one worker writes it. A single combined byte budget governs
the object from admission before its read until full writer completion; the
two handoff queues do not each receive an independent payload allowance.

The line's one structural weakness relative to the fork is that its writer is
fed through the hasher rather than directly, so a preempted hasher can stall the
writer under external CPU load. Controlled measurement (2.4) put that
disadvantage in the single-digit percent range and showed a deep queue closing
it; the larger dip seen in an early run was drive-state degradation compounded
with load, not the topology. The chosen ~eight-chunk queue depth (4.1) is the
mitigation, so this weakness does not offset the linear pipeline's structural
simplicity.

**Why.** In a linear pipeline, writer completion proves that the chunk was
already hashed, so progress needs one acknowledgement rather than a join of
two asynchronous consumers. Immutable objects make reuse races impossible,
one byte ledger makes the memory ceiling truthful across both queues, and
follow-up measurements found no meaningful throughput difference between the
line and fork topologies.

### DR-HASH-07 - Pipeline every size and adapt only the chunk

**Tension.** A fixed 4 MiB read is proven for large files but gives small and
medium files few chunks to overlap and sets a coarse checkpoint interval.
A size-selected dual-engine serial/pipelined hybrid avoids worker startup on
tiny files, but it adds backend selection, protocol inputs, threshold policy,
and a larger cancellation/failure test matrix for a benefit measured only in
an isolated 4 KiB microbenchmark.

**Resolution.** Every normal copy uses the same
`reader -> hasher -> writer` pipeline, including empty and sub-chunk files.
`_prepare_copy()` derives a positive actual `chunk_size` from the reviewed
source size and `ExecutorPolicies.max_chunk_size`, then passes that actual
value through the existing `CopyBackend.copy(..., chunk_size=...)` contract.
`CopyBackend` does not receive `expected_size`, choose an engine, or reinterpret
`chunk_size` as a ceiling.

Use this fixed M1 policy, based only on the reviewed source size:

| Reviewed size | Selected chunk |
| --- | ---: |
| less than 8 MiB | 256 KiB |
| at least 8 MiB and less than 32 MiB | 1 MiB |
| at least 32 MiB | 4 MiB |

Then cap the selected value by `max_chunk_size`. The 8 MiB and 32 MiB
promotion points each start the new band with eight chunks, while a conforming
file below either promotion has at most 32 chunks. Switching directly to a
4 MiB chunk at a 4 MiB file would instead collapse that file to one chunk and
remove the overlap the pipeline is intended to create. A smaller candidate is
not justified: there is no evidence that extra 64 KiB queue handoffs below
256 KiB repay their cost while fixed open, worker, metadata, flush, and publish
work remains. Revisit the table only with a production-shaped distribution
benchmark, not as an implementation-time tuning choice.

Zero-byte files select 256 KiB before the policy ceiling is applied and
immediately encounter EOF. The selected value remains fixed for the whole copy
even if the source grows; the backend still reads to actual EOF and the
executor classifies the size mismatch as `SOURCE_DRIFT`. The values and bands
are private executor constants, not user settings. This adaptive policy
applies only to normal `CopyBackend` copies. The dedicated copied-backup loop
and the non-pipelined verifier retain their 4 MiB read chunks unless their own
measurements justify a change.

Target-temp preallocation remains independently conditional because temp
creation already has the reviewed size. `_prepare_copy()` passes an allocation
request only above its measured crossover; zero-byte and smaller copies skip
it. Only allow-listed errors that mean `FileAllocationInfo` is unsupported
fall back to ordinary streaming; disk-full, quota, permission, unknown, and
other substantive failures remain operation failures.

**Why.** Size affects one scalar chosen before the backend call, while
streaming, hashing, progress, cancellation, and teardown retain one code path.
Renaming only the executor policy to `max_chunk_size` makes its ceiling role
explicit without changing the `CopyBackend` protocol. Lazy worker spin-up is
deferred rather than left as unmeasured production structure.

### DR-HASH-08 - Finalize each temp once before publication

**Tension.** The current path flushes the writer, closes it, applies ACL and
metadata, reopens the temp, and flushes it again. After publication it
unconditionally reapplies the complete metadata set through `os.utime`,
creation-time and attribute calls, even when only a deferred readonly bit (or
nothing) requires repair.

**Resolution.** Close the content writer before final metadata so close-time
timestamp behavior cannot overwrite the intended values. Open one native
finalization handle for the temp before applying a preserved ACL, so a
restrictive copied descriptor cannot prevent the remaining work from
reopening the file. Keep that handle while the ACL is applied. Through it,
query and apply the intended `FILE_BASIC_INFO` fields while preserving
unmanaged attributes and the current `os.utime` behavior of setting last
access equal to mtime, capture the filesystem-normalized basic metadata, and
issue exactly one `FlushFileBuffers(temp)`. That is the only
file-data/metadata durability barrier before the atomic publish.

Readonly remains withheld from the temp when it could obstruct publication.
After publish, stat the target and compare it with the finalized temp
observation, plus any deferred readonly state. Comparing with the observed temp
rather than raw source nanoseconds avoids treating target-filesystem timestamp
rounding as publication damage. Check every field NamiSync promises to
preserve: mtime, optional creation time, and the managed readonly/hidden/system
attributes. If they already match, reuse that stat for the published-size
guard and attestation and do not reopen or rewrite the file. If any field
differs, repair only the differing managed fields through one native handle,
flush that handle, close it, and restat before attestation.

Post-publish repair is stat-driven rather than gated only on the intended
readonly bit. Windows file-name tunneling may restore metadata such as creation
time during rename/replace, so "no readonly requested" is not proof that all
published metadata survived. Conversely, an unconditional full replay is not
needed when the observed values already match.

Copied backups share only the sequential source opener, full-write helper, and
close/finalize/single-flush/publish/conditional-repair filesystem primitives.
They retain a dedicated hashless serial byte loop and do not use
`CopyBackend`, pipeline workers, adaptive chunk selection, or preallocation
in Track 1. A copied backup reads the old target and writes its trash temp on
the same target volume, and the measured cross-volume hashed-pipeline result
does not establish a benefit for that shape. Reconsider backup pipelining or
preallocation only with a separate hardlink-unsupported update benchmark.

An update using a hardlink backup is a required special case: clearing
readonly on the live old inode also clears it on the trash hardlink. Restore
and flush that displaced inode when required before recording the update.

Directory flushing is unchanged. Parent directories are still flushed after
publication and before durable recording; reducing file-handle flushes does
not weaken namespace durability.

**Why.** The first current flush is superseded by the later flush after ACL
and metadata. One finalization handle eliminates repeated opens and path-based
metadata calls, while the post-publish observation preserves the existing
metadata contract and closes the current gap where replayed target metadata
is not followed by a target-file flush.

### DR-HASH-09 - Bind native functions once and use the cached sequential hint

**Tension.** `NativeFileSystem` currently rebuilds `kernel32` or `advapi32`
objects and ctypes signatures inside per-file operations. Source files are
read strictly from beginning to end, but their cached handles do not carry an
explicit sequential-access hint. Adding another application readahead system,
however, would duplicate the pipeline's bounded lookahead.

**Resolution.** On Windows, load the required DLLs and bind argument/return
types once behind an OS guard. Native filesystem methods reuse those bound
callables. Open cached source descriptors with `O_BINARY | O_SEQUENTIAL` and
wrap them as unbuffered Python file objects; retain equivalent sharing,
long-path, and close ownership behavior.

The pipeline's combined in-flight byte window is NamiSync's application-level
readahead. `O_SEQUENTIAL` is complementary OS-level read-ahead: it lets the
Windows cache manager prefetch cached pages outside NamiSync's application
payload queues, without creating app-owned chunks, completion records, or
another cancellation path. "Do not add another source-prefetch queue" means
do not add a second application buffering layer or multiple outstanding reads
to the buffered backend; it does not prohibit the cache-manager hint.

**Why.** Binding once removes pure setup repetition. The sequential flag gives
the Windows cache manager accurate access intent at the handle boundary with
no new buffer-ownership protocol. Additional asynchronous read depth belongs
to a separately measured direct-IO design, not this buffered pipeline.

---

## 4. Implementation

### 4.1 Track 1 - Adaptive-Chunk Pipeline and Finalization

Land Track 1 in reviewable steps, running focused executor tests after each:

1. hoist Win32 bindings and add the cached sequential source hint;
2. consolidate pre-publish metadata and the remaining temp flush into one
   native finalization handle, then make post-publish repair observational and
   conditional;
3. rename the executor policy to `max_chunk_size`, derive the actual
   `chunk_size` before the backend call, and add measured conditional
   preallocation; and
4. add the linear pipeline with one combined byte budget and deterministic
   teardown.

This order takes the fixed per-file reductions first and leaves the concurrency
change until finalization and the current copy behavior are stable.

The pipeline remains contained inside `NativeCopyBackend` in
`modules/executor.py`. Keep the `CopyBackend.copy(..., chunk_size=...)`
protocol unchanged: `chunk_size` is the positive actual read size for that
call. Rename only `ExecutorPolicies.chunk_size` to
`ExecutorPolicies.max_chunk_size`, retaining its 4 MiB default.

Before creating the temp, `_prepare_copy()` calls one private pure helper with
the reviewed source size and policy maximum. The helper returns the actual
chunk size from the fixed 256 KiB / 1 MiB / 4 MiB table at the 8 MiB and
32 MiB boundaries, capped by the policy maximum. Pass that value to
`CopyBackend.copy()`. The backend does not receive the reviewed size, revise
the selection if the source grows, or have a serial/pipeline selection branch.

Every invocation uses the calling thread as reader/coordinator plus one hasher
thread and one writer thread, including empty and very small files. Use
`source.read(chunk_size)` for ordinary reads. Each read returns a fresh
immutable `bytes` object, and the same object moves through two FIFO queues:

```text
caller/reader -> hash queue -> hasher -> write queue -> writer
                                                   \
                                                    completion size
                                                           |
                                                           v
                                                    caller/on_chunk

steady state:
reader: chunk 5    hasher: chunk 4    writer: chunk 3
```

The hasher updates its streaming digest before placing the chunk on the write
queue. The writer retains the existing short-write loop and publishes the
chunk size to a nonblocking completion queue only after the entire chunk has
been written. Therefore one writer completion proves both hash and write
completion. A single FIFO path also makes completion order identical to read
order without sequence numbers or an acknowledgement join.

Do not use `readinto()`, mutable recycled buffers, a free-buffer pool, leases,
reference counts, or discard flags. Python object references own chunk
lifetime.

Only one file streams at a time (DR-HASH-04), so per-copy memory is not scarce
and the byte budget is chosen for throughput, not to minimize RAM. Reserve
from one combined in-flight payload budget before each read, adjust the charge
down for a short final chunk, and release it when the coordinator drains that
chunk's writer completion. Release the whole reservation immediately on EOF
or a read failure before a payload is admitted. On abort, shut down and join
both workers before the coordinator clears the remaining ledger and wakes any
waiter; workers never release credits. This single ownership rule prevents a
writer-completion/abort race from releasing the same charge twice. The same
chunk is charged once across its entire lifetime, not once per queue. Keep a
separate item cap on each FIFO to bound control objects and catch accounting
defects, but do not derive resident memory by adding two independently full
byte allowances.

The combined payload window remains ~32 MiB: eight chunks at the 4 MiB maximum
and more items when the adaptive policy selects a smaller chunk. Cap each FIFO
at 32 entries. With the default 4 MiB policy ceiling and a source matching its
reviewed size, the two smaller bands contain no more than 32 chunks in the
entire file, while the byte budget limits the 4 MiB band to eight resident
chunks. A source that grows across its reviewed band, or a deliberately lower
`max_chunk_size`, may encounter the item cap before filling 32 MiB. Those paths
may run with a shallower window but must remain correct and deadlock-free; a
smaller configured ceiling is not entitled to the default throughput shape.
The 2 GiB/s-class measurements used the eight-by-4-MiB shape; a shallow
two-slot equivalent need not reproduce them. Budget beyond what covers writer
jitter adds RAM without throughput, since the slowest stage still sets the
rate.

Payload depth also absorbs external CPU contention. In the line topology the
writer is fed through the hasher, so a preempted hasher can starve the writer;
a deeper write queue gives the writer buffered chunks to consume across that
gap. A contention pass (2.4) confirmed the direction at the 4 MiB maximum: the
line's small under-load disadvantage at two slots closes by eight. The same
32 MiB budget, rather than a fixed item count, carries that protection across
adaptive chunk sizes.

Normal EOF is an explicit sentinel. The hasher finalizes the digest and
forwards EOF only after consuming every preceding chunk; the writer reports
successful completion only after consuming every preceding write. The caller
performs a final completion drain, joins both workers, validates their result,
and only then returns `CopyDigest`.

#### Native binding lifetime

Move `kernel32` and `advapi32` loading plus every ctypes `argtypes`/`restype`
declaration out of per-file methods. Initialize the bindings once under the
existing Windows platform boundary and reuse them for allocation, security,
basic metadata, attributes, volume identity, flushing, and handle closure.
Keep platform-neutral fallbacks callable without importing Windows-only
symbols. This is binding hoisting only; per-operation handles and security
buffers still have explicit ownership and cleanup.

#### Source handle and size policy

`NativeFileSystem.open_source()` opens the source with the Windows cached
sequential-access hint and returns the same unbuffered `BinaryIO` surface.
This is a cache-manager hint, not direct IO and not a second queue. Preserve
the current source sharing and long-path behavior and prove descriptor closure
on every construction failure. Copied backups use the same sequential source
opener rather than retaining a second path-opening implementation; that
opener reuse does not route their bytes through `CopyBackend`.

`_prepare_copy()` uses the reviewed size for two independent decisions before
creating the temp:

- select the actual positive pipeline `chunk_size` from the fixed three-band
  table, capped by `ExecutorPolicies.max_chunk_size`; and
- decide whether to pass an allocation request.

Zero-byte and small files still enter the pipeline; they merely skip
preallocation where the allocation policy says it cannot repay setup. Do not
expose the chunk bands or allocation crossover as user settings. Before
landing, run the size-distribution benchmark from 2.7, validate the fixed chunk
bands, and record its results and the measured allocation crossover.

#### Target-temp preallocation

Extend the existing filesystem seam to
`create_temp(path, *, allocation_size: int | None)`. `_prepare_copy()` passes
the reviewed source size only when the selected size policy enables
preallocation; otherwise it passes `None`. The reviewed size is already
guarded before streaming and checked again through byte-count and source-drift
guards after streaming.

`NativeFileSystem.create_temp()` still creates the owned temp exclusively,
then conditionally requests the reviewed allocation with Windows
`SetFileInformationByHandle(FileAllocationInfo)`. Allocation size and logical
EOF remain distinct: the request reserves target space while ordinary writes
advance EOF. Skip the request for `None` and zero.

Preallocation is an optimization and early resource check, not evidence that
the copy succeeded:

- Allow-listed unsupported allocation results fall back to ordinary
  streaming; unknown errors do not.
- Disk-full, quota, permission, and other substantive allocation failures
  fail the operation before bytes are copied.
- Short-write checks, digest byte count, flushes, post-copy source guards, and
  owned-temp cleanup remain mandatory.

#### Copied-backup byte loop

`NativeFileSystem.copy_backup()` remains a dedicated serial, hashless copy. It
does not call `NativeCopyBackend`, start pipeline workers, request an adaptive
chunk, or preallocate its trash temp in Track 1. Refactor its inline writes to
reuse the ordinary full-write forward-progress helper, and use the shared
sequential source opener. Its fixed read chunk remains 4 MiB unless a separate
same-volume backup benchmark justifies another policy.

After that byte loop, copied backups do share the common writer-close and
native finalization sequence below. "Shared finalization" does not imply
shared streaming policy or add ACL preservation that `copy_backup()` does not
currently perform.

#### Temp finalization and conditional published repair

`_prepare_copy()` does not flush the content writer. Close it after streaming,
then call one native filesystem operation that:

1. opens the temp once with the access needed to query/set basic information
   and flush it;
2. applies any preserved ACL while that handle is already held;
3. reads current `FILE_BASIC_INFO` so unmanaged attributes survive;
4. writes the intended mtime, matching last-access time, optional creation
   time, and managed hidden/system state while withholding readonly;
5. reads back the filesystem-normalized basic fields used as the
   post-publication comparison baseline;
6. calls `FlushFileBuffers` on that same handle exactly once; and
7. closes the handle before source/target guards and publication.

Replace the current `os.utime`, creation-time-only handle,
get/set-attribute pair, and `flush_path()` reopen on this path. The same native
helper may apply only selected fields during a repair; it must not erase
attributes outside NamiSync's managed mask. `_PreparedCopy` retains the
filesystem-normalized basic metadata returned by finalization so update
continuations and retry recovery compare publication against the same
baseline.

After `publish_new()` or `replace()`, observe the published target before
constructing the attestation. Compare its preserved basic metadata with the
filesystem-normalized temp baseline plus the intended deferred readonly state.
If everything matches, use that observation directly for the published-size
guard and attestation. If readonly or any other promised field differs, repair
the differing fields through one handle, flush the file, close it, and obtain
the final stat used for attestation. Parent-directory flushes remain after this
step.

Apply the same post-loop finalization sequence to copied backups. For hardlink
backups, restore and flush the displaced inode through its trash path if
clearing the live target's readonly bit changed that inode.

#### Published-size guard

Put the executor-specific guard in `_attestation()`, the single constructor
chokepoint used by COPY, UPDATE, and MOVE_UPDATE. Before constructing evidence,
perform an explicit, non-`assert` check that
`subject.size == digest.size`. The copy loop and source-drift guards already
compare the observed byte count against the reviewed source size; this adds the
missing equality between the bytes hashed and the published target. Keeping it
in `_attestation()` prevents three operation-site copies and makes a future
allocation or truncation defect fail before any recorder call.

Also enforce `content.size == subject.size` in
`Attestation.__post_init__`. That is deliberately a global core invariant, not
only a copy-path backstop: it applies to verifier-created attestations,
repository/readback reconstruction, and every future provenance. The
executor's `_attestation()` check remains useful for its local failure
boundary and message; the dataclass invariant prevents any other construction
path from representing content evidence as bound to a differently sized
subject.

#### Callback semantics

`checkpoint()` and `on_chunk()` stay on the original caller/coordinator
thread. Pipeline workers never call either callback.

- Call `checkpoint()` before admitting each new read, matching the current
  chunk-boundary cancellation point.
- Drain ready writer completions before each read, while waiting to enqueue,
  and after normal EOF.
- When the byte budget or a bounded data queue is full, wait with a timeout.
  On each timeout, inspect the first-error slot and call `checkpoint()` before
  waiting again.
- Call `on_chunk(size)` for each drained writer completion. Because the
  hasher is upstream, that chunk has already been included in the digest.
- The single writer's FIFO completions are already in read order; no
  coordinator-side reordering state is needed.

Calling `on_chunk()` immediately after the read would be incorrect: progress
would lead completed work and would overcount when the writer fails.
Progress means written-to-temp and hashed, not durably published.

The production dispatcher checkpoint is an idempotent raise-or-return guard:
it reads pause/cancel flags under a lock and carries no per-call accounting.
Polling therefore changes call frequency but not semantics. Exact checkpoint
call count is not a `CopyBackend` contract; cancellation tests synchronize on
pipeline stage state rather than raising on an ordinal callback invocation.

#### Cancellation and failure

The implementation needs a shared abort flag and a first-error slot.

- A cancellation or pause exception stops new reads, signals abort, shuts down
  both queues, joins both workers in `finally`, then re-raises the original
  control exception.
- Use Python 3.13 `Queue.shutdown(immediate=True)` on both bounded data queues
  during abort. It releases blocked producers and consumers and drops queued
  chunk references; the pipeline does not use `Queue.join()`.
- A worker may finish its current chunk after abort, but the hasher must not
  forward another chunk and the writer must not publish another completion
  after observing abort.
- The coordinator releases normal payload charges while draining writer
  completions. On abort it joins workers first, then clears all remaining
  charges once, including chunks discarded by immediate queue shutdown. No
  worker releases budget, and no waiter may remain blocked after worker join.
- Once abort is observed, the coordinator stops draining completion records,
  stops calling `on_chunk()`, and ignores any completion racing with abort.
  Teardown must preserve the initiating control/error exception rather than
  mask it with queue-shutdown or cleanup failure.
- Writer errors stop further writes. Hasher errors prevent any digest from
  being returned. The first failing worker stores its error and shuts down
  both data queues so the caller and peer cannot remain blocked. Reader and
  callback errors follow the same abort-and-join path.
- Retain the existing short-write loop and the
  `written is None or written <= 0` forward-progress guard.
- The caller never observes a return or exception while a worker is still
  running.

Because the executor publishes only after `copy()` returns, cancellation or
worker failure leaves at most an owned temporary file, which the existing
executor cleanup path removes.

Explicit `Thread`, bounded `Queue`, and one nonblocking completion queue are
favored over a general thread pool: handoff, progress, and shutdown remain
visible and deterministic without inventing buffer ownership state.

### 4.2 Track 2 - Wholesale XXH3-128 Content Hashing

This track deliberately has no registry, algorithm setting, location
preference, or per-run algorithm field.

| Change | Required result |
|---|---|
| `pyproject.toml` | **Stage 1 complete:** declares compatible `xxhash>=3.8.1,<4`; Track 2 consumes it |
| `core/evidence.py` | **Stage 1 protocol complete:** the standard-library-only streaming hasher/factory seam is defined. Track 2 makes `ContentEvidence.algorithm` accept only `xxh3_128`, requires exactly 16 digest bytes, and globally requires attestation content/subject sizes to match |
| `core/execution.py` | `CopyDigest` validates a 16-byte XXH3-128 digest |
| `modules/executor.py` | `NativeCopyBackend` requires a no-argument `hasher_factory`; copy attestation records `xxh3_128`; `ExecutorPolicies.copy_backend` becomes required instead of default-constructing `NativeCopyBackend` |
| `core/integrity.py` | `VerifierContext` requires the same no-argument `hasher_factory` seam |
| `modules/verifier.py` | Baseline, verify, and rebaseline obtain a hasher from the context, require a 16-byte result before any comparison, and record `xxh3_128` |
| `workflows/runtime.py` — Stage 2 half | Composition imports the concrete XXH3 constructor and explicitly supplies `NativeCopyBackend(hasher_factory=...)` when constructing `ExecutorPolicies`. **Lands with Track 2.** |
| `workflows/runtime.py` — Stage 3 half | The later M1 inventory/integrity stage supplies the same constructor when it first creates production `VerifierContext` values. **Does not land in Stage 2:** Track 2 adds the `VerifierContext` factory *field*, but its first production construction site is Stage 3 (see the prose below). |
| `db/repositories.py` | Reconstruct content evidence using the stored identifier rather than replacing it with `sha256` |
| Tests and fixtures | Replace SHA-256 content expectations with canonical XXH3-128 bytes |

Repository reconstruction deliberately reads the stored algorithm identifier
even though `xxh3_128` is the only valid value today. Hardcoding `xxh3_128`
would be equivalent only for valid rows; it would silently reinterpret a
corrupt or unsupported stored identifier instead of letting the fixed
`ContentEvidence` contract reject it. This preserves self-description and
validation, not dormant multi-algorithm support.

The third-party `xxhash` package must not be imported by `core`, which is
standard-library-only. Executor and verifier also do not construct the
third-party implementation themselves: they consume the required factory
seam, while workflow composition supplies the single concrete XXH3-128
constructor. Core owns the fixed evidence contract plus the structural
streaming protocol; it does not own a concrete factory or an algorithm map.

`ExecutorPolicies` currently declares
`copy_backend: CopyBackend = field(default_factory=NativeCopyBackend)`. Once
`NativeCopyBackend` requires its collaborator, that default is invalid. Drop
the default and make workflow composition pass the fully constructed backend
explicitly. Do not preserve the default by making the module import or create
the concrete XXH3 implementation.

Track 2 owns the verifier replacement as well as the copy replacement:
`VerifierContext` gains the required factory field, and baseline, verify, and
rebaseline switch to XXH3-128 with focused module tests here. It does **not**
prematurely construct a production integrity session. `VerifierContext` has no
production construction site until M1's later inventory/integrity stage; that
stage wires the already-fixed seam without reopening the algorithm decision.
Splitting the two consumers across plans would permit copy evidence and
verification evidence to drift during the same destructive schema boundary.

The existing non-content SHA-256 uses in `core/planning.py`,
`dispatcher/custody.py`, `db/history.py`, and `db/recorder.py` are explicitly
unchanged.

### 4.3 Test Impact

Required pipeline coverage:

- The pipelined copy produces the same digest bytes and byte count as a
  test-local serial reference under whichever canonical content hasher is
  active in that revision, across empty, partial-chunk, exact-chunk, and
  multi-chunk files.
- Empty, smaller-than-one-chunk, exact-chunk, and multi-chunk production calls
  all instantiate and cleanly stop the same pipeline workers; there is no
  size-selected serial branch.
- The adaptive chunk helper selects 256 KiB below 8 MiB, 1 MiB from 8 MiB
  through less than 32 MiB, and 4 MiB from 32 MiB upward; zero and both sides
  of each exact boundary are covered. It caps the result by
  `ExecutorPolicies.max_chunk_size` and passes that positive actual value
  through the unchanged `CopyBackend.copy(..., chunk_size=...)` contract.
- The pipeline reads to actual EOF rather than stopping at reviewed size, and
  the initially selected chunk remains fixed while the executor preserves
  `SOURCE_DRIFT` classification for observed shrink or growth.
- A source implementing `read()` but not `readinto()` is sufficient.
- Each immutable chunk reaches the writer only after the hasher consumes it;
  no chunk is mutated or copied during handoff.
- `on_chunk()` occurs only after the line's hash and full-write stages and is
  emitted in read order.
- Filling the combined byte budget or either item-bounded data queue applies
  backpressure without deadlock. A chunk moving between queues is charged
  once, the resident-payload high-water never exceeds the configured budget,
  and every completion or abort releases its charge exactly once.
- With the default policy ceiling, each FIFO's 32-entry cap accommodates every
  conforming smaller-band file and the 4 MiB band's eight-chunk byte window. A
  source that grows across its reviewed band or a deliberately smaller policy
  ceiling may receive a shallower window without deadlock. Exercise EOF
  handoff after a smaller-band producer has filled all 32 entries.
- Short writes make forward progress; zero/`None` writes fail.
- Reader, writer, hasher, and callback failures terminate and join both
  workers without deadlock.
- Cancel and pause at each pipeline stage terminate cleanly, publish no target
  file, stop completion draining, preserve the initiating exception, and
  allow owned-temp cleanup.
- Immediate queue shutdown releases callers or workers blocked on either
  handoff and does not replace the initiating failure with `ShutDown`.
- Cancellation tests use explicit pipeline-stage synchronization rather than
  depending on an exact checkpoint call count.
- Temp creation requests the exact reviewed source allocation only above the
  measured preallocation crossover. Zero-length, small-file, and unsupported
  allocation paths continue correctly only for the allow-listed unsupported
  results, while unknown or substantive allocation failures abort before
  streaming.
- Source shrink/growth after preallocation is still rejected by byte-count
  and post-copy drift guards, and the owned temp is removed.
- `_attestation()` rejects a published size that differs from the hashed byte
  count for COPY, UPDATE, and MOVE_UPDATE before any recorder call.
- `Attestation.__post_init__` rejects mismatched content/subject sizes for
  copy, verifier, repository/readback, and other construction paths as a
  global core invariant.
- Cached source opening carries the sequential hint, retains required sharing
  and long-path behavior, and closes the descriptor on success and failure.
- Win32 DLL loading and function-signature binding occur once rather than once
  per file.
- Normal copy paths perform no writer flush, apply any preserved ACL and
  pre-publish metadata after writer close, and issue exactly one temp-file
  flush before publication.
- Copied-backup paths likewise perform no writer flush and issue one
  post-metadata temp-file flush, without adding a new ACL-copy contract.
- Copied backups use their dedicated serial hashless loop and shared
  sequential opener/full-write/finalization helpers, but do not invoke
  `CopyBackend`, start pipeline workers, or request preallocation.
- Temp finalization acquires its handle before applying a preserved ACL, so a
  restrictive copied descriptor cannot strand metadata or flush work that
  still requires that handle.
- A publish that preserves intended metadata performs no post-publish metadata
  write or target-file flush and reuses its stat for attestation. Comparison
  uses the filesystem-normalized finalized-temp baseline, so supported
  timestamp rounding alone does not trigger repair.
- Deferred readonly, tunneled creation time, or other preserved-field drift
  triggers selective repair, one target-file flush, and a final attestation
  stat. Unmanaged attributes survive both finalization and repair.
- Clearing readonly on an update whose backup is a hardlink restores and
  flushes the displaced inode through the trash path before recording.
- Parent-directory durability and the rule that recording follows successful
  filesystem durability remain unchanged.

Required content-hash coverage:

- Canonical XXH3-128 digest bytes are the unsigned 128-bit result encoded
  big-endian, exactly `intdigest().to_bytes(16, "big")`, matching
  python-xxhash `digest()`/`hexdigest()` rather than native-structure byte
  order.
- The seed-zero empty-input streaming vector is pinned:
  `xxh3_128(b"").digest().hex() ==
  "99aa06d3014798d86001c324468d497f"`, and the same bytes equal the
  big-endian encoding of `intdigest()`.
- Copy attestation round-trips through the recorder and repository as
  `xxh3_128` without byte-order changes.
- Baseline followed by verify succeeds; changed content reports
  `HASH_MISMATCH`.
- Invalid identifier, non-bytes digest, and wrong digest length are rejected.
- A factory returning a non-XXH-shaped digest fails as a collaborator contract
  error before verification comparison; it never becomes `HASH_MISMATCH`.
- Existing plan, selection, history, custody, and recorder identity hashes
  remain unchanged.
- The supported Windows/Python build can import the `xxhash` dependency and
  construct both streaming executor and verifier hashers.
- Refactor setup/tests delete and recreate both ledger and history databases;
  no old SHA-256 evidence or history detail survives the boundary.
- Ledger v1, history v1, and history v2 are refused rather than migrated; the
  retired v1→v2 history shortcut cannot stamp a partial schema with the new
  version.

### 4.4 Estimate

- Track 1: approximately 3 implementation days including adaptive-band
  validation and the preallocation sweep, native allocation and finalization,
  deterministic cancellation/failure handling, and focused tests. The single
  pipeline removes hybrid selection and the prior lease/dual-acknowledgement
  work, but combined-budget accounting, selective metadata repair, queue
  shutdown, and failure coverage remain substantive.
- Track 2: approximately 1 implementation day plus 1 day for fixtures,
  vectors, persistence round-trips, and regression tests.

These remain estimates from the measured prototype and a static read of the
call sites, not from an attempted production implementation.

### 4.5 Acceptance Criteria

4.3 lists the tests to write. This section is the standard those tests are held
to: each item is a pass/fail gate, and a green suite that does not satisfy the
gate is not done. The refactor rewrites the copy state machine, finalization,
and the content hash, so it must re-prove the executor contracts it inherits
(Part A), not only its own new behavior (Parts B and C).

**How to read these gates (anti-slack rules).** Every gate must be able to
fail. A test that would still pass if the behavior under test were deleted does
not satisfy its gate, and reviewers reject it. Concretely:

- **Inject the failure the gate names.** A happy-path copy that asserts
  `target == source` exercises almost none of this document. Where a gate names
  a fault (worker error, mid-stream read failure, cancel at stage N, a source
  that grows during streaming), the test injects exactly that fault.
- **Assert the typed reason, not "it failed."** Pin the exact
  `ExecutionReason` / integrity outcome / exception type. "Raised" or "failed"
  passes for the wrong reason.
- **Prove completeness by content, never by size or existence.** Preallocation
  makes a zero-filled temp of the correct logical size look complete; atomicity
  and drift gates assert full-content digest of the published file, not
  `size`/`exists`.
- **Spy filesystems prove call shape and ordering; they do not prove
  durability or atomicity.** Any gate that says *durable*, *atomic publish*, or
  *conditional refusal* requires at least one real-filesystem test — a no-op
  flush or an unconditional `os.replace` in a stub backend satisfies a spy but
  not the OS.
- **Invariants are raised exceptions, not `assert`.** `assert` vanishes under
  `python -O` (a documented PoC-class bug); every invariant gate constructs the
  violating value and asserts a real exception under `-O`.
- **Cover every path a "global" claim names.** An invariant said to hold for
  executor, verifier, and repository/readback construction is exercised on all
  three, not only the copy path.

#### A. Preserved executor and verifier contracts (re-proven against the refactored path)

These already pass for M0 (`EXECUTOR.md`, `VERIFIER.md` acceptance). The gate is
that they still pass *through the new pipeline, single-handle finalization, and
XXH3 hasher* — the refactor is the reason each is now at risk.

- **A1 — Crash-atomic publish, no partial file.** Fault injected at each
  pipeline stage (reader/hasher/writer) and specifically after preallocation
  but before EOF leaves at most an owned temp and never a published target; the
  published path is byte-for-byte a complete prior or complete new version by
  full-content digest. Include a file whose reviewed size equals its allocation
  request. *Not satisfied by* size/existence checks or happy-path-only copies.
- **A2 — Owned-temp grammar and exclusive create.** The temp created during a
  real copy matches `^<name>\.synctmp-<run-id>-<op-id>$` with *this* run/op ids
  and was made with an exclusive/`CREATE_NEW` primitive (a second create at the
  same name fails); a preallocated temp still matches the exact shape. *Not
  satisfied by* a `*.synctmp*` glob or a hardcoded basename.
- **A3 — Temp cleanup on every non-publishing exit.** For each of source drift,
  reader/hasher/writer/callback error, cancel, pause, and substantive
  preallocation failure — all of which fail *before* publish — zero files
  matching the current run's temp grammar remain, cleaned by the current-run
  per-operation path, not by a later run's recovery sweep. (Published-size
  mismatch fails *after* publish; its post-condition is B18, not temp cleanup.)
- **A4 — Source-missing maps to `SOURCE_MISSING`.** A source absent at touch
  yields exactly `SOURCE_MISSING` (not a generic `OSError`/sharing error from
  the new `O_SEQUENTIAL` opener), no temp, no attestation. *Not satisfied by*
  asserting only that it "failed."
- **A5 — Source-drift by byte count, reading to real EOF.** A source that grows
  past reviewed size, and separately one that shrinks, each yield `SOURCE_DRIFT`
  with no publish and the temp removed — and the observed byte count/digest
  reflects the post-mutation bytes, proving the backend read to actual EOF
  rather than stopping at the reviewed/preallocated size. *Not satisfied by*
  mutating only mtime, or by a reader capped at reviewed size (which makes the
  byte-count guard structurally unable to fire).
- **A6 — Conditional publish refuses an appeared/vanished target.** On a real
  filesystem, a destination created after preflight for an expected-absence
  COPY makes the real conditional primitive fail atomically
  (`DESTINATION_OCCUPIED`/`TARGET_DRIFT`) with the prior file byte-unchanged; a
  vanished required target yields `TARGET_MISSING`. *Not satisfied by* a stub
  backend whose publish is an unconditional overwrite.
- **A7 — Recording follows durability.** The parent-directory flush occurs
  before any `record_*` call and no recorder call precedes it; a fault after
  digest finalization but before/during publish + parent-flush records nothing.
  (The single pre-publish flush count and its post-`FILE_BASIC_INFO` sequencing
  are *new* DR-HASH-08 behavior — gate B14 — not an M0 contract; M0 flushes the
  temp twice and uses `os.utime`.) *Not satisfied by* building the attestation
  from `CopyDigest` the moment `copy()` returns and testing only the happy path.
- **A8 — Metadata mask and last-access preserved.** With an unmanaged attribute
  (e.g. `NOT_CONTENT_INDEXED`) plus managed hidden+system on the source, the
  published target retains the unmanaged attribute and the managed ones, mtime
  equals normalized source mtime, last-access equals mtime, and creation time is
  preserved; a `created_ns` of `None` never overwrites the real creation time.
  Re-assert through a triggered repair. *Not satisfied by* checking only mtime,
  or fixtures that never set an unmanaged attribute or a `None` creation time.
- **A9 — Readonly withheld then applied.** Copying a readonly source publishes
  from a non-readonly temp (`publish_new`/rename succeeds for COPY) and the
  published target is readonly afterward *via the post-publish repair branch*
  (assert the repair ran). *Not satisfied by* a non-readonly source, which makes both halves
  trivial.
- **A10 — Copy-backup stays serial and hashless.** On a no-hardlink target, the
  update backup transfers via the dedicated serial loop with a fixed 4 MiB
  chunk, starts no pipeline/hasher workers, does not preallocate its trash temp,
  and copies no ACL — yet still performs writer-close + one post-metadata flush
  + atomic publish inside the run trash directory. Spy the injected
  `copy_backend` and worker factory and assert zero calls during backup. *Not
  satisfied by* asserting only backup content equality.
- **A11 — Hardlink-backup displaced-inode restore.** Updating a readonly file
  on a hardlink-capable target restores readonly on the trash-hardlinked inode
  and flushes it through the trash path before recording, while the new live
  target carries its own readonly. *Not satisfied by* a non-readonly source or
  inspecting only the live target.
- **A12 — Retry/continuation idempotency.** A sharing violation mid-copy is
  retried within bound: the retry removes the prior owned temp and re-creates it
  without a `CREATE_NEW` collision and converges to one published target; an
  update after backup resumes at replace, recognizing the existing
  backup/published state rather than re-creating and colliding. *Not satisfied
  by* a mock that reuses the same temp handle so the cleanup-before-recreate
  path never runs.
- **A13 — Four independent truth axes.** A recorder failure post-publish keeps
  filesystem `COMPLETED` with `recording=DEGRADED` (reconcilable), never
  relabelling the copy as byte-failed; a hasher-worker failure fails the copy
  with no attestation; audit degradation is reported independently. *Not
  satisfied by* all-green runs where the axis fields are populated but never
  asserted under partial failure.
- **A14 — Cache-honest verification survives the shared helpers.** The verifier
  still opens via the unbuffered cache-honest reader (reports
  `windows-unbuffered`, denies writer/delete sharing, pre/post stats from one
  handle) with its own 4 MiB chunk, and a reparse/alignment/containment reject
  yields `unsupported`, never `verified`. *Not satisfied by* verifying a
  just-written cached file, which matches from cache.
- **A15 — Composite move-update never-neither.** Faults at each move-update
  stage leave old and/or new present (never neither), exactly one ledger
  transition, and the `_attestation()` published-size guard runs for
  MOVE_UPDATE before any recorder call. *Not satisfied by* testing the guard and
  crash-atomicity only for COPY and assuming MOVE_UPDATE is transitively
  covered (its attestation is *cached* in the continuation — a distinct path).
- **A16 — Recovery scope isolation with preallocated temps.** Seed a prior-run
  exact temp (including a preallocated/sparse one), a current-run temp, a
  substring lookalike, an exact-name directory, an off-volume mount, and a
  `.synctrash` entry; recovery removes only the prior-run exact regular files
  (plain and preallocated) in scope and a sweep failure halts before copy
  allocation. *Not satisfied by* seeding only a plain zero-byte prior-run temp.

#### B. New Track 1 behavior — pipeline, finalization, preallocation

The 4.3 pipeline tests are necessary but not sufficient; these close the
loopholes a byte-equal-but-wrong implementation would slip through. The first
two are the ones a passing correctness suite most easily hides.

- **B1 — The stages actually overlap.** With the writer blocked on chunk 1
  until signaled, the reader/hasher advance to at least chunk 2 (ideally to the
  budget depth) *before* chunk 1's completion drains. A serial
  read-all-then-hash-then-write, or a pool that starts threads but serializes
  handoffs, must fail this. *Not satisfied by* digest-equality tests or a
  thread-count spy — overlap, not thread existence, is the contract.
- **B2 — Lookahead is bounded.** With the writer blocked indefinitely and a
  source far larger than the budget, resident/queued chunks and reserved bytes
  plateau at the budget (≤ ~32 MiB, ≤ 32 items/FIFO) and the reader blocks on
  reservation — it does not buffer the whole source. *Not satisfied by* a
  source smaller than the budget, or asserting a `Queue(maxsize=N)` exists by
  construction.
- **B3 — Shallow-window and grown-source paths are deadlock-free.** With
  `max_chunk_size=256 KiB` against a source that grows past its reviewed band,
  and separately a run that hits the item cap before the byte budget, both
  complete (or classify `SOURCE_DRIFT`) within a watchdog deadline with both
  workers joined. *Not satisfied by* testing only the default 4 MiB ceiling with
  conforming sources.
- **B4 — Worker failure while the coordinator is blocked.** Fill the write
  queue (block the writer), then make the writer raise; the coordinator, blocked
  mid-enqueue, wakes within a deadline via the timeout + first-error slot, joins
  both workers, and re-raises the writer's original error (not `ShutDown`).
  Repeat with the hasher. *Not satisfied by* injecting the error while the
  coordinator is idle/draining.
- **B5 — Mid-stream source read error.** A `source.read()` that succeeds for K
  chunks then raises `OSError` makes `copy()` re-raise that exact `OSError` (not
  `ShutDown`), both workers non-alive before the raise is observed, no publish,
  temp left for cleanup. *Not satisfied by* testing only source-missing-at-open,
  which routes through a different guard.
- **B6 — Callback error teardown.** An `on_chunk()` that raises mid-drain (and a
  `checkpoint()` raising a non-control error) follows the abort-and-join path:
  `copy()` re-raises that exact exception, both workers joined, nothing
  published. *Not satisfied by* only ever using a no-op `on_chunk`.
- **B7 — Final-chunk write failure after digest completion.** A writer that
  fails on the *last* chunk (after the hasher already finalized the digest over
  all source bytes) makes `copy()` raise — not return a complete-looking
  `CopyDigest` for a short temp; a merely-slow final write blocks the return.
  This proves the return is gated on the final writer completion, not on hasher
  EOF. *Not satisfied by* failing only non-final chunks.
- **B8 — Byte budget: no leak on the clean path.** After a clean multi-chunk
  copy including one whose size is not a chunk multiple (short-final-chunk
  charge-down), reserved bytes return exactly to zero and peak never exceeded
  the budget; N back-to-back copies start from an identical free budget. *Not
  satisfied by* checking the budget only after an abort.
- **B9 — First-error single winner.** Simultaneous hasher and writer failures
  with distinguishable types make `copy()` re-raise exactly one (the
  first-stored), never a `ShutDown`; a Cancel racing a worker error preserves
  the Cancel. *Not satisfied by* only ever injecting a single failing stage.
- **B10 — Bounded cancellation latency.** With the cancel flag set after chunk K
  on a large source, at most one further read is admitted
  (`reads_admitted ≤ K+1`) before `Canceled`/`PauseRequested` propagates,
  synchronizing on stage state. *Not satisfied by* cancelling before the copy or
  between operations, or asserting an ordinal checkpoint count (explicitly not a
  contract).
- **B11 — `on_chunk` suppressed after abort.** After abort is observed no
  `on_chunk` fires and cumulative reported bytes do not increase; queued
  completions are dropped, not drained-and-reported. *Not satisfied by*
  asserting totals only on successful copies.
- **B12 — Progress is written-and-hashed, in read order, on the caller
  thread.** With a writer failing on chunk 3 of 5, cumulative `bytes_done`
  never exceeds bytes actually written before failure, the emitted `on_chunk`
  sizes arrive in strict read order and sum to exactly the bytes written before
  failure (no `CopyDigest` is returned in this run), no `on_chunk` fires for the
  failed chunk, and every callback ran on the thread that called `copy()`
  (assert thread identity); on a separate clean multi-chunk run the emitted
  sizes sum exactly to `digest.size` in read order. *Not satisfied by* asserting
  only the end-of-copy total on a fully successful run.
- **B13 — Adaptive chunk is actually wired, not the ceiling.** Unit-test the
  band helper (0 and just-below-8 MiB → 256 KiB; 8 MiB and just-below-32 MiB →
  1 MiB; 32 MiB and up → 4 MiB; each capped by `max_chunk_size`) *and* spy the
  `chunk_size` argument `_prepare_copy` actually passes into
  `CopyBackend.copy()` for a spread of sizes; `ExecutorPolicies(max_chunk_size=0)`
  raises. *Not satisfied by* testing the helper in isolation while the call site
  still passes the ceiling — a digest test cannot tell one 4 MiB chunk from
  sixteen 256 KiB chunks.
- **B14 — Single finalization handle, one real flush.** Zero flushes on the
  content-writer handle; exactly one `FlushFileBuffers` on the finalization
  handle, sequenced after `FILE_BASIC_INFO`; the handle is acquired *before* the
  ACL is applied (prove with a restrictive-ACL source whose descriptor would
  deny a later reopen — finalization still completes basic-info + flush through
  the held handle). A zero-flush build fails. *Not satisfied by* asserting
  `flush_count == 1` without checking which handle or when.
- **B15 — Real-filesystem durability barrier.** At least one real-FS test:
  after publish+record, a crash/kill simulation shows the published content and
  the intended mtime/creation/attributes durable on re-read. A no-op or
  wrong-handle flush must fail this. *Not satisfied by* spy-filesystem ordering
  assertions alone.
- **B16 — Conditional post-publish repair is stat-driven.** (a) A publish that
  preserved everything performs zero post-publish metadata *writes* and zero
  target flush, takes exactly one post-publish comparison stat of the target,
  and reuses *that post-publish target stat* for the published-size guard and
  attestation (DR-HASH-08); (b) simulated
  name-tunneling restoring creation time plus a deferred readonly triggers
  selective repair of *only* those fields, exactly one target flush, and a final
  re-stat; (c) supported target-filesystem timestamp rounding alone triggers no
  repair (comparison uses the normalized temp baseline, not raw source
  nanoseconds). *Not satisfied by* always full-replaying metadata (masks the
  no-op fast path) or gating repair only on "readonly requested."
- **B17 — Attestation subject is the post-repair re-stat.** When repair fires,
  `attestation.subject` and the published-size guard use the final re-stat
  (repaired mtime/creation/readonly), not the normalized temp baseline; on the
  no-repair path the post-publish comparison stat is reused — never a
  pre-publish temp stat, whose size trivially equals `digest.size` and would
  neuter the published-size guard. *Not satisfied by* testing attestation-
  subject only on the clean path where the observations are identical.
- **B18 — Published-size guard on all three kinds.** A published target whose
  logical size differs from the hashed byte count makes `_attestation()` fail
  before any recorder call for COPY, UPDATE, *and* MOVE_UPDATE, with a specific
  size-mismatch failure (not a bare `AssertionError`). Because the guard sits in
  `_attestation()` (post-publish), the failure leaves the wrong-sized target
  *published* with no attestation recorded: assert the operation settles FAILED,
  zero `record_*` calls, and the wrong target left in place — this is not a
  temp-cleanup case. *Not satisfied by* adding the check only in `_copy` and
  testing only COPY.
- **B19 — One file streams at a time.** Driving an `ExecutionSet` of several
  COPY ops, at most one `CopyBackend.copy` pipeline is active at any instant (a
  concurrency probe records max simultaneous == 1); a pool-based
  reimplementation with max == 2 fails. This defends the per-copy budget
  rationale. *Not satisfied by* single-copy tests, which never observe
  cross-file concurrency.
- **B20 — Preallocation error classes.** Temp creation requests the exact
  reviewed allocation only above the measured crossover; an allow-listed
  "unsupported" result falls back to ordinary streaming while disk-full, quota,
  permission, and unknown errors fail the operation before any bytes are
  copied; zero-byte and sub-crossover copies request no allocation. *Not
  satisfied by* testing only the supported-and-succeeds path.

#### C. New Track 2 behavior — XXH3-128 evidence and layering

- **C1 — Canonical encoding and vectors.** `xxh3_128(b"").digest().hex() ==
  "99aa06d3014798d86001c324468d497f"` and equals `intdigest().to_bytes(16,
  "big")`; a one-byte flip changes the digest and yields `mismatched`. *Not
  satisfied by* pinning one non-empty fixture computed with the same
  (possibly wrong) endianness on both write and read.
- **C2 — Length gates in all three places.** `CopyDigest` and `ContentEvidence`
  accept 16 bytes and reject 32; `algorithm` accepts only `xxh3_128`. *Not
  satisfied by* changing the literal to 16 while a 32-byte fixture lingers in a
  helper.
- **C3 — Bad factory is a collaborator error, never `HASH_MISMATCH`.** A
  factory returning a wrong-length (e.g. 20-byte) digest makes the verifier
  raise a contract error *before* any baseline comparison, distinct from
  `HASH_MISMATCH`; `HASH_MISMATCH` is reserved for two valid 16-byte digests
  that differ. The guard is length-only (DR-HASH-02), so a non-canonical
  *byte order* — still 16 bytes — is C1's concern, not this gate. *Not
  satisfied by* injecting a wrong-but-16-byte value, which passes the length
  gate and only surfaces at comparison.
- **C4 — Copy and verify share one factory (round-trip).** End-to-end: copy a
  file (records `xxh3_128`), then verify the same file → `verified`/`baselined`,
  never `mismatched`; the stored digest is byte-identical between copy and
  verify; `last_verified_at` stays unset until the verifier read. *Not satisfied
  by* unit-testing the two hashers separately against their own fixtures — the
  one seam that catches a one-sided wiring or byte-order split is the round-trip.
- **C5 — Same hasher, different opener at the composition seam.** One
  composition-level test asserts `NativeCopyBackend` and `VerifierContext` obtain
  digests from the *identical* factory object (byte-identical digests) *and*
  that the verifier's handle reports `windows-unbuffered` while the executor's
  reports the `O_SEQUENTIAL` cached hint — provably different opener objects.
  *Not satisfied by* testing the shared hasher and the unbuffered reader in two
  separate tests; a build that accidentally shares the opener passes each alone.
- **C6 — Attestation size invariant is global and real.** `Attestation` with
  `content.size != subject.size` raises (a real exception under `python -O`)
  when constructed directly, via executor `_attestation`, *and* via repository
  readback reconstruction; a size-mismatched stored row cannot round-trip into a
  valid object. *Not satisfied by* an `assert`, or by testing only the executor
  path.
- **C7 — Self-describing reconstruction.** A ledger row with a corrupt or
  unsupported stored algorithm identifier makes repository reconstruction raise
  via the `ContentEvidence` contract (not relabel to `xxh3_128`); a valid row
  round-trips carrying its own stored identifier. *Not satisfied by* hardcoding
  `xxh3_128` and testing only valid rows.
- **C8 — Import law and required backend.** An import contract test proves
  `core/*.py` has zero third-party imports — no `xxhash`, including inside
  function bodies; `ExecutorPolicies` cannot be constructed without an explicit
  `hasher_factory`-backed `copy_backend`; only `workflows/runtime.py` imports the
  concrete XXH3 constructor. *Not satisfied by* a top-of-file grep (a hidden
  in-function import passes it) or a lazily-raising default factory.
- **C9 — Identity hashes remain SHA-256.** Pin known-input→known-output SHA-256
  vectors for a plan fingerprint, commitment/selection digest, custody key,
  history-chain link, and recorder identity; assert the `hasher_factory` seam is
  not referenced in `core/planning.py`, `dispatcher/custody.py`, `db/history.py`,
  or `db/recorder.py`. *Not satisfied by* asserting "a fingerprint exists" — a
  blanket `sha256→xxhash` replace passes that while silently changing every
  internal identifier.
- **C10 — Schema reset refuses old versions.** Opening a ledger v1, history v1,
  and history v2 database is each refused with the actionable reset message —
  not migrated, not stamped v3 — and the retired history v1→v2 shortcut is
  removed/disabled so it cannot write the new constant onto a partially-migrated
  schema. *Not satisfied by* testing only that a fresh database works.
- **C11 — `modified` vs `mismatched` boundary intact.** Changed size/mtime →
  `modified`; identical stats + differing XXH3 digest → `mismatched` (the bitrot
  signal); a null-hash row during verify → `baselined` with `last_verified`
  unset; provenance is stored exactly per path (`copy`/`verify`/`readback`).
  *Not satisfied by* accepting either `modified` or `mismatched` for a change
  that also moved the stats.

---

## 5. Deferred

- **Concurrent file execution.** Reconsider only if post-XXH3 measurements
  show that a real workload leaves relevant devices underutilized.
- **Lazy worker spin-up for zero/one-chunk files.** Track 1 initially starts
  the pipeline for every normal copy. If a production-shaped directory
  workload later shows a material end-to-end cost from worker and queue
  startup, prefer one engine with a lazy preamble over a size-selected hybrid.
  The caller reads chunk 1 and then attempts chunk 2 before creating queues or
  workers. Empty input returns the empty digest inline. If chunk 2 is EOF, the
  caller hashes chunk 1, fully writes it, emits `on_chunk`, and returns. If
  chunk 2 contains data, the caller starts the existing pipeline, admits both
  chunks in order, and continues normally. This retains one streaming
  implementation: the inline exit is the one-iteration body, not a second
  serial engine. It also needs no `expected_size` protocol input or
  size-selection threshold. Before activation, prove checkpoint behavior on
  both reads, short-read correctness, digest/progress equivalence, and
  cancellation/failure teardown across the lazy-start boundary.
- **Cross-file batching or large-first/small-last passes.** The plan already
  contains global operation knowledge, but reordering alone does not remove
  file opens, metadata work, flushes, recorder calls, or database commits. It
  would change dependency scheduling, progress/history order, pause/cancel,
  failure, stop, and end-of-run semantics. A future batching design must first
  define those contracts. If measurement later justifies multi-file
  preparation, keep reversible copy-to-temp work separate from a plan-order
  coordinator that guards, publishes, flushes, records, and settles each
  operation. Directory-flush coalescing and recorder transaction batching are
  separate durability decisions, not implied by file ordering. This deferral
  also covers a depth-one "publish pipeline" that overlaps file N
  finalization/flush/publish with file N+1 writes: it creates two live
  operations and may turn sequential IO into harmful contention on rotational
  media.
- **Parallel verification.** Same gate: demonstrate an IO-utilization problem
  after XXH3-128 before adding workers.
- **Direct/unbuffered executor IO, including overlapped readahead.** The
  current unbuffered measurements establish a ceiling, not a production win.
  A separate large-file backend would need native handles, logical and
  physical alignment discovery, aligned buffer ownership, sector-multiple
  writes, a zero-padded tail followed by exact logical EOF correction,
  logical-byte-only hash/progress accounting, capability selection, and
  restart-safe fallback. Fallback is simple only before the first successful
  direct write. Under the current monotonic progress contract, a later direct
  failure must fail the operation rather than silently restart and double
  count progress; supporting restart would first require explicit temp
  recreation, hash reset, and progress-correction semantics. Benchmark direct
  IO only after the buffered optimizations land and require a material
  repeatable gain on eligible file sizes before accepting that semantic and
  test cost.
- **Mutable `readinto()` buffers or a fork topology.** Reconsider only if a
  production-shaped benchmark shows a user-visible gain large enough to
  justify explicit buffer ownership and dual-consumer completion state.
- **Additional content algorithms.** Require a concrete product need and a
  new decision covering semantics, evidence compatibility, and tests. No
  registry or dormant extension mechanism is added in M1. The required,
  parameterless hasher factory is only the inversion seam for the one pinned
  implementation; turning it into an algorithm-keyed factory would violate
  DR-HASH-02.
