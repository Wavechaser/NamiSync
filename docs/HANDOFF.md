# Latest session — R5 review and prepared handoff, 2026-11-10

## Outcome

Starting branch `milestone1`, clean `0d6d969e`. R4 remains accepted for
`3ece185f`. R5's byte/evidence review and internal delivery preparation pass,
but **release closure and external handoff are on hold**. The user's decision
on the bounded release-repair proposal is pending; do not infer authorization
from the R4 acceptance or from elapsed time.

The [R5 decision record](M1_PLAN.md#r5-review-and-outstanding-release-decisions--2026-11-10)
owns the findings, finite scope and proposed verification. DEFENSE still requires
standard-integrity GUI enforcement before beta and a security-supported selected
runtime/dependency set. Executable source, build tools, locks and acceptance
policy are unchanged. The accepted archives retain their original README;
the updated repository README will be an input to a future build.

## Completed review and preparation

- Exact accepted ZIP SHA-256:
  `5b9163ce26b2a20734058069c03b966225be5bef6c7aac4b90477a54408f7319`.
  Verified 436 portable members, 350 candidate Git source members, 309 wheel
  members/RECORD, 133 native origins and all 51 notice records. PE classification,
  CRCs and the original/final candidate comparison pass.
- R4 release evidence has 6,556 passes/four privilege skips. All 546 BR-G and
  69 SH-G-named cases pass. The previous 81 was a loose-substring count including
  unrelated cases. DESKTOP_UI's twelve behavior criteria map to 50 exact test
  functions/64 cases; unchanged settlement dependencies retain prior evidence.
- Resource raw FAIL remains explicit: 100k peak 2,316–2,404 MiB, soak trend and
  one 26.629 MiB retained shift exceed yardsticks. The user's acceptance is a
  separate judgment. Correcting units/predicate accounting changes no result.
- BR-G-43 docs now describe shipped sorting/evidence/direct-target writes,
  Remote files and row advisories, accepted R4 status and deferred desktop
  History. The user requested moving the old mockup into obsolete; the two
  files now live under `docs/obsolete/ui_mockup/`, with updated references.
- `build/m1-r5-20261110/delivery/` contains the unchanged renamed executable
  and matching source ZIPs, wheel, required identity/environment files, guides,
  licenses, draft release notes and SHA256SUMS. Eleven files are checksummed;
  the checksum file is the twelfth. Raw native/TOC copies stay in
  `maintainer-evidence/`, outside the prospective tester set. No repack/rebuild.

## Required decisions

1. The candidate has no elevated-GUI refusal, despite DEFENSE's explicit
   pre-beta requirement. Normal-user startup evidence does not close that gate.
   Implementing it or revising the model requires explicit scope authorization.
2. CPython 3.13 remains source-security supported, but the frozen 3.13.17 Windows
   binary misses published 3.13.18 fixes. Normal asset serving reaches Windows
   MIME lookup, with a narrow plausible fixed-path/drive/ACL precondition.
   Setuptools 83.0.0 has a published legacy-installer advisory; the inspected
   supported flows did not invoke its malicious-wheel trigger. No supported hard-wall escape
   was demonstrated. Exact input refresh or a reasoned security-support
   disposition is required; a newer Python number alone is not sufficient.
3. Microsoft distributor/tester agreement and concrete external delivery
   approval remain outstanding. No upload, tag, push or handoff is authorized.

Proposed checkpoint: enforce standard GUI admission, resolve the named runtime/
build/native servicing findings, select exact supported inputs, preserve R3
budgets and renew dependency-affected R3/R4 gates, then return to R5. No such
implementation has started. The old accepted artifact remains evidence.

## Evidence and operational context

`build/m1-r5-20261110/` retains independent artifact review, exact desktop gate
mapping, OSV exact/vendored queries, dated host snapshot, official Python
installation index, full security-support review and the delivery manifest.
The query populations are 17 PyPI pins plus WebView2 SDK and eight vendored
versions; only setuptools matched. Empty queries do not prove safety/support.
The security review includes primary-source links and bounded applicability.

Only read-only receipt/source/advisory checks and documentation validation ran;
no product tests were rerun without changed dependencies. The current host
snapshot is not retroactively attributed to R4. No measuring-session process,
profile, corpus or old artifact was touched. Failed review-helper assumptions
were corrected and receipts retained. Original R4 evidence remains under
`build/m1-r4-20261109/` and the prior handoff is preserved in Git history.
