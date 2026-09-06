# Latest session handoff

## Review pause

Paused after ST-2 by user request. Do not begin ST-3 until the user resumes.
The owning register is TEST_REFINEMENT.md; ST-H, ST-0, ST-1 and ST-2 are
complete. ST-3 through ST-6 remain pending. Use independent GPT reviewers;
consult Claude only when explicitly requested. Ignore the user-owned root
PRODUCTION_ABLATION.md while it exists.

## Delivered on milestone1-anthony

- `6c2dc6e`: ST-H replaces two child reinjection-chain deadlines with waits
  bounded by the existing parent scenario deadline. The separate dispatch
  admission wait remains unchanged. Delayed reinjection distinguishes the old
  failure from the repaired pass; missing reinjection produces no success and
  reaps the child and all eight observed descendants.
- `728f21f`: ST-0 requalifies the baseline and reconstructs the useful recovery
  documentation. The superseded `codex/wip-20260907-0015-test-refinement`
  branch was pruned after independent supersession review; its former commit
  was `c79aead`, never merged or cherry-picked.
- `f55e2d5`: ST-1 uses five named full-output guard fixtures. The analyzer and
  exact source-owner inventory remain intact. Review rejected a merged count
  bucket that allowed errors to cancel; both original
  and final fixtures reject the compensating fault, while the rejected
  intermediate fixture passes it.
- `4efba8f`: ST-2 shares database setup and SQL observations without merging
  the seven tests or their query roles. It corrects the predeclared masked
  source-filter fixture and retains batching, index, ordering, scope and
  snapshot obligations.

The test/harness diff is a diagnostic net increase of 29 lines: ST-H -2,
ST-1 +47, ST-2 -16. This is structural refinement with stronger explicit
coverage, not a bulk-reduction delivery. Production, dependencies, settlement
oracle and SH-G-8 evidence are unchanged.

## Verification and evidence

- ST-0 complete/headed suite: 4,670 passed, four WinError 1314 reparse/symlink
  capability skips; 12 import contracts kept, none broken.
- ST-1 final focused tests: six passed. Core department: 911 passed, one
  unchanged capability skip. All 18 declared old/new probes and the additional
  compensating-error comparison passed their attributed expectations.
- ST-2 final focused tests: nine passed. Database department: 365 passed.
  The 15 role-specific cases plus the corrected F6 supplement retain fault
  detection; raw F1 records its known masked pass separately from the corrected
  fixture's failure. Both snapshot callbacks reach their second batch.
- Independent review accepted both final implementations. All 123 fully
  protected files match frozen raw hashes; all eight protected function ASTs
  and normalized sources, and the exact owner inventory, are unchanged. Two
  ST-1 raw function segments differ only by CRLF-to-LF normalization.

Evidence is retained under `build/test-refinement/1026541/`: ST-0 in
`st-0/requalification-01/`; ST-H in `st-h/`; ST-1 authority is v3 and its
final formatting reconciliation; ST-2 authority is the v3 per-run-cache matrix
plus `probe-manifest-v4-f6.json`, final verification and
`final-protected-reconciliation.json`. Rejected attempts are preserved, not
credited. Source swaps need fresh per-run bytecode caches; exact exits and raw
assertions govern results, never arithmetic estimates. Precreate temporary
parents and capture receipts before pytest retention removes them.

## Resume context

The live `.venv` is stale. The qualified Python 3.13.14 environment is
`build/test-refinement/1026541/baseline/checkout/.venv/Scripts/python.exe`.
That full-history checkout remains based on `1026541`, with the three committed
ST-H/ST-1/ST-2 test changes copied in for combined verification. Its protected
product files were restored after every disposable mutation. Use its own cwd
and environment; explicit Node remains recorded in baseline evidence. Do not
repeat the complete suite solely to recover skip or receipt provenance.

Read-only ST-3 preparation is saved at
`build/test-refinement/1026541/st-3/preparation.md`. No ST-3 implementation,
manifest or tests have begun. Preserve independent observations when combining
fixtures; a mechanism assertion must not prevent its paired behavior from
running. Log and report latent product defects without fixing production.

The pre-existing README and CHANGELOG study edits and staged TEST_ABLATION.md
remain uncommitted and untouched by the checkpoint commits. Earlier handoff
content is preserved in `st-0-inputs/docs__HANDOFF.md`. Final task-level
changelog and ablation disposition reconciliation remain ST-6 work.
