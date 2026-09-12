# Latest session handoff

## Scrollbars and batch feedback (2026-09-12)

Baseline 1bbbeb4 on milestone1. User authorized implementation, review and
commits for GUI-S4/S5; broader batch housing remains investigation-only (GUI-D5).

S4 found a supported WebView2 FluentOverlay environment option in the bundled
SDK, but pinned pywebview has no environment-options initialization hook.
Browser flags are documented as development-only. No host, dependency, vendor,
environment or scrollbar CSS change was made. DESKTOP_UI records the supported
native route and CSS alternative; independent review closed this docs-only row
in 1159abc.

S5 is complete: 60px recent rows, matching 12px folder-column insets,
consistent disabled-cell hover, path-labelled batch rows scoped to their
originating task, and transparent dismiss removal before submission. The global 48-row bound,
single serial runner and exact uncertain retries remain. The origin and any
adopted task retain unresolved reconciliation through close/start guards and
action-guiding text. Queued removal is rechecked immediately before submission;
confirmed origin close clears its accounted rows. New tasks receive no old rows.

Independent adversarial review passed. Verification: 47 focused checks passed;
ordinary suite 4,979 passed with four existing skips; all 30 headed interface
tests passed; all 12 import contracts passed. Evidence is in ignored
build/gui-icons/gui-s5-focused-05.txt, gui-s5-ordinary-01.txt and
gui-s5-headed-all-01.txt. Native Setup checks include pointer hover/press over
both unavailable-row cells, 60px/12px geometry and labelled dismiss removal.
One pytest/Node slot, external unique basetemps and PIP_NO_CACHE_DIR=1 were used.
Direct consumer fixtures were migrated; no test module was retired. The older
same-origin form/batch interlock scenario is superseded by the stronger pending-
batch form-start guard; independent task forms were not globally serialized.
No worktree or recovery branch was created. The broader batch surface remains
discussion-only; a conditional bounded disclosure is the suggested next step.

Relaunch the development app after edits; do not close user-owned windows.
The WCG shadow finding remains diagnostic and unfixed in BUGS.md. Mica, bridge
security, domain behavior and release gates are unchanged.
