# Latest session — Resource study preparation, 2026-11-06

The user requested detailed updated-package measurement preparation, authorized
the full/partial `F:\NamiSyncExecutorBenchSource\` corpus and new targets under
`H:\test_dir\`, and selected the latest settled repeatable package. No app,
measured workload, external fixture or sync was launched. Branch is
`milestone1`; inspected base is `825c5618`.

## Prepared

PERFORMANCE owns seven diagnostic profiles: startup, metadata size, long
Japanese paths, retained tasks, streamed file sizes, repeated lifecycle and
a combined corpus journey. It specifies repetitions, idle windows, process-role
attribution, correctness/history evidence, failed-run handling, cleanup and
separate lab emergency stops. No release memory budget is derived or accepted.
M1_PLAN records preparation and leaves R3/SH-G-15 open.

`build/resource-study-20261106/census.py` read corpus metadata and package
hashes. `census.json` records 1,581 payload files/5,171,478,528 bytes in five
groups, no reparses, and about 401 GiB available on H: at preparation. It is
not a content-hash verification. No external fixture exists to clean up yet.
README defines evidence layout and eventual cleanup boundaries. Product/test
source is unchanged. Independent review passed with no blocking findings and
recomputed corpus totals and identity hashes. Links pass (32 documents, 378
links) and diff checks are clean. This is not product testing or a resource
acceptance run; the review receipt is retained beside the census.

## Artifact and immediate continuation

Latest completed local repeatable package is
`build/m1-release-20261104/repeatable/build-d/NamiSync-windows-x64-dev.zip`,
SHA-256 `1d73619bb23e567f5c461e15fb9c82595853b419e1da169dafb17c165e7cf552`,
477 files, product source b3095886. R2's native-input provenance gap remains:
API-set/UCRT DLL collection included ambient PATH inputs. No malicious-input
or supported sync-failure claim was made. If packaging replaces the runtime,
freeze that replacement before collection; never pool differing package runs.

Next implement the profile driver and separate checker, reusing the passive
Job sampler and successful single-click native input seam. The old passive
driver is hard-coded to attempt-03 and must not run unchanged. Start with an
unmeasured control pilot, then startup/small functional runs; review fidelity
before large cases. No full-tree live UIA polling. Manual phase witnessing
remains an authorized fallback. Hashing/staging and tests/builds stay outside
measured intervals. The full matrix takes hours.

## Preserved release context

Hosted run 42056121788 at `48574eb6` passed 6,371 ordinary tests, twelve import
contracts, build/upload and Node-24 Action checks. It did not native-test the
new hosted artifact. Existing build-d native evidence is scoped to its exact
artifact. Attempt-06 (`248b510c`) remains preserved, ZIP SHA-256
`d38b452f5102d10060c86c0244f50afecb4bdb16f386b28aeb42b9af9e51fd41`.

R2 remains preparation: settle native inputs/origin evidence, complete/export
notices, integrate prepared START-HERE/BUILDING guides. TOOLS owns that census.
User selected unsigned v0.1.0 Gertrud tester delivery; delivery location remains
undecided. R3 resource acceptance, R4 final candidate checks and R5 handoff/
publication remain open. No release/tag/publication occurred. Historical
recovery 987cba84 remains unmerged; preserve earlier package/native evidence.
