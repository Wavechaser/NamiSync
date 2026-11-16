# AB-2/AB-10 incident trace (2026-09-27)

Compacted from the working folders `build/incident-trace-20260927`, `build/trace-20260927/` (122 files, 2.9 MiB); promoted 2026-11-17.

## Contents

Findings with each incident's remaining uncertainty, the evidence summary, verification, event extracts, the native trace reproducer and the Plan Again mapping scripts cited by TESTS, and both 60-iteration Setup traces as aggregates.

`notes.md` concatenates 6 text file(s) verbatim:

- `build/incident-trace-20260927/findings.md`
- `build/incident-trace-20260927/native_trace.py`
- `build/trace-20260927/scripts/plan-again/map_base_lines_9_490.py`
- `build/trace-20260927/scripts/plan-again/map_line_411_variants.py`
- `build/trace-20260927/scripts/plan-again/notice_position.py`
- `build/trace-20260927/scripts/plan-again/order_base_checkpoints.py`

`data.json` holds 5 JSON entries, keyed by source path with the original size and SHA-256 (derived entries name their inputs' hashes). Identical files point at the first copy with `same_as`.

- `build/incident-trace-20260927/evidence-summary.json`: The 22 copied receipt/log hash records replaced by their count and a hash; revision, input hashes, the sample-validator red/control pair and both bridge incident summaries kept.
- `build/incident-trace-20260927/report-verification.json`
- `build/incident-trace-20260927/windows-events.json`
- `build/trace-20260927/setup-trace-60.json`: The per-iteration trace aggregated: iteration count, iterations with failures, stuck drains, drain errors and captures, distinct session-state sets and whether every shutdown completed; any failing iteration kept whole.
- `build/trace-20260927/setup-trace-noise-60.json`: The per-iteration trace aggregated: iteration count, iterations with failures, stuck drains, drain errors and captures, distinct session-state sets and whether every shutdown completed; any failing iteration kept whole.

## Not retained

The AB-2 helper diffs (findings record their conclusion: mechanisms unchanged, prior code presence only), the 22 copied receipt hash records (hashed), per-iteration trace rows, raw bridge-event dumps (660-720 KiB each), incomplete raw trees and native per-run evidence. Per-run inputs/after snapshots, exit codes, logs and pytest XML, raw/asset/install/cache/temp trees, candidate/baseline source copies and patches, and per-run reports already summarized above.
