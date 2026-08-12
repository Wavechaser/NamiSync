"""Built-wheel metadata tests."""

from __future__ import annotations

import tomllib
import zipfile
from pathlib import Path

from conftest import BuiltWheel


PROJECT_ROOT = Path(__file__).parents[1]


def test_built_wheel_declares_and_contains_gpl_license(
    built_wheel: BuiltWheel,
) -> None:
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert project["project"]["license-files"] == ["LICENSE"]

    with zipfile.ZipFile(built_wheel.path) as wheel:
        names = wheel.namelist()
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        license_names = [
            name
            for name in names
            if name.endswith(".dist-info/licenses/LICENSE")
        ]
        metadata = wheel.read(metadata_name).decode("utf-8")

        assert license_names == ["namisync-0.1.0.dist-info/licenses/LICENSE"]
        assert wheel.read(license_names[0]) == (PROJECT_ROOT / "LICENSE").read_bytes()
        assert "License-Expression: GPL-3.0-or-later" in metadata
        assert "License-File: LICENSE" in metadata
        assert "Gertrud" not in metadata
