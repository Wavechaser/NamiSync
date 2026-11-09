# Latest session — table driver repair and projection tuning, 2026-11-09

## Delivered changes

Branch `milestone1`. `c4fb6340` fixes the optional table-loading driver and
its two pre-existing test failures: observe `native.response` after direct
settlement without restoring a clone. Installed verification also exposed a
pre-input Inventory setup race. The driver now waits for authoritative highlight
adoption before the timed ArrowUp; target, geometry and landing checks remain.

The subsequent Plan change computes basenames and sort keys once, shares equal
immutable display/key strings and reuses keys for member rows. It changes no
public fields, frozen constructor, exact paths, raw Unicode sorting or selection.
No global cache or interning is introduced.

## Measurements and decisions

The existing component producer ran three alternating fresh-child pairs per
metric against baseline/sharing 303-file snapshots on CPython 3.13.17:

- Construction-overlap incremental peak private bytes: baseline 309.01–309.61
  MiB; sharing 292.62–295.76 MiB. Every pair improved, by 13.84–16.39 MiB.
- Cold base: 2,190–2,263 versus 2,128–2,226 ms. Heavy: 3,124–3,329 versus
  3,097–3,384 ms. Mixed paired changes and overlapping ranges; no stable speed
  claim. Both base arms exceed the historical 2,000 ms reference budget under
  this observation context. This is not renewed R3 acceptance.
- A separate ignored direct-slot constructor trial saved 130–383 ms in three
  base pairs, with substantial drift in both arms. It remains unshipped: a
  second explicit 35-field initialization mapping adds maintenance beyond the
  small string-sharing change. Keep it as a future lever.
- Full 35-field fingerprints match baseline/sharing/trial over all 120k base
  and 240k heavy nodes. Sampled process-memory savings are not decomposed from
  shallow string bytes or allocator effects.

[PERFORMANCE](PERFORMANCE.md#plan-string-sharing-diagnostics--2026-11-09)
contains the method, ranges and limitations. Sparse records and combined
builders remain excluded. Historical budgets are unchanged.

## Verification and evidence

- Driver: 45 focused tests; final tools department 427 passed, three existing
  symlink-privilege skips. Fixture checks passed. Final installed Plan/Inventory
  each completed 16 gestures, 41/42 requests; all assets restored by hash.
  All 303 installed package files verified. `build/table-driver-fix-20261109/`
  retains receipts, identities, failed attempts and exact setup-race trace.
- Projection: 105 focused projection/review tests passed; baseline negative control
  fails the three intended sharing assertions while both nonsharing cases pass.
  Final workflow/interface verification passed 3,257 tests, with 3,281
  deselected. Logs, JUnit and source identity receipts are under
  `build/projection-tuning-20261109/`.
- Independent reviewers inspected source, metrics, fixture provenance and
  driver asset restoration. Documentation links and diff checks accompany the
  final commit. No budget, safety or timing assertion was weakened.

## Operational context

No measuring-session process, profile or corpus was touched. Driver native
hosts/children exited under existing Job cleanup; pywebview's directory-cleanup
sharing warnings remain in evidence, without claiming natural empty browser
jobs. Ignored snapshots and diagnostic evidence are retained. The previous
17.9 MiB path attribution was corrected in `5081cc17`: that bucket contains
existing node IDs, not newly retained folder paths.
