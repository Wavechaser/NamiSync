# Latest session — incident repairs and closeouts

2026-09-27, `milestone1`, starting revision `a0205c08`. All four authorized
outcomes are implemented and verified; M1_PLAN owns the delivery record.
Evidence: `build/admission-bridge-closeout-20260927/`.

- `e8d3613`: AB-7 Plan-again focus loss is an environmental test limitation,
  removed from BUGS and retained in TESTS. The actor is unknown. Keep the
  enabled-button wait for the preceding asynchronous-filter request. No new
  focus/DWM detector, icon or helper change; the unrealized DWM sentinel is retired.
- `8f75f75`: AB-8 stack/wrap is deferred. TESTS retains the unconfirmed
  live-render/check race and qualified AB-7 larger-shell connection. CSS,
  assertions and the helper remain unchanged.
- `639b2ea`: database admission separates strict cold artifact validation from
  live SQL checks through two lazy runtime-owned role connections. Exact
  contracts, placement, independent history reads, fresh noncreating Plan,
  reader retirement and retryable shutdown remain intact.
- IR-BRIDGE, the commit carrying this handoff: current scalar/terminal shapes,
  ordered reliable witnesses, bounded failed reporting, durable original
  failure metadata, raw incomplete streams and cooperative synthetic cancellation.
  Production host/transport policy and frozen custody artifacts are unchanged.

Final ordinary suite: **5,380 passed, 4 privilege-related symlink/reparse skips,
34 headed deselections** (`bridge-ordinary-final.xml/log`). Installed Setup:
1 passed on unchanged DB product; all 12 import contracts kept. The 35 bridge
owner checks and CRLF page probe pass. Independent review covered source,
consumer fixtures, documentation and retained native evidence.

`bridge-full-final.json` is complete with valid measurement on archived
`639b2ea`: four valid sessions, 150 ordered reliable events each, terminal
event/record pairs, no gaps or browser failure, and monotonic progress.
Historical `passed`/`event_passed` remain false; no timing/custody acceptance
is claimed. `bridge-injected-report-failure.json` proves intentional rejection
after five accepted batches, original cause/report metadata and normal exit.
Its `.raw-incomplete` directory retains matching failure/final milestones,
authenticated samples and all four unfinished producer timing streams.

Retain the failed/in-flight receipts and review corrections: fixture migration
in the initial ordinary run, the control's punctuation expectation, and the
clean-incomplete raw-retention gap. Final review: `db-review.md` and
`bridge-review.md`. Reruns of the performance CLI need a fresh report name:
its existing overwrite refusal suggests an unsupported option; that separate
guidance defect is logged in BUGS and left unchanged.

Preserve `build/incident-trace-20260927/`, `build/trace-20260927/` and original
ablation failures. Reproduced mechanisms do not prove every historical cause.
No unrelated M1 checkpoint, remote update, stash manipulation or recovery cleanup
was included. Existing AB-10 recovery accounting remains under
`build/ab10-20260926/`; no task-created branch/worktree needs integration.
