# Latest session — Create batch package refresh, 2026-11-05

Built the requested portable development package from clean
`248b510c0be36f0ce708c1652a0b71430b019a16`, including both Setup action and Create
batch fixes. No product, dependency, version or icon changes in this session.

Current artifact: `build/m1-release-20261104/attempt-06/NamiSync-windows-x64-dev.zip`
SHA-256: `d38b452f5102d10060c86c0244f50afecb4bdb16f386b28aeb42b9af9e51fd41`.
Extract the entire ZIP and run `NamiSync/namisync-gui.exe`. Source ZIP, wheel,
checksums, source identity and environment record are adjacent. Existing
per-user data placement and optional absolute `--data-dir` remain unchanged.

This supersedes attempt-05 for new debugging/measurement. The user confirmed
no testing between 13:12 and this request used that early-afternoon package.
Earlier artifacts/receipts remain historical; use attempt-06 going forward.

## Verification and evidence

Reused the pinned disposable packaging environment; installed the new wheel
before freezing. `build-06.log` records successful pip check, x64 PE/subsystem
checks and actual console help. `artifact-check-06.json` verifies 312 source
entries, 211 bundled assets and archive/checksum integrity. ICO correspondence
is provenance, not a fixed rendering oracle; no artwork was regenerated.
`native-smoke-06.json` records external extraction, isolated `native-profile-06`,
WebView2 startup, native icon and normal exit 0. Its exact temporary extraction
is retained for debugging; no test window remains open. Earlier packaging
extractions/profiles remain untouched.

The fix's 2,208 interface passes and three installed Setup/shell witnesses are
recorded at `248b510c` and under
`build/setup-admission-20261104/batch-followup-20261105/`. This rebuild checked
packaging/startup only; it did not repeat behavioral or resource acceptance.
M1_PLAN owns dependency hash locks, hosted CI, notices/distribution, resource
acceptance and final candidate gates. No push or publication occurred.
