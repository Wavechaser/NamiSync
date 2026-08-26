"""Shared helpers for frontend asset and Node.js tests."""

from __future__ import annotations

import os
import re
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


def _assert_exact_v5_event_routes(source: str) -> None:
    live = source.split(
        "function validateLiveSessionEvent(event, sessionId) {", 1
    )[1].split("function validateLegacySessionEvent(event, sessionId) {", 1)[0]
    assert re.fullmatch(
        r"\s*return validateDormantSessionEventV5\(event, sessionId\);\s*}\s*",
        live,
    )
    legacy = source.split(
        "function validateLegacySessionEvent(event, sessionId) {", 1
    )[1].split("function validateSessionRecord(record, sessionId) {", 1)[0]
    assert "event.schema_version !== 4" in legacy
    assert "LIVE_CORE_EVENT_SCHEMA_VERSION" not in source
    assert source.count("validateLegacySessionEvent") == 1
    assert source.count("validateLiveSessionEvent(") == 2
    assert "return validateLiveSessionEvent(update.event, sessionId);" in source
    assert "const DORMANT_CORE_EVENT_SCHEMA_VERSION = 5;" in source
    assert source.count("DORMANT_CORE_EVENT_SCHEMA_VERSION") == 2
    v5 = source.split(
        "export function validateDormantSessionEventV5(event, sessionId) {", 1
    )[1].split("function validateDormantProgressV5(value) {", 1)[0]
    assert "event.schema_version !== DORMANT_CORE_EVENT_SCHEMA_VERSION" in v5
    assert 'case "Progress":\n      return validateDormantProgressV5(event.body);' in v5
