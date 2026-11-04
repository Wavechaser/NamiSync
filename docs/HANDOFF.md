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

## Post-commit native journey

Fix commit: `e2f482ae`. The requested accessibility-controlled journey passed
against its verified installed wheel after commit. With Target still focused,
one native down/up reached Plan ready without preparatory blur, a second click
or manual help. The captured native window shows three Copy items, 278 bytes
and zero planning issues. No Execute was sent; source hashes were unchanged
and Target remained empty. Normal close exited 0 with an empty Job.

Evidence: `build/setup-admission-20261104/postcommit-journey/result-03.json`
and `plan-ready.png`. The 6.7-second diagnostic used UIA to locate controls and
read the settled Plan, with native input for the first click and no JavaScript
or CDP injection. The wheel SHA-256 is
`4c2d5b6dd24be22422929331e1a6cfa739ad34d66f84f04dadba61bffc4e837f`;
installed bytes matched before and after. Two earlier controller startup
failures (abbreviated commit identity and unqualified UIA assembly loading)
occurred before app launch and remain recorded. The corrected driver uses the
existing harness's qualified assembly identities and a whole-tree watchdog.
This is one successful first-click observation, not a repeated workload or
release-acceptance claim. Both diagnostic runtime roots and the three session
pytest roots were archived as needed and removed after process checks. Cleanup
receipts are `postcommit-journey/cleanup-result-20261104-161317.json` and
`pytest-cleanup-result-20261104-161340.json`; all five roots are absent. Native
screenshots, wheel/installation identities, failed receipts and fixture archives
remain in the evidence directory. No further test window is open.

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
