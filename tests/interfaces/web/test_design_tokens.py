"""Ordinary SH-G-11 foundation evidence for shipped design tokens."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from _frontend_test_support import ICON_FILES, ICON_MASK_FILES


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
    "--palette-yellow-main": "#FFAA22",
    "--palette-yellow-dark": "#553300",
    "--palette-yellow-light": "#FFDD44",
    "--palette-purple-main": "#8844CC",
    "--palette-purple-dark": "#331155",
    "--palette-purple-light": "#BB88EE",
}
AUTHORED_FILTER_INTERACTION_VALUES = {
    "light": {
        "blueHover": "#33AAEEE6",
        "bluePressed": "#33AAEECC",
        "yellowHover": "#FFAA22E6",
        "yellowPressed": "#FFAA22CC",
        "purpleHover": "#8844CCE6",
        "purplePressed": "#8844CCCC",
        "redHover": "#EE6666E6",
        "redPressed": "#EE6666CC",
        "neutralHover": "#424242E6",
        "neutralPressed": "#424242CC",
    },
    "dark": {
        "neutralHover": "#D6D6D6E6",
        "neutralPressed": "#D6D6D6CC",
    },
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
    "colorStrokeFocus1": "#ffffff",
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
    "colorStrokeFocus1": "#000000",
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
    "--color-focus-inner": "colorStrokeFocus1",
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
    "light": {
        "--color-accent-fill": "#0067C0",
        "--color-accent-fill-hover": "#0067C0E6",
        "--color-accent-fill-pressed": "#0067C0CC",
        "--color-accent-fill-foreground": "#FFFFFF",
    },
    "dark": {
        "--color-accent-fill": "#4CC2FF",
        "--color-accent-fill-hover": "#4CC2FFE6",
        "--color-accent-fill-pressed": "#4CC2FFCC",
        "--color-accent-fill-foreground": "#000000",
    },
}
AUTHORED_CONTROL_VALUES = {
    "light": {
        "--color-control-fill": "#fbfbfb",
        "--color-control-fill-hover": "#f6f6f6",
        "--color-control-fill-pressed": "#f5f5f5",
        "--color-control-border": "#e5e5e5",
        "--color-control-strong-stroke": "#00000072",
        "--color-textbox-border": "rgba(0,0,0,0.06)",
        "--color-textbox-underline": "rgba(0,0,0,0.45)",
    },
    "dark": {
        "--color-control-fill": "#383838",
        "--color-control-fill-hover": "#323232",
        "--color-control-fill-pressed": "#272727",
        "--color-control-border": "#353535",
        "--color-control-strong-stroke": "#FFFFFF8B",
        "--color-textbox-border": "rgba(255,255,255,0.07)",
        "--color-textbox-underline": "rgba(255,255,255,0.55)",
    },
}
AUTHORED_SELECTION_VALUES = {
    "light": {
        "--color-selection-highlight": "rgba(0,0,0,0.04)",
        "--color-selection-highlight-pressed": "rgba(0,0,0,0.02)",
    },
    "dark": {
        "--color-selection-highlight": "rgba(255,255,255,0.08)",
        "--color-selection-highlight-pressed": "rgba(255,255,255,0.04)",
    },
}
AUTHORED_CARD_VALUES = {
    "light": {
        "--color-card-background": "rgba(255,255,255,0.7)",
        "--color-card-background-secondary": "rgba(246,246,246,0.5)",
        "--color-card-background-tertiary": "#ffffff",
        "--color-card-border-solid": "#ebebeb",
        "--color-card-border": "rgba(0,0,0,0.06)",
    },
    "dark": {
        "--color-card-background": "rgba(255,255,255,0.05)",
        "--color-card-background-secondary": "rgba(255,255,255,0.03)",
        "--color-card-background-tertiary": "rgba(255,255,255,0.07)",
        "--color-card-border-solid": "#1c1c1c",
        "--color-card-border": "rgba(0,0,0,0.10)",
    },
}
AUTHORED_FLYOUT_VALUES = {
    "light": {
        "--color-flyout-background-solid": "#ffffff",
        "--color-flyout-border-solid": "#ebebeb",
        "--color-flyout-border": "rgba(0,0,0,0.06)",
        "--color-control-elevation-border-start": "rgba(0,0,0,0.04)",
        "--color-control-elevation-border-end": "rgba(0,0,0,0.12)",
        "--color-control-elevation-border-flat": "rgba(0,0,0,0.10)",
    },
    "dark": {
        "--color-flyout-background-solid": "#292929",
        "--color-flyout-border-solid": "#1c1c1c",
        "--color-flyout-border": "rgba(0,0,0,0.20)",
        "--color-control-elevation-border-start": "rgba(0,0,0,0.08)",
        "--color-control-elevation-border-end": "rgba(0,0,0,0.26)",
        "--color-control-elevation-border-flat": "rgba(0,0,0,0.20)",
    },
}
INTENTS = (
    "copy",
    "mkdir",
    "move",
    "recase",
    "update",
    "move_update",
    "trash",
    "delete",
    "noop",
    "error",
    "unsupported",
    "blocked",
)
LIFECYCLES = (
    "new",
    "planned",
    "queued",
    "executing",
    "verifying",
    "pausing",
    "canceling",
    "completed",
    "partial",
    "degraded",
    "incomplete",
    "paused",
    "interrupted",
    "canceled",
    "canceled_after_publish",
    "canceled_after_mutation",
    "refused",
    "errored",
    "failed",
)
INTEGRITY_STATES = (
    "verified",
    "baselined",
    "unverified",
    "modified",
    "reappeared",
    "unsupported",
    "canceled",
    "missing",
    "mismatched",
    "error",
)
SEMANTIC_TOKENS = {
    "--color-main-fill-foreground",
    "--intent-additive-foreground",
    "--intent-relocating-foreground",
    "--intent-replacing-foreground",
    "--intent-removing-foreground",
    "--intent-neutral-foreground",
    "--intent-permanent-background",
    "--intent-permanent-foreground",
    "--intent-exception-background",
    "--intent-exception-foreground",
    "--lifecycle-neutral-foreground",
    "--lifecycle-active-foreground",
    "--lifecycle-completed-foreground",
    "--lifecycle-attention-foreground",
    "--lifecycle-canceled-background",
    "--lifecycle-canceled-foreground",
    "--lifecycle-attention-background",
    "--lifecycle-attention-fill-foreground",
    "--lifecycle-failure-background",
    "--lifecycle-failure-foreground",
    "--integrity-positive-foreground",
    "--integrity-neutral-foreground",
    "--integrity-attention-foreground",
    "--integrity-attention-background",
    "--integrity-attention-fill-foreground",
    "--integrity-failure-background",
    "--integrity-failure-foreground",
    "--progress-active-fill",
    "--progress-paused-fill",
    "--progress-canceled-fill",
    "--progress-track-background",
}
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


def _theme_variables(
    source: str,
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    light = _variables(_block(source, ":root "))
    dark = light | _variables(_block(source, ':root[data-theme="dark"]'))
    automatic_dark = light | _variables(
        _block(
            _block(source, "@media (prefers-color-scheme: dark)"),
            ':root:not([data-theme="light"])',
        )
    )
    return light, dark, automatic_dark

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
    def allowed_color_value(value: str) -> bool:
        return all(
            ALLOWED_COLOR_VALUE.fullmatch(layer.strip()) is not None
            for layer in value.split(",")
        )

    if RAW_COLOR.search(source) is not None or any(
        not allowed_color_value(match.group(1))
        for match in COLOR_DECLARATION.finditer(source)
    ):
        return True
    return any(
        ALLOWED_SURFACE_CUSTOM_VALUE.fullmatch(value.strip()) is None
        for _name, value in CUSTOM_PROPERTY.findall(source)
    )


def test_sh_g_11_tokens_route_authored_lights_only_to_new_semantic_roles() -> None:
    source = TOKENS.read_text(encoding="utf-8")
    palette = {
        name: value.strip()
        for name, value in VARIABLE.findall(source)
        if name.startswith("--palette-")
    }

    assert palette == AUTHORED_PALETTE
    assert len(palette) == 15
    assert source.count("var(--palette-yellow-light)") == 3
    assert source.count("var(--palette-purple-light)") == 2
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
            *WINDOWS_ACCENT_FALLBACK["light"].values(),
            *WINDOWS_ACCENT_FALLBACK["dark"].values(),
            *AUTHORED_CONTROL_VALUES["light"].values(),
            *AUTHORED_CONTROL_VALUES["dark"].values(),
            *AUTHORED_SELECTION_VALUES["light"].values(),
            *AUTHORED_SELECTION_VALUES["dark"].values(),
            *AUTHORED_CARD_VALUES["light"].values(),
            *AUTHORED_CARD_VALUES["dark"].values(),
            *AUTHORED_FLYOUT_VALUES["light"].values(),
            *AUTHORED_FLYOUT_VALUES["dark"].values(),
            *AUTHORED_FILTER_INTERACTION_VALUES["light"].values(),
            *AUTHORED_FILTER_INTERACTION_VALUES["dark"].values(),
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
    assert WINDOWS_ACCENT_FALLBACK["light"].items() <= light.items()
    assert WINDOWS_ACCENT_FALLBACK["dark"].items() <= dark.items()
    assert WINDOWS_ACCENT_FALLBACK["dark"].items() <= automatic_dark.items()
    assert AUTHORED_CONTROL_VALUES["light"].items() <= light.items()
    assert AUTHORED_CONTROL_VALUES["dark"].items() <= dark.items()
    assert AUTHORED_CONTROL_VALUES["dark"].items() <= automatic_dark.items()
    assert AUTHORED_SELECTION_VALUES["light"].items() <= light.items()
    assert AUTHORED_SELECTION_VALUES["dark"].items() <= dark.items()
    assert AUTHORED_SELECTION_VALUES["dark"].items() <= automatic_dark.items()
    assert AUTHORED_CARD_VALUES["light"].items() <= light.items()
    assert AUTHORED_CARD_VALUES["dark"].items() <= dark.items()
    assert AUTHORED_CARD_VALUES["dark"].items() <= automatic_dark.items()
    assert AUTHORED_FLYOUT_VALUES["light"].items() <= light.items()
    assert AUTHORED_FLYOUT_VALUES["dark"].items() <= dark.items()
    assert AUTHORED_FLYOUT_VALUES["dark"].items() <= automatic_dark.items()
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

    for theme, expected in (
        (light, WINDOWS_ACCENT_FALLBACK["light"]),
        (dark, WINDOWS_ACCENT_FALLBACK["dark"]),
        (automatic_dark, WINDOWS_ACCENT_FALLBACK["dark"]),
    ):
        assert expected.items() <= theme.items()
        assert _contrast(
            _resolve("--color-accent-fill", theme),
            _resolve("--color-accent-fill-foreground", theme),
        ) >= 4.5
        assert _resolve("--color-accent-fill-hover", theme) == (
            f'{_resolve("--color-accent-fill", theme)}E6'
        )
        assert _resolve("--color-accent-fill-pressed", theme) == (
            f'{_resolve("--color-accent-fill", theme)}CC'
        )


def test_sh_g_11_channel_semantic_aliases_are_complete_and_disjoint() -> None:
    values = _variables(TOKENS.read_text(encoding="utf-8"))

    assert SEMANTIC_TOKENS <= values.keys()
    assert {
        name
        for name in values
        if name.startswith(("--intent-", "--lifecycle-", "--integrity-"))
    } == SEMANTIC_TOKENS - {
        "--color-main-fill-foreground",
        "--progress-active-fill",
        "--progress-paused-fill",
        "--progress-canceled-fill",
        "--progress-track-background",
    }
    assert not {
        name
        for name in values
        if name.startswith(("--status-", "--operation-", "--file-status-"))
    }


def test_sh_g_11_channel_mappings_use_theme_secondary_badges() -> None:
    source = TOKENS.read_text(encoding="utf-8")
    light, dark, automatic_dark = _theme_variables(source)

    shared_aliases = {
        "--intent-additive-foreground": "var(--palette-blue-main)",
        "--intent-replacing-foreground": "var(--palette-yellow-main)",
        "--intent-removing-foreground": "var(--palette-red-main)",
        "--intent-neutral-foreground": "var(--color-neutral-foreground-secondary)",
        "--lifecycle-neutral-foreground": "var(--color-neutral-foreground-secondary)",
        "--lifecycle-active-foreground": "var(--color-accent-fill)",
        "--lifecycle-completed-foreground": "var(--palette-green-main)",
        "--lifecycle-attention-foreground": "var(--palette-yellow-main)",
        "--lifecycle-canceled-background": "var(--color-neutral-surface-selected)",
        "--lifecycle-canceled-foreground": "var(--color-neutral-foreground-secondary)",
        "--integrity-positive-foreground": "var(--palette-green-main)",
        "--integrity-neutral-foreground": "var(--color-neutral-foreground-secondary)",
        "--integrity-attention-foreground": "var(--palette-yellow-main)",
        "--progress-active-fill": "var(--color-accent-fill)",
        "--progress-paused-fill": "var(--palette-yellow-main)",
        "--progress-canceled-fill": "var(--color-neutral-foreground-secondary)",
        "--progress-track-background": "var(--color-neutral-surface-pressed)",
    }
    for theme in (light, dark, automatic_dark):
        assert shared_aliases.items() <= theme.items()

    light_badges = {
        "--intent-relocating-foreground": "var(--palette-purple-main)",
        "--intent-permanent-background": "var(--palette-red-light)",
        "--intent-permanent-foreground": "var(--palette-red-dark)",
        "--intent-exception-background": "var(--palette-yellow-light)",
        "--intent-exception-foreground": "var(--palette-yellow-dark)",
        "--lifecycle-attention-background": "var(--palette-yellow-light)",
        "--lifecycle-attention-fill-foreground": "var(--palette-yellow-dark)",
        "--lifecycle-failure-background": "var(--palette-red-light)",
        "--lifecycle-failure-foreground": "var(--palette-red-dark)",
        "--integrity-attention-background": "var(--palette-yellow-light)",
        "--integrity-attention-fill-foreground": "var(--palette-yellow-dark)",
        "--integrity-failure-background": "var(--palette-red-light)",
        "--integrity-failure-foreground": "var(--palette-red-dark)",
    }
    dark_badges = {
        "--intent-relocating-foreground": "var(--palette-purple-light)",
        "--intent-permanent-background": "var(--palette-red-dark)",
        "--intent-permanent-foreground": "var(--palette-red-main)",
        "--intent-exception-background": "var(--palette-yellow-dark)",
        "--intent-exception-foreground": "var(--palette-yellow-main)",
        "--lifecycle-attention-background": "var(--palette-yellow-dark)",
        "--lifecycle-attention-fill-foreground": "var(--palette-yellow-main)",
        "--lifecycle-failure-background": "var(--palette-red-dark)",
        "--lifecycle-failure-foreground": "var(--palette-red-main)",
        "--integrity-attention-background": "var(--palette-yellow-dark)",
        "--integrity-attention-fill-foreground": "var(--palette-yellow-main)",
        "--integrity-failure-background": "var(--palette-red-dark)",
        "--integrity-failure-foreground": "var(--palette-red-main)",
    }
    assert light_badges.items() <= light.items()
    assert dark_badges.items() <= dark.items()
    assert dark_badges.items() <= automatic_dark.items()

    assert light["--color-main-fill-foreground"] == (
        "var(--color-neutral-foreground)"
    )
    assert dark["--color-main-fill-foreground"] == (
        "var(--color-neutral-surface)"
    )
    assert automatic_dark["--color-main-fill-foreground"] == (
        "var(--color-neutral-surface)"
    )
    fill_pairs = (
        ("--intent-permanent-foreground", "--intent-permanent-background"),
        ("--intent-exception-foreground", "--intent-exception-background"),
        (
            "--lifecycle-attention-fill-foreground",
            "--lifecycle-attention-background",
        ),
        ("--lifecycle-failure-foreground", "--lifecycle-failure-background"),
        (
            "--integrity-attention-fill-foreground",
            "--integrity-attention-background",
        ),
        ("--integrity-failure-foreground", "--integrity-failure-background"),
    )
    for theme in (light, dark, automatic_dark):
        ratios = [
            _contrast(_resolve(foreground, theme), _resolve(background, theme))
            for foreground, background in fill_pairs
        ]
        assert all(ratio >= 4.5 for ratio in ratios)
        assert _contrast(
            _resolve("--lifecycle-canceled-foreground", theme),
            _resolve("--lifecycle-canceled-background", theme),
        ) >= 4.5

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
        "ButtonFace",
        "GrayText",
        "Highlight",
        "HighlightText",
    } <= set(re.findall(r"\b[A-Z][A-Za-z]+\b", forced))
    assert "--color-neutral-surface-selected: Highlight;" in forced
    assert "--color-accent-fill: Highlight !important;" in forced
    assert "--color-accent-fill-hover: Highlight !important;" in forced
    assert "--color-accent-fill-pressed: Highlight !important;" in forced
    assert "--color-accent-fill-foreground: HighlightText !important;" in forced
    assert "--color-selection-highlight: Highlight;" in forced
    assert "--color-selection-highlight-pressed: Highlight;" in forced
    assert "--color-neutral-border: ButtonBorder;" in forced
    assert "--color-control-strong-stroke: ButtonBorder;" in forced
    for name in (
        "filter-active-foreground",
        "filter-copy-background",
        "filter-update-background",
        "filter-move-background",
        "filter-purple-active-foreground",
        "filter-move-update-background",
        "filter-recase-background",
        "filter-mkdir-background",
        "filter-trash-background",
        "filter-delete-background",
        "filter-delete-active-foreground",
        "filter-blue-background-hover",
        "filter-blue-background-pressed",
        "filter-yellow-background-hover",
        "filter-yellow-background-pressed",
        "filter-purple-background-hover",
        "filter-purple-background-pressed",
        "filter-red-background-hover",
        "filter-red-background-pressed",
        "filter-noop-background",
        "filter-noop-background-hover",
        "filter-noop-background-pressed",
        "filter-noop-foreground",
        "color-main-fill-foreground",
        "progress-active-fill",
        "progress-paused-fill",
        "progress-canceled-fill",
        "progress-track-background",
    ):
        assert f"--{name}:" in forced
    forced_values = _variables(forced)
    expected = {
        "--color-main-fill-foreground": "HighlightText",
        "--intent-additive-foreground": "CanvasText",
        "--intent-relocating-foreground": "CanvasText",
        "--intent-replacing-foreground": "CanvasText",
        "--intent-removing-foreground": "CanvasText",
        "--intent-neutral-foreground": "CanvasText",
        "--intent-permanent-background": "Highlight",
        "--intent-permanent-foreground": "HighlightText",
        "--intent-exception-background": "Highlight",
        "--intent-exception-foreground": "HighlightText",
        "--lifecycle-neutral-foreground": "CanvasText",
        "--lifecycle-active-foreground": "CanvasText",
        "--lifecycle-completed-foreground": "CanvasText",
        "--lifecycle-attention-foreground": "CanvasText",
        "--lifecycle-canceled-background": "Highlight",
        "--lifecycle-canceled-foreground": "HighlightText",
        "--lifecycle-attention-background": "Highlight",
        "--lifecycle-attention-fill-foreground": "HighlightText",
        "--lifecycle-failure-background": "Highlight",
        "--lifecycle-failure-foreground": "HighlightText",
        "--integrity-positive-foreground": "CanvasText",
        "--integrity-neutral-foreground": "CanvasText",
        "--integrity-attention-foreground": "CanvasText",
        "--integrity-attention-background": "Highlight",
        "--integrity-attention-fill-foreground": "HighlightText",
        "--integrity-failure-background": "Highlight",
        "--integrity-failure-foreground": "HighlightText",
        "--progress-active-fill": "Highlight",
        "--progress-paused-fill": "Highlight",
        "--progress-canceled-fill": "Highlight",
        "--progress-track-background": "Canvas",
    }
    assert {name: forced_values[name] for name in SEMANTIC_TOKENS} == expected


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

    # Pinned native SVG fills only contribute alpha, never application color.
    assert literal_owners - {"tokens.css"} <= {
        f"icons/{filename}" for filename in ICON_FILES
    }
    assert "mask-mode: alpha;" in COMPONENTS.read_text(encoding="utf-8")
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
        ".x { box-shadow: 0 0 0 1px var(--color-focus-inner), "
        "0 0 0 3px var(--color-focus-ring); }",
    ):
        assert not _has_raw_color(allowed), allowed


def test_sh_g_11_channel_selectors_keep_hue_and_form_semantics_scoped() -> None:
    source = COMPONENTS.read_text(encoding="utf-8")

    additive = _block(
        source,
        '[data-intent]:is([data-intent="copy"], [data-intent="mkdir"]) ',
    )
    relocating = _block(
        source,
        '[data-intent]:is([data-intent="move"], [data-intent="recase"]) ',
    )
    replacing = _block(
        source,
        '[data-intent]:is([data-intent="update"], '
        '[data-intent="move_update"]) ',
    )
    assert _variables(additive) == {
        "--nami-state-foreground": "var(--intent-additive-foreground)"
    }
    assert _variables(relocating) == {
        "--nami-state-foreground": "var(--intent-relocating-foreground)"
    }
    assert _variables(replacing) == {
        "--nami-state-foreground": "var(--intent-replacing-foreground)"
    }
    assert _variables(_block(source, '[data-intent="trash"] ')) == {
        "--nami-state-foreground": "var(--intent-removing-foreground)"
    }
    assert _variables(_block(source, '[data-intent="delete"] ')) == {
        "--nami-state-background": "var(--intent-permanent-background)",
        "--nami-state-foreground": "var(--intent-permanent-foreground)",
    }
    intent_exception = _variables(_block(source, "[data-intent]:is(\n"))
    assert intent_exception == {
        "--nami-state-background": "var(--intent-exception-background)",
        "--nami-state-foreground": "var(--intent-exception-foreground)",
    }

    lifecycle_active = _variables(_block(source, "[data-lifecycle]:is(\n"))
    assert lifecycle_active == {
        "--nami-state-foreground": "var(--lifecycle-active-foreground)"
    }
    assert _variables(_block(source, '[data-lifecycle="completed"] ')) == {
        "--nami-state-foreground": "var(--lifecycle-completed-foreground)"
    }
    lifecycle_attention_at = source.index(
        '[data-lifecycle="partial"]',
        source.index('[data-lifecycle="completed"]'),
    )
    lifecycle_attention = _variables(
        _block(source[lifecycle_attention_at:], '[data-lifecycle="partial"]')
    )
    assert lifecycle_attention == {
        "--nami-state-foreground": "var(--lifecycle-attention-foreground)"
    }
    assert _variables(_block(source, '[data-lifecycle="canceled"] ')) == {
        "--nami-state-background": "var(--lifecycle-canceled-background)",
        "--nami-state-foreground": "var(--lifecycle-canceled-foreground)",
    }
    attention_fill_at = source.index('[data-lifecycle="canceled_after_publish"]')
    attention_fill = _variables(
        _block(
            source[attention_fill_at:],
            '[data-lifecycle="canceled_after_publish"]',
        )
    )
    assert attention_fill == {
        "--nami-state-background": "var(--lifecycle-attention-background)",
        "--nami-state-foreground": (
            "var(--lifecycle-attention-fill-foreground)"
        ),
    }
    failure_at = source.index('[data-lifecycle="errored"]')
    failure = _variables(
        _block(source[failure_at:], '[data-lifecycle="errored"]')
    )
    assert failure == {
        "--nami-state-background": "var(--lifecycle-failure-background)",
        "--nami-state-foreground": "var(--lifecycle-failure-foreground)",
    }

    integrity_positive = _variables(_block(source, "[data-integrity]:is(\n"))
    assert integrity_positive == {
        "--nami-state-foreground": "var(--integrity-positive-foreground)"
    }
    assert _variables(_block(source, '[data-integrity="modified"] ')) == {
        "--nami-state-foreground": "var(--integrity-attention-foreground)"
    }
    integrity_attention_at = source.index('[data-integrity="reappeared"]')
    integrity_attention = _variables(
        _block(source[integrity_attention_at:], '[data-integrity="reappeared"]')
    )
    assert integrity_attention == {
        "--nami-state-background": "var(--integrity-attention-background)",
        "--nami-state-foreground": (
            "var(--integrity-attention-fill-foreground)"
        ),
    }
    integrity_failure_at = source.index('[data-integrity="missing"]')
    integrity_failure = _variables(
        _block(source[integrity_failure_at:], '[data-integrity="missing"]')
    )
    assert integrity_failure == {
        "--nami-state-background": "var(--integrity-failure-background)",
        "--nami-state-foreground": "var(--integrity-failure-foreground)",
    }


def test_sh_g_11_components_cover_controls_states_and_non_color_cues() -> None:
    source = COMPONENTS.read_text(encoding="utf-8")
    layout = APP_LAYOUT.read_text(encoding="utf-8")
    controls = {
        "nami-button",
        "nami-combobox",
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
    declaration = "color: var(--color-accent-fill-foreground);"
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
        '.nami-dialog:not([aria-disabled="true"]):active',
        ".nami-menu__item:not(:disabled):hover",
        ".nami-menu__item:not(:disabled):active",
        ".nami-segmented__item:not(:disabled):hover",
        ".nami-segmented__item:not(:disabled):active",
    }
    selected_interactions = _block(
        forced,
        '.nami-task-card[aria-selected="true"]:'
        'not([aria-disabled="true"]):hover,',
    )
    assert "background: var(--color-accent-fill);" in selected_interactions
    assert "color: var(--color-accent-fill-foreground);" in selected_interactions
    assert "outline" not in selected_interactions
    selected_focus = _block(
        forced,
        '.nami-task-card[aria-selected="true"]:focus-visible,',
    )
    assert "box-shadow: none;" in selected_focus
    assert "outline: 2px solid var(--color-focus-ring);" in selected_focus
    selected_forced = _block(
        forced,
        '.nami-task-card[aria-selected="true"]:'
        'not([aria-disabled="true"]),',
    )
    selected_start = forced.index(
        '.nami-task-card[aria-selected="true"]:'
        'not([aria-disabled="true"]),'
    )
    selected_open = forced.index("{", selected_start)
    assert {
        selector.strip()
        for selector in forced[selected_start:selected_open].split(",")
    } == {
        '.nami-task-card[aria-selected="true"]:'
        'not([aria-disabled="true"])',
        '.nami-task-card[aria-current="true"]:'
        'not([aria-disabled="true"])',
        '.nami-task-card[aria-current="page"]:'
        'not([aria-disabled="true"])',
    }
    assert (
        "background: var(--color-neutral-surface-selected);"
        in selected_forced
    )
    assert "box-shadow: none;" in selected_forced
    assert "color: var(--color-accent-fill-foreground);" in selected_forced
    assert "forced-color-adjust: none;" in selected_forced
    toggle_thumb = _block(
        forced,
        ".nami-toggle__control:not(:disabled):hover::after",
    )
    assert "background: var(--color-accent-fill-foreground);" in toggle_thumb
    for selector in (
        ".nami-input:not(:disabled):hover",
        ".nami-select:not(:disabled):hover",
        '.nami-dialog:not([aria-disabled="true"]):hover',
    ):
        assert selector in forced
    assert '.nami-progress:not([aria-disabled="true"]):hover' not in forced
    assert '.nami-progress:not([aria-disabled="true"]):active' not in forced
    row_focus = _block(source, ".nami-row:focus-visible")
    assert "0 0 0 1px var(--color-focus-inner)," in row_focus
    assert "0 0 0 3px var(--color-focus-ring);" in row_focus
    assert "outline: none;" in row_focus

    for channel, keys in (
        ("intent", INTENTS),
        ("lifecycle", LIFECYCLES),
        ("integrity", INTEGRITY_STATES),
    ):
        for key in keys:
            assert f'[data-{channel}="{key}"]' in source
    assert "[data-status" not in source
    for channel, foreground in (
        ("intent", "--intent-neutral-foreground"),
        ("lifecycle", "--lifecycle-neutral-foreground"),
        ("integrity", "--integrity-neutral-foreground"),
    ):
        declarations = _variables(_block(source, f"[data-{channel}] "))
        assert declarations == {
            "--nami-state-foreground": f"var({foreground})",
            "--nami-state-background": "var(--color-semantic-transparent)",
            "--nami-state-indicator": "var(--nami-state-foreground)",
        }
    state_labels = _block(source, ".nami-badge,\n.nami-status-pill ")
    assert "background: var(--color-semantic-transparent);" in state_labels
    assert "border: 0;" in state_labels
    assert "padding: 0;" in state_labels
    filled_label = _block(
        source,
        ':is(.nami-badge, .nami-status-pill)[data-form="fill"] ',
    )
    assert "background: var(--nami-state-background);" in filled_label
    assert "block-size: 18px;" in filled_label
    assert "line-height: var(--font-size-caption);" in filled_label
    assert "padding-block-end: 1px;" in filled_label
    assert "padding-inline: var(--space-3);" in filled_label
    file_label = _block(layout, ".nami-file-state-label ")
    assert "background: var(--color-semantic-transparent);" in file_label
    assert "border-radius: var(--radius-small);" in file_label
    assert "color: var(--nami-state-foreground" in file_label
    file_fill_selector = """.nami-plan-row__intent:is(
  [data-intent="delete"],
  [data-intent="error"],
  [data-intent="unsupported"],
  [data-intent="blocked"]
) .nami-file-state-label,
.nami-integrity-row__presence:is(
  [data-integrity="reappeared"],
  [data-integrity="unsupported"],
  [data-integrity="missing"],
  [data-integrity="mismatched"],
  [data-integrity="error"]
) .nami-file-state-label {"""
    assert file_fill_selector in layout
    file_fills = _block(
        layout,
        file_fill_selector.removesuffix("{"),
    )
    assert "background: var(--nami-state-background);" in file_fills
    assert "block-size: 18px;" in file_fills
    assert "line-height: var(--font-size-caption);" in file_fills
    assert "padding-block-end: 1px;" in file_fills
    assert "margin-inline-start: -4px;" in file_fills
    assert "padding-inline: var(--space-2);" in file_fills
    inline_progress = _block(source, ".nami-progress--inline ")
    assert "block-size: var(--space-2);" in inline_progress
    assert "inline-size: 100%;" in inline_progress
    assert ".nami-state-cue" in source
    task_rail = re.search(r"(?ms)^\.nami-task-rail\s*\{([^}]*)\}", layout)
    assert task_rail is not None
    assert "background: var(--color-neutral-subtle-background);" in (
        task_rail.group(1)
    )
    card = _block(source, ".nami-card ")
    assert "background: var(--color-card-background-solid);" in card
    assert "background: var(--color-card-background);" in card
    assert "border: 1px solid var(--color-card-border-solid);" in card
    assert "border-color: var(--color-card-border);" in card
    assert "background-clip: padding-box;" in card
    assert "box-shadow: none;" in card
    assert ".nami-card:hover" not in source
    assert ".nami-card:active" not in source
    assert """.nami-menu,
.nami-dialog,
.nami-combobox__popup {""" in source
    elevated = _block(source, ".nami-menu,")
    assert "border: 1px solid var(--color-flyout-border-solid);" in elevated
    assert "border-color: var(--color-flyout-border);" in elevated
    combobox_trigger = _block(source, ".nami-combobox__trigger ")
    assert "var(--color-control-elevation-border-start)" in combobox_trigger
    assert "var(--color-control-elevation-border-end)" in combobox_trigger
    assert "linear-gradient(" in combobox_trigger
    combobox_open = _block(
        source,
        '.nami-combobox__trigger:not(:disabled):active,',
    )
    assert "var(--color-control-elevation-border-flat)" in combobox_open
    assert """.nami-combobox__trigger:not(:disabled):active,
.nami-combobox__trigger[aria-expanded="true"] {""" in source
    popup = next(
        block
        for block in re.findall(
            r"(?ms)^\.nami-combobox__popup\s*\{(.*?)^\}",
            source,
        )
        if "box-shadow" in block
    )
    assert "background: var(--color-flyout-background-solid);" in popup
    assert "box-shadow: var(--elevation-16);" in popup
    assert "border-radius: var(--radius-medium);" in popup
    assert "@supports (backdrop-filter:" not in source
    option = next(
        block
        for block in re.findall(
            r"(?ms)^\.nami-combobox__option\s*\{(.*?)^\}",
            source,
        )
        if "min-block-size" in block
    )
    assert "background: var(--color-neutral-subtle-background);" in option
    selected_option = _block(
        source,
        '.nami-combobox__option[aria-selected="true"] ',
    )
    assert "background: var(--color-selection-highlight);" in selected_option
    option_hover = _block(
        source,
        ".nami-combobox__option:is(:hover, [data-active]) ",
    )
    option_pressed = _block(source, ".nami-combobox__option:active ")
    assert "background: var(--color-selection-highlight);" in option_hover
    assert "background: var(--color-selection-highlight-pressed);" in option_pressed
    option_marker = _block(
        source,
        '.nami-combobox__option[aria-selected="true"] '
        ".nami-combobox__selection ",
    )
    assert "background: var(--color-accent-fill);" in option_marker
    selected_option_hover = _block(
        source,
        '.nami-combobox__option[aria-selected="true"]:'
        "is(:hover, [data-active]) ",
    )
    selected_option_pressed = _block(
        source,
        '.nami-combobox__option[aria-selected="true"]:active ',
    )
    assert (
        "background: var(--color-selection-highlight);"
        in selected_option_hover
    )
    assert (
        "background: var(--color-selection-highlight-pressed);"
        in selected_option_pressed
    )
    hdr_fallback = _block(source, "@media (dynamic-range: high)")
    assert ':root[data-theme="dark"] .nami-dialog:not(:focus-visible)' in hdr_fallback
    assert ':root[data-theme="dark"] .nami-menu' in hdr_fallback
    assert ':root[data-theme="dark"] .nami-combobox__popup' in hdr_fallback
    assert "box-shadow: none;" in hdr_fallback
    assert ".nami-combobox__trigger:focus-visible" in source
    assert ".nami-combobox__trigger:focus:not(:focus-visible)" not in source
    assert not re.search(r"\.nami-combobox__trigger:focus\s*[,\{]", source)
    task_card = _block(source, ".nami-task-card ")
    assert "background: var(--color-neutral-subtle-background);" in task_card
    assert "border: 0;" in task_card
    assert "box-shadow: none;" in task_card
    selected_task = _block(
        source,
        '.nami-task-card[aria-selected="true"],',
    )
    assert "background: var(--color-selection-highlight);" in selected_task
    assert "border" not in selected_task
    assert "box-shadow" not in selected_task
    assert re.search(r"(?:^|;)\s*color\s*:", selected_task) is None
    assert '.nami-task-card[aria-current="true"]' in source
    for paired_current_selectors in (
        '.nami-task-card[aria-current="true"],\n'
        '.nami-task-card[aria-current="page"] {',
        '.nami-task-card[aria-current="true"]::before,\n'
        '.nami-task-card[aria-current="page"]::before {',
        '.nami-task-card[aria-current="true"]:'
        'not([aria-disabled="true"]):hover,\n'
        '.nami-task-card[aria-current="page"]:'
        'not([aria-disabled="true"]):hover {',
        '.nami-task-card[aria-current="true"]:'
        'not([aria-disabled="true"]):active,\n'
        '.nami-task-card[aria-current="page"]:'
        'not([aria-disabled="true"]):active {',
        '.nami-task-card[aria-current="true"]:focus-visible,\n'
        '.nami-task-card[aria-current="page"]:focus-visible {',
        '  .nami-task-card[aria-current="true"]:'
        'not([aria-disabled="true"]),\n'
        '  .nami-task-card[aria-current="page"]:'
        'not([aria-disabled="true"]) {',
        '  .nami-task-card[aria-current="true"]::before,\n'
        '  .nami-task-card[aria-current="page"]::before {',
        '  .nami-task-card[aria-current="true"]:'
        'not([aria-disabled="true"]):active,\n'
        '  .nami-task-card[aria-current="page"]:'
        'not([aria-disabled="true"]):hover,\n'
        '  .nami-task-card[aria-current="page"]:'
        'not([aria-disabled="true"]):active {',
        '  .nami-task-card[aria-current="true"]:focus-visible,\n'
        '  .nami-task-card[aria-current="page"]:focus-visible {',
    ):
        assert paired_current_selectors in source
    marker = _block(
        source,
        '.nami-task-card[aria-selected="true"]::before,',
    )
    assert "background: var(--color-accent-fill);" in marker
    assert "inline-size: 3px;" in marker
    assert ".nami-task-card:not([aria-disabled=\"true\"]):hover" in source
    assert ".nami-task-card:not([aria-disabled=\"true\"]):active" in source
    task_hover = _block(
        source,
        '.nami-task-card:not([aria-disabled="true"]):hover ',
    )
    task_pressed = _block(
        source,
        '.nami-task-card:not([aria-disabled="true"]):active ',
    )
    assert "background: var(--color-selection-highlight);" in task_hover
    assert "background: var(--color-selection-highlight-pressed);" in task_pressed
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
    assert "background: var(--color-selection-highlight);" in selected_hover
    selected_pressed = _block(
        source,
        '.nami-task-card[aria-selected="true"]:'
        'not([aria-disabled="true"]):active,',
    )
    assert "background: var(--color-selection-highlight-pressed);" in selected_pressed
    disabled_task = _block(source, '.nami-task-card[aria-disabled="true"] ')
    assert "color: var(--color-neutral-foreground-disabled);" in disabled_task
    assert "cursor: default;" in disabled_task
    selected_focus = _block(
        source,
        '.nami-task-card[aria-selected="true"]:focus-visible,',
    )
    assert "0 0 0 1px var(--color-focus-inner)," in selected_focus
    assert "0 0 0 3px var(--color-focus-ring);" in selected_focus
    assert "outline: none;" in selected_focus
    cue_start = source.index('[data-intent="copy"] .nami-state-cue::before')
    cue_source = source[cue_start : source.index(".nami-progress {", cue_start)]
    for channel, keys in (
        ("intent", INTENTS),
        ("lifecycle", LIFECYCLES),
        ("integrity", INTEGRITY_STATES),
    ):
        for key in keys:
            assert f'[data-{channel}="{key}"]' in cue_source
    assert set(re.findall(r'content:\s*("[^";]+")', cue_source)) >= {
        '"C"',
        '"U"',
        '"M"',
        '"M+"',
        '"Aa"',
        '"+"',
        '"T"',
        '"D"',
        '"!"',
        '"\\2013"',
        '"\\25b6"',
        '"\\2161"',
        '"\\2713"',
        '"\\00d7"',
        '"\\2260"',
    }

    assert HEX_LITERAL.search(source) is None
    assert "--palette-" not in source

    forced = _block(source, "@media (forced-colors: active)")
    assert "outline: 2px solid var(--color-focus-ring);" in forced
    assert "outline-offset: 2px;" in forced
    active_tree = _block(forced, '.nami-tree-row[data-active="true"] ')
    assert "color: var(--color-accent-fill-foreground);" in active_tree
    active_disclosure = _block(
        forced,
        '.nami-tree-row[data-active="true"] .nami-tree-row__disclosure ',
    )
    assert "border-color: var(--color-accent-fill-foreground);" in active_disclosure
    assert re.search(
        r"\.nami-icon\s*\{\s*forced-color-adjust:\s*none;\s*\}",
        forced,
    )


def test_sh_g_11_solid_controls_and_operation_filters_follow_tuned_states() -> None:
    tokens = TOKENS.read_text(encoding="utf-8")
    source = COMPONENTS.read_text(encoding="utf-8")
    light, dark, automatic_dark = _theme_variables(tokens)

    filter_backgrounds = {
        "copy": "blue",
        "update": "yellow",
        "move": "purple",
        "move-update": "yellow",
        "recase": "purple",
        "mkdir": "blue",
        "trash": "red",
        "delete": "red",
    }
    assert light["--filter-purple-active-foreground"] == (
        "var(--color-neutral-surface)"
    )
    assert dark["--filter-purple-active-foreground"] == (
        "var(--color-neutral-foreground)"
    )
    assert automatic_dark["--filter-purple-active-foreground"] == (
        "var(--color-neutral-foreground)"
    )
    for theme in (light, dark, automatic_dark):
        inverse_background = _resolve(
            "--color-neutral-foreground-secondary",
            theme,
        )
        inverse_foreground = _resolve("--color-neutral-surface", theme)
        delete_foreground = _resolve("--filter-delete-foreground", theme)
        assert _contrast(inverse_foreground, inverse_background) >= 4.5
        assert delete_foreground == _resolve("--palette-red-main", theme)
        active_foreground = _resolve("--filter-active-foreground", theme)
        for operation, family in filter_backgrounds.items():
            background = _resolve(f"--filter-{operation}-background", theme)
            assert background == _resolve(f"--palette-{family}-main", theme)
            main = _resolve(f"--palette-{family}-main", theme)
            assert theme[f"--filter-{family}-background-hover"] == f"{main}E6"
            assert theme[f"--filter-{family}-background-pressed"] == f"{main}CC"
            foreground = (
                _resolve("--filter-delete-active-foreground", theme)
                if operation == "delete"
                else (
                    _resolve("--filter-purple-active-foreground", theme)
                    if family == "purple"
                    else active_foreground
                )
            )
            assert _contrast(foreground, background) >= 4.5, operation
        assert _contrast(
            _resolve("--filter-noop-foreground", theme),
            _resolve("--filter-noop-background", theme),
        ) >= 4.5
        noop = _resolve("--filter-noop-background", theme)
        assert theme["--filter-noop-background-hover"].casefold() == (
            f"{noop}E6".casefold()
        )
        assert theme["--filter-noop-background-pressed"].casefold() == (
            f"{noop}CC".casefold()
        )
        assert _resolve("--progress-active-fill", theme) == _resolve(
            "--color-accent-fill", theme
        )
        assert _resolve("--progress-paused-fill", theme) == _resolve(
            "--palette-yellow-main", theme
        )
        assert _resolve("--progress-canceled-fill", theme) == _resolve(
            "--color-neutral-foreground-secondary", theme
        )
        assert _resolve("--progress-track-background", theme) == _resolve(
            "--color-neutral-surface-pressed", theme
        )
        assert _contrast(
            _resolve("--color-neutral-foreground", theme),
            _resolve("--color-control-fill", theme),
        ) >= 4.5

    shared_controls = _block(
        source,
        ".nami-button,\n.nami-chip,\n.nami-icon-button,\n.nami-segmented__item ",
    )
    assert "background:" not in shared_controls
    assert "border:" not in shared_controls
    ordinary_controls = _block(
        source,
        ".nami-button,\n.nami-icon-button ",
    )
    assert "background: var(--color-control-fill);" in ordinary_controls
    assert "border: 1px solid var(--color-control-border);" in ordinary_controls
    assert "color: var(--color-neutral-foreground);" in ordinary_controls
    ordinary_hover = _block(source, ".nami-button:hover,")
    ordinary_pressed = _block(source, ".nami-button:active,")
    assert "background: var(--color-control-fill-hover);" in ordinary_hover
    assert "background: var(--color-control-fill-pressed);" in ordinary_pressed

    primary_boundary = _block(source, ".nami-button--primary ")
    assert "border: 0;" in primary_boundary
    primary = _block(source, ".nami-button--primary:not(:disabled) ")
    assert "background: var(--color-accent-fill);" in primary
    assert "color: var(--color-accent-fill-foreground);" in primary
    primary_hover = _block(
        source,
        ".nami-button--primary:not(:disabled):hover ",
    )
    primary_active = _block(
        source,
        ".nami-button--primary:not(:disabled):active ",
    )
    for interaction in (primary_hover, primary_active):
        assert "color: var(--color-accent-fill-foreground);" in interaction
    assert "background: var(--color-accent-fill-hover);" in primary_hover
    assert "background: var(--color-accent-fill-pressed);" in primary_active
    assert "filter:" not in primary_hover
    assert "filter:" not in primary_active
    forced = _block(source, "@media (forced-colors: active)")
    forced_primary_active = _block(
        forced,
        ".nami-button--primary:not(:disabled):active,",
    )
    assert "filter: none;" in forced_primary_active
    assert ".nami-button--danger" not in source

    input_border = _block(source, ".nami-input,\n.nami-select ")
    assert "border: 2px solid var(--color-textbox-border);" in input_border
    input_surface = next(
        block
        for block in re.findall(
            r"(?ms)^\.nami-input,\n\.nami-select\s*\{(.*?)^\}",
            source,
        )
        if "background:" in block
    )
    assert "box-shadow: inset 0 -2px 0 var(--color-textbox-underline);" in (
        input_surface
    )
    input_focus = _block(source, ".nami-input:focus,\n.nami-select:focus ")
    assert "box-shadow: inset 0 -2px 0 var(--color-accent-fill);" in input_focus

    checkbox = _block(source, ".nami-checkbox ")
    assert "border: 1px solid var(--color-control-strong-stroke);" in checkbox
    assert "color: var(--color-accent-fill-foreground);" in checkbox
    unchecked_checkbox_pressed = _block(source, ".nami-checkbox:active ")
    assert (
        "border-color: var(--color-control-strong-stroke);"
        in unchecked_checkbox_pressed
    )
    checked_checkbox = _block(source, ".nami-checkbox:checked,")
    checked_checkbox_hover = _block(
        source,
        ".nami-checkbox:is(:checked, :indeterminate, "
        '[aria-checked="mixed"]):hover ',
    )
    checked_checkbox_pressed = _block(
        source,
        ".nami-checkbox:is(:checked, :indeterminate, "
        '[aria-checked="mixed"]):active ',
    )
    assert "background: var(--color-accent-fill);" in checked_checkbox
    assert "border-color: var(--color-accent-fill);" in checked_checkbox
    assert "background: var(--color-accent-fill-hover);" in checked_checkbox_hover
    assert (
        "background: var(--color-accent-fill-pressed);"
        in checked_checkbox_pressed
    )

    toggle = _block(source, ".nami-toggle__control:checked ")
    toggle_hover = _block(source, ".nami-toggle__control:checked:hover ")
    toggle_pressed = _block(source, ".nami-toggle__control:checked:active ")
    assert "background: var(--color-accent-fill);" in toggle
    assert "background: var(--color-accent-fill-hover);" in toggle_hover
    assert "background: var(--color-accent-fill-pressed);" in toggle_pressed
    toggle_thumb = _block(source, ".nami-toggle__control:checked::after ")
    assert "background: var(--color-accent-fill-foreground);" in toggle_thumb

    chip = next(
        block
        for block in re.findall(r"(?ms)^\.nami-chip\s*\{(.*?)^\}", source)
        if "--nami-chip-active-background" in block
    )
    assert "--nami-chip-active-background: var(--color-accent-fill);" in chip
    operation_chip = _block(source, ".nami-chip[data-operation] ")
    assert (
        "--nami-chip-active-foreground: var(--filter-active-foreground);"
        in operation_chip
    )
    for interaction in (
        _block(source, '.nami-chip[aria-pressed="true"]:hover '),
        _block(source, '.nami-chip[aria-pressed="true"]:active '),
    ):
        assert "color: var(--nami-chip-active-foreground);" in interaction
    active_operation_hover = _block(
        source,
        '.nami-chip[data-operation][aria-pressed="true"]:'
        "not(:disabled):hover ",
    )
    active_operation_pressed = _block(
        source,
        '.nami-chip[data-operation][aria-pressed="true"]:'
        "not(:disabled):active ",
    )
    assert "opacity:" not in active_operation_hover
    assert "opacity:" not in active_operation_pressed
    assert "transform:" not in active_operation_hover
    assert "transform:" not in active_operation_pressed
    assert (
        "background: var(--nami-chip-active-background-hover);"
        in active_operation_hover
    )
    assert (
        "background: var(--nami-chip-active-background-pressed);"
        in active_operation_pressed
    )
    for operation in filter_backgrounds:
        selector_operation = operation.replace("-", "_")
        operation_filter = _block(
            source,
            f'.nami-chip[data-operation="{selector_operation}"] ',
        )
        assert (
            f"--nami-chip-active-background: "
            f"var(--filter-{operation}-background);"
            in operation_filter
        )
        family = filter_backgrounds[operation]
        assert (
            "--nami-chip-active-background-hover: "
            f"var(--filter-{family}-background-hover);"
            in operation_filter
        )
        assert (
            "--nami-chip-active-background-pressed: "
            f"var(--filter-{family}-background-pressed);"
            in operation_filter
        )
    purple_selector = """.nami-chip:is(
  [data-operation="move"],
  [data-operation="recase"]
) {"""
    assert purple_selector in source
    purple_filters = _block(source, purple_selector.removesuffix("{"))
    assert (
        "--nami-chip-active-foreground: "
        "var(--filter-purple-active-foreground);"
        in purple_filters
    )
    delete_chip = _block(source, '.nami-chip[data-operation="delete"] ')
    assert "color: var(--filter-delete-foreground);" in delete_chip
    assert (
        "--nami-chip-active-foreground: "
        "var(--filter-delete-active-foreground);"
        in delete_chip
    )
    assert (
        '.nami-chip[data-operation="delete"]:'
        'not([aria-pressed="true"]):not(:disabled):hover'
        not in source
    )

    badges = _block(source, ".nami-badge,\n.nami-status-pill ")
    assert "border: 0;" in badges
    progress_at = source.index(
        ".nami-progress {",
        source.index('[data-integrity="mismatched"]'),
    )
    progress = _block(source[progress_at:], ".nami-progress ")
    assert "--nami-progress-fill: var(--progress-active-fill);" in progress
    assert "background: var(--progress-track-background);" in progress
    assert "border: 0;" in progress
    progress_bar = _block(source, ".nami-progress__bar ")
    assert "background: var(--nami-progress-fill);" in progress_bar
    active_progress_selector = """.nami-progress:is(
  [data-lifecycle="executing"],
  [data-lifecycle="verifying"],
  [data-lifecycle="pausing"],
  [data-lifecycle="canceling"]
) {"""
    assert active_progress_selector in source
    active_progress = _block(
        source,
        active_progress_selector.removesuffix("{"),
    )
    assert "--nami-progress-fill: var(--progress-active-fill);" in active_progress
    paused_progress = _block(
        source, '.nami-progress[data-lifecycle="paused"] '
    )
    canceled_progress = _block(
        source, '.nami-progress[data-lifecycle="canceled"] '
    )
    assert "--nami-progress-fill: var(--progress-paused-fill);" in paused_progress
    assert (
        "--nami-progress-fill: var(--progress-canceled-fill);"
        in canceled_progress
    )
    frozen_progress_selector = """.nami-progress--indeterminate:is(
  [data-lifecycle="paused"],
  [data-lifecycle="canceled"]
) .nami-progress__bar {"""
    assert frozen_progress_selector in source
    frozen_progress = _block(
        source,
        frozen_progress_selector.removesuffix("{"),
    )
    assert "animation-play-state: paused;" in frozen_progress
    assert ".nami-progress:hover" not in source
    assert ".nami-progress:active" not in source

    segmented_match = re.search(
        r"(?ms)^\.nami-segmented\s*\{\s*background:\s*"
        r"var\(--color-neutral-surface-selected\);(?P<body>.*?)^\}",
        source,
    )
    assert segmented_match is not None
    segmented = segmented_match.group("body")
    assert "border: 0;" in segmented
    assert (
        "background: var(--color-neutral-surface-selected);"
        in segmented_match.group(0)
    )
    segmented_item = next(
        block
        for block in re.findall(
            r"(?ms)^\.nami-segmented__item\s*\{(.*?)^\}",
            source,
        )
        if "background:" in block
    )
    assert "border: 0;" in segmented_item
    selected_segment = _block(
        source,
        '.nami-segmented__item[aria-checked="true"] ',
    )
    assert "background: var(--color-accent-fill);" in selected_segment
    assert "color: var(--color-accent-fill-foreground);" in selected_segment
    segment_hover = _block(
        source,
        '.nami-segmented__item[aria-checked="true"]:not(:disabled):hover ',
    )
    segment_pressed = _block(
        source,
        '.nami-segmented__item[aria-checked="true"]:not(:disabled):active ',
    )
    assert "background: var(--color-accent-fill-hover);" in segment_hover
    assert "background: var(--color-accent-fill-pressed);" in segment_pressed
    for interaction in (segment_hover, segment_pressed):
        assert "color: var(--color-accent-fill-foreground);" in interaction
    assert "transform: translateX(1.25rem);" in source


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
    assert len(re.findall(r"--nami-icon-mask-(?:sm|md|lg): url\(", components)) == len(ICON_MASK_FILES)
    assert "http:" not in components
    assert "https:" not in components
