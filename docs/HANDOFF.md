# Latest session — AB-1 documentation ownership

2026-09-25; execution baseline `6a55239` on `milestone1`. The user activated
the full [AB-1–AB-10 batch](M1_PLAN.md#post-m1-8-reduction-plan). AB-1 is complete;
AB-2–AB-10 retain their dependencies and
need no repeated activation. No product, test, tool or evidence JSON was edited
for AB-1.

[PERFORMANCE](PERFORMANCE.md) now owns methods, reference profiles, fixture and
sample rules, raw provenance and source-linked historical observations. The
component docs retain criteria, and [DEFENSE](DEFENSE.md#7-quantitative-evidence-and-measurement-authority)
retains evidence authority. AB-1 does not demote any executable gate. AB-2 will
move performance drivers with their consumers and make its named families
optional while preserving correctness, custody, settlement and SH-G-15.

[M1_PLAN](M1_PLAN.md) condenses completed M1/GUI/MOVE/study records and retains
DOC-2 and M1-9/10/12/Release pending. M1-8 A6 is closed from
`build/m1-8-archive-20260924/integration.json`: merge
`6c00ec731dd176d201e2a2c3a2a53b47652c544e`, tree
`f7691c518a31a160f888db299faa9342bd9a4349`, postmerge PASS.
The five earlier studies were already moved; no archive migration was repeated.

AB-1 verification: `ab1-checks.json` and `ab1-review.md` in
`build/post-m1-8-ablation-20260925/` record 320 links, independent figures/A6
trees, unchanged executable/evidence population and passing independent review
after provenance/routing corrections. Documentation-only checks suffice here.

Next: refresh `ab2-design.md` against the AB-1 commit and implement AB-2.
Its early characterization has five bridge source/schedule passes, three Plan
fixture/order/folder passes and one receipt-observer pass. The latter first hit
sandbox temp-directory denial, then passed unchanged with normal temp access;
both logs remain in the evidence root. These are not a full runtime gate.
Preserve raw JSON/log paths,
unrelated refs and stashes. DOC-2 branch rewriting, push and PR remain outside
this batch. D2/D4 and rejected/deferred dispositions remain in the current
register and study.
