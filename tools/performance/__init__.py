"""Selected, development-only measurement cases."""

from __future__ import annotations

import importlib
import platform
import subprocess
import sys
from pathlib import Path


_MODULES = {
    "plan": "plan",
    "execution-receipt": "execution_receipt",
    "execution-ui": "execution_ui",
    "bridge-event": "bridge_event",
    "history": "history",
}
_REPOSITORY = Path(__file__).resolve().parents[2]


def _family(name: str):
    try:
        module_name = _MODULES[name]
    except KeyError as error:
        raise ValueError(f"unknown performance family: {name}") from error
    return importlib.import_module(f".{module_name}", __name__)


def list_cases() -> dict[str, tuple[str, ...]]:
    return {name: tuple(_family(name).CASES) for name in _MODULES}


def _source() -> dict[str, object]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=_REPOSITORY,
        capture_output=True, text=True, check=False, timeout=10,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=_REPOSITORY, capture_output=True, text=True, check=False, timeout=10,
    )
    return {
        "revision": revision.stdout.strip() if revision.returncode == 0 else None,
        "dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
    }


def _environment() -> dict[str, object]:
    return {
        "platform": platform.platform(),
        "python": sys.version,
        "driver_source": _source(),
    }


def run_case(
    family: str, case: str, *, output: Path, installed_root: Path | None = None,
) -> dict[str, object]:
    module = _family(family)
    if case not in module.CASES:
        raise ValueError(f"unknown {family} case: {case}")
    observation = module.run_case(case, output=output, installed_root=installed_root)
    if not isinstance(observation, dict):
        raise ValueError("performance case returned no report")
    return {
        "schema": "namisync-performance-case-v1",
        "status": "incomplete" if observation.get("status") == "incomplete" else "complete",
        "family": family,
        "case": case,
        "environment": _environment(),
        "observation": observation,
    }


def failure_report(family: str, case: str, error: Exception) -> dict[str, object]:
    return {
        "schema": "namisync-performance-case-v1",
        "status": "incomplete",
        "family": family,
        "case": case,
        "environment": _environment(),
        "failure": {
            "type": type(error).__name__,
            "message": str(error)[:2048],
        },
    }
