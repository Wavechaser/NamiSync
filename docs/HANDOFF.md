# Latest session — M1-R2 distribution closure, 2026-11-09

## Delivered outcome

Branch `milestone1`, starting at `bde18995`. R2 completes the portable
distribution inputs and guidance; it does not freeze or distribute the R4/R5
candidate. R3's existing disposition remains unchanged.

- Build ships START-HERE, BUILDING, GPL and THIRD-PARTY-NOTICES: twenty existing
  About records plus 31 pinned supplements. Preserve attribution notes, exact
  upstream texts, source directions and byte-preserving Git attributes.
- Cover Python's compiled/native dependencies, PyInstaller's bootloader and its
  separate zlib, setuptools' vendored/configuration code and MPL source access.
  Independent review additionally followed 19 Python Windows projects, 290
  direct references, 790 resolved source/header paths and 45 bootloader files.
- Trace 43 stray DLLs (29 core API sets, 13 CRT API sets, ucrtbase) to the
  freezer's ambient PATH lookup into Codex's libheif directory. Constrain its
  PATH, omit Windows 11's system UCRT/API sets, retain Python's VC runtime and
  verify collected native origins/hashes. CI now retains origins and raw TOCs.
- Existing dependency versions, app behavior and measured artifacts remain
  unchanged. The external Microsoft binary-terms agreement is explicitly an R5
  handoff prerequisite; notice inclusion is not agreement or redistribution
  clearance.

## Verification and evidence

`build/m1-r2-20261109/attempt-04/` is the final diagnostic portable build from
isolated `checkout-05`, with canonical source bytes checked against the integration
inputs. The source archive has 350 files. Its census reconciles all 436 bundle/ZIP
files, 133 native origins, 773 distinct module/embedded/bootstrap input triples
and 51 notice records. No ambient/UCRT remnants or unknown owner remains.
The 43 removed PE paths are exactly the historical stray population; retained
non-executable native bytes match the earlier build.

- Tools department: 449 passed, three existing symlink-privilege skips. Final
  notice-focused verification: 16 passed. No assertion or gate weakened.
- Actual console help and PE architecture/subsystems pass. Fresh extraction
  outside the checkout, system-only PATH and medium integrity: UI reaches Ready,
  Settings/About displays 0.1.0 and twenty app notices, startup logs agree, normal
  close exits 0 with no Job members remaining before cleanup.
- Independent review checks the actual ZIP, source/notice hashes, compiled
  dependencies, licensing text provenance and final diff. TOOLS owns the summary;
  raw build/census/smoke receipts and source-match evidence live in the task folder.
  Downloaded originals and notice-focused receipts live in
  `build/r2-notices-20261109/`.
- Changed-source whitespace checks pass excluding the verbatim upstream notice
  texts. The full staged check reports inherited CRLF/trailing-space/blank-EOF
  bytes in those texts; preserve them to retain the reviewed upstream hashes.
  `upstream-whitespace.log` records that intentional exception.

Earlier attempts remain as evidence: sandbox environment/temp setup failures;
superseded notice builds; smoke probes that looked for detached About before
opening Settings; and a diagnostic snapshot with checkout rather than canonical
Git line endings. Each was corrected and reverified. No product startup failure
was found. R4 must still assess its exact release candidate and applicable gates.

## Operational context

No measuring-session process, profile, corpus or package was changed. Owned
native probes exited, with bounded Job cleanup. Ignored diagnostic checkouts,
their local Git identities, locked environment, Temp extractions and raw evidence
are retained for provenance; none is a branch or commit to merge. No release,
tag, upload or external delivery occurred. The next release work is R4, then
R5's concrete candidate review and agreed tester handoff.
