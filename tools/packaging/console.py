"""Frozen console entry point; preserve the installed launcher's behavior."""

from namisync.interfaces.launcher import main

if __name__ == "__main__":
    raise SystemExit(main())
