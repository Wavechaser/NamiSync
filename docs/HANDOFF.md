# Latest session — Plan limits and copy-only throughput, 2026-11-06

Base `8628a5b9`, branch `milestone1`. Preflight now charges reviewed operations
once. Every derived source, target, prior path and parent remains scoped to
that Plan. The original dry run now saves 100,000 copies and 1,000 directories
with 202,000 observations and can proceed to explicit review. Its empty target
and private databases were removed. The core, preflight and workflows gates
passed 2,191 tests with one skip. Receipts in `build/coverage-study-20261106/`:
`refusal.json`, `fixed-plan.json` and `fixed-plan-tests.xml`.

The page retains the terminal refusal on release and reselection. A focused
WebView2 journey exercised a real refusal on a small fixture, with no target
changes and normal exit. All 65 frontend checks passed. Evidence:
`build/refusal-ui-20261106/runs/refusal/verified.json`.

The performance envelope is 100,000 + 20,000. Best-effort capacity reaches
150,000 logical rows and 300,000 ordered results. A real 130,000-file dry
run saved all 131,300 operations. A separate runner test retained every one
of 260,000 distinct copy/verify receipts in order. The new pair is ledger
v4/history v8, epoch 8. Starting on a previous pair requires the documented
manual archive-and-start-fresh procedure; the compatibility test used
disposable databases from the previous DDL and confirmed byte-for-byte
preservation after refusal. No existing user database was changed.

The new 150,000-row refusal reached the card and panel on a private desktop.
The first attempt timed out before terminal release; its log did not pinpoint
the stall. The instrumented repeat confirmed the current limit, no additional
Plan read on reselection, disabled Execute and normal shutdown. See
`build/scale-headroom-20261106/plan-130k.json` and
`build/scale-headroom-retry-20261106/runs/refusal/verified.json`.

On the integrated source, the ordinary suite passed 6,390 with four skips
and all 12 import contracts passed. The installed private-desktop suite
passed all 11. The full input-desktop gate passed 33/35 in one invocation.
The Windows accessibility probe lost its HWND before seeing Ready, then
passed alone. The larger execution journey failed its exact-branch host
receipt check after its browser assertions passed; it passed on the private
desktop. The failed receipt does not identify the individual missing fact.
All 35 distinct cases have passing evidence across runs. Retain the failed
full-gate receipt for the next candidate's release check. Receipts in
`build/scale-headroom-20261106/`: `ordinary.xml`, `background.xml`,
`headed.xml`, `native-retry.xml` and `larger-completion-checks.json`.

PERFORMANCE records the copy phase alone on frozen sources `23589bd` and
`a91bf617` using identical input and target drives. The 10-directory corpus
ran at 3.18–3.22 ms/file in the current rig, 4.09–4.15 through the service
and 6.53–6.95 with the Plan visible. A test-only poll delay reduced the
visible executor time to 5.23 ms/file; no production timing was changed.
Evidence and exact-hash receipts: `build/copyonly-20261106/`.
