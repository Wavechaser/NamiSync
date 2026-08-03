# NamiSync Session Handoff

Date: 2026-08-03
Branch: `milestone1`

## Session Outcome

Closed the three review findings raised against the previous audit-parity and
WebView2-detection hardening. No new subsystem behavior was introduced; each
change corrects a side effect of the prior commit or narrows a claim that was
broader than the code.

- **Separated audit producer backpressure from durable finalization.** One
  `audit_timeout` had been feeding three unrelated bounds — the finalization
  cutoff, the per-envelope `offer` enqueue wait, and hub close — so deriving a
  longer finalization cutoff from the writer retry silently multiplied how long
  a wedged audit writer could stall the emitting workflow thread on a full
  queue. `Dispatcher` and `EventHub` now take an independent
  `audit_offer_timeout`, and the service constant is required not to scale with
  the history writer.
- **Shortened the derived shutdown allowance from twenty-two to twelve
  seconds.** History finalization no longer reuses the ledger's generic
  ten-second serialized-writer retry. It is an independently degradable axis
  whose exhaustion costs one audit row and an honest `audit=DEGRADED`, never
  filesystem or integrity truth, so it now retries for five seconds. Every
  audit and shutdown bound scales from that value: the ownership cutoff is six
  seconds and default service close is twelve.
- **Named the prerequisite a WebView2 refusal actually found missing.** An
  absent .NET Framework release key previously reported that Edge WebView2
  Runtime needed installing. `missing_dotnet_framework` now selects a .NET
  4.6.2 message instead.
- **Documented the mirror's one deliberate divergence.** The same absent-key
  state is where the side-effect-free detector intentionally differs from
  pinned pywebview 6.2.1, whose `_is_chromium` raises `UnboundLocalError` from
  a `finally` that closes a never-bound `net_key`. The mirror refuses cleanly.
  Windows 11 ships .NET Framework 4.8 in-box, so the state is unreachable on a
  supported installation, but the parity claim is now exactly true rather than
  approximately true.
- Updated `BUGS.md`, architecture, dispatcher/history, feature, and
  interface/desktop contracts to match, including the Stage 6 obligation that
  service close must not run on pywebview's synchronous UI-thread callback.

## Verification

- Full repository: `869 passed in 27.78s`.
- Import boundaries: all eight contracts kept, zero broken.
- Composition values confirmed at runtime: history retry 5.0s, audit cutoff
  6.0s, offer bound 5.0s, service close 12.0s.
- New regressions: producer backpressure under a long finalization cutoff;
  offer/finalization independence and the shutdown ceiling; the absent-.NET
  upstream divergence; and which install message each refusal path chooses.

## Immediate Next Context

The open substantive bug in `BUGS.md` remains executor pause after a durable
retry sub-step. No executor code was changed in this session.

The agreed M1 design is to latch pause while an UPDATE or MOVE_UPDATE
continuation owns durable backup/temp state, finish that operation, then raise
`PauseRequested` at the settled boundary. Two refinements from review must
survive into implementation:

1. **The latency bound is honest, not wall-clock.** A latched pause rides out
   every remaining retry, not one. State the production budget as at most
   350ms of remaining retry sleep (50/100/200ms) plus up to three further
   guarded attempts, and note explicitly that filesystem calls, metadata
   repair, durability flushes, and recording stay outside any strict elapsed
   bound. Those further attempts perform no byte copying — both `_update` and
   `_move_update` skip `_prepare_copy` when a continuation exists — so the
   residual cost is rename, metadata, flush, and recorder I/O. Capping retries
   at one is rejected: it would convert a transient sharing violation into a
   permanent operation failure, making pause more destructive than not pausing.
2. **`stop_requested` interacts with the latch.** It is loop-local, so raising
   a latched pause immediately after settling a failed operation discards a
   policy `Stop` on resume. Decide explicitly whether a latched pause
   suppresses, defers to, or is suppressed by that decision.

The cancellation audit requested last session is complete, and the sibling is
more serious than an orphaned backup. It is logged separately and splits into
three cases with different remedies:

- `_cleanup_inflight` removes only `state.inflight_temp` and never a
  continuation's trash entry; orphan recovery never enters `.synctrash` and M1
  has no trash-purge workflow, so an UPDATE canceled after a pre-publish
  sharing failure retains its old-version backup indefinitely. Treat this as
  visibility plus deferred reclamation — deleting the backup during cancel is
  wrong, because after a committed `replace` it is the only copy of the old
  version.
- UPDATE can receive an error after `replace` already committed; canceling
  during that backoff reports the operation canceled although the new target is
  live. Under the four-axis rule the filesystem axis genuinely succeeded, so
  `CANCELED` is wrong on the axis that matters most.
- MOVE_UPDATE publishes the new target before installing its continuation, so
  canceling during an old-to-trash retry can leave new+old or new+trash while
  reporting `CANCELED` without published evidence. This one is unambiguously a
  filesystem/result truth mismatch and is classified severe.

The last two share the pause fix's insight and its code site: an operation that
owns durable state must not unwind without a settlement derived from that
state. Neither needs rollback — completed work is not rolled back and the next
scan converges — so both are reporting-and-recording fixes. Note that settling
such an operation as succeeded requires attaching `PublishedCopyEvidence` or
the XV-1 cardinality invariant fires; UPDATE computes its attestation only
after the failure point, so define the fallback before writing code.

For the fixes delivered here, preserve these invariants:

1. The production audit cutoff is strictly longer than the history writer's
   retry bound, that bound is strictly shorter than the generic
   serialized-writer bound, and default service shutdown covers both bounds in
   sequence while staying under the pinned ceiling.
2. Audit offer backpressure never scales with the finalization cutoff.
3. The finalization latch is claimed before history builds the payload hash, so
   live and retained audit axes cannot disagree.
4. WebView2 absence is decided before `create_window`/`webview.start` by the
   shared read-only detector, while renderer verification still runs first in
   the synchronous initialized callback.
5. Changes to the pinned pywebview detector must fail the executable parity
   tests and trigger a host security re-audit.
