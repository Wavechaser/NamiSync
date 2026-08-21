"""Shared helpers for frontend asset and Node.js tests."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


ASSET_ROOT = "namisync/interfaces/web/assets/"
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
    "icons/checkmark_circle_20_regular.svg",
    "icons/dismiss_circle_20_regular.svg",
    "icons/info_20_regular.svg",
    "icons/warning_20_regular.svg",
    "index.html",
    "integrity.js",
    "panels.js",
    "plan.js",
    "rail.js",
    "readiness.js",
    "render.js",
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
