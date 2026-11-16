# resource-studies: retained claim support

## Adequacy supplement — 2026-11-17

Both full schedules remain failure records, not acceptance passes. The following
identity extracts bind their package, host/source and collector/checker inputs.
The six-task memory observations are recomputed from complete Job samples using
the original `multi_summary.py` method: last 30 seconds of each named window,
independent medians for total and host private bytes. Forced-GC windows are
explicitly labeled; they are not normal collection behavior. Four tasks executed
and two stayed Plan-only. Phase durations include scheduling/admission waits;
the long concurrent Plan is not an isolated planner benchmark. This restores
the 1,260/764/660 MiB and approximately 285 MiB host observations without keeping
the sample series. No new performance gate or causal attribution is inferred.

```json
{
 "schedules": {
  "resource-study-20261106c": {
   "input": "build/resource-study-20261106c/full/collection.json",
   "sha256": "633275c43e1770f2fe9779fd157c139fd39b401f14427be214f58dddf149d480",
   "archive_sha256": "a4b1a042404d6a9abf69f16e9af6e47349acaefc31e8df7e28d4367f0320b98d",
   "host": {
    "platform": "Windows-11-10.0.26200-SP0",
    "processor": "Intel64 Family 6 Model 183 Stepping 1, GenuineIntel",
    "cpu_count": 24,
    "total_physical_bytes": 68388208640,
    "power_scheme": "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)",
    "git_head": "b6a4fefebb9504504920e1eb03edacd6da4d6cad",
    "git_status": ""
   },
   "tools": {
    "tools/performance/resources.py": "cbd1555a14c91c1a559194cf7453376bbedf65fe8f1db979e9f13b04d884169a",
    "tools/performance/_cdp.py": "d425def55f9e5f22af01aee4347958faa82642150fd66360db02df74b00e612c",
    "tests/interfaces/web/_headed_native.py": "a817439b1ac1b81f8635e3ce341551821fcb094fada85884e1e35a19c779f75c",
    "tests/interfaces/web/_headed_host_child.py": "7c1e38e41c26a86e8002ecde81ad56e534de847853c8732645b4121ee95d2513",
    "tools/performance/bridge_event/__init__.py": "aa05d9de23661fe0375af984cd0d829a23a658725bd6813dbcb6b7a1ef8be494",
    "tools/performance/validate_resources.py": "9325e164eb64ddf8f241dbb316b9c49eb611e730db12d2a6a249538df0f487d4"
   },
   "corpus": "F:\\NamiSyncExecutorBenchSource",
   "bundle_files": 434,
   "corpus_metadata_entries": 2
  },
  "resource-study-20261108": {
   "input": "build/resource-study-20261108/full/collection.json",
   "sha256": "f57c1606ed26ac0a809d0f4f7376261fd3c7c841067091cd9f8fc37a2155e0cb",
   "archive_sha256": "c14d1691ed8fde68d073c76c58ba2a29c9925c8817f537a5cb91dcc676a7c082",
   "host": {
    "platform": "Windows-11-10.0.26200-SP0",
    "processor": "Intel64 Family 6 Model 183 Stepping 1, GenuineIntel",
    "cpu_count": 24,
    "total_physical_bytes": 68388208640,
    "power_scheme": "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)",
    "git_head": "733f0cb1e78d048c196815b84e95758307c16f2c",
    "git_status": ""
   },
   "tools": {
    "tools/performance/resources.py": "cbd1555a14c91c1a559194cf7453376bbedf65fe8f1db979e9f13b04d884169a",
    "tools/performance/_cdp.py": "d425def55f9e5f22af01aee4347958faa82642150fd66360db02df74b00e612c",
    "tests/interfaces/web/_headed_native.py": "a817439b1ac1b81f8635e3ce341551821fcb094fada85884e1e35a19c779f75c",
    "tests/interfaces/web/_headed_host_child.py": "7c1e38e41c26a86e8002ecde81ad56e534de847853c8732645b4121ee95d2513",
    "tools/performance/bridge_event/__init__.py": "aa05d9de23661fe0375af984cd0d829a23a658725bd6813dbcb6b7a1ef8be494",
    "tools/performance/validate_resources.py": "9325e164eb64ddf8f241dbb316b9c49eb611e730db12d2a6a249538df0f487d4"
   },
   "corpus": "F:\\NamiSyncExecutorBenchSource",
   "bundle_files": 434,
   "corpus_metadata_entries": 2
  }
 },
 "multi_task": {
  "inputs": [
   {
    "input": "build/resource-study-20261106c/multi/runs/multi-02/samples.jsonl",
    "sha256": "827d7347740bd6a6dc8cd615846dd835856ecdaacd1619c1b95ab49d16e8de0f"
   },
   {
    "input": "build/resource-study-20261106c/multi/runs/multi-02/events.jsonl",
    "sha256": "952a581e0a0797e533c6187455049b42a110e8f0165183832f45d71dd8c21b5e"
   },
   {
    "input": "build/resource-study-20261106c/multi_summary.py",
    "sha256": "2df9a16f679d0ed7f6b41fe19d08fb9ea8d434c0998c56604eb566b0c6841459"
   }
  ],
  "windows": {
   "initial-idle": {
    "samples": 30,
    "median_private_mib": 360.47265625,
    "host_private_mib": 93.40625
   },
   "open-1T": {
    "samples": 30,
    "median_private_mib": 735.42578125,
    "host_private_mib": 175.45703125
   },
   "open-1T1P": {
    "samples": 30,
    "median_private_mib": 766.40625,
    "host_private_mib": 200.11328125
   },
   "open-2T1P": {
    "samples": 30,
    "median_private_mib": 1030.296875,
    "host_private_mib": 261.9921875
   },
   "open-2T2P": {
    "samples": 30,
    "median_private_mib": 1051.08203125,
    "host_private_mib": 284.61328125
   },
   "open-4T2P": {
    "samples": 30,
    "median_private_mib": 1260.45703125,
    "host_private_mib": 379.671875
   },
   "open-4T2P-gc": {
    "samples": 30,
    "median_private_mib": 764.453125,
    "host_private_mib": 379.734375
   },
   "closed-1": {
    "samples": 20,
    "median_private_mib": 741.259765625,
    "host_private_mib": 371.75
   },
   "closed-2": {
    "samples": 20,
    "median_private_mib": 713.44921875,
    "host_private_mib": 350.953125
   },
   "closed-3": {
    "samples": 20,
    "median_private_mib": 710.0078125,
    "host_private_mib": 339.078125
   },
   "closed-4": {
    "samples": 20,
    "median_private_mib": 692.8515625,
    "host_private_mib": 316.125
   },
   "closed-5": {
    "samples": 20,
    "median_private_mib": 679.96484375,
    "host_private_mib": 302.34765625
   },
   "closed-6": {
    "samples": 20,
    "median_private_mib": 659.73828125,
    "host_private_mib": 286.779296875
   },
   "final-idle": {
    "samples": 30,
    "median_private_mib": 657.75,
    "host_private_mib": 284.98828125
   },
   "final-gc": {
    "samples": 30,
    "median_private_mib": 648.32421875,
    "host_private_mib": 284.98828125
   }
  },
  "phase_seconds": {
   "t1-plan": 4.548,
   "t1-execute": 84.838,
   "t2-plan": 5.068,
   "t3-plan": 5.58,
   "t3-execute": 87.274,
   "t4-plan": 5.567,
   "t5-plan": 5.573,
   "t5-execute": 0.531,
   "t6-plan": 86.757,
   "t6-execute": 86.87
  }
 }
}
```
