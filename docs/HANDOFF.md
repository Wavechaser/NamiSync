# Latest session handoff

## Maintained icon foundation (2026-09-11)

Base: M1-6 `76ba7d0` on `milestone1`. GUI-I1/I2 form one completed icon
foundation outcome; GUI-D4 is a separate documentation-only investigation.
M1-7 and startup layout/control placement changes remain outside this task.
The user authorized commits and removal of root ICONS.md; its 47 names match
tools/icons.json and the superseded untracked file was removed. No push or PR.

The 47 Regular glyphs use 136 native SVGs for 141 size mappings with five
explicit 20 px fallbacks. Existing API, currentColor/alpha masks, local URLs,
license and original assets are preserved. Selective placement/density rules
are stronger than the flexible action examples. No current controls or badges
changed.

Edit tools/icons.json, run tools/icons.py sync, then check. Both accept a pinned
local --archive; otherwise they fetch the official pinned npm archive. The
command verifies integrity before reading selected members, validates native
sizes/fallbacks and safe SVGs, then generates assets, SOURCE and marked registry/
CSS regions. It removes only unchanged previous receipt-owned stale assets.
Check is read-only. Git pins the two generated code owners to LF so Windows
checkout conversion does not create false drift. The app never loads or packages the tool/catalog. Tests use
the authored catalog for inventory expectations and independent synthetic
archives for generator rules; authenticity still requires the official archive
check. See DESKTOP_UI for update/license instructions.

Final verification: 61 focused passed (4 headed deselected); 4,972 ordinary
passed, 4 skipped, 30 headed deselected; all 30 installed headed tests passed.
The ordinary suite includes both owning departments and the newly registered
tests/test_icon_maintenance.py (26 tests); no test module was retired. Authentic
archive check passed; sync reported zero changes/removals. Fresh adversarial
review approved after correcting a digit-bearing glyph regex in the independent
registry assertion. Logs are build/gui-icons/maintenance-focused-01.txt,
maintenance-ordinary-01.txt and maintenance-headed-01.txt. Tests used one slot,
fresh external basetemps and PIP_NO_CACHE_DIR=1.

Earlier GUI-I1 evidence: 1,520 interfaces and 30 headed passed. A shell focus
assertion failed once then passed isolated and full without a source change.
A concurrent image probe had one unexplained light info:md failure; it now
decodes 136 unique URLs sequentially once without retries, retaining all 141
mapping checks and failure details. That does not prove the old failure cause.
Prior logs and the pinned archive remain in ignored build/gui-icons/.

GUI-D4 completed its source audit and paired manual comparison, without a
production shadow change. Popup is an opaque direct body child with two black
Fluent shadow layers; no inherited card opacity, active blur, blend mode or
extra elevation was found. The gallery's old normal/opaque specimen labels are
stale and nested cards exaggerate alpha, so the dedicated diagnostic uses
explicit receivers and shadow layers instead. Ordinary source-over darkens
these colors; double alpha or divergent color conversion is a hypothesis, not
an established bug in our code or an identified upstream defect.

The user disabled HDR while keeping 10 bpc and automatic color management on;
read-only native probe confirmed LG WCG, HDR false. They report halos on single
white 5% and nested white 5% receivers with key-only or combined shadows, not
ambient-only/no-shadow or the opaque receiver. Switching alpha-zero white to
alpha-zero black made no noticeable difference. Native receipts verify both
Mica hosts and exact requested ARGB. Thus hidden-white RGB is a weaker
hypothesis, while broad shadow plus translucent receiver remains the target.
Native Fluent ThemeShadow and a CSS shadow in transparent WebView2 do not share
an identical rendering implementation; neither comparison alone assigns blame.

Diagnostic wrappers and frozen baseline child/scenario are in ignored
`build/gui-tuning/halo-10bit/`; `composite-d4a-white/` and
`composite-d4a-black/` contain isolated state, native receipts and gallery
milestones. Overlay computed-style receipts are visible in each window and are
separate from the gallery's pre-overlay completion evidence. Both new diagnostic
windows remain open for user comparison; prior user-owned/diagnostic windows
and display settings were not changed by the agent. Mica remains required and
no shadow mitigation is implemented. BUGS and M1_PLAN retain findings and limits.

Useful primary references:
- https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2controller.defaultbackgroundcolor
- https://www.w3.org/TR/compositing-1/#simplealphacompositing
- https://learn.microsoft.com/en-us/windows/apps/develop/ui/shadows
