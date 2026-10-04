"""Shared helpers for frontend asset and Node.js tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence

from _headed_native import scenario_deadline, start_headed_process, terminate_process_tree


ASSET_ROOT = "namisync/interfaces/web/assets/"
# Authored development catalog, independent of generated runtime declarations.
ICON_CATALOG_PATH = Path(__file__).parents[3] / "tools" / "icons.json"
ICON_CATALOG = json.loads(ICON_CATALOG_PATH.read_text(encoding="utf-8"))
ICON_GLYPHS = tuple(ICON_CATALOG["glyphs"])
ICON_MASK_FILES = {
    f"{glyph}:{size}": (
        f"{ICON_CATALOG['filled'].get(glyph, glyph).replace('-', '_')}_{ICON_CATALOG['fallbacks'].get(glyph, {}).get(size, native)}_{'filled' if glyph in ICON_CATALOG['filled'] else 'regular'}.svg"
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
    "execution_confirmation.js",
    "file_row.js",
    "filter_menu.js",
    "icons.js",
    "icons/LICENSE.txt",
    "icons/SOURCE.json",
    *(f"icons/{filename}" for filename in ICON_FILES),
    "index.html",
    "integrity.js",
    "inventory_review.js",
    "panels.js",
    "plan.js",
    "plan_review.js",
    "rail.js",
    "task_status.js",
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


_NODE_JOB_MEMORY_BYTES = 512 * 1024 * 1024
_NODE_OUTPUT_BYTES = 1024 * 1024


def run_node_probe(
    command: Sequence[str | os.PathLike[str]], *, timeout: float,
) -> subprocess.CompletedProcess[str]:
    """Run a short Node probe in a preassigned, memory-bounded Windows Job."""

    actual_command = tuple(os.fspath(part) for part in command)
    deadline = scenario_deadline(timeout)
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        child = start_headed_process(
            actual_command,
            cwd=Path.cwd(),
            environment=os.environ.copy(),
            deadline=deadline,
            job_memory_limit_bytes=_NODE_JOB_MEMORY_BYTES,
            stdout=stdout,
            stderr=stderr,
        )
        try:
            returncode = child.process.wait(timeout=deadline.remaining())
        finally:
            terminate_process_tree(child, deadline=deadline)
        output = []
        for name, stream in (("stdout", stdout), ("stderr", stderr)):
            stream.seek(0)
            content = stream.read(_NODE_OUTPUT_BYTES + 1)
            if len(content) > _NODE_OUTPUT_BYTES:
                raise AssertionError(f"Node probe {name} exceeded 1 MiB")
            output.append(content.decode("utf-8", errors="replace"))
    return subprocess.CompletedProcess(actual_command, returncode, *output)
