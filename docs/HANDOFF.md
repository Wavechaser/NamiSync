# Latest session — executor consolidation complete

2026-09-30, `milestone1-adelbert`, result 7 candidate based on `6157226`.
The user explicitly authorized removing method-identity gates after the
compatibility explanation, moving saved work back to this branch, and probing
the direct-write threshold after consolidation review. Production direct-write
refactoring remains excluded.

## Completed

Directive `8b2b00e`, version recognition `d43f832`, path composition `6157226`.
Result 7 removes native identity gates/constants from admission, resolve,
leaf-volume observation and runtime delegation. Default fresh held attributes,
descendants, fallback admission and exact reviewed authority remain. Primitive
fault controls replace override-dispatch variants; 12 redundant parameter cases
were retired while preserving no-effect/source-swap checks. MKDIR's first
synthetic control changed only the later held-query seam; it was corrected to
also affect first full admission, without relaxing effect or recording assertions.

Final gates: 331 native/runtime and 5,699 ordinary tests passed; four existing
capability skips, 34 deselected. All 12 imports, unchanged 30x3 settlement oracle,
70-row/391-effect guard scan and fixed 67-group differential pass with zero
differences. Fresh independent reviewer found no blocking source/test issue.
Source native SHA256: 4156db81aa06cefe3d859e3017b7ec03dec0451ec15f31ab1eaa1b3b50354007.

Evidence root: build/executor-simplification-20260929/.
Logs: differential/result7-*. Candidate capture:
differential/runs/candidate-result7-dispatch-47f0f4e2d7da4a2b85df35211397dce1/.
Measurement prefix: measurements/result7-6157226f-20260930-170339-3d6968b5.
All 25 five-band executions/readbacks passed, stable dependencies, zero
reservations and owned cleanup. Medians 3.341 / 1.740 / 0.356 / 0.290 / 1.924 s;
every predecessor range overlaps. PERFORMANCE owns limits and full table.

## Immediate next work

Commit result 7 after final evidence/doc review. Then run the reviewed standalone
ceilings/direct_write_threshold.py helper: G-only 2 MiB pilot plus tail witness,
then six paired samples at 2/4/8/16/32 MiB on G/H/E/J/L from existing read-only F
source. Query alignment, flush, validate exact unbuffered readback and tail EOF,
retain source/dependency hashes, every sample and owned cleanup. M1_PLAN owns
criteria and bounded refinement; PERFORMANCE will record the device decisions.
This helper is experiment code only. No shipping threshold, unbuffered product
writer or pipeline change is authorized here. Existing five-band results did
not answer the threshold question; the user clarified this explicitly.

## Preservation

Recovery 259aee0 was restored as three uncommitted files on integration, never
merged/cherry-picked. Earlier recovery 9f01bfd9 was rebuilt into d43f832.
Retain both codex/wip-20260930-* recovery refs until final accounting, then remove
only those fully accounted task refs. No worktree created; unrelated b8baf42d
worktree and original F corpus remain protected.
Native tests use actual-user/default pytest temp. Old result6 temp-ACL cleanup
and development-log reconstruction receipts remain; final acceptance logs are
intact. Failed result7 migration controls are retained rather than overwritten.
