# Hash Pipeline and XXH3 Refactor

Status: investigation and planning completed 2026-07-22. Nothing below is
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
- Unbuffered IO (`FILE_FLAG_NO_BUFFERING`), sector-aligned buffers

The unbuffered requirement is not incidental. A first pass using ordinary
buffered IO with a 1 GiB file on a 64 GB machine measured a fully page-cached
read leg on the slower `C:` volume and understated the hash cost by roughly
half. Any future re-measurement must defeat the page cache and must not
silently copy within one volume when the intent is cross-volume.

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

Serial is the exact current `NativeCopyBackend.copy` shape: `read -> write ->
update` in one thread. Pipelined is a three-stage version with separate
reader/coordinator, writer, and hasher threads over a recycled buffer pool.
Digests were asserted identical between the two shapes for every measured
algorithm.

| Algorithm | Serial MiB/s | Pipelined MiB/s | Gain |
|---|---:|---:|---:|
| none (hashless) | 2 637 | 5 254 | +99.2% |
| xxh3_128 | 2 118 | 5 318 | +151.1% |
| sha256 | 1 261 | 1 910 | +51.5% |
| blake2b | 591 | 971 | +64.1% |

Run-to-run variance across passes was roughly 5% (hashless serial measured
2 680 and 2 637 on two runs; SHA-256 serial measured 1 189 and 1 261). Treat
all figures as approximate; the ratios are what matter.

### 2.5 What the Numbers Mean

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

### 2.6 Where the Algorithm Change Matters

Pipelined SHA-256 saturates at roughly 1 900-2 400 MiB/s. Below that, the copy
path is already storage-bound and changing the hash does not improve transfer
speed. The algorithm replacement is therefore a fast-path optimization for
high-throughput storage, while the pipeline addresses structural
serialization on every medium.

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

---

## 4. Implementation

### 4.1 Track 1 - Pipelined Copy Backend

The pipeline remains contained inside `NativeCopyBackend` in
`modules/executor.py`. The `CopyBackend` call boundary stays synchronous: it
returns one `CopyDigest` or raises only after all worker threads have stopped.

Use one caller/coordinator thread, one writer thread, and one hasher thread
over a bounded recycled buffer pool. Eight 4 MiB buffers measured well and
consume roughly 32 MiB because writer and hasher share the same buffer.
Ordinary buffered IO does not require sector-aligned buffers; alignment only
becomes a contract if the executor separately adopts unbuffered IO.

#### Buffer lifecycle

```text
                              writer releases lease(completed=...)
                            /
free -> coordinator reads buffer
       and creates two leases
                            \
                              hasher releases lease(completed=...)

final lease release
  -> if neither consumer discarded: publish ChunkComplete(sequence, size)
  -> always return buffer directly to free pool

coordinator consumes ChunkComplete
  -> reports progress in sequence order
```

The buffer must not be mutated or returned to the free pool until both
consumers release their lease. Each buffer carries a thread-safe remaining
consumer count initialized to two plus a `discarded` flag. Writer and hasher
each release exactly once in `finally`, including failure and abort paths. A
release with `completed=False` sets `discarded`; the final release returns the
buffer directly to the free pool regardless of success.

Only a genuine dual completion publishes immutable
`ChunkComplete(sequence, size)` metadata. If either consumer skipped,
discarded, or failed its work, the buffer is recycled but no completion record
is emitted and `on_chunk()` can never count it. Publish the completion record
before returning the buffer so the record exists before reuse, and use a
nonblocking producer queue such as `SimpleQueue`; a bounded completion queue
can recreate the two-queue deadlock this ownership model removes.

The coordinator never returns buffers. It drains completion records before
and after scheduling reads and after EOF, reports them in sequence order, and
may safely process a record after its buffer has already been reused because
the record contains no buffer reference. Writer and hasher each consume a FIFO
work queue; sequence checks make the normal-path ordering invariant explicit
and testable.

#### Callback semantics

`checkpoint()` and `on_chunk()` stay on the original caller/coordinator
thread. Workers never call either callback.

- Call `checkpoint()` before admitting each new read, matching the current
  chunk-boundary cancellation point.
- When the free pool is empty, wait with a bounded timeout. On each timeout,
  inspect the first-error slot and call `checkpoint()` before waiting again;
  never block forever on the free queue while control or worker failure is
  pending.
- Call `on_chunk(size)` only after that chunk has been fully written to the
  owned temporary file and included in the digest.
- Release progress in sequence order, even if worker acknowledgements arrive
  at different times.

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
- A worker may finish its current chunk after abort, but must not start useful
  work on later queued chunks. Queued buffers are consumed and released with
  `completed=False` so no producer or peer remains blocked on the bounded pool
  and no discarded chunk produces progress.
- Once abort is observed, the coordinator stops draining completion records,
  stops calling `on_chunk()`, and applies no normal-path sequence assertions.
  A genuine completion racing with abort may remain queued and is ignored.
  Teardown must preserve the initiating control/error exception rather than
  mask it with a progress-order assertion or secondary cleanup failure.
- Writer errors stop further writes. Hasher errors prevent any digest from
  being returned. Reader and callback errors follow the same abort-and-join
  path.
- Retain the existing short-write loop and the
  `written is None or written <= 0` forward-progress guard.
- The caller never observes a return or exception while a worker is still
  running.

Because the executor publishes only after `copy()` returns, cancellation or
worker failure leaves at most an owned temporary file, which the existing
executor cleanup path removes.

Explicit `Thread`, bounded `Queue`, and small buffer-state records are favored
over a general thread pool: ownership, draining, and shutdown need to remain
visible and deterministic.

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
- `on_chunk()` occurs only after both write and hash acknowledgement and is
  emitted in sequence order.
- Exhausting the free pool while completions are pending cannot deadlock;
  final worker release recycles the buffer without coordinator intervention.
- A write/hash discard releases both leases, returns the buffer, emits no
  `ChunkComplete`, and advances no progress.
- Short writes make forward progress; zero/`None` writes fail.
- Reader, writer, hasher, and callback failures terminate and join both
  workers without deadlock.
- Cancel and pause at each pipeline stage terminate cleanly, publish nothing,
  stop completion draining without a teardown ordering assertion, preserve the
  initiating exception, and allow owned-temp cleanup.
- The bounded pool is actually bounded and buffers are never reused before
  both consumers release them.
- Cancellation tests use explicit pipeline-stage synchronization rather than
  depending on an exact checkpoint call count.

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

- Track 1: approximately 2-3 implementation days including deterministic
  cancellation/failure handling and focused tests. The earlier one-day
  estimate omitted acknowledgement and shutdown semantics.
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
- **Additional content algorithms.** Require a concrete product need and a
  new decision covering semantics, evidence compatibility, and tests. No
  registry or dormant extension mechanism is added in M1. The required,
  parameterless hasher factory is only the inversion seam for the one pinned
  implementation; turning it into an algorithm-keyed factory would violate
  DR-HASH-02.
