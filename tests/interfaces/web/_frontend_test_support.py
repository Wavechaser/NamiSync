"""Shared helpers for frontend asset and Node.js tests."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


ASSET_ROOT = "namisync/interfaces/web/assets/"
# Authored development catalog, independent of generated runtime declarations.
ICON_CATALOG_PATH = Path(__file__).parents[3] / "tools" / "icons.json"
ICON_CATALOG = json.loads(ICON_CATALOG_PATH.read_text(encoding="utf-8"))
ICON_GLYPHS = tuple(ICON_CATALOG["glyphs"])
ICON_MASK_FILES = {
    f"{glyph}:{size}": (
        f"{glyph.replace('-', '_')}_{ICON_CATALOG['fallbacks'].get(glyph, {}).get(size, native)}_regular.svg"
    )
    for glyph in ICON_GLYPHS
    for size, native in (("sm", 16), ("md", 20), ("lg", 24))
}
ICON_FILES = tuple(sorted(set(ICON_MASK_FILES.values())))


INITIAL_ASSETS = {
    "app.css",
    "app.js",
    "appearance.js",
    "bridge.js",
    "components.css",
    "file_row.js",
    "icons.js",
    "icons/LICENSE.txt",
    "icons/SOURCE.json",
    *(f"icons/{filename}" for filename in ICON_FILES),
    "index.html",
    "integrity.js",
    "panels.js",
    "plan.js",
    "rail.js",
    "readiness.js",
    "render.js",
    "setup.js",
    "tokens.css",
    "theme.js",
    "tree.js",
}


def _node_executable() -> Path | None:
    configured = os.environ.get("NAMISYNC_TEST_NODE")
    if configured is not None:
        return Path(configured)
    installed = shutil.which("node")
    return Path(installed) if installed is not None else None
