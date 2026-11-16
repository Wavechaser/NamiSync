# projection-tuning: retained claim support

## Adequacy supplement — 2026-11-17

Baseline is Git `c4fb6340`; source-package snapshots contain 303 files each.
The verification's variant deltas below identify the measured sharing and
unshipped descriptor trial independently of their matching output fingerprints.
Baseline values for every changed file and common verification inputs are kept.
Measurement-script identities identify historical tools, not new acceptance.

```json
{
 "input": "build/projection-tuning-20261109/verification.json",
 "sha256": "379d12b4b334b3e63aba04eaf9b10afc875162499ad933fe60edd55cec75a599",
 "package_files": 303,
 "baseline_changed_files": {
  "namisync/workflows/plan_projection.py": "379d4fec9b5976c33deb8f5b291f78e9a083602b9e9c031c02ebdc9170630e4f"
 },
 "variant_deltas": {
  "sharing": {
   "namisync/workflows/plan_projection.py": "13353f9a3699b0ce3fd04e4f1b1b013b55d1c5b8828abb5b7f6aaf7269304331"
  },
  "descriptor-trial": {
   "namisync/workflows/plan_projection.py": "b511db3733d2d52dd5c9b198721e017d4a3b1b68046f052cb7eb9df21663feed"
  }
 },
 "verification_inputs": {
  "tools/performance/plan.py": "75f1344b032738e322000201d227c5586073c32b365ae530d3f33d880cbda718",
  "tools/performance/_child.py": "54014e47c626d1da8c929782d9c3d3b622e103bc1d806b0ead2c5eca59b41977",
  "tests/interfaces/web/m1_7_plan_compact_contract.json": "396d07109f506fd7d4f52c23046719e4263c39353695303dd5b17db911bf34d0",
  "tests/interfaces/web/_headed_native.py": "a817439b1ac1b81f8635e3ce341551821fcb094fada85884e1e35a19c779f75c",
  "tests/test_plan_projection.py": "e29088a5d5d14aaad1322ee7696523ac6552317b3ea04d2185a897f450f2699b"
 },
 "producers": {
  "measure.py": "a12675fac64738374d168480b57ef327d34f331862702749c53af7e771eb5d58",
  "projection_diagnostic_child.py": "e117aa76e7b4bb390ea828f22ed76b2c017f645886fe84fa61de61b3b1d5a9d9",
  "extra_runs.py": "3e5d0c1de4d54179e4d896f999d1682f63150e62a9b1fedf325cdd18ae44ae14",
  "prepare_descriptor.py": "9709cb4fea30e780a45b6bbe8aab3eeb47ecb1942874bf5ab6c4fecc22188b2f",
  "verify.py": "1e4a79b35b8fbf8cd3802a42c2e9a113ad5afc66bf6ac7de54f1ae34c9acd61b"
 }
}
```
