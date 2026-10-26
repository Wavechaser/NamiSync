# Latest session — headline and startup refinement, 2026-10-26

User-authorized GUI round from `7015596a` on `milestone1`, using execute-task,
independent review and two serialized atomic outcomes. M1-12, release, DOC-2,
push and PR remain inactive. No task-created branch/worktree or recovery ref.

- H1 `fdc0e839`: ordinary rail/card headlines name the operation and share
  execution wording, while error/recovery and current-versus-retained activity
  exceptions remain. Rail details stay single-line; concise normal guidance
  and full exceptional text/tooltips preserve the available recovery actions.
  The gallery has three representative production-rendered task tabs: execution
  in progress, ready plan and execution completed with issues.
- H2: startup initiates one blank task after an empty initial list only if no
  task mutation overtook that read and no creation attempt remains. It reuses
  the existing creation/recovery path without blocking theme/default Setup
  initialization. Closing all tasks later leaves the app empty. Its ordinary
  New Task button uses the existing add-square-multiple icon, centered content
  and standard task-card dimensions; the top icon-only control remains.

No workflow/bridge/domain contract changed. Exact task creation/recovery,
current-session identity, reviewed effects, selection and controls remain.
No recent-path behavior changed. README milestone synopsis remains unchanged.

H1: 2,091 unaffected interface tests plus the corrected full Inventory pane
probe pass; all six installed obligations pass across native r2/r3. Independent
review approved. The three requested long headlines fit one line at 288 px rail
width and 14 px font; at the minimum 238.429 px rail, Execution completed with
issues uses two lines (132 px card versus 112 px). Other examples remain one
line; details remain one 16 px line. This preserves wording without shrinking
text. Failed legacy text expectations and inherited-error test-fixture receipts
remain in evidence; no product issue was inferred from those failed tests.

H2: eight focused startup cases pass. All five installed obligations pass:
initial gallery, Setup and execution default/larger in r2, shell in r3. Real
startup and empty button both measure 278.2857 by 112 px; centered icon/text,
native pointer and Enter creation, no replenishment after Close, 200% reflow
and forced-color focus pass. The final interface gate passes all 2,098 tests;
independent source, correction, native-evidence and documentation review approves
both units. H2 is the startup/empty-state commit containing this handoff.
Test-driver corrections preserve existing assertions: wait for seeded Setup
recents, use the established Enter input sequence, observe the unchanged empty
work accessible text, and restore focus after the added button focus probe.
Sandbox Temp/packaging setup errors and all failed native attempts are retained.

H3 read-only scope: Setup recents currently derive from sync runs. Inventory
locations persist but share registration with integrity and may survive later
recording failure. Querying observed locations needs no schema change but
broadens suggestions beyond Inventory use. Exact admitted Inventory-start hints
need an explicit bounded persistence/representation policy; current cosmetic
state deliberately excludes recents and newly admitted roots may lack durable
location IDs. A dedicated hint policy can avoid inventing Inventory run records.
Recent pairs can remain sync-only; all selected hints still need fresh admission.
No option is implemented or approved by this investigation.

Evidence: `build/gui-headlines-startup-20261026/receipts.md` and neighboring
focused/native/interface logs. Raw installed receipts are in external Temp
`namisync-headlines-h1-*` and `namisync-headlines-h2-*` directories. The owning
M1_PLAN row tracks final review/commit status; no native input guard was relaxed.
All requested GUI changes are complete; the recents item remains investigation-only.
No outstanding test gate, finding or task-created checkout remains.
This round does not declare M1 or release acceptance.
