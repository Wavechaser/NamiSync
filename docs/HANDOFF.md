# Latest session handoff

## M1-async delivery (2026-09-10)

Delivered on `milestone1` from `74aa6b7` in the atomic commit
`feat(web): add bounded asynchronous command completion`. M1-4 remains complete
in `ab453e1`. Native create/start/release/close return admission separately from
bounded completion. Direct/custom calls, task/session effects, replay identities,
shutdown recovery and the existing final native-send guard remain intact.

The shared exchange population retains both real worker exits and both delivery
phases. DocumentChannel separates its single native send from outstanding
receipts, so absent cosmetic acknowledgement and lost command delivery do not
block later command completions. Queued, sending and awaiting command receipts
together remain bounded to 64. No general scheduler or durable command store
was introduced.

Verification:

- Interfaces/dispatcher neighborhood: 1655 passed, 3262 deselected in 56.02s
- Ordinary repository: 4884 passed, 4 skipped, 29 deselected in 211.92s (0:03:31)
- Installed-wheel real WebView2: 29 passed, 4888 deselected in 130.37s (0:02:10)
- All twelve import contracts pass; browser timeout/recovery probe, focused
  transition witnesses, documentation links and diff checks pass.
- Fresh adversarial review covers the actual diff and raw evidence, including
  independent receipt custody, exact cleanup, generation races and recovery.

The four ordinary skips are existing Windows symlink privilege limitations.
Headed evidence proves the declared app/page contracts, not Windows compositor
health or a new whole-runtime resource claim. Protected measurement artifacts
remain unchanged. No collected test module was retired or added.

Raw evidence, candidate hashes and replay helpers remain under ignored
`build/m1-async/evidence/` and `inputs/`; the initial failed invocations are
retained with their causes and corrective evidence. The approved README update
and real-channel logging fixture migration are included. Applied closure drafts
are cleaned; task-owned evidence is retained. No recovery branch was needed.

M1-5 is authorized next, with its finite scope and gate in M1_PLAN. Before edits,
record this integrated commit and refresh its retained baseline using
`build/m1-5-design/inputs/run-retained-baseline.ps1` with a fresh external
basetemp and the shared runner idle. Recheck replay before slots and candidate
admission after the task claim; preserve fresh point-of-use probes. Workflow
types own candidate/recent results; schema, public service-view registry and
Setup widgets remain outside M1-5.

Finish M1-5 with its own verification, fresh adversarial review and atomic
commit, then pause for recap and GUI adjustments. M1-6, historical DOC-2 branch/
PR work, unrelated files, pushes and PRs are not part of this delivery.
