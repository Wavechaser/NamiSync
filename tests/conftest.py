"""Shared installed-wheel evidence for shell acceptance tests."""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from dataclasses import dataclass
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parents[1]


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
            str(PROJECT_ROOT),
        ],
        cwd=wheel_dir,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    wheels = tuple(wheel_dir.glob("namisync-*.whl"))
    assert len(wheels) == 1
    return BuiltWheel(wheels[0])


@pytest.fixture(scope="session")
def installed_wheel(
    tmp_path_factory: pytest.TempPathFactory,
    built_wheel: BuiltWheel,
) -> InstalledWheel:
    root = tmp_path_factory.mktemp("installed-wheel") / "venv"
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
    return HeadedInstalledWheel(
        built_wheel.path,
        root,
        python,
        root / "Scripts",
    )
