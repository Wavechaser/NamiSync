# Latest session — repeatable builds and hosted CI verified, 2026-11-05

Implemented and reviewed `b3095886` from base `848450da`. The user explicitly
requested integration and push on `milestone1`; that fast-forward and push are
complete. Recovery `987cba84` was not merged/cherry-picked and is not in
milestone1 ancestry. Its useful changes were rebuilt with the newline correction
and matching tests/docs. Product source and the reviewed icon were not edited.

## Delivered

Hash-locked existing runtime/freezer downloads plus pip/setuptools bootstrap;
clean committed-source admission; explicit Git newline conversion settings;
fixed archive metadata/freezer hash seed; exact dependency inventory; source
and bundle identities. CI pins Action commits and Python/Node versions and
fetches full history for the existing custody validators. No validator was
relaxed. TOOLS owns commands and the bounded repeatability claim.

## Verification

Evidence: `build/m1-release-20261104/repeatable/`.

- Eight focused tests; ordinary: 6,367 passes, four capability skips, 35 headed
  exclusions; twelve import contracts. All 35 headed obligations pass across
  29 original passes and six retry passes (47 total cases in selected retry
  files). The original five foreground refusals and one unexpected focus
  observation remain; unchanged retry passed during the user's quiet desktop
  window. Preservation archives contain 63 original and 26 retry evidence files.
- Two fresh corrected builds (`build-c`, `build-d`) at `b3095886`: independent
  Git-tree checks confirm 313 exact source blobs; wheels, source ZIPs and
  executables match. Four installer metadata files differ with environment
  paths/launcher hashes. Hash-locked offline installation and wrong-hash
  rejection pass. Initial builds and failed focused receipts remain retained.
- Hosted run https://github.com/Wavechaser/NamiSync/actions/runs/42041508978
  passes 6,371 ordinary tests, twelve imports and portable build/upload on
  `windows-2025-vs2026` image `20261030.294.1`. Both job logs and status receipts
  are preserved. The prior shallow-checkout failure remains in hosted-original.log.
- Downloaded artifact `13424042162` is under `hosted/`. Its wrapper SHA-256
  `712568b146d5bb9ee5c578c82debc667c96da03e67f51ad1710173c30ad3575e`
  matches GitHub; all archive/checksum/source/dependency checks pass. Hosted and
  local source ZIPs, wheels and executables match. Across hosts 48 files differ:
  four installer metadata files plus 44 Windows/SQLite DLLs; both SQLite file
  versions are 3.50.4.0. Full ZIP byte identity across hosts is not claimed.
- Both final local and downloaded hosted frozen GUIs start with WebView2/icon
  and close normally on Windows 11. `native-smoke-final.json` and
  `native-smoke-hosted.json` name retained external extractions and isolated
  `native-profile-07`/`native-profile-08`. No test window remains open.

The local CI watcher lost its connection; GitHub continued successfully. The
stalled gh download was interrupted, and the GitHub connector's artifact was
saved and verified instead. An initial public push was rejected by automatic
approval review; the user's explicit milestone1 push instruction resolved it.
No release/tag was published. The closeout only updates documentation; executable,
producer, test and workflow inputs remain at the verified commit.

## Immediate context

Measured attempt-06 from `248b510c` is unchanged, SHA-256
`d38b452f5102d10060c86c0244f50afecb4bdb16f386b28aeb42b9af9e51fd41`.
The newly verified hosted development ZIP has SHA-256
`c9e25aa191e1b3a02ec5c1b1ab9d5078a29f7acbdccd414f59cc139880ef9fb3`.
Do not silently substitute it in the ongoing resource baseline. The new build
normalizes archive source newlines; all 303 product files match attempt-06 after
CRLF normalization, with 101 newline-only differences. Six extra empty pip
REQUESTED markers reflect explicit dependency locking. This is development
build/CI closure, not final release acceptance. Notices/source distribution,
resource acceptance, final candidate gates and release publication remain with
M1_PLAN. Retain all build evidence and prior packaging extractions/profiles.
