"""Ordinary SH-G-13 foundation evidence for the motion guardrails."""

from __future__ import annotations

import re
from pathlib import Path


ASSET_ROOT = (
    Path(__file__).parents[3]
    / "namisync"
    / "interfaces"
    / "web"
    / "assets"
)


def _rule_bodies(source: str, selector_fragment: str) -> tuple[str, ...]:
    return tuple(
        body
        for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", source)
        if selector_fragment in selectors
    )


def test_sh_g_13_motion_tokens_and_reduced_motion_override_are_owned() -> None:
    tokens = (ASSET_ROOT / "tokens.css").read_text(encoding="utf-8")
    components = (ASSET_ROOT / "components.css").read_text(encoding="utf-8")

    for name in (
        "--motion-duration-instant",
        "--motion-duration-fast",
        "--motion-duration-normal",
        "--motion-duration-slow",
        "--motion-duration-progress-cycle",
        "--motion-easing-standard",
        "--motion-easing-accelerate",
        "--motion-easing-decelerate",
    ):
        assert f"{name}:" in tokens

    assert "@media (prefers-reduced-motion: reduce)" in tokens
    assert "@media (prefers-reduced-motion: reduce)" in components
    reduced_tokens = tokens.split("@media (prefers-reduced-motion: reduce)", 1)[1]
    reduced = components.split("@media (prefers-reduced-motion: reduce)", 1)[1]
    assert "transition-duration: var(--motion-duration-instant);" in reduced
    assert "--motion-duration-progress-cycle: 0.01ms;" in reduced_tokens
    assert ".nami-dialog[open]" in reduced
    assert ".nami-progress--indeterminate .nami-progress__bar" in reduced
    assert reduced.count("animation: none;") >= 2


def test_sh_g_13_no_motion_is_bound_to_virtualized_row_lifecycle() -> None:
    components = (ASSET_ROOT / "components.css").read_text(encoding="utf-8")

    for row in (".nami-row", ".nami-list-row", ".nami-tree-row"):
        bodies = _rule_bodies(components, row)
        assert bodies, row
        for body in bodies:
            assert "animation" not in body
            assert "transition" not in body

    app = (ASSET_ROOT / "app.js").read_text(encoding="utf-8")
    assert not re.search(r"(?:animate|transition|animation)", app, re.IGNORECASE)
    assert not re.search(r"(?<![-\w])[0-9.]+m?s\b", components)
