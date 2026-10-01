# Latest session — reviewed open-bug resolutions

2026-10-01 on `milestone1`, base `1d17883`. The three user-authorized outcomes
were implemented/disposed under execute-task and independently reviewed. No
worktrees or branches were created. M1_PLAN owns the compact outcome record.

## Delivered changes

- `c0f8da0`: optional replacement advice. Performance refuses overwrite with
  “choose a new `--json` path”; existing replacement callers retain their flags.
- `d8badc8`: bounded exception-retention closure without product edits.
  INTERFACES names host/document endpoints and the measured production-owner
  retention required to reopen. The earlier finalizer probe deliberately held
  its returned error and did not prove excess product lifetime.
- The identity fix shares the scanner's NTFS/ReFS predicate. Only failed
  `FileIdInfo` calls probe the handle filesystem; only confirmed other
  filesystems permit absent identity. NTFS/ReFS and lookup failures still raise,
  and successful queries add no lookup. Review caught the database consumer's
  unchecked nullable return; it now preserves identity-required `OSError`
  refusal and query-handle closure. No database identity guarantee was weakened.

The response-copy entry remains byte-for-byte unchanged. Native exFAT reader
compatibility does not relax the verifier engine's reviewed-volume identity
requirement: workflow verification can still refuse absent identity.

## Verification and operational context

- Ordinary suite: **5,733 passed, four skipped, 34 headed tests deselected**;
  the one warning concerns pytest cache-write permissions. All 12 import
  contracts and settlement **30 scenarios × three identical runs** pass.
- Native scanner/planner/executor COPY and UPDATE across all four NTFS/exFAT
  directions: eight successful cases, native unbuffered readback, then fresh
  NOOP plans. All task-owned K: and local fixtures were removed.
- Focused evidence: 354 core/executor-native/verifier-native tests, final core
  144, database 216, tools department 336/three skips, and four existing
  host/document lifetime/retry cases. Independent reviews approved each outcome
  and confirmed the database correction. Diff and 140 local documentation-link
  checks pass; no protected oracle authority changed.

Evidence root: `build/open-bugs-20261001/`. `identity-fix.json` and its probe own
the native matrix; `ordinary-external.log/.xml`, `imports-final.log`,
`settlement.log`, `database.log`, `doc-links.json`, `exclusions.json` and
`cleanup.json` retain final checks. Initial ordinary attempts are retained:
the default pytest temp directory was sandbox-inaccessible, then an in-repo
basetemp violated the custody harness's external-cache rule. Neither counts as
passed evidence. The final suite used a unique external temp directory, since
removed along with task-owned workspace test fixtures. Prechange receipts
`current.json` and `reader.json` retain their diagnostic provenance.

No further work is authorized on response-copy charging, whole-runtime memory
certification, verifier volume policy, or future M1 delivery in this task.
