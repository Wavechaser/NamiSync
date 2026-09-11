# Latest session handoff

## Shadow composition audit (2026-09-11)

Base: `76ba7d0`, `milestone1`. Diagnostic-only outcome; no rendering change.

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
