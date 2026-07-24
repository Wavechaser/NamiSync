# Hash Pipeline, XXH3, and Executor IO Refactor

Status: investigation and planning last revised 2026-07-24. Nothing below is
implemented. This document records two independent M1 performance tracks:
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
   report adaptive chunk candidates, preallocation crossover, total operations
   per second, and fixed finalization time separately.
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

Use a small fixed set of candidate chunk sizes selected by a
production-shaped size sweep rather than a continuous formula. The selected
chunk never exceeds `max_chunk_size`; zero-byte files receive the smallest
positive candidate and immediately encounter EOF. The candidate values and
size bands are private executor constants, not user settings. Record the
measured table and rationale before landing them.

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
`CopyBackend`, pipeline workers, adaptive engine selection, or preallocation
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
`ExecutorPolicies.max_chunk_size`.

Before creating the temp, `_prepare_copy()` calls one private pure helper with
the reviewed source size and policy maximum. The helper returns the actual
chunk size from the measured fixed candidate table. Pass that value to
`CopyBackend.copy()`. The backend does not receive the reviewed size and has
no serial/pipeline selection branch.

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
and more items when the adaptive policy selects a smaller chunk. The separate
item cap is a safety bound and must not accidentally turn the measured smaller
chunk policies into a much smaller byte window. The 2 GiB/s-class measurements
used the eight-by-4-MiB shape; a shallow two-slot equivalent need not reproduce
them. Budget beyond what covers writer jitter adds RAM without throughput,
since the slowest stage still sets the rate.

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

- select the actual positive pipeline `chunk_size` from the measured candidate
  table, capped by `ExecutorPolicies.max_chunk_size`; and
- decide whether to pass an allocation request.

Zero-byte and small files still enter the pipeline; they merely skip
preallocation where the allocation policy says it cannot repay setup. Do not
expose the chunk bands or allocation crossover as user settings. Before
landing, run the size-distribution benchmark from 2.7 and record the measured
constants and rationale.

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
| `pyproject.toml` | Add the pinned/compatible `xxhash` dependency |
| `core/evidence.py` | `ContentEvidence.algorithm` accepts only `xxh3_128`; digest length is exactly 16 bytes; `Attestation` globally requires content and subject sizes to match; define the standard-library-only streaming hasher/factory protocol used by both consumers |
| `core/execution.py` | `CopyDigest` validates a 16-byte XXH3-128 digest |
| `modules/executor.py` | `NativeCopyBackend` requires a no-argument `hasher_factory`; copy attestation records `xxh3_128`; `ExecutorPolicies.copy_backend` becomes required instead of default-constructing `NativeCopyBackend` |
| `core/integrity.py` | `VerifierContext` requires the same no-argument `hasher_factory` seam |
| `modules/verifier.py` | Baseline, verify, and rebaseline obtain a hasher from the context, require a 16-byte result before any comparison, and record `xxh3_128` |
| `workflows/runtime.py` | Composition imports the concrete XXH3 constructor and explicitly supplies `NativeCopyBackend(hasher_factory=...)` when constructing `ExecutorPolicies`; the later M1 integrity stage supplies the same constructor when it creates production `VerifierContext` values |
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
- The adaptive chunk helper returns a positive candidate no greater than
  `ExecutorPolicies.max_chunk_size`, selects the expected band at every
  boundary, and passes that actual value through the unchanged
  `CopyBackend.copy(..., chunk_size=...)` contract.
- The pipeline reads to actual EOF rather than stopping at reviewed size, and
  the executor preserves `SOURCE_DRIFT` classification for observed shrink or
  growth.
- A source implementing `read()` but not `readinto()` is sufficient.
- Each immutable chunk reaches the writer only after the hasher consumes it;
  no chunk is mutated or copied during handoff.
- `on_chunk()` occurs only after the line's hash and full-write stages and is
  emitted in read order.
- Filling the combined byte budget or either item-bounded data queue applies
  backpressure without deadlock. A chunk moving between queues is charged
  once, the resident-payload high-water never exceeds the configured budget,
  and every completion or abort releases its charge exactly once.
- The item cap accommodates the intended 32 MiB payload window at every
  adaptive chunk candidate while still bounding control-object count.
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

- Track 1: approximately 3 implementation days including the adaptive
  chunk/preallocation sweep, native allocation and finalization, deterministic
  cancellation/failure handling, and focused tests. The single pipeline
  removes hybrid selection and the prior lease/dual-acknowledgement work, but
  combined-budget accounting, selective metadata repair, queue shutdown, and
  failure coverage remain substantive.
- Track 2: approximately 1 implementation day plus 1 day for fixtures,
  vectors, persistence round-trips, and regression tests.

These remain estimates from the measured prototype and a static read of the
call sites, not from an attempted production implementation.

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
