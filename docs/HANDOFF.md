# Latest session — backend-idle renderer collection, 2026-11-07

## Delivered behavior

The desktop attempts native renderer GC after successful terminal-session release
and completed task Close. The backend permits it only when no admissions or
unreleased sessions remain; paused, queued, running and terminal-but-unreleased
sessions block it. A lifecycle reservation holds new admissions until native
completion or renderer exit, with no lifecycle lock held during the native call.
Collection failure is logged without changing the successful release/close result.

The host wraps the existing commands; there is no new browser command, frontend
change, workflow barrier, timer, heap cap or Low-memory target. Phase-transition
GC is shelved by user decision. Busy/overlapping attempts are skipped until a
later successful release/close; this is not collection on every possible idle
transition. Collection precedes the small command response, so it does not promise
immediate reclamation of page objects still live until task teardown.

## Verification and evidence

- 229 focused tests, 2,239 ordinary interface tests and six installed native
  transport cases pass. Tests cover pending/unreleased sessions, concurrent
  admission, collection failure, renderer exit and shutdown.
  Independent adversarial review approved source, tests, artifact identity,
  raw native evidence and final documentation.
- The installed-wheel probe native-paused-10k-01 holds a real 1k execution
  paused while a separate 10k copy/automatic verification completes and closes.
  Its exact Plan release, execution release and Close all skip collection.
  After the held execution resumes and completes, production GC reduces JS heap
  from 334.74 to 3.24 MiB in a 70.31 ms native round trip. Final Close collects
  3.97 to 3.18 MiB in 137.90 ms. These are not isolated GC pause measurements.
  Both exact mirrors, unchanged inputs/product and normal exit with an empty
  owned Job pass. All resource windows are complete; all owned apps are closed.
  Runtime is now Edge 157.0.4341.42 / V8 15.7.11.4, so these observations are
  not a matched comparison with the earlier 156/15.6 diagnostics.
- build/idle-gc-20261107/ retains builder/integration reports, exact test logs,
  installed wheel and source/runtime/producer manifests, and raw run receipts.
  All 303 product files match the working tree, frozen reference and installed
  wheel. The diagnostic observes production collection; it never requests GC.
  native-report.json selects the complete windows and hashes its raw inputs.
- Earlier failed test attempts remain preserved: sandbox temporary-directory
  creation errors, then rejection of a repository-local pycache by the existing
  custody fixture. Unchanged product/tests pass with normal external temp access.

PERFORMANCE owns detailed observations and their limits. Earlier allocation and
GC/Low diagnostics remain at cbf3f090 / 2d86b1a0, with evidence under
build/allocation-20261107/ and build/memory-probe-20261107/. The original
resource-study package, fixtures and unrelated processes were not modified.

## Operational context

No phase-transition or execution-peak policy is scheduled. This bounded native
witness does not replace the prior long-run stability schedule or establish
behavior under system memory pressure. Grouped recording, parent flushes and
small-file batching remain M2 work.

The longstanding installed execution-review exact-receipts failure remains
unresolved; fcb72b37 added its trace. TESTS describes preserving the sidecar;
paired historical failures remain in build/receipt-rate-20261106/.
