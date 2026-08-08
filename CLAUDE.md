@AGENTS.md

## Working Style

- Default to discussion, not changes. Treat questions, reviews, plan critiques,
  and thinking-out-loud as requests for assessment: report findings and stop.
  Make file edits, commits, or other side-effectful actions only when the user
  explicitly asks to edit/implement/commit (or the request plainly implies it).
  When in doubt, propose and ask rather than apply.

## Claude Code Notes

- This repo is Windows/PowerShell-only (see AGENTS.md "Windows Rules"). Use the
  PowerShell tool for all commands, not Bash/Git Bash/WSL, unless a task is
  genuinely impossible from PowerShell.
- The project virtual environment is at `.venv\`. Run tests with
  `.venv\Scripts\python.exe -m pytest`; check import boundaries with
  `.venv\Scripts\lint-imports.exe`; run the dev measurement harness with
  `.venv\Scripts\python.exe -m tools`.
- Start each session by reading `docs/HANDOFF.md` for the latest session
  state, then the relevant focused doc in `docs/` (see the README
  documentation index) before making changes.
- Current phase: M1 Stages 1-5.5 are implemented; Stage 6 (the headed
  WebView2 desktop) is next — see `docs/M1_SHELL.md`.
