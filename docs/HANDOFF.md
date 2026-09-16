# Latest session handoff

## M1-7 completed measurement run — acceptance failed (2026-09-15)

The user authorized one fixed measurement run and required a stop/recap regardless
of result. That run completed all 175 children; strict quantitative validation
failed. No retry, repair, further investigation, refreeze, merge or branch pruning
followed. Work remains on `codex/wip-20260914-1600-m1-7`, based on repair commit
`325b0a6`. All previous commits remain unchanged; `milestone1` remains `40ca76f`.

### Result

The artifact has 35 metrics and 775 samples (55 cold, 720 warm), with 175 distinct
child IDs, launch tokens and process identities. All incremental receipt hashes
match the terminal artifact; the collection is complete. Authority and full
35-case readiness remain valid. This establishes complete evidence, not acceptance.

The strict validator stopped at the changed-search maximum exceeding 3 seconds.
Independent calculation with the unchanged statistics found 12 failing metrics:

- All ten changed-window cases (search, filter, collapse, reset, and six sibling
  sorts) exceed both 1.5-second p95 and 3-second maximum limits. Observed p95 spans
  4.396–6.143 seconds; observed maxima span 4.415–6.258 seconds.
- Incremental projection/staging memory: 525,881,344 bytes versus 335,544,320.
- Typed execution-start receipt: p95 520.4 ms versus 100 ms; maximum 523.7 ms
  versus 250 ms.

The other 23 metrics meet their criteria. No cause is assigned here. First child
receipt creation to terminal artifact write took 6,099.423 seconds (about 102
minutes); this excludes earlier wrapper setup.

### Evidence and preservation

Run directory: `build/m1-7/evidence/framework-20260915-155500/`.
Canonical raw artifact: `tests/interfaces/web/m1_7_plan_measurements.json`.
Raw SHA-256:
`345c2fcc14517218ce57741967594cb10ce690e6696604e69a619af22df50c13`.
Authority SHA-256:
`e068a5d36045247f0329a20251d13dee97e693d8d7eb1143030c79db3f2cef63`.
Readiness SHA-256:
`80693eb505fe89764e540cdd66722a26087a3100477570f842f7d11345d51562`.
The complete index and individual receipts are under `workspace/measurement*`.
`strict-validator.txt` retains the validator failure; `measurement-derived-review.json`
lists all 35 observed statistics, maxima, budgets and pass/fail comparisons.
`run-completion.txt` records the tool-reported exit 0. The successful runner
emitted no stdout/stderr, so there is no `run.txt`; this does not replace or
invalidate the canonical measurement receipts.

Preserve the artifact and stop documentation in a separate recovery commit and
verified bundle. No changed budget or test authority may turn this failed run
into acceptance. Resume only after the user's next decision; M1-7 stays unmerged.

Prior readiness repairs remain in `325b0a6`: missing message-listener registration
and a 600-second watchdog only for the grouped readiness component child. All
measurement children retained 300 seconds. The run used unchanged installed
product/wheel/runtime/profile/fixtures and fresh measured child state. Earlier
failed attempts and all recovery history remain preserved in their directories.
