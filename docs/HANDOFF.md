# Latest session — AB-4 desktop selection handoff

2026-09-25; `milestone1`. The AB-1–AB-10 batch remains active. AB-1 is
`29d9b8f`; AB-2 is `8ba38ced`; reviewed AB-3 `c5f1de8` was integrated in
`dd23c270`. AB-4 started from that clean integrated base. The AB-3 worktree
and branch remain for final accounting.

AB-4's current candidate pairs a small immutable selection summary with the
Plan projection's existing workflow-owned selected frozenset. Service still
checks current artifact, selection state/revision/phase after projection build;
drain still checks task generation/retirement before publication. Direct leaf
resolution avoids folder-wide safety derivation, while folder expansion,
workflow mutation/admission and public CLI/API previews retain their contracts.
Eleven focused candidate tests passed after eight baseline seam tests; the
interfaces/workflows neighborhood passed 2,605 tests. Ordinary passed 5,305
with four privilege skips, four installed Plan/execute cases and 12 import
contracts passed. Fresh independent review found no blocking issue. The
candidate remains uncommitted pending final documentation checks and root
commit.

Next: finish documentation consistency/link/diff checks and commit one AB-4
checkpoint. The ignored
`build/post-m1-8-ablation-20260925/ab4-design.md` records baseline seams; the
current M1_PLAN row owns scope and status. Preserve raw evidence, unrelated
work and stashes. D2/D4 and future checkpoint boundaries stay binding; no
DOC-2 rewrite, push or PR is authorized.
