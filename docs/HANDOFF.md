# Latest session — Resource pilot defect fixes, 2026-11-06

Branch `milestone1`. Commit `edd02012` preserves the original pilot tools,
reports and handoff. The user requested fixes to the two reported defects.

The renderer now separates event delivery from repaint and preserves stable
committed Plan rows across a background refresh. The two final diagnostic
runs, using the original build-d host with only the two corrected frontend
assets substituted, verified 1,000 and 10,000 files by hash. Both exited
normally. See [PERFORMANCE](PERFORMANCE.md) for original and fixed peaks,
method and limitations. Raw events, process samples, asset hashes and cleanup
receipts are in `build/render-fix-20261106/`. The comparison targets,
package extracts and profiles were removed. No supplied corpus files were used.

The separate shutdown fix addresses an in-flight pywebview return after the
renderer dies. The pilot's original log did not identify the blocked worker.
A controlled native crash at the same seam captured its stack and the
close-status stack in `build/dead-page-1441cbff/`. Keep shutdown verification
and integration separate from the two renderer-only comparisons.

R3 remains open. Rebuild from the integrated fixes before running the resource
matrix, then assess the observed behavior. The original pilot drivers' fixed
yardsticks are historical. The pre-existing F: and H: pilot fixtures are
listed in `build/resource-baseline-20261106/pilot/fixtures.jsonl` and
`build/resource-baseline-20261106/fixtures.jsonl`. Verify their exact paths
and ownership before removal. R2 provenance, R4 and R5 remain open.
