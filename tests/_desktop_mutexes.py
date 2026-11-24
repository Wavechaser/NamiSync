"""Desktop instance mutex names that development and headed tests must agree on.

The release and development names come from the host's identity constructors,
and the development launcher's plan is asserted against them in
``test_tools_gui``; the gallery names are owned by ``tools/desktop/gui.ps1`` and
asserted there too.
"""

from __future__ import annotations

from namisync.interfaces.web.host import (
    development_instance_identity,
    production_instance_identity,
)


GALLERY_MODES = ("light", "dark", "forced", "reduced")


def gallery_mutex(mode: str) -> str:
    return rf"Local\NamiSync.Development.Gallery.{mode}"


def watched_desktop_mutexes() -> tuple[str, ...]:
    """Every desktop mutex whose holder may legitimately change a real data root."""

    return (
        production_instance_identity().mutex_name,
        development_instance_identity().mutex_name,
        *(gallery_mutex(mode) for mode in GALLERY_MODES),
    )
