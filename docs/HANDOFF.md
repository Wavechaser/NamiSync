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

Renderer fix `ea0daac2` and the separate native-host fix have distinct
witnesses. A controlled native crash captured the blocked pywebview return
worker and close-status stack in `build/dead-page-1441cbff/`. On the corrected
host the crash during a pending reply reached `shutdown.complete` and exit 0
(`build/dead-page-202f2869/namisync.log`). The host waited for actual worker
exit. That crash witness did not count surviving Job processes. A temporary
WebView2 profile cleanup warning was logged. All five crash-probe profiles
were subsequently removed. Host and bridge focused checks passed (169).

R3 remains open. Rebuild from the integrated fixes before running the resource
matrix, then assess the observed behavior. The original pilot drivers' fixed
yardsticks are historical. The pre-existing F: and H: pilot fixtures are
listed in `build/resource-baseline-20261106/pilot/fixtures.jsonl` and
`build/resource-baseline-20261106/fixtures.jsonl`. Verify their exact paths
and ownership before removal. R2 provenance, R4 and R5 remain open.
