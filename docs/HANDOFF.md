# Latest session — GUI-WR1 WCG mitigation review

Reviewed `c637025` against `6c00ec7`: native Advanced Color detection and
subscriptions, appearance-v3 publication/receiver, shadow selectors and direct
test/helper consumers. Independent native/API review found no concrete defect;
no production or test changes were needed. Microsoft DisplayConfig definitions
match the ctypes layouts and flags. The documented topology-read failure path
keeps the prior value until another observation; no new retry policy was added.
The remaining appearance-v2 string in `test_host.py` intentionally exercises
non-readiness rejection and does not require migration.

Verification: 165 focused materials/frontend/token tests passed. The initial
sandboxed run had 149 passes and 16 temporary-directory permission errors;
the rerun with filesystem access passed all 165. Installed gallery: three
checks passed initially; the matrix failed
`minimum-folded-empty.no_horizontal_control_clipping` in dark mode. Its isolated
unchanged rerun passed. Raw reports also mark clipping false in the other three
dark minimum cases on the first attempt. The detector and Plan geometry are
unchanged by `c637025`; no WCG causal link or deterministic defect was established.
Do not erase that failed attempt or infer a full clean first run.

`build/wcg-review-20260924/` retains both gallery attempts and wheel/install
identity records; `review.md` records commands and review dispositions. Reports
show `advanced_color: true`, `hdr: true`, dark popup shadow `none`, and light
shadow retained. This session therefore does not isolate the WCG-only selector
or verify live ACM toggling. Prior WCG-only and LG → Dell → LG move evidence
remains in `build/gui-tuning/halo-10bit/transfer-w1-dataset/`; GUI-D8–D10 raw
composition evidence and reproducer remain in that parent directory.

The Windows composition bug remains DEFERRED and mitigated, not fixed.
Only review records changed; no public contract or consumer migration was
needed. No interface-department rerun was required for these documentation-only
edits. Preserve Mica/material, readiness and safety authority. Filter/Search,
new GUI changes, M1-7 study resumption, M1-9, push and PR remain excluded;
DOC-2 remains pending. If the minimum-layout failure recurs, use the preserved
reports to investigate that mechanism separately without weakening its gate.
