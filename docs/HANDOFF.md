# NamiSync Session Handoff

Date: 2026-08-03
Branch: `milestone1`

## Session Outcome

Corrected the cancellation classifier introduced by the durable-retry fix and
made the policy-Stop settlement sweep cancelable.

- **An intact owned temp is decisive non-publication evidence.** After a failed
  COPY publish or UPDATE replace, a foreign process may create or rewrite the
  target during retry backoff. If NamiSync's matching staged temp still exists,
  cancellation now settles the operation `CANCELED`, records the unexpected
  target state, removes only the temp, and leaves recording `OK`. It never
  claims `canceled-after-publish` for the foreign mutation.
- **Positive publication evidence is explicit.** The classifier first trusts
  the continuation's synchronous `published` flag, describes the target against
  cached `published_stat` when available, and uses consumed-temp plus a present
  target only as the committed-but-raised fallback. Post-publish metadata
  changes therefore no longer degrade otherwise reliable durable-state detail.
- **Unknown is not silently promoted to published.** If neither the owned temp
  nor positive publication evidence can classify the state, the item fails with
  its target-drift/target-missing/I/O reason, reports `publish_state=unverified`,
  preserves any known UPDATE backup detail, and does not degrade recording or
  claim NamiSync publication.
- **Policy Stop remains authoritative but interruptible.** A latched pause is
  still suppressed after a failure-policy `Stop`; the later `policy-stop`
  outcome sweep now checks cancellation before each status emission while
  ignoring pause. A large plan therefore does not delay cancel until every
  remaining item event has been emitted.
- Updated `BUGS.md`, `EXECUTOR.md`, and README to state the corrected evidence
  hierarchy and cancel behavior.

No payload, schema, persisted continuation, or public bridge type changed.

## Verification

- Focused executor suite: `157 passed`.
- Executor/dispatcher/resume/payload integration selection: `303 passed`.
- Full repository: `886 passed in 30.38s`.
- Import boundaries: all eight contracts kept, zero broken (50 files and 183
  dependencies analyzed).
- Package health: `pip check` reported no broken requirements.
- New regressions cover foreign UPDATE writes after a failed replace, foreign
  COPY destinations after a failed publish, a genuinely unclassifiable missing
  temp/target state, cached post-metadata published evidence, and cancellation
  partway through a policy-stop outcome sweep.

## Immediate Next Context

`BUGS.md` records the classifier regression as fixed. Stage 6 remains the next
product delivery: implement the pywebview/WebView2 desktop shell in the slice
order and against `M1_BRIDGE.md` and `DESKTOP_UI.md`.

Preserve this cancellation evidence order in later executor work:

1. `continuation.published` is decisive positive evidence after a publish call
   returned successfully.
2. A matching intact owned temp is decisive negative evidence because
   `publish_new` and `replace` consume it. Target drift cannot override this.
3. With no intact temp, a present target is the fallback for a publish that
   committed before its call reported failure; compare it to cached
   `published_stat` for descriptive detail when available.
4. If state remains unclassifiable, fail under the observed drift/I/O reason.
   Do not claim `canceled-after-publish` or degrade recording without positive
   evidence that NamiSync published.
5. Policy Stop suppresses pause, not cancel. Keep cancellation observable while
   settling the remaining status-only `policy-stop` outcomes.
