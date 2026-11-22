# Scope, Findings And Recovery

Read this for a formal batch or accepted register row, a finding outside the
active scope, a question about a scope or ownership boundary, and any stop or
recovery. [AGENTS](../../AGENTS.md) keeps the always-on stop triggers; this
document owns the procedure behind them.

These boundaries apply with or without a skill. Execution skills define the
investigation, interaction, delegation and recovery procedure; they cannot
expand authority or relax repository gates.

## Scope and completion

- For a user-requested formal batch or an existing accepted register, record
  stable outcomes, dependencies, named verification, non-goals and task-specific
  stops in its owning delivery document. Before implementing a pending row,
  identify its owners and direct consumers, preserved guarantees, finite
  production/test/doc population, acceptance gate and commit boundary. Check
  relevant archived dispositions and likely regressions. Keep this proportional
  to the outcome; routine in-bound choices need no new approval. Explicit
  exclusions remain binding. Quantified criteria need a finite domain,
  procedure and terminal observation; discovery may instead close over a named
  corpus/method without authorizing fixes.
- Continue through implementation, correction of introduced regressions, required
  tests/docs and final adversarial review of every checkpoint. Completion means
  every accepted row passes its named gate without regressing the declared
  baseline. Resolve routine ambiguity from contracts and state material
  assumptions; ask when an outcome or boundary changes.
- Next-checkpoint design may overlap the predecessor's final implementation and
  verification, but stays read-only toward product/tests and cannot weaken or
  delay its gate. Record the inspected revision and revalidate changed seams
  against the integrated predecessor. Dependent implementation waits for its
  completion and active user scope; a future outcome or ready plan is not authority.

## Findings and scope decisions

- New findings do not add scope. Regressions are lost guarantees, false states,
  unauthorized/duplicate effects or newly unbounded work; test color alone proves
  neither their presence nor absence. Correct introduced regressions before a
  mergeable commit. A bounded pre-existing substantive defect may receive a
  separate fix commit only while no stop rule applies; log and defer other
  verified findings. A blocked gate with no authorized remedy needs adjudication.
- Only the user may change active scope. Suspend dependent work when an outcome,
  architectural ownership, safety/effect model or mechanism/verification boundary
  changes; do not split off a non-atomic commit to evade that boundary. Before a
  scope-only full stop, investigate a finite corpus covering cause, owners,
  dependencies and consumers (including external test helpers), preserved
  guarantees and verification. Present one coherent proposal, not successive
  first-failure additions. Investigation does not authorize implementation.
- A narrow understood extension preserving outcome and ownership/safety may seek
  an explicit in-turn decision. Larger architectural changes, unresolved
  boundaries or changed safety/effects require a full stop and reviewable redesign.
  Existing approval persists. While a decision is pending, only independent
  authorized work may continue. No answer within a bounded response window means
  stop and recover, never consent. Always-stop rules override investigation/waiting.

## Recurrence pause

On the **second unplanned instance of one causal mechanism**, or **third
unplanned substantive defect** in a pass/checkpoint, finish only the current
safety-preserving atomic outcome and begin no further instance fix. Produce a
mechanism table of consequences, owners and common choke point (or why none
exists); reorganize and obtain review before resuming. Narrow reorganization
may use in-turn adjudication, never waive the pause/review. Count mechanisms
semantically, not by BUGS category spelling. Predeclared finite migrations
are exempt from this recurrence rule.

### Sibling analysis

For sibling analysis in [BUGS](../BUGS.md), filter across owners using causal
terms as well as categories (`python -m tools.repo.bugs`), then read the complete
candidate entries and relevant current code/tests. Record the compared IDs,
population and exclusions. Exact category or text matches retrieve candidates;
they do not prove common cause, duplicate records, current defects or
applicability of a recurrence stop. Do not truncate entries to fit a batch; use
explicit record offsets/limits.

## Stops and recovery branches

The always-stop conditions are in [AGENTS](../../AGENTS.md#stops). Broad
checkpoints may add narrower stops with precise consequences/transitions before
work starts; only the user may expand them during a checkpoint.

If stopping before a merge-ready commit, preserve only task-owned changes on
an isolated disposable recovery branch with provenance, scope, verification
and excluded-work details sufficient for exact resumption. Never absorb or
destroy unrelated work. Recovery commits are not review units: never merge or
cherry-pick them as-is. Rebuild useful changes into coherent verified commits;
remove recovery refs only after review, integration and full accounting.
