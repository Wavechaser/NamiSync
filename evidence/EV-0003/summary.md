# AB-7 command completion without timed mutation replay — summary

Condensed from the AB-7 builder, reviewer and verification notes in
`build/post-m1-8-ablation-20260925/`. The outcome is commit `6287db0c`
("refactor(web): simplify command completion without timed mutation replay"),
based on `2b4a2214`, with 39 paths. BRIDGE, INTERFACES, DESKTOP_UI and TESTS
hold the resulting contracts.

## Outcome

- **Native.** A read-only `observe:<request_id>:<command>` control uses the
  existing dispatch entry and the original command's current OPEN admission and
  trusted-origin check. It never invokes the original handler and allocates no
  effect slot. Direct and async results stay in the existing 64-slot custody
  until their exact ACK or genuine document/host retirement. Request identity
  is bound before preparation, and a duplicate live request id is refused
  before a second effect.
- **Browser.** Mutations are observed, not replayed. There is a five-second
  delay notice, then at most three read-only observations, and a later result
  is kept for adoption. Nothing resubmits the original request, and results are
  validated before they are acknowledged.
- **Fixed unknown outcomes.** A captured exact `internal_error` or
  `response_too_large` after a possible effect is noncheckable: the result is
  ACKed, transport custody is retired, and there is no Retry. The affected UI
  intent stays fenced until the user closes and reopens.

## Important corrections

1. **Recurrence review (four grouped mechanisms, user-approved).**
   - A captured fixed error was mislabeled as checkable delivery loss.
   - An uncertain Close dropped the fence on replacement work.
   - Replacement location gestures and Add pair bypassed an unresolved folder
     outcome.
   - A timed-out read lost its cleanup ACK; it now keeps a bounded cleanup-only
     entry.
2. **Native ACK owner.** Replacing the completion-ACK lookup had excluded the
   read-only `probe_recent_pairs` async path. This was corrected with a focused
   witness: 286 tests passed before the correction, 287 after.
3. **Opus 5.5 review**, cumulative list cost $7.09:
   - stale Plan-again tracer anchors;
   - a stale cosmetic policy test;
   - a review fence that removed Cancel and Close for the session;
   - a Close button that stayed enabled but did nothing.

   Blanket fence removal was rejected because controls have domain effects.
   Instead, one separate Cancel is allowed after a fixed unknown review
   outcome, and a shared Close-block reason drives both the rail button and the
   handler. The same-session follow-up found no remaining blocker. Together
   with a CSS rule that overrode the hidden theme Retry button, these findings
   reached the recurrence threshold. Work paused and the reorganization was
   reviewed before resuming.
4. **Helper migration.**
   - The tracer now hooks the observed branch and keeps the Close/start fences.
   - The timeout probe asserts exactly one completion ACK.
   - The transport fixture targets the post-dispatch feedback timer.
   - The Setup diagnostic re-raises its original exception.
   - The task-shell helper now waits for Notice text, cleared review pending
     and an enabled Plan again before its single click.

## Verification

- Focused: frontend UI probes 56/56, transport 130/130, drain probe 1/1, native
  bridge/commands 287 (independently rerun), Node probes 3/3.
- The first complete run (5,257 passed, 73 failed, 28 errors) used a
  repository-local basetemp. That tripped the pycache/source-tree guards,
  causing 64 of the failures and all 28 errors. The affected files passed
  outside the repository: 189 passed, 3 skipped. The remaining nine failures
  were stale helpers.
- The final complete run passed 5,353, failed 3 and skipped 4, with every
  ordinary case passing. The normal-asset installed rerun passed 33 of 34. The
  task-shell rerun passed 2/2. Installed coverage is therefore 32 unaffected
  cases plus the two task-shell cases, not one clean all-suite run. Twelve
  import contracts were kept.
- An early packaging failure (34 setup failures after `bridge.js` changed
  between wheel build and install validation) is invalidated packaging, not 34
  regressions.

## Unresolved limitations

- **Default-shell Plan Again** (final complete run). Task 53 was created,
  selected and rendered. Then the keyboard focus re-entry wait observed
  `document_has_focus: false`, with the failure site at CDP lines 9/490. The
  actor is unknown. The retained receipts in `data.json` record that state.
  The mapping scripts are in the `incident-trace` candidate.
- **Larger-shell first Plan Again timeout** (33/34 rerun). There is no
  failure-site snapshot. A text-only wait could click before review pending
  cleared, but that is a helper precondition, not a proven cause.
- **Setup mixed batch.** A real normalized start error remains unclassified.
  Unknown-effect behavior was correct in the failed receipt. Later passes
  cannot prove the earlier start failed before any effect.
- **`pick_folder`** has no lost-return recovery; this is documented rather
  than fixed with a timer.
- These are fake-DOM and installed probes. They make no compositor-health
  claim.
