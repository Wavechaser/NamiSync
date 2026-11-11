# Desktop UI

This is the visual and interaction contract for M1's Windows desktop: process-live
Setup/tasks, Plan/execution review, Inventory/integrity, ordinary copied-file Verify
and Settings. Desktop History and durable task/restart recovery remain deferred.
UI presentation never decides sync policy, computes plans, writes SQLite, mutates
files or creates a second domain lifecycle.

[Visual system](#visual-system) · [Setup](#setup-and-location-flow) ·
[Review](#review-viewport-focus-and-navigation) · [Execution](#live-execution-controls) ·
[Inventory](#inventory-review-and-stored-evidence) · [Acceptance](#acceptance-criteria)

## Scope and owners

| Owner | Authority |
| --- | --- |
| This document | Appearance, layout, labels, gestures, accessibility and visible feedback. |
| [PRESENTATION](PRESENTATION.md) | Projection identity, complete hierarchy/membership, windows, search/filter/sort, selection, Follow resolution and scale. |
| [BRIDGE](BRIDGE.md) | Exact transport, bounded envelopes, revisions/opaque IDs, command/recovery custody, progress and response validation. |
| [INTERFACES](INTERFACES.md) | Host, task/session observation, native admission, per-user paths/logging, prerequisites and ordered shutdown. |
| [TOOLS](TOOLS.md) / [TESTS](TESTS.md) | Asset maintenance, development launch, installed/native evidence and verification routes. |
| [M1_PLAN](M1_PLAN.md) | Completed delivery, accepted residuals, exclusions and unresolved observations. |

M1 keeps the standard native frame and separate GUI/console entry points over
workflow composition. There is no unattended execution, durable Plan/session
storage, cross-process task visibility, settings CLI or hidden workflow API.
Forced exit promises neither settlement nor restart-resume. Later work starts
with fresh observation and review. [ARCHITECTURE](ARCHITECTURE.md) owns imports;
the desktop never reaches around workflow composition to reinterpret domain state.

## Visual system

Use Fluent 2 Windows 11 presentation, Segoe UI Variable body text and Cascadia
Mono/Consolas paths/hashes. Mica is the whole-window base: page, rail and resting
task cards remain transparent; content cards use their primary blend. High
contrast, unavailable material or failed transparency uses an opaque neutral
fallback. M1 adds neither Acrylic nor a custom caption.

Microsoft's [Fluent](https://github.com/microsoft/fluentui/) and
[WinUI](https://github.com/microsoft/microsoft-ui-xaml/) examples guide behavior,
states and accessibility; the packaged web surface remains plain same-origin ES
modules without importing those frameworks. Source files own their signatures and
view shapes; the rules below describe what the resulting controls must do.

### Palette and semantic channels

Only `tokens.css` contains these fifteen authored palette primitives. Renderers
consume semantic/component roles, not raw colors or direct palette references.
No renderer invents a new hardcoded/derived hue; a changed visual role requires
an explicit design decision and matching token/contract/evidence update.

```css
--palette-red-main: #EE6666;
--palette-red-dark: #551111;
--palette-red-light: #FFAACC;
--palette-green-main: #33DD99;
--palette-green-dark: #004422;
--palette-green-light: #99EEDD;
--palette-blue-main: #33AAEE;
--palette-blue-dark: #002255;
--palette-blue-light: #99CCFF;
--palette-yellow-main: #FFAA22;
--palette-yellow-dark: #553300;
--palette-yellow-light: #FFDD44;
--palette-purple-main: #8844CC;
--palette-purple-dark: #331155;
--palette-purple-light: #BB88EE;
```

Palette identity is main-first in both ordinary themes; light/dark tones support
surfaces, interaction and contrast rather than silently replacing main with theme.
Dark relocating text explicitly uses purple-light; Light uses purple-main. The
blue/green/yellow/red main text on pale Light zebra rows, inactive Delete's red-main
text, and the recorded Light red/yellow filled pairs retain their authored visual
exceptions. Their words/non-color cues carry meaning; they are not blanket
accessible-color claims. Forced colors use Windows system colors.

Hue names a class; form communicates attention. One rendered signal belongs to
one channel. Context, text, shape and accessible state distinguish channels using
the same hue. Ordinary states use text; attention/action may use a filled badge
or another explicit structural cue, never color alone.

**Text** has no semantic background. **Fill** is a borderless 18-logical-pixel
badge with optically raised text: Light uses family-light surface, Dark uses
family-dark; Dark labels use main, Light red/yellow labels use dark. Neutral fill
uses selected-neutral surface/secondary text. Standalone pills are permitted;
compact file-list badges use 4 px corners/padding and bleed 4 px into the leading
cell inset so filled and plain labels align. Windows colors override these pairs
in forced colors. Existing main-first visual exceptions remain explicit.

#### Channel 1 — intent

Plan intent follows reversibility. Exception presentation overrides the displayed
family, not the reviewed operation or its result.

| Class | Members | Hue | Form |
| --- | --- | --- | --- |
| Additive | `copy`, `mkdir` | blue | text |
| Relocating | `move`, `rename`, `recase` | purple | text |
| Replacing | `update`, `move_update` | yellow | text |
| Removing — recoverable | `trash` | red | text |
| Removing — permanent | `delete` | red | fill |
| Nothing | `noop` | neutral | text |
| Exception | `error`, `unsupported`, `blocked` | yellow | fill |

#### Channel 2 — lifecycle

| State or projected result condition | Hue | Form |
| --- | --- | --- |
| new / planned / queued | neutral | text |
| executing / verifying | system accent | text |
| completed | green | text |
| skipped operation (row only) | neutral | text |
| completed, partial / degraded / incomplete | yellow | text |
| `PAUSING` / `CANCELING` | system accent | text |
| `PAUSED` / recoverable `INTERRUPTED` | yellow | text |
| plain `CANCELED` | neutral | fill |
| execution reason `CANCELED_AFTER_PUBLISH` / `CANCELED_AFTER_MUTATION` | yellow | fill |
| `REFUSED` | yellow | fill |
| capacity exhaustion or capacity refusal | yellow | fill |
| errored / `FAILED` | red | fill |

Yellow attracts review without hiding a known failure. Pausing/canceling stays
accent while the system approaches a safe boundary. Paused freezes the last bar
in yellow; plain canceled freezes it in neutral gray, with fill distinguishing a
stopped task from one never started. After-publication/mutation cancellation and
refusal require attention. Additional stopped-count/percentage presentation is
latent, not an implied payload or renderer field.

Rail headlines share the status card's semantic role and current activity wording;
supporting text/progress keep their own roles. Distinct task, release/recovery,
Inventory or auxiliary activity facts may require different headlines. Forced-color
rail text inherits the selected/hovered card's system foreground.

#### Channel 3 — integrity

| `IntegrityResult` or inventory condition | Meaning | Hue | Form |
| --- | --- | --- | --- |
| `VERIFIED` / retained verified evidence on rescan | hash or metadata equals the record, including matching identity where available | green | text |
| `BASELINED` | evidence recorded for the first time | green | text |
| `UNVERIFIED` | no evidence yet | neutral | text |
| `MODIFIED` | evidence is stale because metadata drifted | yellow | text |
| `REAPPEARED` | file returned and needs heightened verification attention | yellow | fill |
| `UNSUPPORTED` | entry type cannot be verified | yellow | fill |
| `CANCELED` | verification stopped | neutral | text |
| `MISSING` | recorded file is not found on disk | red | fill |
| `MISMATCHED` | hash is confirmed different | red | fill |
| `ERROR` | read failed | red | fill |

Reappeared is an Inventory presentation condition, not an IntegrityResult; it
overrides ordinary unverified/modified but never stronger mismatch/error truth.
Stored evidence, live progress and latest ordinary results remain separate.

Native appearance supplies observed Accent, AccentLight1–3 and AccentDark1–3;
the page receives semantic accent-fill/text-fill roles. Neutral/scales use the
pinned Fluent token subset, independently tested from the authored palette.
Its source is `@fluentui/tokens@1.0.0-alpha.24`, commit
`32b42a5bf79c1836047dfc7fae07b1320731bce4`; fixtures retain exact source hashes.
Contrast targets are 4.5:1 normal text, 3:1 large text/non-text indicators, subject
to the explicit visual exceptions above. Subtle elevation strokes are construction
lines; keyboard focus supplies an independently visible boundary.

### Control fills, borders and focus

Alpha applies to fills, never whole controls. Textboxes/combobox triggers share
ordinary fills; focus, popups and disabled roles stay independent.

| Role | Light | Dark |
| --- | --- | --- |
| Ordinary rest/hover/press/disabled fill, CSS RGBA | `#ffffffb3`, `#f9f9f980`, `#f9f9f94d`, `#f9f9f94d` | `#ffffff0f`, `#ffffff15`, `#ffffff08`, `#ffffff0b` |
| Input-active fill | opaque white | `#1e1e1eb3` |
| Ordinary perimeter/bottom, hex alpha | black 0F / 29 | white 18 / 12 |
| Pressed/disabled flattened stroke | black 0F | white 12 |
| Accent rest/hover elevation | white 14 over black 66 | white 14 over black 23 |
| Disabled label | `#bdbdbd` | `#5c5c5c` |
| Unchecked checkbox stroke, WinUI ARGB | `#72000000` | `#8BFFFFFF` |
| Disabled unchecked checkbox stroke | `#00000037` | `#FFFFFF28` |
| Consequential accent base | AccentDark1 | AccentLight2 |

Buttons/checkboxes/toggles use authored 1.2 px strokes; this biases Chromium
fractional-DPI snapping, not native thickness or identical physical pixels.
Accent pressed/disabled borders are transparent. Accent hover/press use the same
base RGB at 90%/80% opacity; one native luminance calculation chooses exact black
or white label text from the opaque base and that text never inverts on interaction.
The selected Sync/Integrity half, checked boxes and switches share this ladder;
progress/selection markers use the base only. Forced colors use Highlight/HighlightText.

Textboxes paint one padding-clipped fill and a straight 2 px lower strip within
rounded clipping, not a bent perimeter. Focus accents the strip. Pointer focus
suppresses only that textbox's extra dual ring until blur; keyboard focus retains
it. Disabled textboxes remove the strip and flatten all edges. Comboboxes likewise
paint one fill with independent elevation edges, never stacked fill gradients.
Ordinary keyboard focus uses a 1 px inner separator and 2 px outer Fluent ring;
mouse activation does not request it. Forced colors keep a system-visible outline.

Checkbox outer geometry is 16 px, with a centered roughly 12 px pinned Fluent
checkmark mask and small dilation; mixed uses the subtract mask. Switches are
40×20 px: thumb 12×12 at rest/disabled, 14×14 hover, 17×14 pressed, elongating
inward. Off states retain native translucent alternate fill and strong stroke,
including disabled; checked borders are transparent. Disabled fills/thumbs follow
native roles, with the unchanged off-stroke as the explicit local exception.

Clear/dismiss controls are transparent at rest/disabled, use task-card hover/press
fills and retain keyboard feedback. Operation chips are borderless: inactive
inverse grayscale; active family-main with contrast-selected neutral label, same
90%/80% hover/press, no lift/scale. Inactive Delete alone keeps red-main text while
using ordinary grayscale interaction backgrounds. Progress has a neutral track,
accent active/resumed, yellow paused, neutral-gray plain canceled; forced colors
use Canvas/Highlight. Sync/Integrity uses radiogroup/radio with exactly one
aria-checked selection. Border removal never removes keyboard/forced-color cues.

Disabled-label blur was not reproduced in the clean installed gallery. Do not
change tokens on that hypothesis. Reopen with runtime, DPI/text scaling,
active/monitor-move and HDR/material state, plus same-frame enabled/disabled
captures; whole-surface blur needs host rasterization investigation.

### Surfaces, appearance and motion

| Surface | Contract |
| --- | --- |
| Content card | Static 1.2 px outline; Light `#EBEBEB` fallback, black 6% blended stroke, white 70% fill; Dark `#1C1C1C`, black 10%, white 5%. Secondary/tertiary blends remain contextual roles; no hover/press. |
| Flyout boundary | Black 6% Light / 20% Dark with opaque stroke fallback, separate from accessible control strokes. Ordinary SDR dialogs/menus retain black elevation shadows. |
| Advanced Color | Dark menus/comboboxes and non-keyboard-focused dialogs suppress CSS shadows when HDR dynamic-range or native SDR-WCG evidence says Advanced Color. Boundary remains; Light/cards/fills are unchanged. |
| Motion | Shared tokens/Fluent easing for controls, disclosures, progress and dialogs. Reduced motion stops/reduces non-essential transitions. Virtualized creation/recycling never animates. |

Advanced Color shadow suppression mitigates the external DWM composition defect;
it is not a Windows fix or a promise that translucent fills are exact. Raw Win32
controls reproduce it without WebView2/Mica; legacy screenshots cannot see the
FP16 halo. scRGB output was rejected because it changes translucent colors/HDR.
[BUGS](BUGS.md#desktop-material-composition) owns the residual/reopening record.

System/Light/Dark is a production DOM combobox: disabled until its initial cosmetic
read, serial revision-bound choices, canonical accepted display only—never
optimistic CSS. Failure/Refresh reads current state; it does not claim the old
write settled. Generation fences suppress late replies; no sticky original-response
fence. Cosmetic failure stays local/sanitized and does not block operational readiness.
High contrast temporarily overrides the saved choice without overwriting it.

The portaled fixed listbox matches trigger width, centers the selected option
when possible and clamps to an 8 px viewport inset. Resting options are transparent;
hover/selection share a neutral overlay, selection adds a 3 px accent pill, press
weakens the overlay. Trigger elevation flattens while pressed/open; keyboard ring
remains. Popup is opaque theme surface with flyout stroke/radius and elevation 16,
not Acrylic. Forced colors use Canvas/CanvasText/ButtonBorder/Highlight/HighlightText.

The same initial cosmetic snapshot drives native material, opaque background and
the first page appearance envelope before creation; section initialization cannot
delay operational readiness. This is not a compositor flash-free-paint guarantee.
Live appearance reads/apply coalesce on the native UI thread; subscription precedes
initial read and changed native generations cannot overwrite newer state.
Unknown/unreadable display flags retain prior state. Appearance-envelope revisions
are not persisted cosmetic or bridge-protocol versions. Injected contrast/CDP
evidence is not a real OS-theme-transition witness.

Unconfirmed native reapply publishes degraded and restores an opaque page base.
Startup refuses only if native enhancement may have changed the surface and opaque
rollback cannot be confirmed. Appearance observation survives incomplete/exceptional
Close and closes once after complete service shutdown, before destruction.
Dialogs keep compatible exit state before close; no minimum visible exit duration.

### Scrolling and gutters

Window size is 1280×800 logical px with 1024×640 minimum through pywebview's public
API; its backend performs DPI conversion. No JavaScript/native-minimum correction.
A 48 rem container query preserves stacked reflow under WebView zoom.

Shell padding is 24 px except inline end: subtract the shared 10 px scrollbar to
14 px. No document gutter; each work panel keeps its stable gutter even with hidden
outer overflow, making normal-theme content end 24 px from the edge. Forced colors
keep shell padding and browser scrollbar width consistently across pages. The
natural-height gallery alone has document scrolling/stable gutter and symmetric
24 px padding; its production-shell specimen temporarily removes/restores that override.

Plan/Inventory use one two-axis viewport, opaque sticky 24 px header and shared
column tracks; the viewport alone reserves a stable vertical gutter even if rows
fit. Horizontal scrollbar reduces usable row height. Reveal reserves the header,
and file-column resize keeps its initial width snapshot. Setup/generic tables
instead use vertically scrolling bodies below fixed headers, matched gutters and
outer horizontal scrolling. No width-measuring/correcting JavaScript.

Scrolling stays browser-owned. M1 CSS approximates Fluent with fixed gutter,
thin resting thumb widened on hover/drag, subtle track and no extra pressed/fade/
pane show-hide logic; forced colors use browser defaults. Wheel, keyboard, track
click and drag stay native. Native Fluent overlay/fade/input/system preference
parity requires coordinated host startup changes and remains M2 work, not a flag
or vendor patch. TOOLS owns current development/installed compositions.

### File-row components and geometry

The shared skeleton and integrity cell render page-local projected views;
function signatures, argument schemas and supported keys are source-owned in
`file_row.js`, `plan.js` and `integrity.js`, not another wire contract. The gallery
uses those same components with test-only fixtures; production keeps real hierarchy,
selection and activation owners. No fake Plan/session/temporary command ships.

Projected state chooses a fixed semantic role; the browser never derives domain
result, urgency, hue or counter ratio. Actual completed NOOP says green **No change**;
other skipped outcomes, including deselected NOOP, say neutral **Skipped**. A
projected executing/verifying cell uses its finite 0–100 percentage for a 4 px
bar across the cell with 8 px side insets; supplied text labels accessibility.
Unknown progress remains text/indeterminate. Terminal text never disappears.

| Shared geometry | Contract |
| --- | --- |
| Production Plan/Inventory | 24 CSS px rows; generic tree renderer independently remains 28 px. Two fixed virtual spacers; no zebra fill on spacers. |
| Typography/checkboxes | 12 px/16 px caption text; 16 px boxes, semibold folders/state labels, monospace checksums. |
| Headers/columns | Same tracks for header/body; Name absorbs passive growth. Freeze fitted non-Name widths at first visible loaded layout; hidden/disconnected waits, reuse retains widths. |
| Resize | Constrained pointer/keyboard parity; Notes yields width until its minimum. A positive fixed-column resize cannot exceed remaining Notes reserve. |
| Minima | Action 6 rem; Inventory Filename/Modified/Notes 12/7/14 rem. Existing generic/gallery File/Notes 12/14 rem constraints remain. |
| Neutral facts | Size, Modified, Notes and rail paths use `#616161` Light / `#adadad` Dark; forced colors use system text. |

Physical row/column geometry, fixed tracks, constrained resize, width-preserving
horizontal overflow and focus/reflow are installed-gallery acceptance, not a new
browser-owned ordering or selection model. Do not infer domain policy from static
gallery checkbox reconciliation or its sample action counts.

Gallery row specimens use Selection, Filename, Size, Operation/Presence, Checksum,
Notes; Selection has no visible caption but retains its accessible name. Five
focusable separators control preceding tracks, not Notes' outer edge. First resize
freezes fixed tracks; File/path alone flexes with a 12 rem minimum, Notes at least
14 rem. Pointer/Left/Right share the same inverse-Notes calculation, preserving
intervening tracks and right edge. Effective minimum is max(48 rem, fixed tracks +
12 rem File + stored Notes); overflow preserves customized widths. Widths are
DOM-local, not persisted/bridge state. Only direct rows own zebra fill, ending at
the last row; cells/group backgrounds stay transparent with no filler height.
Folders have borderless disclosure/mixed checkbox, children indented basenames.

### App icon and glyph vocabulary

The app icon combines rear source-sheet outline and front paper/water layers:
sky, teal wave and deep right-rising swell. The three 256×256 SVG masters under
`interfaces/branding/` are full-color gradients/shadows, blue-main/dark-blue
two-tone and currentColor mono. Flat variants omit teal and add the left closing
bar; the color master has no bar. Remaining geometry is shared.

Masters are packaged artwork outside web glyph/palette rules. Full color is
ratified for executable/title bar/taskbar; mono variants serve in-interface text.
Tracked `namisync.ico` has 16/20/24/32/40/48/64/128/256 px frames. Builds consume
it unchanged; tests check parsing/sizes, not regeneration or byte equality.
Regeneration requires explicit artwork review.

#### Maintaining the icon vocabulary

[TOOLS](TOOLS.md#icon-maintenance) owns catalog edits, authenticated archive sync,
generated registries/receipts, native 16/20/24 artwork/fallbacks, license updates
and checks. Do not hand-edit generated regions, maintain another glyph/hash
catalog, or package maintenance tooling. Registration never authorizes placement.

#### Icon placement and meaning

Icons differentiate rather than decorate. Text-and-icon lists/menus stay text-first;
frequent or attention-demanding actions may receive supplementary glyphs, with
consistent text alignment. Familiar clear actions may be icon-only when their
button has an explicit accessible action name and hover/keyboard tooltip; ambiguous
actions keep text. Close, Clear and Cancel must remain contextually distinguishable.
The glyph itself is decorative. A badge already carrying status gets no duplicate
status icon. Use one consistent glyph per contextual action, never similar variants
as decoration. Preserve fixed local artwork rather than substitute font glyphs.

| Action | Glyph | Meaning boundary |
| --- | --- | --- |
| New item/task | `add` | Creation in the current context; retain text when the kind is unclear. |
| Browse/open folder | `folder-open` | Folder access or selection, not starting a sync. |
| Save | `save` | Persist an editable choice; not execute a reviewed plan. |
| Close/clear | `dismiss` | Local dismissal or clearing, with an explicit contextual name. |
| Settings | `settings` | Open settings. |
| Search | `search` | Find/filter in the named scope. |
| Delete | `delete` | An actual removal action; retain consequence wording where needed. |

## Host and security boundary

INTERFACES owns singleton/token/prerequisite admission, per-user paths/logging,
database startup, native origin/navigation controls, appearance landing and ordered
shutdown. Production uses Edge Chromium/WebView2 and packaged local assets with
no silent fallback. M1 does not invoke the Evergreen bootstrapper; missing runtime
gets read-only installation guidance. Unsigned packages publish hashes/source
identity and honest unknown-code-policy guidance. Browser state grants no authority.

GUI-only data-dir relocates every artifact together. The development launcher
uses its distinct mutex/title and NamiSync-Development root; test compositions'
local-index seam is not a production argument/environment/page/bridge override.
Clean installed-wheel evidence is separate from editable preview. The old PySide
proof/mockup is [historical](obsolete/ui_mockup/mockup.md).

BRIDGE owns dispatch/envelope/identity/recovery, neutral readiness and response
custody. The initial five-second readiness deadline does not turn a nonce into
authorization. A genuine replacement permanently retires page command/appearance
authority and directs close/reopen plus fresh review; admitted work still settles.
Same-document history/canceled navigation are distinct. Private parsed response
adoption follows BRIDGE, not an obsolete deep-copy recipe.

Keep first-head CSP, inert text/layout-control markers and bidi isolation. No
innerHTML or executable/attribute/URL/style/command interpolation of filesystem
text. Ordinary Unicode stays exact; raw callback IDs remain separate from display.
Only bridge.js references window.pywebview. Static assets are not an API channel.
Native shutdown runs off the UI thread with visible Closing; the service allowance
may reach twelve seconds. Incomplete shutdown retains the window, owned Retry/
Cancel and original diagnosis; no silent force-close or authority reopening.

## Interaction contract

### Shared review behavior

Card labels/file rows are not browser-text-selectable; expanded Task/Item details
and editable fields retain selection/copy. Detail buttons remain controls.
Selection/highlight paint never changes tracks. Current view segment keeps accent
and ordinary button behavior; clicking it stays put. Other destination is disabled
during copying and enabled for linked Verify/original release; disabled appearance
is preserved. Plan Again is absent during execution or unsettled admission, with
original-outcome recovery still available.

Automatic post-copy Verify opens once when observed, then respects manual return
to Plan. Before original release it uses bounded execution review/operation identity
and that run's controls, without creating/mutating an Inventory publication. Release
opens ordinary target Inventory; original Plan/results remain. Between files Go
retains the last observed subject; Gap/phase/terminal/session replacement retires it.
Verify headline/counters describe that phase, including partial/failure/cancel,
while recording/audit issues remain visible. Partial execution telemetry never
becomes a fabricated final counter.

Observed recall evidence gets the 16 px Fluent plain cloud, 6 px name gap, clipped
16×12 slot shifted up 1 px. Label/tooltip: “Not fully available locally. Access may
retrieve content through your provider.” Remote files filters include directories
on their own evidence; matching rows are not total download bytes. Unmarked files
are not certified local. Aggregate recall facts remain available for later status
work, without another cloud paragraph/modal or remote-completion claim.

Background/drain updates preserve foreground drafts, highlight, selection, scroll
and current feedback. Same-session confirmed Inventory views can be reused; pending
change, replacement, release or uncertain delivery requires current bounded read,
with only the latest reread behind an in-flight one. Explicit reread keeps mounted
pane/tree focus/expanded Task details/anchored scroll and retires prior item evidence
before new publication. A view read never changes scan/integrity activity status.

### Setup and location flow

Only the selected Sync/Inventory type's Create action is visible. Segmented radio
supports arrow keys; changing mode/purpose invalidates prior folder authority.
Inventory uses one Root and shows the admitted frozen root. Setup reads defaults,
captures per-task overrides, and never saves global settings.

Setup/Recent pairs are separate cards. Setup begins at work-area top with no
repeated visible task/type heading; accessible region identity stays. Each path
row has fixed Source/Target/Root label track, editable path with inset Clear/recent
caret and separate square Browse. Clear edits locally/invalidate candidate without
Python, even if textbox focused. Recent dropdown supports arrows/Enter/Escape;
pointer-open starts neutral, keyboard highlights, pointer movement restores hover.
Disclosure uses pinned 16 px up/down chevrons.

Verify execution then Additive sync occupy the left option row with 16 px gap;
Additive maps on→additive, off→trash. More options sits right, changing only
disclosure, not values. Expanded preservation/update/casing/filter controls have
extra top space and 8 px row gaps; caption follows toggle, Add filter beside text.
Creation-time/ACL/source-casing and linked verification remain captured options.
No Mirror control; ADS is visibly unavailable/frozen off. [PLANNER](PLANNER.md#exclude-filter-syntax-and-effect)
owns exact exclude syntax/effect. No disabled checked option implies honored work.

Empty/resolved paths omit routine hints. Folder/action/recovery feedback shares
the area left of Add pair/Create, named by Source/Target/Root, with accessible
descriptions; it never inserts error text under rows or shifts top-aligned actions.
Mount controls stay with fields and row-specific outcomes stay in batch tables.
Clear/Browse/recent/More options/recent Refresh/New task are transparent at rest,
task-card fills on interaction and retain keyboard/forced-color feedback.

Before start, editing immediately drops accepted slot authority. Validate on Enter,
blur, completed paste, picker/recent choice or start, not each keystroke. Refusal
stays editable/action-guiding. A selected file remains visible as not-directory,
never silently converted to parent. Native/workflow code owns parsing/admission.

Create remains available during an ordinary check: one guarded attempt shows
Checking folders and awaits the current check, without duplication or stale choice.
Editing abandons it; refusal starts nothing. Picker/mount waits keep their guards.
Ambiguity requires an explicit current mount, expiring purpose-bound reference and
fresh checks—not first-match or cached authorization.

#### Recent pairs and batches

Recent/batch tables share caption/header/zebra surfaces, 56 px two-line rows,
28 px headers, 12 px folder-column insets and five reserved slots; excess scrolls
below a fixed header. Empty slots are inert/inaccessible. Source:/Target: share
label width, paths tail-elide with full tooltip. Full-row hover/press/focus, never
cell-only. Online has a green dot, Offline red, neutral text and 1 px lowered dots.
Missing root/volume is Offline; other refusals Unavailable; incomplete probes show
Checking/Could not check. All rows remain visible; only both-Online pairs select.
The current recent query returns at most five. Refresh is ephemeral probing, not
task start/authority; unresolved identities never display a stale drive hint.

Add pair captures private paths/options even during ordinary check; batch later
admits that snapshot independently, reusing a captured accepted choice if present.
The coordinator holds at most 48 stable-ID pairs with per-row options/results.
Queued rows show paths, Verify/deletion/filter/preservation values; later form
edits cannot change them. Canonical preparation replaces only that row's snapshot.
Rows belong to their origin Sync task; Inventory hides, rather than loses, its queue.

One batch gesture serially prepares/admits its selected rows, not a global queue
for independent forms. Preparation refusal affects one row; removal before
submission prevents it and late admission replies cannot revive it. Submitted
Create/Start cannot be removed. Delay keeps original payload/promise and read-only
Check, never replacement/replay. Created tasks are not rolled back.

Add pair precedes single Create, which remains visible but disabled for queued/
unresolved batch work. Conditional table sits near actions; right-aligned Create
batch is 8 px below it. Create batch/Clear results stay visible while table exists,
disabled without eligible work/settled results or during guards. Clear removes only
settled receipts, never tasks/unknown outcomes; hide table only when empty.

Navigation retains coordination. Genuine replacement stops only unsubmitted rows;
admitted tasks are rediscovered. Closing origin discards queued rows/detaches pending
folder admission, but preparation and unreconciled start outcomes block Close/new
form starts. Adopted tasks name their origin blocker; Check remains on the origin.
Popovers, global trays and a dedicated Batch page remain unimplemented alternatives.

### Review viewport, focus and navigation

PRESENTATION owns full hierarchy/window/selection/sort/anchor policy; the page
never infers it from displayed paths, adjacency or retained rows. Render only
server-returned windows (at most 256 rows plus spacers), with exact row-height
geometry, full layout-safe accessible labels and stale-owner refusal before payload
adoption. Dispose controllers before removing roots so listeners/queued work retire.

Tree root is one Tab stop using aria-activedescendant. Server position/parent/
child metadata supports arrow/Home/End/Enter navigation across windows. Expansion
state/disclosure exists only for a retained immediate child. Disclosures focus and
request one expand/collapse without activation; labels activate. Covered scroll
moves presentation focus to a visible row or clears ARIA until coverage, never
domain activation. Keyboard/external targets reveal the whole row below the header.

Scroll/resizes coalesce; compatible overlapping replies may adopt while preserving
scrollTop, then reconcile remaining coverage. Keyboard/external requests retain
exact intent. Failed/blocked reads settle without idle retry loops; later scrolling,
hidden return or changed viewport can retry. An unchanged narrower page waits for
new geometry instead of alternating edges. Settings/hidden render defers geometry;
return can retry the same offset. No implicit minimum page width.

#### Sorting, search and filters

Headers Name/Size/Modified cycle ascending, descending, canonical; switching header
starts ascending. Buttons fill padded header cells with active chevron right.
Raw numeric size/mtime keys and complete siblings are server-owned; ties/unavailable
handling, revisions and index/anchor rebuilding stay in PRESENTATION. Sorting never
changes hierarchy, IDs, selection, collapse, execution scope/order or durable settings.
Ordinary sort/reset starts at zero. No status/progress/global-flat sorting in M1.

Search is narrower/right-aligned with inset submit/Clear; Clear restores focus and
clears immediately. A fixed 150 ms trailing debounce remains editable during read:
keep newest query behind the current request, including across retained task navigation.
Search/filter do not mutate selection; stale success/failure cannot replace current view.

Both panes use one ordinary Filters button with regular Filter/chevron and caption
Filters · matching/total, or Filters until accepted counts. Counter uses All's
population: search changes numerator, scrolling/folding do not. Inventory All
excludes acknowledged rows but denominator includes them. All clears categories;
all thirteen Plan categories stay independent with counts including zero.
Trigger stays neutral at All and accent for active categories.

Checkbox-menu items/counts stay stable/focused during updates; pending refuses
gestures without adding a query queue. Scrollable popup clamps to work panel and
viewport, opens above if room is better; label/count have a dedicated gap and
right-aligned count. Up/Down/Home/End navigate, Enter/Space toggle, Escape returns
trigger focus even pending. Pending trigger is focusable aria-disabled but cannot
open. Outside interaction/focus loss/blur/hidden, outer scroll/resize or owner
replacement closes and removes listeners; internal scrolling works, reuse restores.

#### Sorting and automatic Follow

Follow is eligible only in canonical order without search/filter, initially on for
new eligible execution/ordinary integrity. It follows active or last-settled
nominal subject/visible collapsed ancestor; linked Verify ends navigation at terminal
and opens Inventory on release. It never changes selection or keyboard focus.
Manual scroll-away or changed sort/search/filter disables it, even while pending;
only explicit Enable resumes. Programmatic scroll, pause and task navigation do
not silently change the choice. Repeated loaded-target progress does not reposition;
explicit Go does.

Go/Follow/move jumps use four leading rows, max(0, target index − 4), applied after
rows/spacers mount and clamped at the end. Use target identity captured at click,
not the next item. Retain last target between files; Gap, pane/phase/session change
or terminal retirement invalidates stale intent. Excluded target/ancestors gets
guidance, never fabricated row. Go changes neither filters/sort nor Follow choice.

Float Go to current operation/item and Turn on autoscroll at lower-right 32 px
insets: square icon-only targets, accessible names/tooltips, navigation-location-target
and location-arrow. Go is ordinary neutral; Enable primary accent. Each has an
opaque neutral wrapper in every interaction state, without blur/Acrylic. Rows remain
scrollable clear. Enable appears only eligible/off; no active target means no jump.

Inventory Follow leaves highlights, checkboxes, Details and Refresh selected alone.
Off-window active identity stays retained while ARIA detaches; render restores it.
Focus alone does not reveal/override Follow. Explicit navigation resumes there;
real disappearance, including collapsing its parent, clears active/action target.

### Plan columns, scope and operation labels

Plan columns are Select, Name, Action, Checksum (empty), Size, Modified, Notes;
Checksum/Modified default widths match. Synthetic root is omitted. The header
tri-state selects the complete matching selectable population, not just loaded/
expanded rows; folders use server-defined descendants. Dependency/safety closure
remains workflow-owned. View changes alone never change execution selection.

Plan ready is neutral for every built unexecuted Plan, not execution eligibility.
Execute still needs nonempty executable selection and preflight. Strictly empty and
filtered-empty views differ. Notes omit dependency counts/Risk:none but show actual
risks. Size/time/notes use shared tertiary foreground. Binary labels have two fixed
decimals from 1 KiB upward, exact integer bytes below; Modified uses local display
without changing raw sort facts. Plan remains hash-free; any execution-owned evidence
comes only from atomic ledger classification, separately labeled from current state.

Friendly labels are No change, Create folder, Rename, Move + update, Move to trash
and Delete. Recase/pure same-parent move display/filter as Rename; cross-parent
Move and Move + update remain distinct. Details/diagnostics retain actual kind.

| Input | Display policy |
| --- | --- |
| Operation reason `source_only`, `metadata_match`, `identity_rename`, `required_directory` | Hide only when risk is `none` and there is no blocker or selection exclusion; action/hierarchy already conveys the low-risk explanation. |
| Those same reasons on risky/blocked/excluded rows | Show the friendly explanation. |
| `metadata_changed`, `identity_rename_changed`, `target_only`, `directory_cleanup` | Show changed-file, removal or cleanup context. |
| Case, Unicode, type, policy and destination conflicts; unsupported and blocked reasons | Show friendly explanation. |
| Selection exclusions, including incomplete scan and deselection | Show; never apply the operation-reason hiding list to them. |
| Move peer / prior-location rows | Keep paired-move / previous-location context; expandable old contents attach at their deepest surviving scanned target ancestor. |
| Non-neutral risk, free-form notices, partial/overflow totals | Show unchanged. |
| Any unrecognized or future reason/notice | Show verbatim as inert text; hiding never follows a broad pattern. |

Known reason translation is display-only; unknown reasons remain inert and visible.
Operation/ordinary-integrity overlays replace only one complete current generation;
stale or missing facts never become fabricated planned paths/results.

#### Move and prior-location context

Prior groups start collapsed. One count/destination badge in Name is distinct from
disclosure; 4 px corners/padding align with action badges, slight leading bleed aligns
text. Light uses light-purple/dark text, Dark dark-purple/light text; hover/press
reduce only fill to 90%/80%, with focus ring and forced-color Highlight pair.
Disclosure shares Inventory's chevrons without double rotation.

Destination is the target parent, even for directory move. Compact basename with
ellipsis prefix is bounded to 255 UTF-16 units and shared by tooltip/accessibility;
full destination is in Details. Activation reveals canonical destination, expands
ancestors and clears only obstructing filters/search; target-root destination uses
first canonical moved item. Badge/prior contents never enter execution totals/selection.

Canonical Move appends moved from another folder; Move + update says previous
location available in details, including same-folder updates. Rename shows renamed
from [previous name], has no prior group, elides annotation with prior-name tooltip.
Annotation gap is 4 px and at most half Name width so filename remains readable.
Projection supplies classification/labels; browser does not derive membership.
Changed destination window keeps coherent review and offers Refresh review; a
coherent conflict aligns loaded viewport before asking another click. Old owners stay silent.

#### Highlighting, Details and confirmation

Highlight is independent of execution selection. Pointer/keyboard replace/toggle/
extend/add ranges in full server order. A checkbox in a multi-highlight set applies
direct row contributions; singleton/outside-set folder stays recursive, with
descendant checkbox aggregation. Search/filter clears highlight; sort/scroll/
disclosure does not. Gestures send endpoints/revisions, not browser-owned row arrays.

Display labels/notices are bounded to 300 UTF-16 units; the highlighted node gets
one complete detail read, never fan-out. Original-case paths/digests remain copyable.
Join supplied origin to reviewed root only for display; prior/move and execution
backup/mutation/prior/published/trash fields use target root, global trash already
absolute. No filesystem probe or diagnostic-text parsing. View/session/action/Close
fences retire old details before replies; returning to Plan reads highlight anew.
Planned-detail loading/failure stays visible alongside execution-detail status.

Destructive workflow count opens the shared smoke dialog, explains replacement/
removal and selected count, with Cancel and Confirm and execute. Paragraph gap is
16 px, action gap 24 px; no persistent consent. Non-destructive selection submits
immediately. showModal, existing material/motion, app/popup inertness and scroll lock
remain through exit; restore prior overflow/value/priority. Dialog can scroll short
viewports. Cancel initially focused; Tab contained, Escape cancels; restore invoker
only if available. Backdrop pointer/wheel/key gestures do not reach background.

Confirm is single-shot/start admission immediately; Cancel before submission keeps
review editable. Delayed admission offers Check and fences selection/Close. A
tests-only exit-animation barrier proves background blocking, not product latency;
zero-motion may close in one frame. Preview uses the same dialog with no effects,
not a second production command. Plan Again eligibility follows dispatch blockers;
an unsubmitted click never displays a completed-request message.

### Shell layout and Settings

Viewport bounds shell; tasks scroll independently between Tasks/New task and the
full-width bottom Settings button; work area scrolls separately. Landmarks are
labeled, not gratuitous tab stops. Empty navigation/work explain no task selected.
After first authoritative enumeration create one blank task only if no mutation or
creation overtook it, once per document. Last Close then leaves empty work with
ordinary New Task button sharing the top Create's pending/recovery state.

Rail is a transparent Mica seam, without border/shadow. Resting unselected cards
transparent; hover/current share neutral overlay, press weakens it. Live current
cards keep 3 px × 2 rem (32 px default) accent marker; Settings marker is 1 rem.
Task text leading inset 20 px, Settings 16 px. Sibling select/dismiss buttons never
nest; dismiss transparent at rest, task-card interaction fills, contextual Close/
Retry accessible name. Forced-color enabled current cards use Highlight/HighlightText
and opposing marker; disabled GrayText; focus stays visible. Current selection is
explicit aria-current/selected, not inferred from running state.

Cards show current status digest rather than visible Task N, compact operation/
binary-byte detail, source/target paths or -, and progress; internal ID is unchanged.
Labels reserve 3.5 em tracks with 2 px gaps, detail/path/progress end 18 px inside
the right edge below close, with equal progress spacing. Subject-only activity never
invents a source→target pair. Ready Plan progress is inert, planning indeterminate,
execution uses authoritative progress, never selected rows. Stable card elements
stay attached during same-order repaint so trusted press/release survives.
Rail keeps its 18 rem cap, compact 14 px headlines and one-line path/detail text;
headlines may wrap at native minimum instead of forcing horizontal overflow.

Settings has Setup defaults, Appearance and About cards. Explicit Save defaults
patches only changed supported options; excludes Add/Remove preserve exact pattern
spelling and ADS stays unavailable. Reads preserve unsaved edits while refreshing
untouched values; reads/saves serialize and disable editing. Footer advisory left,
Save right with reserved row height. Delayed save stays pending; unconfirmed save
offers Read current defaults before another explicit write, never replay or claimed
settlement. Existing drafts/frozen Plan-again choices remain unchanged.

Theme uses the appearance contract above. About shows version/nickname, License and
Open source acknowledgements, no resting underline; shared neutral hover/press with
unchanged accent text and keyboard focus/system link colors. Each opens read-only
native modal with shared material/motion, selectable scrolling text and fixed Close.
GPL bytes remain LF-pinned and exact; notices cover current packaged dependencies
and derived assets. URLs are inert; no remote load/navigation. Close/Escape restore
available invoker and background inertness through exit. Task navigation/drafts/
activity survive Settings; background updates never navigate away. An unraced
successful New task opens its task; clicking a task returns to it.

### Live execution controls

Pause/Resume, Cancel, Refresh and Baseline dropdown use square 32 px targets.
Pause is icon-only neutral Regular Pause; authoritative Paused becomes accented
Filled Play Resume. Accessible action/tooltip follows state; waiting/pausing disables
repeat but keeps Cancel. Pausing remains Pausing until actual Paused settlement.

Cancel is neutral Regular Stop. First click arms accented Filled Stop for a
monotonic five-second deadline; second submits. Arming does nothing to execution,
renders do not extend it. Expiry, leave/retire, unavailable control or submission
disarms; expiry timer changes only that button.

Control attempts belong to exact task/session through refresh, with no duplicate
request. Authoritative control/terminal/session state supersedes old replies;
byte ticks do not erase refusal. Lost updates disable controls and offer one Retry
updates even before review or during Close. Last truth stays visible—lost updates
do not prove stopped work. Retry observes same session, never restarts it; controls
wait for validated recovery. Terminal/release retries and original Close Check
remain distinct, with unresolved Close's fence first.

### Close and uncertain outcomes

Busy Close says Closing, requests cooperative cancellation and retains the task
until settlement/release. Incomplete Close stays actionable, never domain retry or
force-close. Close/publication fault retires rail/panel/tree generations before
clearing cached values. Task Close never purges trash. Terminal retry/Verify remaining
and explicit session cleanup remain M2; ordinary owned-temp/read/operation retries
and pause/transport/shutdown recovery keep their separate policies.

Mutation delay is availability feedback, not timeout cancellation. After five seconds
qualify original-result waiting. Failed observation says Outcome unavailable and
offers read-only Check; fixed unreadable final result says unknown/invalid_result
with close/reopen/fresh-review guidance. Acknowledge native bytes for cleanup without
lifting its intent fence; an impossible recovery does not get a fake Retry button.
Healthy pending stays pending; if delivery already failed, request explicit Check.
Late original promise is sole adopter and cannot repeat confirmation or navigation.

BRIDGE's protected effect commands retain task/session/revision and original-intent
fences; uncertain Close blocks starts/replacement. Current-state view/highlight/theme
Refresh has its own generations, not a sticky original-outcome fence; current state
does not prove an old effect settled. Folder edits/clear/mount/recent changes retire
older local admission replies; only one native picker stays owned. Check never mutates.

A fixed unknown review does not prevent separately canceling the exact live execution
unless Cancel itself was unknown; retain both warnings/attempts and do not repeat
unknown Cancel. Explicit Close after a fixed review/control error still needs the
exact native task/session and cannot resolve the old outcome. Unknown start,
execution admission, release and Close remain fenced; disabled Close explains why.
Retained execution-admission guidance survives review reconstruction.

### Retained execution and issue presentation

Normal completion retains file lists, item and phase status for read-only review;
successful copied scope may be ordinarily verified after release. Non-stopping
degradation keeps review with independent issue axes, without resume/item retry.
Canceled/abnormal retained truth does not imply restart/domain retry. One coherent
bounded Plan window supplies execution header/rows; bursts coalesce selected-window
reads, hidden tasks retain summary rather than full browser results.

Execution row lifecycle, automatic verification, stored evidence, recording and
audit remain independent. A copy awaiting its verification is Pending, not verified;
settled verification cannot restart the copy lifecycle. Aggregate capacity yellow
needs exact retained result proof; an individual capacity-failed row independently
says Failed in yellow. Mixed/unknown/generic failure stays red, with no hidden
integrity/recording/audit failure. Location-only trash text claims neither existence,
total nor purge; richer typed I/O reasons remain later work.

#### Status card and Details layout

Status title and primary action share one row even at native minimum; active
controls may wrap to the next. Facts/status occupy two logical caption/secondary
lines left of Details and wrap long advice rather than tooltip/truncate it. Progress
follows. Status/table top inset is 16 px, status bar 8 px, rail bar 4 px, Plan
switch radius 6 px. Natural-height cards leave remaining default/larger viewport
space to the scrolling table. Sync/Integrity outer radius includes its inset.

Before execution show selection/required space/planning issues; during work show
phase/items/percent/rate/ETA; terminal facts replace stale Plan claims. Unknowns
stay unavailable. Details starts collapsed per app launch, with one nonpersisted
visibility choice across Plan/Inventory/tasks/Settings; visibility never shares facts.
Optional right column spans Setup/status/table, capped 20 rem/40%, restoring width
when hidden. Global/item cards scroll independently with 1:2 height allocation and
minimum-height chain. Recovery/Gap guidance stays central when Details is hidden.

Global Details contains current diagnostics/action messages, nonzero action counts,
issues/omissions and location-only trash. Highlighted item Details uses action/reason
first, then actual operation/recording, separate automatic/current evidence, full
paths/digests and applicable metadata. Planned and execution detail loading/failure
remain independent. Neutral fact labels use tertiary text; local display/time
formatting never alters exact stored facts. Hiding Details restores focus if inside.

The expanded item pane always exists, prompting for a highlight when absent;
click does not reopen a deliberately collapsed pane. Paths/digests use full-width
rows, other metadata 1:1.5 label/value columns with thin neutral group dividers.
Inventory file groups are presence, path, checksum/observation/result/recording,
attested facts, observed facts, dates; applicable missing/acknowledged/reappeared/
unsupported/invalidation facts remain. Folders put path before scope/object facts,
omit observed size/file-verification facts, and show folder advisory only with
eligible visibility actions. Only reviewed source observations supply operation
source paths; never infer them for target-only/structural/prior/unsupported subjects.
No ordinary operation ID, sticky shaded title, per-row Details/Close or reserved
empty diagnostics strip. Fold keeps view/selection/highlight/scroll and essential
issue/Gap/degradation guidance. Terminal time is matching-session local completion
plus nonnegative full-precision elapsed; invalid/null timing is omitted, overlapping
errors never summed. UI dates use local `yyyy-MM-DD HH:mm` consistently for rows,
hover, completion and detail, without changing machine/diagnostic values.

On review-publication-protocol-failed, retain prior settled truth, clear faulting
live decoration, disable mutation and say: **NamiSync could not publish this review
safely. Close the task and try again.** Drain/exact release continue for custody;
queued events cannot revive that generation, and the issue lasts until task Close.
Retention exhaustion directs Close/wait for retry-state expiry; population refusal
directs narrower roots or scan/preflight repair. Initial refusal has no partial
tree; replacement refusal keeps the prior complete one. Never browser-cache a
full result or transient operation hashes; BRIDGE/DEFENSE own exact hard walls.

### Execution admission and Plan again

Creating Plan/Inventory immediately shows review shell: Checking folders then
Planning/Scanning, indeterminate bar, blank table until complete publication.
Filters/actions stay unavailable. Submitted path is context, not admission evidence;
refusal returns Setup. Delayed start retains Check; fixed unknown stops animation
while retaining fence. Ready unexecuted Plan stays idle, not fabricated readiness.

Execute needs commitment, dependency-closed selection and fresh preflight. Unrun/
refused displays Execution did not start, retains committed review and fixed
actionable guidance rather than raw paths/exceptions. Reviewed-negative refusal
gets guidance without commitment. Only failed admission restores editable selection;
preflight rejection after admission does not. Pre-execution/queued capacity refusal
keeps task without execution/retry/automatic Close; planner population refusal may
have no Plan, review-preflight refusal may keep a complete negative Plan.

Plan Again freshly resolves reviewed identities/current ambiguity, creates a new
task with frozen options/default selection and no copied authorization. Changed Setup
also creates another task; no background replan/execute-anyway/autocommit. Keep old
review until new task adopted; select new only if user did not navigate elsewhere.
Original Plan identity/details/Follow/viewport remain while auxiliary activity owns
current status. Pane changes retire navigation reads; old replies cannot cross panes.

### Ordinary copied-file and selected Verify

After original release, Plan/Verify opens existing target ledger without scan/hash.
Verify copied starts ordinary scan/Verify on server-derived successful-copy scope,
can repeat with a new command after partial or linked work, and never changes
checkboxes or original results. Empty scope starts nothing. Confirmed zero successes
keeps button visible/disabled with selected-Verify guidance; unavailable summary is
not an empty scope or a new readiness authority.

Verify selected uses complete nonempty server selection, never automatic. Ordinary
Baseline/Rebaseline also use selected files; no separate linked/copied-scope baseline
button ships despite infrastructure support. Both Verify scopes share current
session controls/latest ordinary result, not original execution controls/results.
Refresh does not warn about forfeiting the retired one-shot exact action. Missing
evidence may become Baseline created, never Verified; raw verification-incomplete
classification, recording/audit issues, missing/unsupported rows and scan warnings
remain. Later scan evidence may supersede display without rewriting originals.

### Inventory review and stored evidence

Inventory is a separate bounded projection, not a Plan mode. Frozen Setup/status/
table align visually; standalone switch selects Integrity and disables Sync. Current
ledger evidence, latest ordinary overlay and actual scan publication have distinct
identities. No view/selection/Refresh silently hashes or creates baseline evidence.

Presence shows current integrity progress, then current-session/displayed-scan
ordinary results, then ledger state; a newer successful scan adopts current ledger
facts. Mismatch wins over Reappeared, then Verified/Modified/Unverified; Reappeared
alone proves no verification. Missing/unsupported/error stay explicit, ordinary
present folders green Present, rowless folders blank, scan notices neutral Notice.
Known progress uses inline bar, unknown text; settle exact current result even if
zero outcomes, repairing gaps rather than leaving rows pending.

Warnings are outside action/selection and folder rollup populations. Folder Size
is complete file bytes with own object facts in tooltip/Details; overflow is
unavailable, never clamped. Acknowledged rows remain in authoritative totals even
when hidden. Complete evidence/digests and partial/omission qualifications stay in
Details/tooltips; compact Notes carries acknowledgement, warning and size qualifiers.
Forced-color text inherits HighlightText without erasing Presence/checkbox cues.

#### Inventory controls and Details

Toolbar order: square Arrow Clockwise Refresh, Baseline split button, accented
Verify. Baseline runs directly; same-width/leading-edge dropdown offers Rebaseline
with shared menu keyboard/currentness/dismissal/focus rules. Root region keeps
Plan's two-line minimum while showing one real root. Status paragraph describes
loading/action/gap/recovery and scoped/incomplete/previous publication without
repeating rollups. Complete/hidden selection counts and scan scope live in Task
details; visible row count is not another inventory total. Shared bar stays visible,
unknown totals indeterminate, terminal stops without invented percentage.

Details shares disclosure/layout. Fact labels are tertiary; omit repeated status/
file total, redundant target path/algorithm/observed-kind/current-ledger headings.
Keep full baseline digest/attested metadata/Last verified and applicable abnormal
dates/reasons. Leading file status adopts newer same-owner windows; superseded
activity says Previous. Folder Details has path/object/scope totals and nonzero
missing/acknowledged counts, no verification fields. Acknowledge/Restore follows
facts, with compact folder-scope advisory and complete server-owned scope.

Click/Enter and accepted keyboard highlight read exact detail, including off-window
navigation. Domain rows read fresh ledger evidence; synthetic folders/notices use
published facts labeled Path at scan time. Join supplied paths to publication root
for display only; missing root keeps relative text, null notice path stays unavailable.
Task/view/Close retires detail before late replies. Refresh rereads surviving focus
under new view without stealing focus or reviving an old result.

#### Refresh and missing visibility

Refresh selected is file/folder context action, usable with Details hidden; notices
offer none. Folder scope includes hidden/off-window descendants. Acknowledge hides
missing subjects from default matches; Restore reverses acknowledgement, not files.
Visibility needs confirmed current publication/released-session eligibility; a
currently missing domain folder qualifies on its own presence, not its descendants.

Uncertain actions retain Check original outcome through navigation. Show actual
applied/noop/stale/conflict counts and unresolved suffix. Failed/pending Refresh
keeps prior complete publication with its producing scope. Current scan/status and
published scope are separately labeled: whole location, exact item, recursive folder
or selected items. Scoped completion/counts do not claim other items rescanned;
notices belong only to that scan. Selecting/changing view cannot revive older results.

Explicit delayed/stale/failed read offers Reload inventory view, reading current
publication without new scan; ordinary loading/progress/info does not. Authoritative
replacement clears recovery. Refused Refresh with retained old publication/no
current detail directs reconnect/check location then Refresh. Recovery buttons live
in top action row, preserve exact command semantics and do not move DOM focus.

### Integrity operation semantics

Baseline missing evidence only; Verify compares existing evidence or creates an
initial baseline without claiming verification. Rebaseline freshly hashes and
conditionally replaces/creates even matching/null evidence, clearing verification
freshness. Nonempty complete server selection and revision-bound blocking count/
scope confirmation are required, including all-null/mixed sets; Cancel changes
nothing. Request/view change invalidates consent. [VERIFIER](VERIFIER.md#accepted-standalone-operation-policy)
owns exact outcomes/deferred compare-and-accept. Current ordinary controls target
only that exact activity, with original-command Check and no replay. Scan scope/
counts continue describing the actual published scan, not an integrity activity.

### Context menus

Right-click targets the pointed row without changing execution selection or loading
Details; Shift+F10/Menu targets focused Plan/active Inventory row. Show details
opens that exact row; Plan selection/Expand/Collapse reuse server scope. Committed,
disabled/info Plan rows offer no selection; Inventory uses checkboxes, never context
selection. Domain file/folder rows offer Refresh selected; eligible missing/acknowledged
rows offer missing visibility, notices Details only. Opening never dispatches.

Menu currency binds nominated row, view/publication and action/session; same-row
highlight repaint alone need not dismiss, lost row/changed view does. Stale/pending/
closing/replaced owners cannot act. Owned gestures suppress browser menu, including
its Menu-key follow-up. Popup stays in viewport/work area, arrows/Home/End navigate,
Escape restores current invoker, Tab dismisses and continues. Outside/focus loss,
scroll/resize/replace/dispose dismiss without stealing focus. Pointer may preserve
partly visible-row scroll; keyboard uses current active authority.

## Presentation and responsiveness

The Python snapshot/reducer owns authoritative phase, counts, nominal active item,
display high-water and rate/ETA; BRIDGE owns scalar/event validation and cadence.
The browser formats facts, never parses diagnostics for status or derives identity
from path. Reliable item/terminal delivery stays distinct from lossy progress;
ordinary sequence holes/coalescing do not imply Gap or recovery.

Phase aggregate bytes drive percent, with known byte-free item-count fallback;
unknown totals remain indeterminate and zero/zero is not success. Settled items
are distinct from active ordinal. Row bar uses matching nominal item/attempt bytes,
not aggregate percent, and terminal outcome retires decoration. Verify cannot turn
a completed copy back into Copying. Within phase/item retain displayed high-water
through valid retry/pause/hidden return; new phase/item, Gap or retirement resets
the domain. Raw attempt counters may restart; held/100% never asserts success.

One five-second time-weighted EMA serves rate/phase ETA (`alpha = 1-exp(-dt/5s)`),
seeded by valid positive monotonic sample intervals at adapter-sink acceptance,
independent of drain/repaint/replay. Exact byte subtraction precedes approximate
ratio conversion. Unknown total or zero rate means unavailable ETA; rate may still
exist. Item handoff retains aggregate sampling; pause/resume, same-item retry or
budget change restarts it; phase/session/Gap/terminal retires it. Invalid samples
clear estimates with diagnostic feedback without blocking reliable final truth.
Equal/backward sample time rebases and leaves estimate unavailable until a positive
interval, without rejecting otherwise valid progress. Sample only newly accepted
Progress, not outcome updates carrying old Progress; navigation adopts current
estimates rather than starting another history.
No second history/filter, background timer, per-item rate, SLO or device-speed claim.

Show rate in bytes/second and phase-only time **remaining**. Round up whole seconds:
seconds below a minute; minutes+seconds through three minutes; whole minutes above
three; hours+whole minutes from an hour. Omit zero units except 0 seconds remaining.
Do not predict later Verify time from Execute. Retry catch-up may show zero rate;
verifier budget may grow. Pipeline diagnostics are separate developer observations.

Use accessible text/non-color cues, stable layout and complete elided-path labels.
Empty/unavailable/ambiguous/blocked/failure feedback names the next action. Installed
acceptance exercises native keyboard/accessibility, 200% zoom, forced colors,
reduced motion, layout-safe hostile names, exact bounded rows/identity, material
and focus/scroll ownership. Gallery-only/source-only/DOM-only evidence does not
prove native input, compositor pixels or the unresolved physical-wheel/label-blur
reports. TESTS owns exact scenario mechanics; performance observations remain separate.

History stays deferred; future activity-aware retained details are neither replay,
resume nor fallback for missing task artifacts. No task review depends on that page.

## Acceptance criteria

- A desktop request produces the same facade call, primitive views, result
  classification, and mandatory sync review as the CLI. Console entry points
  remain CLI-only, the GUI entry point retains no console, and an explicit CLI
  subprocess imports no pywebview module.
- The app starts only with Edge Chromium/WebView2, blocks external navigation
  and popups, rejects off-origin dispatch, and transports no application data
  through executable JavaScript text.
- Missing WebView2 is refused before pywebview initialization without writing
  fallback browser settings to HKCU. From the packaged page,
  `window.open('https://example.invalid/')` neither launches the system browser
  nor replaces the document, and the bridge remains usable afterward.
- File logging and the deterministic WebView2 storage path are configured before
  pywebview import. An injected headed-test root receives every local artifact
  and leaves the real per-user directory untouched.
- A bounded coalescing event drain preserves reliable item/terminal ordering,
  makes gaps visible, releases terminal sessions without disposing of their
  reviewed tasks, and closes all remaining observations on explicit close or
  app shutdown.
- Repeated task create/plan-only-close, terminal-close, and busy-cancel-close
  cycles release all process-local task artifacts and keep service, runtime,
  bridge, and adapter maps bounded while retained history remains readable.
- Hostile filenames remain structured raw data. Filesystem labels render as
  inert text with exact visible layout-control markers and bidi isolation,
  never HTML or executable content; generic Unicode and identity stay exact.
- Plan and inventory consume facade views only and remain semantically separate;
  Setup reads defaults but commits no global setting, and UI cosmetics never
  change a plan's captured options. Settings and the deferred history page cannot
  be a hidden dependency of task review.
- Busy, pausing, paused, canceled, refused, partial, degraded, mismatch, and compound
  verification outcomes are truthful and distinguishable without parsing
  strings or inferring status from bytes.
- Tests cover destructive-confirmation gating, location ambiguity, opaque-id authority,
  duplicate/out-of-order bridge responses, event-gap recovery, context target
  selection, process-local restart limits, and one-instance behavior.
- Setup and task-review headed evidence covers editable typed/picker/recent
  admission, serial multi-pair behavior, immutable plan review, bounded
  same-document re-observation, stale-response suppression, admission rollback versus retained
  preflight refusal, reviewed-
  identity Plan again, and action-guiding refusal/close states.
- Plan and inventory headed evidence proves server-owned hierarchy, accessible
  grouping, independent evidence/result axes, confirmation-gated rebaseline,
  ordinary copied-file Verify with separate original/current results, and
  no browser-retained full result.
- Exact target contracts and gates remain in
  [BRIDGE.md](BRIDGE.md), delivery coverage in
  [M1_PLAN.md](M1_PLAN.md), and test-scope policy in
  [TESTS.md](TESTS.md).
