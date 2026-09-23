"""Exact source, wheel, and installed-package identity checks."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import zipfile
from collections import Counter
from pathlib import Path
from typing import Mapping


BUILD_INPUTS = ("pyproject.toml", "README.md", "LICENSE")
PACKAGE_PREFIX = "namisync/"


class WheelIdentityError(AssertionError):
    """The built or installed package is not the declared source population."""


def source_inputs(project_root: Path) -> dict[str, bytes]:
    """Read the finite tracked/nonignored build-input population from disk."""

    completed = subprocess.run(
        [
            "git",
            "-C",
            str(project_root),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "namisync",
            *BUILD_INPUTS,
        ],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise WheelIdentityError(
            "cannot enumerate package build inputs: "
            + completed.stderr.decode(errors="replace")
        )
    paths = sorted(
        os.fsdecode(raw).replace("\\", "/")
        for raw in completed.stdout.split(b"\0")
        if raw
    )
    required = set(BUILD_INPUTS)
    if not required.issubset(paths):
        raise WheelIdentityError("required package build inputs are missing")
    if not any(path.startswith(PACKAGE_PREFIX) for path in paths):
        raise WheelIdentityError("package source population is empty")

    inputs: dict[str, bytes] = {}
    for relative in paths:
        path = project_root / Path(relative)
        if not path.is_file():
            raise WheelIdentityError(f"package build input is unavailable: {relative}")
        inputs[relative] = path.read_bytes()
    return inputs


def assert_source_inputs(project_root: Path, expected: Mapping[str, bytes]) -> None:
    _assert_population("source", expected, source_inputs(project_root))


def stage_source_inputs(staging_root: Path, inputs: Mapping[str, bytes]) -> None:
    if staging_root.exists() and any(staging_root.iterdir()):
        raise WheelIdentityError("package staging directory is not empty")
    for relative, content in inputs.items():
        target = staging_root / Path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    assert_staged_inputs(staging_root, inputs)


def assert_staged_inputs(
    staging_root: Path,
    expected: Mapping[str, bytes],
    *,
    allow_generated: bool = False,
) -> None:
    actual = {
        path.relative_to(staging_root).as_posix(): path.read_bytes()
        for path in staging_root.rglob("*")
        if path.is_file()
    }
    if not allow_generated:
        _assert_population("staged", expected, actual)
        return
    declared_and_package = {
        relative: content
        for relative, content in actual.items()
        if relative in expected or relative.startswith(PACKAGE_PREFIX)
    }
    _assert_population("staged", expected, declared_and_package)


def package_inputs(inputs: Mapping[str, bytes]) -> dict[str, bytes]:
    return {
        relative: content
        for relative, content in inputs.items()
        if relative.startswith(PACKAGE_PREFIX)
    }


def assert_wheel_package(wheel_path: Path, expected: Mapping[str, bytes]) -> None:
    try:
        with zipfile.ZipFile(wheel_path) as archive:
            names = [info.filename for info in archive.infolist()]
            duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
            if duplicates:
                raise WheelIdentityError(
                    "wheel contains duplicate ZIP members: " + ", ".join(duplicates)
                )
            actual = {
                name: archive.read(name)
                for name in names
                if name.startswith(PACKAGE_PREFIX) and not name.endswith("/")
            }
    except (OSError, zipfile.BadZipFile) as error:
        raise WheelIdentityError("wheel package is unreadable") from error
    _assert_population("wheel package", expected, actual)


def assert_installed_package(
    site_packages: Path,
    expected: Mapping[str, bytes],
) -> None:
    package_root = site_packages / "namisync"
    actual = {
        f"namisync/{path.relative_to(package_root).as_posix()}": path.read_bytes()
        for path in package_root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    }
    _assert_population("installed package", expected, actual)


def write_identity_record(
    path: Path,
    inputs: Mapping[str, bytes],
    wheel_path: Path,
    *,
    site_packages: Path | None = None,
) -> None:
    record: dict[str, object] = {
        "schema": 1,
        "source": {
            relative: _sha256(content) for relative, content in sorted(inputs.items())
        },
        "wheel": {
            "name": wheel_path.name,
            "sha256": _sha256(wheel_path.read_bytes()),
        },
    }
    if site_packages is not None:
        record["installed"] = {
            relative: _sha256(content)
            for relative, content in sorted(package_inputs(inputs).items())
        }
        record["site_packages"] = str(site_packages.resolve())
    path.write_bytes(
        (
            json.dumps(
                record,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    )


def assert_recorded_artifact(
    record_path: Path,
    project_root: Path,
    wheel_path: Path,
) -> dict[str, bytes]:
    try:
        record = json.loads(record_path.read_bytes())
        recorded_source = record["source"]
        recorded_wheel = record["wheel"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise WheelIdentityError("wheel identity record is invalid") from error
    if (
        record.get("schema") != 1
        or not isinstance(recorded_source, dict)
        or not isinstance(recorded_wheel, dict)
        or set(recorded_wheel) != {"name", "sha256"}
    ):
        raise WheelIdentityError("wheel identity record is invalid")

    inputs = source_inputs(project_root)
    actual_source = {
        relative: _sha256(content) for relative, content in inputs.items()
    }
    _assert_population("recorded source", recorded_source, actual_source)
    actual_wheel = {
        "name": wheel_path.name,
        "sha256": _sha256(wheel_path.read_bytes()),
    }
    _assert_population("recorded wheel", recorded_wheel, actual_wheel)
    return inputs


def _assert_population(
    label: str,
    expected: Mapping[str, object],
    actual: Mapping[str, object],
) -> None:
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    changed = sorted(
        relative
        for relative in set(expected) & set(actual)
        if expected[relative] != actual[relative]
    )
    if missing or extra or changed:
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("extra=" + ",".join(extra))
        if changed:
            details.append("changed=" + ",".join(changed))
        raise WheelIdentityError(f"{label} identity mismatch: " + "; ".join(details))


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
