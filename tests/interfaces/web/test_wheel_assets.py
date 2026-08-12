"""Installed-wheel web-asset evidence."""

from __future__ import annotations

import json
import os
import subprocess
import tomllib
import zipfile
from pathlib import Path

from conftest import BuiltWheel, InstalledWheel


PROJECT_ROOT = Path(__file__).parents[3]
ASSET_ROOT = "namisync/interfaces/web/assets/"
INITIAL_ASSETS = {
    "app.css",
    "app.js",
    "bridge.js",
    "index.html",
}


def test_built_wheel_contains_exact_initial_web_assets(
    built_wheel: BuiltWheel,
) -> None:
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert project["tool"]["setuptools"]["package-data"] == {
        "namisync.interfaces.web": ["assets/*"]
    }

    with zipfile.ZipFile(built_wheel.path) as wheel:
        assets = {
            name.removeprefix(ASSET_ROOT)
            for name in wheel.namelist()
            if name.startswith(ASSET_ROOT) and not name.endswith("/")
        }

    assert assets == INITIAL_ASSETS


def test_installed_wheel_resolves_index_with_package_resources(
    installed_wheel: InstalledWheel,
) -> None:
    script = """
import importlib.resources
import json

index = (
    importlib.resources.files("namisync.interfaces.web")
    / "assets"
    / "index.html"
)
print(json.dumps({
    "exists": index.is_file(),
    "text": index.read_text(encoding="utf-8"),
}))
"""
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [installed_wheel.python, "-c", script],
        cwd=installed_wheel.root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    result = json.loads(completed.stdout)
    assert result["exists"] is True
    assert "<title>NamiSync</title>" in result["text"]
