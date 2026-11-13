# Latest session — retention policy and evidence records, 2026-11-14

The user ratified kind-based retention (PERFORMANCE "Evidence retention",
AGENTS structure table and closeout rule, DEFENSE Tier 2 wording): `build/`
must be clearable at any time; validated records are promoted to tracked
`evidence/` at session closeout. `python -m tools.evidence` (TOOLS "Evidence
records") allocates IDs, seals file hashes and checks the manifest and EV
citations. A fresh Opus review found two blockers (doc example breaking
`check`, unsorted/duplicate file lists passing); both were fixed and the delta
re-reviewed clean. Tools department: 504 passed, 3 skipped; 12 import
contracts kept; `tools.evidence check` clean with two records.

Round 7 removed the three secondary worktrees (HEADs on main), R5 packages,
`m1-token-audit-*`, gui-tuning HDR captures and everything not cited by a
lasting document, keeping M1_PLAN-cited text records as early-M2 reference.
Build is 1.21 GiB / 20,122 files. Promoted: EV-0001 cleanup receipts and
EV-0002 documentation-compaction verification.

## Open items

- Elevated rerun for 1,347 Codex-sandbox-denied files (temporary pointer; the
  manifests and executor stay in `build/mop-up-survey-20261111/` until done):
  `.venv\Scripts\python.exe -I build\mop-up-survey-20261111\execute_tiers_ab.py hdr-capture r5-package m1plan-workspace unretained`,
  then the same with `--verify` first.
- Not promoted, user decision: EV-0002's full disposition ledger
  `documentation-dispositions.jsonl` (1.6 MiB, over the 1 MiB file cap).
- Promotion backlog: remaining lasting-cited study folders (PERFORMANCE, BUGS,
  TOOLS, TESTS citations, ~0.9 GiB) need review/compaction before promotion;
  the BUGS stable-ID checkpoint receipts remain only in the survey folder.

Keep F:\NamiSyncExecutorBenchSource, the user's H:\test_dir\source and target
play directories including trash, and `dist/v0.1.0/`. Final candidate
b0a3fe13 / Package05, ZIP SHA-256
652c55ca3c2ace0903732490ead0b907ac726dba5af4155aa5345db80c8e9efc. M1 headings
remain pending external delivery.
