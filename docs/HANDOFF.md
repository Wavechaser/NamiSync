# Session Handoff

Status (2026-08-15): `DEFENSE.md` is the normative threat, fault, and tolerance
model. It centralizes the supported standard-integrity single-user baseline,
trusted computing base, hard walls, user-authorization boundary, T0–T4
tolerance policy, WebView trust decision, TOCTOU mitigation ladder and stopping
rule, and EW-1 through EW-4 residual dispositions.

The policy was reconciled against the compact `ARCHITECTURE.md` and
`FEATURES.md` forms landed on 2026-08-15 rather than the older documents used
during the initial discussion. Full data preservation is now explicitly
conditional on managed-root quiescence during mutation. Observable external
drift remains guarded, while post-final-guard path races are classified by
their exact consequence instead of timing or guessed intent.

The packaged desktop document is trusted code and every value it displays,
receives, or sends remains untrusted data. Arbitrary same-origin script is a
trusted-base compromise, not a contained renderer principal. The 64-handler
bridge ceiling is documented as bounding admitted domain work after
pywebview's exposed-call thread creation, not raw WebMessage threads.

## Documentation Propagation

- `AGENTS.md`, `README.md`, and `ARCHITECTURE.md` index the new authority.
- `FEATURES.md`, `EXECUTOR.md`, and `PREFLIGHT.md` point their external-writer
  descriptions to the defense dispositions. The stale pre-M0
  `DESIGN_REVIEW.md` moved unchanged to `docs/obsolete/`.
- `BUGS.md` distinguishes a technical residual from policy acceptance.
- `M1_BRIDGE.md` and `INTERFACES.md` defer the trusted-base decision to
  `DEFENSE.md` while retaining exact mechanism and gate ownership;
  `M1_SHELL.md` carries the standard-integrity release work.

No production behavior or test code changed. The next mutating desktop command,
new principal, elevated host, network authority, or promise of safe concurrent
external mutation must reopen the applicable defense review before
implementation.

## Verification

- Read the complete final `DEFENSE.md` and reviewed the complete documentation
  diff.
- Confirmed `DEFENSE.md` contains no elevation-based snapshot rung.
- Confirmed external-writer, residual-acceptance, renderer-trust, and bridge-
  admission wording is consistent across the propagated documents.
