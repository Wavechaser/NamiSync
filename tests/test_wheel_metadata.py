"""Built-wheel metadata tests."""

from __future__ import annotations

import json
import subprocess
import tomllib
import warnings
import zipfile
from pathlib import Path

import pytest

from _wheel_identity import (
    WheelIdentityError,
    assert_installed_package,
    assert_recorded_artifact,
    assert_source_inputs,
    assert_staged_inputs,
    assert_wheel_package,
    source_inputs,
    stage_source_inputs,
    write_identity_record,
)
from conftest import BuiltWheel, InstalledWheel


PROJECT_ROOT = Path(__file__).parents[1]
SAMPLE_PACKAGE = {
    "namisync/__init__.py": b"value = 1\n",
    "namisync/data.txt": b"data\n",
}


def test_built_wheel_declares_lower_bound_only_python_requirement(
    built_wheel: BuiltWheel,
) -> None:
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert project["project"]["requires-python"] == ">=3.13"

    with zipfile.ZipFile(built_wheel.path) as wheel:
        metadata_name = next(
            name
            for name in wheel.namelist()
            if name.endswith(".dist-info/METADATA")
        )
        metadata_lines = wheel.read(metadata_name).decode("utf-8").splitlines()

    assert "Requires-Python: >=3.13" in metadata_lines


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


def test_built_wheel_publishes_canonical_identity_record(
    built_wheel: BuiltWheel,
) -> None:
    record_path = built_wheel.path.parent / "wheel-identity.json"
    encoded = record_path.read_bytes()
    record = json.loads(encoded)

    assert encoded.endswith(b"\n")
    assert encoded == (
        json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode()
    assert record["schema"] == 1
    assert record["wheel"]["name"] == built_wheel.path.name
    assert set(record["source"]) == set(source_inputs(PROJECT_ROOT))


def test_installed_wheel_publishes_canonical_identity_record(
    installed_wheel: InstalledWheel,
) -> None:
    record_path = installed_wheel.root.parent / "installed-wheel-identity.json"
    encoded = record_path.read_bytes()
    record = json.loads(encoded)

    assert encoded == (
        json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode()
    assert record["schema"] == 1
    assert record["wheel"]["name"] == installed_wheel.wheel.name
    assert set(record["installed"]) == {
        path for path in record["source"] if path.startswith("namisync/")
    }


@pytest.mark.parametrize("corruption", ["missing", "extra", "changed"])
def test_source_identity_rejects_real_population_and_byte_corruption(
    tmp_path: Path,
    corruption: str,
) -> None:
    root = tmp_path / "project"
    (root / "namisync").mkdir(parents=True)
    for relative, content in {
        **SAMPLE_PACKAGE,
        "pyproject.toml": b"[build-system]\n",
        "README.md": b"readme\n",
        "LICENSE": b"license\n",
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    expected = source_inputs(root)

    if corruption == "missing":
        (root / "namisync" / "data.txt").unlink()
    elif corruption == "extra":
        (root / "namisync" / "extra.py").write_bytes(b"extra\n")
    else:
        (root / "namisync" / "data.txt").write_bytes(b"changed\n")

    with pytest.raises(WheelIdentityError, match="source identity mismatch|unavailable"):
        assert_source_inputs(root, expected)


@pytest.mark.parametrize("corruption", ["missing", "extra", "changed"])
def test_staged_identity_rejects_real_population_and_byte_corruption(
    tmp_path: Path,
    corruption: str,
) -> None:
    inputs = {**SAMPLE_PACKAGE, "pyproject.toml": b"[build-system]\n"}
    stage_source_inputs(tmp_path, inputs)

    if corruption == "missing":
        (tmp_path / "namisync" / "data.txt").unlink()
    elif corruption == "extra":
        (tmp_path / "namisync" / "extra.py").write_bytes(b"extra\n")
    else:
        (tmp_path / "namisync" / "data.txt").write_bytes(b"changed\n")

    with pytest.raises(WheelIdentityError, match="staged identity mismatch"):
        assert_staged_inputs(tmp_path, inputs, allow_generated=True)


@pytest.mark.parametrize("corruption", ["missing", "extra", "changed", "duplicate"])
def test_wheel_identity_rejects_real_population_byte_and_zip_corruption(
    tmp_path: Path,
    corruption: str,
) -> None:
    wheel = tmp_path / "candidate.whl"
    members = dict(SAMPLE_PACKAGE)
    if corruption == "missing":
        del members["namisync/data.txt"]
    elif corruption == "extra":
        members["namisync/extra.py"] = b"extra\n"
    elif corruption == "changed":
        members["namisync/data.txt"] = b"changed\n"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(wheel, "w") as archive:
            for relative, content in members.items():
                archive.writestr(relative, content)
            if corruption == "duplicate":
                archive.writestr(
                    "namisync/data.txt",
                    SAMPLE_PACKAGE["namisync/data.txt"],
                )

    with pytest.raises(
        WheelIdentityError,
        match="wheel (package identity mismatch|contains duplicate)",
    ):
        assert_wheel_package(wheel, SAMPLE_PACKAGE)


@pytest.mark.parametrize("corruption", ["missing", "extra", "changed"])
def test_installed_identity_rejects_real_population_and_byte_corruption(
    tmp_path: Path,
    corruption: str,
) -> None:
    site_packages = tmp_path / "site-packages"
    package_root = site_packages / "namisync"
    package_root.mkdir(parents=True)
    for relative, content in SAMPLE_PACKAGE.items():
        (site_packages / relative).write_bytes(content)
    if corruption == "missing":
        (package_root / "data.txt").unlink()
    elif corruption == "extra":
        (package_root / "extra.py").write_bytes(b"extra\n")
    else:
        (package_root / "data.txt").write_bytes(b"changed\n")

    with pytest.raises(WheelIdentityError, match="installed package identity mismatch"):
        assert_installed_package(site_packages, SAMPLE_PACKAGE)


@pytest.mark.parametrize("corruption", ["build-input", "wheel"])
def test_recorded_artifact_rejects_changes_between_build_and_install(
    tmp_path: Path,
    corruption: str,
) -> None:
    root = tmp_path / "project"
    (root / "namisync").mkdir(parents=True)
    for relative, content in {
        **SAMPLE_PACKAGE,
        "pyproject.toml": b"[build-system]\n",
        "README.md": b"readme\n",
        "LICENSE": b"license\n",
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    inputs = source_inputs(root)
    wheel = tmp_path / "candidate.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for relative, content in SAMPLE_PACKAGE.items():
            archive.writestr(relative, content)
    record = tmp_path / "wheel-identity.json"
    write_identity_record(record, inputs, wheel)

    if corruption == "build-input":
        (root / "README.md").write_bytes(b"changed\n")
    else:
        wheel.write_bytes(wheel.read_bytes() + b"changed")

    with pytest.raises(
        WheelIdentityError,
        match="recorded (source|wheel) identity mismatch",
    ):
        assert_recorded_artifact(record, root, wheel)
