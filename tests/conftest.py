"""Shared pytest policy and installed-wheel evidence."""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from dataclasses import dataclass
from pathlib import Path

import pytest

from _departments import (
    DepartmentManifestError,
    modules_for_departments,
    repository_module_path,
    requested_departments,
    validate_department_manifest,
)
from _wheel_identity import (
    assert_installed_package,
    assert_recorded_artifact,
    assert_source_inputs,
    assert_staged_inputs,
    assert_wheel_package,
    package_inputs,
    source_inputs,
    stage_source_inputs,
    write_identity_record,
)


PROJECT_ROOT = Path(__file__).parents[1]


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    try:
        ownership = validate_department_manifest()
        selected = requested_departments(config.getoption("departments") or ())
        item_modules = {
            item: repository_module_path(Path(item.path)) for item in items
        }
        unresolved = sorted(set(item_modules.values()) - set(ownership))
        if unresolved:
            raise DepartmentManifestError(
                "collected items have no primary owner: " + ", ".join(unresolved)
            )
    except DepartmentManifestError as error:
        raise pytest.UsageError(str(error)) from error

    if not selected:
        return
    selected_modules = modules_for_departments(selected, ownership)
    retained = [item for item in items if item_modules[item] in selected_modules]
    deselected = [item for item in items if item_modules[item] not in selected_modules]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
    items[:] = retained


@dataclass(frozen=True, slots=True)
class BuiltWheel:
    path: Path


@dataclass(frozen=True, slots=True)
class InstalledWheel:
    wheel: Path
    root: Path
    python: Path


@dataclass(frozen=True, slots=True)
class HeadedInstalledWheel:
    wheel: Path
    root: Path
    python: Path
    scripts: Path


@pytest.fixture(scope="session")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> BuiltWheel:
    wheel_dir = tmp_path_factory.mktemp("wheel")
    staging_root = wheel_dir / "source"
    inputs = source_inputs(PROJECT_ROOT)
    stage_source_inputs(staging_root, inputs)
    assert_source_inputs(PROJECT_ROOT, inputs)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--disable-pip-version-check",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            str(staging_root),
        ],
        cwd=wheel_dir,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert_source_inputs(PROJECT_ROOT, inputs)
    assert_staged_inputs(staging_root, inputs, allow_generated=True)
    wheels = tuple(wheel_dir.glob("namisync-*.whl"))
    assert len(wheels) == 1
    assert_wheel_package(wheels[0], package_inputs(inputs))
    write_identity_record(wheel_dir / "wheel-identity.json", inputs, wheels[0])
    return BuiltWheel(wheels[0])


@pytest.fixture(scope="session")
def installed_wheel(
    tmp_path_factory: pytest.TempPathFactory,
    built_wheel: BuiltWheel,
) -> InstalledWheel:
    root = tmp_path_factory.mktemp("installed-wheel") / "venv"
    venv.EnvBuilder(with_pip=False, clear=True).create(root)
    python = root / "Scripts" / "python.exe"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "--python",
            str(python),
            "install",
            "--disable-pip-version-check",
            "--no-deps",
            str(built_wheel.path),
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    identity_record = built_wheel.path.parent / "wheel-identity.json"
    inputs = assert_recorded_artifact(identity_record, PROJECT_ROOT, built_wheel.path)
    assert_wheel_package(built_wheel.path, package_inputs(inputs))
    site_packages = root / "Lib" / "site-packages"
    assert_installed_package(site_packages, package_inputs(inputs))
    write_identity_record(
        root.parent / "installed-wheel-identity.json",
        inputs,
        built_wheel.path,
        site_packages=site_packages,
    )
    return InstalledWheel(built_wheel.path, root, python)


@pytest.fixture(scope="session")
def headed_installed_wheel(
    tmp_path_factory: pytest.TempPathFactory,
    built_wheel: BuiltWheel,
) -> HeadedInstalledWheel:
    """Install the wheel and all runtime dependencies into a clean venv."""

    root = tmp_path_factory.mktemp("headed-installed-wheel") / "venv"
    venv.EnvBuilder(with_pip=True, clear=True).create(root)
    python = root / "Scripts" / "python.exe"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            str(built_wheel.path),
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    checked = subprocess.run(
        [str(python), "-m", "pip", "check"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    identity_record = built_wheel.path.parent / "wheel-identity.json"
    inputs = assert_recorded_artifact(identity_record, PROJECT_ROOT, built_wheel.path)
    assert_wheel_package(built_wheel.path, package_inputs(inputs))
    site_packages = root / "Lib" / "site-packages"
    assert_installed_package(site_packages, package_inputs(inputs))
    write_identity_record(
        root.parent / "installed-wheel-identity.json",
        inputs,
        built_wheel.path,
        site_packages=site_packages,
    )
    return HeadedInstalledWheel(
        built_wheel.path,
        root,
        python,
        root / "Scripts",
    )
