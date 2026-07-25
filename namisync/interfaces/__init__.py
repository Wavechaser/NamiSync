"""User-facing adapters for NamiSync workflows."""


def main(*args, **kwargs):
    """Invoke the CLI without importing an adapter during package initialization."""

    from namisync.interfaces.cli import main as cli_main

    return cli_main(*args, **kwargs)


__all__ = ["main"]
