# Latest session — M1-9 delivered

2026-10-01–2026-10-02 on `milestone1`, original task base `937af54`.
M1-9 is complete. Stop here for the requested recap and GUI tweaks. M1-10,
M1-12, release and DOC-2 remain unactivated. M1_PLAN is the delivery authority.

## Integrated changes

- `ec3865c`: immutable inventory projection and shared sibling ordering.
- `12cae9b`: independent cold projection collector/checker and accepted evidence.
- `a84e816`: bounded inventory reads and fresh exact-row details.
- `687549a`: inventory desktop read pane and controls.
- `9266845`: same-task Refresh with original-result recovery.
- `978ddf1`: conditional acknowledge/restore with truthful partial dispositions.
- `910255f`: shared admitted-start identity for Plan, inventory, Plan again and
  pair batches; replace drains and fence older lists without confusing execution.
- `02d7595`: exact headed command catalogs and bounded native completion waits.
- `5cf18f8`: desktop Refresh/visibility actions and the narrowed installed witness.

Each outcome has independent review. The shared fix was committed first as the
user directed; desktop Refresh uses it. The witness uses producer-owned identity
and proves native clicks, replacement display, row hide/return and screenshot/
task/host Close. It does not independently reimplement ledger rules.

## Verification and evidence

All raw receipts and independent reviews are in `build/m1-9-20261001/`.

- `complete-ordinary-20261002.log`: 5,829 passed, four skipped, 35 headed excluded.
- `desktop-refresh-frontend-focused.txt`: 64 passed, six deselected; shared and
  Refresh lifecycle controls retain prior-red/corrected-green evidence.
- `native-wait-ordinary.log`: all 1,890 interfaces checks pass after test-only
  maintenance; unaffected ordinary evidence is reused by dependency.
- All 35 headed cases pass across affected runs: 30 unchanged existing passes
  from `complete-headed-20261002.log`, fresh AB-6 replacement/Close from
  `native-replacement-20261002.log`, transport from `headed-recheck-20261002.log`,
  two live-host gates from `native-wait-headed.log`, and the inventory journey
  from `inventory-headed-focus-ready.log`. No single aggregate invocation is claimed.
- `final-imports-20261002.log`: 12 contracts kept. Final local document targets
  and diff checks pass; link checking does not validate heading anchors.
- `cold-evidence-final-20261002.log` revalidates five samples per fixture and
  unchanged source dependencies: maxima 1.9712401/2.8123806 s below 3/6 s.
  No new timing was needed. User says the machine is idle.

The live-host test's ten-second local wait was a false refusal: matching native
navigation/popup completion arrived after 17.7/13.3 seconds in a bounded
counter-observation. Only three local waits changed; the sixty-second parent
bound and all semantic assertions remain. Actual acceptance runs passed after
that correction; diagnostic runs are not counted as acceptance. No DNS, browser
update, GIL issue or product security failure is inferred. Earlier failed and
incomplete receipts are retained.

## Preservation and immediate context

Recovery `4b936db` was never merged/cherry-picked wholesale. All twenty saved
paths are accounted for in `recovery-accounting.json`; the original recovery
patch is preserved and hashed. Its disposable branch was removed after final
closeout review approved the accounting. No worktrees or unrelated changes were created.
Thirty-four inventory receipt/identity files are copied and hash-verified under
`inventory-native-preserved/`; other raw evidence and external task Temp roots
remain retained. No fixture or unrelated filesystem cleanup was performed.

No native-input interval remains active and no further measurement is needed.
The saved inventory PNG is a browser surface capture with alpha, not acceptance
of native material appearance or GUI polish. The next interaction is the user's
M1-9 recap/GUI review, not implementation of the next checkpoint.
