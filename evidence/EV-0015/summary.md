# exec-time: retained claim support

## Adequacy supplement — 2026-11-17

PERFORMANCE attributes this exploratory source-host comparison to `7413a833`.
The corpus is 10,000 files at 32 bytes, with separate fresh H: targets and
Execute plus automatic Verify. It is neither an installed-release gate nor a
causal speed comparison. The unchanged GUI, headless, timer, GIL, throttling,
minimized and profiler arms remain distinct in data.json, in original batch
order. Failed trials are excluded from successful execution statistics and
remain listed as failures. The minimized out8 `min-00` outlier (177.4 seconds)
retains its core-placement observation below; sampled call shares are not CPU
time shares and do not establish cause. The script hashes are those of the
retained study inputs inspected at compaction, not a recovered per-trial freeze
manifest. Do not use them to claim source/runtime stability beyond the original
diagnostic's scope. No new acceptance is claimed.

```json
{
 "retained_instruments": {
  "gui.py": "5568427afeba868fd3bd51764be46beb005dd62c7ab773404110213151e1470c",
  "svc.py": "2931be096afb3940d600deafc98d37d1ef13ab56f044884686e258d0e21a6abb",
  "svc_t.py": "dd73eb4de6ad3126c74b9f8062d6dd49a3ce6f7fc5f53561b33db59b461a608b",
  "threadprobe.py": "a0d540222c1a3078ab88697109f95d4f53ef51568caf3189cf2f470a7220d339",
  "wrapper.py": "30650d3a87e46900057b29c10cb1e09414fdd42595d55fe76cf32b284365bb2b",
  "wrapper_si.py": "1cc2e07d4188eeeee436653241148c5e6d518633f70dae5e1bb6014caea38d3f",
  "wrapper_t.py": "8e8b7152a1b8f69aab1f22aa39173b34a05e3c1d715f3070b4109d7005df947d",
  "wrapper_linger.py": "922a9f6c56daf9f752102ddf802a80fb80f6ee5872aa88299bfae1c5efb4f1a2",
  "timers.py": "d1af240324e0f9be7353fcb30da3547ed360e159d20509a0b2701c2dc63b5253",
  "cores_report.py": "491f015e1b56a15f309099db6b5e858297a52e02f666d6e5a3bc8fdb5f608430"
 },
 "minimized_outlier": {
  "input": "build/exec-time-20261109/out8/runs/min-00/threads.jsonl",
  "sha256": "ecfcbafbf5ea1d8cdddd289fb0b74413ca60d912b22cbd81bf6e824edb453fbf",
  "sampled_calls": 4240,
  "efficiency_core_sampled_calls": 559
 }
}
```
