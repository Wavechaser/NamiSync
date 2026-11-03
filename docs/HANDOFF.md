# Latest session — CLI filename display and launchers, 2026-11-04

The console displays layout controls in filesystem text as ASCII code-point
markers and doubles a literal opening bracket. Review, execution and history
show the same spelling. The filesystem and ledger keep the original name.
The shared CLI/desktop cases include literal markers and ordinary Unicode.
The fix and the previously pending cleanup changelog entry are in `c5111740`.

The installed commands are `namisync` and `namisync-gui`. The project venv
has the refreshed editable installation. Other installations pick up the new
launchers when reinstalled. The module entry point is `python -m namisync`.

Verification receipts in `build/`: `cli-safe-department-20261104.xml`,
`cli-integrated-department-20261104.xml` and `cli-installed-integrated-20261104.xml`.
The installed gates cover Windows launcher classification, console/module
guidance and native host composition. The interfaces department exercises all
six subcommands and real filename round trips with UTF-8 and cp1252 output.

[M1_PLAN](M1_PLAN.md) retains the M1-12 baseline and release scope.
The build cleanup restore instructions are in `build/build_cleanup_*_summary.json`.
