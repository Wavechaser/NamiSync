# Latest session — M1-R4 candidate run, 2026-11-09/10

## Outcome

Branch `milestone1`. R4's gates pass on final candidate `3ece185f`; closeout
awaits the user's SH-G-15 judgment. M1_PLAN ("R4 candidate run") holds the
decision record and PERFORMANCE holds the resource numbers. All evidence is under
the git-ignored `build/m1-r4-20261109/`.

- **Final candidate:** `package-2/` was built from clean `3ece185f` with the locked
  R2 recipe (`build_package_2.ps1`, `build-2.log` exit 0). Portable ZIP SHA-256
  `5b9163ce26b2a20734058069c03b966225be5bef6c7aac4b90477a54408f7319`.
  Against the soaked `1f632b13` package (`package/`), wheel and source members
  are byte-identical and executable payloads match. Only PE timestamps/checksums
  and install metadata differ (`package-compare.txt`, `exe-compare.txt`,
  `exe-bytes.txt`).
- **Release command:** `release-3/` on `3ece185f`, idle desktop, gives 6,556 passed
  and 4 symlink-privilege skips. lint-imports and diff check pass. All 546 BR-G
  and 81 SH-G cases pass. BR-G-44 is satisfied.
- **Task-shell fix (`3ece185f`):** the driver focused Pause while the closing
  execution confirmation still kept the page `inert`, so focus never landed.
  It now waits for the close and asserts focus. Product focus is unaffected
  (`focus-diag/` traces and `diagnostic.diff`; `release/` holds the original
  failure; `bisect/` holds the onset logs).
- **Gallery flakes:** `release-2/` and the morning reruns failed the component
  gallery intermittently in three forms while the desktop was in use. On an idle
  desktop, 11 instrumented runs (`gallery-diag/`, `diagnostic.diff`) and
  `release-3/` all pass. No change made; headed release runs need an idle desktop.
- **Witness:** `witness-08/receipt.json` passed on the final ZIP (`witness_2.py`),
  and `witness-07` passed on the first ZIP.
- **SH-G-15:** `soak/`, collected on `1f632b13` and applicable to `3ece185f`.
  All 17 runs are clean. The 100k peak (2.32–2.40 GiB) and the soak whole-app
  slope (+0.28–0.35 MiB/cycle, renderer +0.20–0.22 as before) exceed the
  historical yardsticks.

## Next

1. The user judges SH-G-15 on the measured behavior.
2. R4 closes with one reviewed closeout commit; R5 then reviews the exact
   `package-2/` candidate for tester handoff.

## Operational context

Diagnostic worktrees are removed. Resource and witness fixtures are registered
collector-owned roots under `F:\` and `H:\test_dir\`. They remain on disk, and
`resources cleanup --out <dir>` removes them on request. The corpus and
`H:\test_dir\source`/`target` were not touched. No push, tag, release or upload.
