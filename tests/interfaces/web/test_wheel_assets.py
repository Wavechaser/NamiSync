"""Installed-wheel web-asset evidence."""

from __future__ import annotations

import json
import os
import subprocess
import tomllib
import zipfile
from pathlib import Path

from conftest import BuiltWheel, InstalledWheel
from _frontend_test_support import ASSET_ROOT, INITIAL_ASSETS


PROJECT_ROOT = Path(__file__).parents[3]


def test_sh_g_6_built_wheel_contains_exact_initial_web_assets(
    built_wheel: BuiltWheel,
) -> None:
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert project["tool"]["setuptools"]["package-data"] == {
        "namisync.interfaces.web": ["assets/*", "assets/icons/*"]
    }

    with zipfile.ZipFile(built_wheel.path) as wheel:
        assets = {
            name.removeprefix(ASSET_ROOT)
            for name in wheel.namelist()
            if name.startswith(ASSET_ROOT) and not name.endswith("/")
        }

    assert assets == INITIAL_ASSETS


def test_br_g_32_built_wheel_contains_no_test_report_implementation(
    built_wheel: BuiltWheel,
) -> None:
    with zipfile.ZipFile(built_wheel.path) as wheel:
        containing_literal = [
            name
            for name in wheel.namelist()
            if not name.endswith("/") and b"test_report" in wheel.read(name)
        ]

    assert containing_literal == []


def test_installed_wheel_resolves_index_with_package_resources(
    installed_wheel: InstalledWheel,
) -> None:
    script = """
import importlib.resources
import importlib.util
import json
import sys

index = (
    importlib.resources.files("namisync.interfaces.web")
    / "assets"
    / "index.html"
)
print(json.dumps({
    "exists": index.is_file(),
    "index": str(index),
    "pip_available": importlib.util.find_spec("pip") is not None,
    "prefix": sys.prefix,
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
    assert Path(result["index"]).resolve().is_relative_to(
        installed_wheel.root.resolve()
    )
    assert result["pip_available"] is False
    assert Path(result["prefix"]).resolve() == installed_wheel.root.resolve()
    assert "<title>NamiSync</title>" in result["text"]
