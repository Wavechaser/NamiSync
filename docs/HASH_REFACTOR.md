# Hash Pipeline and Algorithm Refactor

Status: investigation and planning completed 2026-07-22. Nothing below is
implemented. This is both the plan for two related performance tracks and the
decision log for the choices made while shaping them, in the same role
`M1_PLAN.md` plays for M1 and `DESIGN_REVIEW.md` plays for M0.

**Standing.** This document governs the unimplemented hash-throughput work
until each decision is promoted into the active documents. `FEATURES.md` owns
behavior, `ARCHITECTURE.md` owns contracts, module docs are subordinate to
both; where this plan changes a settled bullet, the active document is edited
**as that track lands**, not deferred. Once promoted, the active document
wins and this file becomes history.

---

## 1. What Prompted This

Benchmarking showed the verifier is CPU-bound as expected, but the executor
was *also* CPU-bound in some configurations, capped by SHA-256 throughput on
the copying thread. The original M1 assumption was that multithreaded verify
was the answer. This investigation asked a narrower question: what is
actually limiting `NativeCopyBackend.copy`, and would supporting a faster
hash algorithm help more than threading?

The answer turned out to be **both, in a specific order**, and the reasoning
depends on measurements that contradict the first plausible guess. Section 2
records the measurements because they are the entire basis for the decisions
in Section 3.

---

## 2. Measurements

### 2.1 Bench Environment

- CPU: Intel Core i7-13700K, 16C/24T, SHA-NI present
- RAM: 64 GB
- Python 3.13.14, `xxhash` 3.8.1
- Source: `F:` — WD_BLACK SN850X 4 TB
- Target: `G:` — WD_BLACK SN850X 4 TB (separate physical disk)
- 8 GiB workload, 4 MiB chunks (the `chunk_size` default in
  `executor.py` and `integrity.py`)
- **Unbuffered IO** (`FILE_FLAG_NO_BUFFERING`), sector-aligned buffers

The unbuffered requirement is not incidental. A first pass using ordinary
buffered IO with a 1 GiB file on a 64 GB machine measured a fully
page-cached read leg on the slower `C:` volume (Samsung 970 EVO Plus, Gen3)
and produced numbers that understated the hash cost by roughly half. Any
future re-measurement must defeat the page cache and must not silently copy
within one volume when the intent is cross-volume.

### 2.2 Hash Throughput, Single Thread, No IO

| Algorithm | MiB/s |
|---|---|
| xxh3_128 | 35 433 |
| xxh3_64 | 34 491 |
| xxh64 | 19 616 |
| sha256 | 2 441 |
| blake2b | 1 067 |

SHA-256 is hardware-accelerated on this CPU and is consequently *faster than
BLAKE2b and faster than MD5*. Any intuition that "a non-cryptographic hash is
obviously faster" is only correct here because XXH3 is roughly 14.5x SHA-256;
it does not generalize to the BLAKE family, which is slower.

### 2.3 IO Ceilings

| Operation | MiB/s |
|---|---|
| read-only, unbuffered | 5 433 |
| write-only, unbuffered | 5 316 |

### 2.4 Copy Loop: Serial vs Pipelined

Serial is the exact current `NativeCopyBackend.copy` shape — `read → write →
update` in one thread. Pipelined is a three-stage version with separate
reader, writer, and hasher threads and a recycled buffer pool. Digests were
asserted identical between the two shapes for every algorithm.

| Algorithm | Serial | Pipelined | Gain |
|---|---|---|---|
| none (hashless) | 2 637 | 5 254 | +99.2% |
| xxh3_128 | 2 118 | 5 318 | +151.1% |
| sha256 | 1 261 | 1 910 | +51.5% |
| blake2b | 591 | 971 | +64.1% |

Run-to-run variance across passes was roughly 5% (hashless serial measured
2 680 and 2 637 on two runs; sha256 serial 1 189 and 1 261). Treat all
figures as approximate; the ratios are what matter.

### 2.5 What the Numbers Mean

**The serial loop wastes half the disk before hashing enters the picture.**
Hashless serial reaches 2 637 MiB/s against disks that sustain 5 300+,
because `read`, `write`, and `update` are serialized in one thread and their
throughputs combine harmonically rather than overlapping. Pipelining alone
recovers this to 5 254 — effectively the IO ceiling.

**SHA-256 currently costs 52% of achievable throughput** (2 637 → 1 261 in
the serial shape).

**Pipelining converts SHA-256 from a tax into a hard ceiling.** Once stages
overlap, throughput becomes the slowest stage. With SHA-256 that stage is the
hash at 2 441 MiB/s, and the measured pipelined result is 1 910. With
XXH3 the hash stage disappears entirely and the pipeline reaches 5 318.

**Neither change alone gets more than roughly 2 000 MiB/s:**

| Configuration | MiB/s | vs today |
|---|---|---|
| Serial + sha256 (today) | 1 261 | — |
| Pipeline only, keep sha256 | 1 910 | +51% |
| Algorithm only, stay serial | 2 118 | +68% |
| **Both** | **5 318** | **+322%** |

### 2.6 The Crossover — Where XXH3 Stops Mattering

Pipelined SHA-256 saturates at roughly 1 900–2 400 MiB/s. Below that, the
copy path is IO-bound and **SHA-256 is already free**. The algorithm choice
therefore only matters when the slower end of the copy path sustains more
than about 2 GB/s.

On the development machine's own hardware that means SN850X-to-SN850X or the
Optane volumes qualify; the portable SSDs, the USB-NVMe enclosure, the 16 TB
spinning disks, and any network target do not. This is the single most
important constraint on the work: **the algorithm track is a fast-path
optimization, not a general one.** The pipeline track, by contrast, helps
everywhere, because read/write serialization costs throughput on slow media
too.

### 2.7 Bench Reproduction

The bench scripts are session scratch artifacts and are not committed. To
reproduce, a script must:

1. Open source and target with `FILE_FLAG_NO_BUFFERING` and sector-aligned
   buffers, or otherwise guarantee cache-cold reads.
2. Use a workload comfortably larger than any plausible cache effect.
3. Copy **across two physical volumes**, and record which volumes.
4. Assert digest equality between serial and pipelined shapes.
5. Report a hashless baseline alongside every hashed measurement, since the
   hashless number is what separates IO cost from hash cost.

Any figure in Section 2 that is re-derived on other hardware should be
recorded with its own environment block rather than overwriting these.

---

## 3. Decision Log

Numbered `DR-HASH-##` to avoid colliding with `DR-M1-##` in `M1_PLAN.md` and
`DESIGN_REVIEW.md`'s M0 numbering.

### DR-HASH-01 — Pipeline before algorithm

**Tension.** Both changes yield roughly +50–70% alone; the 4.2x needs both.
Which lands first?

**Resolution.** Pipeline first, as an independent track that ships on its
own.

**Why.** It is a universal win — read/write serialization costs throughput on
every medium, not just above the 2 GB/s crossover. It requires no format
change, no configuration surface, no new outcome states, and no dependency.
Critically it is *contained*: the `CopyBackend` protocol at
`core/execution.py:148` already isolates the byte loop, so the entire change
lives inside `NativeCopyBackend` in `modules/executor.py`. It is also a
prerequisite for the algorithm track to pay off fully — a faster hash in a
serial loop tops out at 2 118 MiB/s.

### DR-HASH-02 — Support multiple algorithms rather than switching wholesale

**Tension.** A wholesale switch to XXH3 is roughly half a day. Supporting
both is 2–3 days. Ledger and history contain no production data and can be
reset, so the migration cost that would normally dominate this comparison is
zero.

**Resolution.** Support both. SHA-256 stays the default.

**Why.** Section 2.6 is the argument. Below the crossover, SHA-256 is
already free because the path is IO-bound; deleting a zero-cost option to
save two days is a poor trade. The registry indirection is the small part of
the work — most of the 2–3 days is test churn that a wholesale switch
incurs anyway. Retaining SHA-256 also keeps cryptographic evidence available
for users who want it, and keeps the unwritten sidecar-import module able to
consume TeraCopy `.sha256` files without a special case.

**Explicitly not a factor.** Deliberate tampering is out of scope for
NamiSync, which targets naturally occurring defects such as bit rot. The
cryptographic strength of SHA-256 is retained as a side benefit, not as a
security guarantee the product makes.

### DR-HASH-03 — Algorithm is fixed per location

**Tension.** If the configured algorithm can differ from the algorithm stored
on a row, VERIFY compares digests of different lengths at
`modules/verifier.py:329` and reports `HASH_MISMATCH` — a **false bit-rot
alarm**, the worst possible failure for this tool.

**Resolution.** The algorithm is a per-location property chosen at location
creation. VERIFY reads the algorithm **from the baseline row**, not from
configuration. BASELINE reads it from the location's configuration.

**Why.** This makes a cross-algorithm comparison structurally impossible in
VERIFY rather than merely guarded against. The remaining guard (DR-HASH-04)
becomes defensive rather than load-bearing.

### DR-HASH-04 — Algorithm change is a rebaseline, not a mismatch

**Tension.** A user who changes a location's algorithm still needs a defined
path, and the existing invariant at `core/integrity.py:247` requires VERIFY
to have established evidence.

**Resolution.** One new `IntegrityReason` — `ALGORITHM_MISMATCH` — reported
by a guard placed next to the existing `BASELINE_EXISTS` check at
`modules/verifier.py:253`, before any read occurs. It does not advance
`last_verified_at` and does not report `MISMATCHED`. Migration is performed
by the existing `IntegrityMode.REBASELINE`.

**Why.** The machinery already exists. `REBASELINE` is defined at
`core/integrity.py:48` and exposed at `modules/verifier.py:100`, and the
invariants at `core/integrity.py:245-249` already give it the correct
semantics: rebaseline does not advance verification time, which is exactly
right for an algorithm migration — the file was re-hashed, not verified.
Placing the guard before the read also avoids paying IO for a comparison that
cannot succeed.

### DR-HASH-05 — Single evidence column group; rejected two-column split

**Tension.** A proposal to carry two ledger digest columns, one per
algorithm, with flags recording which is populated. The stated goal was to
eliminate cross-algorithm comparison and mixed-inventory concerns at the
schema level.

**Resolution.** Rejected. Keep the single evidence group.

**Why.** The digest is not a standalone column. It is one field of a
**14-column evidence group** (`db/schema.py:98-110`): algorithm, digest,
size, provenance, observed_at, seven `attested_*` subject-stat fields, and
`last_verified_at`. That group is bound to a *single read* —
`modules/verifier.py:342-356` takes `observed_at` from the clock at hash time
and `subject` from the `after` stat of the same open handle. `Attestation`
means one read, one algorithm, one observed subject, and that binding is what
makes it evidence rather than a cached value.

Two digest columns therefore force a choice, and all three branches are worse
than the single column:

- **Share the evidence group.** Unsound. Two digests computed from two reads
  at different times sit under one `content_observed_at` and one
  `attested_mtime_ns`; if the file changed between them the row asserts
  something false. This directly attacks the integrity property the product
  exists to provide.
- **Duplicate the group per algorithm.** Sound, but roughly ten additional
  columns, and the all-or-nothing CHECK at `db/schema.py:120-129` becomes two
  independent groups plus an at-least-one rule. Every future algorithm is
  another `ALTER TABLE`.
- **Require both digests from one read.** Sound and cheap — XXH3 alongside
  SHA-256 is nearly free — but self-defeating. Always computing both means
  always paying SHA-256's 2 441 MiB/s ceiling, which pipelined is ~1 910
  MiB/s, precisely the status quo. The entire gain evaporates.

The only thing the split genuinely buys is per-file coexistence, allowing an
incremental algorithm change without a full rebaseline. That is real but
worth less than it appears, because the only honest way to populate both
digests is the self-defeating third branch.

**If coexistence is later wanted**, the correct shape is a child table keyed
`(inventory_id, algorithm)` carrying a complete evidence group per row — not
more columns. That models `Attestation` exactly as `core/evidence.py` already
defines it and makes future algorithms a zero-schema-change addition. Cost is
roughly one day over the single-column plan, since `db/repositories.py:103`
and the two recorder UPDATE paths (`db/recorder.py:656`, `:1129`) move from
column access to a join and an upsert.

**Note on the reset argument.** "The DB can be nuked" is true today and was
correctly used to discount migration cost in DR-HASH-02. It is deliberately
*not* used to justify schema shapes here: the reset window closes at v1.0,
and the schema chosen now should be the one wanted then.

---

## 4. Implementation

Two independent tracks. Track 1 ships alone and is worth shipping alone.

### 4.1 Track 1 — Pipelined Copy Backend

Entirely contained within `NativeCopyBackend` in `modules/executor.py:93`.
The `CopyBackend` protocol at `core/execution.py:148` is unchanged, so no
caller, policy, or contract outside the class is affected.

Shape: a reader thread, a writer thread, and a hasher thread over a recycled
pool of aligned buffers (8 buffers measured well). Each chunk is handed to
both the writer and the hasher; the buffer returns to the free pool once both
consumers release it.

Constraints to preserve:

- `checkpoint()` and `on_chunk` are per-chunk callbacks in the current
  contract. Keep both **in the reader thread** so their ordering and
  cancellation semantics are unchanged and no caller needs to become
  thread-safe.
- Forward-progress and short-write handling in the writer must retain the
  current `written is None or written <= 0` guard.
- Cancellation must not deadlock: a checkpoint raising mid-stream has to
  drain or abandon queues without leaving threads joined forever.
- The digest must be byte-identical to the serial shape. The bench asserted
  this; the test suite should too.

An open question is whether the executor should also move to unbuffered IO.
The bench used it to defeat the page cache, but the executor currently opens
files through ordinary buffered `open()`. The pipelining gain is structural
and should hold either way; whether unbuffered helps or hurts real copies is
a separate measurement, not assumed here.

### 4.2 Track 2 — Multi-Algorithm Support

| Change | Size |
|---|---|
| New `HashAlgorithm` registry: name → factory, digest size | ~40 lines |
| `core/evidence.py:50-62` — `Literal["sha256"]` → validated name; fixed 32-byte check → registry length | ~5 lines |
| `core/execution.py:137-143` — add `algorithm` to `CopyDigest`; length check via registry | ~5 lines |
| `modules/executor.py` — `ExecutorPolicies.algorithm` field; backend uses it; `_attestation` at `:2100` reads it from `CopyDigest` instead of the literal at `:2104` | ~10 lines |
| `modules/verifier.py` — `VerifierContext.algorithm`; construct via registry at `:294`; algorithm at `:345` from context | ~10 lines |
| `db/repositories.py:120` — read the stored `content_algorithm` instead of hardcoding | 1 line |
| DR-HASH-04 guard + new `IntegrityReason` | ~15 lines |
| `pyproject.toml` — `xxhash` dependency | 1 line |
| **DB schema / migration** | **none** |
| **CLI** | **none yet** |

Two notes on that table:

`content_algorithm` is already a real per-row column written from
`attestation.content.algorithm` (`db/recorder.py:666`) and compared in the
idempotence check (`db/recorder.py:710`). The only place it is discarded is
the hardcoded `"sha256"` on read at `db/repositories.py:120`. **The DB layer
needs no schema change**, independent of the reset question.

`interfaces/cli.py` does not expose baseline, verify, or rebaseline at all
today, so no interface work is required by this track. The per-location
algorithm setting from DR-HASH-03 lands with whichever M1 track introduces
location configuration, and should be treated as a dependency on that track
rather than duplicated here.

`chunk_size` is the precedent for how the algorithm threads through: a
defaulted dataclass field on `VerifierContext` (`core/integrity.py:289`) and
`ExecutorPolicies` (`modules/executor.py:152`). Following it introduces no new
plumbing concept.

### 4.3 Test Impact

Seven test files reference `sha256`, `ContentEvidence`, or `CopyDigest`:
`tests/_db_fixtures.py`, `tests/core/test_session_events.py`,
`tests/modules/test_verifier.py`, `tests/test_core_scanplan.py`,
`tests/test_executor.py`, `tests/test_recorder_inventory_integrity.py`,
`tests/test_scanner.py`.

Most churn is mechanical — threading an `algorithm` through constructors.
New coverage needed:

- Round-trip baseline → verify parametrized across algorithms.
- DR-HASH-04: VERIFY against a row whose algorithm differs reports
  `ALGORITHM_MISMATCH`, does not report `MISMATCHED`, does not advance
  `last_verified_at`, and performs no read.
- REBASELINE migrates a row from one algorithm to another.
- Pipelined and serial copy backends produce identical digests.
- Cancellation mid-copy in the pipelined backend terminates cleanly.

### 4.4 Estimate

Track 1: ~1 day plus tests. Track 2: ~1 day production code, ~1 day test
churn, ~0.5 day for the DR-HASH-04 path and its tests.

These are estimates from a static read of the call sites, not from an
attempted implementation.

---

## 5. Deferred

- **Multithreaded verify.** Unchanged as an M1 item and independent of both
  tracks here. The verifier is parallel across files, so it scales with cores
  rather than capping at a single-stream ceiling.
- **Per-file multi-algorithm evidence.** Only via the child table in
  DR-HASH-05, only if a concrete need appears.
- **Unbuffered executor IO.** Needs its own measurement (§4.1).
- **Additional algorithms.** The registry makes BLAKE3 or others additive,
  but §2.2 shows the BLAKE family is slower than hardware SHA-256 on this
  class of CPU, so there is no throughput case for them today.
