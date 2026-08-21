# Desktop UI

Status: M1 Stage 6 design and delivery contract. M1 Stages 1–5.5 provide the
desktop's service, view, settings, session-observation, and bridge-security
seams. The classified launchers, wheel-packaged bootstrap assets, secured
product-host composition, and the production transport defined by
`M1_BRIDGE.md` now exist. Ordinary and installed-wheel evidence covers host
isolation, runtime refusal, popup/navigation guards, single-instance behavior,
native picker path confinement, committed-origin refusal, hostile text, and
logging privacy. The named browser-behavior witnesses now run through the
installed production bridge and renderer in real WebView2. Slice 3 evidence
covers transactional observation, bounded drain behavior, recovery, and
repeated bridge readiness. The fixed, non-sliding 150 ms progress-only linger
and its immediate reliable/lifecycle wake regressions have landed. An active
long poll may hold the first detailed progress snapshot for the full interval;
receipt and reliable running-state feedback bypass that linger. Benchmark
accounting now streams bounded browser/producer evidence, performs final
assembly after the child exits, and labels whole-runtime memory as a
non-acceptance diagnostic; its event pass alone is not SH-G-8 custody closure
authority. The accepted independent custody evidence below supplies closure.
The frozen/disjoint realistic corpus and production-path runner have also
landed, including exact real-deque 128/64/64 no-`Gap`, terminal path-cut,
cleanup, and clean source/dependency/runtime/digest-authority witnesses. The
committed calibration-a artifact records normative ordinary/exact-maximum
transport measurements, the separate contract freezes the 1,966,080-byte
ceiling, and three fresh holdout-b runs pass at 1,351,794 ordinary and 1,513,014
exact-maximum bytes. This closes SH-G-8 and BR-G-42 event/transport custody
only. A separate current-source one-child guard now requires both live custody
shapes to remain within that frozen ceiling on ordinary suite runs;
BR-G-45 separately leaves full terminal-artifact retention open, and
shell-owned SH-G-15 leaves version-bound whole-runtime containment open. The
earlier whole-Job delta is diagnostic input only, not a result for any of those
new predicates. GUI Break 1 and Slice 4 completed their audited realignment and
were hardened and reverified on 2026-08-17 with ordinary, scale, and real
clean-wheel headed evidence. User-facing plan, inventory, history,
and control surfaces remain; `M1_SHELL.md` owns their implementation order and
beta-package closure.

Current executor/verifier item progress now crosses the production bridge
under the expanded exact browser shape. Stable row projection and visual
consumption remain Slice 5 work.

`M1_BRIDGE.md` is the sole normative authority for bridge envelopes, commands,
errors, retry/revision identity, sequence and terminal lifecycle, and BR-G
acceptance gates. This document owns the user-facing and visual contract; it
does not restate the wire protocol.

## Purpose

NamiSync's Windows desktop is a local, headed adapter for reviewing and
controlling safe one-way mirroring, location inventory and integrity work, and
retained history. It makes the workflow's existing facts comprehensible; it
does not decide sync policy, calculate plans, write SQLite, mutate files, or
own a second session lifecycle.

The Stage 6 target is a `pywebview` host forced to Edge Chromium/WebView2 with
packaged web assets. The earlier PySide6 proof-of-concept is historical input,
not the implementation target or test contract. `ui_mockup/mockup.html` is the
starting frontend artifact to revise into the packaged UI.

## Scope and delivery boundary

Stage 6 delivers:

- a `nami-sync-gui` GUI-subsystem entry point with no retained console window;
- one single-instance desktop shell, task rail, work area, plan review,
  inventory view, and history dialog;
- desktop actions for reviewed sync, inventory, baseline, verify, rebaseline,
  semantic settings, and pause/resume/cancel where the registered activity
  supports them; and
- the WebView2 bridge, static-asset packaging, security controls, and frontend
  tests needed to make those views safe to use with hostile filesystem names.

It does not add durable plan or session storage, cross-process task visibility,
general migration, history retention, unattended execution, a settings CLI,
or a new workflow API. Session and saved-plan state are process-local in M1:
closing the desktop loses unexecuted plans and restart-resume is not promised.

## Packaging and local host state

The console and desktop entry points deliberately remain separate Windows
subsystems over one implementation. `nami-sync` and `python -m namisync` always
route through `interfaces/launcher.py` to the CLI; with no subcommand they print
usage, point to `nami-sync-gui`, and exit with the existing usage status.
`nami-sync-gui` resolves its one path authority, then lazily imports the web
host. The host acquires the fixed per-logon instance mutex before creating any
directory or logger; only the primary configures file logging and imports
pywebview. Explicit CLI work never imports or initializes pywebview.

NamiSync remains version `0.1.0` until M1 is complete. The runtime `VERSION`
alone supplies project/package metadata, logging, protocol-independent version
checks, and later frozen-file metadata. `NICKNAME` is `Gertrud` and is only a
human-facing label for About, release notes, and changelog headings; it never
enters filenames, databases, mutexes, CLI behavior, protocols, or compatibility
logic. The host stack pins pywebview 6.2.1 and pythonnet 3.1.0;
Bottle has a floor of 0.13.4, the reality-tested server version. NamiSync uses
pythonnet's default Windows .NET Framework (`netfx`) runtime and refuses a
conflicting runtime override. The existing read-only .NET Framework check is
therefore also the pythonnet prerequisite check.

One host-owned path set places production data under
`%LOCALAPPDATA%\NamiSync`: databases/settings/UI state at the root, rotating
UTF-8 logs under `logs`, and persistent WebView2 user data under `webview2`.
The GUI-only `--data-dir PATH` option accepts an absolute local root for tests
and isolated runs; it must relocate every artifact together.
The `namisync` and `pywebview` loggers share the file handler, which is installed
before pywebview import. Pywebview starts with `private_mode=True` and the
explicit `webview2` storage path; browser state never becomes plan, task, or
filesystem authority.

For editable-source UI iteration, `tools/gui.ps1` supplies a distinct
development mutex/title and roots all state beneath
`%LOCALAPPDATA%\NamiSync-Development`. Bare invocation opens the real shell;
`gallery` opens the dark component gallery by default. This developer-only
composition does not change the production launcher's arguments, environment
contract, packaged assets, or desktop behavior. `TOOLS.md` owns its exact
commands, relaunch loop, diagnostic lifecycle, and process-safety rules.

Before window creation, the primary host constructs the service and consumes
the shared database-pair facade. Fresh state initializes ledger then history;
ready state continues; refused state runs the bounded finalizer and shows the
coordinated reset action through the stable native startup dialog. It then
resolves `index.html` from package resources, creates one pending native
document and a dispatcher snapshotted from the production command mapping
defined exclusively by `M1_BRIDGE.md`, and starts only Edge Chromium with
the packaged page served on a random loopback origin. The initialized callback
binds that exact origin once. Renderer/origin failure aborts before native
window creation. An initial guard failure or pre-open loaded refusal rejects
authority, attempts public destruction once, and, if that call throws or
returns without closing, posts one owner-bound `WM_CLOSE`. Neither request
guarantees that a broken native window closes. Service, logging, and mutex
finalization follows only after the WebView loop returns; authority remains
rejected meanwhile, and cleanup never replaces the original failure diagnosis.

Native test and gallery compositions may supply an existing absolute physical
local index file directly to `run_desktop`. The production launcher never
exposes that construction-only seam through arguments, environment, page data,
or bridge traffic, and the test page is never package data.

The editable gallery launcher reuses the existing test-owned gallery child and
scenario without changing them. That child remains in the real host loop after
publishing `ready`; the clean-wheel pytest parent is what closes the acceptance
window, while a direct editable launch waits for the operator. Its manually
generated milestones are convenience diagnostics rather than headed evidence.

Frontend assets are setuptools package data and use plain same-origin ES
modules. At Slice 2 closure the wheel contained exactly `index.html`, `app.css`,
`app.js`, `bridge.js`, and `render.js`; `render.js` owns the strict
`textContent` sink. GUI Break 1 adds exactly `tokens.css`, `components.css`,
`icons.js`, `appearance.js`, four pinned local SVGs, and their `SOURCE.json` and `LICENSE.txt`
records under `assets/icons/`. The component-gallery scenario remains test-only
and absent from the wheel.
Post-realignment readiness hardening additionally packages `readiness.js` as
the neutral host-challenge receiver; it adds no second application-data bridge.
There is no npm, framework, bundler, transpiler, source map, inline script, or
inline event handler. The first running shell and installed-wheel
proof precede PyInstaller work. The frozen specification, dependency lock, CI,
third-party notices, and exact-source release material close in the final beta
packaging slice.

GUI Break 1, scheduled after Slice 3 and before production surfaces begin,
establishes the completed design-token foundation. NamiSync presents as a
Fluent 2 Windows 11 app using Segoe UI Variable for body text and
Cascadia Mono/Consolas for paths and hashes. It retains the standard native
frame. Mica is the whole-window base: the page, controller, task rail, and
resting task cards are transparent, while background/content cards use a low-
opacity primary blend over that base. High contrast,
unavailable material, or a transparency failure falls back to an opaque
system-appropriate neutral surface. M1 adds neither Acrylic nor a custom
caption.

When building, reviewing, or tuning UI elements, refer to Microsoft's official
[Fluent UI](https://github.com/microsoft/fluentui/) and
[WinUI](https://github.com/microsoft/microsoft-ui-xaml/) examples. NamiSync's
web surface remains framework-free, but the official React and XAML
implementations remain instructive for behavior, states, accessibility, and
visual details; adapt their lessons rather than importing their frameworks.

`tokens.css` is the only source file allowed to contain these exact 15 authored
red/green/blue/yellow/purple palette primitives:

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

The former yellow and purple main values retain their exact hex values as the
new `yellow-light` and `purple-light` primitives. Operation-family consumers
remain bound to `main`. The semantic-label contract below explicitly uses
light/dark family tones as supporting badge surfaces, and Dark relocating text
uses purple-light as a documented readability exception.

Palette use is main-first. When an authored family communicates identity or
state, its `main` swatch is the default color in both ordinary themes. The
family's `light` and `dark` tones normally contextualize that main—as a
supporting surface, inverse, interaction tone, or contrast fallback—and do not
replace it merely because the page theme changed. A role that intentionally
makes a light/dark tone primary without its main must be named as an explicit
exception in this visual contract and receive a same-change token and evidence
update. Contrast remains a required default and Windows forced colors remain
authoritative. If product design explicitly keeps a main foreground below the
normal-text contrast target, that exception must retain visible non-color text,
be measured rather than claimed accessible, and be recorded here. Light-theme
main text in the blue, green, yellow, and red families can fall below the
normal-text target on pale zebra rows. Dark relocating text therefore uses
purple-light while Light retains purple-main. These are explicit text-form
exceptions, not accessible-color claims. The inactive Delete filter
is the same kind of explicit red-main foreground exception on its neutral
resting fill. Selected filter pills retain contrast-safe neutral labels. Filled
semantic forms deliberately pair main-colored text with a supporting family
surface; the Light red/yellow pairs are authored visual exceptions below the
normal-text target for this review pass. Their words carry meaning independently
of color, forced colors replace them with Windows system colors, and the gallery
evidence records the exact installed pairs and measured ratios.

### Semantic color channels

Status (2026-08-21): the 15-token palette, channel-scoped aliases and
components, static projected fixtures, and gallery evidence implement this
contract. Production task and file-list surfaces remain dormant, so the
delivered visual foundation still presents no live workflow data.

Intentions and information are never conveyed through color or form alone.
Hue answers **what class** a signal belongs to; form answers **how much the
user should care**. Ordinary states use colored text. A state needing immediate
attention or action uses a more prominent form such as a filled badge, a
flashing element where motion is appropriate, or another explicit structural
cue. Urgency is never inferred from hue alone.

One rendered signal belongs to exactly one semantic channel at a time. A
component must not make one color simultaneously mean plan intent, task
lifecycle, and integrity. When separate channels need the same color family,
their channel-specific label, accessible state, surrounding context, and form
keep the meanings distinct.

In these tables, **text** means colored text without a semantic background.
**Fill** means a borderless pill-shaped badge with an 18 logical px height and
optically raised label alignment. Light uses the family's `light` swatch as the
surface and Dark uses its `dark` swatch. Dark labels use the exact `main`
swatch; Light red and yellow labels use their exact `dark` swatches so the
filled attention forms remain contrast-safe. Neutral fill uses the corresponding selected-neutral surface and
secondary neutral text. Text, icon/shape, and accessible state continue to name
the meaning. Forced colors replace authored foregrounds and fills with Windows
system colors.

#### Channel 1 — intent

Intent says what the reviewed plan wants to do. Its classes follow
reversibility because reversibility best predicts user regret.

| Class | Members | Hue | Form |
| --- | --- | --- | --- |
| Additive | `copy`, `mkdir` | blue | text |
| Relocating | `move`, `recase` | purple | text |
| Replacing | `update`, `move_update` | yellow | text |
| Removing — recoverable | `trash` | red | text |
| Removing — permanent | `delete` | red | fill |
| Nothing | `noop` | neutral | text |
| Exception | `error`, `unsupported`, `blocked` | yellow | fill |

An exception presentation overrides an operation-family presentation for the
rendered status; it does not rewrite the reviewed operation or domain result.

#### Channel 2 — lifecycle

Lifecycle describes task cards and run status.

| State or projected result condition | Hue | Form |
| --- | --- | --- |
| new / planned / queued | neutral | text |
| executing / verifying | system accent | text |
| completed | green | text |
| completed, partial / degraded / incomplete | yellow | text |
| `PAUSING` / `CANCELING` | system accent | text |
| `PAUSED` / recoverable `INTERRUPTED` | yellow | text |
| plain `CANCELED` | neutral | fill |
| execution reason `CANCELED_AFTER_PUBLISH` / `CANCELED_AFTER_MUTATION` | yellow | fill |
| `REFUSED` | yellow | fill |
| errored / `FAILED` | red | fill |

Yellow means that nothing is known broken, but the result needs user attention
and was not part of the original plan. `PAUSING` and `CANCELING` retain the
pre-stopping accent because the system is still complying with the request and
working toward a safe boundary. Once settled, `PAUSED` becomes yellow. Plain
`CANCELED` remains a low-urgency neutral result, but its filled form prevents it
from resembling a task that never started. `CANCELED_AFTER_PUBLISH`,
`CANCELED_AFTER_MUTATION`, and `REFUSED` use yellow fill because a filesystem
change may need review or a precondition needs repair.

The progress interpretation is explicit: a paused task freezes at its last
value with a yellow fill; resume returns it to system accent. A plain canceled
task freezes at its last value with a neutral-gray fill. The product may later
add a stopped count or percentage such as “stopped after 412 of 1,908” or “42%
completed” to paused/canceled presentation. That decision remains latent: this
checkpoint defines no payload, projection, or renderer field for it.

#### Channel 3 — integrity

Integrity owns the single collapsed inventory presence/integrity column.
Healthy inventory remains calm text while items requiring action use fill.

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

`REAPPEARED` is an inventory presentation condition, not an
`IntegrityResult`. It overrides ordinary `UNVERIFIED` or `MODIFIED` display and
forces yellow fill without changing the retained integrity truth. It does not
erase a stronger confirmed mismatch or error.

A future hardcoded or derived color value is possible only after an explicit
product-author design decision and a same-change contract/token/evidence update; it is
not silently synthesized by a renderer. `tokens.css` also owns channel-scoped
intent, lifecycle, and integrity aliases; neutral roles use a
pinned Microsoft Fluent light/dark subset. Native appearance retains the
observed Windows `Accent`, `AccentLight1`, `AccentLight2`, and `AccentDark1`
ramp values, while the page receives only semantic accent-fill roles. These
externally owned design inputs are tested separately from the 15
NamiSync-authored primitives. The neutral and scale values are transcribed from
pinned `@fluentui/tokens@1.0.0-alpha.24` source at commit
`32b42a5bf79c1836047dfc7fae07b1320731bce4`; exact source hashes are retained
in test fixtures. Accessible stroke roles own visible boundaries only for
components whose visual contract still uses a stroke; keyboard focus remains a
separate visible ring even on borderless controls.
`components.css`
consumes only those aliases for channel-scoped semantic labels, progress
indicators, and related controls; Slice 4-7 renderers consume
component/semantic contracts and contain
neither raw color literals nor direct palette references. The component gallery
settles light/dark mappings with visual and numeric contrast evidence rather
than inferring theme roles from swatch names. Forced colors use Windows system
colors, and text plus icon/shape/state cues keep every status understandable
without color. The gallery resolves production HTML/CSS from a clean installed
wheel and records exact installed `tokens.css`/`components.css` bytes; its own
page remains tests-only. That clean-wheel statement applies to the pytest
acceptance composition, not the editable `tools/gui.ps1` preview. Computed text
pairs must reach 4.5:1 for normal text and 3:1 for large text except for the
explicit main-first text cases recorded above. Every ordinary-theme filled
badge pair reaches the 4.5:1 normal-text floor. State indicators,
checkbox/toggle boundaries, and the textbox underline meet the 3:1 non-text
floor. Ordinary button and textbox elevation strokes are deliberately subtle
construction lines; the dual keyboard-focus stroke remains the accessible
control boundary.

The tuned component contract has two command-button tiers. Ordinary buttons
use the WinUI control composites: `#fbfbfb` fill with a subtle `#e5e5e5`
boundary in Light and the slightly lifted `#383838` fill with `#353535` in
Dark. A Windows-accent
primary modifier marks consequential actions such as Execute and Verify.
Light selects Windows `AccentDark1` as its base; Dark selects `AccentLight2`.
Hover and press retain that base at 90% and 80% opacity respectively, so Mica
or the owning control surface remains the real compositing base. Primary
button labels use exact black or white chosen once from the opaque base by the
native WCAG relative-luminance calculation. Every accent-filled label retains
that foreground through interaction, so text never reverses. The selected
Sync/Integrity half, checked boxes, and toggles use the same state ladder;
progress and selection markers consume only the base fill. Forced colors use
the system `Highlight`/`HighlightText` pair.
Filter
pills are likewise borderless: inactive pills use an inverse grayscale surface
and text pairing, while an active operation filter uses that operation family's
exact main swatch with contrast-selected grayscale text. Delete is the
deliberate exception only at rest: its inactive label is exact red-main in both
ordinary themes, while its active red-main surface uses the same contrast-safe
neutral label policy as other selected filters.
Active chip hover/press cues preserve the opaque color pair and use a small
geometric change rather than reducing opacity; plain pressed chips likewise
retain their active label color rather than carrying a latent state inversion.
Channel-scoped labels use colored text or the borderless 18 logical px filled
form required by the tables above; their words and non-color cues remain
visible in either form. Progress uses a neutral gray track with system accent
for active/resumed work, frozen yellow for paused work, and frozen neutral gray
for plain canceled work, without hover/pressed inset strokes. Forced colors
use a `Canvas` track and `Highlight` fill so completed and unfilled portions
remain distinct. The two-half
Sync/Integrity component's state contract uses
`radiogroup`/`radio` semantics: exactly one half carries
`aria-checked="true"`, and that selected half uses the live Windows accent
roles. The owning later renderer still supplies interaction behavior. These
ordinary-theme border removals do not remove keyboard focus indication or
override forced-color authority.

Ordinary keyboard focus uses Fluent's opposing dual stroke: a 1 px inner
`colorStrokeFocus1` separator and a 2 px outer `colorStrokeFocus2` ring. This
keeps the page-contrast ring distinct from inverse control fills. Mouse
activation does not request that ring. Forced colors continue to use the
system focus outline and its explicit offset.

Unchecked checkboxes use a 1 logical px neutral Fluent
`ControlStrongStrokeColorDefault` boundary (`#72000000` Light / `#8BFFFFFF`
Dark in WinUI ARGB notation, authored as CSS RGBA hex). Their selected fill and
boundary become semantic accent states while retaining the 16 px outer
geometry. Textboxes use a
separate subtle 2 px control
boundary and a stronger neutral bottom stroke at rest; focus changes only that
underline to the semantic accent fill. Mouse focus therefore does not gain a
keyboard ring, while `:focus-visible` composes the accented underline with the
shared dual focus stroke.

Elevated surfaces use a dedicated flyout boundary rather than the accessible
control-stroke role: black 6% in Light and black 20% in Dark, with opaque
Light/Dark stroke fallbacks. Dialogs and menus keep their ordinary black
elevation shadows in SDR. On a high-dynamic-range display, a dark transparent
WebView2/Mica composition suppresses those CSS shadows because Windows HDR
alpha compositing can otherwise produce a bright perimeter halo; the subtle
flyout boundary remains. The test-only gallery places normal, shadowless, and
opaque-base flyout specimens side by side so an HDR operator can distinguish a
shadow-compositing defect from a surface-alpha defect. This is a platform
fallback, not a claim that SDR shadows are defective.

The pre-Slice-5 file-list checkpoint ships three deliberately dormant surface
modules. `file_row.js` owns the shared row skeleton; `plan.js` exports only
`renderPlanRow(element, rowView)` and `integrity.js` exports only
`renderIntegrityRow(element, rowView)`. Inputs are page-local presentation
views, not bridge envelopes or compatibility contracts. Callers supply native
checkbox state, mixed state and accessible labels; depth, folder and expanded
state; display-ready basename and size text; list-specific status text; and
notes. `renderPlanRow` accepts an empty `intentKey` for a plain row, exact operation
keys `copy`, `mkdir`, `move`, `recase`, `update`, `move_update`, `trash`,
`delete`, and `noop`, or exact exception keys `error`, `unsupported`, and
`blocked`. A projected execution row may instead supply exact lifecycle key
`executing` or `completed`; its caller supplies the visible label such as
“Copying” or “Completed.” `renderIntegrityRow` accepts only `verified`,
`baselined`,
`unverified`, `modified`, `reappeared`, `unsupported`, `canceled`, `missing`,
`mismatched`, and `error`, or exact projected lifecycle key `verifying` or
`completed`. Each renderer wraps the supplied label in the
channel-scoped semantic-label component. The already-projected key selects its
fixed component role; there is no form field and JavaScript does not derive a
domain result, hue, or urgency. The renderers also do not aggregate sizes,
truncate hashes, split paths, reconstruct hierarchy, or dispatch anything. All
text still passes through `render.js`. Neither `app.js` nor `panels.js` imports
these modules, so production remains the honest empty Slice 4 shell until
Slice 5 owns validated Python projections and bridge paths.

Both lists use the same compact six-column grid, 24 px rows, 12 px row text,
and 16 px native checkboxes. The sync plan order is Selection, Filename, Size,
Operation / status, Checksum, Notes. The integrity order is Selection,
Filename, Size, Presence, Checksum, Notes: integrity classification is carried
inside the projected presence/status label because a checksum comparison is
irrelevant when the expected file is absent. Selection has no visible header text and retains
the accessible name `Selection`. The gallery exposes five focusable vertical
separators after Selection, File/path, Size, Operation/Presence, and Checksum;
Notes has no outside-edge separator. On the first pointer or Left/Right
interaction, the test-only controller reads all six rendered header widths in
one pass, freezes Selection, Size, Operation/Presence, Checksum, and Notes as
pixel tracks, and changes File/path to the sole `minmax(12rem, 1fr)` track in
one style write. That transition preserves the current visual result before
applying the requested delta. Each separator controls the preceding column. A
fixed-column delta is transferred inversely to Notes; the File/path separator
changes Notes and lets the residual flexible track absorb the result. Notes
never falls below 14 rem, the resized track never falls below its authored
minimum, intervening fixed tracks retain their widths, and the table's right
edge remains anchored. Pointer drag and Left/Right keyboard input use the same
calculation. The gallery retains those widths only in its current DOM and adds
no persistence, bridge state, or production column-layout contract. Folder rows expose a borderless disclosure
button and mixed checkboxes; projected child rows carry only their basename,
indent under the folder, and never repeat the full visual path. Plan and
integrity cells use the channel-specific semantic text or 18 logical px filled
form defined above, while JavaScript consumes only the exact already-projected
key. Zebra backgrounds belong only to
direct rendered rows, including folders; cells and columns are transparent and
the row group has no filler height, so striping ends at the final row. The
untouched grid has a 48 rem content floor. After manual resizing, ordinary
window-width changes affect File/path alone; it grows and contracts down to
12 rem while every stored pixel track remains unchanged. The effective table
minimum is the greater of 48 rem and the sum of the stored fixed tracks, the
12 rem File/path minimum, and stored Notes. Once that minimum is reached the
preserved grid overflows horizontally, so a customized 58 rem layout remains
58 rem wide in a 48 rem viewport and resumes flexing only when more space
returns. The right edge aligns with the visible container when the tracks fit
and with the scrollable table edge when they do not. Forced colors replace
colored state text with the system neutral foreground.

The component gallery owns the only current callers and fixtures. Its static
sync array covers one plain row, every operation once, all three exception
states, and a
partially selected expanded `photos` folder with two indented basename-only
children, plus explicit Copying and Completed lifecycle rows. A second static
array covers every integrity state, Verifying and Completed lifecycle rows,
and another partially selected folder with two children. Test-owned
listeners exercise computed collapse/restore and direct-child checkbox
reconciliation—including mixed to fully selected and back—without inventing
product hierarchy or recursive selection policy. Each gallery header also owns
a test-only master checkbox whose checked/mixed state is derived from every
selectable specimen row and whose change selects or deselects them all; this
settles the interaction without claiming Slice 5's server-owned selection
policy. The same driver proves stationary first-freeze geometry, inverse Notes
reserve, pointer and keyboard parity, fixed intervening tracks, 12/14 rem
clamps, File/path-only viewport response, the computed effective minimum, and
preserved-width horizontal overflow. The specimens
fill the shell's wide `work` area; a transient constrained measurement proves
horizontal overflow without leaving
the visible gallery narrow. The clean-wheel gallery passes projected row views
directly to the two installed renderers and proves the resulting DOM. Fixture
markers and gallery code are absent from the wheel. No temporary command, fake
`SyncPlan`, workflow, dispatcher, or session participates. Slice 5 therefore
begins at validated Python projection → existing bridge → the local renderers,
without a temporary data channel to preserve or remove.

The same gallery gives every lifecycle case its own task-card/status specimen
and separately exercises active, resumed, paused, and canceled progress.
Lifecycle cases do not become file rows. All fixtures pass exact display-ready
presentation values directly to production components/renderers; they do not
derive planner, dispatcher, or verifier meaning.

The same break establishes only the icon infrastructure, not the later surface
icon vocabulary. Four regular 20 px Microsoft Fluent System Icons are vendored
locally from `@fluentui/svg-icons@1.1.334` with exact package/file URLs,
per-file SHA-256 hashes, and license. A frozen
`icons.js` registry maps visual glyph names to fixed component classes; the
classes use fixed local CSS masks painted with `currentColor`. `tokens.css`
owns exact 16/20/24 px `sm`/`md`/`lg` icon sizes and `components.css` owns
alignment and states.
There is no remote load, icon font, runtime registration, inline/generated SVG,
or data-derived class/asset path. Icons remain decorative beside visible text;
icon-only controls require their own accessible name. Later slices extend the
fixed set only when their real controls make a glyph necessary.

Native appearance observes Windows light/dark/high-contrast state and live
`UISettings` `Accent`, `AccentLight1`, `AccentLight2`, and `AccentDark1` values.
The raw ramp stays native-side. The revisioned `namisync.appearance.v2`
envelope publishes only `accentFill`, its 90% hover and 80% pressed values, and
one contrast-selected foreground to packaged `appearance.js` through UI-thread
`document_channel.py`; only its exact schema and fixed CSSOM sinks are valid.
This internal document-envelope revision changes neither the persisted cosmetic
value version nor the bridge request protocol.
Observation subscribes before its mandatory initial read. Later native events
advance one coalesced generation whose current state is read and applied on the
window UI thread; a newer generation is deferred to another UI turn so stale
callback-thread snapshots cannot become newest or starve the message pump.
The installed materials composition gate applies an injected native
high-contrast snapshot and CDP `forced-colors` emulation in the same production
window, then compares resolved surfaces with dynamic system-color probes while
retaining the native Mica-off checks. It does not claim to exercise a real OS
contrast-theme transition.
The product header now includes the labelled System/Light/Dark selector carried
by the ratified cosmetic channel. It stays disabled until its initial section
read succeeds; exhausted initial transport failure leaves only that control
disabled and does not alter operational readiness. It serializes replacements,
reconciles only server-accepted state, and never mutates theme CSS
optimistically. After exhausted uncertain
replacement delivery it performs a guarded read; an unchanged revision remains
ambiguous and therefore disabled. A new page generation waits any prior
replacement settlement when the JavaScript realm remains live. After a full
document replacement, a later validated native appearance publication triggers
another authoritative section read on the healthy publication path; it
converges a late prior-document mutation without claiming a zero-stale interval
when the old realm no longer exists. Save failure remains a sanitized log event
in this checkpoint;
it does not block bridge readiness or replace the shell's operational status.
The stored override drives both the native window material and the page
tokens. Active high contrast temporarily wins without overwriting the
stored choice; system accent and reduced-motion state remain unchanged.
Component gallery `light` and `reduced` modes seed `light`, while `dark` and
`forced` seed `dark`, before window creation. The installed witness forces a
real accepted selector change, proves the choice is not rendered
optimistically, restores the seeded choice, and checks native/page agreement.
The selector is a production-owned DOM combobox rather than the browser's
native picker. Its fixed-position listbox is portaled under `body`, matches the
trigger width, aligns the selected option center with the trigger center when
space permits, and clamps to an 8 px viewport inset. Ordinary options are
transparent at rest. Hover and selection use one shared neutral overlay;
selection additionally keeps a 3 px accent pill, and press temporarily weakens
that overlay. Task cards consume the same two selection roles.
The closed trigger uses a subtle tokenized vertical
elevation boundary at rest/hover and a flat subtle boundary while pressed/open;
mouse activation does not request a focus ring, while `:focus-visible` retains
the shared dual keyboard ring. The M1 popup uses an opaque theme surface because
no Acrylic owner exists yet, plus the flyout stroke, overlay radius, and
elevation 16. Forced colors remove shadow and use Canvas, CanvasText, ButtonBorder,
Highlight, and HighlightText through system-owned tokens. Microsoft's official
[XAML styling guide](https://github.com/microsoft/microsoft-ui-xaml/blob/main/docs/design-notes/xaml-styling-guide.md)
is the reference for the closed control-elevation boundary.
The host loads the cosmetic authority before choosing the opaque fallback
background or creating the window. That same initial effective snapshot feeds
title-bar/material policy, the appearance controller, and the first page
appearance envelope; page-side section initialization remains post-`OPEN` and
cannot delay readiness. The precreate opaque background and first authoritative
appearance envelope use the same override, and settled native/page presentation
must agree; this is not a compositor-level claim of flash-free first paint.
The native window is constructed at 1280 x 800 logical pixels with an explicit
1024 x 640 logical-pixel minimum through pywebview's public `create_window`
arguments. Pywebview's WinForms backend performs the DPI conversion; NamiSync
does not mutate `window.native.MinimumSize` or correct geometry from JavaScript.
The former viewport media query is removed. A 48 rem inline-size container
query retains the stacked reflow because WebView2 zoom can still make the CSS
viewport narrower than the logical host dimensions.
Opaque fallback requires sufficient structured backdrop/glass/form/controller
landing evidence. A live reapply that confirms neither native path publishes
`degraded`, which returns the page itself to its theme-correct opaque base;
initial configuration, observation, or publication failure degrades over the
opaque window baseline. Startup refuses only when native enhancement may have
changed that surface and an opaque rollback cannot be confirmed. Appearance remains
subscribed through incomplete or exceptional close attempts and closes once
only after complete service close, before destruction. Shared dialogs likewise
retain their ordinary lifecycle:
`data-closing` runs the compatible exit state before the owner calls `close()`.

Motion tokens and Fluent easing curves live in `tokens.css`; controls,
expand/collapse, progress, and dialog transitions consume those shared values.
`prefers-reduced-motion` reduces or stops non-essential motion. Virtualized row
creation and recycling never animate, so scroll performance and row geometry
remain stable. GUI Breaks tune choreography without creating another motion
contract.

M1 does not bundle or automatically invoke the Evergreen WebView2 Bootstrapper.
The supported target remains Windows 11; missing WebView2 is refused read-only
with an official installation direction. M1 beta binaries may be unsigned and
must publish hashes, exact source identity, and an honest warning that Windows
or enterprise policy may block unknown unsigned code.

## Adapter boundary

The desktop imports only `NamiSyncService` and its primitive workflow views.
It must not import `core`, `modules`, `db`, CLI internals, or construct a
dispatcher, runtime, workflow request, repository, or recorder.

The service already provides the desktop's command surface:

```python
start_plan(source, target, *, deletion_policy=None, command_id=None,
           observation_sink=None) -> PlanSession
start_execution(request_id, *, verify_after_execute=False) -> ExecutionSession
start_inventory(...), start_baseline(...), start_verify(...), start_rebaseline(...)
read_semantic_settings() -> SemanticSettingsView
commit_semantic_settings(patch) -> SemanticSettingsView
```

`SessionObserver.observe(session_id, sink)` supplies primitive current-state
and event/record views. Plan start's optional sink is attached transactionally
before the session can run. `M1_BRIDGE.md` exclusively defines the recovery
cursor and command-receipt identity exposed across the wire. The desktop owns the bounded
presentation queue fed by that sink; it does not expose raw dispatcher streams to JavaScript. It must
unsubscribe on task close and close every observation before service shutdown.

An initial loaded-time security, unsafe-surface, or document-readiness refusal
closes dispatcher admission and wakes the task registry before appearance
teardown or any window close request. Public destruction is attempted once;
after a throw or a return without closure, the host posts one `WM_CLOSE` to its retained
native window handle so the startup-refused path can release the GUI loop. A
failure of both close paths never reopens authority or replaces the original
startup diagnosis.

Native load alone does not open a document. The packaged module installs its
neutral readiness receiver before the appearance receiver and shell DOM, then
sends `shell_ready` through the existing sole `dispatch` function. After safe
base-surface settlement, the host posts a current-generation nonce; the page
echoes it through `readiness_echo` and shows `Ready` only after a truthful
acknowledgement. Startup rechecks document-epoch ownership after each wait, so
a raw API notification cannot advance a superseded attempt. Ordinary commands
remain unavailable until native security/load, shell acknowledgement, safe
surface settlement, and the neutral post/echo roundtrip converge. The nonce is
liveness evidence only, never authorization, and is neither logged nor
persisted. A fixed five-second product deadline starts at each native `loaded`.
Before the first open generation, missing acknowledgement, unsafe surface, or
failed neutral publication enters the direct fail-closed startup-refusal path.
Appearance publication continues independently and may degrade. After an
earlier generation opened, a reload refusal that
wins while the host remains open records the diagnosis and uses the ordinary
bounded service-close state machine, preserving active-work teardown. A close
already in flight retains ownership and the later refusal cannot replace it.
The visible `Ready` label waits for the bilateral readiness acknowledgement. A
same-origin reload closes normal admission until the new packaged document
completes the same handshake; stale timers, acknowledgements, and queued posts
cannot settle a later generation.

`NamiSyncService.close()` is bounded but not instantaneous: its derived
allowance is twelve seconds, reached only when the audit writer is genuinely
wedged, and a healthy close returns in milliseconds. The host must therefore
never call it from pywebview's `closing` callback, which pywebview runs
synchronously on the WinForms UI thread — a window that stops pumping messages
is marked unresponsive by Windows within a few seconds. The close handler
returns `False` to veto the immediate close, shows a determinate closing
affordance, runs the ordered teardown off the UI thread, and closes the window
programmatically when the `ShutdownView` returns. An incomplete shutdown stays
visible rather than being swallowed by window destruction. The implemented
controller rejects new bridge admission, closes the task registry to wake
drains and capacity-blocked sinks, waits for admitted calls, unsubscribes task
observations, then calls the service. A complete result permits one recursive-safe
programmatic destroy only after window-owned appearance observation closes
exactly once. An incomplete result or exception keeps the window open with
appearance observation still active,
sets fixed retry guidance in the packaged status element, and presents an owned
native Retry/Cancel dialog. Only its Retry choice starts another worker; another
title-bar close can reopen the dialog but neither retries nor force-closes.
Each loaded document binds its current status element before a close worker may
render, so a late worker never queries a destroyed or replaced document;
presentation failure is sanitized and cannot change shutdown truth.
`classify_result()` supplies the single headline and independent filesystem,
integrity, recording, audit, disposition, and cancellation axes. The frontend
renders those facts; it never reimplements headline precedence or parses
diagnostic text.

Location commands bind one explicit root or retained location id before
admission. `LocationResolutionError` already carries the five visible states
(`resolved`, `offline`, `ambiguous`, `root_missing`, `root_unavailable`), exact
candidate mounts, and corrective detail. The UI must request a user-selected
mount for ambiguity rather than inferring one from a mapping or prior task.

Semantic settings and UI state are deliberately separate. Semantic settings
are read and partially committed through the facade, then captured immutably
by planning. The ratified `ui_state.py` replacement will own a strict,
section-versioned cosmetic document; schema v1 contains only the appearance
override. Recents, geometry, columns,
sorting, treegrid expansion/grouping state, and filter chips remain planned
typed sections, including the state later needed by the file-list treegrid. It
must not become
another semantic-settings or session store.

## Bridge and renderer security

The host exposes one function-table `dispatch` entry, and only packaged
`bridge.js` references `window.pywebview`. `M1_BRIDGE.md` exclusively defines
the complete envelope bound, immutable command mapping, opaque identities,
exact errors, deadlines and retry classes, revision rules, drain recovery,
sequence/`Gap`/terminal semantics, and terminal-session release versus explicit
task close. This document requires those mechanisms to produce actionable,
path-sanitized UI feedback; it does not duplicate their wire contract.

NamiSync-owned code never constructs JavaScript or calls `evaluate_js`,
`run_js`, or `Window.state` as an application-data channel. Pinned pywebview
6.2.1 internally constructs JavaScript to return exposed-function results, so
its serializer/escaper and the real-browser hostile-name round trip remain part
of the security boundary. The exact pythonnet 3.1.0 pin is equally part of that
boundary because native delegate subscription, WinForms thread affinity, and
`CoreWebView2` access pass through it. Browserless/Node probes are supplemental;
the exception is the ordinary, non-skippable drain-manager Progress
validator/replay gate, which resolves Node.js from `NAMISYNC_TEST_NODE` before
`PATH` and proves atomic rejection before cursor or reliable-sibling delivery.
The installed real-WebView2 witnesses own the remaining named
browser-behavior gates.

The host must force `gui="edgechromium"` and fail with an install action if the
Microsoft Edge WebView2 Runtime is unavailable; silent MSHTML fallback is not
acceptable. Before `create_window` it calls the shared host preparation, which
sets
`OPEN_EXTERNAL_LINKS_IN_BROWSER=False`, `ALLOW_FILE_URLS=False`,
`ALLOW_DOWNLOADS=False`, and `REMOTE_DEBUGGING_PORT=None` and performs only
read-only WebView2 runtime registry access through one side-effect-free
compatibility module. It mirrors pinned pywebview 6.2.1's .NET prerequisite,
accepted Edge channels, and HKCU/HKLM architecture routing, with executable
upstream parity coverage. The `86.0.622.0` token is retained because that
backend passes it to its compatibility helper; NamiSync mirrors the helper's
actual comparison and makes no security-patch freshness claim. A configured
`WEBVIEW2_RUNTIME_PATH` bypasses only Edge-channel discovery, not the shared
.NET/netfx prerequisite read. One typed probe snapshot supplies
both availability and refusal reason: an absent prerequisite names .NET or
WebView2, while an unreadable or malformed registry state reports detection
failure and recommends repair instead of falsely claiming a component is
missing. Host preparation never repeats the .NET registry read merely to choose
its message. The start wrapper repeats
preparation, passes `debug=False`, and uses one zero-argument `initialized`
callback that verifies the selected renderer before invoking the host callback.
Every shipped JavaScript primitive must also run at that admitted floor:
own-property checks use the compatible prototype call, ARIA roles use explicit
attributes, and opaque bridge identities use `crypto.getRandomValues` rather
than newer convenience APIs. Static installed-wheel guards and the real
WebView2 accessibility witness cover that implementation side of compatibility.
Once the static asset server has selected its random loopback port, the host
callback derives the exact origin from the complete `window.real_url` with
`urlsplit` and registers an
idempotent synchronous `before_load` callback. On the WinForms UI thread
`before_load` reaches
`CoreWebView2` and attaches the tested `NavigationStarting`,
`FrameNavigationStarting`, `NewWindowRequested`, and `SourceChanged` handlers
exactly once before application calls are exposed; setup and dispatch workers
never access the UI-affine native object. Top-level navigation outside the
exact packaged asset origin is canceled, every frame navigation is canceled,
and every popup is handled. Attachment failure is sticky and observable:
dispatch remains closed and the host tears down the dead window with an
actionable message after load rather than relying on an exception that
pywebview logs and swallows.

`dispatch` independently rechecks a lock-protected snapshot of the native
committed `CoreWebView2.Source` on every call. It does not authorize from
pywebview's managed `Source` or `get_current_url()`: both can report a rejected
navigation target after WebView2 canceled it and retained the packaged
document. A canceled request leaves the snapshot unchanged, while a genuinely
committed off-origin source replaces it and causes dispatch to fail closed.
Origin authorization is an entry-time admission check; the bridge neither
holds the document lock across a handler nor rolls back completed work if
navigation or reinjection makes its response undeliverable. That state is
uncertain delivery, not uncertain commit; `M1_BRIDGE.md` owns the corresponding
retry and recovery rules. The packaged static-asset server is not an API or
event channel.

The frontend places the restrictive CSP meta element first in `<head>` so no
earlier resource escapes it; `frame-src 'none'` independently blocks frames
during initial parsing before the native hooks exist. DOM APIs such as
`textContent` render all filesystem-derived data. The frontend must never use
`innerHTML`, build executable script from returned data, or interpolate a
filename into an attribute, URL, command, style, or bridge request.
Hostile-name fixtures are required end-to-end.

Filesystem-derived row labels use the narrower `renderFilesystemText` sink.
It maps `DEFENSE.md`'s exact layout-control set and literal marker delimiters to
injective uppercase `⟦U+XXXX⟧` markers, then delegates to the sole
`textContent` writer. The label is a bidi isolate. This final presentation
projection neither mutates nor caps filename display in Python/wire/search;
callbacks separately receive raw opaque node ids. Marker spelling has no
decoding or search meaning.
Trusted shell copy continues through the generic inert-text sink. Ordinary
markup-like text, Arabic, Hebrew, combining sequences, emoji/variation
selectors, ZWNJ/ZWJ, and long labels remain exact.

## Interaction contract

Slice 4 establishes only the presentation core and honest shell frame. It adds
no presentation command or placeholder plan, inventory, history, or control
surface. The page exposes labelled
task navigation and a work region with truthful empty states under the standard
native title frame. `rail.js` and `panels.js` own that accessible frame; they
do not create fake task or session data.

The shared `tree.js` consumes only windows already decided by Python's pure
`visible_sequence.py`. It renders at most 256 returned rows plus fixed virtual
spacers, uses exact 28-CSS-pixel rows and the filesystem-text helper, exposes
the complete layout-safe label to accessibility even when the visual label elides, and ignores a
stale response generation. The root is the single Tab stop, row focus uses
`aria-activedescendant`, and server-derived level, sibling-set, parent, and
first-child metadata support Up/Down/Home/End/Left/Right/Enter navigation even
across a window boundary. `aria-expanded` and the disclosure appear only when
the active filtered projection retains an immediate child: expanded and
collapsed projected parents emit `true` and `false`, while leaves and
structural containers with no retained child emit no expansion state. It never
lets an active descendant remain outside the tree viewport: keyboard movement
and a completed off-window target use the fixed 28-pixel global index to reveal
the entire row without scrolling an outer surface. User scroll bursts and
layout-only tree-root resizes enter the same coalesced animation-frame
reconciliation. Crossing a virtual spacer requests the missing leading or
trailing global index with the tree-owned generation;
the returned page preserves `scrollTop` and cannot snap the viewport. Scrolling
within a covered window sends no request and moves only presentation focus to a
fully visible rendered row when one is available; otherwise it clears the
active descendant until a covering commit. Neither outcome invokes domain
activation. An external projection request takes priority over scroll state
from the old DOM, and stale page responses are refused before their payload is
read. Clicking a disclosure
focuses that row and requests exactly one expand/collapse change without
activating it; clicking the label activates as usual. It never filters a viewport, reconstructs ancestry,
searches a path, owns selection, or talks to the bridge. Slices 5 and 6 remain the first owners
of real plan/inventory rows and their command wiring. The exact Python
structural/search/filter/window/anchor contract and installed shell/tree
contract live in `M1_BRIDGE.md`; the installed shell/tree witness is SH-G-7 in
`M1_SHELL.md`.

A valid scroll page is terminal for the viewport snapshot that requested it.
If it is narrower than the viewport, the renderer waits for a later viewport
change rather than automatically alternating requests between missing edges;
the owning view is not subject to an implicit minimum page width.

The Slice 4 frame has two labelled structural regions beneath the header: task
navigation stating that no tasks are available and a work region stating that
no task is selected. Landmarks are not gratuitous tab stops; the first real
tree is the operable widget. The completed clean-installed-wheel SH-G-7 run uses
native keyboard events, platform accessibility inspection, native 200% WebView
zoom, and forced-colors emulation against production assets. It verifies focus order and visibility,
usable stacked reflow without horizontal overflow, system-color focus,
exact layout-control markers with no surviving active controls, unchanged
ordinary hostile/Unicode and long labels, raw callback ids through `tree.js`,
exact 28-pixel rows, no more than
256 rows plus two spacers, and stale-generation refusal. Python is the sole
validation/window authority and emits the exact renderer view. One canonical
temporary JSON manifest is produced through the real workflow tree,
visible-sequence, window, and wire-view functions; the direct Node probe and
installed WebView2 child consume those same bytes, and Python, child, and page
SHA-256 values match. Its cases cover the `head`, `next`, `tail`, `empty`,
`maximum`, and `layout_control` views, expansion tri-state across the pointer
and projected-empty views, and ordinary-Unicode and long-label values carried
by `next`.
The real workflow fixture uses representative admitted layout controls; the
exhaustive fixed-set sink probe is renderer-local because C0 characters are not
valid Windows filename input. JavaScript does not duplicate structural
validation. Before removing a tree root, its owner disposes the controller;
that idempotently disconnects resize observation, removes controller-owned root
listeners, invalidates pending work, and makes an already queued frame inert.
The manifest remains test-only and absent from the wheel. This
evidence adds no bridge
command or synthetic domain state. Slice 5 remains the first real plan surface.

The rail itself is a Mica seam: it has no card background, border, or shadow.
A resting unselected task card is fully transparent. Hover and selected/current
rest use the same neutral selection overlay; press temporarily weakens it.
Selected/current cards retain a 3 px sampled-accent marker,
so hover never erases selection. Task cards have no painted border or elevation
in ordinary themes. In forced colors,
every enabled selected/current card pairs the `Highlight` surface with
`HighlightText` and an opposing marker; disabled cards retain `GrayText`, and
keyboard focus retains a system-visible outline. Selection is conveyed
with `aria-selected`/`aria-current` and is not
inferred from a task's running status.

Background/content cards are a separate static component role. They do not
react to hover or press. Light uses a solid `#EBEBEB` stroke fallback beneath a
black 6% blended stroke and a white 70% primary fill; Dark uses a solid
`#1C1C1C` fallback beneath a black 10% blended stroke and a white 5% primary
fill. The token foundation also retains the supplied secondary and tertiary
blends for state/context use. Forced colors replace these material blends with
opaque system surfaces and boundaries.

The task rail is a presentation grouping over live service sessions and
retained history, not a new durable task model. It shows activity kind, source
and target when applicable, current phase, progress, and a truthful terminal
headline. Subject-only activities do not fabricate a source-to-target label.
An accepted pause immediately renders **Pausing…** from the existing `pausing`
session state and remains distinct from **Paused** until custody actually
releases. Repeat pause/resume is disabled during that drain, cancellation stays
available, and the next state may be paused or terminal if the active operation
settles the run first.
Successful terminal presentation releases only observation/session authority;
the reviewed plan, task identity, and presentation remain. Task close is a
separate explicit user action, with confirmation/control when work is still
queued or busy. `M1_BRIDGE.md` exclusively defines the exact release and close
commands, ordering, retries, and retained artifacts. Retained history remains,
and the UI never treats a transient progress flag as completion.

Sync remains a two-session interaction: plan first, review its immutable
fingerprint-bound intent, choose a dependency-closed selection, then start
execution with fresh preflight. The service decides whether the selection needs
an explicit destructive confirmation; the browser never derives that risk or
requires a typed phrase. Editing selection or plan-affecting options requires a
new commitment. There is no execute-anyway, auto-commit, or unattended path.
`verify_after_execute` is an explicit option; when selected, the one execution
session may return ordered operation and integrity items plus ordered phase
summaries.

Plan review shows executable operation ids, dependencies, reasons, source and
destination, bytes, evidence, conflicts, blocks, and deferred outcomes. A
folder or rename grouping is presentation only and never turns into a hidden
directory mutation. The UI distinguishes refusal, all-noop, partial, canceled,
failed, mismatch, verification-incomplete, and recording/audit degradation
from the typed result axes rather than color or byte totals alone.

Inventory is retained state distinct from plan state. Its location scope,
completeness, observed/missing counts, presence, and evidence come from
`InventoryDetailsView` and `InventoryRowView`. Refresh, baseline, verify, and
rebaseline reuse one action definition across buttons and context menus.
Selected paths are exact root-relative scope; rebaseline always asks for its
explicit acceptance intent. A context action first establishes a valid target
row, and blank space targets nothing.

History uses retained activity-aware envelopes and details. It exposes all four
truth axes and ordered items/phases, including compound execute-to-verify runs.
Restoring a prior run means starting a fresh plan; history is not a replay or
resume surface.

## Presentation and responsiveness

Progress is replaceable telemetry. The browser receives exact core event v4
snapshots through a `SessionEventView` that exposes the nested event
`schema_version`; the containing bridge command/response schema remains v1.
Every snapshot self-describes its phase and may carry optional nominal
active-item identity plus an opaque attempt id and paired attempt-local byte
counters alongside aggregate bytes, item counts, and the display path. Only
nominal identity may locate a row; `item_type` selects the opaque id's
operation/integrity lookup namespace and `current_path` remains informational,
may outlive an intermediate or terminal settlement, and never implies an
active item when nominal identity is absent. Executor cancellation/exception
publishes live aggregate item and byte state after reliable unwind settlement
while clearing nominal item state and `current_path`. Executor pause publishes
one coherent live snapshot that retains the active item, attempt, and path; its
live aggregate high-water also continues through resume. Verifier pause
publishes its live reporter state.
Attempt counters may restart only under a newly minted attempt id when an
actual retry or resumed copy/read stream begins. If work exceeds the admitted
item total, item and attempt identity stay active but the determinate byte pair
becomes absent, while aggregate progress retains the producing module's
monotonic semantics. The dormant row renderers do not yet consume these fields.
Executor pipeline diagnostics are opt-in developer data, not the rolling
transfer rate or ETA promised to users.
Filter/search state never changes the underlying plan or inventory selection;
changing a location or plan option invalidates only the state that semantically
depends on it.

The first real plan/inventory search owner uses a fixed 150 ms trailing
debounce. Every search, filter, or collapse intent invalidates earlier response
generations immediately; only the final search in a burst is dispatched, stale
successes and failures are ignored, and the current valid page remains visible
while pending. The pure Slice 4 helper therefore admits the documented bounded
literal query rather than substituting an arbitrary responsiveness limit.

Use accessible text and non-color outcome cues, stable layouts, and full-path
accessibility text for elided paths. Empty, unavailable, ambiguous, blocked,
and failure states must say what the user can do next. The desktop presents as a
Fluent 2 (Windows 11) app that follows the system light/dark theme and reads the
system accent, over a standard window frame on a Mica base; the visual authority
is the design-token/material/motion contract above.
Contrast and no-color-only signaling remain requirements in every theme.

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
- Plan, inventory, settings, and history consume facade views only and remain
  semantically separate; UI cosmetics never change a plan's captured settings.
- Busy, pausing, paused, canceled, refused, partial, degraded, mismatch, and compound
  verification outcomes are truthful and distinguishable without parsing
  strings or inferring status from bytes.
- Tests cover destructive-confirmation gating, location ambiguity, opaque-id authority,
  duplicate/out-of-order bridge responses, event-gap recovery, context target
  selection, process-local restart limits, and one-instance behavior.
