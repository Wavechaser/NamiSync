# Root admission optimization (RO), 2026-09-28 – 09-29 — summary

Condensed from the user-adjudicated handoff, the core review binding and the
17 independent per-outcome reviews under
`build/root-admission-optimization-20260928/`. EXECUTOR, PREFLIGHT, VERIFIER,
CORE and DEFENSE hold the resulting contracts. PERFORMANCE holds the
measurement method and its qualified conclusions. AGENTS states the
`RootAuthority` hold rule.

## Fixed gate every outcome passed

Each outcome below passed the following before its commit:

- focused and direct-consumer runs (direct: 574 passed, 2 symlink-privilege
  skips for executor outcomes);
- the ordinary suite (5,410 at baseline, rising to 5,611 by the last outcome,
  with 4 skips and 34 headed deselections);
- 12 import contracts;
- the unchanged settlement oracle, 30 scenarios × 3 runs;
- a guard scan: 70 rows, 391 effects, zero missing admissions;
- byte-identical gate input/output manifests;
- a qualified differential: 67 full comparison groups (46 before the executor
  groups were added) with no unexpected differences. Held-window renames were
  blocked with WinError 32 and compared against full unswapped controls. The
  actual case fallback still swapped. Its 23-check supplement is
  `acceptance: false`;
- a fresh or explicitly disclosed reused independent review.

## Outcomes

| Outcome | Result | 1,000 × 4 KiB F:→G: median (diagnostic) |
| --- | --- | --- |
| Core invocation holds and final-path corroboration | A hold reuses admission only after full admission inside the hold. The normalized DOS final-handle path must match the logical root exactly, ignoring only drive-letter case. Aliases and unavailable, malformed or oversize evidence release the hold and fall back. | — |
| Executor invocation hold | Lazy full admission and strict live confirmation before reuse. An introduced first-descendant omission was restored, with a retained no-effect regression. | 11.204 s, 0.349 MiB/s |
| Held-root attribute correction (after P1 below) | All three reuse selectors query fresh `FileBasicInfo` on the live handle. Reparse/placeholder state or a failed query refuses and can never select fallback. | 15.271 / 15.711 / 15.047 s, 0.256 MiB/s |
| Guarded preflight holds | Cached admission returns only after `RootHold.require_ordinary()`. Observation: 2.722 s median at baseline, 0.551 s at candidate. Judgment unchanged. | — |
| Single leaf observation | One checked no-follow snapshot supplies kind, size, mtime, identity, links and attributes: 12,000 fewer observations. | 12.365 s, 0.316 MiB/s |
| Bounded pure path reuse | Successful pure conversions are kept with exact raw keys, at most four root/anchor entries plus one nonroot slot, cleared on every invocation exit. | 10.757 s, 0.363 MiB/s |
| Single-lstat descendant walks | One `_reject_reparse` per component. Missing stops the walk; other errors propagate. | 9.684 s, 0.403 MiB/s |
| Descendant refusal (correctness) | `PermissionError` and other I/O failures are no longer treated as absence. NTFS ACL-junction witnesses refuse without writing through the junction. | — |
| Anchor-comparison authority (docs only) | The volume observation reports the admitted anchor, so the later comparison is not an independent freshness check. The comments now say so. | — |
| Cheap cache eligibility | A string predicate replaces `PureWindowsPath` construction. Eligibility is not validation; the core converter stays the authority. | 7.756 s, 0.504 MiB/s |
| Leaf volume from checked stat | The admitted `VolumeId` is reused when the low 32 bits of `st_dev` match and current held attributes pass. Anchor and volume queries fell from 6,002 to 2 each. | 5.383 s, 0.726 MiB/s |
| Held-root lexical containment | A confirmed default hold needs zero physical resolutions. Custom validators keep both. Draft review caught a dynamic-class default check and a lost custom backstop, both fixed. | 3.387 s, 1.153 MiB/s (fixture goal met) |
| Production held-root stat fast path (test/docs) | A native witness shows that default `stat` makes zero physical-resolution and volume queries under a confirmed hold. | — |
| Narrow runtime target admission (09-29) | Only the adjacent `_resolve_target_path` admission pair is delegated; the eligibility predicate is exact-class. Full-corpus medians: 3.627 / 1.958 / 0.372 / 0.304 / 2.004 s across five bands. | — |
| Verifier invocation holds | Engine and native final-touch reuse both require current ordinary held attributes. 3.885 s baseline vs 1.998 s candidate (VERIFY, 1,000 files). | — |
| Verifier opened-handle geometry | `FileStorageInfo` (class 16) on the opened handle, falling back to the existing pathname query. 1.512 s median. | — |

The timings are serialized, sequential desktop observations without
randomized order or cache eviction. Counted and profiled runs are separate
from them. They are not causal evidence, a latency gate or release throughput
acceptance.

## Important corrections and stops

- **RO-0b stop and user adjudication (09-28).** A production-shaped probe
  renamed the reviewed target away after the first control checkpoint and
  created a same-volume ordinary replacement. COPY then wrote into the
  replacement and reported success. The root contract had no object identity,
  so the acceptance criterion was a plan error. The user ruled that the
  promise starts at invocation binding. Before binding, including
  preflight-to-execute and pause/resume, the pathname, volume and per-item
  guards apply. Review-to-execution root identity became a future rung outside
  RO. DEFENSE EW-5 records both dispositions.
- **Intermediate-junction witness.** The initial hold failed the native
  intermediate-junction replacement witness. Full-width identity
  corroboration fixed the first instance but not a restored-junction second
  instance. That led to exact final-path corroboration as the common choke
  point. Whole-path casefold is not sufficient for case-sensitive directories.
- **P1: a confirmed hold permits in-place root reparse conversion** (blocked
  preflight review). With the hold open, a standard-user process (medium
  integrity, from a later read-only token query) opened the held directory
  with write access and set a mount-point reparse tag. `root.resolve()` then
  pointed at the sibling. A hold alone does not keep the root free of
  reparse. Preflight's cached-admission return would have lost baseline's
  refusal. No executor mutation, data loss or false terminal result was
  observed. The held-attribute correction closed it for every reuse consumer.
  The receipts are in `data.json`.
- **Observed-anchor spelling mismatch.** Reproduced against `b8baf42d`,
  corrected, and confirmed to preserve exact native evidence.
- **Reviewer reuse.** Agent-thread capacity limits made some reviews reuse an
  earlier reviewer context. Each review states this; none claims
  fresh-history independence.

## Unresolved limitations

- **exFAT FileIdInfo.** On K: exFAT, handle metadata fails at `FileIdInfo`
  with WinError 87. The executor copy witness fails truthfully as `io-error`.
  The exact receipt is `executor/exfat-handle-metadata.log` in `notes.md`.
  BUGS bug-0021 records the later fix. RO claimed no exFAT copy or
  verification support.
- **Measurement.** The 1 MiB/s fixture goal was unmet until the held-root
  lexical containment outcome. Exceeding it on this fixture is not a universal
  throughput guarantee.
- **Quiescence.** DEFENSE's quiescence assumption still governs the interval
  between the attribute check and use. No atomic immunity is claimed.

## Adequacy supplement — 2026-11-17

Per-outcome source/rig/measurement identities below are extracted from the frozen
gate manifests; the outcome name is the original manifest stem. They identify
measured physical candidates rather than treating a base revision as the edited
product. Full gate equality is reported only where the paired output exists.
The original baseline/verifier/runtime limits and nonacceptance of profiled
timings remain unchanged. Full test/document hash inventories are not retained.

```json
{
 "bound-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/bound-gate-inputs.json",
  "sha256": "72383307c1fe299f8693ee0ecf537ab422f0770145ac08d8b38ce25e3eaf4003",
  "owning_inputs": {
   "namisync/core/root_authority.py": "c0f98a9de5e8f91f575688b2f620199fd2259184decbb881ace62cfeed041d15",
   "build/root-admission-optimization-20260928/resume/run_finalpath_gates.ps1": "b99312371baca4b404c1a51ca096195cf91768cdd609b499a5fc7bfafe18271e"
  },
  "full_gate_input_output_equal": true
 },
 "executor-cheap-cache-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/executor-cheap-cache-gate-inputs.json",
  "sha256": "aa61f149045310f122bf086a73a3eb9f0c2a762e5df5fabc8761e1330779ee24",
  "owning_inputs": {
   "build/root-admission-optimization-20260928/ro0a/scan_v1_guards.py": "f9f3862fa518c45a2738c22304e499938a072ffef2bebb4c75f0a961f6b18842",
   "build/root-admission-optimization-20260928/resume/run_executor_cheap_cache_gates.ps1": "b6eea818847f2bfebfc22098212da382905241869d531e075b557b6875042662",
   "namisync/core/root_authority.py": "ef0852f54e8ea823fc77f2c6a7b8bd2cf47171ded79e64b053347a184d9cc19f",
   "namisync/modules/executor/native.py": "dc0f794af0a7735e6ad55a60be8c717def7fa18e8aabb764893eb60be8818f49",
   "namisync/modules/executor/runtime.py": "5b6de694c79187adc432cbc267061aee890c92e879628a66b6b3e4bdec7cdac5",
   "namisync/modules/preflight.py": "983efb8f4445c227a78b45368683450ad6baecfffeabb54ca82273e61dc2efd8",
   "namisync/modules/verifier/engine.py": "0a5a5002c5558069021a561da691a7b567ee3ca8b35626e4be6fba76d82268a6",
   "namisync/modules/verifier/native.py": "384cc16e176a96dcaed3c08503f1eb3c701e429b6df3e8d30502a26d34aeed88",
   "tools/executor_rig.py": "5b9b288f9b1270f8cd146531b133328ad032311567476c5000e4d1667ce91e7f",
   "tools/verifier_rig.py": "9b3f8e21dec167de3f7918fdc525a86da0a072ba3e7519e5f7887d124a97d537"
  },
  "full_gate_input_output_equal": true
 },
 "executor-descendant-refusal-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/executor-descendant-refusal-gate-inputs.json",
  "sha256": "e9c4c9677ae3523ee8bdd94315247844fe205419d2866748f0bded4877e15273",
  "owning_inputs": {
   "build/root-admission-optimization-20260928/ro0a/scan_v1_guards.py": "f9f3862fa518c45a2738c22304e499938a072ffef2bebb4c75f0a961f6b18842",
   "build/root-admission-optimization-20260928/resume/run_executor_descendant_refusal_gates.ps1": "b56934df9de95aa427ed079b9f753e2c439a9f95d1caf58fd9fa01de8cf23fa5",
   "namisync/core/root_authority.py": "ef0852f54e8ea823fc77f2c6a7b8bd2cf47171ded79e64b053347a184d9cc19f",
   "namisync/modules/executor/native.py": "30993b9bde2ee93f930c0834a22a791f14ec76e8f294ac848767b4492cf47244",
   "namisync/modules/executor/runtime.py": "5b6de694c79187adc432cbc267061aee890c92e879628a66b6b3e4bdec7cdac5",
   "namisync/modules/preflight.py": "983efb8f4445c227a78b45368683450ad6baecfffeabb54ca82273e61dc2efd8",
   "namisync/modules/verifier/engine.py": "0a5a5002c5558069021a561da691a7b567ee3ca8b35626e4be6fba76d82268a6",
   "namisync/modules/verifier/native.py": "384cc16e176a96dcaed3c08503f1eb3c701e429b6df3e8d30502a26d34aeed88",
   "tools/executor_rig.py": "5b9b288f9b1270f8cd146531b133328ad032311567476c5000e4d1667ce91e7f",
   "tools/verifier_rig.py": "9b3f8e21dec167de3f7918fdc525a86da0a072ba3e7519e5f7887d124a97d537"
  },
  "full_gate_input_output_equal": true
 },
 "executor-descendant-stat-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/executor-descendant-stat-gate-inputs.json",
  "sha256": "ff14e1a890df0933d06cae098d0fed57b619915193ff01478e6be8c320f969bc",
  "owning_inputs": {
   "build/root-admission-optimization-20260928/ro0a/scan_v1_guards.py": "f9f3862fa518c45a2738c22304e499938a072ffef2bebb4c75f0a961f6b18842",
   "build/root-admission-optimization-20260928/resume/run_executor_descendant_stat_gates.ps1": "3347f73de05e9f83a15285479064210f5043b749c79eccd8f6a3beeb301f9910",
   "namisync/core/root_authority.py": "6fba7b3aeb37b316c99d4edc4ef229fcf71d830715a7baa12a1a36a12e1084b4",
   "namisync/modules/executor/native.py": "933f0a9ad3888ad94b6a3b1f410c15d1769a589c0352cedbcc58ea7b2de7e2dc",
   "namisync/modules/executor/runtime.py": "5b6de694c79187adc432cbc267061aee890c92e879628a66b6b3e4bdec7cdac5",
   "namisync/modules/preflight.py": "983efb8f4445c227a78b45368683450ad6baecfffeabb54ca82273e61dc2efd8",
   "namisync/modules/verifier/engine.py": "0a5a5002c5558069021a561da691a7b567ee3ca8b35626e4be6fba76d82268a6",
   "namisync/modules/verifier/native.py": "384cc16e176a96dcaed3c08503f1eb3c701e429b6df3e8d30502a26d34aeed88",
   "tools/executor_rig.py": "5b9b288f9b1270f8cd146531b133328ad032311567476c5000e4d1667ce91e7f",
   "tools/verifier_rig.py": "9b3f8e21dec167de3f7918fdc525a86da0a072ba3e7519e5f7887d124a97d537"
  },
  "full_gate_input_output_equal": true
 },
 "executor-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/executor-gate-inputs.json",
  "sha256": "4b008525c792c55ec5dbbaed1259a256e617fcb289b99a0aa20f0eee65054758",
  "owning_inputs": {
   "build/root-admission-optimization-20260928/ro0a/scan_v1_guards.py": "f9f3862fa518c45a2738c22304e499938a072ffef2bebb4c75f0a961f6b18842",
   "build/root-admission-optimization-20260928/resume/run_executor_gates.ps1": "21d00d608eff6ced2aa36dbae0726749a3bb64fa11b5a190e00a4394d7b7e272",
   "namisync/core/root_authority.py": "c0f98a9de5e8f91f575688b2f620199fd2259184decbb881ace62cfeed041d15",
   "namisync/modules/executor/native.py": "04784bec5786adbb56e23fec26fdd323128d8053d0cdf8330a3f141eccda7a96",
   "namisync/modules/executor/runtime.py": "12d77b900a85aa98d3b9a18fb5587124caae71e2bfb4c0f7a6acfc42549562e5",
   "namisync/modules/preflight.py": "f89ff64dc6dd57cd26c1ba250f80a509833828f64d65f84b6bd54b41ea8b0a8a",
   "namisync/modules/verifier/engine.py": "f6cff85bd477bf0e2423d8b8c98f26bbe6186f37bdde00fe994af2f25a756ebd",
   "namisync/modules/verifier/native.py": "b23414106a6eb196ec6c71f4ec01bd5e2739736e092d276db7eb53acf5601fc9",
   "tools/executor_rig.py": "5b9b288f9b1270f8cd146531b133328ad032311567476c5000e4d1667ce91e7f",
   "tools/verifier_rig.py": "9b3f8e21dec167de3f7918fdc525a86da0a072ba3e7519e5f7887d124a97d537"
  },
  "full_gate_input_output_equal": true
 },
 "executor-held-resolve-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/executor-held-resolve-gate-inputs.json",
  "sha256": "604a8e54ef303d90f62c11b5e125ad9e2b2bf93d8bfee32bddb084df528fa5a7",
  "owning_inputs": {
   "build/root-admission-optimization-20260928/ro0a/scan_v1_guards.py": "f9f3862fa518c45a2738c22304e499938a072ffef2bebb4c75f0a961f6b18842",
   "build/root-admission-optimization-20260928/resume/run_executor_held_resolve_gates.ps1": "fcdc670125b22c92008d5c335ebed85bacaa23e2857edfaf45670a1c5b03b0dc",
   "namisync/core/root_authority.py": "ef0852f54e8ea823fc77f2c6a7b8bd2cf47171ded79e64b053347a184d9cc19f",
   "namisync/modules/executor/native.py": "08e5afc556997a373db19389c1fd99e7b060866366dd3ca1689e63bc36575ad5",
   "namisync/modules/executor/runtime.py": "5b6de694c79187adc432cbc267061aee890c92e879628a66b6b3e4bdec7cdac5",
   "namisync/modules/preflight.py": "983efb8f4445c227a78b45368683450ad6baecfffeabb54ca82273e61dc2efd8",
   "namisync/modules/verifier/engine.py": "0a5a5002c5558069021a561da691a7b567ee3ca8b35626e4be6fba76d82268a6",
   "namisync/modules/verifier/native.py": "384cc16e176a96dcaed3c08503f1eb3c701e429b6df3e8d30502a26d34aeed88",
   "tools/executor_rig.py": "5b9b288f9b1270f8cd146531b133328ad032311567476c5000e4d1667ce91e7f",
   "tools/verifier_rig.py": "9b3f8e21dec167de3f7918fdc525a86da0a072ba3e7519e5f7887d124a97d537"
  },
  "full_gate_input_output_equal": true
 },
 "executor-path-cache-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/executor-path-cache-gate-inputs.json",
  "sha256": "132e6b576ab475c5bfad6bb75cce28275a79db2cc0d2987555f426f83ac45242",
  "owning_inputs": {
   "build/root-admission-optimization-20260928/ro0a/scan_v1_guards.py": "f9f3862fa518c45a2738c22304e499938a072ffef2bebb4c75f0a961f6b18842",
   "build/root-admission-optimization-20260928/resume/run_executor_path_cache_gates.ps1": "c7ca0a7bc0c1107f1745edc55b3f6a7df1b0945cd40b9435d4dcccad3ca2d1e2",
   "namisync/core/root_authority.py": "6fba7b3aeb37b316c99d4edc4ef229fcf71d830715a7baa12a1a36a12e1084b4",
   "namisync/modules/executor/native.py": "4f7e22cb474ad4ff3e1ac1e22b85d5ef4ecf329580d0728f24525af3ef2d9386",
   "namisync/modules/executor/runtime.py": "5b6de694c79187adc432cbc267061aee890c92e879628a66b6b3e4bdec7cdac5",
   "namisync/modules/preflight.py": "983efb8f4445c227a78b45368683450ad6baecfffeabb54ca82273e61dc2efd8",
   "namisync/modules/verifier/engine.py": "0a5a5002c5558069021a561da691a7b567ee3ca8b35626e4be6fba76d82268a6",
   "namisync/modules/verifier/native.py": "384cc16e176a96dcaed3c08503f1eb3c701e429b6df3e8d30502a26d34aeed88",
   "tools/executor_rig.py": "5b9b288f9b1270f8cd146531b133328ad032311567476c5000e4d1667ce91e7f",
   "tools/verifier_rig.py": "9b3f8e21dec167de3f7918fdc525a86da0a072ba3e7519e5f7887d124a97d537"
  },
  "full_gate_input_output_equal": true
 },
 "executor-runtime-narrow-final-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/executor-runtime-narrow-final-gate-inputs.json",
  "sha256": "d7fd1a9b58659e9f42a4574021ff947e4adcc942cfe4fe729a5fd255fae8998e",
  "owning_inputs": {
   "build/root-admission-optimization-20260928/ro0a/scan_v1_guards.py": "f9f3862fa518c45a2738c22304e499938a072ffef2bebb4c75f0a961f6b18842",
   "build/root-admission-optimization-20260928/resume/run_executor_runtime_narrow_final_gates.ps1": "96e8112b80433620561982f42bee609e5ba50da31fe5da1a4ea28fd133cd9fa3",
   "namisync/core/root_authority.py": "ef0852f54e8ea823fc77f2c6a7b8bd2cf47171ded79e64b053347a184d9cc19f",
   "namisync/modules/executor/native.py": "6382806b521e3439cecd97c760e2b0c1e9474b1198976b74edd8c7f184459e38",
   "namisync/modules/executor/runtime.py": "08333a2d3b40ac2760ee8f2cbb0495cbbd41fc84ea981b43698f737a4e484c31",
   "namisync/modules/preflight.py": "983efb8f4445c227a78b45368683450ad6baecfffeabb54ca82273e61dc2efd8",
   "namisync/modules/verifier/engine.py": "0a5a5002c5558069021a561da691a7b567ee3ca8b35626e4be6fba76d82268a6",
   "namisync/modules/verifier/native.py": "384cc16e176a96dcaed3c08503f1eb3c701e429b6df3e8d30502a26d34aeed88",
   "tools/executor_rig.py": "5b9b288f9b1270f8cd146531b133328ad032311567476c5000e4d1667ce91e7f",
   "tools/verifier_rig.py": "9b3f8e21dec167de3f7918fdc525a86da0a072ba3e7519e5f7887d124a97d537"
  },
  "full_gate_input_output_equal": true
 },
 "executor-runtime-narrow-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/executor-runtime-narrow-gate-inputs.json",
  "sha256": "5ad016477e949fb1238750c0f2938a38a260c50543bdd92e7c4940f75c1464a9",
  "owning_inputs": {
   "build/root-admission-optimization-20260928/ro0a/scan_v1_guards.py": "f9f3862fa518c45a2738c22304e499938a072ffef2bebb4c75f0a961f6b18842",
   "build/root-admission-optimization-20260928/resume/run_executor_runtime_narrow_gates.ps1": "d5b3bac7b35170f3e4cb476a864f3886c2286d6dba2ee8b89f26ed22e8bda9c2",
   "namisync/core/root_authority.py": "ef0852f54e8ea823fc77f2c6a7b8bd2cf47171ded79e64b053347a184d9cc19f",
   "namisync/modules/executor/native.py": "da02e4a4e79d0c8937ce462f651ea8023b91a521cb7c2483892a544938d750ae",
   "namisync/modules/executor/runtime.py": "08333a2d3b40ac2760ee8f2cbb0495cbbd41fc84ea981b43698f737a4e484c31",
   "namisync/modules/preflight.py": "983efb8f4445c227a78b45368683450ad6baecfffeabb54ca82273e61dc2efd8",
   "namisync/modules/verifier/engine.py": "0a5a5002c5558069021a561da691a7b567ee3ca8b35626e4be6fba76d82268a6",
   "namisync/modules/verifier/native.py": "384cc16e176a96dcaed3c08503f1eb3c701e429b6df3e8d30502a26d34aeed88",
   "tools/executor_rig.py": "5b9b288f9b1270f8cd146531b133328ad032311567476c5000e4d1667ce91e7f",
   "tools/verifier_rig.py": "9b3f8e21dec167de3f7918fdc525a86da0a072ba3e7519e5f7887d124a97d537"
  },
  "full_gate_input_output_equal": null
 },
 "executor-single-stat-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/executor-single-stat-gate-inputs.json",
  "sha256": "cfb4641e94cfab456d34d82bbc24b2eb27cf2365d8c49566d36c13b78e5221b3",
  "owning_inputs": {
   "build/root-admission-optimization-20260928/ro0a/scan_v1_guards.py": "f9f3862fa518c45a2738c22304e499938a072ffef2bebb4c75f0a961f6b18842",
   "build/root-admission-optimization-20260928/resume/run_executor_single_stat_gates.ps1": "1fffb26cce2ce325df9551f163182f8c24af84806059e59739077676bac9bed6",
   "namisync/core/root_authority.py": "6fba7b3aeb37b316c99d4edc4ef229fcf71d830715a7baa12a1a36a12e1084b4",
   "namisync/modules/executor/native.py": "f28c0df6268d47b4bbc4df804f1ebdf8399dad164e60f8d0012dce30438b11d6",
   "namisync/modules/executor/runtime.py": "12d77b900a85aa98d3b9a18fb5587124caae71e2bfb4c0f7a6acfc42549562e5",
   "namisync/modules/preflight.py": "983efb8f4445c227a78b45368683450ad6baecfffeabb54ca82273e61dc2efd8",
   "namisync/modules/verifier/engine.py": "0a5a5002c5558069021a561da691a7b567ee3ca8b35626e4be6fba76d82268a6",
   "namisync/modules/verifier/native.py": "384cc16e176a96dcaed3c08503f1eb3c701e429b6df3e8d30502a26d34aeed88",
   "tools/executor_rig.py": "5b9b288f9b1270f8cd146531b133328ad032311567476c5000e4d1667ce91e7f",
   "tools/verifier_rig.py": "9b3f8e21dec167de3f7918fdc525a86da0a072ba3e7519e5f7887d124a97d537"
  },
  "full_gate_input_output_equal": true
 },
 "executor-stat-volume-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/executor-stat-volume-gate-inputs.json",
  "sha256": "895331b5c3f20967593843066b2e7291c4fd8fdfc6b2255ba815ddcdbce9dd91",
  "owning_inputs": {
   "build/root-admission-optimization-20260928/ro0a/scan_v1_guards.py": "f9f3862fa518c45a2738c22304e499938a072ffef2bebb4c75f0a961f6b18842",
   "build/root-admission-optimization-20260928/resume/run_executor_stat_volume_gates.ps1": "6f0afb473f406fe60376bd18db068b73bd486dcec0f0862d67734a16d6638736",
   "namisync/core/root_authority.py": "ef0852f54e8ea823fc77f2c6a7b8bd2cf47171ded79e64b053347a184d9cc19f",
   "namisync/modules/executor/native.py": "6ff1b1c21960226a44063c47accf06fc8ed947c53e74eccf4381174dabeb36ad",
   "namisync/modules/executor/runtime.py": "5b6de694c79187adc432cbc267061aee890c92e879628a66b6b3e4bdec7cdac5",
   "namisync/modules/preflight.py": "983efb8f4445c227a78b45368683450ad6baecfffeabb54ca82273e61dc2efd8",
   "namisync/modules/verifier/engine.py": "0a5a5002c5558069021a561da691a7b567ee3ca8b35626e4be6fba76d82268a6",
   "namisync/modules/verifier/native.py": "384cc16e176a96dcaed3c08503f1eb3c701e429b6df3e8d30502a26d34aeed88",
   "tools/executor_rig.py": "5b9b288f9b1270f8cd146531b133328ad032311567476c5000e4d1667ce91e7f",
   "tools/verifier_rig.py": "9b3f8e21dec167de3f7918fdc525a86da0a072ba3e7519e5f7887d124a97d537"
  },
  "full_gate_input_output_equal": true
 },
 "held-attributes-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/held-attributes-gate-inputs.json",
  "sha256": "f5ed75891c5f82e018c39774d70a4590014e24527080458354f668f13a700466",
  "owning_inputs": {
   "build/root-admission-optimization-20260928/ro0a/scan_v1_guards.py": "f9f3862fa518c45a2738c22304e499938a072ffef2bebb4c75f0a961f6b18842",
   "build/root-admission-optimization-20260928/resume/run_held_attributes_gates.ps1": "3879418e62d8c64b8ad3a96e74a90b6e849cce19d9033260542a723e86f0bd9f",
   "namisync/core/root_authority.py": "6fba7b3aeb37b316c99d4edc4ef229fcf71d830715a7baa12a1a36a12e1084b4",
   "namisync/modules/executor/native.py": "7e68306b01bcdf983ae25204e82aa892aaf6eb898d70c14494b7fe5cfa4e1c17",
   "namisync/modules/executor/runtime.py": "12d77b900a85aa98d3b9a18fb5587124caae71e2bfb4c0f7a6acfc42549562e5",
   "namisync/modules/preflight.py": "f89ff64dc6dd57cd26c1ba250f80a509833828f64d65f84b6bd54b41ea8b0a8a",
   "namisync/modules/verifier/engine.py": "f6cff85bd477bf0e2423d8b8c98f26bbe6186f37bdde00fe994af2f25a756ebd",
   "namisync/modules/verifier/native.py": "b23414106a6eb196ec6c71f4ec01bd5e2739736e092d276db7eb53acf5601fc9",
   "tools/executor_rig.py": "5b9b288f9b1270f8cd146531b133328ad032311567476c5000e4d1667ce91e7f",
   "tools/verifier_rig.py": "9b3f8e21dec167de3f7918fdc525a86da0a072ba3e7519e5f7887d124a97d537"
  },
  "full_gate_input_output_equal": true
 },
 "preflight-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/preflight-gate-inputs.json",
  "sha256": "0a6e1198078b7dfaab9e284293b20bc8cc0c7ec1bb6819b60f44911251b20be8",
  "owning_inputs": {
   "build/root-admission-optimization-20260928/ro0a/scan_v1_guards.py": "f9f3862fa518c45a2738c22304e499938a072ffef2bebb4c75f0a961f6b18842",
   "build/root-admission-optimization-20260928/resume/run_preflight_gates.ps1": "aec7bb8b026c4938e1e1f333bcaf217b1d89b7a2100234ecb2c70aec5d73d7d4",
   "namisync/core/root_authority.py": "c0f98a9de5e8f91f575688b2f620199fd2259184decbb881ace62cfeed041d15",
   "namisync/modules/executor/native.py": "04784bec5786adbb56e23fec26fdd323128d8053d0cdf8330a3f141eccda7a96",
   "namisync/modules/executor/runtime.py": "12d77b900a85aa98d3b9a18fb5587124caae71e2bfb4c0f7a6acfc42549562e5",
   "namisync/modules/preflight.py": "e08047e6eef3c1f7373b3cad0d67d4b4ec3df7a29785d39e705c2e7bc9c04c85",
   "namisync/modules/verifier/engine.py": "f6cff85bd477bf0e2423d8b8c98f26bbe6186f37bdde00fe994af2f25a756ebd",
   "namisync/modules/verifier/native.py": "b23414106a6eb196ec6c71f4ec01bd5e2739736e092d276db7eb53acf5601fc9",
   "tools/executor_rig.py": "5b9b288f9b1270f8cd146531b133328ad032311567476c5000e4d1667ce91e7f",
   "tools/verifier_rig.py": "9b3f8e21dec167de3f7918fdc525a86da0a072ba3e7519e5f7887d124a97d537"
  },
  "full_gate_input_output_equal": null
 },
 "preflight-guarded-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/preflight-guarded-gate-inputs.json",
  "sha256": "83bd735150fafc4f9f24980c96737ca84784bedacd0ebfa9b250a8571c365388",
  "owning_inputs": {
   "build/root-admission-optimization-20260928/ro0a/scan_v1_guards.py": "f9f3862fa518c45a2738c22304e499938a072ffef2bebb4c75f0a961f6b18842",
   "build/root-admission-optimization-20260928/resume/run_preflight_guarded_gates.ps1": "d0fb22af32aa6a310a0797f5e52dc17a35e5ed6dd147f18e280dad2092ca92cf",
   "namisync/core/root_authority.py": "6fba7b3aeb37b316c99d4edc4ef229fcf71d830715a7baa12a1a36a12e1084b4",
   "namisync/modules/executor/native.py": "7e68306b01bcdf983ae25204e82aa892aaf6eb898d70c14494b7fe5cfa4e1c17",
   "namisync/modules/executor/runtime.py": "12d77b900a85aa98d3b9a18fb5587124caae71e2bfb4c0f7a6acfc42549562e5",
   "namisync/modules/preflight.py": "983efb8f4445c227a78b45368683450ad6baecfffeabb54ca82273e61dc2efd8",
   "namisync/modules/verifier/engine.py": "f6cff85bd477bf0e2423d8b8c98f26bbe6186f37bdde00fe994af2f25a756ebd",
   "namisync/modules/verifier/native.py": "b23414106a6eb196ec6c71f4ec01bd5e2739736e092d276db7eb53acf5601fc9",
   "tools/executor_rig.py": "5b9b288f9b1270f8cd146531b133328ad032311567476c5000e4d1667ce91e7f",
   "tools/verifier_rig.py": "9b3f8e21dec167de3f7918fdc525a86da0a072ba3e7519e5f7887d124a97d537"
  },
  "full_gate_input_output_equal": true
 },
 "verifier-geometry-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/verifier-geometry-gate-inputs.json",
  "sha256": "100604e3904b5cc0a69a3fee62167f504d05c4e10b76c1a258368bed8501a1ff",
  "owning_inputs": {
   "build/root-admission-optimization-20260928/ro0a/scan_v1_guards.py": "f9f3862fa518c45a2738c22304e499938a072ffef2bebb4c75f0a961f6b18842",
   "build/root-admission-optimization-20260928/resume/run_verifier_geometry_gates.ps1": "429094e4499cb903590ced8aeca5e59edbeb98ad57606f62563aab6f3e75ab57",
   "namisync/core/root_authority.py": "6fba7b3aeb37b316c99d4edc4ef229fcf71d830715a7baa12a1a36a12e1084b4",
   "namisync/modules/executor/native.py": "7e68306b01bcdf983ae25204e82aa892aaf6eb898d70c14494b7fe5cfa4e1c17",
   "namisync/modules/executor/runtime.py": "12d77b900a85aa98d3b9a18fb5587124caae71e2bfb4c0f7a6acfc42549562e5",
   "namisync/modules/preflight.py": "983efb8f4445c227a78b45368683450ad6baecfffeabb54ca82273e61dc2efd8",
   "namisync/modules/verifier/engine.py": "0a5a5002c5558069021a561da691a7b567ee3ca8b35626e4be6fba76d82268a6",
   "namisync/modules/verifier/native.py": "384cc16e176a96dcaed3c08503f1eb3c701e429b6df3e8d30502a26d34aeed88",
   "tools/executor_rig.py": "5b9b288f9b1270f8cd146531b133328ad032311567476c5000e4d1667ce91e7f",
   "tools/verifier_rig.py": "9b3f8e21dec167de3f7918fdc525a86da0a072ba3e7519e5f7887d124a97d537"
  },
  "full_gate_input_output_equal": true
 },
 "verifier-held-gate-inputs.json": {
  "input": "build/root-admission-optimization-20260928/resume/verifier-held-gate-inputs.json",
  "sha256": "f7b227a807f908918b706e9d43c04a6b34d6065aca7bbbcc0ec57f4e67ac8292",
  "owning_inputs": {
   "build/root-admission-optimization-20260928/ro0a/scan_v1_guards.py": "f9f3862fa518c45a2738c22304e499938a072ffef2bebb4c75f0a961f6b18842",
   "build/root-admission-optimization-20260928/resume/run_verifier_held_gates.ps1": "87b4889ab8b57465bce4ac1a216f8fb2c4fc1a25df0b247345869b83f530de92",
   "namisync/core/root_authority.py": "6fba7b3aeb37b316c99d4edc4ef229fcf71d830715a7baa12a1a36a12e1084b4",
   "namisync/modules/executor/native.py": "7e68306b01bcdf983ae25204e82aa892aaf6eb898d70c14494b7fe5cfa4e1c17",
   "namisync/modules/executor/runtime.py": "12d77b900a85aa98d3b9a18fb5587124caae71e2bfb4c0f7a6acfc42549562e5",
   "namisync/modules/preflight.py": "983efb8f4445c227a78b45368683450ad6baecfffeabb54ca82273e61dc2efd8",
   "namisync/modules/verifier/engine.py": "0a5a5002c5558069021a561da691a7b567ee3ca8b35626e4be6fba76d82268a6",
   "namisync/modules/verifier/native.py": "119ba0c0e29ac24a4f70267bb787e46cd3d7a9123dc5952486d591e2136cae67",
   "tools/executor_rig.py": "5b9b288f9b1270f8cd146531b133328ad032311567476c5000e4d1667ce91e7f",
   "tools/verifier_rig.py": "9b3f8e21dec167de3f7918fdc525a86da0a072ba3e7519e5f7887d124a97d537"
  },
  "full_gate_input_output_equal": true
 }
}
```
