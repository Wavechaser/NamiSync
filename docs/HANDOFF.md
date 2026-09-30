# Latest session — direct-write implementation activated

2026-09-30, milestone1-adelbert, base 2f1511f. The user authorized the direct-write
refactor after correcting held-root delegation, choosing a blanket 8 MiB
threshold across all devices. No volume/model discrimination. M1_PLAN owns the
active result8 boundary and preserved contracts; the measured device-specific
candidates remain historical diagnostics in PERFORMANCE.

## Delegation correction

The native delegation helper now accepts only concrete NativeFileSystem.
Subclasses retain runtime reviewed admission because their resolve overrides
need not admit the root. Public resolve contract unchanged; no method-identity
gates restored. A native lexical-only subclass witness fails against the prior
predicate (missing refusal), then executor coverage passes 620 tests with
5,118 deselected; all 12 import contracts pass. Fresh independent review found
no blocker in the correction and witness.
Evidence: build/executor-simplification-20260929/differential/delegation-subclass-*.

## Direct-write work next

Read-only design is tracing native/pipeline/runtime, shared contracts and direct
adapters/helpers. Implementation waits for the correction commit and a concrete
finite population in M1_PLAN. Result8 includes 8 MiB direct targets, bounded
buffer ownership, exact tail EOF/hash, capability fallback diagnostics, preserved
retained-handle durability/publication, create-new-first temp recovery, and a
synchronous single-chunk path. Existing import law and safety stops remain.

Previous accepted commits: d43f832 (version recognition), 6157226 (path composition),
878f15e (single-path dispatch), 2f1511f (threshold evidence). Previous result7
ordinary gate was 5,699/4 skipped/34 deselected; its receipts remain. The new
implementation will invalidate affected evidence and receive fresh gates.

Native tests run as actual user with default pytest temp. All historical and
failed receipts remain under build/executor-simplification-20260929/. Original
F source and unrelated b8baf42d worktree remain protected. Both earlier task
recovery branches were fully accounted and removed; no task worktree is active.
