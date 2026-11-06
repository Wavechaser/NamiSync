# Latest session — Headed coverage and package diagnostics, 2026-11-06

Base `beed6c7a`, branch `milestone1`. The packaged resource driver now
discovers an ephemeral DevTools endpoint in the new run profile, checks the
browser PID against the launched Job, then binds its page session. The
`48b1f708` rebuilt package passed a one-file Plan/Execute with verification,
mirror equality, exit 0 and an empty Job. A foreign-Job control was refused.
Evidence: `build/cdp-isolation-20261106/`. Nine focused tests passed; the
tools department also reported two stale table-loading instrumentation cases.
The corrected anchor hooks the same post-render point. All 424 applicable
tools tests subsequently passed, with three skips.
Keep the old driver's identity with its existing measurements.

Run `python -m tools.headed_background` from the project venv for unattended
installed page coverage. All 11 cases passed together in 156 s. An external
observer saw the same foreground HWND throughout with no cursor movement and
found the app and WebView windows on the named private desktop. The native
picker separately delivered a real blur that dismissed the open row menu.
An earlier larger-window trial failed a completion assertion after both syncs
and verifies had completed. The focused repeat and combined gate passed; the
specific earlier failure remains unattributed. Evidence: `build/bg-private-final.*`,
`build/bg-interrupt.log`, `build/bg-cleanup-smoke.xml`. The full interactive
release gate still includes cases beyond either marker.
The complete interface headed gate passed all 35 on the input desktop. The
ordinary suite passed 6,378 with four skips. Receipts: `headed.xml` and
`ordinary.xml` in `build/coverage-study-20261106/`.

Earlier package/fixture receipts remain under
`build/resource-study-20261106b/` (full, smoke, retention, debug100k). The
100k scale refusal and misleading retry guidance remain open in BUGS. R2
provenance, R3 resource judgment, R4 checks and R5 handoff remain open.
