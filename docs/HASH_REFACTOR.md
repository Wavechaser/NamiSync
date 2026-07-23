# Hash Pipeline and XXH3 Refactor

Status: investigation and planning last revised 2026-07-23. Nothing below is
implemented. This document records two independent M1 performance tracks:
single-file copy pipelining and the wholesale replacement of SHA-256 content
hashing with XXH3-128.

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

The first problem calls for a bounded three-stage pipeline inside one file
copy. The second calls for a faster content hash. These changes complement
one another but solve different problems: XXH3-128 removes hashing as the
reason to execute multiple files concurrently; it does not remove the need to
overlap one file's reads, writes, and hashing.

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
| pipelined read() + preallocation (chosen) | ~2 700-3 100 | +120% to +150% |

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
by 4 MiB. M1 accepts that small-file penalty: filesystem enumeration, open,
metadata, and publish costs already dominate that workload, and a second
serial mode would add a branch and test matrix without a demonstrated
user-visible benefit.

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

Figures re-derived on other hardware should be recorded with their own
environment block rather than overwriting these results.

---

## 3. Decision Log

### DR-HASH-01 - Keep the pipeline and algorithm tracks independent

**Tension.** Both changes improve throughput, but they address different
limits and have different failure surfaces.

**Resolution.** Implement the pipelined copy backend as an independent track.
The XXH3-128 replacement neither absorbs nor weakens that work.

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
same object, and one worker writes it. The target temp is preallocated from
the reviewed source size before streaming.

No serial fast path is added for small files. The measured worker-startup
penalty is accepted at 4 KiB and is negligible by 4 MiB.

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
bounded queues retain backpressure, and follow-up measurements found no
meaningful throughput difference between the line and fork topologies.
Preallocation recovers roughly the same performance increment as mutable
buffer reuse without importing its ownership protocol.

---

## 4. Implementation

### 4.1 Track 1 - Pipelined Copy Backend

The pipeline remains contained inside `NativeCopyBackend` in
`modules/executor.py`. The `CopyBackend` call boundary stays synchronous: it
returns one `CopyDigest` or raises only after all worker threads have stopped.

Use the calling thread as reader/coordinator plus one hasher thread and one
writer thread. Keep the existing `source.read(chunk_size)` contract. Each read
returns a fresh immutable `bytes` object, and the same object moves through
two bounded FIFO queues:

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
lifetime. Bound the two data queues so backpressure also bounds memory.

Only one file streams at a time (DR-HASH-04), so per-copy memory is not scarce
and queue depth is chosen for throughput, not to minimize RAM. Size the
combined in-flight payload to about the measured prototype (roughly eight
4 MiB chunks, ~32 MiB) so the reader and hasher can run ahead and keep the
writer from starving during bursty device writeback. The 2 GiB/s-class
measurements used that depth; a shallow two-slot queue would bound memory
tighter but need not reproduce them. Depth beyond what covers writer jitter
adds RAM without throughput, since the slowest stage still sets the rate.

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

#### Target-temp preallocation

Extend the existing filesystem seam to
`create_temp(path, *, allocation_size: int)`. `_prepare_copy()` passes
`operation.source_expected.size`, which is the reviewed size already guarded
before streaming and checked again through byte-count and source-drift guards
after streaming.

`NativeFileSystem.create_temp()` still creates the owned temp exclusively,
then requests the reviewed allocation with Windows
`SetFileInformationByHandle(FileAllocationInfo)`. Allocation size and logical
EOF remain distinct: the request reserves target space while ordinary writes
advance EOF. Skip the request for zero-byte files.

Preallocation is an optimization and early resource check, not evidence that
the copy succeeded:

- Unsupported allocation requests fall back to ordinary streaming.
- Disk-full, quota, permission, and other substantive allocation failures
  fail the operation before bytes are copied.
- Short-write checks, digest byte count, flushes, post-copy source guards, and
  owned-temp cleanup remain mandatory.

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
thread. Workers never call either callback.

- Call `checkpoint()` before admitting each new read, matching the current
  chunk-boundary cancellation point.
- Drain ready writer completions before each read, while waiting to enqueue,
  and after normal EOF.
- When a bounded data queue is full, wait with a timeout. On each timeout,
  inspect the first-error slot and call `checkpoint()` before waiting again.
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
- A source implementing `read()` but not `readinto()` is sufficient.
- Each immutable chunk reaches the writer only after the hasher consumes it;
  no chunk is mutated or copied during handoff.
- `on_chunk()` occurs only after the line's hash and full-write stages and is
  emitted in read order.
- Filling either bounded data queue applies backpressure without deadlock or
  exceeding the configured resident-payload bound.
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
- Temp creation requests the exact reviewed source allocation; zero-length and
  unsupported-allocation paths continue correctly, while substantive
  allocation failures abort before streaming.
- Source shrink/growth after preallocation is still rejected by byte-count
  and post-copy drift guards, and the owned temp is removed.
- A published file whose size differs from the hashed byte count fails the
  operation before recording, rather than persisting mismatched evidence.
- A 4 KiB file uses the same pipeline rather than a separate serial fast path.

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

- Track 1: approximately 2 implementation days including native
  preallocation, deterministic cancellation/failure handling, and focused
  tests. The linear pipeline removes the prior lease and dual-acknowledgement
  work, but queue shutdown and failure coverage remain substantive.
- Track 2: approximately 1 implementation day plus 1 day for fixtures,
  vectors, persistence round-trips, and regression tests.

These remain estimates from the measured prototype and a static read of the
call sites, not from an attempted production implementation.

---

## 5. Deferred

- **Concurrent file execution.** Reconsider only if post-XXH3 measurements
  show that a real workload leaves relevant devices underutilized.
- **Parallel verification.** Same gate: demonstrate an IO-utilization problem
  after XXH3-128 before adding workers.
- **Unbuffered executor IO.** Needs its own measurement; the current benchmark
  does not establish that it improves the production buffered path.
- **Mutable `readinto()` buffers or a fork topology.** Reconsider only if a
  production-shaped benchmark shows a user-visible gain large enough to
  justify explicit buffer ownership and dual-consumer completion state.
- **Small-file serial fast path.** The measured pipeline penalty is accepted
  for M1. Reconsider only if directory-level workloads, rather than isolated
  4 KiB microbenchmarks, show a user-visible regression.
- **Additional content algorithms.** Require a concrete product need and a
  new decision covering semantics, evidence compatibility, and tests. No
  registry or dormant extension mechanism is added in M1. The required,
  parameterless hasher factory is only the inversion seam for the one pinned
  implementation; turning it into an algorithm-keyed factory would violate
  DR-HASH-02.
