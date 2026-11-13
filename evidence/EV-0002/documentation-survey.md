# M1 documentation compaction survey — 2026-11-11

Inspected tracked baseline: `f80773b5b1dfdded1df86fa9be87152ead599e1e`.
This is a proposal, not a completed rewrite. No build evidence was moved or
deleted. Further build cleanup is paused by the user.

## Census and diagnosis

| Document | Lines | Words | Headings | External inbound Markdown links, active / obsolete |
| --- | ---: | ---: | ---: | ---: |
| M1_PLAN | 2,760 | 28,678 | 67 | 19 / 11 |
| PERFORMANCE | 5,134 | 46,512 | 100 | 50 / 1 |
| CHANGELOG | 1,876 | 16,365 | 78 | 2 / 10 |

Counts exclude headings inside fenced code. Word counts split on whitespace;
link counts cover tracked Markdown, exclude self-links and distinguish
docs/obsolete sources. This is a structural survey with targeted content review,
not a clause-by-clause deletion authorization or validator for measurement facts.
The heuristic paragraph comparison found only three strongly similar pairs;
the main redundancy is repeated meaning and chronology, not identical wording.

- PERFORMANCE's first 2,119 lines of dated studies occupy lines 13–2,131.
  Executor/verifier methods and their accumulated studies occupy another 1,384
  lines; GUI-C5 mixes its method and follow-up results across 597 lines.
- M1_PLAN's three largest sections occupy 2,131 lines. Their headings disguise
  nesting problems: the 923-line pre-closeout section contains unrelated later
  GUI, planning and review batches. The 481-line Remaining checkpoints section
  contains delivered/investigated work. M1-Release alone has 727 lines.
- The eight largest CHANGELOG tasks total 871 lines. One desktop-review task is
  225 lines, the M1-10 task 120, portable packaging 111, and renderer work 106.
  They carry investigation, plans, intermediate fixes, test-count chronology and
  numeric results already described by the other two documents.

## Verified stale or misleading framing

1. PERFORMANCE lines 5,101–5,127 still describe current bridge timing as open
   and SH-G-15 budgets/artifacts as not established. Its own R3 renewal result
   at 3,481 and accepted R4 schedule at 143 document the later outcomes.
   Remove those obsolete current-status claims; keep historical qualification.
2. GUI-C5 at 2,517 describes a current-source observation before request
   coalescing, while later sections document the shipped coalescing and changed
   driver. Separate the reusable method from the dated baseline description.
3. M1_PLAN Remaining checkpoints is completed history, not an active work queue.
   R5 review and outstanding release decisions at 1,004 is historical input to
   the repair and final closure at 962; unresolved-at-the-time is not open now.
4. CHANGELOG portable-package bullets describe successive final candidates,
   open release acceptance, held closure and eventual closure together without
   a compact final disposition. Keep the final outcome and essential repairs.

These are documentation findings; no product failure is inferred from them.

## Proposed disposition map

Ranges below refer to the inspected baseline. Grouping is editorial, not a
claim that everything within a range can be deleted. Before rewriting, map each
removed block's unique decision, qualification or evidence pointer to its
surviving summary/owner or explicit historical disposition.

| Source population | Proposed treatment | Required survivor |
| --- | --- | --- |
| PERFORMANCE 13–187: Resources03/04, Close diagnosis and accepted R4 schedule | One release-resource family: final follow-up, accepted baseline, incomplete attempt | Exact build/runtime links; raw FAIL/incomplete versus user acceptance; missing-coverage resolution; unproven cause of original timeout |
| PERFORMANCE 188–737: DOM, GUI/headless, refresh and Follow studies | Combine into one rendering/copy-cost outcome table with qualified comparison rows | Shipped versus diagnostic-only variants; variance/non-causal limits; deferred ACK/cadence choices |
| PERFORMANCE 738–1,840: resource generations, root spelling, copy/verify, GC and retention | Combine resource generations into a comparison table; keep short mechanism/disposition notes | Profile differences, observer effects, no leak/cold-cache/speed guarantees, serial verification boundary, deferred alternatives |
| PERFORMANCE 1,841–2,131: early resource preparation, pilots and manual diagnostics | Remove obsolete next-step instructions; summarize original method limitations | Current reusable resource method from completed collectors; failed/partial runs remain identifiable |
| PERFORMANCE 2,132–2,181 and 2,195–2,448: planning/handle-relative/axis investigations | One historical optimization and unresolved-observation summary | Accepted logical-spelling/observation boundaries; physical axis-switch report remains unresolved |
| PERFORMANCE 2,182–2,194: retention | Keep and position near the front | Distinguish regenerable fixtures from receipts, unknown provenance and unresolved/user-owned data; do not redesign storage in this task |
| PERFORMANCE 2,449–3,090: reference profile and GUI-C5 | Keep reusable fixture/actions/observer/stats/rerun method; condense baseline and variants into tables | Corrected observer versus old observer; action/population identity; no invented latency gate; result-specific scope |
| PERFORMANCE 3,091–3,193: cold Inventory | Keep method; tabulate the two older results | Source closure, five-child/max procedure, exact 3/6 s criteria and independent checking |
| PERFORMANCE 3,194–3,507: historical observations and R3 | One current R3 result table plus profile-version history and shared procedure | Final cfeac2d9 results; unchanged limits/statistics; committed authority links; historical runtime qualification and SH-G-8 v2 meaning |
| PERFORMANCE 3,508–3,592: optional Plan/UI | Keep concise current case/fixture description | Advisory status and distinction from Inventory/custody/release gates |
| PERFORMANCE 3,593–4,976: backend methods and studies | Separate reusable executor/verifier/report/sidecar/cache/cleanup semantics from historical result tables; collapse per-commit experiment recaps | Mode/outcome validity, source stability, timed endpoints, allocation distinction, quiescence and rerun triggers; final qualified results and unresolved directions |
| PERFORMANCE 4,977–5,134: History/bridge/closing material | Keep family methods; combine old results; remove superseded preparation/status prose and repeated retention paragraph | Current event-v5 fixture meaning; historical v1 calibration/holdout versus v2 verifier; no custody-to-whole-runtime promotion |
| M1_PLAN 22–58: cleanup chronology | One current disposition with receipt pointer | Build cleanup paused; kept roots/worktrees; superseded recovery ref disposal; retention/storage redesign unresolved |
| M1_PLAN 59–539: completed November work | One delivered-outcome table, grouped by mechanism | Shipped behavior, deferred/rejected options, unresolved observations, owner and evidence pointers |
| M1_PLAN 540–1,266: release and repair | One completed R0–R5/RR outcome map plus final-candidate gate record | Package05 identity, dependency-scoped gate reuse, acceptance qualifications, release repair dispositions, delivery still separate |
| M1_PLAN 1,267–2,244: verification, consolidation, GUI/planning/review batches | Fold into a completed-checkpoint map; remove spent execution recipes and repeated gate transcripts | Stable outcomes, specific accepted residuals, future boundaries, rejected alternatives and evidence/revision pointers |
| M1_PLAN 2,245–2,314: accepted behavior and release completeness | Replace duplicated subject-contract narration with owner links and a short milestone closure record | Any uniquely accepted outcome first reconciled into its actual owner; final release status retained |
| M1_PLAN 2,315–2,760: historical batches/backend/AB/checkpoints | Integrate into the same completed map | No new future authorization; deferred/rejected choices and unconfirmed observations still discoverable |
| CHANGELOG all 68 task entries | Merge overlapping stages of the same outcome; shorten large tasks to delivered changes, essential caveats and evidence/owner links | Existing milestone/phase hierarchy and newest-first convention; task dates; final delivered outcome; no reproduction of gates/methods |

The 68 task entries count only level-four task headings. M0 history should be
kept; shorten it only where a specific redundant block is identified, rather
than deleting it because M1 is finished.

## Suggested final shape

- **M1_PLAN:** closed milestone identity and final gate summary; completed
  checkpoint/decision map; unresolved observations and explicit deferrals; current
  mop-up state. It remains the completed M1 decision record, not a new M2 plan.
- **PERFORMANCE:** scope/profile/statistics/retention; current measurement methods
  by family; current qualified result tables; compact historical comparisons and
  unresolved investigation conclusions. Methods precede dated results.
- **CHANGELOG:** existing milestones/phases, with concise outcome-based task
  entries. Exact trial matrices, every intermediate pass count and command
  chronology belong in evidence, not repeated in task bullets.

Provisional editorial budgets: M1_PLAN 400–600 lines; PERFORMANCE 1,000–1,400;
CHANGELOG 700–900. These are planning estimates, not acceptance thresholds or
grounds for dropping unique facts. Disposition completeness determines the
final size. Do not meet a line target by simply moving the entire old file into
a new giant archive. Git at the inspected revision already preserves old prose;
use docs/obsolete only for historical material that merits a maintained reader
entry point and has an explicit finite disposition.

## Boundaries and verification for a rewrite

Active external links consume seven distinct M1_PLAN anchors and 23 PERFORMANCE
anchors. Preserve meaningful short summaries at still-useful anchors, or update
their direct consumers when an obsolete heading is replaced. Six obsolete
sources link to M1_PLAN (eleven links) and one to PERFORMANCE; their links must also remain
resolvable or be deliberately retargeted to historical material. CHANGELOG has
two active whole-file links and no active incoming task anchors in this census.
The machine-readable census records every observed source/line/anchor.
Its heading/slug check also flags nine pre-existing unresolved references:
three internal PERFORMANCE links to the dated full-resource schedules, and six
links from obsolete/M1_BRIDGE to old CHANGELOG task headings. Confirm and
reconcile those destinations during the rewrite; they are not evidence of a
new regression or an instruction to edit unrelated obsolete prose wholesale.

Primary edit population: the three subjects, HANDOFF and session record.
README/subject documents need only direct link/index repairs or a uniquely owned
decision correction demonstrated by the disposition map. AGENTS ownership and
evidence rules do not need changing to permit this cleanup. No code, tests,
frozen JSON/authority, budgets or build contents should change. Search of tools,
tests and CI found document filenames in a historical raw dirty-status receipt,
not an executable dependency on these three documents; do not rewrite receipts.

Verification: baseline-to-survivor disposition review; current-status consistency
against final release records and subject owners; exact numeric/qualification
comparison for retained methods/results; Markdown path/anchor checks including
the affected obsolete consumers; diff checks; separate adversarial reread of the
changed text. Product tests are unnecessary while executable contracts and test
authority remain unchanged. New quantitative claims or changed authority are
outside this proposal, not incidental editorial corrections.

## Evidence

`document-survey.json` contains heading spans, line/word counts, inbound Markdown
links and heuristic similar-paragraph pairs. `survey_documents.py` produces it.
It does not decide what to delete. The original survey snapshot precedes this
session's administrative note updates; line references are frozen to its baseline.
