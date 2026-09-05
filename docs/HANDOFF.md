# Session Handoff

Status (2026-09-05): TS-R2 through TS-R5 external review and its separate
TS-R5-CR correction are complete. TS-R6 has not started.

## Review and corrections

- User authorized a read-only Claude Code review and a separate correction
  commit for valid issues. Model: `claude-opus-5`; effort: `xhigh`.
- Two exchanges reused session `fbc3fbb8-05e9-4b92-a629-81cc88af1c17`.
  About 26 minutes for the initial review and four for reconciliation;
  CLI-reported list-price cost: $20.565848.
- Claude judged the four checkpoints sound. Three remaining normal service
  constructor bypasses now use `make_service`; both promoted Node gates have
  explicit path/launch/timeout guidance. Required-probe and fixture documents
  are aligned; baseline support counts remain frozen while additions are
  explicit TS-R8/TS-R9 inputs. No production source changed.
- The protocol-rename drift claim was withdrawn because those exact names
  were explicitly approved. The missing-close-lock detection claim was also
  withdrawn: the existing concurrent-close test catches that mutation.
  The Node error/failure classification was corrected; the surviving issue was
  diagnostic quality. No unresolved substantive review finding remains.

## Verification

- Focused controls: 164 before and 164 after. Transport alone: 124 passed.
- Interfaces/dispatcher: 1,605 passed. Ordinary: 4,642 passed, four
  established capability skips, 28 headed deselected. All 12 imports pass.
- Isolated constructor and Node witnesses verify the intended improvements.
  The settings closed-flag variant is irrelevant to early malformed-settings
  refusal; a lost runtime is the settings initialization detector. Earlier
  classifier stops are preserved, not represented as passing evidence.
- Original oracle (30 scenarios x3) and headed (28 cases) results remain the
  prior TS-R5/TS-R4 evidence. Production is unchanged in this correction.

## Review boundary and resumption

- The first Claude session created and deleted `ns_files_tmp.txt` despite the
  read-only request. Its separate Write attempt was blocked. Exact pre/post
  Git status was unchanged. The follow-up removed shell/write tools and used
  only Read/Grep/Glob; exact pre-existing status was again preserved.
- Full review, reconciliation, metadata, mutation evidence and status snapshots
  are under ignored `build/claude-review/ts-r2-r5-20260905-191946/`.
- Earlier checkpoint evidence remains under
  `build/test-simplification/536915fb28068c141f59b2243119530205538b4d/`.
  The original delivery register is `docs/TEST_SIMPLIFICATION.md`.
- Stop here for the user. Do not start TS-R6 automatically. Reviewed execution
  through the working native PowerShell host remains the reliable tool path;
  use explicit UTF-8 for all Python text I/O.
