"""Production runtime admission for the task artifact reservation model."""

from __future__ import annotations

import os
import platform
import struct
import sys
import sysconfig
from dataclasses import dataclass

from .readiness import DesktopStartupError


_SUPPORTED_IMPLEMENTATION = "cpython"
_SUPPORTED_VERSION = (3, 13)
_SUPPORTED_PLATFORM = "win32"
_SUPPORTED_MACHINES = frozenset({"amd64", "x86_64"})
_SUPPORTED_POINTER_BITS = 64
_SUPPORTED_ALLOCATOR_OVERRIDES = frozenset({"", "pymalloc"})
_REFUSAL = (
    "NamiSync task surfaces require a 64-bit CPython 3.13 release build on "
    "Windows x64 with the standard GIL and pymalloc allocator. Install that "
    "runtime, remove any PYTHONMALLOC override, and restart NamiSync."
)


@dataclass(frozen=True, slots=True)
class TaskArtifactRuntimeProfile:
    implementation: str
    version: tuple[int, int]
    platform: str
    machine: str
    pointer_bits: int
    debug_build: bool
    gil_disabled: bool
    pymalloc_enabled: bool
    allocator_override: str


def current_task_artifact_runtime_profile() -> TaskArtifactRuntimeProfile:
    """Read only the process traits used by the analytical graph contract."""

    pymalloc_config = sysconfig.get_config_var("WITH_PYMALLOC")
    return TaskArtifactRuntimeProfile(
        implementation=sys.implementation.name,
        version=(sys.version_info.major, sys.version_info.minor),
        platform=sys.platform,
        machine=platform.machine().casefold(),
        pointer_bits=struct.calcsize("P") * 8,
        debug_build=(
            hasattr(sys, "gettotalrefcount")
            or _config_enabled(sysconfig.get_config_var("Py_DEBUG"))
        ),
        gil_disabled=_config_enabled(
            sysconfig.get_config_var("Py_GIL_DISABLED")
        ),
        pymalloc_enabled=(
            pymalloc_config is None or _config_enabled(pymalloc_config)
        ),
        allocator_override=(
            os.environ.get("PYTHONMALLOC", "").strip().casefold()
        ),
    )


def task_artifact_runtime_supported(
    profile: TaskArtifactRuntimeProfile,
) -> bool:
    """Return whether one exact process profile satisfies the frozen premise."""

    return (
        type(profile) is TaskArtifactRuntimeProfile
        and type(profile.implementation) is str
        and profile.implementation == _SUPPORTED_IMPLEMENTATION
        and type(profile.version) is tuple
        and all(type(value) is int for value in profile.version)
        and profile.version == _SUPPORTED_VERSION
        and type(profile.platform) is str
        and profile.platform == _SUPPORTED_PLATFORM
        and type(profile.machine) is str
        and profile.machine in _SUPPORTED_MACHINES
        and type(profile.pointer_bits) is int
        and profile.pointer_bits == _SUPPORTED_POINTER_BITS
        and type(profile.debug_build) is bool
        and profile.debug_build is False
        and type(profile.gil_disabled) is bool
        and profile.gil_disabled is False
        and type(profile.pymalloc_enabled) is bool
        and profile.pymalloc_enabled is True
        and type(profile.allocator_override) is str
        and profile.allocator_override in _SUPPORTED_ALLOCATOR_OVERRIDES
    )


def require_task_artifact_runtime() -> None:
    """Refuse before task registry construction when its premise is false."""

    if not task_artifact_runtime_supported(
        current_task_artifact_runtime_profile()
    ):
        raise DesktopStartupError(_REFUSAL)


def _config_enabled(value: object) -> bool:
    return value not in (None, False, 0, "", "0")
