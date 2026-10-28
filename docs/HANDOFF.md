# Latest session — Item detail grouping, 2026-10-29

One presentation outcome on milestone1 from 2cf04ad2. Plan and Inventory item
details now use divider-separated blocks and 1:1.5 metadata columns. Plan keeps
action/reason/recording before full paths and metadata. Inventory files group
presence, path, checksum/result/combined recording, attested facts, observed
facts and dates. Folders omit observed size; the scope advisory is visible only
alongside eligible acknowledge/restore actions. Conditional exceptional evidence,
current/previous outcome identity, action scope and copyability remain intact.
No bridge, domain, persistence, selection or lifecycle changes.

## Verification

Evidence lives in build/gui-detail-groups-20261029/. Focused rendering probes
pass; gallery fixtures now assert the column ratio and divider presence, complete
paths/checksums and folder fact/advisory gating. Initial interfaces run passed
2,104 tests with one failure: new divider setAttribute calls violated the existing
packaged-asset sink guard. Replaced both with the established ariaHidden property;
the guard/allowlist remains unchanged. Corrected focused/static run passes 64.
An earlier sandboxed focused wheel build hit pip temporary-file permission
errors; the escalated rerun passed. All failed receipts are retained.

Initial nine installed checks passed. Final interfaces-r2 passes 2,105 tests.
Native-r2 passes eight cases; default Plan-shell stopped at the Plan Again stage
and passed unchanged in native-r3. The retained failure shows a fresh task row,
but does not establish the exact cause of the stage timeout. All nine final
installed cases are accounted for without relaxing assertions. Independent
source and correction review found no remaining issue. Gallery geometry checks
cover full-width paths/hashes, 1:1.5 columns and dividers in all display modes;
native captures were inspected with their existing transparent-surface limits.

No new worktree, recovery branch, push or PR. Inventory recents, queued-input
coordinator, M1-12, release and DOC-2 remain inactive.
