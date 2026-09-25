# Latest session — AB-5 bridge response adoption

2026-09-25; `milestone1` at integrated base `9cfd2a0`. AB-1 is `29d9b8f`,
AB-2 is `8ba38ced`, reviewed AB-3 `c5f1de8` was integrated in `dd23c270`,
and AB-4 is `9cfd2a0`. The AB-1–AB-10 batch remains active. The AB-3 worktree
and branch remain for final accounting.

AB-5 keeps hostile response capture and exact byte admission before touching
detached values. Ordinary response projection and `to_primitive_view` now
perform registered semantic validation during that owned projection walk,
without re-invoking nested registered validators beneath a validated view.
The typed continuation and drain-prefix validation paths remain intact; drain
validation still completes before queue consumption. Browser native detachment,
whole-batch decoding and identity checks remain separate adoption boundaries.
The private projector requires an explicit validation mode at each entry, and
no extra primitive drain graph is retained. One shared-alias/caller-detachment
witness was added. This removes a repeated generic walk without claiming a
line-count, timing or memory reduction.

The 67-case focused baseline passed before and after; 228 selected response,
serializer, codec and drain cases and 14 added refusal/decoder/continuation
cases passed. Ordinary passed 5,306 with four unchanged symlink-privilege skips;
six installed transport cases, 12 import contracts and independent review passed.
The first installed run selected an old source directory and failed five tests
through the shared fixture; an unchanged retry passed all six. Preserve both
receipts and `ab5-picker-failure.md`; the native picker navigation cause remains
unconfirmed, with no product or harness repair claimed. AB-5 is delivered in
this checkpoint commit. Next is AB-6's installed gesture characterization and
contained second-load behavior; `ab6-design.md` is read-only preparation.
Commands and raw outcomes are in
ignored `build/post-m1-8-ablation-20260925/ab5-verification.md`; the read-only
design and AB-4 refresh are in `ab5-design.md`. M1_PLAN owns the finite scope
and gate. Preserve history write/readback, workflow authority, raw evidence,
unrelated work and stashes. Do not start dependent AB-8 implementation before
AB-5 and its other prerequisites complete.
