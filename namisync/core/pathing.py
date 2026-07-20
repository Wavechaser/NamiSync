"""Pure Windows relative-path safety and identity helpers."""

from __future__ import annotations

import os
import re
from pathlib import PureWindowsPath


class PathValidationError(ValueError):
    """Raised when a path cannot safely identify an entry below a root."""


_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_DEVICE_PREFIXES = ("\\\\?\\", "\\\\.\\", "\\??\\")
_RESERVED_BASENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def _uppercase_one_codepoint(value: str) -> str:
    """Apply an invariant one-codepoint uppercase mapping.

    Python's ``str.upper`` may expand one character into several (for example
    ``ß`` to ``SS``). Windows path identity does not use that expansion. A
    character whose uppercase form expands is therefore retained verbatim.
    """

    mapped: list[str] = []
    for character in value:
        uppercase = character.upper()
        mapped.append(uppercase if len(uppercase) == 1 else character)
    return "".join(mapped)


def validate_relative_path(value: str, *, allow_root: bool = False) -> str:
    """Validate and return a canonical-separator Windows relative path."""

    if not isinstance(value, str):
        raise TypeError("relative path must be a string")
    if "\x00" in value:
        raise PathValidationError("relative path contains NUL")
    if any("\ud800" <= character <= "\udfff" for character in value):
        raise PathValidationError("relative path contains an unpaired surrogate")
    if value == "":
        if allow_root:
            return ""
        raise PathValidationError("relative path is empty")

    canonical = value.replace("/", "\\")
    upper_prefix = canonical.upper()
    if canonical.startswith("\\") or _DRIVE_PREFIX.match(canonical):
        raise PathValidationError("relative path is absolute or qualified")
    if upper_prefix.startswith(_DEVICE_PREFIXES):
        raise PathValidationError("relative path uses a device namespace")

    components = canonical.split("\\")
    for component in components:
        if component in {"", ".", ".."}:
            raise PathValidationError("relative path has an unsafe component")
        if ":" in component:
            raise PathValidationError("relative path contains a stream or drive qualifier")
        if component.endswith((" ", ".")):
            raise PathValidationError("relative path has a Windows-ambiguous suffix")
        basename = component.split(".", 1)[0]
        if _uppercase_one_codepoint(basename) in _RESERVED_BASENAMES:
            raise PathValidationError("relative path names a Windows device")

    if PureWindowsPath(canonical).is_absolute():
        raise PathValidationError("relative path is absolute")
    return canonical


def normalize_relative_path(value: str, *, allow_root: bool = False) -> str:
    """Return the canonical Windows comparison key for a relative path."""

    canonical = validate_relative_path(value, allow_root=allow_root)
    return _uppercase_one_codepoint(canonical)


def is_path_below(candidate: str, root: str) -> bool:
    """Return whether two resolved absolute paths preserve root containment."""

    try:
        common = os.path.commonpath((os.path.abspath(candidate), os.path.abspath(root)))
    except ValueError:
        return False
    return os.path.normcase(common) == os.path.normcase(os.path.abspath(root))


def join_under_root(root: str, relative_path: str) -> str:
    """Join a lexically valid relative path beneath an absolute root."""

    canonical = validate_relative_path(relative_path)
    candidate = os.path.abspath(os.path.join(root, *canonical.split("\\")))
    if not is_path_below(candidate, root):
        raise PathValidationError("relative path escapes its root")
    return candidate


def to_extended_length_path(path: str) -> str:
    """Return a Windows extended-length spelling without changing identity."""

    absolute = os.path.abspath(path)
    if os.name != "nt" or absolute.startswith("\\\\?\\"):
        return absolute
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute[2:]
    return "\\\\?\\" + absolute
