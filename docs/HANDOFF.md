# Session Handoff

Status (2026-08-27): the power-loss recovery is complete. Checkpoint 3.3
remains committed at `092b628`; checkpoint 4 remains before its first required
reservation-model commit. The production command map still has exactly nine
rows, no task command or control has activated, and no analytical constant,
fixture, hash, or acceptance result has been frozen.

## Recovery and delivery

- The complete interrupted 19-path worktree, including untracked files, is
  preserved at Git object `33f699448b5940b2aa4b0464b3a238297c68ab86` and
  anchored by branch `codex/recovery-power-loss-20260827`.
- The live worktree returned to the last safe commit, `b457ef9`, before only the
  coherent adapter exception-retirement batch was restored. The interrupted
  planning implementation and provisional reservation model remain available
  through the recovery anchor but were not restored for continued development.
- `SessionObserver` now retires raw close/join failures and completed observation
  aliases before raising fresh fixed cleanup or timeout errors. A still-running
  observation remains owned only for the existing retry path.
- Service shutdown reduces observer-close failure to fixed ordinary/interrupted
  state before dispatcher and runtime closure. It preserves dependency ordering,
  incomplete-shutdown truth, and observer retry without retaining the private
  exception graph.
- Explicit task recovery reduces reobserve, validation, and stale-unsubscribe
  failure to closed codes before condition reconciliation. Unadmitted current
  views and private tracebacks retire; generation, queue, unsubscribe, release,
  and retry truth remain explicit.
- `INTERFACES.md` and `BUGS.md` describe the active mechanism and causal fix.
  The checkpoint plan and changelog now record this prerequisite closure without
  claiming checkpoint-4 model acceptance.
- The required-Node interfaces gate exposed a stale package identity vector from
  `b457ef9`: its fixture had changed from invalid `p` digits to valid hexadecimal
  `a` digits without updating the pinned SHA-256. Independent canonical JSON and
  `hashlib.sha256` calculation reproduced both values; only the expected test
  vector changed.

## Verification

- Final focused adapter files: **191 passed**.
- The first interfaces-department run passed **1,368** tests and exposed the one
  inherited fingerprint-vector failure unchanged in archived `b457ef9`.
- After correcting that stale vector, the required-Node interfaces department
  passes **1,371 tests** with **3,455 deselected**.
- No checkpoint-4 model, task lifecycle, command-map, or product-surface claim
  is inferred from this verification.

## Next work and preserved boundaries

Rebuild the planning source/retained-owner wall from `b457ef9` rather than
continuing the interrupted implementation. Use the recovery snapshot only as a
review source for exact snapshots, hostile-type cases, and pre-join diagnostics.
Keep unavoidable simultaneously retained owners, first-excess/no-partial
refusal, logical-byte overflow, and typed `REFUSED+UNRUN`; exclude dead
sequential temporaries and identity-sensitive duplicate-text estimates from the
runtime prerequisite.

After that focused prerequisite and its adversarial verification, close the
remaining source-derived workflow/callback owners separately. Then follow
checkpoint 4's ordered stops in
[M1_SHELL_H2.md](M1_SHELL_H2.md#4-install-task-centric-lifecycle-and-compact-artifacts):
model/validator first, dormant machinery second, coherent 12-row activation
third. The provisional recovery model's totals, hash, formulas, and fixtures are
not authority and must not be reused as accepted evidence.

Protected settlement and transport authorities remain unchanged. The active
database pair remains ledger v4/history v6 at shared data epoch 6. BR-G-45 and
SH-G-15 remain open, and the production command map must remain at nine until
the model and dormant-machinery gates pass.
