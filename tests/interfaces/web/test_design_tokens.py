"""Ordinary SH-G-11 foundation evidence for shipped design tokens."""

from __future__ import annotations

import hashlib
import json
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
APP_LAYOUT = ASSET_ROOT / "app.css"
FLUENT_FIXTURE = Path(__file__).parents[2] / "assets" / "fluent_tokens"

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
FLUENT_SOURCE = {
    "package": "@fluentui/tokens@1.0.0-alpha.24",
    "commit": "32b42a5bf79c1836047dfc7fae07b1320731bce4",
    "files": {
        "package.json": "6f2af81d6cadd474dc8e4a30cd512ccf5f0aa3e6221985ea6b28ce0e866c9991",
        "lightColor.ts": "0882854a85d8433e530bb5e40adff342e321361c64cd295255127c06fea55a48",
        "darkColor.ts": "ed15b83e605999aa196ba04ac9d03557cf943a3ba7ce3a3979650992505c2bea",
        "borderRadius.ts": "156bf14d20515100a28356daa7c07c9766a1108a0e4efef86ae171ee8c505f34",
        "curves.ts": "e1681eb819b86380e9ef6d52b9821b5fce2382d8d0070a33eef6429c4e0e2a6c",
        "durations.ts": "34ef2eb5444fa422632f5ec1c2033f947d953f96c569e23e0ad8f78a6921f6bf",
        "fonts.ts": "ba5c662e2ec0e216f98ca28433ab439ecb4036d30d2311aa3f7d9c362ddcb2e9",
        "spacings.ts": "63a64eba054236a88c80293f3128f89e988f22da90e7b4637a53ad92a89f9c2d",
        "shadows.ts": "0f76754193af8f255401fe69f0288dd96767f4e35e7663bd0f84bf8af879d61a",
    },
}
FLUENT_LIGHT_VALUES = {
    "colorNeutralBackground1": "#ffffff",
    "colorNeutralBackground1Hover": "#f5f5f5",
    "colorNeutralBackground1Pressed": "#e0e0e0",
    "colorNeutralBackground1Selected": "#ebebeb",
    "colorNeutralBackground2": "#fafafa",
    "colorSubtleBackground": "transparent",
    "colorSubtleBackgroundLightAlphaHover": "rgba(255,255,255,0.7)",
    "colorSubtleBackgroundLightAlphaPressed": "rgba(255,255,255,0.5)",
    "colorNeutralForeground1": "#242424",
    "colorNeutralForeground2": "#424242",
    "colorNeutralForegroundDisabled": "#bdbdbd",
    "colorNeutralStrokeAccessible": "#616161",
    "colorNeutralStrokeAccessibleHover": "#575757",
    "colorNeutralStrokeAccessiblePressed": "#4d4d4d",
    "colorNeutralStroke2": "#e0e0e0",
    "colorNeutralBackgroundDisabled": "#f0f0f0",
    "colorBackgroundOverlay": "rgba(0,0,0,0.4)",
    "colorNeutralShadowAmbient": "rgba(0,0,0,0.12)",
    "colorNeutralShadowKey": "rgba(0,0,0,0.14)",
    "colorStrokeFocus2": "#000000",
}
FLUENT_DARK_VALUES = {
    "colorNeutralBackground1": "#292929",
    "colorNeutralBackground1Hover": "#3d3d3d",
    "colorNeutralBackground1Pressed": "#1f1f1f",
    "colorNeutralBackground1Selected": "#383838",
    "colorNeutralBackground2": "#1f1f1f",
    "colorSubtleBackground": "transparent",
    "colorSubtleBackgroundLightAlphaHover": "rgba(36,36,36,0.8)",
    "colorSubtleBackgroundLightAlphaPressed": "rgba(36,36,36,0.5)",
    "colorNeutralForeground1": "#ffffff",
    "colorNeutralForeground2": "#d6d6d6",
    "colorNeutralForegroundDisabled": "#5c5c5c",
    "colorNeutralStrokeAccessible": "#adadad",
    "colorNeutralStrokeAccessibleHover": "#bdbdbd",
    "colorNeutralStrokeAccessiblePressed": "#b3b3b3",
    "colorNeutralStrokeSubtle": "#0a0a0a",
    "colorNeutralBackgroundDisabled": "#141414",
    "colorBackgroundOverlay": "rgba(0,0,0,0.5)",
    "colorNeutralShadowAmbient": "rgba(0,0,0,0.24)",
    "colorNeutralShadowKey": "rgba(0,0,0,0.28)",
    "colorStrokeFocus2": "#ffffff",
}
FLUENT_LIGHT_ALIASES = {
    "--color-neutral-canvas": "colorNeutralBackground1Hover",
    "--color-neutral-surface": "colorNeutralBackground1",
    "--color-neutral-surface-subtle": "colorNeutralBackground2",
    "--color-neutral-surface-hover": "colorNeutralBackground1Hover",
    "--color-neutral-surface-pressed": "colorNeutralBackground1Pressed",
    "--color-neutral-surface-selected": "colorNeutralBackground1Selected",
    "--color-neutral-subtle-background": "colorSubtleBackground",
    "--color-neutral-subtle-hover": "colorSubtleBackgroundLightAlphaHover",
    "--color-neutral-subtle-pressed": "colorSubtleBackgroundLightAlphaPressed",
    "--color-neutral-foreground": "colorNeutralForeground1",
    "--color-neutral-foreground-secondary": "colorNeutralForeground2",
    "--color-neutral-foreground-disabled": "colorNeutralForegroundDisabled",
    "--color-neutral-border": "colorNeutralStrokeAccessible",
    "--color-neutral-border-hover": "colorNeutralStrokeAccessibleHover",
    "--color-neutral-border-pressed": "colorNeutralStrokeAccessiblePressed",
    "--color-neutral-border-subtle": "colorNeutralStroke2",
    "--color-neutral-disabled-background": "colorNeutralBackgroundDisabled",
    "--color-backdrop": "colorBackgroundOverlay",
    "--color-shadow-ambient": "colorNeutralShadowAmbient",
    "--color-shadow-key": "colorNeutralShadowKey",
    "--color-focus-ring": "colorStrokeFocus2",
}
FLUENT_DARK_ALIASES = {
    **FLUENT_LIGHT_ALIASES,
    "--color-neutral-canvas": "colorNeutralBackground2",
    "--color-neutral-border-subtle": "colorNeutralStrokeSubtle",
}
FLUENT_SCALE_VALUES = {
    "fontSizeBase200": "12px",
    "fontSizeBase300": "14px",
    "fontSizeBase400": "16px",
    "fontSizeBase500": "20px",
    "fontSizeHero700": "28px",
    "lineHeightBase200": "16px",
    "lineHeightBase300": "20px",
    "lineHeightBase400": "22px",
    "lineHeightBase500": "28px",
    "lineHeightHero700": "36px",
    "fontWeightRegular": "400",
    "fontWeightMedium": "500",
    "fontWeightSemibold": "600",
    "spacingHorizontalNone": "0",
    "spacingHorizontalXXS": "2px",
    "spacingHorizontalXS": "4px",
    "spacingHorizontalS": "8px",
    "spacingHorizontalM": "12px",
    "spacingHorizontalL": "16px",
    "spacingHorizontalXXL": "24px",
    "spacingHorizontalXXXL": "32px",
    "borderRadiusNone": "0",
    "borderRadiusMedium": "4px",
    "borderRadiusXLarge": "8px",
    "borderRadius2XLarge": "12px",
    "borderRadiusCircular": "10000px",
    "durationFaster": "100ms",
    "durationNormal": "200ms",
    "durationSlow": "300ms",
    "curveEasyEase": "cubic-bezier(0.33,0,0.67,1)",
    "curveAccelerateMax": "cubic-bezier(0.9,0.1,1,0.2)",
    "curveDecelerateMax": "cubic-bezier(0.1,0.9,0.2,1)",
}
FLUENT_SCALE_ALIASES = {
    "--font-size-caption": "fontSizeBase200",
    "--font-size-body": "fontSizeBase300",
    "--font-size-body-large": "fontSizeBase400",
    "--font-size-title": "fontSizeBase500",
    "--font-size-heading": "fontSizeHero700",
    "--line-height-caption": "lineHeightBase200",
    "--line-height-body": "lineHeightBase300",
    "--line-height-body-large": "lineHeightBase400",
    "--line-height-title": "lineHeightBase500",
    "--line-height-heading": "lineHeightHero700",
    "--font-weight-regular": "fontWeightRegular",
    "--font-weight-medium": "fontWeightMedium",
    "--font-weight-semibold": "fontWeightSemibold",
    "--space-0": "spacingHorizontalNone",
    "--space-1": "spacingHorizontalXXS",
    "--space-2": "spacingHorizontalXS",
    "--space-3": "spacingHorizontalS",
    "--space-4": "spacingHorizontalM",
    "--space-5": "spacingHorizontalL",
    "--space-6": "spacingHorizontalXXL",
    "--space-7": "spacingHorizontalXXXL",
    "--radius-none": "borderRadiusNone",
    "--radius-small": "borderRadiusMedium",
    "--radius-medium": "borderRadiusXLarge",
    "--radius-large": "borderRadius2XLarge",
    "--radius-circular": "borderRadiusCircular",
    "--motion-duration-fast": "durationFaster",
    "--motion-duration-normal": "durationNormal",
    "--motion-duration-slow": "durationSlow",
    "--motion-easing-standard": "curveEasyEase",
    "--motion-easing-accelerate": "curveAccelerateMax",
    "--motion-easing-decelerate": "curveDecelerateMax",
}
FLUENT_SHADOW_VALUES = {
    "shadow2": (
        "0 0 2px var(--color-shadow-ambient), "
        "0 1px 2px var(--color-shadow-key)"
    ),
    "shadow4": (
        "0 0 2px var(--color-shadow-ambient), "
        "0 2px 4px var(--color-shadow-key)"
    ),
    "shadow8": (
        "0 0 2px var(--color-shadow-ambient), "
        "0 4px 8px var(--color-shadow-key)"
    ),
    "shadow16": (
        "0 0 2px var(--color-shadow-ambient), "
        "0 8px 16px var(--color-shadow-key)"
    ),
}
FLUENT_SHADOW_ALIASES = {
    "--elevation-2": "shadow2",
    "--elevation-4": "shadow4",
    "--elevation-8": "shadow8",
    "--elevation-16": "shadow16",
}
WINDOWS_ACCENT_FALLBACK = {
    "--color-accent": "#0078D4",
    "--color-accent-hover": "#0091F8",
    "--color-accent-pressed": "#0067C0",
    "--color-accent-foreground": "#FFFFFF",
    "--color-accent-hover-foreground": "#000000",
    "--color-accent-pressed-foreground": "#FFFFFF",
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
    assert "--palette-yellow-light" not in source
    assert "--palette-purple-light" not in source
    assert "color-mix(" not in source
    assert not re.search(r"\b(?:hsl|hsla|hwb|lab|lch|oklab|oklch)\(", source)

    actual_literals = {
        value.replace(" ", "").casefold()
        for value in (
            *HEX_LITERAL.findall(source),
            *re.findall(r"rgba\([^)]*\)", source, re.IGNORECASE),
        )
    }
    expected_literals = {
        value.replace(" ", "").casefold()
        for value in (
            *AUTHORED_PALETTE.values(),
            *FLUENT_LIGHT_VALUES.values(),
            *FLUENT_DARK_VALUES.values(),
            *WINDOWS_ACCENT_FALLBACK.values(),
        )
        if value != "transparent"
    }
    assert actual_literals == expected_literals


def test_sh_g_11_fluent_table_matches_pinned_source_transcription() -> None:
    source = TOKENS.read_text(encoding="utf-8")
    light = _variables(_block(source, ":root "))
    dark = light | _variables(_block(source, ':root[data-theme="dark"]'))
    automatic_dark = light | _variables(
        _block(source, ':root:not([data-theme="light"])')
    )

    expected_light = {
        local: FLUENT_LIGHT_VALUES[upstream]
        for local, upstream in FLUENT_LIGHT_ALIASES.items()
    }
    expected_dark = {
        local: FLUENT_DARK_VALUES[upstream]
        for local, upstream in FLUENT_DARK_ALIASES.items()
    }
    expected_scales = {
        local: FLUENT_SCALE_VALUES[upstream]
        for local, upstream in FLUENT_SCALE_ALIASES.items()
    }
    expected_shadows = {
        local: FLUENT_SHADOW_VALUES[upstream]
        for local, upstream in FLUENT_SHADOW_ALIASES.items()
    }

    assert expected_light.items() <= light.items()
    assert expected_dark.items() <= dark.items()
    assert expected_dark.items() <= automatic_dark.items()
    assert expected_scales.items() <= light.items()
    assert expected_shadows.items() <= light.items()
    assert WINDOWS_ACCENT_FALLBACK.items() <= light.items()
    assert str(FLUENT_SOURCE["package"]).removeprefix(
        "@fluentui/tokens@"
    ) in source
    for name, sha256 in FLUENT_SOURCE["files"].items():
        assert f"{name} SHA-256: {sha256}" in source
    assert (
        "https://github.com/microsoft/fluentui/tree/"
        f"{FLUENT_SOURCE['commit']}/packages/tokens"
    ) in source

    assert {
        path.name for path in FLUENT_FIXTURE.iterdir() if path.is_file()
    } == {*FLUENT_SOURCE["files"], "LICENSE"}
    for name, sha256 in FLUENT_SOURCE["files"].items():
        assert hashlib.sha256((FLUENT_FIXTURE / name).read_bytes()).hexdigest() == sha256
    package = json.loads(
        (FLUENT_FIXTURE / "package.json").read_text(encoding="utf-8")
    )
    assert f"{package['name']}@{package['version']}" == FLUENT_SOURCE["package"]
    license_text = (FLUENT_FIXTURE / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in license_text
    assert "Copyright (c) Microsoft Corporation" in license_text

    for theme in (light, dark):
        assert len(
            {
                _resolve("--color-neutral-surface", theme),
                _resolve("--color-neutral-surface-hover", theme),
                _resolve("--color-neutral-surface-pressed", theme),
                _resolve("--color-neutral-surface-selected", theme),
            }
        ) == 4
        assert len(
            {
                _resolve("--color-neutral-subtle-background", theme),
                _resolve("--color-neutral-subtle-hover", theme),
                _resolve("--color-neutral-subtle-pressed", theme),
            }
        ) == 3

    assert len(
        {
            _resolve(name, light)
            for name in WINDOWS_ACCENT_FALLBACK
            if "foreground" not in name
        }
    ) == 3
    for state in ("", "-hover", "-pressed"):
        assert _contrast(
            _resolve(f"--color-accent{state}", light),
            _resolve(f"--color-accent{state}-foreground", light),
        ) >= 4.5


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
            assert _contrast(foreground, background) >= 4.5, prefix
            assert _contrast(indicator, background) >= 3.0, prefix

        focus = _resolve("--color-focus-ring", theme)
        assert _contrast(focus, _resolve("--color-neutral-canvas", theme)) >= 3.0


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
    assert "--color-neutral-surface-selected: Highlight;" in forced
    assert "--color-neutral-border: ButtonBorder;" in forced
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
    layout = APP_LAYOUT.read_text(encoding="utf-8")
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
        "nami-task-card",
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
    assert """.nami-row:not([aria-disabled="true"]):hover,
.nami-list-row:not([aria-disabled="true"]):hover,
.nami-tree-row:not([aria-disabled="true"]):hover {""" in source
    assert """.nami-row:not([aria-disabled="true"]):active,
.nami-list-row:not([aria-disabled="true"]):active,
.nami-tree-row:not([aria-disabled="true"]):active {""" in source
    assert ".nami-row:hover," not in source
    assert ".nami-row:active," not in source
    forced = _block(source, "@media (forced-colors: active)")
    declaration = "color: var(--color-accent-foreground);"
    declaration_at = forced.index(declaration)
    rule_open = forced.rfind("{", 0, declaration_at)
    selector_start = forced.rfind("}", 0, rule_open) + 1
    paired_interactions = {
        selector.strip()
        for selector in forced[selector_start:rule_open].split(",")
    }
    assert paired_interactions == {
        ".nami-button:not(:disabled):hover",
        ".nami-button:not(:disabled):active",
        ".nami-checkbox:not(:disabled):hover",
        ".nami-toggle__control:not(:disabled):hover",
        ".nami-chip:not(:disabled):hover",
        ".nami-chip:not(:disabled):active",
        ".nami-icon-button:not(:disabled):hover",
        ".nami-icon-button:not(:disabled):active",
        '.nami-row:not([aria-disabled="true"]):hover',
        '.nami-row:not([aria-disabled="true"]):active',
        '.nami-list-row:not([aria-disabled="true"]):hover',
        '.nami-list-row:not([aria-disabled="true"]):active',
        '.nami-tree-row:not([aria-disabled="true"]):hover',
        '.nami-tree-row:not([aria-disabled="true"]):active',
        '.nami-task-card:not([aria-disabled="true"]):hover',
        '.nami-task-card:not([aria-disabled="true"]):active',
        '.nami-card:not([aria-disabled="true"]):active',
        '.nami-dialog:not([aria-disabled="true"]):active',
        ".nami-menu__item:not(:disabled):hover",
        ".nami-menu__item:not(:disabled):active",
        ".nami-segmented__item:not(:disabled):hover",
        ".nami-segmented__item:not(:disabled):active",
    }
    selected_forced_hover = _block(
        forced,
        '.nami-task-card[aria-selected="true"]:'
        'not([aria-disabled="true"]):hover,',
    )
    assert "outline: 1px solid var(--color-accent-foreground);" in (
        selected_forced_hover
    )
    assert "outline-offset: -1px;" in selected_forced_hover
    selected_forced_pressed = _block(
        forced,
        '.nami-task-card[aria-selected="true"]:'
        'not([aria-disabled="true"]):active,',
    )
    assert "outline: 2px solid var(--color-accent-foreground);" in (
        selected_forced_pressed
    )
    assert "outline-offset: -2px;" in selected_forced_pressed
    toggle_thumb = _block(
        forced,
        ".nami-toggle__control:not(:disabled):hover::after",
    )
    assert "background: var(--color-accent-foreground);" in toggle_thumb
    for selector in (
        ".nami-input:not(:disabled):hover",
        ".nami-select:not(:disabled):hover",
        '.nami-card:not([aria-disabled="true"]):hover',
        '.nami-dialog:not([aria-disabled="true"]):hover',
        '.nami-progress:not([aria-disabled="true"]):hover',
        '.nami-progress:not([aria-disabled="true"]):active',
    ):
        assert selector in forced
    row_focus = _block(source, ".nami-row:focus-visible")
    assert "box-shadow: 0 0 0 2px var(--color-focus-ring);" in row_focus
    assert "outline: none;" in row_focus

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
    task_rail = re.search(r"(?ms)^\.nami-task-rail\s*\{([^}]*)\}", layout)
    assert task_rail is not None
    assert "background: var(--color-neutral-subtle-background);" in (
        task_rail.group(1)
    )
    task_card = _block(source, ".nami-task-card ")
    assert "background: var(--color-neutral-subtle-background);" in task_card
    assert "border: 1px solid var(--color-neutral-subtle-background);" in task_card
    selected_task = _block(
        source,
        '.nami-task-card[aria-selected="true"],',
    )
    assert "background: var(--color-neutral-surface-selected);" in selected_task
    assert "border-color: var(--color-neutral-border);" in selected_task
    assert "box-shadow: var(--elevation-2);" in selected_task
    assert '.nami-task-card[aria-current="true"]' in source
    assert ".nami-task-card:not([aria-disabled=\"true\"]):hover" in source
    assert ".nami-task-card:not([aria-disabled=\"true\"]):active" in source
    assert (
        '.nami-task-card[aria-selected="true"]:'
        'not([aria-disabled="true"]):hover'
    ) in source
    assert (
        '.nami-task-card[aria-current="true"]:'
        'not([aria-disabled="true"]):active'
    ) in source
    selected_hover = _block(
        source,
        '.nami-task-card[aria-selected="true"]:'
        'not([aria-disabled="true"]):hover,',
    )
    assert "background: var(--color-neutral-surface-hover);" in selected_hover
    selected_pressed = _block(
        source,
        '.nami-task-card[aria-selected="true"]:'
        'not([aria-disabled="true"]):active,',
    )
    assert "background: var(--color-neutral-surface-pressed);" in selected_pressed
    disabled_task = _block(source, '.nami-task-card[aria-disabled="true"] ')
    assert "color: var(--color-neutral-foreground-disabled);" in disabled_task
    assert "cursor: default;" in disabled_task
    selected_focus = _block(
        source,
        '.nami-task-card[aria-selected="true"]:focus-visible,',
    )
    assert "box-shadow: var(--elevation-2);" in selected_focus
    assert "outline: 2px solid var(--color-focus-ring);" in selected_focus
    assert "outline-offset: 2px;" in selected_focus
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
    active_tree = _block(forced, '.nami-tree-row[data-active="true"] ')
    assert "color: var(--color-accent-foreground);" in active_tree
    active_disclosure = _block(
        forced,
        '.nami-tree-row[data-active="true"] .nami-tree-row__disclosure ',
    )
    assert "border-color: var(--color-accent-foreground);" in active_disclosure
    assert re.search(
        r"\.nami-icon\s*\{\s*forced-color-adjust:\s*none;\s*\}",
        forced,
    )


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
