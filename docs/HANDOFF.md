# Latest session — repeatable builds and CI verification, 2026-11-05

User cleared local verification while resource baselining proceeds separately.
Product, reviewed icon and measured attempt-06 remain unchanged. Build/CI work
starts from `848450da`; recovery `987cba84` is preservation only and must not be
merged/cherry-picked. Reconstruct the reviewed task delta on a normal branch.

## Changes and local verification

Hash-lock existing runtime/freezer downloads plus pip/setuptools bootstrap.
Build from clean committed source with explicit Git newline settings, fixed
archive metadata/freezer hash seed, exact environment admission and source/bundle
manifests. Pin Action commits and Python/Node versions; ordinary CI fetches full
history for frozen custody evidence. Tools/tests/docs are the only changed owners.

Evidence: `build/m1-release-20261104/repeatable/`.
Eight focused checks pass (`focused-final.xml`); ordinary: 6,367 passed, four
capability skips, 35 headed deselected (`ordinary.xml`). Twelve import contracts
pass. Headed: 29 original passes plus six retry passes, with 47 total selected
cases in `headed-retry.xml`. Original five foreground refusals and one unexpected
focus observation remain in `headed.log`; the unchanged retry passed with the
user leaving test windows in front. All test windows are closed.

Fresh offline locked installs and wrong-hash rejection pass. `build-a`/`build-b`
have equal wheels, source ZIPs and executables; four environment-specific
installer metadata files differ. `comparison-build-a-build-b.json` verifies
archives/manifests/checksums. A focused test exposed implicit Git archive newline
conversion; explicit settings fix it. These initial builds precede that correction;
corrected-source builds and hosted verification are next. Earlier failed focused
receipts remain; no source/product test authority was relaxed.

## Hosted run and remaining work

Prior run https://github.com/Wavechaser/NamiSync/actions/runs/41864478291 had
6,361 passes/two failures caused by shallow history; portable was skipped.
`hosted-original.log` preserves evidence. Corrected hosted ordinary/import/portable
jobs have not yet run. Next: reviewed task commit on `codex/m1-release-repeatable`,
corrected isolated builds, remote CI branch run and exact artifact checks, then
closeout. No release publication is part of this task. Source snapshots and
serviced Windows runtime identities qualify repeatability; ZIP byte identity is
not claimed across installer paths or different hosts.

Measured package remains attempt-06 from `248b510c`, SHA-256
`d38b452f5102d10060c86c0244f50afecb4bdb16f386b28aeb42b9af9e51fd41`.
M1_PLAN owns remaining distribution/resource/final release gates. Packaging
smoke extractions/profiles and all failed receipts remain preserved.
