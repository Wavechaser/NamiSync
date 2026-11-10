# Latest session — R5 and M1 closed, 2026-11-11

The user handed administrative R5 closure to this session. M1_PLAN's
[R5 closure](M1_PLAN.md#r5-closure--2026-11-11) owns the decision record; this
file gives resumption context only.

## Outcome

- Final tester candidate is clean `b0a3fe133745b2212b8c7d1254c317879e980f90`
  (Package05). It is `1d936876` plus the `MICROSOFT-TERMS.txt` bundle file and
  guide pointers, followed by documentation-only commits. Portable ZIP SHA-256
  `652c55ca3c2ace0903732490ead0b907ac726dba5af4155aa5345db80c8e9efc`.
- The complete release command passes on that commit: 6,575 passed, 4 symlink-privilege
  skips, all 35 headed cases, 12 import contracts. The packaged Medium witness
  passes on the exact ZIP. Package05 reconciles against the commit and Package04.
- The tester set is in git-ignored `dist/v0.1.0/` (13 files, checksums verified)
  and in `build/m1-r5-20261111/delivery/`. Its release notes are short and
  M1-focused; the frozen START-HERE still calls the build a development package.
- `MICROSOFT-TERMS.txt` is the maintainer's own wording of the recipient terms.
  It was not legally reviewed.

## Not done

- Nothing was pushed, tagged, uploaded, signed or sent to testers. Delivery is
  the user's separate act.
- CHANGELOG/README keep `M1` headings. Switching to `v0.1.0 "Gertrud"` headings
  after delivery follows AGENTS' changelog rule.
- The user plans a separate README cleanup/revision; only status lines changed here.

## Evidence and retained state

Evidence root `build/m1-r5-20261111/` (README there defines layout):
`reconcile.json` (Package04), `reconcile-package05.json`, `acceptance/20261111-01/`
(setup, package, release), `portable/medium-20261111-01/receipt.json`,
`delivery/`, superseded `delivery-package04-draft/`.

- `build/m1-r5-20261111/checkout/` is a Git worktree at `b0a3fe13` with its own
  `.venv`; remove it with `git worktree remove` after final accounting.
- The Medium witness left its fixtures `F:\NamiSync-resource-repair-witness-20261111-01-d4ea4b42\`
  and `H:\test_dir\NamiSync-resource-repair-witness-20261111-01-2f706228\`.
- Earlier retained state is unchanged: frozen `acceptance-checkout` (`cfeac2d9`)
  and `idle-followup-checkout` (`1d936876`) under `build/m1-release-repair-20261110/`,
  recovery `ed18ad3e` on `codex/wip-20261110-release-repair`, R4 evidence
  `build/m1-r4-20261109/`, and old R5 delivery `build/m1-r5-20261110/`. No cleanup
  was performed; all of it awaits the user's final accounting.
