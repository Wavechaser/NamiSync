# executor-assessment: retained claim support

## Adequacy supplement — 2026-11-17

The initial foreground timing bands remain unchanged. These additional aggregates
restore verifier read/tap controls and instrumented root/admission attribution.
Nested stage spans overlap and include instrumentation cost; do not sum them into
a wall-time partition or interpret them as uninstrumented speedups. Source is
`0e4595e4142fc78cfbf8e274832520a4344f3b5e`; runtime/dependencies/host remain in
notes.md and data.json. These reports use XXH3; tap/no-tap are separate modes.
No null-hasher measurement survives in this source folder, so it is a rerun
control recipe, not a retained observation. The original verifier audit reported 8 invocations / 30 samples
and 148 focused passes; the aggregates below independently check recording and
verified populations from those reports. No raw sample or per-test ledger is kept.

```json
{
 "verifier": {
  "verifier-1000x4KiB.json": {
   "input": "build/executor-assessment-20260927/verifier-1000x4KiB.json",
   "sha256": "c4640c74ad98a7492ed2a519da893202036aa46549a8a797f5d16cd752f8c510",
   "configuration": {
    "baselines": "primed",
    "chunk_size": 4194304,
    "hasher": "xxh3_128",
    "mode": "verify",
    "repeat": 5,
    "root": "F:\\NamiSyncExecutorBenchSource\\1000x4KiB",
    "sidecar": null,
    "tapped": true
   },
   "summary": {
    "n": 5,
    "seconds": {
     "maximum": 3.771726,
     "median": 3.652458,
     "minimum": 3.574651
    },
    "throughput_mib_s": {
     "median": 1.069
    }
   },
   "all_recording_ok": true,
   "all_verified": true,
   "open_seconds_median": 1.5748174991458654,
   "read_seconds_median": 0.7319644997478463
  },
  "verifier-1x4GiB.json": {
   "input": "build/executor-assessment-20260927/verifier-1x4GiB.json",
   "sha256": "ae73bba02f1416ec883f91ce751a958f1fbdc38655971985103a069a36e278fb",
   "configuration": {
    "baselines": "primed",
    "chunk_size": 4194304,
    "hasher": "xxh3_128",
    "mode": "verify",
    "repeat": 5,
    "root": "F:\\NamiSyncExecutorBenchSource\\1x4GiB",
    "sidecar": null,
    "tapped": true
   },
   "summary": {
    "n": 5,
    "seconds": {
     "maximum": 1.956233,
     "median": 1.926348,
     "minimum": 1.862475
    },
    "throughput_mib_s": {
     "median": 2126.303
    }
   },
   "all_recording_ok": true,
   "all_verified": true,
   "open_seconds_median": 0.0013547000125981867,
   "read_seconds_median": 1.4858171002124436
  },
  "verifier-4x128MiB.json": {
   "input": "build/executor-assessment-20260927/verifier-4x128MiB.json",
   "sha256": "ae278555d08696ee2fa14119af4a02612e850a397acd93bd6f748b7f6e58384e",
   "configuration": {
    "baselines": "primed",
    "chunk_size": 4194304,
    "hasher": "xxh3_128",
    "mode": "verify",
    "repeat": 5,
    "root": "F:\\NamiSyncExecutorBenchSource\\4x128MiB",
    "sidecar": null,
    "tapped": true
   },
   "summary": {
    "n": 5,
    "seconds": {
     "maximum": 0.246438,
     "median": 0.237032,
     "minimum": 0.236316
    },
    "throughput_mib_s": {
     "median": 2160.046
    }
   },
   "all_recording_ok": true,
   "all_verified": true,
   "open_seconds_median": 0.005331400025170296,
   "read_seconds_median": 0.17911070014815778
  },
  "verifier-512x128KiB.json": {
   "input": "build/executor-assessment-20260927/verifier-512x128KiB.json",
   "sha256": "7db959dba7330e9a83bf25c23e97c5b2be8ad86f13adc65c5e6eae026d05c502",
   "configuration": {
    "baselines": "primed",
    "chunk_size": 4194304,
    "hasher": "xxh3_128",
    "mode": "verify",
    "repeat": 5,
    "root": "F:\\NamiSyncExecutorBenchSource\\512x128KiB",
    "sidecar": null,
    "tapped": true
   },
   "summary": {
    "n": 5,
    "seconds": {
     "maximum": 2.024646,
     "median": 1.912649,
     "minimum": 1.836528
    },
    "throughput_mib_s": {
     "median": 33.461
    }
   },
   "all_recording_ok": true,
   "all_verified": true,
   "open_seconds_median": 0.8078586000483483,
   "read_seconds_median": 0.4046313010621816
  },
  "verifier-64x4MiB.json": {
   "input": "build/executor-assessment-20260927/verifier-64x4MiB.json",
   "sha256": "b3b3781ef347235580dc0ca86ee819c77c86fe0cc954ec0ca6c788b2b0366965",
   "configuration": {
    "baselines": "primed",
    "chunk_size": 4194304,
    "hasher": "xxh3_128",
    "mode": "verify",
    "repeat": 5,
    "root": "F:\\NamiSyncExecutorBenchSource\\64x4MiB",
    "sidecar": null,
    "tapped": true
   },
   "summary": {
    "n": 5,
    "seconds": {
     "maximum": 0.317162,
     "median": 0.311207,
     "minimum": 0.306913
    },
    "throughput_mib_s": {
     "median": 822.604
    }
   },
   "all_recording_ok": true,
   "all_verified": true,
   "open_seconds_median": 0.08354190009413287,
   "read_seconds_median": 0.12653249956201762
  },
  "verifier-large-instrumented.json": {
   "input": "build/executor-assessment-20260927/verifier-large-instrumented.json",
   "sha256": "bdb3ac71d4d64fdbd810e098f80d4be58f58b0287dc0e2c551ffb26b7f5e4fe4",
   "configuration": {
    "baselines": "primed",
    "chunk_size": 4194304,
    "hasher": "xxh3_128",
    "mode": "verify",
    "repeat": 1,
    "root": "F:\\NamiSyncExecutorBenchSource\\1x4GiB",
    "sidecar": null,
    "tapped": true
   },
   "summary": {
    "n": 1,
    "seconds": {
     "maximum": 2.008474,
     "median": 2.008474,
     "minimum": 2.008474
    },
    "throughput_mib_s": {
     "median": 2039.359
    }
   },
   "all_recording_ok": true,
   "all_verified": true,
   "open_seconds_median": 0.001294099958613515,
   "read_seconds_median": 1.5942224992904812
  },
  "verifier-small-instrumented.json": {
   "input": "build/executor-assessment-20260927/verifier-small-instrumented.json",
   "sha256": "3727c80c0ff514c5a0f03365cdf778cfd47ce7ae12c4968cb43e196c96a60462",
   "configuration": {
    "baselines": "primed",
    "chunk_size": 4194304,
    "hasher": "xxh3_128",
    "mode": "verify",
    "repeat": 1,
    "root": "F:\\NamiSyncExecutorBenchSource\\1000x4KiB",
    "sidecar": null,
    "tapped": true
   },
   "summary": {
    "n": 1,
    "seconds": {
     "maximum": 3.195918,
     "median": 3.195918,
     "minimum": 3.195918
    },
    "throughput_mib_s": {
     "median": 1.222
    }
   },
   "all_recording_ok": true,
   "all_verified": true,
   "open_seconds_median": 1.3615919990697876,
   "read_seconds_median": 0.6575501004117541
  },
  "verifier-small-no-tap.json": {
   "input": "build/executor-assessment-20260927/verifier-small-no-tap.json",
   "sha256": "5f86bc998c4d523785a6e5c60c34352e2059c71d2fa98be05bf3b4dddb516e17",
   "configuration": {
    "baselines": "primed",
    "chunk_size": 4194304,
    "hasher": "xxh3_128",
    "mode": "verify",
    "repeat": 3,
    "root": "F:\\NamiSyncExecutorBenchSource\\1000x4KiB",
    "sidecar": null,
    "tapped": false
   },
   "summary": {
    "n": 3,
    "seconds": {
     "maximum": 3.337029,
     "median": 3.286997,
     "minimum": 3.281786
    },
    "throughput_mib_s": {
     "median": 1.188
    }
   },
   "all_recording_ok": true,
   "all_verified": true,
   "open_seconds_median": 0,
   "read_seconds_median": 0
  }
 },
 "instrumented_stages": {
  "stages-1000x4KiB-stages.json": {
   "input": "build/executor-assessment-20260927/stages-1000x4KiB-stages.json",
   "sha256": "96a915df4d922e2adeaf06cfd307bb3d2fde435f9524325030397b8f41c34e14",
   "scope": null,
   "columns": [
    "calls",
    "inclusive_seconds",
    "exclusive_seconds"
   ],
   "rows": {
    "runtime._target_root_authority": [
     7000,
     0.33393079874804243,
     0.33393079874804243
    ],
    "runtime._require_reviewed_runtime_root": [
     14000,
     0.36172030569287017,
     0.36172030569287017
    ],
    "native._observe_root_anchor": [
     28000,
     6.398065198329277,
     6.398065198329277
    ],
    "native._observe_root_component": [
     38000,
     3.5158945043222047,
     1.6818686076439917
    ],
    "native._observe_root_volume": [
     20000,
     5.564388801052701,
     5.564388801052701
    ],
    "native.revalidate_root": [
     27000,
     16.83254620624939,
     3.5530939017771743
    ],
    "runtime._revalidate_target_root": [
     7000,
     4.211009201535489,
     0.04075570061104372
    ],
    "runtime._source_root_authority": [
     7000,
     0.36855469847796485,
     0.36855469847796485
    ],
    "runtime._revalidate_source_root": [
     7000,
     8.24718570098048,
     0.04430089727975428
    ],
    "native._volume_id": [
     6000,
     2.0736889023683034,
     0.013306802837178111
    ],
    "native._stat_path": [
     9000,
     3.004636600438971,
     0.6174142973613925
    ],
    "native.stat_path": [
     8000,
     2.713711899530608,
     0.009868900058791041
    ],
    "native.stat": [
     6000,
     7.041116697888356,
     0.016625598829705268
    ],
    "native._stat_handle": [
     1000,
     0.033636999723967165,
     0.033636999723967165
    ],
    "runtime._require_stat_path": [
     1000,
     0.36797250021481887,
     0.0008598996791988611
    ],
    "runtime._stat_target_path": [
     1000,
     1.5892527991672978,
     0.0024510998046025634
    ],
    "runtime._guard_path_stat": [
     1000,
     0.0013388993102125823,
     0.0007884001242928207
    ],
    "runtime._profiled_stat": [
     1000,
     0.00043739972170442343,
     0.00043739972170442343
    ],
    "runtime._published_copy_stat": [
     1000,
     1.5764433987787925,
     0.004583297355566174
    ],
    "runtime._guard_attestation_size": [
     2000,
     0.0009217003243975341,
     0.0009217003243975341
    ],
    "runtime._attestation": [
     1000,
     0.016155600547790527,
     0.015820800501387566
    ],
    "runtime._execute_operation": [
     1000,
     27.85664800001541,
     0.0038122994010336697
    ],
    "execute": [
     1,
     27.90129790001083,
     0.006170298962388188
    ]
   }
  },
  "verifier-small-stages.json": {
   "input": "build/executor-assessment-20260927/verifier-small-stages.json",
   "sha256": "62a686dc4714c23a6e583df80867727713987b908a200ccc69e02c52e8430160",
   "scope": "verify calls only; priming, scans and authority setup excluded",
   "columns": [
    "calls",
    "inclusive_seconds",
    "exclusive_seconds"
   ],
   "rows": {
    "engine._require_selected_root": [
     2000,
     0.06629679939942434,
     0.06629679939942434
    ],
    "api.GetVolumePathNameW": [
     4000,
     1.1565699000493623,
     1.1565699000493623
    ],
    "root.current_volume_anchor": [
     2000,
     0.7488167998963036,
     0.1582652991055511
    ],
    "root._native_lstat": [
     2000,
     0.09637519827811047,
     0.09637519827811047
    ],
    "root.admit_root_chain": [
     2000,
     1.0791718005784787,
     0.13775740255368873
    ],
    "api.GetVolumeInformationW": [
     1000,
     0.02346850006142631,
     0.02346850006142631
    ],
    "root.observe_native_volume": [
     1000,
     0.39856200059875846,
     0.10113530000671744
    ],
    "root.admit_root": [
     1000,
     0.980033399653621,
     0.019186698831617832
    ],
    "engine._admit_verification_root": [
     1000,
     1.0072396998293698,
     0.0018688004929572344
    ],
    "native._verification_lstat": [
     3000,
     0.1544401003047824,
     0.1544401003047824
    ],
    "native.api.stat": [
     4000,
     0.07856940507190302,
     0.04441780521301553
    ],
    "engine._require_reviewed_open_volume": [
     1000,
     0.0005518989055417478,
     0.0005518989055417478
    ],
    "api.ReadFile": [
     1000,
     0.5208972004475072,
     0.5208972004475072
    ],
    "verify": [
     1,
     3.1959086999995634,
     0.12833949271589518
    ]
   }
  },
  "verifier-large-stages.json": {
   "input": "build/executor-assessment-20260927/verifier-large-stages.json",
   "sha256": "4047d220fe5793b4ff8f9c5026eaad5801bc78ad0e4bf165b2d5e4c59ad03e57",
   "scope": "verify calls only; priming, scans and authority setup excluded",
   "columns": [
    "calls",
    "inclusive_seconds",
    "exclusive_seconds"
   ],
   "rows": {
    "engine._require_selected_root": [
     2,
     5.2900053560733795e-05,
     5.2900053560733795e-05
    ],
    "api.GetVolumePathNameW": [
     4,
     0.001055500004440546,
     0.001055500004440546
    ],
    "root.current_volume_anchor": [
     2,
     0.000678999989759177,
     0.00014409999130293727
    ],
    "root._native_lstat": [
     2,
     8.279993198812008e-05,
     8.279993198812008e-05
    ],
    "root.admit_root_chain": [
     2,
     0.0009707999997772276,
     0.00012470007641240954
    ],
    "api.GetVolumeInformationW": [
     1,
     2.3900007363408804e-05,
     2.3900007363408804e-05
    ],
    "root.observe_native_volume": [
     1,
     0.00037480000173673034,
     9.34000127017498e-05
    ],
    "root.admit_root": [
     1,
     0.0008641000022180378,
     2.1299987565726042e-05
    ],
    "engine._admit_verification_root": [
     1,
     0.0008898999658413231,
     3.2999087125062943e-06
    ],
    "native._verification_lstat": [
     3,
     0.00013529998250305653,
     0.00013529998250305653
    ],
    "native.api.stat": [
     4,
     0.00011180003639310598,
     6.940000457689166e-05
    ],
    "engine._require_reviewed_open_volume": [
     1,
     1.300009898841381e-06,
     1.300009898841381e-06
    ],
    "api.ReadFile": [
     1024,
     0.8376063005998731,
     0.8376063005998731
    ],
    "verify": [
     1,
     2.0084663999732584,
     1.1627125000813976
    ]
   }
  }
 },
 "instruments": {
  "diagnostic.py": "1adc1fd86e62bbd98c47447b180f5ac7efed6a3ce840d13f824a75357de39624",
  "verifier_diagnostic.py": "a545be9385cef1025db3e411648eb2b8c93569d5820131d8ba40f28d50a6fc54",
  "verifier_audit.py": "30b5480088b1532ca4d208c51827dc800551f271ae74f45b65521d49485fcc62",
  "baseline.ps1": "048e062c5c5569e959a38db0ce380a9bdf40f564c9320ccf980169e457a9fb49",
  "verifier_baseline.ps1": "1d795e72d8523ae98398a95e452ea484b70a722d6e373b0df2e68ef7e84b9daa"
 }
}
```
