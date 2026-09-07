# M1 Delivery Register

This is the sole active M1 delivery register. It records remaining accepted outcomes, their order, and the verification that closes each one. Implemented contracts are owned by their active subject documents; completed delivery history and superseded mechanisms are in [obsolete](obsolete/). The archived plan files retain historical staging and review but are not instructions for new work.

[BRIDGE.md](BRIDGE.md) owns external command, transport, retry/recovery, and bridge-gate contracts. [PRESENTATION.md](PRESENTATION.md) owns trees, views, search, selection, sorting, and scale evidence. [INTERFACES.md](INTERFACES.md) owns implemented task lifecycle and desktop host/package rules. [FEATURES.md](FEATURES.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [DEFENSE.md](DEFENSE.md) remain the owners of product behavior, cross-layer meaning, and safety/evidence policy.

[PRODUCTION_REDUCTION.md](PRODUCTION_REDUCTION.md) is the closed maintenance
subregister for the active production-ablation pass under M1-12. Its PR-0
through PR-9 rows remove redundant implementation and test prescriptions; they
do not add, defer, or reinterpret an M1 product outcome.

## Current boundary

The secured desktop host and transport, presentation foundation, current service/CLI surface, and implemented ledger/history boundary are active. The frozen v1 event-and-transport custody claim remains closed at its bridge evidence owner. That closure does not establish whole-runtime containment.

The following accepted user outcomes remain unrealized: process-live desktop task surfaces; shared location admission and frozen Setup; reviewed plan execution; execution and inventory projections; integrity controls and manual post-copy verification; and release closure. The history page, global-settings mutation page, drag-and-drop, file-scoped planning, durable task survival across a process restart, durable sort preferences, status/progress or global-flat sorting, and compare-and-accept rebaseline semantics are deferred.

The prior aggregate complete-owner-graph model and BR-G-45 are retired. No future work inherits its reservation, DTO, lease, byte-budget, command-count, or representation recipe. Before task lifecycle/retention work starts, a new closed register must define finite user outcomes, runtime enforcers, and named verification. Existing externally enforced ingress and population bounds remain active independently.

## Remaining checkpoints

Each checkpoint is a closed register row. A new finding does not enlarge a row; apply the repository containment rules in `AGENTS.md`. A change begins only after its row has named the relevant active subject contracts and finite verification. The row's verification is in addition to ordinary affected department and consumer checks.

| ID | Accepted outcome | Dependencies and named verification |
| --- | --- | --- |
| M1-4 | Define and implement a bounded process-live task lifecycle that retains reviewable results across navigation, separates terminal-session release from explicit task close, handles retry/staleness/concurrency truthfully, and shuts down safely. | Replace this row with a finite lifecycle register before implementation. Test claim, observation, stale session, retry identity, terminal reconciliation, release/close, worker/subscription teardown, and shutdown races through the public service and desktop path. Do not reactivate BR-G-45 or its aggregate reservation model. |
| M1-5 | Give Setup and inventory one workflow-owned location-candidate pipeline with typed admission results and bounded remembered locations. | Verify parser refusals; leaf/reparse/placeholder and long paths; missing, offline, remount, and clone ambiguity; bounded recents; activation/slot races and purpose mismatch. Review path parsing and TOCTOU. Scanner, preflight, executor, and verifier retain fresh re-probes. |
| M1-6 | Deliver frozen, backend-canonical Setup, typed/picker/recent inputs, standalone inventory creation, serial best-effort pair creation, and explicit Plan-again after fresh reviewed-identity resolution. | Verify bounded inputs, canonical snapshots, immediate invalidation, no global-default mutation or browser filter normalization, partial-pair refusal, mixed batches, replay/recovery, slot/plan-generation races, and headed hostile-text/picker/recent flows. Map needed command behavior in BRIDGE when this activates; do not prescribe the retired 18-command expansion. |
| M1-7 | Deliver bounded plan review, selection, execution admission, and the full plan consumer for sibling sorting. A review remains truthful when execution never ran and preserves first-ran finality. | Exercise plan publication, selection and commitment freshness, stale/replayed mutation, reopening/revision transitions, destructive confirmation, controls, windows/anchors/search/filter, and headed production flows. BRIDGE and PRESENTATION define protocol and projection criteria. |
| M1-8 | Deliver live and retained execution review with bounded item windows, exact execution overlays, task/item recording issues, terminal axes, and current ledger evidence. | Test filesystem/recording combinations, overlay and omission invariants, Gap plus terminal reconciliation, navigation/re-observation, generic unrun presentation, bounded evidence queries, and post-copy overlay independence. |
| M1-9 | Deliver bounded inventory projections, current evidence, and the full inventory consumer for sibling sorting. | Test complete or prior-complete publication, warnings outside action scope, raw evidence provenance, search/filter/collapse/window/detail behavior, replacement/races, supported sort/reset production paths, and headed witnesses. |
| M1-10 | Deliver baseline, verify, and rebaseline controls plus same-task manual post-copy verification without persistent operation-time hashes. Rebaseline includes eligible null-evidence files and always hashes/replaces evidence; matching content is not a verified match. | Test acknowledgement admission before claim/native work; all-null and mixed rebaseline through workflow, service/CLI, and desktop; conditional-recording and supersession races; handoff classification; pause/resume/cancel and remaining-subset retry; and overlay/result identity boundaries. Independently review the operation matrix and conditional-recording races. |
| M1-11 | Close the lifecycle and retention outcome defined by the replacement M1-4 register. | The replacement register names finite profiles, runtime enforcers, public behavior, and verification. No pre-existing aggregate-artifact or whole-owner-graph criterion closes this row. |
| M1-12 | Complete integrated adversarial, documentation, ordinary, and headed verification for activated M1 surfaces. | Run applicable settlement-oracle stability, ordinary/headed suites, installed-wheel/product witnesses, import checks, `git diff --check`, active-link checks, and independent review for requirement drift, security, lifecycle, executor, bridge, and presentation behavior. |
| M1-Release | Produce beta packaging and release closure after delivery rows above are complete. | Build/test an installed artifact from a clean checkout; supply frozen specification/dependency/CI, notices and corresponding-source release material, standard-integrity host proof, and every applicable BR-G and SH-G gate. INTERFACES owns host/package and SH-G release criteria; BRIDGE owns BR-G evidence. |

## Accepted behavior carried by the delivery rows

Location admission is workflow-owned and reused by typed, picker, and recent Setup/inventory inputs. A remembered location is not authorization; every consumer retains its point-of-use re-probe. Setup freezes its semantic plan options in a backend-derived snapshot and never writes global defaults or makes browser text/filter normalization authority.

Plan review must preserve operation, selection, scope, and fresh-preflight truth across view gestures. New views use canonical path-key order; filename, raw size, and raw mtime sorting in either direction and reset to canonical order are accepted M1 behavior. Sorting is process-live view state only and cannot alter selection, commitment, operation/dependency order, risk/counts, or action scope. It orders complete siblings before windowing and preserves node identity/hierarchy. Its exact protocol, validation, and scale evidence belong to BRIDGE and PRESENTATION.

Execution, inventory, and post-copy overlays stay distinct from each other and from ledger-derived state. A zero-byte activity that ran is never presented as unrun. Inventory warnings stay outside path/action scope and publication is complete or retains the prior complete generation. Baseline, verify, and rebaseline remain distinct operations. Rebaseline requires acknowledgement, includes eligible selected null-evidence files, replaces/creates evidence after a fresh hash, clears verification freshness, and does not become compare-and-accept. Manual exact post-copy verification uses an atomic handoff classification, works only on a ready subset, preserves original execution truth, and reports ineligible outcomes truthfully.

Release remains an accepted outcome. [INTERFACES.md](INTERFACES.md#sh-g-release-criteria) owns the open SH-G-15 scoped cold-start and repeated/long-workload resource policy. It has no numeric budget or acceptance artifact yet; runtime request/population bounds and the separate SH-G-8 transport-custody evidence remain unchanged.

## Release completeness

BR-G-43: active docs, README and UI/mockup status must describe shipped behavior.
Map every active DESKTOP_UI acceptance item to its subject check or an explicitly
approved deferral; an omitted item or copied unmapped checklist is not closure.
BR-G-44: from a clean checkout, run the complete suite including ordinary-default
exclusions, lint-imports and diff checks. All test_br_g cases must be collected
and pass without skip/xfail on Windows; narrow selections do not substitute for
release evidence. TESTS owns collection commands and routing. These requirements
remain open release obligations, not an assertion that this docs-only migration
performed a product release run.
