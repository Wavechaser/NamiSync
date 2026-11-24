# Latest session — M2-A1 live-data guard and M2-A2 spikes, 2026-11-24

Work is on `milestone2`; nothing is pushed. The user accepted M2-A1 and M2-A2
and their decisions are in [M2_PLAN](M2_PLAN.md).

## Changes

- `ab31ba08` docs(m2): accept the A1 and A2 checkpoints.
- `9bb58fa9` feat(interfaces): M2-A1 complete. Source runs default to
  `%LOCALAPPDATA%\NamiSync-Development`, and only the frozen release uses
  `NamiSync`. The desktop identity follows the resolved root, which revises
  SH-G-10. A session-wide audit hook in `tests/conftest.py` fails any test that
  tries to change the live root. `gui.ps1`'s shell now uses the development
  root itself, and the old `NamiSync-Development\shell` data is left unused.
- `114c9c26` docs(m2): A2 spike results recorded in each feature's entry, with
  evidence in [EV-0040](../evidence/EV-0040/README.md). Also in this commit:
  A1 marked complete and A2 left active.

## Verification

- A1: lint-imports 13/0. The ordinary suite has 6675 passed, 4 skipped and 7
  failed; the 7 are the known `.venv`-interpreter failures listed below. Headed
  SH-G-2 passed 3/3 and the focused modules 322/322. Two adversarial review
  rounds closed with no open findings.
- A2: the spike numbers were spot-checked against the raw files in EV-0040, and
  the evidence check reports no problems.

## Open items

- A2 stays active until the desktop checks are done; each spike's checklist is
  in its EV-0040 report. Still open: real Explorer drops and the elevated-app
  case (`build/m2-a2/drop/spike.py`); and the framing prototype
  (`build/m2-a2/framing/proto.py --mode nonclient_carve`) for Win+Arrow, high
  contrast, light/dark switching, and Alt+Space with PowerToys Run quit. My
  computer-use access could not drag from Explorer or see the venv-Python
  window. The prototypes stay in `build/m2-a2/` for these checks.
- Decisions the spikes raise for the user:
  - whether NamiSync may write a per-user `AppUserModelId` registry key for
    toasts (against INTERFACES' no-registry stance);
  - how Stop handles planning, which has no checkpoints and keeps volume
    custody.
- Finding, not fixed: planning time grows faster than the trees (10 s at
  10k/3k files, 41 s at 30k/9k, more than 8 min at 100k/30k on a loaded
  machine). It needs a measured study before any fix.
- A8's gate needs an HDD that carries two lettered partitions; none exists on
  the reference machine.
- `J:\NamiSyncSpike\stop-latency` (about 157 MB) is kept as the HDD fixture
  until the user decides. Leaving Do Not Disturb off was the user's choice.
- Carried over: the local `.venv` is CPython 3.13.17, not the release
  interpreter 3.15.2. Because of that, six custody tests and one native-gate
  test (a pythonnet 3.1.0 vs 3.2.1 mismatch) fail locally; rebuild the venv per
  TOOLS before relying on them. Also carried over:
  - Elevated cleanup of the Codex-sandbox `build/` residue.
  - Frozen `sh_g_8_*` artifacts must not move.
  - Keep `F:\NamiSyncExecutorBenchSource`, `H:\test_dir`, `dist/v0.1.0/` and
    `build/inventory-cold/`.
