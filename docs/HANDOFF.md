# Latest session — M1-R4 candidate run, 2026-11-09/10

## Outcome

Branch `milestone1` at `1f632b13`. R4 ran in full on a clean candidate and
remains **open**. One intermittent headed-test failure blocks BR-G-44, and the
SH-G-15 judgment belongs to the user. No product source changed this session.
M1_PLAN ("R4 candidate run") records the decision state;
PERFORMANCE records the resource numbers.

- **Candidate:** `build/m1-r4-20261109/package/` was built from clean `1f632b13`
  with the locked R2 recipe (`build_package.ps1`, `build.log` exit 0). Portable
  ZIP SHA-256 `58429fa854c3161cd5e43bffeaedda05fc6373541430ece369009af40547478f`;
  `SHA256SUMS.txt` and the identity/origin JSONs sit beside it.
- **Release command:** `release/`, from `run_release.ps1`. 1 failed, 6,555
  passed, 4 privilege-capability skips (symlink/reparse, WinError 1314).
  lint-imports and diff check pass; the tree was clean before and after. All
  546 BR-G and 81 SH-G cases pass. Per-case results are in `release/cases.txt`.
- **Blocking failure:** `test_task_shell_headed[larger]`, `focusPreserved`
  False. A focused live Pause button drops focus to `body` during automatic
  Follow. Isolated reruns at HEAD fail in every attempt
  (`release/rerun-task-shell-*.log`). Worktree reruns (`bisect/summary.txt`)
  place the onset at `ea0daac2`; `b3095886` passed 8 of 8, and the commits
  between them are docs only. The suspected route is the deferred execution
  paint (renderTasks/queuePlanFollow) re-rendering an ancestor; this is not yet
  pinned. Bisect worktrees are removed; logs remain.
- **DESKTOP_UI mapping:** `ui_map.ps1` maps every criterion to passing cases;
  the only gap is this failure.
- **Portable witness:** `witness.py` drives Ready, About (0.1.0, 20 notices),
  reviewed copy, exact mirror, Integrity inventory, Baseline, Verify and
  close. It runs from Temp at medium integrity on a system-only PATH.
  `witness-07/receipt.json` passed. Attempts 01–06 failed on driver races and
  are retained.
- **SH-G-15:** `soak/`, `soak.log`, `soak-validation.json`. All 17 runs
  completed with exact mirrors and exit 0. The validator's FAILs are the 100k
  peak (2.32–2.40 GiB, about 1 GiB below `733f0cb1`) and the soak whole-app
  slope (+0.28–0.35 MiB/cycle). The renderer share, +0.20–0.22, is unchanged
  from the prior study.

## Next

1. The user decides on a fix for the focus regression. Any product fix
   invalidates the candidate's release, witness and SH-G-15 evidence. A new
   clean candidate then needs a rebuild, the release command, a `witness.py`
   rerun and the 17-run schedule (about 4.5 h).
2. The user judges SH-G-15 on the measured behavior.
3. R4 closes with one reviewed commit once BR-G-44 passes; R5 follows.

## Operational context

Evidence is under the git-ignored `build/m1-r4-20261109/`. The
resource and witness fixtures are registered collector-owned roots under `F:\` and
`H:\test_dir\`. They remain on disk, and `resources cleanup --out <dir>`
removes them on request. The corpus and `H:\test_dir\source`/`target` were
not touched. No push, tag, release or upload.
