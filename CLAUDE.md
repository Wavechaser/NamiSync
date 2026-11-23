@AGENTS.md

## Working Style

- Default to discussion, not changes. Treat questions, reviews, plan critiques,
  and thinking-out-loud as requests for assessment: report findings and stop.
  Make file edits or other side-effectful actions only when the user explicitly
  asks to edit/implement (or the request plainly implies it); that request
  includes committing per AGENTS, but push and merge need their own.
  When in doubt, propose and ask rather than apply.

## Claude Code Notes

- Use the PowerShell tool for all commands, not Bash/Git Bash/WSL, unless a
  task is genuinely impossible from PowerShell.
- The project virtual environment is at `.venv\`: run tests with
  `.venv\Scripts\python.exe -m pytest`, import contracts with
  `.venv\Scripts\lint-imports.exe`, and development tools with
  `.venv\Scripts\python.exe -m tools`.
