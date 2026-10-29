# Latest session — Settings links and footer, 2026-10-29

Completed the approved two-part follow-up on milestone1 from 156677de.

- c51ff241 places the Setup defaults advisory and actions in one footer row,
  advisory left and Save defaults right. The persistent Save button reserves
  ordinary clean/dirty height; saving and recovery behavior remain unchanged.
- The accompanying accent commit reads and validates all seven Windows colors:
  Accent, Light1-3 and Dark1-3. The native snapshot retains the full ramp;
  only semantic accentTextFill reaches the exact browser appearance receiver.
  HyperlinkButtons use Dark2 in Light and Light3 in Dark without underlines,
  keeping that text color through hover/press with neutral surface feedback.
  Existing accent-filled controls and forced colors are unchanged.

Verification: 225 focused cases, 2,138 interface cases and all 12 installed
cases passed (four gallery modes, two Settings window sizes, six appearance
scenarios). Both Settings receipts prove unchanged clean/dirty card height and
left/right alignment in a shared row. Native appearance evidence retains all
seven raw colors and exact selected text color. Independent source, provenance
and evidence reviews passed. The installed run needed no retry.

Evidence is under build/gui-settings-footer-20261029/; verification.md records
initial sandbox pip temporary-directory errors and the unsettled early probe,
then successful final gates. Official fallback source bytes and SHA256 are
retained. Native temp root: namisync-settings-footer-native under Local/Temp.
No worktrees, recovery refs, push or PR. Inventory recents, queued-input
coordinator, M1-12, release and DOC-2 remain inactive.
