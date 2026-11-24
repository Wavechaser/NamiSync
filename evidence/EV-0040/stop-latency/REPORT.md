# M2-A2 spike: Stop's cancel-to-release time

Written by the orchestrator from the builder's final report (subagents may not
write report files). Warm statistics recomputed from `samples_F_warm.json`
with `analyze.py`; they match.

Status: F: (NVMe) validated. J: (HDD) not run: the builder's J: write was
refused by its permission classifier; nothing exists on J:.

## Files

`harness.py` (gen, calibrate, run, cold), `analyze.py`, `scan_ms.json`,
`scan_ms_compute.json`, `calibration.json`, raw samples
`samples_F_warm.json` (90), `samples_F_cold.json` (18),
`samples_F_compute10k.json` (5), `samples_F_compute30k.json` (2), run logs,
regenerable fixtures (`fixture`, `fixture_s10`, `fixture_s30`) and `data_*`
isolated data roots.

## Identity and qualifications

CPython 3.13.17 / SQLite 3.50.4 (`.venv`; release interpreter is 3.15.2);
Windows 11 Pro 26200; F: WD_BLACK SN850X NVMe; revision `ab31ba08`, dirty
(other agents' tracked edits; the harness changed none). Not a quiet machine:
concurrent pytest runs and spikes, so tails are inflated. "Cold-ish" = fresh
Python process per sample with the OS metadata cache still warm; a truly cold
cache needs a reboot, dismount or admin standby flush (none done). The
scanner checkpoint was wrapped in-process to count checkpoints and stamp the
moment `Canceled` is raised.

## Seams

- Start: `NamiSyncService.start_inventory` (`namisync/interfaces/service.py:1589`),
  `start_plan` (`:908`); explicit paths via `NamiSyncService(ledger, history,
  settings_path=)` (`:345`); dispatcher composed at `:3036` with Windows named
  mutex custody (`dispatcher.py:266`, `custody.py` `default_lock_provider`).
- Cancel: `service.cancel` (`service.py:1823`) → `Dispatcher.cancel`
  (`dispatcher/dispatcher.py:766`).
- Scanner checks: `ctx.checkpoint()` per directory and entry
  (`modules/scanner.py` ~614, 815-841); plan scans `workflows/sync.py:394`,
  `:409`; inventory scan `workflows/inventory.py` ~2658.
- Terminal: `service.observe` (`service.py:1776`; `session_observer.py:278-332`).
- Custody release has no event or state. Measured directly on the custody
  primitive: mutex `Global\NamiSync.Resource.<sha256>` keyed by
  `volume:<serial>:<fs_type>` (replicates private `runtime.py`
  `_volume_resource_key`); a second thread waits on it. Each sample first
  proved custody held (0 ms wait times out): 108/108.
- `_settle` releases custody before publishing the terminal transition
  (`dispatcher.py` ~1520, `_release_custody` ~1602).

## Method

Seed 0x4E414D49; 100,000 files in 2,000 directories (depth ≤ 7, 0–512 B) plus
a 30,000-file target. Cases: inventory scan, plan source scan, plan target
scan, plan compute. Cancel delay 0.05–0.8 of calibrated scan time (inventory
7,100 ms, plan source 6,980 ms, plan target 2,170 ms); 9.5k–257k checkpoints
at cancel. `perf_counter_ns`.

## F: results (ms after cancel request, nearest rank; all CANCELED, valid)

Warm, n = 30 per case:

| case | scanner raises p50/p95/max | custody released p50/p95/max | Terminal p50/p95/max |
|---|---|---|---|
| inventory scan | 0.14 / 0.25 / 0.35 | 3.61 / 8.44 / 12.57 | 6.47 / 10.44 / 14.35 |
| plan source scan | 0.14 / 0.20 / 0.32 | 3.81 / 7.64 / 7.72 | 4.15 / 7.97 / 7.99 |
| plan target scan | 0.14 / 0.21 / 0.22 | 11.05 / 12.84 / 23.26 | 11.34 / 13.23 / 23.89 |

Cold-ish, n = 6 per case: custody maxima 10.2, 9.6, 15.2; Terminal maxima
13.1, 9.8, 15.5. `cancel()` ≈ 0.1 ms. Plan target ≈ 11 ms is probably
teardown of the 100k source scan (inference). Max checkpoint gap ≈ 20 ms on
inventory/source; the ≈ 120 ms on plan target spans the hand-off between the
two scans (harness artifact).

## Findings

1. Scan phase: custody released 1–25 ms after cancel on NVMe; the plan's
   "well under a second" holds there.
2. Planning cannot be stopped and keeps custody. After both scans return the
   session sits in CANCELING with the volume mutex held until planning and
   later phases finish, then ends `completed` with a plan. Plan compute: 9.6–
   9.9 s on 10k/3k trees, 41.0–41.7 s on 30k/9k (≈3x files → ≈4.2x time);
   100k/30k ran > 8 min during calibration without finishing (loaded machine).
   The plan entry's "does not use the scanned volumes" is true for I/O but
   custody is held, and Stop during planning returns COMPLETED.
3. Inventory: one cancel issued after its scan returned did not cancel; it
   completed ≈ 3.4 s later (one observation).

## J: HDD results (orchestrator, 2026-11-24, after user approval)

Fixture generated at `J:\NamiSyncSpike\stop-latency\fixture` (Ultrastar DC
HC550, SATA, disk 0): 130,001 files, 33,366,687 B payload, J: free-space delta
156,549,120 B, 80.9 s. Calibration (`calibration_J.json`): inventory 5,218 ms,
plan source 5,363 ms, plan target 1,681 ms (metadata cached: the fixture had
just been written). `samples_J_warm.json`, n = 30 per case, all CANCELED,
custody held before cancel in 90/90:

| case | scanner raises p50/p95/max | custody released p50/p95/max | Terminal p50/p95/max |
|---|---|---|---|
| inventory scan | 0.15 / 0.25 / 0.25 | 4.21 / 8.43 / 8.94 | 7.17 / 11.07 / 11.40 |
| plan source scan | 0.14 / 0.20 / 0.22 | 4.88 / 8.73 / 11.55 | 5.19 / 9.00 / 11.75 |
| plan target scan | 0.14 / 0.29 / 0.35 | 11.42 / 14.44 / 17.47 | 11.75 / 14.69 / 17.75 |

Warm HDD matches NVMe because enumeration is served from cached metadata. A
cold scan of a sleeping disk (where one blocking call can wait for the 8.3 s
spin-up measured in the volume spike) needs a reboot and was not run. The
fixture is kept on J: pending the user's decision.

## HDD run (commands as prepared)

Estimated fixture: 33.4 MB payload in 130,000 files; most files < 512 B are
MFT-resident, so roughly 0.15–0.3 GB on disk (measure the free-space delta).
Generation ≈ 40 s on NVMe; minutes on HDD.

```powershell
$d='build\m2-a2\stop-latency'
.venv\Scripts\python.exe $d\harness.py gen --fixture-root J:\NamiSyncSpike\stop-latency\fixture
.venv\Scripts\python.exe $d\harness.py calibrate --fixture-root J:\NamiSyncSpike\stop-latency\fixture --data-root $d\data_calibJ --out $d\calibration_J.json
# write measured scan ms to $d\scan_ms_J.json as {"inventory-scan":..,"plan-source-scan":..,"plan-target-scan":..}
.venv\Scripts\python.exe $d\harness.py run --fixture-root J:\NamiSyncSpike\stop-latency\fixture --data-root $d\data_warmJ --scan-ms $d\scan_ms_J.json --samples 30 --out $d\samples_J_warm.json
.venv\Scripts\python.exe $d\analyze.py $d\samples_J_warm.json
```

Calibration exits via `os._exit` because the plan session keeps planning
after its scans return. Only the first scan after a reboot is truly cold. Skip
plan compute on J: (CPU-bound). For the sleeping-drive case, spin the drive
down before the first sample and record it.
