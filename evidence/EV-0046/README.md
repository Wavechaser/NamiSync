# EV-0046: M2-A8 real inventory pairs on the reference disks (2026-11-27)

Gate record for [M2_PLAN](../../docs/M2_PLAN.md)'s M2-A8 row, for its clauses
"`J:` and `M:` never run together while two NVMe roots do" and "one real
inventory pair on `J:\NamiSyncSpike\stop-latency` and a seeded folder of at
most 64 MB on `M:`". Origin: `build/a8-evidence/` at `0c92160a`
(`milestone2`, clean tree; the product under test). Profile: the PERFORMANCE
reference machine, Windows 11 Pro 26200, CPython 3.13.17 from the development
`.venv` (not the release interpreter). No user database was opened: each run
used a fresh database pair in its own `build/` folder.

## Disks

As read by `namisync.core.disk_topology` during the runs:

| Root | Volume size | Disk | Bus type | Seek penalty | Counts as spinning |
| --- | --- | --- | --- | --- | --- |
| `J:` | 16.0 TB | 0, WDC WUH721816ALE6L4 (SATA HDD) | 11 (SATA) | yes | yes |
| `M:` | 4.3 GB | 0, same disk | 11 (SATA) | yes | yes |
| `C:` | 498 GB | 2, Samsung SSD 970 EVO Plus (NVMe) | 17 (NVMe) | no | no |
| `F:` | 4.0 TB | 3, WD_BLACK SN850X (NVMe) | 17 (NVMe) | no | no |

`J:` and `M:` are different volumes with different volume custody resources
(`84B7DB1C:NTFS`, `40BCC30B:NTFS`), so only the disk key can order them.

## Fixtures

| Root | Files | Bytes | Origin |
| --- | --- | --- | --- |
| `J:\NamiSyncSpike\stop-latency` | 130,001 in 2,603 folders | 33,366,687 | EV-0040's stop-latency fixture (its `fixture/manifest.json`, `src` seed 1312902473, `tgt` 1312902474); read only |
| `M:\NamiSyncA8` | 384 in 16 folders | 52,457,792 | `a8_pair.py seed M:\NamiSyncA8 384 4096 262144 20261127`; content digest `1aa8cda5…3e10`; kept in place |
| `F:` control, under `build/` | 8,000 in 16 folders | 18,466,954 | `seed … 8000 512 4096 20261128`; deleted after the runs |
| `C:` control, under `%TEMP%` | 8,000 in 16 folders | 18,148,491 | `seed … 8000 512 4096 20261129`; deleted after the runs |

The `J:` tree's listing digest (sorted relative path, size and mtime) was
`faca8a8e…8534` before and after every run.

## Method

`a8_pair.py` (SHA-256 `244FC3E0…876D`) opens one `NamiSyncService`, the
composition the desktop and CLI use, with all six registrations and the real
`read_disk_scheduling_keys`. The reader is wrapped only to time and log each
call. It calls `start_inventory(root_path=…)` for `J:` then `M:` back to back,
waits for both terminal results, then does the same for `F:` then `C:`. Times
are the dispatcher's own stored `created_at` (admission), `started_at`
(RUNNING) and `ended_at` (terminal) for each session. The overlap test uses
only these timestamps, with no barrier or injected delay. After the runs, each
captured checkpoint was read 20 more times. Three runs, one process each.

## Results

All 12 sessions completed with a complete inventory and no warnings (`J:`
132,604 rows, `M:` 400, each control 8,016; rows count folders too). Seconds are
from the first session's admission in its pair:

| Run | `M:` admitted | `J:` RUNNING → terminal | `M:` RUNNING → terminal | `F:` RUNNING → terminal | `C:` RUNNING → terminal |
| --- | --- | --- | --- | --- | --- |
| 1 | +0.047 | +0.030 → +13.062 | +13.064 → +13.113 | +0.007 → +0.854 | +0.030 → +1.041 |
| 2 | +0.046 | +0.027 → +12.905 | +12.906 → +12.952 | +0.007 → +0.913 | +0.030 → +1.091 |
| 3 | +0.046 | +0.027 → +12.805 | +12.806 → +12.852 | +0.008 → +0.856 | +0.031 → +1.026 |

- **`J:` and `M:`:** serialized in 3 of 3 runs. `M:` was admitted while `J:`
  was running and entered RUNNING 1 to 2 ms after `J:`'s terminal transition.
- **NVMe control:** overlapped in 3 of 3 runs. `C:` entered RUNNING before `F:`
  was terminal.

Keys and read times, in microseconds:

| Root | Keys | In-session reads | 20 repeat reads, median / max |
| --- | --- | --- | --- |
| `J:` | `("disk", 0)` | 446, 445, 594 | 88 to 94 / 291 to 300 |
| `M:` | `("disk", 0)` | two per run: 452 and 901, 625 and 761, 529 and 797 | 88 to 91 / 166 to 185 |
| `F:` | none | 364, 361, 350 | 88 to 92 / 107 to 194 |
| `C:` | none | 334, 341, 311 | 86 to 90 / 105 to 195 |

`M:` was read twice per run, consistent with one read while it waited behind
`J:` and a fresh one at its launch.

## Gate

| Gate clause | Verdict |
| --- | --- |
| `J:` and `M:` never run together; two NVMe roots do | Met through real reads and the real service, 3 of 3 runs |
| Injected unreadable read falls back | Not covered here; `tests/test_disk_scheduling.py::test_reference_disks_serialize_hdd_partitions_and_overlap_nvme_roots` |
| One real inventory pair on `J:\NamiSyncSpike\stop-latency` and `M:` (≤ 64 MB) | Met; `M:` holds 52.5 MB |
| Ordinary suite and `lint-imports` | 7557 passed, 8 failed, 4 skipped, 36 deselected in 430 s; `lint-imports` 13 kept, 0 broken |

Seven failures are the known interpreter-bound ones: six
`test_bridge_transport_custody*` tests and
`test_native_host_gate_page_keeps_the_probe_in_inert_page_data`. The eighth,
`tests/test_tools_evidence.py::test_real_evidence_tree_is_valid`, failed
because this record was still unsealed during the run; it passed after
sealing.

## Limits

- No speed claim; durations above only show the order of events.
- Warm disk: `J:` was enumerated just before the runs. A cold or spun-down
  disk was not tested.
- One process. Cross-process serialization is a non-goal.
- The overlap of the NVMe pair depends on timing and was not forced. It held
  in each run by over 0.8 s.

## Rerun

Copy `a8_pair.py` to a folder two levels below the repository, such as
`build/a8-evidence/`; it finds the repository as its third parent. Seed the
fixtures with the commands above, then run
`a8_pair.py run OUTDIR J:\NamiSyncSpike\stop-latency M:\NamiSyncA8 F_ROOT C_ROOT`
with the project venv. It writes `OUTDIR/run.json`.
