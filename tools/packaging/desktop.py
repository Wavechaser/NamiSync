"""Frozen desktop entry point; preserve the installed launcher's behavior."""

from namisync.interfaces.launcher import gui_main

if __name__ == "__main__":
    raise SystemExit(gui_main())
