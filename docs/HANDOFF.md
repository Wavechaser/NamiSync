# Latest session — portable package refresh, 2026-11-05

Built a new development package at the user's request after the Setup control
fix. Product/build inputs were clean at `939e57c17f8209c2d9c42e45228ba4acb583e149`;
no product, dependency, version or icon changes were made in this session.

Artifact: `build/m1-release-20261104/attempt-05/NamiSync-windows-x64-dev.zip`
SHA-256: `be10b5c90915975194d0e4dd72c64434d0164af86ecd3554a86911e0b1fd4162`.
The source ZIP, wheel, SHA256SUMS, source identity and environment record are
adjacent. Extract the entire ZIP and run `NamiSync/namisync-gui.exe`.
Existing per-user data placement and optional absolute `--data-dir` are unchanged.

## Verification

The existing pinned disposable package environment was reused; the build
installs the new wheel before freezing. PE x64/subsystems, pip check and real
console help passed. `artifact-check-05.json` records 312 source entries,
211 bundled assets and ZIP/checksum verification. Asset comparisons establish
source correspondence, not a fixed ICO rendering oracle. No icon was rebuilt.
`native-smoke-05.json` records GUI WebView2 startup, native icon and normal exit
0 from an external extraction with an isolated profile. The source/asset and
build checks passed; no full behavioral or resource gate was rerun.

`build-04.log` retains the initial sandbox pip temporary-directory permission
failure. `build-05.log` records the successful native build. Attempt-04 remains
as failed evidence; previous successful packages remain intact.

## Resumption

Latest package supersedes attempt-03 for new debugging/measurement. The native
smoke receipt names its retained temporary extraction and `native-profile-05`;
prior packaging extractions/profiles are preserved. No test window remains open.
Setup fix and first-click wheel evidence remain under
`build/setup-admission-20261104/`, documented at `939e57c1`. Older portable
measurements remain diagnostic and do not automatically certify changed assets.
M1_PLAN owns remaining dependency hash locks, hosted CI, notices/distribution,
resource acceptance and final candidate gates. No push or publication occurred.
