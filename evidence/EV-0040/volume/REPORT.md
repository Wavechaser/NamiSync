# M2-A2 spike: volume overview queries

Written by the orchestrator from the builder's final report (subagents may not
write report files); numbers spot-checked against `results.json`.

Files: `probe.py` → `results.json` (main probe), `summ.py` (table),
`power.py` → `power.json` (HDD power state), `unc.py` → `unc_isolated.jsonl`,
`unc_repeat.jsonl` (unreachable network path), `abandon.py` → `abandon.json`.
Runtime: `.venv` CPython 3.13.17, unelevated, zero-access handles only.

## 1. Elevation: not needed (high confidence)

Token: TokenElevation 0, TokenElevationType 3 (Limited), IsUserAnAdmin false.
On all 12 letters C–N, unelevated: GetLogicalDrives, GetDriveTypeW,
GetVolumeInformationW, GetDiskFreeSpaceExW / shutil.disk_usage, zero-access
CreateFileW on `\\.\X:`, IOCTL_STORAGE_QUERY_PROPERTY (device and seek
penalty), IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS. Zero-access
`\\.\PhysicalDriveN` also opens for all 12 disks.

Only K: (removable, no media) fails: path queries error 21 ERROR_NOT_READY;
seek-penalty IOCTL error 1 ERROR_INVALID_FUNCTION. It still answers
GetDriveTypeW (REMOVABLE), CreateFileW, the device property (USB, removable,
Sony MRW-S1) and disk extents (disk 10).

## 2. Spin-up of a sleeping HDD: not observable (user did not allow changing the disk timeout)

GetDevicePowerState on volume and PhysicalDrive handles for I: (disk 1) and J:
(disk 0): "on" before and after each of 8 queries (32 reads), never changed;
the disks were awake. Indirect: first calls in a fresh process on the HDDs took
0.003–0.056 ms, like SSDs, so answers come from memory while awake. This does
not exclude a wake from standby (first free-space read after mount may touch
the NTFS bitmap; GetDevicePowerState may not see firmware standby).

### 2a. Spin-up measured (orchestrator, 2026-11-24, user-approved elevated openSeaChest)

`spinup.ps1` (power-mode polling between spin-down and query) never saw
standby on M: (Barracuda LP on a USB bridge, disk 11) or J: (disk 0): no
Windows I/O on either disk in a 60 s counter sample, so the polling itself
woke them. `spinup2.ps1` then spun down, waited 45 s untouched, and timed
one query in a fresh process (`spin_query.py`), elevated, 1 repetition:

- J: standby check after 45 s: "PM2: Standby, Standby_z". Positive control
  (unbuffered 4 KiB read): 8,279 ms and 8,293 ms. Every overview query
  (GetLogicalDrives, GetDriveTypeW, GetVolumeInformationW,
  GetDiskFreeSpaceExW, zero-access CreateFileW, device property, seek
  penalty, disk extents, GetDevicePowerState): 0.013–0.091 ms. None waits
  for the platters.
- M: standby check after 45 s: Active/Idle; positive control 84 ms: the
  bridge did not keep the drive in standby, so USB is untested. M: reports
  IncursSeekPenalty true through its bridge.

Files: `spinup2-20261124T084325Z.jsonl` / `.raw.txt`; earlier polled runs
`spinup-*-*.jsonl`.

## 3. Per-drive deadline: recommend 3 s

Medians over 20 repetitions (ms): GetDriveTypeW 0.001; GetVolumeInformationW
0.009–0.024; GetDiskFreeSpaceExW / disk_usage 0.006–0.017; each IOCTL
0.003–0.005; open+device+seek+extents+close 0.015–0.020. Worst single call on
any drive with media 0.113 ms. K: path queries 1.32–1.49 ms (error 21).

"No disc": GetDriveTypeW REMOVABLE or CDROM and GetVolumeInformationW error 21.
A fixed disk returning error 21 should read "Not ready".

## 4. Unreachable network path: 13 s to 93+ s, not cancellable once blocked

`\\192.0.2.1\share\` (TEST-NET-1), one daemon thread per call with an outer
timeout:

| Call | Observed |
| --- | --- |
| GetDriveTypeW | blocked >30 s, >60 s, >120 s; once NO_ROOT_DIR after 92.6 s |
| GetVolumeInformationW | 41.5, 92.9, 39.6 s, error 64; once blocked >30 s |
| GetDiskFreeSpaceExW | 13.4, 92.7, 92.4 s, error 64; once blocked >60 s |

An abandoned worker keeps one thread for up to ~93 s, releases the GIL (200
local C: queries with three abandoned workers: median 0.035 ms, max 0.131 ms),
and as a daemon thread does not delay exit (1.09 s). Design consequences: use
daemon threads (a ThreadPoolExecutor worker is joined at exit); never start a
second query for a drive with an outstanding worker; a late result may replace
"Not responding". `unc_repeat.jsonl` ran parallel jobs that may share SMB
client state. CancelSynchronousIo was not tried. A real mapped drive (where
GetDriveTypeW normally returns REMOTE at once) was not tested: no mappings.

## 5. Disk type and bus

IncursSeekPenalty true on I: and J: (HDDs); false on all NVMe volumes and on
the USB SSDs L: and N:. BusType NVMe, SATA or USB. For USB devices the
vendor/product strings name the device or bridge (Samsung PSSD T7, SanDisk
SDDR-F451 reader, Realtek RTL9210 bridge), not the media. M: (SD card in a
reader) and the USB SSDs report DRIVE_FIXED, RemovableMedia false. Optical with
media, virtual, RAM-disk, Storage Spaces and spanning volumes not present.

## 6. Disk numbers (input to M2-A8)

| Drive | C | D | E | F | G | H | I | J | K | L | M | N |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Disk | 2 | 7 | 6 | 3 | 5 | 4 | 1 | 0 | 10 | 8 | 11 | 9 |

Every volume has one extent. No HDD on this machine carries two lettered
partitions, so A8's gate (two partitions of the HDD fixture serialize) has no
fixture yet.

## Rerun (from this folder)

```powershell
$py = '..\..\..\.venv\Scripts\python.exe'
& $py -I probe.py --reps 20 --unc-timeout 30
& $py -I summ.py
& $py power.py
foreach ($q in 'GetDriveTypeW','GetVolumeInformationW','GetDiskFreeSpaceExW') { & $py unc.py $q 120 }
& $py abandon.py
```
