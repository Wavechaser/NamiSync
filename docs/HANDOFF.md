# Latest session — Settings and final layout, 2026-10-29

Completed the approved three-part batch on milestone1 from c64aec73:

- 24edbc6c: Filters caption/count, 32px Go/Follow insets, 1.2px card outlines,
  and Rebaseline menu width/leading-edge alignment. Minimum-width inspection
  also caught caption wrapping; intrinsic filter width and remaining-space
  Search sizing keep the label on one line without changing narrow stacking.
- 8c44f88a: Setup defaults, Appearance and About cards, explicit dirty-field
  saves and persisted automatic verification. Existing task drafts, Plan again,
  CLI behavior, theme persistence and disabled ADS remain intact.
- The accompanying About commit adds separate License and Open source
  acknowledgements links, selectable scrolling dialogs with fixed Close, and
  verified packaged notices. No new EULA or release certification.

Settings uses strict schema 2, as approved for this unreleased app. Old development
settings require manual reset; they are not migrated or automatically overwritten.
No default settings file was present in the checked local application-data path.

Verification: ordinary suite 6,274 passes/four skips, then 45 affected lifecycle
passes after updating the exact port expectation. Interface run 2,129 passes,
then 14 focused passes after token/fake-DOM corrections. Twelve import contracts
kept. The final filter correction passes 47 focused checks. All nine installed
checks have passing evidence: final combined run passed eight, and default Plan
passed unchanged on a single rerun after a Plan-again transition failure whose
cause is unestablished. Four gallery modes verify dialogs, menu geometry and
minimum-width layout; minimum screenshots were inspected. Independent source,
legal provenance, correction and evidence reviews passed.

Raw receipts, including failed harness attempts and corrections, are retained
under build/gui-settings-20261029/; verification.md explains dependency reuse.
The final native roots are namisync-settings29-final and
namisync-settings29-final-shell under the user's Local/Temp directory. No timeout
or foreground guard was weakened. No worktrees, recovery refs, push or PR.
Inventory recents, queued-input coordinator, M1-12, release and DOC-2 stay inactive.
