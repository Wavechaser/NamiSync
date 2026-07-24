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

The first problem therefore calls for an adaptive backend: a bounded
three-stage pipeline for files large enough to amortize it and a direct serial
loop for smaller files. The second calls for a faster content hash. The
remaining fixed costs call for fewer native setup calls, one pre-publish file
durability barrier, and conditional post-publish metadata repair. These
changes complement one another but solve different problems: XXH3-128 removes
hashing as the reason to execute multiple files concurrently; it does not
remove the need to overlap large-file reads, writes, and hashing or to reduce
per-file executor overhead.

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
| pipelined read() + preallocation (large-file path) | ~2 700-3 100 | +120% to +150% |

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
files, while the pipeline begins helping only when a file spans enough chunks
to overlap stages. Track 1 therefore retains the current serial loop as a real
small-file engine and selects the engine once from the reviewed source size.
A directory-level size sweep chooses the crossover; it is not guessed from
the 4 KiB microbenchmark.

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
   report serial/pipeline crossover, preallocation crossover, total operations
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

**Resolution.** Implement the adaptive serial/pipelined copy backend and its
executor IO/finalization reductions as an independent track. The XXH3-128
replacement neither absorbs nor weakens that work.

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

**Resolution.** M1 uses one file operation at a time. Each copy may pipeline
that file's read, write, and hash stages. Verification remains single-stream.
Parallel file execution or verification requires a later benchmark showing a
real workload that remains underutilized after XXH3-128.

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

### DR-HASH-07 - Select a real serial engine for smaller files

**Tension.** Making the pipeline "act serial" would retain worker and queue
startup while adding a special execution mode inside the harder code path.
Always using the current serial loop would leave large-file overlap on the
table. Fixed chunk and preallocation policies likewise charge small files for
work that may not repay its setup cost.

**Resolution.** `NativeCopyBackend.copy()` receives the reviewed
`expected_size` and selects exactly once between private `_copy_serial` and
`_copy_pipelined` engines. The serial engine uses no queue or worker thread.
Both engines share only the hasher construction, full-write helper,
checkpoint/progress contract, and result validation needed to keep their
outputs identical.

`expected_size` is a tuning input, not an EOF boundary or success claim. Both
engines still read until actual EOF and return the observed byte count so
source growth and shrink remain detectable.

The selected engine also chooses its chunk size from the reviewed size and a
measured policy. The pipeline retains the measured 4 MiB chunk size. The
serial path may use a smaller chunk where that reduces peak chunk residency or
checkpoint latency without losing throughput to extra syscalls. A file no
larger than one pipeline chunk cannot overlap stages and is always serial; a
production-shaped size sweep determines whether the serial region extends
farther.

Target-temp preallocation is independently conditional because temp creation
precedes the backend call. `_prepare_copy()` passes an allocation request only
above its measured size crossover; zero-byte and smaller copies skip it.
Only allow-listed errors that mean `FileAllocationInfo` is unsupported fall
back to ordinary streaming; disk-full, quota, permission, unknown, and other
substantive failures remain operation failures. The preallocation crossover
need not equal the serial/pipeline crossover.

The crossover values are private implementation constants established by the
benchmark matrix, not user settings or new executor policy surface. The
initial measurement bands are `<= 4 MiB`, `4-16 MiB`, and `>= 16 MiB`, but
those are experiment bins rather than shipping thresholds.

**Why.** Selection at the synchronous backend boundary keeps pipeline
shutdown semantics out of the serial path. Passing expected size explicitly
also avoids inferring policy from the first read or duplicating planner
knowledge. Keeping the allocation gate at temp creation respects the current
executor/filesystem boundary rather than adding a strategy object solely to
couple two separately measured cutovers.

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

The copy-backup path uses the same close, metadata, single-flush, publish, and
conditional-repair primitives. An update using a hardlink backup is a required
special case: clearing readonly on the live old inode also clears it on the
trash hardlink. Restore and flush that displaced inode when required before
recording the update.

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
readahead. Do not add another source-prefetch queue or multiple outstanding
reads to the buffered backend.

**Why.** Binding once removes pure setup repetition. The sequential flag gives
the Windows cache manager accurate access intent at the handle boundary with
no new buffer-ownership protocol. Additional asynchronous read depth belongs
to a separately measured direct-IO design, not this buffered pipeline.

---

## 4. Implementation

### 4.1 Track 1 - Adaptive Copy Backend and Finalization

Land Track 1 in reviewable steps, running focused executor tests after each:

1. hoist Win32 bindings and add the cached sequential source hint;
2. consolidate pre-publish metadata and the remaining temp flush into one
   native finalization handle, then make post-publish repair observational and
   conditional;
3. pass reviewed size through `CopyBackend`, retain a true serial engine, and
   add measured adaptive chunk/preallocation selection; and
4. add the linear pipeline with one combined byte budget and deterministic
   teardown.

This order takes the fixed per-file reductions first and leaves the concurrency
change until the serial reference and finalization path are stable.

The adaptive copy implementation remains contained inside
`NativeCopyBackend` in `modules/executor.py`. Extend the `CopyBackend` protocol
with the reviewed `expected_size`; do not hide that input in a concrete
backend constructor. The call boundary stays synchronous: it returns one
`CopyDigest` or raises only after the selected serial loop finishes or all
pipeline workers have stopped.

Select `_copy_serial` or `_copy_pipelined` before the first read. Both return
the same `CopyDigest`, report the byte count checked by the executor against
`expected_size`, retain the full-write forward-progress guard, and deliver
`checkpoint()` and `on_chunk()` on the caller thread. The executor retains the
existing `SOURCE_DRIFT` mapping for a size mismatch. Neither engine treats
`expected_size` as a read limit; each reads through actual EOF. The serial
implementation is the direct `read -> full write -> hash` reference path; it
does not instantiate pipeline queues or threads.

For the pipeline, use the calling thread as reader/coordinator plus one hasher
thread and one writer thread. Keep the existing `source.read(chunk_size)`
contract. Each read returns a fresh immutable `bytes` object, and the same
object moves through two FIFO queues:

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

The combined payload window remains roughly eight 4 MiB chunks (~32 MiB) so
the reader and hasher can run ahead and keep the writer from starving during
bursty device writeback. The 2 GiB/s-class measurements used that window; a
shallow two-slot equivalent need not reproduce them. Budget beyond what covers
writer jitter adds RAM without throughput, since the slowest stage still sets
the rate.

Depth also absorbs external CPU contention. In the line topology the writer is
fed through the hasher, so a preempted hasher can starve the writer; a deeper
write queue gives the writer buffered chunks to consume across that gap. A
contention pass (2.4) confirmed the direction: the line's small under-load
disadvantage at two slots closes by eight. Eight chunks covers both device
writeback jitter and scheduler preemption, so no separate contention tuning is
needed.

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
opener rather than retaining a second path-opening implementation.

The backend receives the reviewed size and uses private measured constants to
choose:

- serial versus pipeline engine;
- the serial read chunk size, capped by the existing 4 MiB pipeline chunk.

Separately, `_prepare_copy()` uses the reviewed size to decide whether to pass
an allocation request while creating the temp. Zero-byte files remain serial
and perform no allocation request. Files no larger than one pipeline chunk
remain serial because they cannot overlap two chunks. Do not expose either
cutover as a user setting. Before landing, run the size-distribution benchmark
from 2.7 and replace the experimental bands in DR-HASH-07 with measured
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

Apply the same primitive sequence to copied backups. For hardlink backups,
restore and flush the displaced inode through its trash path if clearing the
live target's readonly bit changed that inode.

#### Published-size guard

After publish and the post-copy stat, assert `published.size == digest.size`
before recording the attestation. The copy loop and source-drift guards already
compare against the reviewed source size; this adds the missing equality
between the bytes hashed and the bytes that reached the target, so any size
divergence (including a future allocation or truncation defect) fails the
operation loudly at write time instead of surfacing later as a content
`ValueError` when the verifier first reads the row. `Attestation` may also
enforce `content.size == subject.size` in `__post_init__` as a cheap structural
backstop.

#### Callback semantics

`checkpoint()` and `on_chunk()` stay on the original caller/coordinator
thread in both engines. Pipeline workers never call either callback.

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
- In the serial engine, call `on_chunk(size)` only after that chunk has been
  fully written and hashed, preserving the same externally visible meaning.

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
| `core/evidence.py` | `ContentEvidence.algorithm` accepts only `xxh3_128`; digest length is exactly 16 bytes; define the standard-library-only streaming hasher/factory protocol used by both consumers |
| `core/execution.py` | `CopyDigest` validates a 16-byte XXH3-128 digest |
| `modules/executor.py` | `NativeCopyBackend` requires a no-argument `hasher_factory`; copy attestation records `xxh3_128`; `ExecutorPolicies.copy_backend` becomes required instead of default-constructing `NativeCopyBackend` |
| `core/integrity.py` | `VerifierContext` requires the same no-argument `hasher_factory` seam |
| `modules/verifier.py` | Baseline, verify, and rebaseline obtain a hasher from the context, require a 16-byte result before any comparison, and record `xxh3_128` |
| `workflows/runtime.py` | Composition imports the concrete XXH3 constructor and explicitly supplies `NativeCopyBackend(hasher_factory=...)` when constructing `ExecutorPolicies`; the M1 integrity workflow supplies it to `VerifierContext` in the same pass |
| `db/repositories.py` | Reconstruct content evidence using the stored identifier rather than replacing it with `sha256` |
| Tests and fixtures | Replace SHA-256 content expectations with canonical XXH3-128 bytes |

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

`VerifierContext` has no production construction site yet because the M1
integrity workflow is not wired. Add its required factory field now and wire
that workflow in the same pass; postponing the seam until after M1 would only
create avoidable constructor churn.

The existing non-content SHA-256 uses in `core/planning.py`,
`dispatcher/custody.py`, `db/history.py`, and `db/recorder.py` are explicitly
unchanged.

### 4.3 Test Impact

Required pipeline coverage:

- Serial reference and pipelined copy produce identical digest bytes and byte
  counts under whichever canonical content hasher is active in that revision,
  across empty, partial-chunk, exact-chunk, and multi-chunk files.
- Backend selection uses only the reviewed expected size, occurs before the
  first read, and creates no worker or queue for serial files. Files no larger
  than one pipeline chunk are serial; measured threshold boundary cases select
  the intended engine.
- Both engines read to actual EOF rather than stopping at expected size, and
  the executor preserves `SOURCE_DRIFT` classification for observed shrink or
  growth.
- Adaptive serial chunking never exceeds the configured pipeline chunk, emits
  progress with the same semantics, and preserves checkpoint responsiveness.
- A source implementing `read()` but not `readinto()` is sufficient.
- Each immutable chunk reaches the writer only after the hasher consumes it;
  no chunk is mutated or copied during handoff.
- `on_chunk()` occurs only after the line's hash and full-write stages and is
  emitted in read order.
- Filling the combined byte budget or either item-bounded data queue applies
  backpressure without deadlock. A chunk moving between queues is charged
  once, the resident-payload high-water never exceeds the configured budget,
  and every completion or abort releases its charge exactly once.
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
- A published file whose size differs from the hashed byte count fails the
  operation before recording, rather than persisting mismatched evidence.
- Cached source opening carries the sequential hint, retains required sharing
  and long-path behavior, and closes the descriptor on success and failure.
- Win32 DLL loading and function-signature binding occur once rather than once
  per file.
- Normal copy and copied-backup paths perform no writer flush, apply ACL and
  pre-publish metadata after writer close, and issue exactly one temp-file
  flush before publication.
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

### 4.4 Estimate

- Track 1: approximately 3-4 implementation days including the measured
  size-policy sweep, serial/pipeline selection, native allocation and
  finalization, deterministic cancellation/failure handling, and focused
  tests. The linear pipeline removes the prior lease and
  dual-acknowledgement work, but combined-budget accounting, selective
  metadata repair, queue shutdown, and failure coverage remain substantive.
- Track 2: approximately 1 implementation day plus 1 day for fixtures,
  vectors, persistence round-trips, and regression tests.

These remain estimates from the measured prototype and a static read of the
call sites, not from an attempted production implementation.

---

## 5. Deferred

- **Concurrent file execution.** Reconsider only if post-XXH3 measurements
  show that a real workload leaves relevant devices underutilized.
- **Cross-file batching or large-first/small-last passes.** The plan already
  contains global operation knowledge, but reordering alone does not remove
  file opens, metadata work, flushes, recorder calls, or database commits. It
  would change dependency scheduling, progress/history order, pause/cancel,
  failure, stop, and end-of-run semantics. A future batching design must first
  define those contracts. If measurement later justifies multi-file
  preparation, keep reversible copy-to-temp work separate from a plan-order
  coordinator that guards, publishes, flushes, records, and settles each
  operation. Directory-flush coalescing and recorder transaction batching are
  separate durability decisions, not implied by file ordering.
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
