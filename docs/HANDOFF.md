# Latest session — Python/pip security maintenance complete, 2026-10-22

Updated system Python at `C:\Program Files\Python313` and the user-managed
Python3.13 runtime to3.13.17. Updated the existing managed3.14 runtime to3.14.9.
NamiSync stays on3.13; `venv --upgrade` refreshed its existing launcher/config.
System installer completed after user-approved UAC: exit0, no restart required.
The supervising update command also exited0. No installer/approval remains pending.
Python Install Manager automatically updated itself to26.4 during inspection.

All four interpreters now have pip26.2.2 and vendored certifi2026.10.19, checked
in both normal and isolated mode. The compromised emSign root is absent from
each bundle, and isolated `pip check` passes for all four. Removed the redundant
user-level pip copy created by the supervisor after verifying fixed global pip.
NamiSync's installed package versions differ only in pip26.1.2 ->26.2.2.
No product/test source or other project dependency changed.

Compatibility on the updated NamiSync environment:
- Host/native87 and imports12 pass.
- Ordinary6,178 pass; four existing symlink-privilege skips,35 headed deselected.
- One real installed-wheel SH-G-6 WebView2 startup/Ready/close smoke passes.
- Final interpreter/package checks, repository diff and active local doc links pass.
The system-wide update does not change the tested venv/base; these passes remain
applicable. The smoke is not the complete headed release suite.

Evidence: `build/node-security-20261022/python-update/`, including original
config/packages, verified installer/wheel, install logs, ordinary/headed XML,
`final-verification.json` and `status.md`. A failed quoting-only cleanup attempt
made no changes; its receipt remains alongside successful guarded cleanup.

Earlier Node24.22.1 maintenance and local security triage remain in the parent
evidence directory. `security-review.md` records the earlier inspection, not
current Python/pip status. The user reports Chrome updated. FlClash/Codex vendor
updates and VMware remain deferred by the user; their managed files were not
modified. GitHub private Dependabot alerts remain unread (HTTP401 at triage).

Baseline inspected: `a631891430210f6f423805463b8724867e3cb435`. PO4 remains
complete; prior evidence is in `build/handle-relative-investigation-20261021/implementation/`.
Retained `K:\NamiSync-probe-5d4b3b539c3d4e5a8f1fa95568a26e6d` fixture and
read-only `H:\OneDrive\NamiSync_OneDrive` context were not used or cleaned up.
M1-12/release/DOC-2 remain inactive. No commit/push/PR/history rewrite occurred.
