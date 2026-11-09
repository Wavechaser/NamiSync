# Latest session — table driver repair and projection tuning, 2026-11-09

## Delivered driver repair

Base `5081cc17`, branch `milestone1`. Product code is unchanged in this
checkpoint. The optional table-loading driver now observes `native.response`
after direct settlement, without restoring the removed clone. Drift refusal
covers all four assets; a bounded runtime test verifies actual bridge accounting.

Installed verification exposed a separate setup race. Inventory's local active
row preceded authoritative highlight adoption; the driver sent ArrowUp with
an old revision and correctly received a conflict. The pre-input wait now
requires authoritative focus and completed Inventory highlight adoption.
Targets, geometry, input timing and landing assertions are unchanged.

## Verification

- Focused tests: 45 passed. Final tools department: 427 passed, three existing
  Windows symlink-privilege skips, 6,104 deselected. Fixture checks passed.
- The existing instrumented bridge probe accounts for 125 window requests,
  zero pending, and complete response phases. Final installed Plan and Inventory
  probes both pass all 16 gestures with restored assets. Raw receipts are
  `install-02/plan-probe-03.json` and `install-02/inventory-probe-03.json`
  under `build/table-driver-fix-20261109/`.
- Failed sandbox/temp attempts, relative-output launch failure and both
  Inventory keyboard failures plus the command/frame trace are retained.
  Asset restoration is checked independently by hash; no measuring-session
  resources were used. This is diagnostic-driver correctness, not renewed
  timing acceptance. Pywebview may report its user-data-directory cleanup
  sharing warning; do not equate host exit with naturally empty browser jobs.

## Remaining authorized work

The user authorized modest memory/cold-projection tuning after this repair,
without changing public node contracts or budgets. A read-only census found
119,996 equal-but-distinct display/sort-key strings per reference fixture:
6,139,876 shallow bytes each. Test sharing these immutable strings before
considering more elaborate construction changes. The existing frozen-node
materialization microbenchmark remains only a candidate, not an end-to-end
speed result. Sparse-record redesign and combined tree/projection builders
remain excluded.

Evidence: `build/projection-tuning-20261109/` owns this session's census and
subsequent trials; `build/projection-investigation-20261109/` retains the
prior field/path census. PERFORMANCE owns measurements and their limits.
The previous 17.9 MiB path attribution was corrected in `5081cc17`: that bucket
contains existing node IDs. The fixed-slot increase does not decompose process
peak growth, and path sharing has negligible reference-fixture opportunity.
R3 acceptance and historical budgets remain unchanged.
