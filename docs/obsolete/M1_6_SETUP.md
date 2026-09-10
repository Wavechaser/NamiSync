# M1-6 accepted Setup study

Historical design and scope provenance for M1-6, based on `b98dce4`. This file
is not an active implementation plan. [M1_PLAN](../M1_PLAN.md) owns delivery
status; active subject documents own current behavior and future changes.

## M1-6 expansion

**Outcome.** Activate real Setup in the existing desktop task shell: complete
backend-canonical options, typed/picker/remembered roots, standalone inventory
starts, one serial best-effort pair coordinator, and explicit Plan again using
freshly resolved reviewed identities. The user authorized expansion and
implementation on 2026-09-11; stop before M1-7. This includes the inherited
GUI-D2/D3 notes, the requested unresolved rendering entry in BUGS, and condensed
M1-5 history, all in the final M1-6 commit.

**Finite production population.** `namisync/workflows/{inventory.py,models.py,
runtime.py,sync.py,views.py,__init__.py}`;
`namisync/interfaces/{service.py,task_lifecycle.py,task_port.py}`;
`namisync/interfaces/web/{slots.py,commands.py,drain.py}`;
`namisync/interfaces/web/assets/{app.js,bridge.js,panels.js,app.css,setup.js}`,
where `setup.js` is a new presentation module. No core/domain module,
dispatcher, database/schema/settings-store, native material, icon or asset
policy change is included. Existing package-data globs cover the new script.

**Finite test population.** `tests/{_service_fixtures.py,test_service.py,
test_bridge_service.py,test_task_lifecycle.py,test_workflows.py,
test_workflow_views.py,test_workflow_domain_checkpoints.py,
test_inventory_workflow.py,test_inventory_runtime.py,_departments.py}`;
`tests/interfaces/web/{_public_view_witnesses.py,_frontend_test_support.py,
test_slots.py,test_commands.py,test_drain.py,test_bridge.py,test_transport.py,
test_frontend_static.py,test_wheel_assets.py,test_setup_headed.py,
_setup_headed_child.py}`; `tests/assets/{app_startup_probe.mjs,setup_probe.mjs}`.
Exact command-table consumers and their child harnesses are also included:
`tests/interfaces/web/{test_host.py,test_native_host_gates.py,
test_transport_headed.py,test_bridge_event_benchmark.py,
test_component_gallery_headed.py,_transport_gate_child.py,_native_gate_child.py,
_component_gallery_child.py,_bridge_event_benchmark_child.py}`. Their namespace
and fixture migrations preserve the original behavioral and resource assertions.
Also include `tests/bridge_event_benchmark.py`,
`tests/assets/{bridge_timeout_probe.mjs,task_shell_probe.mjs}` and
`tests/interfaces/web/{test_task_shell_headed.py,_task_shell_headed_child.py}`.
The old empty-task-body assertion is replaced by real Setup content while its
navigation, selection and Close assertions remain. Protected transport
calibration/holdout/ceiling JSON is unchanged. Cosmetic-channel and launcher
command-name references were traced and require no migration.
The new collected headed module receives one department registration; existing
task-shell, picker, transport and resource witnesses remain. Other departmental
tests are verification consumers, not automatic editing scope.

The user's offline test/documentation preauthorization covers the additional
`tests/assets/transport_gate/transport.js` and
`tests/assets/bridge_interactive_probe.mjs` consumers. A complete `tests/assets`
search traced their old plan-start and picker-result shapes to the new command
contract; migrate only those fixtures while preserving timeout, origin and
transport assertions. `off_origin_start.js` uses an unaffected test-report
command and needs no change. Focused frontend and installed transport gates
verify this finite test-only extension.

Documentation is this register, BUGS, HANDOFF, BRIDGE, DESKTOP_UI, INTERFACES,
FEATURES, INVENTORY, WORKFLOWS, README and CHANGELOG. Edit only matching behavior
and status. The inherited dirty M1_PLAN/HANDOFF snapshots are retained under
ignored `build/m1-6/inputs/`; the explicit carry-forward authorization covers
their relevant content. No unrelated cleanup or separate documentation commit.

Closure may archive this accepted M1-6 study as
`docs/obsolete/M1_6_SETUP.md` while condensing the active completed record. This
single documentation-only addition falls under the user's preauthorization;
the archive is historical provenance, not another active delivery authority.
Verify its local links and preserve the shipped/excluded outcomes and gate
evidence in this register.

**Owners and design.** Workflow types and `FilterSet`/`SyncOptions` own complete
option validation and canonicalization. Settings only seed a draft; mirror has
no control and ADS is visibly unavailable/off without writing global settings.
One backend `prepare_setup` result freezes each batch
gesture; starts revalidate that complete value independently of later defaults.
The existing workflow candidate route owns literal parsing, no-follow checks,
current volume resolution and all typed refusals. The slot table retains bounded,
expiring source/target/inventory choices, not lasting filesystem authority.

The existing application lifecycle gains an atomic first-session claim for a
published blank task. Plan and inventory reuse its admission, attachment,
publication, rollback, release and close owners. A second start or close race
cannot admit two sessions or strand the original shell. Inventory has its own
task kind and details retirement, without a fabricated pair or plan token.
Task enumeration returns lightweight session identity/kind; direct `read_setup`
returns defaults/recents or one exact task's default/frozen Setup. Async create
and start results remain identity-only, so two long roots and options cannot
overflow the small completion boundary or multiply across a task-list response.
No second task, queue or lifecycle owner is
introduced to work around shell attachment.

Plan requests/artifacts retain optional exact admitted location bindings and
linked-verification choice; preparation and publication validate those bindings
against observed plan roots/volumes. Direct legacy callers remain supported;
an artifact lacking reviewed bindings cannot provide Plan-again authority.
Fresh Plan again resolves both reviewed identities, then starts a new task with
the old frozen options and default selection. It never copies selection or
authorization or trusts an old display path. Equal successful replay precedes
old-artifact, expired-choice and native-probe access. Current-mount ambiguity
requires a fresh explicit choice; no old clone choice is silently reused.
Optional source/target mount choices on Plan again are matched only against
the freshly enumerated mounts of those reviewed identities; they cannot supply
replacement root paths, options, selection or authorization.

The command table/browser mirror own exact wire shapes: read Setup defaults and
recents; prepare complete options; admit one location; picker through that same
admission route; plan/inventory start on a blank task; Plan again; and enriched
task readback. Starts consume purpose-bound choices. The UI transparently admits
unresolved nonempty rows on Start, so no separate validation gesture is required.
Extend the existing asynchronous small-command boundary for the new session
starts; preserve its shared 64 exchanges and exact acknowledgement/worker exits.

`setup.js` owns stable form DOM and inert text rendering; `app.js` owns commands,
task identity, row revisions and one page-owned coordinator of at most 48 pairs.
Every edit immediately clears the old choice. Enter, blur, completed paste,
picker/recent selection and Start validate; keystrokes do not probe. Obsolete
responses cannot restore authority or overwrite newer text. Navigation and drain
updates preserve focus/drafts; document replacement stops only unsent batch rows.
Each submitted row has a stable command id and independent outcome, with no
rollback of earlier successes. Admitted tasks are rediscovered after reload.

**Preimplementation study.** Read-only backend/frontend lanes traced the exact
owners above at `b98dce4`. The unchanged product/test corpus passed 851 tests in
the thirteen modules listed by `build/m1-6/inputs/run-baseline.ps1`; a further
91 workflow request/view/checkpoint tests passed via `run-model-baseline.ps1`.
Raw commands/results are in `build/m1-6/evidence/baseline-01/` and
`baseline-models-01/`. Source tracing identified the shell's original receipt
signature as the barrier to attaching its first session, the missing retained
volume-relative identity in PlanRequest, and the frontend's blank-panel/repaint
seam. These are declared M1-6 adaptations, not newly discovered fix scope.

Regression means a lost guarantee, false state, unauthorized/duplicate effect
or newly unbounded work. The probed surfaces are task capacity/claim/close and
receipt replay; option/filter bounds and settings immutability; candidate input,
purpose/expiry and remount/clone authority; plan publication/retirement identity;
observation attachment and exact inventory cleanup; stale page/row responses;
focus/navigation and serial mixed-batch outcomes. Red tests require tracing the
reached consequence; green tests cannot prove absence. Implementation validates
these finite surfaces rather than beginning a new broad audit.

**One acceptance gate and commit.** M1-6-G requires focused behavioral witnesses
for the surfaces above, exact wire/view/package validation, the workflows and
interfaces neighborhood (plus database consumers for shared settings/recents),
the ordinary repository suite, all installed interface headed tests including
the new real Setup flow, twelve import contracts, documentation/link/diff checks,
and a fresh independent adversarial review of the final diff and raw evidence.
Headed evidence must reach typed refusal/recovery, picker/recent admission,
hostile text, partial/mixed pair creation, navigation/reload and Plan-again new
task identity. No test retirement or green-only weakening closes this gate.
Deliver one atomic `feat(web): deliver frozen task setup and location flows`
commit on `milestone1`, including the requested documentation changes.

**Dispositions and stops.** Retired 18-command expansion, speculative DTO/lease,
reservation and aggregate byte-budget recipes remain retired. M1-7 plan review,
execution controls, inventory panes, durable tasks, global settings UI, domain
retry/cleanup, halo mitigation, display settings and new resource certification
are excluded. Existing complete-request, task, exchange and slot bounds remain.
Apply AGENTS/DEFENSE mandatory and recurrence stops; any necessary scope-only
extension follows the bounded investigation/adjudication procedure before edits.
Expansion was frozen after independent design review on 2026-09-11. Review
closed the long-root response-sizing seam through identity-only async results
and per-task readback, and traced the exact command-table/harness migrations
listed above. M1-6 product implementation may now proceed within this boundary.

**Offline authority (2026-09-11).** The user preauthorizes necessary M1-6
documentation and test scope expansions. Probe and record each exact addition,
its cause and verification before editing; no further scope question is needed
for those populations. Product scope is not preauthorized to expand. If a
product extension becomes necessary, suspend its dependent edits, complete all
independent work permitted by the current scope as fully as possible, then
preserve recovery state and stop. Mandatory safety stops remain immediate;
this instruction does not waive a product acceptance or review gate.

**Frontend gate clarification.** The finite async-gesture review requires one
form revision and one in-flight attempt per task, plus one page batch owner
over the exact queued rows and canonical options captured by the gesture.
Edits invalidate authority; document supersession stops unsent starts. Keep
the existing same-command retry closure after uncertain create or start rather
than marking uncertainty as refusal or minting replacement intent. The create
wrapper exposes its already-owned submission closure through a typed uncertainty
error; this adds no backend command, exchange, task owner or retry loop.
Setup selects Sync plan or Inventory before folder admission so picker choices
have the correct purpose; changing mode invalidates the previous choice.
Frozen inventory displays its root from inventory readback. Typed and recent
clone choices retain their candidate; picker choices use only opaque continuation.

Under the user's test preauthorization, add `tests/assets/setup_app_probe.mjs`
and its runner in the already-named `test_frontend_static.py`. It executes the
production page controller with delayed bridge promises to cover stale edits,
single batch ownership, fixed gesture population, generation retirement and
same-command recovery without native task effects. Existing renderer and real
headed witnesses remain; these controls do not replace them. The finite corpus
is the five frontend production files, existing bridge/task-shell/Setup probes,
and their Python runners. Independent review found incomplete declared-surface
enforcement, with no exercised always-stop consequence. All corrections join
M1-6-G and the same atomic commit.

**Approved extension: picker ambiguity (2026-09-11).** The finite probe traced
`admit_location_candidate`, `_binding_from_identity`, candidate projection,
picker dispatch, slot lookup and the browser row handlers. An ambiguous native
picker result exposes current mounts but no continuation for the original
selection. Independent review rejects treating the earlier folder gesture as
an informed clone choice. Echoing the candidate instead can exceed the existing
65,536-byte follow-up request bound for a valid long native path. Display text
cannot become authority, and ingress limits will not be relaxed.

The approved correction is a non-startable ambiguity continuation sharing the
existing 32-entry purpose-bound slot table, fixed expiry and LRU policy. Keep
`choice_id` exclusive to resolved choices; add nullable `continuation_id` to
LocationChoice. The existing `admit_location` gains an exact alternative
payload `{purpose,continuation_id,mount_index}`. The immutable continuation
retains the original candidate, first-admission volume identity, canonical
volume-relative root, nullable location identity and ordered mount tuple. A
bounded index selects only from that tuple, followed by fresh workflow
admission outside the slot lock. Before publishing a startable choice, require
retained/fresh identity and relative-root agreement, location-id agreement when
present, exact current mount-tuple agreement and the indexed selected mount.
Replacement volumes and changed/reordered mounts yield typed changed/new
ambiguity, never silent substitution. Retained binding is evidence, not lasting
authority. No extra queue, owner, durable record or command is proposed.

Before insertion or eviction, admit the bridge-safe immutable continuation
projection and prospective LocationChoice together through the existing canonical
8,388,608-byte direct-response admission routine, using fixed-length placeholder
ids. Existing field and mount-candidate limits remain prerequisites. Refusal
creates no continuation. This is a per-entry enforceable admission rule, not
an aggregate budget or measurement claim; the existing 32-entry table remains
the sole population bound and request bounds remain unchanged.

Implementation remains in the named commands/slots and bridge/app/Setup
files, with workflow admission touched only if needed for typed stale-mount
refusal. Verification must cover non-startability, purpose/expiry/LRU and shared
capacity, malformed/out-of-range index, stale/reordered/disappeared mounts,
valid long native paths, exact prepublication size refusal without eviction, no
task/session/recent effects before Start, stale page responses, and actual
headed ambiguity selection. Existing exact-wire witnesses and matching docs
must migrate together. This changes the frozen wire and slot-state mechanism.
After reviewing the consolidated proposal, the user explicitly approved the
folder-picker continuation-state correction on 2026-09-11. This approval adds
the mechanism above to M1-6; it does not authorize an implicit picker clone
choice, candidate echo, ingress relaxation or another slot owner.

Picker-continuation implementation may now resume within the existing finite
file population. Its verification joins M1-6-G and must pass with the complete
integrated checkpoint before the atomic M1-6 commit. Pause before M1-7.
