# Latest session — AB-3 integration after performance tools

2026-09-25; `milestone1`. The full AB-1–AB-10 batch remains active. AB-1 is
`29d9b8f`; AB-2 is `8ba38ced`. This checkpoint integrates reviewed AB-3
`c5f1de8` from `codex/ab3-mapping`; conflicts were only shared status/changelog
documents. Both delivered outcomes remain intact.

AB-3 removes unused historical mapping readers. The live scan-scoped query,
planner ambiguity/hardlink safeguards, schema and history remain unchanged.
Its isolated gate passed seven focused cases before/after, 1,331 department
tests and 12 import contracts, plus independent review. Evidence lives in
`build/post-m1-8-ablation-20260925/ab3-worktree/build/ab3-mapping/`.
The integrated tree passed the same seven focused cases and all 12 import
contracts; `ab3-integrated.log/xml` and `ab3-integrated-imports.log` retain results.

AB-2 optional tools passed 5,302 ordinary tests (four unavailable symlink/reparse
privilege skips), all 33 installed interface tests and 12 import contracts.
The later stronger COPY-ID assertion passed its focused rerun. Selected current
Plan, receipt/UI and history cases completed; the bridge diagnostic timeout
remains incomplete with unknown cause and no v5 repair claim. Historical JSON
is unchanged. Its migration, review, raw reports and gate logs remain under
`build/post-m1-8-ablation-20260925/`; PERFORMANCE owns methods and limitations.

Next: refresh `ab4-design.md` against this integrated tree and implement AB-4.
The existing projection already carries immutable membership; retain identity
and revision checks while replacing the unused full desktop preview. Preserve
D2/D4 decisions and the other pending checkpoint boundaries. Keep the AB-3
worktree and branch until final integration accounting; preserve unrelated
work, raw evidence and stashes. No DOC-2 rewrite, push or PR is authorized.
