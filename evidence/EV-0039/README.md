# Measurement receipts moved out of tests/interfaces/web (2026-11-23)

Compacted from 18 measurement JSON files (1.6 MiB) committed under
`tests/interfaces/web/`, each unchanged on `main` at `7b2b014f`; promoted
2026-11-23.
The frozen `sh_g_8_*` transport custody files stay there because tests read
them. The Plan measurement contract moved unchanged to
`tools/performance/plan_contract.json`; the Plan fixture manifests the tests
compare against moved to `tests/assets/plan_fixture_manifests.json`.

## Contents

Copied unchanged, so each recorded hash still matches its file:

- `r3_inventory_cold_20261109_{raw,validation}.json` and
  `r3_br_g_42_validation_20261109.json`: the R3 acceptance collection on
  `cbb07d5f` (CPython 3.13.17).
- `r3_inventory_cold_20261110_{raw,validation}.json` and
  `r3_br_g_42_validation_20261110.json`: the renewed release collection on
  `cfeac2d9` (CPython 3.15.2).
- `m1_8_execution_receipt_result.json` (P2, `4bbf943`) and
  `m1_8_execution_ui_result.json` (U-v2, `3ea4e6b`): the metric summaries.

Each Inventory validation's `raw_sha256` names its raw file. Each M1-8
result's `receipts_sha256` names the retired receipts file below.

## Retired to Git

These files carried per-child fixture records and receipts whose results
[PERFORMANCE](../../docs/PERFORMANCE.md) already holds. Restore one with
`git restore --source=<commit> -- tests/interfaces/web/<file>`; the checked-out
bytes match the SHA-256.

| File | Commit | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `m1_7_plan_compact_authority.json` | `7cf44489` | 48,679 | `ec8b2cf4687dbd08349f3c0fd103a70739e9198c3c9d28059048cc7bdec0f945` |
| `m1_7_plan_compact_measurements.json` | `d1ce79d5` | 565,933 | `e5718367c4f386e5845b93b7de484176228504b8382d0f6d5c0a1317d862665d` |
| `m1_8_execution_receipt_authority.json` | `4bbf9436` | 51,897 | `541a2bf7016977aca1cafe0556b8c38fec1f93850de6b584676f2ad76c4af7b7` |
| `m1_8_execution_receipt_receipts.json` | `4bbf9436` | 121,059 | `24d3a32f30d01844b775f849ced3d52371268af5d42e0491063d367a762ff57e` |
| `m1_8_execution_ui_authority.json` | `3ea4e6b1` | 52,512 | `8c7a88be79ee765de3f00bfc7267650846a2100bded9d386b2bfc55b4013dd17` |
| `m1_8_execution_ui_receipts.json` | `3ea4e6b1` | 697,100 | `14871ad13282b8f5567a34d104eda6c3ca64d734491e546feda03e814c088b67` |
| `m1_9_inventory_cold_raw.json` | `12cae9bc` | 31,913 | `16f09630910065e6d1f3e6802e2013083aed66b367b7efd2845ad71f3cbf5bdc` |
| `m1_9_inventory_cold_validation.json` | `12cae9bc` | 411 | `37ceb9a20319b398f2fe2537efa2c47a653605cbac7c6934179c08bef0414d27` |
| `m1_closeout_inventory_cold_20261030_raw.json` | `9dd384ae` | 31,101 | `ffb24fd99ef03db0f7b21b5bd2f269635de48ed2e5f2ac0a059e3d3e2aca9628` |
| `m1_closeout_inventory_cold_20261030_validation.json` | `9dd384ae` | 411 | `d964f62dccc9ecb4c9c863133d0a55bd0391a18becdf32399d7090c9838809c1` |

The M1-7 measurements' `contract_sha256` is the SHA-256 of the contract's
canonical JSON (sorted keys, compact separators, UTF-8), not of its file bytes.

## Not retained

The rejected pre-compaction M1-7 contract, authority and measurements were
deleted without promotion. They were introduced at `ae3daf67`, are unchanged
on `main` at `7b2b014f`, and the archived M1-7 ablation study records their
rejection.
