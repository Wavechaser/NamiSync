# Latest session — retention policy and evidence records, 2026-11-14 – 2026-11-15

The user ratified kind-based retention (PERFORMANCE "Evidence retention",
AGENTS structure table and closeout rule, DEFENSE Tier 2 wording): `build/`
must be clearable at any time; validated records are promoted to tracked
`evidence/` at session closeout. `python -m tools.evidence` (TOOLS "Evidence
records") allocates IDs, seals file hashes and checks the manifest and EV
citations. A fresh Opus review found two blockers (doc example breaking
`check`, unsorted/duplicate file lists passing); both were fixed and the delta
re-reviewed clean.

Round 7 removed the three secondary worktrees (HEADs on main), R5 packages,
`m1-token-audit-*`, gui-tuning HDR captures and everything not cited by a
lasting document, keeping M1_PLAN-cited text records as early-M2 reference.
The user's elevated rerun then removed all 1,347 sandbox-locked files.

2026-11-15 pilot compaction: the user added the rule that per-run records,
differentials, ledgers and Git-reproducible copies are not promoted however
small. EV-0001 (cleanup receipts) and EV-0002 (documentation compaction
checks) were pruned from 45 files / 411 KB to 20 files / 57 KB; both disposition
ledgers were dropped (one fixed reason per disposition; Git reproduces the
block map). `seal` now caps records at 256 KiB per file, 1 MiB and 24 files.
The survey working folder was deleted; build is 1.00 GiB / 18,627 files.
Evidence tests: 31 passed; `tools.evidence check` clean.

## Open items

- Promotion backlog, staged 2026-11-15 and not promoted (user: "don't promote
  any yet"): `build/evidence-candidates/INDEX.md` (working pointer) lists 36
  compacted candidates, 99 flat files / 1.04 MiB, from the lasting-cited study
  folders (~950 MiB, untouched). Each is README.md plus an optional authored
  `summary.md` (`_authored/`), `notes.md` (verbatim text under source-path
  headings) and/or `data.json` (JSON keyed by source path with original size
  and SHA-256). `spec.py` holds each pick; `reducers.py` holds the named
  content reductions (per-run aggregates, inventories as counts and hashes,
  SH-G-15 failure records, scroll statistics); `build_candidates.py` rebuilds
  them and checks `seal`'s caps. The 2026-11-16 content pass covered R2
  distribution/notices, executor simplification, planning PO3, exec-time,
  copyonly, AB-7/AB-8, root admission, M1-9, incident trace, resource and
  scroll studies; the remaining small records were not revisited. The user is
  reviewing per-claim adequacy before promotion, which then repoints the citing
  lines and deletes the source folder. No record (user, 2026-11-16/17): the R4
  package ZIP, icon archive, the cited `failure.png` (repoint its PERFORMANCE
  sentence to the failure mirror) and the inventory collector's profile and
  output. The M1-9 candidate is now summary-only and cited only by M1_PLAN's
  M1-9 row.
- The inventory cold collector writes to `build/inventory-cold/` (verified
  profile copied there). At the later `build/` cleanup, keep that folder and
  other likely-regenerated working files such as the icon archive.
- 55 empty folders under `build/move-history-20260925/` stay locked by old
  Codex-sandbox ACLs; an elevated `Remove-Item -Recurse` clears them.

Keep F:\NamiSyncExecutorBenchSource, the user's H:\test_dir\source and target
play directories including trash, and `dist/v0.1.0/`. Final candidate
b0a3fe13 / Package05, ZIP SHA-256
652c55ca3c2ace0903732490ead0b907ac726dba5af4155aa5345db80c8e9efc. M1 headings
remain pending external delivery.
