"""Product/distribution version agreement tests."""

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from namisync.version import NICKNAME, VERSION

from conftest import InstalledWheel


PROJECT_ROOT = Path(__file__).parents[1]


def test_product_version_is_the_dynamic_distribution_source() -> None:
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert project["project"]["dynamic"] == ["version"]
    assert "version" not in project["project"]
    assert project["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "namisync.version.VERSION"
    }
    assert VERSION == "0.1.0"


def test_product_nickname_is_separate_human_facing_metadata() -> None:
    assert NICKNAME == "Gertrud"
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert project["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "namisync.version.VERSION"
    }
    assert "NICKNAME" not in (PROJECT_ROOT / "pyproject.toml").read_text(
        encoding="utf-8"
    )


def test_importing_version_loads_no_other_namisync_submodule() -> None:
    script = """
import json
import sys
from namisync.version import NICKNAME, VERSION
print(json.dumps({
    "version": VERSION,
    "nickname": NICKNAME,
    "modules": sorted(
        name for name in sys.modules
        if name.startswith("namisync.")
    ),
}))
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "version": "0.1.0",
        "nickname": "Gertrud",
        "modules": ["namisync.version"],
    }


def test_installed_wheel_version_agrees_with_metadata(
    installed_wheel: InstalledWheel,
) -> None:
    script = """
import importlib.metadata
import json
import sys
from namisync.version import NICKNAME, VERSION

distribution = importlib.metadata.distribution("namisync")
print(json.dumps({
    "constant": VERSION,
    "metadata": distribution.version,
    "nickname": NICKNAME,
    "module_file": sys.modules["namisync.version"].__file__,
    "distribution_root": str(distribution.locate_file("")),
    "modules": sorted(
        name for name in sys.modules
        if name.startswith("namisync.")
    ),
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
    assert result["constant"] == result["metadata"] == "0.1.0"
    assert result["nickname"] == "Gertrud"
    assert result["modules"] == ["namisync.version"]
    assert Path(result["module_file"]).is_relative_to(installed_wheel.root)
    assert Path(result["distribution_root"]).is_relative_to(
        installed_wheel.root
    )


def test_sh_g_4_startup_log_uses_installed_product_version(
    installed_wheel: InstalledWheel,
    tmp_path: Path,
) -> None:
    log_root = tmp_path / "app"
    script = """
import importlib.metadata
import json
import sys
from pathlib import Path
from namisync.interfaces.web.logging_config import configure_logging
from namisync.interfaces.web.paths import AppPaths
from namisync.version import NICKNAME, VERSION

paths = AppPaths.from_root(Path(sys.argv[1]))
configure_logging(paths)
print(json.dumps({
    "constant": VERSION,
    "metadata": importlib.metadata.version("namisync"),
    "nickname": NICKNAME,
    "log": paths.log_file.read_text(encoding="utf-8"),
}))
"""
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [installed_wheel.python, "-c", script, str(log_root)],
        cwd=installed_wheel.root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    result = json.loads(completed.stdout)
    assert result["constant"] == result["metadata"] == "0.1.0"
    assert result["nickname"] == "Gertrud"
    assert "startup.begin product_version=0.1.0" in result["log"]
    assert "Gertrud" not in result["log"]
