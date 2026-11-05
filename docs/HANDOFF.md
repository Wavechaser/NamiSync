# Latest session — Action refresh and distribution preparation, 2026-11-05

The user requested latest stable Action pins, CI verification, then distribution
readiness preparation; selected `v0.1.0` without a beta suffix and explicitly
chose unsigned tester delivery. Branch is `milestone1`.

## Delivered and verified

`48574eb6` updates checkout to v7.0.1, setup-python/setup-node to v7.1.0 and
upload-artifact to v7.0.2, all pinned to full commits. Each declares Node 24.
The project Python 3.13.17/Node 24.22.1 pins, locks, full-history test checkout,
read-only permissions and workflow scope remain unchanged.

Hosted run https://github.com/Wavechaser/NamiSync/actions/runs/42056121788
passes 6,371 ordinary tests (35 headed exclusions), twelve import contracts,
portable build and upload. Saved log contains no Node 20 deprecation warning.
Artifacts: ordinary-results `13428549363`; development package `13429968717`.
This session verified upload but did not download/native-test that new artifact.
Prior b3095886 local/hosted native evidence remains scoped to its exact artifacts.
Raw refresh evidence: `build/m1-release-20261104/repeatable/action-refresh.log`
and `action-refresh-jobs.json`.

Distribution preparation is documentation and artifact inspection only:
`tools/packaging/START-HERE.txt` and `BUILDING.txt` prepare tester and matching-
source rebuild guidance. They are not yet consumed by the builder; the generated
ZIP guide remains unchanged. README links them as preparation materials.
TOOLS owns the distribution census/notice gaps; M1_PLAN owns remaining gates.
The package/About version already is 0.1.0, nickname Gertrud.

## Census and next work

`build/m1-release-20261104/distribution/census.py` verifies retained local build-d
at b3095886: all 477 files match its collection sources and bundle manifest.
`census.json` records both executable analyses (763 distinct source/name pairs),
entry-point bootstrap/bootloader inputs, source hashes and twenty existing About
notices. It does not declare redistribution clearance.

Actual frozen inputs extend beyond the app's requirements: CPython/native
libraries, PyInstaller bootstrap, setuptools and its vendored modules, and
packaging need distribution-wide notices. The old About corpus remains useful
but cannot certify that whole population. Relevant upstream license/build
references and the finite notice families are in TOOLS.

Local build-d also contains 42 API-set DLLs and ucrtbase.dll originating from
an ambient Codex runtime libheif directory. PyInstaller's Windows resolver falls
back to PATH. This is a native-input provenance gap; no supported sync failure,
data-loss finding or malicious DLL claim is made. The earlier hosted artifact
has different Windows DLL bytes, but its origin tables were not uploaded; do
not infer its origins from the local build.

Next settle native collection inputs and retain their origins for both local
and CI builds, then complete/export notices and integrate the prepared guides.
A changed native runtime invalidates affected installed/resource evidence; use
fresh candidate attempts and preserve the baseline. Do not claim that input
hashes or successful startup alone resolve distribution provenance.

## Preservation and remaining gates

Measured package remains `build/m1-release-20261104/attempt-06/` from 248b510c,
ZIP SHA-256 d38b452f5102d10060c86c0244f50afecb4bdb16f386b28aeb42b9af9e51fd41.
No baseline package, runtime, source product, icon, native profile or retained
failure receipt was changed. Recovery 987cba84 remains historical and was not
merged/cherry-picked. Keep all earlier repeatable-build and native evidence.

R2 is in preparation, not closed. R3 resource acceptance, R4 final candidate
verification and R5 handoff/publication remain open. Delivery location still
needs selecting before handoff. No release/tag, installer, updater, signing
configuration or extra publication permissions were created. Documentation
closeout uses [skip ci]: no executable/workflow/test input changes after the
successful Action-refresh run. Local diff/link and evidence reviews cover it.
