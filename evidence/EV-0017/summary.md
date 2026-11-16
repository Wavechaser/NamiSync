# executor-simplification: retained claim support

## Adequacy supplement — 2026-11-17

Result 8 measured a dirty tree, not the base commit alone. These are the exact
changed product/rig/test and measurement-driver identities from its pre-run
receipt, with explicit post-run equality checks. Unchanged inputs are bound to
the recorded base plus the full mapping digest already retained in data.json.
No equivalence to a later integrated commit is asserted without a byte check.
Source-corpus stability is a metadata-manifest observation, not proof against
same-stat historical content replacement. The original timing vectors remain
in the comparison aggregates; detailed per-sample reports remain excluded.

```json
{
 "before": {
  "input": "build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-before.json",
  "sha256": "899eff86a26151012d5458f8782779e1e72c01524470bc2f50348f2362ae168f"
 },
 "after": {
  "input": "build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-after.json",
  "sha256": "7f834ffaea103de5a98e1410eab6355d43d9af451ebac1c170ad3d1ab1ca22b6"
 },
 "base": "b9c4ad3eced994e9958e8ad685e2450486284213",
 "changed_paths": [
  "namisync/core/evidence.py",
  "namisync/core/execution.py",
  "namisync/modules/executor/native.py",
  "namisync/modules/executor/pipeline.py",
  "namisync/modules/executor/runtime.py",
  "tests/test_executor_native.py",
  "tests/test_executor_pipeline.py",
  "tests/test_executor_runtime.py",
  "tests/test_tools_executor.py",
  "tests/test_tools_executor_settlement_audit.py",
  "tests/test_verifier_recorder_integration.py",
  "tools/executor_rig.py",
  "tools/executor_settlement_audit.py",
  "tools/executor_settlement_baseline.json"
 ],
 "delta_and_driver_sha256": {
  "build/executor-simplification-20260929/scripts/five_band_result8.ps1": "1b5a15348859d43e92579783a10e473149a925296366bd57868f3b45e40490ae",
  "build/executor-simplification-20260929/scripts/five_band_result8_receipt.py": "89034b8f901a6878f032419ee027ddcf905bdc350d17512ffbfa41092d18f38d",
  "namisync/core/evidence.py": "16464f191ceddcbca0d16420e9c27007b2d0ec6793f09aad30c484382d949c2c",
  "namisync/core/execution.py": "2dfc4e2ff2aa9783289f5e0d5672a3c94f08092af8b4ee23d655547c2392f58f",
  "namisync/modules/executor/native.py": "747c2d22aa557d5270f4774d7faff3537ba38bdb23d2138e5175b6637579fa98",
  "namisync/modules/executor/pipeline.py": "7f122bcd8ae66ba1246edbc25a3de7504a54303f1cca2dd0a242c5e64c348278",
  "namisync/modules/executor/runtime.py": "087a585650db09d3b8e91995e45e7b1ba895dc27dab250b768fc0a4976aaea73",
  "tests/test_executor_native.py": "f94a02eab9803a44bc11ffb7598c4a75ee02c0629e285877a2d395b9562c32fa",
  "tests/test_executor_pipeline.py": "c3d7c7c2967622e4824855a8127d4423d443424711d12a51527169f386f50b47",
  "tests/test_executor_runtime.py": "03d0040f4d0e1593318899ff92bae8b263ea9fdaf9410242cbad8188b59e984f",
  "tests/test_tools_executor.py": "375b3b871f26855bfa051d1d188e9ab70550638c53c5121daf1302f7d6ca2210",
  "tests/test_tools_executor_settlement_audit.py": "38a63affffcddf0ff9d02fe76f101b83f09aaac7d4912e2af3e4af09bb5eee1b",
  "tests/test_verifier_recorder_integration.py": "7da80fd1c468881319436e6296939df4a6a43eeb58313c7bd760e1221deaaaae",
  "tools/executor_rig.py": "14ecc9f46ac9bddf003c39087abd4558d396ad4378ad00a9c0719ff3ddc63a47",
  "tools/executor_settlement_audit.py": "2b2e20a85bb8ad234fa523cfbca211ea1739b51c585a9ad23af847b5ca88c48b",
  "tools/executor_settlement_baseline.json": "b6bbdf40f2d0bc7e038b983e12512fd8c524b425f7667e6acb7d4adfce7aac02"
 },
 "all_dependency_identities_equal": true,
 "source_metadata_equal": true,
 "source_matches_original_before_after": [
  true,
  true
 ],
 "original_manifest_sha256": "3664b8e9a6e6bceb05977cc9ef14afed387c79700dfc91721f5dfa7285142e97",
 "runtime": {
  "python": "3.13.14 (tags/v3.13.14:fd17997, Jun 10 2026, 13:03:48) [MSC v.1944 64 bit (AMD64)]",
  "platform": "Windows-11-10.0.26200-SP0",
  "xxhash": "3.8.1",
  "sqlite": "3.50.4"
 }
}
```
