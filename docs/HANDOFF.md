# Latest session handoff

## M1-async and M1-5 delivery (2026-09-10)

M1-async is committed on `milestone1` as `675181a`. This M1-5 delivery is
based on that commit, with the atomic commit title
`feat(workflows): unify location admission and remembered locations`.
M1-4 remains complete in `ab453e1`. No recovery branch was needed.

M1-async adds bounded native admission/completion for create/start/release/close,
retaining the existing task/session effect owners, replay, recovery and one
native-send guard. Its final evidence is in `build/m1-async/evidence/`:
4,884 ordinary tests passed with four existing privilege skips, all 29 installed
headed tests passed, and neighborhood/import/docs/adversarial checks passed.
The approved README status update and real-channel logging fixture migration
are included in that commit.

M1-5 shares workflow-owned typed location admission across current picker plan
starts and inventory/integrity. Bounds precede task custody; replay precedes
native work; refusal creates no delivery/session effect. Remounted remembered
identities are freshly resolved. Durable sync activity supplies at most five
sources, five targets and five active pairs in one read-only snapshot. Existing
point-of-use probes remain; candidates and remembered hints grant no authority.

M1-5 verification:

- Focused: 680 passed in 23.68s
- Database/workflows/interfaces neighborhood: 2697 passed, 2248 deselected in 111.58s (0:01:51)
- Ordinary: 4912 passed, 4 skipped, 29 deselected in 237.83s (0:03:57)
- Installed-wheel real WebView2: 29 passed, 4916 deselected in 132.51s (0:02:12)
- All twelve import contracts, documentation/link/diff checks, and independent
  adversarial review passed. No collected module was added or retired.

The ordinary skips remain existing Windows symlink privilege limitations.
No new timing, whole-runtime resource or compositor-health claim is made.
The baseline was refreshed on clean `675181a` before M1-5 edits: 44 owner-seam
and 17 picker tests passed. Raw evidence remains in
`build/m1-5-design/runs/integrated-675181a-02/`.

M1-5 raw commands/results, final hashes and review remain under
`build/m1-5/evidence/`, with reproducible inputs under `build/m1-5/inputs/`.
The first focused failure and subsequent green runs are retained. Review found
two introduced service regressions, both corrected before closure: exception
context retention and oversized path custody before validation. Their existing
or added assertions remain in the final suite. Generated evidence is ignored;
no unrelated files or branches were cleaned.

Pause here for the user's recap and GUI adjustments. Typed/recent Setup widgets,
picker-time feedback, frozen options and M1-6 onward remain pending. No push,
PR or further checkpoint implementation is authorized by this delivery.
