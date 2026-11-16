# M1-9 Inventory projection and cold measurement — summary

Condensed from the builder and coordinator notes in `build/m1-9-20261001/`. The
committed tests, `docs/PERFORMANCE.md` (cold Inventory projection method) and
the validation committed under `tests/interfaces/web/` hold the method and
accepted numbers. This record keeps the outcomes, the corrections and the
limits.

## Outcomes

| Commit | Outcome |
| --- | --- |
| `ec3865c` | Inventory facts projected with shared sibling ordering. Plan sorting delegates to the same sorter, with no change to Plan callers, buckets or ties. |
| `12cae9b` | Cold Inventory projection limits verified (collector, fixture and separate checker). |
| `a84e816` | Bounded Inventory review reads exposed. |
| `687549a` | Bounded Inventory review pane on the desktop. |
| `9266845` | Inventory Refresh within its existing task. |

The projection keeps complete immutable rows, independent warning leaves,
exact current and attested evidence, domain indexes, complete-folder scope and
checked rollups. Warnings never enter domain scope or indexes.

## Important corrections

- **Real-row filename key** (independent review, P2). For canonical ancestors,
  `node_tree` chose one display spelling. After a scoped scan, that spelling
  could differ from a real row's retained spelling: a directory `ı` with child
  `I\child` and sibling `j` got filename key `i`. Real rows now take filename
  facts from `row.rel_path`; only synthetic ancestors use the tree path. The
  uncorrected regression failed once at the exact assertion. Afterwards:
  focused 160 passed, workflow department 894 passed.
- **Windows venv launch provenance.** The first coordinator collection
  (`…20261001T114855Z-e2acfce0`) failed its launch assertion. The venv
  redirector sits between collector and child, so requiring the collector as
  every child's parent was wrong. Popen now records the launched id. A direct
  child must have that id with the collector as parent. A redirector child must
  have the launched id as parent and a different id of its own. Process ids may
  be reused, and no cryptographic protection is claimed. Afterwards: native
  gate 1 passed, focused 23 passed.
- **Tools department environment failures.** In the first run, 64 failures
  came from corpus/CLI/executor cases that refuse temporary targets inside the
  repository, plus one execution-policy block on `tools/gui.ps1`. Neither was a
  product defect. A rerun with an external temp passed: 353 passed, 3 skipped.
- **Test-fixture errors** in the first projection test run (17 failed: a
  mis-unpacked helper and a nonexistent enum member) were corrected before
  review.

## Verification

- Projection: focused 159 passed; workflow department 893 passed. The fixture
  check confirmed correctness only, collecting no timings. Base has 120,000
  displayed rows; information-heavy has 240,000 (100,000 files, 20,000 synthetic
  folders, 120,000 warnings). Both have 700,000 known bytes.
- Bounded reads: 3,109 passed. Refresh: neighborhood 2,769 passed, native 79
  passed. Headed tree check: 1 passed.
- The R3 validation (`status: pass`, base maximum 1.623 s and information-heavy
  2.297 s against 3 s / 6 s) is committed as
  `tests/interfaces/web/r3_inventory_cold_20261109_validation.json`.

## Limits

- Pytest durations are correctness diagnostics, not cold-projection samples.
  Acceptance is the separate five-children-per-case collection under the
  reference profile only. It makes no universal latency or memory claim.
- The completed tree-headed witness produced no screenshots. Its six identity
  and host receipts were hash-checked when copied. External temp roots were
  inventoried by name only.
- The desktop-actions design note (2026-10-01) was a pre-implementation input
  for later work. It is superseded and not retained.
