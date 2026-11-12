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


def _rule_bodies(source: str, selector: str) -> tuple[str, ...]:
    return tuple(
        body
        for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", source)
        if selector in {item.strip() for item in selectors.split(",")}
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
    assert ".nami-dialog," in reduced
    assert ".nami-tree-row__disclosure," in reduced
    assert ".nami-progress--indeterminate .nami-progress__bar" in reduced
    assert reduced.count("animation: none;") >= 1


def test_sh_g_13_disclosure_and_dialog_use_css_motion_with_real_exit() -> None:
    components = (ASSET_ROOT / "components.css").read_text(encoding="utf-8")

    disclosure = _rule_bodies(components, ".nami-tree-row__disclosure")
    assert any(
        "transition: transform var(--motion-duration-fast)" in body
        for body in disclosure
    )
    assert "@starting-style" not in components
    assert "allow-discrete" not in components
    assert "overlay var(" not in components
    dialog = _rule_bodies(components, ".nami-dialog")
    assert dialog
    exit_rule = next(body for body in dialog if "opacity: 0;" in body)
    assert "opacity var(--motion-duration-normal)" in exit_rule
    assert "transform var(--motion-duration-normal)" in exit_rule
    opened = _rule_bodies(components, ".nami-dialog[open]")
    assert any("opacity: 1;" in body for body in opened)
    assert any("animation: nami-dialog-enter" in body for body in opened)
    closing = _rule_bodies(components, '.nami-dialog[data-closing="true"]')
    assert any("opacity: 0;" in body for body in closing)
    assert any("pointer-events: none;" in body for body in closing)
    closing_backdrop = _rule_bodies(
        components,
        '.nami-dialog[data-closing="true"]::backdrop',
    )
    assert any("opacity: 0;" in body for body in closing_backdrop)
    assert "@keyframes nami-dialog-enter" in components


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
