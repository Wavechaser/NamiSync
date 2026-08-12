"""Ordinary SH-G-11 foundation evidence for shipped design tokens."""

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
TOKENS = ASSET_ROOT / "tokens.css"
COMPONENTS = ASSET_ROOT / "components.css"

AUTHORED_PALETTE = {
    "--palette-red-main": "#EE6666",
    "--palette-red-dark": "#551111",
    "--palette-red-light": "#FFAACC",
    "--palette-green-main": "#33DD99",
    "--palette-green-dark": "#004422",
    "--palette-green-light": "#99EEDD",
    "--palette-blue-main": "#33AAEE",
    "--palette-blue-dark": "#002255",
    "--palette-blue-light": "#99CCFF",
    "--palette-yellow-main": "#FFDD44",
    "--palette-yellow-dark": "#553300",
    "--palette-purple-main": "#BB88EE",
    "--palette-purple-dark": "#331155",
}
STATUSES = (
    "complete",
    "success",
    "failure",
    "error",
    "warning",
    "degraded",
    "incomplete",
    "active",
    "paused",
    "canceled",
    "mismatch",
    "blocked",
    "deferred",
    "neutral",
    "noop",
)
OPERATIONS = (
    "copy",
    "update",
    "move",
    "move_update",
    "recase",
    "mkdir",
    "trash",
    "delete",
    "noop",
)
ROLES = ("foreground", "background", "indicator")
HEX_LITERAL = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
RAW_COLOR = re.compile(
    r"#[0-9A-Fa-f]{3,8}\b|"
    r"\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color|device-cmyk|"
    r"light-dark|color-mix)\s*\(|"
    r"(?<![-\w])(?:transparent|Canvas|CanvasText|ButtonFace|ButtonText|"
    r"ButtonBorder|GrayText|Highlight|HighlightText|AccentColor|"
    r"AccentColorText)(?![-\w])",
    re.IGNORECASE,
)
COLOR_DECLARATION = re.compile(
    r"(?is)(?:^|[;{])\s*(?:color|background(?:-color)?|"
    r"border(?:-(?:block|inline)(?:-(?:start|end))?)?(?:-color)?|"
    r"border-(?:top|right|bottom|left)(?:-color)?|outline(?:-color)?|fill|"
    r"stroke|box-shadow|text-shadow|caret-color|accent-color)\s*:\s*([^;}]+)"
)
CUSTOM_PROPERTY = re.compile(
    r"(?is)(?:^|[;{])\s*(--[a-zA-Z0-9_-]+)\s*:\s*([^;}]+)"
)
ALLOWED_SURFACE_CUSTOM_VALUE = re.compile(
    r'(?is)^(?:var\(--[a-zA-Z0-9_-]+\)|url\("\./icons/[a-z0-9_]+\.svg"\))$'
)
ALLOWED_COLOR_VALUE = re.compile(
    r"(?is)^(?:"
    r"(?:(?:-?[0-9.]+(?:px|rem|em|%)?|solid|dashed|dotted|double|inset|"
    r"outset|groove|ridge)\s+)*(?:var\(--[a-zA-Z0-9_-]+\)|currentColor)"
    r"|0"
    r"|none|inherit|initial|unset|revert"
    r")$"
)
VARIABLE = re.compile(r"(--[a-zA-Z0-9_-]+)\s*:\s*([^;]+);")


def _block(source: str, selector: str) -> str:
    start = source.index(selector) + len(selector)
    opening = source.index("{", start)
    depth = 1
    for index in range(opening + 1, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    raise AssertionError(f"unterminated CSS block for {selector}")


def _variables(source: str) -> dict[str, str]:
    return dict(VARIABLE.findall(source))


def _resolve(name: str, values: dict[str, str], seen: frozenset[str] = frozenset()) -> str:
    assert name not in seen, f"cyclic token alias: {name}"
    value = values[name].strip()
    match = re.fullmatch(r"var\((--[a-zA-Z0-9_-]+)\)", value)
    if match is None:
        return value
    return _resolve(match.group(1), values, seen | {name})


def _luminance(value: str) -> float:
    assert re.fullmatch(r"#[0-9A-Fa-f]{6}", value), value
    channels = [int(value[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    lighter, darker = sorted(
        (_luminance(first), _luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def _has_raw_color(source: str) -> bool:
    if RAW_COLOR.search(source) is not None or any(
        ALLOWED_COLOR_VALUE.fullmatch(match.group(1).strip()) is None
        for match in COLOR_DECLARATION.finditer(source)
    ):
        return True
    return any(
        ALLOWED_SURFACE_CUSTOM_VALUE.fullmatch(value.strip()) is None
        for _name, value in CUSTOM_PROPERTY.findall(source)
    )


def test_sh_g_11_tokens_preserve_exact_authored_palette_without_missing_lights() -> None:
    source = TOKENS.read_text(encoding="utf-8")
    palette = {
        name: value.strip()
        for name, value in VARIABLE.findall(source)
        if name.startswith("--palette-")
    }

    assert palette == AUTHORED_PALETTE
    assert HEX_LITERAL.findall(source) == list(AUTHORED_PALETTE.values())
    assert "--palette-yellow-light" not in source
    assert "--palette-purple-light" not in source
    assert "color-mix(" not in source
    assert not re.search(r"\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch)\(", source)
def test_sh_g_11_all_status_and_operation_aliases_are_complete() -> None:
    values = _variables(TOKENS.read_text(encoding="utf-8"))

    expected = {
        *(f"--status-{status}-{role}" for status in STATUSES for role in ROLES),
        *(
            f"--operation-{operation}-{role}"
            for operation in OPERATIONS
            for role in ROLES
        ),
    }

    assert expected <= values.keys()
    assert not {
        name
        for name in values
        if name.startswith(("--status-", "--operation-"))
        and name not in expected
    }


def test_sh_g_11_semantic_text_and_indicator_pairs_meet_contrast_floors() -> None:
    source = TOKENS.read_text(encoding="utf-8")
    light = _variables(_block(source, ":root "))
    dark = light | _variables(_block(source, ':root[data-theme="dark"]'))

    for theme in (light, dark):
        for prefix in (
            *(f"status-{status}" for status in STATUSES),
            *(f"operation-{operation}" for operation in OPERATIONS),
        ):
            foreground = _resolve(f"--{prefix}-foreground", theme)
            background = _resolve(f"--{prefix}-background", theme)
            indicator = _resolve(f"--{prefix}-indicator", theme)
            if prefix in {"status-neutral", "status-noop", "operation-noop"}:
                assert {foreground, background, indicator} <= {
                    "ButtonFace",
                    "ButtonText",
                    "CanvasText",
                }
                continue
            assert _contrast(foreground, background) >= 4.5, prefix
            assert _contrast(indicator, background) >= 3.0, prefix

        assert _resolve("--color-neutral-surface", theme) == "Canvas"
        assert _resolve("--color-neutral-canvas", theme) == "Canvas"
        assert _resolve("--color-neutral-foreground", theme) == "CanvasText"
        assert _resolve("--color-neutral-foreground-secondary", theme) == "ButtonText"
        assert _resolve("--color-neutral-border", theme) == "ButtonBorder"
        focus = _resolve("--color-focus-ring", theme)
        assert focus in AUTHORED_PALETTE.values()
        assert _resolve("--color-accent", theme) == "AccentColor"
        assert _resolve("--color-accent-foreground", theme) == "AccentColorText"


def test_sh_g_11_forced_colors_replaces_semantics_with_system_colors() -> None:
    source = TOKENS.read_text(encoding="utf-8")
    forced = _block(source, "@media (forced-colors: active)")

    assert "--palette-" not in forced
    assert ':root[data-theme="dark"]' in forced
    assert ':root:not([data-theme="light"])' in forced
    assert {
        "Canvas",
        "CanvasText",
        "ButtonBorder",
        "ButtonText",
        "GrayText",
        "Highlight",
        "HighlightText",
    } <= set(re.findall(r"\b[A-Z][A-Za-z]+\b", forced))
    for family in (
        "positive",
        "negative",
        "warning",
        "active",
        "paused",
        "mismatch",
        "blocked",
        "neutral",
    ):
        for role in ROLES:
            assert f"--semantic-{family}-{role}:" in forced


def test_sh_g_11_only_tokens_owns_raw_colors_and_palette_consumption() -> None:
    shipped = [
        path
        for path in ASSET_ROOT.rglob("*")
        if path.is_file() and path.suffix in {".css", ".html", ".js", ".svg"}
    ]
    literal_owners = set()
    for path in shipped:
        source = path.read_text(encoding="utf-8")
        if _has_raw_color(source):
            literal_owners.add(path.relative_to(ASSET_ROOT).as_posix())
    palette_consumers = {
        path.relative_to(ASSET_ROOT).as_posix()
        for path in shipped
        if "--palette-" in path.read_text(encoding="utf-8")
    }

    assert literal_owners == {"tokens.css"}
    assert palette_consumers == {"tokens.css"}


def test_sh_g_11_raw_color_scanner_catches_literal_and_mixed_css_escapes() -> None:
    for mutation in (
        ".x { color: red; }",
        ".x { border: 1px solid red; }",
        ".x { border-inline-start: 1px solid white; }",
        ".x { background: linear-gradient(var(--safe), red); }",
        ".x { color: color(display-p3 1 0 0); }",
        ".x { color: light-dark(red, blue); }",
        ".x { fill: device-cmyk(0 1 1 0); }",
        ".x { --surface-color: red; color: var(--surface-color); }",
    ):
        assert _has_raw_color(mutation), mutation
    for allowed in (
        ".x { color: var(--color-neutral-foreground); }",
        ".x { border: 1px solid var(--color-neutral-border); }",
        ".x { background-color: currentColor; }",
        ".x { box-shadow: 0 0 0 2px var(--color-focus-ring); }",
    ):
        assert not _has_raw_color(allowed), allowed


def test_sh_g_11_components_cover_controls_states_and_non_color_cues() -> None:
    source = COMPONENTS.read_text(encoding="utf-8")
    controls = {
        "nami-button",
        "nami-select",
        "nami-checkbox",
        "nami-progress",
        "nami-input",
        "nami-toggle",
        "nami-chip",
        "nami-list-row",
        "nami-tree-row",
        "nami-card",
        "nami-dialog",
        "nami-menu",
        "nami-segmented",
        "nami-badge",
        "nami-banner",
        "nami-status-pill",
    }
    for control in controls:
        assert f".{control}" in source

    for state in (":hover", ":active", ":disabled", ":focus-visible"):
        assert state in source
    assert '[aria-checked="mixed"]' in source
    assert ":indeterminate" in source
    assert '[aria-selected="true"]' in source
    assert '[aria-disabled="true"]' in source

    for status in STATUSES:
        assert f'[data-status="{status}"]' in source
    for operation in OPERATIONS:
        assert f'[data-operation="{operation}"]' in source
    for family, keys in (("status", STATUSES), ("operation", OPERATIONS)):
        for key in keys:
            declarations = _variables(
                _block(source, f'[data-{family}="{key}"]')
            )
            assert declarations == {
                f"--nami-state-{role}": f"var(--{family}-{key}-{role})"
                for role in ROLES
            }
    assert ".nami-state-cue" in source
    cue_owners: set[tuple[str, str]] = set()
    for rule in re.finditer(r"([^{}]+)\{([^{}]*)\}", source):
        if re.search(r"(?:^|;)\s*content\s*:", rule.group(2)) is None:
            continue
        cue_owners.update(
            (kind, key)
            for kind, key in re.findall(
                r'\[data-(status|operation)="([a-z_]+)"\]\s+'
                r"\.nami-state-cue::before",
                rule.group(1),
            )
        )
    assert cue_owners == {
        *(("status", status) for status in STATUSES),
        *(("operation", operation) for operation in OPERATIONS),
    }

    assert HEX_LITERAL.search(source) is None
    assert "--palette-" not in source

    forced = _block(source, "@media (forced-colors: active)")
    assert "outline: 2px solid var(--color-focus-ring);" in forced
    assert "outline-offset: 2px;" in forced
    assert re.search(
        r"\.nami-icon\s*\{\s*forced-color-adjust:\s*none;\s*\}",
        forced,
    )
    for selector in (
        ".nami-input:hover",
        ".nami-select:hover",
        ".nami-card:hover",
        ".nami-dialog:hover",
        ".nami-progress:hover",
        ".nami-progress:active",
    ):
        assert selector in forced


def test_sh_g_11_shipped_page_loads_tokens_components_then_layout() -> None:
    source = (ASSET_ROOT / "index.html").read_text(encoding="utf-8")
    links = re.findall(r'<link rel="stylesheet" href="([^"]+)">', source)

    assert links == ["/tokens.css", "/components.css", "/app.css"]
    layout = (ASSET_ROOT / "app.css").read_text(encoding="utf-8")
    assert HEX_LITERAL.search(layout) is None
    assert "--palette-" not in layout


def test_sh_g_11_icon_foundation_uses_shared_sizes_and_fixed_local_masks() -> None:
    tokens = _variables(TOKENS.read_text(encoding="utf-8"))
    components = COMPONENTS.read_text(encoding="utf-8")

    assert {
        "--icon-size-sm": "16px",
        "--icon-size-md": "20px",
        "--icon-size-lg": "24px",
    }.items() <= tokens.items()
    assert "background-color: currentColor;" in components
    assert "mask-image: var(--nami-icon-mask);" in components
    assert "-webkit-mask-image: var(--nami-icon-mask);" in components
    assert components.count("--nami-icon-mask: url(") == 4
    assert "http:" not in components
    assert "https:" not in components
