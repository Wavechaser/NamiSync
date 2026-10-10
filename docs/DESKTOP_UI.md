# Desktop UI

The secured host, theme/accessibility foundation, generic tree renderer and
file-row gallery are implemented. Process-live tasks expose frozen Setup and
typed/picker/recent plan and standalone inventory starts. Production Plan
review, execution admission and live pause/resume/cancel controls are active;
retained execution-result review is active in that Plan pane. Inventory has a
separate bounded read pane with search, facets, sibling sorting and current
evidence details, Refresh and missing-item visibility controls. Hashing controls,
history and full settings remain pending. Current v5 item
progress and detailed result rows are reduced by the bridge for bounded display.

This document owns visual/user interaction behavior. BRIDGE owns exact transport,
PRESENTATION owns projection/window/search/sort behavior, INTERFACES owns the host,
and M1_PLAN owns remaining delivery. Historical build and calibration recaps are
archived with the original plans; current bridge evidence has one BRIDGE owner.

## Purpose

NamiSync's Windows desktop is a local, headed adapter for reviewing and
controlling safe one-way mirroring, location inventory and integrity work, and
retained history. It makes the workflow's existing facts comprehensible; it
does not decide sync policy, calculate plans, write SQLite, mutate files, or
own a second session lifecycle. Live execution refresh does not interrupt a
foreground view, highlight, selection, or scroll interaction; changed ownership
replays the refresh at the accepted window, while navigation, Settings,
and stale or failed receipts remain inert toward visible result/detail facts.
A replacement document retires the window's authority and requires reopening.

The Stage 6 target is a `pywebview` host forced to Edge Chromium/WebView2 with
packaged web assets. The earlier PySide6 proof-of-concept is historical input,
not the implementation target or test contract. `ui_mockup/mockup.html` is the
starting frontend artifact to revise into the packaged UI.

## Scope and delivery boundary

Stage 6 delivers:

- a `nami-sync-gui` GUI-subsystem entry point with no retained console window;
- one single-instance desktop shell, Setup, process-live task rail, work area,
  plan/execution review, and inventory/integrity views; the history dialog is a
  later M1 surface outside the accepted second-half reslice;
- desktop actions for reviewed sync, inventory, baseline, verify, rebaseline,
  per-task Setup overrides, and pause/resume/cancel where the registered
  activity supports them; global semantic-settings mutation remains deferred;
  and
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
The gallery is a natural-height specimen document with page scrolling; it does
not inherit the task shell's viewport-height limit. Installed gallery checks
reject overlap between its top-level specimen sections.

Scrolling remains browser-owned. The bundled WebView2 SDK supports
[`ScrollBarStyle = FluentOverlay`](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2environmentoptions.scrollbarstyle),
but pinned pywebview 6.2.1 creates its environment through
`CoreWebView2CreationProperties` and `EnsureCoreWebView2Async(None)` without an
environment-options hook. Changing the scrollbar after initialization is not
the supported API path. No vendor patch or environment override is installed;
Microsoft classifies the Fluent scrollbar browser flag as
[development-only](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/webview-features-flags).
Native integration is deferred to M2: the feasible Windows-backend change also
requires coordinated startup, early navigation/HTML-loading and rendering tests,
which is not justified solely for the M1 scrollbar. Current CSS
approximates Fluent with a small fixed gutter: the softened rounded thumb is
always thin at rest and wider on direct hover/drag, with no extra pressed
highlight or pane show/hide logic. The track uses a subtle neutral fill. Wheel, keyboard,
track clicks and dragging remain native; forced colors use browser defaults.
The fixed gutter avoids hover layout shifts but cannot paint over content like
native Fluent. CSS also does not reproduce native fade, input-method awareness
or system-preference parity. Microsoft's [scroll viewer guidance](https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/scroll-controls)
describes the thin-to-wide behavior; Chromium's [scrollbar styling guidance](https://developer.chrome.com/docs/css-ui/scrollbar-styling)
explains the classic gutter introduced by custom scrollbar dimensions.

Tables share a CSS layout with a vertical body scroll area below the header.
Both header and body reserve the same stable gutter, including when rows fit;
the header does not display a vertical scrollbar. Shared column tracks keep
their cells aligned. One outer horizontal scroll area moves both together and
shows its scrollbar only when needed. This uses the
[CSS stable-gutter contract](https://www.w3.org/TR/css-overflow-3/#scrollbar-gutter-property),
including hidden-overflow header compensation, without measuring scrollbar
widths or repeatedly correcting column positions in JavaScript. File-column
resize gestures retain their existing initial width snapshot.

Before window creation, the primary host constructs the service and consumes
the shared database-pair facade. Fresh state initializes ledger then history;
ready state continues; refused state runs the bounded finalizer and shows the
coordinated reset action through the stable native startup dialog. It then
resolves `index.html` from package resources, creates one pending native
document and a dispatcher snapshotted from the production command mapping
defined exclusively by `BRIDGE.md`, and starts only Edge Chromium with
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
`icons.js`, `appearance.js`, pinned local SVGs, and their `SOURCE.json` and `LICENSE.txt`
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
exceptions, not accessible-color claims. The generic inactive Delete chip
is the same kind of explicit red-main foreground exception on its neutral
resting fill. Plan and Inventory use a neutral Filter trigger with an accent
fill only when canonical category settings are active. Filled
semantic forms deliberately pair main-colored text with a supporting family
surface; the Light red/yellow pairs are authored visual exceptions below the
normal-text target for this review pass. Their words carry meaning independently
of color, forced colors replace them with Windows system colors, and the gallery
evidence records the exact installed pairs and measured ratios.

### Semantic color channels

Status (2026-09-10): the 15-token palette, channel-scoped aliases and
components, static projected fixtures, and gallery evidence implement this
contract. The task rail uses neutral lifecycle text; production workflow and
file-list color consumers remain dormant.

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
**Fill** means a borderless badge with an 18 logical px height and optically
raised label alignment. Light uses the family's `light` swatch as the
surface and Dark uses its `dark` swatch. Dark labels use the exact `main`
swatch; Light red and yellow labels use their exact `dark` swatches so the
filled attention forms remain contrast-safe. Neutral fill uses the corresponding selected-neutral surface and
secondary neutral text. Standalone badges may remain pill-shaped; compact
file-list badges share the checkbox's 4 px radius, use 4 px inner padding on
both sides, and bleed that same 4 px into the leading cell padding so filled
and unfilled text align. Text, icon/shape, and accessible state continue to name
the meaning. Forced colors replace authored foregrounds and fills with Windows
system colors.

#### Channel 1 — intent

Intent says what the reviewed plan wants to do. Its classes follow
reversibility because reversibility best predicts user regret.

| Class | Members | Hue | Form |
| --- | --- | --- | --- |
| Additive | `copy`, `mkdir` | blue | text |
| Relocating | `move`, `rename`, `recase` | purple | text |
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
| capacity exhaustion or capacity refusal | yellow | fill |
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
contract defines no payload, projection, or renderer field for it.

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
use WinUI's translucent control fills rather than opaque RGB approximations.
In CSS RGBA order, Dark rest/hover/press/disabled use `#ffffff0f`,
`#ffffff15`, `#ffffff08` and `#ffffff0b`; Light uses `#ffffffb3`,
`#f9f9f980`, `#f9f9f94d` and `#f9f9f94d`. Textboxes and combobox triggers
share these control-fill roles. Focused textboxes use the native input-active
role: `#1e1e1eb3` in Dark and opaque white in Light. Alpha applies to the fill,
not the whole element, so text and glyphs retain their own contrast.
Light ordinary-button borders retain black 0F on the top/sides and 29 below;
Dark uses white 18 on the top/sides and 12 below, flattening to black 0F or
white 12 when pressed or disabled (hex alpha).
Accent buttons use white 14 over black 66 in Light and white 14 over black 23
in Dark for normal/hover elevation; pressed and disabled accent borders are
transparent.
Ordinary button borders flatten to the neutral stroke when pressed or disabled;
checkbox and toggle strokes use an authored 1.2px width to bias Chromium's
fractional-DPI snapping;
this is a local visual adjustment, not native WinUI thickness or a guarantee
of identical physical pixels across displays. Native 1 logical px and the
original elevation roles were referenced from Microsoft's
[Button resources](https://github.com/microsoft/microsoft-ui-xaml/blob/main/controls/dev/CommonStyles/Button_themeresources.xaml)
and [common colors](https://github.com/microsoft/microsoft-ui-xaml/blob/main/controls/dev/CommonStyles/Common_themeresources_any.xaml).

The GUI-D7 disabled-button label investigation found no element-wide alpha,
filter or transform in the button path. Light and Dark use dedicated opaque
disabled foregrounds (`#bdbdbd` and `#5c5c5c`), consistent with Fluent's
separate disabled-label brush rather than fading the whole control. The clean
installed gallery did not reproduce the intermittent blur, so production CSS
is unchanged. WebView2 defines rasterization scale as the combination of
monitor DPI and text scaling and tracks monitor changes; Microsoft also records
[high-DPI blurry-text](https://github.com/MicrosoftEdge/WebView2Feedback/issues/571)
and [transparent-host rendering](https://github.com/MicrosoftEdge/WebView2Feedback/issues/4945)
reports. Those make a renderer/compositor condition plausible, not proven.
Reopen with the WebView2 runtime version, monitor DPI and text scale,
active/inactive and monitor-move state, HDR/material state, and a same-frame
capture of enabled and disabled labels; whole-surface blur should be diagnosed
through the host's
[rasterization-scale contract](https://github.com/MicrosoftEdge/WebView2Feedback/blob/main/specs/RasterizationScale.md)
before changing color tokens.

Textboxes paint one translucent fill clipped to the padding box. Their top and
side edges use the authored 1.2px control stroke; the ordinary lower border is
transparent and a single straight 2px border-box layer supplies the neutral or
accent strip. The rounded outer clip tapers the strip ends instead of bending a
2px physical border up both sides. Focus changes the strip to accent. A
capture-phase pointer marker suppresses the shared dual ring only for a clicked
textbox and clears on blur; keyboard traversal retains that ring. Disabled
textboxes remove the strip and flatten every edge to black 0F in Light or white
12 in Dark; their fill follows the disabled control role.
Forced colors remain system-owned. The mapping follows the same
[common resources](https://github.com/microsoft/microsoft-ui-xaml/blob/main/controls/dev/CommonStyles/Common_themeresources_any.xaml),
[textbox resources](https://github.com/microsoft/microsoft-ui-xaml/blob/main/controls/dev/CommonStyles/TextBox_themeresources.xaml)
and [combobox resources](https://github.com/microsoft/microsoft-ui-xaml/blob/main/controls/dev/ComboBox/ComboBox_themeresources.xaml).
Popup material and shadow composition remain separate from trigger fills.
The combobox trigger paints its fill once, with independent top/side/bottom
strokes; it no longer stacks a fill gradient over a second fill and a full-area
border gradient. This preserves the intended alpha over its actual parent.
Its authored 1.2px perimeter matches buttons and textboxes while retaining
native black 0F/29 elevation edges in Light and white 18/12 in Dark;
pressed edges flatten to black 0F or white 12 respectively. The separately tuned
ordinary-button stroke tones above remain a local choice.
A Windows-accent
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
The gallery's generic operation-chip specimens are likewise borderless:
inactive chips use an inverse grayscale surface and text pairing, while an
active operation chip uses that operation family's
exact main swatch at rest with contrast-selected grayscale text. Delete is the
deliberate exception only at rest: its inactive label is exact red-main in both
ordinary themes, while its active red-main surface uses the same contrast-safe
neutral label policy as other selected chips.
Active operation-chip hover/press cues retain the same main RGB at 90%/80%
strength, matching other colored clickable controls; they do not lift or scale.
Inactive Delete retains red-main text but otherwise uses the same distinct
grayscale hover and pressed backgrounds as every other inactive chip.
Plain pressed chips likewise
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

Unchecked checkboxes use a 1.2px neutral Fluent
`ControlStrongStrokeColorDefault` boundary (`#72000000` Light / `#8BFFFFFF`
Dark in WinUI ARGB notation, authored as CSS RGBA hex). Their selected fill and
boundary become semantic accent states while retaining the 16 px outer
geometry. Selected checkboxes use the pinned local Fluent
`checkmark_16_regular.svg` mask rather than a font glyph, centered as a roughly
12 px check with a small authored dilation; mixed state uses the pinned
`subtract_16_regular.svg` mask. Disabled unchecked boxes use the dedicated
theme stroke (`#00000037` Light, `#FFFFFF28` Dark, and `GrayText` in forced
colors), following the native
[CheckBox resources](https://github.com/microsoft/microsoft-ui-xaml/blob/main/controls/dev/CommonStyles/CheckBox_themeresources.xaml).
Textboxes use a separate subtle 2 px control
boundary and a stronger neutral bottom stroke at rest; focus changes only that
underline to the semantic accent fill. Mouse focus therefore does not gain a
keyboard ring, while `:focus-visible` composes the accented underline with the
shared dual focus stroke.

Switches retain a 40x20 logical pixel footprint and use the same strong neutral
off-state stroke, including while disabled. The checked boundary is transparent.
Following [WinUI's switch template](https://github.com/microsoft/microsoft-ui-xaml/blob/main/controls/dev/CommonStyles/ToggleSwitch_themeresources.xaml),
the centered thumb is 12x12 at rest/disabled, 14x14 on hover and 17x14 while
pressed, elongating inward. Off-state switches and checkboxes use the native
translucent alternate-control fill roles; checked states retain the accent
base and its native hover/press opacity ladder. Disabled off/on fills and thumb colors follow native disabled
resource roles; keeping the off-state stroke unchanged is the requested local
exception. Keyboard focus and forced-color system strokes remain independent.

The clear-button modifier is transparent at rest and when disabled, uses the
task-card hover/press fills when enabled and keeps keyboard focus feedback.
Its Clear/dismiss specimen is included in the component gallery's full state
matrix and the same modifier styles the two path Clear buttons.

Elevated surfaces use a dedicated flyout boundary rather than the accessible
control-stroke role: black 6% in Light and black 20% in Dark, with opaque
Light/Dark stroke fallbacks. Dialogs and menus keep their ordinary black
elevation shadows on ordinary SDR displays. In Dark, dialogs other than a
keyboard-focused one, menus and combobox popups drop those CSS shadows while
the window's display composes in Windows Advanced Color: through
`(dynamic-range: high)` for HDR, and through the native `data-advanced-color`
flag for SDR WCG, which CSS media queries report as plain sRGB. The subtle
flyout boundary remains. This mitigates, and does not fix, the Windows
composition defect in [BUGS.md](BUGS.md#desktop-material-composition).

That defect's evidence method: GDI/BitBlt screenshots show DWM's legacy 8-bit
composition, which is exact and cannot see the halo. The GUI-D8–D10 diagnostics
capture the scRGB desktop through Desktop Duplication FP16 (ffmpeg `ddagrab`),
fit flat straight-alpha patches against sRGB-space, linear and linearized-
premultiplied blends, and repeat the layout from a raw Win32 window writing exact
premultiplied pixels. That raw window and a black-backdrop gray/alpha grid
reproduce the error without WebView2 or Mica. `--force-color-profile=scrgb-linear`
makes DWM's blend physically linear and removes the ring, but lightens every
translucent token and renders HDR grayish, so it is not adopted. Light theme,
cards and fills are unchanged; their small WCG deviation is accepted. The
gallery's historical normal/opaque flyout labels do not isolate popup alpha
(both fills are opaque); its shadowless control remains useful.

Three file-list surface modules share presentation components.
`file_row.js` owns the shared row skeleton; `plan.js` exports only
`renderPlanRow(element, rowView)` and `integrity.js` exports
`renderIntegrityRow(element, rowView)` plus its existing `createIntegrityCell`
helper, reused by Inventory without replacing tree-owned row elements.
Inputs are page-local presentation
views, not bridge envelopes or compatibility contracts. Callers supply native
checkbox state, mixed state and accessible labels; depth, folder and expanded
state; display-ready basename and size text; list-specific status text; and
notes. `renderPlanRow` accepts an empty `intentKey` for a plain row, exact operation
and presentation keys `copy`, `mkdir`, `move`, `rename`, `recase`, `update`, `move_update`, `trash`,
`delete`, and `noop`, or exact exception keys `error`, `unsupported`, and
`blocked`. A projected execution row may instead supply exact lifecycle key
`executing` or `completed`. An `executing` row additionally requires a finite,
already-projected `progressPercent` from 0 through 100 and renders a 4 logical
px mini progress bar across the cell's content width, preserving the standard
8 px inset on both sides; supplied text such as “Copying” becomes its
accessible label. `completed` remains visible semantic text.
`renderIntegrityRow` accepts only `verified`,
`baselined`,
`unverified`, `modified`, `reappeared`, `unsupported`, `canceled`, `missing`,
`mismatched`, and `error`, or exact projected lifecycle key `verifying` or
`completed`; `verifying` follows the same explicit percentage/bar contract and
uses text such as “Verifying” as its accessible label. Each non-progress state
wraps the supplied label in the
channel-scoped semantic-label component. The already-projected key selects its
fixed component role; there is no form field and JavaScript does not derive a
domain result, hue, urgency, transport-counter ratio, or row identity. The
renderers also do not aggregate sizes,
truncate hashes, split paths, reconstruct hierarchy, or dispatch anything. All
text still passes through `render.js`. Production Plan consumes its row renderer;
Inventory consumes the integrity state-cell helper while retaining its own
tree identities, disclosure listeners and navigation. The complete integrity
row renderer remains a gallery specimen.

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
integrity cells use the channel-specific semantic text, 18 logical px filled
form, or active 4 logical px padded-content progress form defined above, while
JavaScript consumes only the exact already-projected key and percentage. Zebra backgrounds belong only to
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

The component gallery owns the complete static row fixtures; production consumers
reuse the presentation components described above. Its static
sync array covers one plain row, every operation once, all three exception
states, and a
partially selected expanded `photos` folder with two indented basename-only
children, plus explicit Copying progress and Completed text rows. A second static
array covers every integrity state, Verifying progress and Completed text rows,
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

The gallery keeps the rail, Plan review controls, status card, and row fixtures
visually and semantically parallel with production; its gallery-only callbacks
perform no domain-backend writes and its plan data remains presentation-owned.
Persistent production Plan panels show preflight, commitment and other refusal
guidance, expandable prior-location contents with a destination-reveal preview,
and interactive Pause/Resume plus two-click Cancel. Their callbacks only update
gallery presentation values. Installed checks retain the refusal disclosures,
move navigation and selection observations, control labels/tones/glyphs, and
Cancel's five-second expiry alongside the existing gallery matrix.
The same gallery
gives every lifecycle case its own task-card/status specimen
and separately exercises active, resumed, paused, and canceled progress.
Lifecycle cases do not become file rows. All fixtures pass exact display-ready
presentation values directly to production components/renderers; they do not
derive planner, dispatcher, or verifier meaning.

The icon foundation includes the selected Regular glyph vocabulary and the
explicit Filled Stop alias used only for armed execution cancellation, vendored
locally from `@fluentui/svg-icons@1.1.334` with exact package/file URLs,
per-file SHA-256 hashes, and license. A frozen
`icons.js` registry maps visual glyph names to fixed component classes; the
classes use fixed local CSS masks painted with `currentColor`. `tokens.css`
owns exact 16/20/24 px `sm`/`md`/`lg` icon sizes and `components.css` owns
alignment and states.
Each size selects native artwork rather than scaling a single universal asset.
The authored catalog and generated receipt record the current coverage. Where the pinned
upstream package has no native size, the fixed mapping scales 20 px artwork:
Arrow Sync Checkmark at 16, Database Arrow Up at 24, Folder Holder at 16/24,
and Timeline at 16. These are explicit exceptions, not runtime asset discovery.
20 px is the default control glyph; 16 px supports compact text/controls, and
24 px is reserved for deliberately larger controls. Glyph size does not define
the button's hit target.
There is no remote load, icon font, runtime registration, inline/generated SVG,
or data-derived class/asset path. Icons remain decorative beside visible text;
icon-only controls require their own accessible name.

#### Maintaining the icon vocabulary

See [TOOLS.md](TOOLS.md#icon-maintenance) for the command syntax and options.

Edit `tools/icons.json` to add or remove glyphs and declare missing-size
fallbacks. Then run `.\.venv\Scripts\python.exe tools/icons.py sync`.
The command authenticates the pinned npm archive and updates
the native SVGs, SOURCE receipt, fixed JavaScript registry and CSS mappings.
Do not edit those generated regions or per-file receipts manually. Native
16/20/24 px artwork is selected automatically; missing sizes require an explicit
fallback, and a fallback becomes an error when native artwork is available.

Run `.\.venv\Scripts\python.exe tools/icons.py check` to verify generated files
without writing. Both commands accept `--archive path/to/svg-icons.tgz` for
offline use; otherwise they download the pinned official archive. The authentic
archive check proves upstream correspondence; receipt consistency tests alone
do not. Independent tests cover safety, fallbacks, drift, packaging and rendering
without a second hand-maintained glyph or hash list.

For an upstream update, review the catalog's version, archive integrity, commit
and license hash together. The npm archive omits the license file: retain or
deliberately update the reviewed local `LICENSE.txt`; the tool validates its
hash and refuses a mismatch. Review the generated diff and run the icon/tool
tests and installed gallery gate. The catalog and maintenance tool are not
packaged or loaded by the app. Registration never authorizes placement.

#### Icon placement and meaning

The governing rule is that icons help users differentiate. Their availability
in the registry is not a reason to display them. Placement, presentation and
density are stronger constraints than the example actions or glyph mappings
below. Shared text-and-icon surfaces, including lists and menus,
remain text-first. Only frequent actions (such as New, Open and Save) or actions
requiring immediate attention (such as deletion) receive supplementary glyphs.
Do not decorate every row or assign an icon merely to fill a column. Align text
consistently when some entries have icons and others do not.

Familiar, unambiguous controls may use only an icon: New, Save, Search, Settings,
and a contextually clear Close/Clear are examples, not an exhaustive eligibility
list. Other actions may qualify when their meaning is clear in context. The
button owns an explicit accessible action name and a tooltip available on hover
and keyboard focus;
the glyph remains decorative. An ambiguous action retains visible text. In
particular, dismissing a panel, clearing an input, and canceling running work
must remain distinguishable through context and naming even when their glyphs
are related. Registration does not convert current text buttons automatically.

Operation and status badges already carry their semantic cues; do not add a
second status icon beside a badge for the same information. A standalone warning
or error may use an attention icon where no badge already expresses it. Glyph
shape is not operation authority: creation variants, folder variants, play/sync,
and database variants require an explicit surface meaning before placement.
Use one consistent glyph for each action within a context; do not use similar
variants as interchangeable decoration or to distinguish unrelated actions.

The initial action vocabulary below is a guideline, not a fixed mapping or
whitelist. A surface may use a different glyph or another well-understood
icon-only action when that improves recognition in context. Such exceptions
must preserve the stronger rules: selective emphasis, restrained density,
clear action meaning and accessibility, and no redundant badge/icon cues.
The examples do not change current controls or make every occurrence eligible
for an icon.

| Action | Glyph | Meaning boundary |
| --- | --- | --- |
| New item/task | `add` | Creation in the current context; retain text when the kind is unclear. |
| Browse/open folder | `folder-open` | Folder access or selection, not starting a sync. |
| Save | `save` | Persist an editable choice; not execute a reviewed plan. |
| Close/clear | `dismiss` | Local dismissal or clearing, with an explicit contextual name. |
| Settings | `settings` | Open settings. |
| Search | `search` | Find/filter in the named scope. |
| Delete | `delete` | An actual removal action; retain consequence wording where needed. |

Task cancellation is a lifecycle action, not removal or mere dismissal. Keep
its meaning distinct from `delete` and from closing a panel. The remaining
registered glyphs are available vocabulary; assign their surface semantics when
the corresponding interaction is designed, rather than inventing 47 actions.

Native appearance observes Windows light/dark/high-contrast state and live
`UISettings` `Accent`, `AccentLight1`, `AccentLight2`, and `AccentDark1` values.
The raw ramp stays native-side. The revisioned `namisync.appearance.v3`
envelope publishes only `accentFill`, its 90% hover and 80% pressed values, one
contrast-selected foreground and the Boolean `advancedColor` of the window's
current display to packaged `appearance.js` through UI-thread
`document_channel.py`; only its exact schema and fixed CSSOM/dataset sinks are
valid. `advancedColor` is read through DisplayConfig (24H2 active Advanced
Color, else the original enabled bit) and refreshed on display-setting changes,
monitor changes while moving and window activation. That refresh republishes
only a changed value and never reapplies material; a read failure keeps the
prior value.
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
disabled and does not alter operational readiness. Within one displayed generation
it serializes replacements,
reconciles only server-accepted state, and never mutates theme CSS
optimistically. A delayed replacement keeps its original request and shows
qualified feedback. Failure or explicit Refresh reads the current canonical
section and permits a new revision-bound choice. Refresh does not claim the old
replacement settled; generations prevent its late reply from restoring an older
display. No original-response observation or sticky outcome fence is retained.
Document replacement follows the host's close/reopen contract. Save failure remains a sanitized log event
in the active cosmetic contract;
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

The service currently provides this pre-reslice command surface:

```python
start_plan(source, target, *, deletion_policy=None, command_id=None,
           observation_sink=None) -> PlanSession
start_execution(request_id, *, verify_after_execute=False) -> ExecutionSession
start_inventory(...), start_baseline(...), start_verify(...), start_rebaseline(...)
read_semantic_settings() -> SemanticSettingsView
commit_semantic_settings(patch) -> SemanticSettingsView
```

`SessionObserver.observe(session_id, sink)` supplies primitive current-state
and event/record views. Plan start's optional sink is currently attached
transactionally before the session can run. The accepted target requires that
same attach-before-schedulability path for every desktop-created execution,
inventory, integrity, and manual-verification session. `BRIDGE.md`
exclusively defines the recovery cursor and command-receipt identity exposed
across the wire. The desktop owns the bounded presentation queue fed by that
sink; it does not expose raw dispatcher streams to JavaScript. It must
unsubscribe the exact terminal session on release or task close and close every
remaining observation before service shutdown.

The desktop submits complete Setup and freezes the native canonical result;
defaults only prepopulate the page and Setup never writes global settings.
Session starts create or attach to a process-live task, and bounded readback
reconstructs the rail/pane after navigation. Exact Setup, task authority, and
concurrent start/close/release behavior remain bridge authority.

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
echoes it through `readiness_echo` and records `Ready` only after a truthful
acknowledgement. The ordinary Ready label is hidden; other host status messages
remain visible. Repeated raw API notifications do not restart shell startup.
Ordinary commands
remain unavailable until native security/load, shell acknowledgement, safe
surface settlement, and the neutral post/echo roundtrip converge. The nonce is
liveness evidence only, never authorization, and is neither logged nor
persisted. A fixed five-second product deadline applies to the initial document.
During initial startup, missing acknowledgement, unsafe surface, or
failed neutral publication enters the direct fail-closed startup-refusal path.
Appearance publication continues independently and may degrade. Reload is not
a supported user action. A genuine replacement document permanently loses
command and appearance authority, including during initial startup. Host-owned
guidance tells the user to close and reopen NamiSync, review the folders and make
a fresh plan. Admitted work retains its existing owners and settles normally;
reload does not automatically cancel work, release a task, or close the service.
The normal X action still performs bounded, retryable shutdown. Stale timers,
acknowledgements and queued posts cannot reopen authority. Canceled navigation,
blocked popups and same-document fragment history leave the current shell usable.

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
drains and capacity-blocked sinks, waits for admitted native call workers to
finish their return path and exit, unsubscribes task observations, then calls the
service. A complete result permits one recursive-safe
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

Current location commands bind one explicit root or retained location id before
admission. `LocationResolutionError` already carries the five visible states
(`resolved`, `offline`, `ambiguous`, `root_missing`, `root_unavailable`), exact
candidate mounts, and corrective detail. The shared workflow-owned location
candidate service and bounded remembered-location readback are implemented;
typed, picker and remembered Setup inputs use that admission route. The UI must
request a user-selected current mount for ambiguity rather than inferring one
from a mapping or prior task. Its process-local slot is purpose-bound, expires,
and is freshly re-admitted at every real start; it is not lasting root
authority.

Semantic settings and UI state are deliberately separate. Existing service/CLI
callers may read and partially commit semantic settings. Desktop
Setup reads them only as initial values and freezes per-task overrides without
writing the file. The ratified `ui_state.py` replacement owns a strict,
section-versioned cosmetic document; schema v1 contains only the appearance
override. Recents are not a future cosmetic section: they derive from ledger
runs and current workflow probing. Geometry, columns, treegrid
expansion/grouping state, and filter chips remain deferred typed sections.
H2 sorting is process-live view state, not a persistence section; durable sort
preferences are excluded from M1. UI
state must not become another semantic-settings, task, or session store.

## Bridge and renderer security

The host exposes one function-table `dispatch` entry, and only packaged
`bridge.js` references `window.pywebview`. `BRIDGE.md` exclusively defines
the complete envelope bound, immutable command mapping, opaque identities,
exact errors, deadlines and retry classes, revision rules, drain recovery,
sequence/`Gap`/terminal semantics, and terminal-session release versus explicit
task close. This document requires those mechanisms to produce actionable,
path-sanitized UI feedback; it does not duplicate their wire contract.

NamiSync-owned code never constructs JavaScript or calls `evaluate_js`,
`run_js`, or `Window.state` as an application-data channel. Pinned pywebview
6.2.1 internally constructs JavaScript to return exposed-function results, so
its serializer/escaper and the real-browser hostile-name round trip remain part
of the security boundary. The host retains each admitted call's handler position
until that exact worker exits; a browser timeout or completed domain handler
does not release native-return custody. It also discards the pinned runtime's
unused synchronous callback-registry entries without changing the return
channel. [INTERFACES.md](INTERFACES.md) owns those compatibility mechanisms and
their remaining containment boundary. The exact pythonnet 3.1.0 pin is equally
part of that boundary because native delegate subscription, WinForms thread
affinity, and `CoreWebView2` access pass through it. Required ordinary Node
probes are unmarked and non-skippable; probes marked `supplemental_node` may
skip. Both resolve Node.js from `NAMISYNC_TEST_NODE` before `PATH`. Required
bridge probes cover original start-plan outcome observation without mutation
replay and single-attempt interactive wrappers. The required drain-manager Progress validator/replay gate
proves atomic rejection before cursor or reliable-sibling delivery. Installed
real-WebView2 witnesses cover native custody and renderer behavior;
[TESTS.md](TESTS.md) owns the ordinary gate requirements.

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
document replacement makes its response undeliverable. That state is
uncertain delivery, not uncertain commit; `BRIDGE.md` owns the corresponding
retry and recovery rules. The packaged static-asset server is not an API or
event channel.

Each native response carries a private transport token around the unchanged
bridge envelope. JavaScript validates the wrapper, clones the response, and
then acknowledges that token; provider mutation during acknowledgment cannot
change the delivered clone. A late response that loses a timeout race still
performs the same clone-and-receipt cleanup. Genuine replacement retires host
response custody and permanently revokes page admission. Older workers retain
their execution ownership until exit, without delivering results to a successor
page or reopening it.

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

### Setup and location flow

Setup labels its modes Sync and Integrity before folder admission; the latter
retains the existing standalone inventory behavior. The selected mode
sets the picker purpose; changing it invalidates prior folder authority. Inventory
uses one root and shows that exact frozen root after admission. Sync Setup exposes
trash/additive deletion, trash-on-update, filters, creation-time and ACL
preservation, source-casing propagation, and linked verification. Mirror has no
control. ADS is visibly unavailable and frozen off; the page never implies a
disabled checked option will be honored. Wire encoding is
owned by [BRIDGE.md](BRIDGE.md).

Setup and Recent pairs occupy separate cards. Setup starts at the work area's
top without a repeated task-title heading; the region's accessible name retains
the selected task identity. The task type uses the gallery's
segmented radio control, with arrow-key selection. Each path row places its
Source/Target label in a compact fixed-width track on the left, an editable path and recent-folder caret in one
standard textbox, with its compact caret button inset on all sides and an accessible
folder-open Browse button outside on the right. The
recent dropdown supports keyboard navigation, selection and Escape dismissal.
Pointer opening leaves its items neutral; keyboard navigation highlights the
focused item, and pointer movement hands highlighting back to hover. The path
dropdown and More options use centered 16px Fluent down/up chevrons from the
pinned local directional set.
Plan options have no enclosing outline or divider: Verify execution and Additive
sync switches sit together on the left, in that order, with 16px between them. Additive on maps to
`additive`; off maps to `trash`. More options
sits on the right of the same row and reveals preservation/update/casing switches
and exclude filters below. Each advanced caption follows its toggle directly;
Add filter sits beside the filter textbox; [PLANNER.md](PLANNER.md#exclude-filter-syntax-and-effect)
documents pattern syntax and effect. Disclosure changes presentation only,
never option values. Only the selected task type's Create action is visible.
Expanded options have extra spacing below the always-visible switches and 8px
between their rows. Buttons, textboxes and combobox triggers use translucent
disabled fills; other disabled surfaces retain their own component roles.
Forced-color and transparent-action overrides remain independent.
Empty and resolved paths omit routine hints; refusal and recovery messages remain
visible. Each path has compact inset Clear and recent-folder buttons; Clear
empties only that local field and invalidates its candidate without a Python
request, including when the textbox was focused. Browse is square. Idle and
disabled path-action buttons are transparent, with
task-card hover/press fills when enabled.
Textboxes retain their normal accented active underline without an extra outer
ring; forced colors retain a visible outline. Dropdown-option buttons have no
native resting border, while keyboard-focused options retain the common focus
indicator. More options, recent-pair Refresh and New task are also transparent
at rest and use task-card hover/press fills. The square Refresh uses Arrow Clockwise;
New task uses the larger Add Square Multiple glyph. Add pair precedes single
Create at the right. Single Create remains visible but disabled while the origin
has queued or unresolved batch work. Create batch appears below its table,
aligned right. Routine introductory guidance and
the visible Task type caption are omitted; the switch retains its accessible name.

A path row remains editable before its task starts. Editing an
accepted path immediately drops the page's slot reference and marks it
unresolved; the UI never silently reuses cached authority. Validation runs on
Enter, blur, completed paste, picker/remembered selection, or start—not each
keystroke. Refusal keeps the row editable and gives action-guiding typed
feedback. A selected file remains visible with `not-directory`; it is never
silently converted to its parent. Native code owns parsing, volume support, and
no-follow admission.

When a picked folder has multiple current mounted copies, Setup presents the
current mount choices. Choosing one continues that exact selection through a
short-lived opaque reference and fresh native identity checks. It cannot start
work until resolved, silently choose the first mount, or reuse a stale choice.

Setup shows recent sources, targets, and active pairs derived from ledger runs.
The recent-pair table reuses file-table surfaces with taller rows, two stacked
source/target paths in its first column and two aligned endpoint statuses in its
second. Corners, caption typography, header fill and alternating row surfaces
match the gallery plan table, with 3.5rem (56px by default) two-line rows,
1.75rem (28px) headers and 12px folder-column header/content insets. Both recent
and batch tables reserve five row slots, scrolling additional rows beneath a
fixed header. Empty slots are inert and excluded from accessibility. Both path
lines carry Source:/Target: labels in one shared-width track, so their truncated
path values start at the same horizontal position. The existing recent-activity query returns
at most five pairs; the shared table also supports larger batch populations.
Hover, press and keyboard
focus paint the whole enabled row, never individual cells. Long
paths truncate at the tail and retain the full text in a tooltip. Online uses a
green solid circle; Offline uses red; accompanying text stays neutral. Status
dots have a 1px downward optical adjustment beside their captions. A missing
root or absent volume makes that endpoint Offline. Other resolver refusals show
Unavailable, and incomplete/failed probes show Checking/Could not check. Only
pairs with both endpoints Online can be selected; all rows remain visible.
Refresh rechecks these
ephemeral observations. It does not start a task or retain folder authority.
Unresolved remembered locations remain visible with stable identity context,
never a stale drive hint. Multi-pair creation is a browser coordinator over
ordinary serial plan starts: Add pair captures a private options snapshot for
that row, each row has a stable command id and independent outcome, and completed rows are never
rolled back. Same-document navigation keeps the coordinator; document
replacement may stop only rows not yet submitted, while admitted tasks are
rediscovered from task enumeration.

One active batch gesture owns its selected rows, each with its own captured
options. Before admitting a queued pair, its snapshot is independently
canonicalized; a preparation refusal affects only that row. Removing the row
during preparation prevents its admission and submission. Delayed requests
retain their canonical options and original promise without preparing them again.
Additional batch
rows and new form starts wait for it to finish; each form also rejects overlapping
gestures on that same task. This is not a global queue for independent form
attempts already underway. Delayed or unavailable creation/start offers the
exact command's read-only Check and remains distinct from refusal; Check never
substitutes edited input or creates a replacement intent. Late completion is
adopted by the original issuing operation.

Core folder rows and the primary action appear first; More options reveals
the remaining task-local choices. Start admits unresolved nonempty rows automatically.
Stable form elements retain focus and drafts through rail, drain and navigation
updates; response revisions cannot restore an edited row's old choice. The
page retains one coordinator of at most 48 pairs. Each row belongs to its
originating task, and only an editable Sync Setup displays or starts those rows;
Inventory Setup hides the retained queue and remains startable while rows are
queued. Returning to Sync restores the same rows. Rows show
source and target paths, Verify and deletion settings, and creation status in a
conditional table under the composition actions. Queued entries display their
own captured settings, including independent filter lists and preservation
choices; later form edits cannot alter them. Preparation replaces only that
row's snapshot with canonical settings. Ordinary statuses are Ready, Created and Failed; in-flight and uncertain
requests retain truthful intermediate labels. Results remain visible until
Clear results removes settled receipts, without closing created tasks or
discarding unresolved requests. The table hides only when no entries remain.
The right-aligned Create batch footer sits 8px below the table. Create batch and
Clear results both remain visible whenever the table exists. They are disabled
when no eligible creation/Check or settled result is available, respectively;
creation also retains the existing editing, closure and in-flight guards.
Remove discards a queued row locally, including during preparation, or a row
still waiting for folder admission before task creation. The runner rechecks
membership before submission; late folder replies cannot revive a removed row.
Create/Start requests already submitted cannot be removed. Closing the origin
discards its queued rows and can detach pending folder admission, but its close
control remains unavailable during preparation or while Create/Start outcomes
need reconciliation. An adopted task also cannot close or submit a fresh
form while its batch start needs reconciliation; guidance names the origin.
The close control explains that reason. Original-outcome observation Check remains
available on the origin, and navigation never transfers the rows to a new task.
After a start, per-task readback shows the backend-frozen locations and options.
Plan again reads fresh availability for the reviewed identities, requests an
explicit current mount when ambiguous, and starts a separate plan with the
same frozen options and default selection. It copies no execution authority.
Terminal status alone never fabricates an empty or ready review.

The conditional table keeps batch composition near its actions; created tasks
remain the task rail's responsibility. The earlier popover, page-level tray and
dedicated Batch page alternatives remain unimplemented.

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
new positions share the in-flight scroll generation. A still-owned response
that overlaps the current viewport is accepted even after further scrolling,
preserves `scrollTop`, and chooses a visible active row using the current
viewport. Reconciliation then requests any remaining uncovered range. Keyboard
and external requests retain exact generations. Failed or blocked Inventory reads
settle their exact pending generation without retrying at rest; later changed
scrolling can retry without reloading the page. Scrolling
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
contract live in `PRESENTATION.md`; the installed shell/tree witness is SH-G-7 in
`INTERFACES.md`.

Plan and Inventory views use server-owned sibling sorting.
New views start in canonical path-key order; users can choose filename, size,
or mtime with explicit direction, and reset restores path-key order. The server
sorts complete sibling sets before windowing, with deterministic ties and
unavailable values last. Size/time use raw numeric facts, including only a
folder's own available mtime, never a time inferred from descendants. Sorting
preserves hierarchy, node ids, selection, collapse, and execution authority
and order. It advances coherent view revisions, indexes, and anchors; the
browser cannot sort only a page or reuse old numeric indexes. Ordinary
sort/reset starts at offset zero. **M1-8-R0 follow:** automatic following
is available only in canonical path-key order with no search or filters. It
starts enabled for a new eligible execution and follows execution/post-copy
verification's active operation or nearest visible collapsed ancestor. User
scrolling the target out of view, or changing sort/search/filter, disables it;
only explicit action resumes it, even after returning to an eligible view.
Programmatic scroll does not disable follow. Pause/phase changes preserve the
choice; task navigation cannot silently re-enable it. Follow never changes
selection or keyboard focus, and stale replies cannot undo manual navigation.
Repeated progress for the same target in the loaded window does not reposition
the viewport; explicit Go still jumps to it.

Float **Go to current operation** and **Turn on autoscroll** over the rows at
the viewport's lower-right, reusing existing floating-control conventions. Go
performs a one-time jump in the current view, without enabling follow or changing
sort/filters. If the target and ancestors are excluded, report that fact. Enable
appears only when follow is eligible and off. With no active target, controls
cannot jump to a fabricated row. Both actions support keyboard use; underlying
rows/actions must be scrollable clear of the overlay. A distance readout is not
required. PRESENTATION owns resolution; M1_PLAN owns finite R0 acceptance.

The Plan review renders its current bounded window in the compact file-row grid
with exact 24-CSS-pixel rows and matching leading/trailing spacer offsets; the
generic `tree.js` renderer keeps its separate 28-pixel contract. A Plan card
shows the switcher at left, frozen source/target paths in two middle rows and
Verify on/off and Trash/Additive in two lines aligned with the paths at right.
These fixed-width semantic fields reserve their icon and label slots: Verify on
uses accent `arrow-sync-checkmark`, Verify off uses muted `arrow-sync`, Trash
uses muted `delete`, and Additive uses accent `document-add`. Text remains visible;
the decorative icons use the pinned Microsoft Fluent assets, not substitute glyphs.
Plan paths and semantic labels use 12px caption text. The semantic field is
7rem wide, shifting its icon edge right to align optically with Plan again.
A Status card shows selected/byte/planning-issue facts and execution controls;
one table card owns search, the shared Filter menu and the grid, without a footer.
While no reviewed plan is available, execution and replan actions are not
actionable; a loading or unavailable panel cannot retain a previous task's
enabled controls. Reusing the Plan panel also restores viewport resize
observation so newly exposed rows reconcile without requiring a scroll gesture.
Status and table cards use a 16 px top inset. The status
progress bar is 8 px thick; the rail's progress remains 4 px. The Plan view switcher has
a 6 px outer radius. At default (1280×800) and larger window sizes the natural-height
Plan and Status cards leave the remaining work-panel height to the table card;
the table body scrolls rather than the page. Search is a narrower right-aligned
box with inset submit and Clear icons styled like Setup path-box controls.
Clear restores input focus and immediately clears the query. Plan and Inventory
share one ordinary-sized Filter button with regular Filter and chevron icons.
Its visible count includes zero and counts selected canonical categories only,
excluding All and search. It stays neutral at zero and uses the accent fill when
categories are active. The popup reuses the existing menu surface and follows
Microsoft's [checkbox menu guidance](https://fluent2.microsoft.design/components/web/react/core/menu/usage)
for multiple filter criteria. Every canonical category has a checkmark and its
authoritative count, including zero; All clears category settings. Inventory's
All has no counter and retains its acknowledged-item default visibility policy.
Stable items keep the popup open and focused through pending/settled updates;
pending guards refuse another gesture without introducing a query queue.
The popup has a bounded scrollable height within its owning work panel and
viewport and opens above when more room is available there. Resize or scrolling
outside the menu dismisses its old geometry; scrolling inside remains usable. Up/Down/Home/End navigate, Enter/Space toggle, and Escape closes
and returns trigger focus, including while pending. The pending trigger remains
focusable with aria-disabled and refuses opening. Outside pointer interaction,
focus leaving, window blur/hidden document, context replacement and retirement
close the popup and remove its document/window listeners. Panel reuse restores
normal interaction. The Sync/Integrity outer corner radius
includes its inset so it is concentric with the inner buttons. Status-card actions
align right alongside the large status title, with an arrow-reset Plan again
button before Execute. It stays icon-only when used to Check the original
Plan-again outcome; its accessible name and tooltip follow that current action
without replacing the icon.
Concise actionable warnings, errors and in-flight feedback share the second row
with the status digest; idle and successful messages take no space. Feedback
shares the digest's caption size and secondary foreground. At ordinary
widths both texts stay on one line, with full feedback available in its tooltip;
at narrow card widths both use a stacked, wrapping layout.
The progress track deliberately uses the ordinary button-rest translucent fill
instead of Microsoft's stronger ProgressBar stroke resource. It composites over
the card, without opacity on the whole control. Forced colors retain Canvas.
Dispatched planning and loading its completed review use indeterminate progress
in the shared task digest and loading status card; no scan percentage is invented.
Pre-admission folder checks and ready, unexecuted plans remain idle. Errors stop
planning animation, and execution retains its existing progress authority.
The production Plan grid orders Select, Name, Action, Checksum (empty), Size,
Modified and Notes; Checksum and Modified share their default width. The
gallery shares that column order. Dependency counts and `Risk: none` are omitted
from Notes; actual risks and diagnostics remain. Size, Modified and Notes use
the same tertiary text color (#616161 Light, #adadad Dark, CanvasText in forced
colors); task-rail paths share it. The synthetic Plan root is omitted from the table. The Select
header is the sole tri-state bulk control for all selectable operations
matching the active search/filter query, not merely the
loaded or expanded rows. Folder checkboxes target matching descendants;
changing views alone never changes selection. Its separate header and body share the Setup table's stable
gutter and thin-to-wide scrollbar styling, so the scrollbar does not overlay
the header. At the first visible loaded layout, production freezes the fitted
non-Name widths; subsequent table growth goes entirely to Name. Hidden or
disconnected rendering defers that snapshot, and panel reuse retains it.
Production columns use the gallery's constrained pointer/keyboard resizing,
with Notes yielding width. When Notes is already at its minimum, a positive
fixed-column resize stays clamped until a deliberate reduction creates Notes
space. Action's 6rem minimum is shared by its
default track and pointer/keyboard constraints. Name, Size and Modified headers cycle
ascending, descending, canonical path order with catalog chevrons; a different
header starts ascending. Sort buttons fill the padded header cell, with the
active chevron aligned right. Status and row
byte labels use binary units with two fixed decimals from 1 KiB upward and exact
integer bytes below it, while sort keys remain raw backend facts.
Filter labels and counters occupy separate spans with a dedicated gap, never
expanded word spacing. Menu counters align to the right edge. The Plan-again
icon button is square. Plan and task-tab Source/Target labels use equal-width
3.5em slots with a 2px gap so path starts align without excess spacing.
Task-tab details, paths and progress end 18px inside
the tab's right edge; title and close-button positioning remain unchanged.

Plan action/filter labels use sentence case and friendly names:
`noop` is **No change**, `mkdir` is **Create folder**,
`rename` is **Rename**, `move_update` is **Move + update**, `trash`
is **Move to trash**, and `delete` is **Delete**. Destructive confirmation and
the irreversible risk detail remain unchanged. Plan projection classifies recase
and pure same-parent moves as Rename; their row labels and Rename filter agree.
Cross-parent moves remain Move, while Move + update stays distinct even in place.
Item details and execution diagnostics retain the actual operation kind, including
Recase. The single Filter menu retains
all thirteen canonical Plan categories independently and their counters; the
former grouped shortcuts are replaced by those explicit checkbox choices.
The Notes policy is explicit and fail-visible:

| Input | Display policy |
| --- | --- |
| Operation reason `source_only`, `metadata_match`, `identity_rename`, `required_directory`, `empty_directory` | Hide only when risk is `none` and there is no blocker or selection exclusion; action/hierarchy already conveys the low-risk explanation. |
| Those same reasons on risky/blocked/excluded rows | Show the friendly explanation. |
| `metadata_changed`, `identity_rename_changed`, `target_only`, `directory_cleanup` | Show changed-file, removal or cleanup context. |
| Case, Unicode, type, policy and destination conflicts; unsupported and blocked reasons | Show friendly explanation. |
| Selection exclusions, including incomplete scan and deselection | Show; never apply the operation-reason hiding list to them. |
| Move peer / prior-location rows | Keep paired-move / previous-location context; expandable old contents attach at their deepest surviving scanned target ancestor. |
| Non-neutral risk, free-form notices, partial/overflow totals | Show unchanged. |
| Any unrecognized or future reason/notice | Show verbatim as inert text; hiding never follows a broad pattern. |

Known reason-code labels are translated only at rendering; backend facts,
selection and execution authority remain unchanged.

Prior groups start collapsed and show one clickable badge containing both the
count (`N items moved to`) and compact destination in the filename area, with
separate expand/collapse disclosure. Its 4 px corners and inner padding match
the compact action badges. The target parent is the destination even for a directory move.
The destination label is a basename with an ellipsis prefix when ancestors are
omitted, bounded to 255 UTF-16 units; its tooltip and accessible name use the
same compact label. Full filesystem destinations are available in the highlighted
group's item details. Use purple background/text:
light purple badge fill with dark purple text in Light, dark purple fill with light
purple text in Dark, and system colors in forced colors. Activation reveals the
canonical destination, expanding its ancestors and clearing only obstructing
search/filters. Root destinations jump to the first canonical moved item.
The pill and its contents stay outside execution selection and totals.
Canonical move rows append purple **moved from another folder** text after the
filename. Move + update uses **previous location available in details**, including
same-folder updates. Rename rows show **renamed from [previous name]** and have no
prior-location groups. The browser renders projection-supplied classification
and bounded prior basenames; it never hides rows or derives filter membership.
Long Rename annotations ellipsize and retain their prior basename in a tooltip.
They use at most half the Filename cell so long origins leave the filename readable.
If the destination's follow-up window no longer matches, retain the last coherent
review and offer **Refresh review** with an explanation. A coherent conflict
response aligns the viewport with the loaded offset before asking the user to
click the destination again; obsolete task/navigation responses remain silent.

Window display and notice labels are bounded to 300 UTF-16 units. A separate
read for the highlighted node supplies complete original-case relative paths,
its source/target origin, previous path, move destination and full notice without
filesystem access. Item details join paths to the reviewed source or target root
according to their supplied origin; previous paths and move destinations use the
target root. Execution operation, automatic verification and the five supplied
backup/mutation destination/prior/published/trash path fields also use that target
root. The global trash location is already absolute. Joining is display-only,
without filesystem probes or parsing diagnostic prose. Node, view, session, action, navigation and
Close guards reject obsolete replies. Returning to a retained Plan reads its
highlighted node again; retired paths never reappear from a cached detail.
Reads never fan out across visible rows.
Planned-detail loading or failure stays visible alongside execution-detail status.

Row highlighting is distinct from execution selection. Pointer and keyboard
gestures replace, toggle, extend, or add ranges in the complete server-owned
ordered view; the visible 256-row window merely paints returned highlight flags.
Checkboxes preserve a highlight and apply to its whole range when the checked
row is inside that range. Search/filter changes clear highlighting, while
scrolling, sorting and disclosure changes do not. The bridge carries compact
gesture endpoints and expected revisions rather than row or operation arrays.
The status tier says neutral **Plan ready** for every built, unexecuted plan.
This is not an execution-readiness claim: Execute still requires preflight and
a nonempty executable selection. Strictly empty plans have an explicit empty
message, distinct from a filtered-empty view.
Task tabs share the status digest, replacing the visible Task N title with the
current lifecycle state. They show a shorter detail (selected operation count and required
binary bytes), source/target paths or `-`, and an aggregate progress track.
The title is semibold. Detail and path text uses compact caption line spacing;
those rows and progress extend below the upper-right close button, ending at
an 18px right inset to align optically with its icon. Progress has matching space above and below. Live task
selection markers are 2rem, Settings is 1rem; the production-rail gallery shares them.
Internal task identity is unchanged. Ready-plan progress remains inert; planning
uses the indeterminate state described above. Execution progress
comes only from the accepted progress reducer, never from selected rows.
Production commands, validators, state, raw row facts, and window/anchor
behavior remain active. Status/progress sorting, global
flat sorting, and durable preferences are excluded from M1. Exact rules and
acceptance live in [Bridge DR-BR-15](PRESENTATION.md#search-filters-sorting-and-follow);
the existing shell/tree witness does not close this new work. The active M1
delivery plan owns sequencing.

Execute opens a Fluent smoke confirmation dialog whenever the workflow reports
selected destructive operations. The dialog states the replacement/removal
consequence and selected count, with Cancel and Confirm and execute actions.
Its paragraphs use a 16 px separation and the action row uses a 24 px separation.
There is no persistent consent checkbox. Non-destructive selections submit
immediately. Request/revision binding and admission recovery are owned by
[BRIDGE](BRIDGE.md); the dialog grants no separate lasting authority.

The native HTML dialog uses `showModal()` and existing `.nami-dialog` material
and motion. The app and theme-popup roots remain inert through the exit
transition: pointer, wheel, keyboard and focus cannot interact with the page
behind the smoke. Backdrop gestures are consumed; the page scroll lock retains
and restores the prior inline overflow value and priority, while the dialog can
scroll within a short viewport. Initial focus is Cancel; Tab
stays within the dialog, Escape cancels, and closing restores the invoking
control's focus when it remains available. Confirm is single-shot and begins
admission immediately. Cancel before submission leaves the review editable;
delayed submission instead offers read-only Check and disables selection and
Close until admission truth is recovered. Shared reduced-motion and
forced-color rules apply.

Closing has no minimum observable duration. The installed task-shell correctness
scenario arms a finite tests-only animation before trusted confirmation so the
native driver can test background input during closing, then completes that
animation after recording the witness. This barrier does not alter product code
or measure latency. Transient closing attributes must not be treated as durable
readiness; the production zero-motion path may finish after a single frame.

Plan-again availability follows the same app-owned eligibility rule as dispatch,
including loaded Setup readiness, pending attempts and batch/close blockers.
The control remains disabled while those prerequisites are unresolved; an
unsubmitted gesture never displays a completed-request message.
Plan-review layout rules honor HTML hidden state, including the loading toolbar,
status actions and inactive execution controls. An unbound review exposes no
actionable controls.
If a Plan load fails, the task card directs the user to select it to retry.
Selecting that eligible task retries Plan loading as well as Setup; repeated
selection shares an in-flight load and an already current review remains cached.
Successful recovery clears the error and restores the exact reviewed task.

The component gallery includes a Preview destructive confirmation button. It
opens this same production dialog with a sample count of 13; Cancel and Confirm
only dismiss the preview and report that no files changed. It stays closed at
rest, so the gallery remains available for inspecting other components. The
installed light/dark/forced-color/reduced-motion gallery witness exercises both
dismissals, background inertness, native wheel blocking and focus restoration alongside the existing
material matrix.

A scroll page settles the viewport snapshot that requested it. If that snapshot
is unchanged and the page is narrower than the viewport, the renderer waits for
a later viewport change rather than automatically alternating missing edges.
A changed viewport is reconciled after the response, including a response now
outside the viewport;
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

The window bounds the shell to its viewport. Task items scroll independently
between the rail header and the full-width Settings button at the bottom;
work content has its own scrolling area. The compact New task icon is centered
beside the Tasks heading. Live task text has a 20 px leading inset, while the
Settings control keeps its own 16 px inset. Task text has additional left
padding.

Settings is an ordinary work-area page, not a modal. Its Settings card contains
the existing Theme selector; About initially contains `0.1.0 "Gertrud"`.
About/license/third-party links remain to be populated with their actual content.
Opening Settings preserves task identities, drafts, activity and closure state.
Background task updates do not navigate away from Settings. Clicking a task
returns to it; an unraced successful New task action opens its new task.
Global semantic-settings mutation remains deferred.

The rail itself is a Mica seam: it has no card background, border, or shadow.
A resting unselected task card is fully transparent. Hover and selected/current
rest use the same neutral selection overlay; press temporarily weakens it. The
live rail's selected navigation button exposes `aria-current="page"`; the
gallery's `aria-current="true"` and `aria-selected="true"` variants retain the
same component treatment. Live selected/current cards retain a 3 px wide, 2 rem tall
(32 CSS px at the default root size) sampled-accent marker,
so hover never erases selection. Task cards have no painted border or elevation
in ordinary themes. Each live card spans the rail column with a dismiss icon
inset at the right; selection and dismissal remain sibling buttons, never nested
interactive controls. Dismiss is transparent at rest and uses the task-card
hover/press fills, with contextual accessible Close/Retry naming and the existing
pending-close availability rules. In forced colors,
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

The accepted rail presents process-live adapter tasks, not dispatcher history.
A task may outlive its serial sessions but is not durable across application
restart. Task enumeration/detail observes the rail and selected pane during
same-document navigation. Cards show truthful activity, scope, phase, progress,
and terminal headline; subject-only work never fabricates a source-to-target
label. Exact task/result revisions and named-generation rules are bridge
authority.

M1-4 activates task page creation, selection/navigation, rail interactions, and
explicit closure. The rail is newest-first, keeps stable process-local labels
and card elements across re-observation of published blank,
active-session, and terminal/released tasks within the current document. Page
bodies now show editable or frozen Setup; review, execution and inventory
content await their owning checkpoints. Task identity, activity/terminal state,
and pending/failed close remain truthful and observable; this slice does not
prebuild those later content projections. Stale create, close, list, and drain
responses cannot replace current-generation state or steal a later selection.

An accepted pause renders **Pausing…** until custody actually reaches
**Paused**; repeat pause/resume is disabled during the drain and cancellation
remains available. Terminal presentation releases only that exact session while
review artifacts remain.

Execution uses one stable Pause/Resume button with visible action text and
Regular Pause/Play artwork. Running Pause is neutral; authoritative Paused
switches it to accented Resume. Waiting and pausing keep the button unavailable
while existing lifecycle feedback remains truthful. Cancel is neutral with
Regular Stop artwork. Its first click arms an accent fill with Filled Stop for
five seconds; a second click within that monotonic deadline submits cancellation.
Arming does not submit a command. Ordinary renders never extend the deadline;
expiry, task/session replacement, unavailable controls, leaving the panel and
submission disarm it. The expiry timer changes only the Cancel button.

Execution-control attempts belong to the task and session across review refreshes.
A replacement review retains pending and relevant accepted/refused/uncertain
feedback, without allowing a duplicate request. New authoritative control state,
terminal or replacement session wins over obsolete replies; ordinary byte-progress
ticks do not erase a refusal. If task updates stop, disable Pause/Resume/Cancel
and expose one task-card **Retry updates** action, including before review loads
or while task Close is pending. Keep last-known execution truth: lost updates
are not proof that work stopped. Retry restores observation of the same session;
it does not restart work. Controls remain unavailable until recovery delivery
is validated. Terminal display/release failures reuse their distinct retries.
An unresolved Close keeps its original-result Check and fence ahead of observation recovery;
a pending Close can finish after recovered terminal delivery.

Closing a live task renders
**Closing…**, immediately requests best-effort cooperative cancellation, and
stays visible until cancellation settlement and resource release permit close.
An incomplete close remains actionable through close/shutdown recovery; this
does not retry the domain operation. There is no force-close
path. Close and publication-fault observations invalidate rail, panel, and
affected tree request generations before clearing cached data, so detached old
responses are inert before payload read.

Mutation response delay is availability feedback, not an operation deadline.
After five seconds, qualify the wait for the original result; finite failed
observation qualifies communication as **Outcome unavailable** and offers a
read-only Check, with normal application close/reopen and current-state review
as a fallback if communication remains unavailable. A matching unreadable final
response is noncheckable fixed-unknown, with an `invalid_result` diagnostic and
close/reopen guidance. Native cannot repair its retained bytes; acknowledge them
for cleanup while preserving the intent fence. A healthy pending response remains pending when the
bounded round ends. If direct delivery already failed, explicitly ask the user
to Check rather than claiming to await an automatic response. Still-live delivery
can update its owner through the original promise, which remains the sole adopter.
For the eleven protected commands in
BRIDGE, keep the original intent and relevant task/session/revision fences until
its outcome is resolved. A captured final response that cannot establish the effect
keeps the intent fence with close/reopen and fresh-review guidance, without a
Retry button that cannot recover anything. An unresolved Close blocks new starts
and replacement tasks. Folder choices remain local: editing, clearing, mount or
recent-choice replacement invalidates older admission replies; Start/batch uses
only the latest resolved choice. One live native picker remains separately owned.
View, highlight and theme use authoritative current-state Refresh, with revisions
and generations preventing stale adoption. Current state does not prove an old
effect settled. These five commands do not keep original-outcome fences, and
their uncertainty alone does not block unrelated Close or controls.
Check cannot submit another mutation. Late adoption repeats no confirmation
and does not change current navigation.
Successful pending Close and live session observation retain their separate
settlement paths. D4 highlight/focus remains independent of execution selection.
After a captured noncheckable review response, a user may still Cancel the same
active execution if the unknown action was not Cancel. Its separate control
attempt retains its own outcome and observation Check while the original review
warning remains. This exception does not reopen in-flight protected review work,
or repeat an unknown Cancel. After a fixed review/control error, explicit Close
is available when the retained review identifies the exact native task/session
pair; native cancellation and settlement own that cleanup. It does not resolve
the earlier unknown outcome. Unknown starts, execution admission, release and
Close remain fenced. Disabled Close gives the same action-guiding reason
enforced by its handler.
An uncertain execution admission also keeps its retained execution handle's
guidance visible in Plan review, including after the review is reconstructed.

Task closure never purges trash. User-invoked session cleanup and terminal
execution/verification retry actions, including **Verify remaining**, are
deferred to M2. Existing automatic owned-temp recovery, bounded operation/read
retries, pause/resume, transport replay, and shutdown recovery remain unchanged.
A forced process exit cannot wait for settlement and provides no durable live
task or resume promise; later work starts from fresh observation and review.

Normally completed linked execution/verification retains read-only file lists,
item status, and each phase's aggregate status. Normal execution-only completion
may offer the first manual post-copy verification when eligible. Non-stopping
degradation retains that same review experience with visible issue axes, without
item retries. Canceled or otherwise abnormally terminated sessions retain their
terminal truth for review and close, without resume, retry, or session cleanup.
Paused live sessions retain their existing controls.

M1 execution review is active in the existing Plan pane. The execution header
and every row come from one coherent bounded Plan window; live update bursts
coalesce into one selected-window read at a time, while a hidden task keeps only
a dirty marker until it is selected. The browser never builds a complete result
map. Every read is pinned to the task, session, reviewed request, view action and
execution revision; Settings navigation, task navigation, document retirement, Close and
replacement generations make older replies inert. Terminal release explicitly reopens the retained Plan
truth. The task rail may use the exact terminal session result immediately so a
known failure or degradation cannot remain labelled as green completion while
retained capacity counts are still being captured.

Rows present the operation result, automatic linked verification, recording
state and current stored evidence as independent axes. Structural operation
containers may carry projected rollups without pretending to be a detail
subject. Missing means unknown, and a successful zero-byte operation is still
reported as ran. One explicit row action may load full operation detail; the
pane retains only that one response and retires it when its operation identity
or execution revision changes. Hostile detail remains inert text. Producer and
presentation omission counts, recording issues, terminal filesystem/integrity/
audit axes, phases, errors and observed Gap history remain visible after
settlement. Capacity guidance uses yellow in the aggregate run header and task
rail only when the retained counts, terminal axes and active-result identity
prove that classification. Independently, an operation row that itself failed
for the exact disk-capacity reason uses the yellow capacity lifecycle. The row
still says Failed, keeps the capacity reason, and preserves independent
verification, recording and stored-evidence facts. It does not inherit or
reinterpret the aggregate result. Unknown, stale, generic or mixed aggregate
failure evidence remains red and never masks an independent operation,
integrity, recording or audit failure; each row continues to show its own facts.
The accepted M1-8 closure interaction uses one detailed status line on the
Plan/execution page: selected a of b, required space and planning-issue count
before execution; phase, item progress, percent, throughput and ETA during it;
key terminal outcomes afterward. Execution and terminal information replace
stale plan facts. Unknown totals/rates/ETA remain unavailable rather than being
invented; presentation estimates do not become durable execution facts.

The status title and primary action share one row at the native minimum width;
active controls may occupy the next row. The detailed status line places its
Details disclosure at the right. Progress follows the status line. The shared
card is used by Plan, live and
terminal execution; the same presentation remains available to a future Verify
view without implementing that view here. Details starts collapsed. Its optional
right column spans Setup, status and table, capped at 20rem and 40% of the
available width. Hiding it returns that width to all three central cards.
Two stacked cards scroll independently: global plan/execution diagnostics,
the supplied detailed status and action messages, nonzero canonical plan-action
counts, issues, omissions and trash location above the highlighted item's facts.
The item card receives three parts of the available card height to the global
card's two, preserving independent scrolling.
Action recovery and Gap guidance also remain visible in the central status card
while Details is hidden. This
uses the supplemental, simultaneous-interaction pattern in Microsoft's
[inline drawer guidance](https://fluent2.microsoft.design/components/web/react/core/drawer/usage).
The task rail keeps its 18rem cap and narrows in smaller windows while retaining
tab, path-label and close-control alignment. The
item pane always exists while expanded and prompts for a highlight when none is
active. The server-owned highlight focus, including the last focus in a range,
chooses the item; a row click does not force a deliberately collapsed pane open.
Checkbox selection remains independent. Planned facts include supplied size,
Modified time, positive dependency count and applicable selection/folder totals;
they never infer a missing planned path. Planned facts appear before execution;
later the one retained operation response adds distinct operation, automatic
verification and stored-evidence truth. Ordinary detail omits the operation ID
and has no sticky shaded title or per-row Details/Close buttons. The whole area
collapses while retaining the table view, selection, highlight and scroll, and
focus returns to the disclosure when hidden content held it. No separate card
or reserved blank diagnostic row sits below the table. Headline failures,
independent degraded outcomes and issue/Gap indication remain visible when
folded. Trash is location-only, with no existence/count/purge claim.
Terminal detail includes a concise outcome, local completion time when known,
and nonnegative elapsed wall time from the matching session's end and start;
null or invalid timing is omitted, and overlapping error categories are never
summed into an invented total.
UI dates use local `yyyy-MM-DD HH:mm` consistently for Plan/Verify modified
times, terminal completion and detail dates. Missing dates retain their existing
blank, omitted or Unavailable presentation. Raw nanoseconds and operation
diagnostics retain their machine values; sorting and elapsed time use the
original facts rather than the minute-resolution display.
The default/minimum windows remain 1280×800/1024×640; Details preserves the
bounded table viewport and its virtual scrolling at both sizes. The global and
item cards wrap long text and retain separately reachable scrolling and focus.

[M1_PLAN](M1_PLAN.md#m1-8-execution-review-closure) owns M1-8 delivery status and its finite
acceptance. The superseded `76f9281` allocation and its rejected layout evidence
are historical in [the recovery archive](obsolete/M1_8_U_RECOVERY.md).

On `review-publication-protocol-failed`, the pane keeps prior settled review
truth, clears the faulting live row decoration, disables mutating actions, and
shows: **NamiSync could not publish this review safely. Close the task and try
again.** Event drain and exact release continue for custody, but queued events
cannot repopulate the discarded generation. The issue remains visible after
release until task close. Fault precedence, phase mapping, disposal, and
allowed operations follow this document and [INTERFACES.md](INTERFACES.md).

The browser retains only one accepted byte-fitting tree window for the selected
pane. It never keeps a hidden complete plan/inventory list and never receives
`OperationResult.items` or transient operation hashes. Retention exhaustion
guides the user to close a task or wait for retry state to expire. A tree
population refusal instead guides them to narrow roots or resolve scan/preflight
problems; an initial refusal has no partial tree and a replacement refusal keeps
the prior complete tree. Exact budgets, hard-wall precedence, omission
witnesses, paging, generation pins, and close/release reservations remain
bridge/defense authority.

Plan and inventory windows carry the complete server-owned generic row frame.
The browser passes identity, hierarchy, accessibility position, expansion, and
revision authority through without inferring them from paths, adjacency, or the
currently retained rows. A raced read is rejected rather than splicing
generations.

Sync is a serial task interaction: Setup creates one immutable reviewed
plan, the user chooses a dependency-closed selection, and Execute attaches to
the same task only after commitment and fresh preflight of that set. A terminal
with `filesystem="refused"` and `disposition="unrun"` displays the generic
“Execution did not start” state and retains the committed selection for review.
After retained review capture, separate guidance identifies preflight refusal,
invalid execution commitment, or another refusal. Closed preflight codes select
fixed actionable explanations, such as insufficient target space; raw exception
and path details are not displayed. The guidance survives release and navigation.
A reviewed-negative admission receives preflight guidance immediately without
committing selection; [BRIDGE](BRIDGE.md) owns the bounded refusal disclosure.
Recovery is explicit **Plan again**. Only failure to admit an execution restores
editable selection; a preflight rejection after admission does not. Plan again freshly resolves
the immutable reviewed volume pair, then creates a new task with the old frozen
Setup and default selection; changed Setup also creates a new task. Neither path
copies authorization. There is no background replan, execute-anyway,
auto-commit, or unattended path. Automatic linked verification stays in the
execution session; manual
exact post-copy verification is a later session that never rewrites execution.
When exact handoff is blocked, the UI explains why and offers only the clearly
labelled ordinary **Verify current state** fallback for an otherwise eligible,
normally completed execution; this is not a terminal retry action.

Pre-execution capacity refusal, including queued wakeup refusal, keeps the task
visible without execution, automatic retry, or automatic close. Scan/planner
population refusals may have no plan; review-preflight space refusal may retain
an immutable plan with a negative verdict. They must not share a fabricated
partial review. After resolving the cause, explicit Plan again performs fresh
scans and review. Recognized operation/copy, cleanup and destructive-prerequisite
disk-capacity failure during execution now settles the current operation and
admits no later operation. Recorder-only item-write failure remains recording
degradation. Execution review shows the yellow capacity message. This color does not
erase any known failure or independent recording/integrity issue. Other I/O
failures use the existing typed generic reason and available diagnostic detail;
a richer I/O taxonomy is deferred to M2.

M1 execution review also supplies an informational trash-location string. It is
shown as a location only, without a total, existence claim, scan of everything
in `.synctrash`, or promise that externally removable files still exist. No
purge action is implied.

The Plan pane distinguishes immutable **Review snapshot** context from the
current edited selection and the latest fresh-execution notices. Search,
filters, collapse, and viewport never change selection. Notices are visible
typed context. Their exact supplied notice/path facts are available in Details;
they remain inert for selection and execution.
Operation groups expose every operation once, with a distinct non-folder
semantic; group/folder checkboxes operate on server-defined membership
independent of the current window. Move peers, item/node anchors, dependencies,
rollups, risk, and selection authority all come from the server projection.
The browser never reconstructs them from display paths.

Plan rows remain hash-free. Execution evidence is shown only when the bounded
atomic ledger view classifies it as execution-owned; current-state evidence is
labelled separately. Execution and manual post-copy overlays remain independent
fields. A replacement attempt decorates from one complete new generation, never
a mixture or old fallback, while settled membership remains stable until
terminal publication. View behavior, grouping, evidence classes, overlays,
and anchor behavior are defined here and in [PRESENTATION.md](PRESENTATION.md); future exact DTOs remain open.

Inventory remains distinct from plan review. Released terminal inventory tasks
open their own read pane, including when selected again. It supports backend
literal search, counted server facets, collapse, bounded windows and explicit
sibling filename/own-size/own-mtime sorting through the Filename, Size and Modified
headers: ascending, descending, then canonical path order. The Default facet view hides acknowledged direct matches;
their complete count and Acknowledged facet remain available, and necessary
folder ancestors remain visible. Neither browsing nor hidden rows changes
complete folder rollups. The browser retains at most 256 rows and reuses the
generic tree controller's keyboard, scroll and stale-generation behavior with
an explicit 24 px row height; other tree consumers retain the 28 px default.
Its columns are Selection, Filename, Presence, Checksum, Size, Modified and Notes.
The Selection header has an accessible name and no visible text. Header and row
checkboxes are disabled, unchecked and non-mixed; they dispatch no selection
or action. Functional Inventory selection remains M1-10.
Checksum shows eight characters of recorded baseline evidence, with the full
stored digest in its tooltip; no evidence shows an em dash. Missing, modified or
reappeared rows retain their stored checksum. A scan does not verify current bytes.
Presence shows one gallery-style semantic label. Missing and unsupported presence
retain their labels; for present items, Mismatch overrides Reappeared, then
the stored verification state supplies Verified, Modified or Unverified.
Reappeared stands alone without implying fresh verification. Rowless folders
and scan notices remain neutral Folder and Notice labels. Acknowledgement,
bounded warning details and partial/overflow size qualifiers appear in Notes;
complete evidence remains in Details and tooltips. Filename alone absorbs
passive width growth. Manual resizing transfers width from Notes down to its
14rem minimum; Filename and Modified retain their 12rem and 7rem minima.
Both lists reuse 24 px rows, 12 px/16 px caption text, shared zebra surfaces,
16 px checkboxes, semibold folder names and state labels, monospace checksums,
and the shared tertiary foreground for Size, Modified and Notes. In forced
colors, active Inventory text cells inherit HighlightText while filled Presence
backgrounds and disabled checkbox semantics remain. Tree spacers do not receive
zebra fill. Folder Size shows
complete file bytes while its tooltip and Details distinguish own object facts.

The frozen Setup, status and table align with Plan review. The standalone task's
switcher selects Integrity and disables Sync. Whole and selected Refresh are
status actions. Setup's path region shares Plan's two-line minimum height while
retaining one real Root line. The status card keeps the current scan outcome,
complete inventory rollup summary and one persistent detailed status paragraph.
That paragraph carries the displayed publication's scope and scan counts, marks
incomplete coverage, and includes loading, action-result or recovery guidance
without adding temporary paragraphs. The visible-row count remains a view fact,
not a second inventory total. Its shared 8 px progress track remains visible;
unknown active scan totals use the shared indeterminate animation, and terminal
state stops animation without inventing a completion percentage. Supplied known
progress retains the task snapshot's value. Details starts hidden and opens a full-height optional right
column using Plan's two independently scrolling cards: task facts above and item
details below, with a selection placeholder. Hiding Details restores focus when
it was inside that column. The shared 20rem/40% cap, 2:3 global/item allocation and minimum-size chain
preserve table scrolling. Acknowledgement and restore controls remain with the
selected item's details.

Refresh selected follows the tree's current active file or folder in its loaded
window, including arrow-key navigation while Details is hidden. Arrows move
highlight without reading or replacing item details. A cleared active row or an
active notice disables Refresh selected. Acknowledge missing and Restore visibility
continue to act on the item displayed in the details card.

Activate a row with click or Enter to load its detail selection. Domain subjects load fresh exact
ledger evidence with observed and attested facts, full digest, provenance,
evidence observation time, verification freshness and invalidation. Synthetic
folders show complete rollups and their path; notices show their informational warning only.
Window labels are bounded basenames, and flat notices show a code plus bounded
path tail. The existing detail read supplies complete folder/notice paths and
diagnostics from the published snapshot, labelled **Path at scan time**; domain
subjects keep their separate fresh ledger evidence. Full-path server search is
preserved independently of those compact labels.
Ledger, synthetic-folder and non-null notice paths use the published summary's
root for full filesystem display. Missing roots retain relative text, and a null
notice path remains unavailable. Global detailed scan scope also uses that root;
the central status scope, item titles and table text retain their existing form.
These joins use supplied detail facts without filesystem probes.
Task navigation, view changes and Close retire details before late replies can
restore them. A failed read normally offers Reload inventory view, which reads
current publication without starting another scan. If a refused Refresh has no
current details and retains an earlier publication, guidance instead directs
the user to check the location/reconnect its drive and use Refresh. Confirmed
Refresh admission clears its transient action message; the current scan state
owns progress and terminal feedback. The pane labels the current scan
state separately from a displayed prior publication. The displayed scan summary
names its producing scope: Entire location, an exact item, a folder including
subfolders, or selected items. Completion and observed/missing counts apply to
that scope; a scoped Refresh also states that other inventory items were not
rescanned. Notices are labelled as belonging to this scan, with no accumulation
of earlier scans' notices. A retained prior publication keeps its original scope.
Refresh acts on the whole
location or a selected file/folder; folder scope includes hidden and off-window
descendants. Acknowledge missing hides missing subjects from default matches,
while Restore visibility reverses only that acknowledgement and does not restore files.
The controls show confirmed applied/noop/stale/conflict counts and an unresolved
suffix. An uncertain original action retains Check original outcome across task
navigation. Visibility needs a confirmed current publication; Refresh can recover
from a prior publication after a failed rebuild. Notices have no action controls.
Baseline, Verify, Rebaseline and live integrity overlays remain future controls.

Plan and Inventory rows offer a shared context menu using the existing menu
surface and item styles. Right-click targets the row under the pointer without
changing execution selection or loading details. Shift+F10 or the ContextMenu
key targets the focused Plan row or Inventory tree's active row. Show details
opens the existing Details pane for that exact row; Plan selection and container
Expand/Collapse reuse the existing server-scoped actions. Committed, disabled
and informational Plan rows have no selection action. Inventory has no
selection action; its checkboxes are disabled visuals only. Its domain file/folder rows offer Refresh selected;
Acknowledge missing is offered only for a currently eligible row whose own
presence is missing, including a domain folder, using the existing node-scoped
visibility command. Missing descendants do not qualify a present folder. The
toolbar retains its existing complete-folder actions. Notices offer details only.
Opening a menu never initiates a command; stale, pending, closing or replaced
owners cannot dispatch one.
Owned row gestures suppress the browser context menu even when their current
custom menu is stale or empty. The open menu also consumes the Menu key's native
follow-up context gesture without moving the popup or its focus.

Menus remain inside the viewport and work area. Arrow keys and Home/End move
within the menu; Escape restores the current invoker and Tab dismisses while
continuing normal navigation. Outside interaction, focus/foreground loss,
scroll, resize, task/view replacement and disposal dismiss without stealing
focus. Inventory pointer invocation preserves a partially visible row's scroll
position, while keyboard invocation reuses the tree's active-row authority.

The accepted but unrealized policy admits eligible selected files with or
without evidence to rebaseline. It always hashes and conditionally replaces or
creates evidence,
even for a genuine match, and clears verification freshness; explicit
acceptance remains required for all-null and mixed selections. Baseline stays
missing-evidence-only; verify compares existing evidence or establishes an
initial baseline without claiming a verification. The
[three-operation policy](VERIFIER.md#accepted-standalone-operation-policy)
owns the outcomes and deferred compare-and-accept behavior. This is accepted,
not current desktop functionality.

The accepted future integrity surface presents ledger-derived verification state
separately from its latest ordinary-integrity overlay. Manual post-copy results
never enter that field. Folder rollups exclude warnings and do not change when acknowledged
rows are hidden. Overflow is displayed as unavailable, never a clamped total.
Details label current digest provenance/currentness/invalidation and render
times without floating-point authority. Exact inventory view, filter, overlay,
rollup, scalar, warning-identity, and replacement rules remain bridge/domain
authority.

The future history page will use retained activity-aware envelopes and details
and remain neither replay nor resume. It is explicitly deferred from this
second-half reslice; task review does not depend on that page or use history as
a fallback for missing task artifacts.

## Presentation and responsiveness

Progress is replaceable telemetry. The browser reports the active nested event
version truthfully; exact current/target versions and atomic cutover are owned
by [BRIDGE.md](BRIDGE.md).
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
monotonic semantics. The bridge drain consumes these fields through its pure
protocol reducer and exposes a frozen derived state to update consumers; the
Plan row adapter consumes nominal active-item progress without changing the
settled operation lifecycle during automatic verification.
At the accepted cutover, the UI preserves large quantities exactly and keeps
opaque identity non-arithmetic. Scalar and event-containment mechanics remain
bridge/defense authority.
Executor pipeline diagnostics are opt-in developer data, not the rolling
transfer rate or ETA promised to users.

**M1-8 progress presentation.** Events carry dispatcher-stamped UTC `at`;
ordinary executor/verifier progress is throttled (normally 100 ms), with forced
boundaries and lossy coalescing, not a delivery metronome. The Python adapter
reduces accepted Progress and publishes presentation facts (BRIDGE owns the
snapshot contract); the browser formats those facts.
The digest uses phase aggregate bytes, with item-count fallback only for known
byte-free work. Nominal active-item bytes feed Plan row progress independently;
automatic verification preserves the settled operation lifecycle.

- The status line shows phase aggregate byte progress and settled item count
  (`items_done` of `items_total`); an active ordinal, if shown, is labeled
  separately and never increments the settled count. The overall percentage
  uses phase `bytes_done / bytes_total`; known byte-free work may use known item
  counts, while unknown totals stay indeterminate. Zero/zero alone is not success.
- An active row uses only nominal `item_type`/`item_id` matching and its own
  `item_bytes_done / item_bytes_total`. No aggregate percentage is copied into
  a row; a path is never identity. Unknown item counters remain indeterminate.
  Reliable outcomes retire active decoration and supply the terminal row result.
  Verification progress remains separate from the already-settled operation
  result; it must not turn a completed copy back into an executing copy.
- Throughput uses aggregate byte deltas divided by Python monotonic sample deltas
  stamped when Progress reaches the adapter sink, independent of drain cadence.
  Share one five-second smoothing horizon with phase ETA: a time-weighted EMA
  with `alpha = 1 - exp(-dt / 5s)`, seeded by the first valid two-sample rate.
  Retain only a prior sample and smoothed rate. Subtract Scalar64 bytes exactly
  before approximate rate/ratio conversion. No per-item rate or second filter.
  Sample once per newly accepted Progress update, never on replay, repaint or an
  outcome update that merely retains the prior Progress body.
- ETA is `(bytes_total - bytes_done) / smoothed_rate` for this phase only.
  Unknown totals or a zero/unavailable rate give unavailable ETA; throughput can
  remain available without a total. Estimates never predict subsequent verify
  work from execute, or survive terminal settlement. Label them as estimates.
- Equal/backward sample times simply rebase sampling and make the estimate
  unavailable until another positive interval; do not reject valid progress.
  Ordinary item handoffs retain aggregate sampling, including handoff after a
  reliable outcome; outcomes themselves do not sample. A stream's first attempt
  ID retains sampling. Pause/resume, retry of the same item and budget changes
  restart sampling; phase, session, explicit Gap and terminal/reset retire the
  old estimate. Navigation
  does not create a second rate history: returning to a task adopts its current
  authoritative estimate. Ordinary sequence holes/coalescing use observed
  deltas with no recovery or compensation.
- Inconsistent progress clears the affected estimates and comparison state,
  with visible diagnostic feedback. Reliable control and final results continue
  to arrive; a presentation fault cannot keep a settled task looking active.
- Preserve ARCHITECTURE's aggregate high-water rule. Within a phase, displayed
  percentage is a high-water of the valid computed percentages, so an expanded
  verifier budget does not move the bar backward. For the same active item,
  retain its displayed high-water across new attempts; raw attempt bytes may
  restart. Keep only that active item's display state. Pause/resume and hidden
  return preserve visual high-water; new phase/item, explicit Gap or session
  retirement starts a fresh display domain. Unknown counters do not become
  fabricated known values. Neither a held bar nor 100% claims success.

Executor retry catch-up may temporarily produce zero observed throughput, and
verifier counters measure physical read work with a growing budget. These are
approximate progress estimates, not certified device speed or durable bytes.
Loss/retry noise is acceptable; no accuracy SLO, retained sample history,
background sampling timer or adaptive estimator is required for M1-8.

Filter/search state never changes the underlying plan or inventory selection;
changing a location or plan option invalidates only the state that semantically
depends on it.

Plan search uses a fixed 150 ms trailing debounce and remains editable during
view refresh. If a query arrives while a view request is in flight, the task
retains only the newest query and dispatches it after that request settles;
switching tasks does not discard a queued query for a retained review. Search
and filter navigation never mutates selection. Stale successes and failures do
not replace the current valid page. The pure Slice 4 helper admits the
documented bounded literal query rather than an arbitrary responsiveness limit.

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
- Plan and inventory consume facade views only and remain semantically separate;
  Setup reads defaults but commits no global setting, and UI cosmetics never
  change a plan's captured options. The deferred history/settings pages cannot
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
  exact-handoff fallback labeling, and no browser-retained full result.
- Exact target contracts and gates remain in
  [BRIDGE.md](BRIDGE.md), delivery coverage in
  [M1_PLAN.md](M1_PLAN.md), and test-scope policy in
  [TESTS.md](TESTS.md).
