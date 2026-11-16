# copyonly: retained claim support

## Adequacy supplement — 2026-11-17

This is a 1,000-file F:→H: exploratory comparison. `historical` and `current`
are the study's original snapshot labels, not today's HEAD. The fields below
record whether those snapshots still exist; both were already removed before
this correction. No revision or source hash is invented. Profiled, rig and plain
service cases stay separate in data.json. GUI statistics pool hidden, visible
and delayed variants and are descriptive ranges, not a controlled comparison;
the six run names retain that qualification. They establish no throughput gain
or verification-concurrency benefit. A new comparison requires a new frozen
source/runtime profile; these observations are diagnostic history only.

```json
{
 "snapshots": {
  "historical": {
   "retained": false,
   "limitation": "Original source snapshot was removed before this correction; no exact revision or source freeze recovered."
  },
  "current": {
   "retained": false,
   "limitation": "Original source snapshot was removed before this correction; no exact revision or source freeze recovered."
  }
 },
 "instruments": {
  "bench.py": "0900c6b4da110bda6edb617ca73a7066537c5df0dad913437a2be64af2c45878",
  "instrumentation.py": "01e976bb7ea45a3de91482a97d8ade63398eabbc5947c1caadacfa9840520359",
  "gui_timing.py": "a56cf2a2d9369fff3509b7b8bb44fb02d0501c8525355d6ae549ab81398680fb",
  "run.ps1": "0eea09dabb6818124b94183e3eb08d4b2a4fa75df2107e40d84716bea4fc32e8"
 }
}
```
