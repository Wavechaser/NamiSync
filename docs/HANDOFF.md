# Latest session handoff

## GUI integration tuning (2026-09-11)

GUI-1 restores persistent selection paint and the 3 px accent marker on the live
rail. The only production change adds `aria-current="page"` to the existing
ordinary/forced-color task-card state rules; gallery variants and the separate
Close button remain. Base is clean `e19ed9d` on `milestone1`. The task uses the
current checkout; the atomic delivery title is
`fix(web): restore live task rail selection cues`. No worktree, recovery branch,
push or PR is involved.

Verification: the pre-fix real installed-wheel task-shell test reproduced
the missing marker. After the fix, 56 focused checks, the task-shell headed
witness, 1,503 interface tests and all 12 import contracts passed. Independent
GUI-1 review approved the actual diff. All 29 installed-wheel interface headed
tests passed in the final interactive-desktop run (`headed-03.txt`). The first
attempt failed reading a shared pip cached wheel; the cache-free sandbox retry
could not enumerate desktop windows. Both failures preceded GUI assertions;
the final run used `PIP_NO_CACHE_DIR=1` and interactive desktop access. No
production/test workaround was added. Logs and review receipts are in ignored
`build/gui-tuning/evidence/`. Diff checks passed; no test module was added or
retired. No task-created branch, worktree or disposable input needed cleanup.

GUI-D1 remains investigation only. The old HDR fallback from `1fe32b3` still
wins by specificity; SDR uses black shadows. Mica's host/page is transparent
while the dropdown surface is opaque. The gallery's normal/opaque specimen
labels no longer distinguish alpha, and its elevation-8 differs from the real
dropdown's elevation-16. Source findings passed separate read-only review;
there is no claim of visual halo reproduction or a proven compositor cause.

The user sees dropdown halos on natively SDR displays, but not after moving a
window from HDR to SDR on this computer. After the rail tests finished, they
disabled HDR globally and reported reliable halos where dropdown shadows overlap
cards, but not bare Mica. Dark cards use white at 5% alpha; the earlier solid CSS
background is a fallback, not an opaque underlay. Next diagnostic should record
Chromium dynamic-range, native material and popup styles, then compare the real
dropdown shadow over bare Mica, translucent cards and a temporarily opaque card,
with a shadowless control. That isolates the newly reported overlap condition;
the renderer/compositor cause remains unconfirmed. No shadow or card correction
is authorized by the current investigation.

M1-4, M1-async and M1-5 remain complete. M1-6 onward is outside this task. README's
phase synopsis and the substantive defect ledger need no change for this
presentation correction. Existing Close pending/retry semantics remain binding.
