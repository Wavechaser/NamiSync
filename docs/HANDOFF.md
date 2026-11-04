# Latest session — Setup admission and feedback, 2026-11-04–05

The user authorized fixing the blur/check/Create gesture race and centralizing
Setup feedback left of Add pair/Create. Create plan and inventory now retain
one attempt and await the row's current admission promise, including a recheck
of an accepted path. Both source and target in-flight results are retained at
attempt entry. Stale edits, refusal and double activation still start no extra
task. Add pair keeps its separately approved private-snapshot behavior and may
capture a row while its ordinary check runs; batch admission stays independent.

Setup path, action/recovery and frozen guidance messages share the action-row
feedback area. Source/Target/Root labels and accessible field descriptions are
retained; path rows and action buttons do not move when an error appears.
Mount selection and per-pair result cells keep their existing locations.
Checking folders remains in the existing task-status shell once Create begins.
No bridge, backend, execution authorization or package-release behavior changed.

## Verification and review

Evidence: `build/setup-admission-20261104/`. Focused browser probes reproduce
the old refusal and pass the shared-check, stale/refused result, repeated
activation, target-before-source settlement and feedback placement controls.
The installed Setup flow and both task-shell sizes pass (three cases), including
same-turn blur/Create activation and stable error layout. These witnesses use
the installed wheel, not the old portable package.

All 2,208 interface cases are accounted for: 2,204 passed in the department
run, and four failures passed after correcting two direct browser fixtures
(five focused passes including both bounded-diagnostics controls). One fixture
assumed synchronous setup admission; the other omitted the new row promise
field as well. Their corrections preserve lifecycle assertions and await the
actual deferred stage. Failed receipts remain, including a sandbox temp-root
refusal before the successful fixture rerun. Fresh independent review approved
the fix and its evidence; local links and diff checks pass.

## Immediate continuation

The user requested a small accessibility-controlled journey **after** the fix
is reviewed and committed. Its prepared driver and conventions are under
`build/setup-admission-20261104/postcommit-journey/`; do not claim it ran yet.
Reuse the verified current installed-wheel environment, send one down/up while
Target retains focus, observe Plan, then close normally. No preparatory blur,
second click or Execute is part of that diagnostic. The outer Job bounds the
whole controller and app tree. Preserve the receipt/screenshot and clean the
exact owned runtime fixture afterward; include final handoff in a follow-up
evidence commit if the result arrives after the product commit.

## Prior package context

Portable attempt-03 remains at
`build/m1-release-20261104/attempt-03/NamiSync-windows-x64-dev.zip`, SHA-256
`acc2c253057bce8af3c497053dfab3765da0621c9c507792b2aa4fb6e553bd69`.
It predates this fix and is not a clean release candidate. Prior behavior and
measurement evidence remains in `build/bughunt-20261104/packaged-round/`;
`continuation-native-20261104/summary.md` records the completed three sync/four
verification workload and its diagnostic limits. Prior runtime fixtures were
cleaned, while packaging-owned extraction/native profiles remain excluded.
The user's blur-race reconstruction prompted this fix; the earlier DPI failure
is not retrospectively classified. Longer/heavier resource acceptance, clean
release proof, dependency/notices/signing/distribution and GitHub CI execution
remain open under M1_PLAN. No push or release is authorized by this fix.
