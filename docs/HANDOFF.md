# Latest session — GUI duration and date formatting, 2026-11-08

## Delivered changes

On milestone1 base `650cddbc`, the small interface-only presentation fix replaces
the seconds-only ETA label with a human-readable duration followed by remaining.
It retains rounding up to whole seconds, shows minutes/seconds through 180
seconds, drops seconds above that, and adds hours from 3600 seconds. Zero units
are omitted except for zero seconds. Unknown estimates remain omitted.

Linked Verify waiting rows now say Pending. Their active-progress and result
precedence is unchanged. Inventory's Modified tooltip reuses its existing local
`yyyy-MM-DD HH:mm` cell formatter instead of exposing raw nanoseconds.
No backend, bridge, timestamp, sorting, lifecycle or progress contract changed.

## Audits and limitations

The absolute-date sweep covered Plan/Verify rows and hover text, terminal
completion, item details, Inventory attestation/ledger dates and Modified values.
The Inventory tooltip was the sole mismatch. Setup recents do not display their
transport timestamps. UTC serialization/logs, numeric sorting facts, durations
and verbatim legal/diagnostic text are outside this UI date-format change.

The finite Action/Presence audit used current source labels, CSS minima and
Windows WPF measurements at 12 px semibold across installed Segoe variants.
Pending fits comfortably. Move + update is 82.89–86.54 px against an 80 px padded
Action minimum, still inside its 88 px visible reach. Other current labels fit
their padded minima. Existing historical WebView2 measurement corroborates
83.93 px for Move + update at a wider default gallery column; this is not a new
current-browser clipping assertion. No visible clipping was established and that
label remains unchanged, as the user requested checking other labels.

## Verification

Evidence: `build/gui-format-20261108/`.

- `interfaces.xml`: all 2,261 interface cases passed.
- `headed.xml`: both installed execution window sizes and Inventory passed
  on the private test desktop.
- Existing production renderer probes cover 17 remaining-time cases, including
  unavailable estimates, and Pending/progress/verified transitions. Focused
  frontend/Plan checks passed 116; the date/Inventory/terminal selection passed
  five. Independent review ran its own four-case selection successfully.
- Shared date probes cover UTC, Asia/Shanghai and America/New_York, early years,
  the admitted nanosecond boundary, missing and invalid values.
- `measure_label_fonts.ps1` and `label-font-measurements.txt` retain the
  bounded font audit. The standalone headless diagnostic produced no usable
  layout output; no claims rely on it.
- Independent review approved the code and subject docs; diff checks passed.

No live user app, measurement-session fixture or unrelated files were changed.
No branch or worktree was created. No push or release packaging is included.
The preceding bounded admission/idle-GC work remains at `650cddbc`; its own
subject and evidence records remain authoritative.
