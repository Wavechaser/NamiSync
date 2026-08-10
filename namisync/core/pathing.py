"""Pure Windows relative-path safety and identity helpers."""

from __future__ import annotations

import os
import re
from pathlib import Path, PureWindowsPath


class PathValidationError(ValueError):
    """Raised when a path cannot safely identify an entry below a root."""


_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_DEVICE_PREFIXES = ("\\\\?\\", "\\\\.\\", "\\??\\")
_INVALID_ABSOLUTE_COMPONENT_CHARACTERS = frozenset('<>"/\\|?*')
_RESERVED_BASENAMES = {
    "CON",
    "CONIN$",
    "CONOUT$",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
    *(f"COM{number}" for number in "¹²³"),
    *(f"LPT{number}" for number in "¹²³"),
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


def relative_path_depth(path: str) -> int:
    """Return the number of components in a relative Windows path."""

    return len(PureWindowsPath(path).parts)


def relative_path_parent(path: str) -> str | None:
    """Return a relative path's parent, or ``None`` for a top-level path."""

    parent = str(PureWindowsPath(path).parent)
    return None if parent == "." else parent


def is_relative_path_descendant(path: str, directory: str) -> bool:
    """Return whether ``path`` is strictly below ``directory`` by segments."""

    path_key = normalize_relative_path(path)
    directory_key = normalize_relative_path(directory)
    return path_key.startswith(directory_key + "\\")


def strip_common_relative_path_suffix(
    left: str,
    right: str,
) -> tuple[str, str]:
    """Strip equal trailing path components and preserve each prefix spelling."""

    left_parts = PureWindowsPath(
        validate_relative_path(left, allow_root=True)
    ).parts
    right_parts = PureWindowsPath(
        validate_relative_path(right, allow_root=True)
    ).parts
    common_count = 0
    for left_part, right_part in zip(
        reversed(left_parts),
        reversed(right_parts),
        strict=False,
    ):
        if _uppercase_one_codepoint(left_part) != _uppercase_one_codepoint(
            right_part
        ):
            break
        common_count += 1
    if common_count == 0:
        return "\\".join(left_parts), "\\".join(right_parts)
    return (
        "\\".join(left_parts[:-common_count]),
        "\\".join(right_parts[:-common_count]),
    )


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


def _validate_absolute_path_spelling(path: str) -> None:
    """Require an absolute drive/UNC path with stable ordinary components."""

    canonical = path.replace("/", "\\")
    upper = canonical.upper()
    if upper.startswith(("\\\\?\\", "\\\\.\\", "\\??\\", "\\\\??\\")):
        raise PathValidationError("path uses a device namespace")
    if canonical.startswith("\\\\"):
        pieces = canonical[2:].rstrip("\\").split("\\")
        if len(pieces) < 2 or not pieces[0] or not pieces[1]:
            raise PathValidationError("UNC path is incomplete")
        components = pieces
    elif (
        _DRIVE_PREFIX.match(canonical)
        and len(canonical) >= 3
        and canonical[2] == "\\"
    ):
        tail = canonical[3:].rstrip("\\")
        components = [] if not tail else tail.split("\\")
    else:
        raise PathValidationError("path is not an absolute drive or UNC path")

    for component in components:
        if not component:
            raise PathValidationError("absolute path has an empty component")
        if any(
            character in _INVALID_ABSOLUTE_COMPONENT_CHARACTERS
            for character in component
        ):
            raise PathValidationError(
                "absolute path has an invalid Windows component"
            )
        validate_relative_path(component)


def _display_extended_length_path(path: str) -> str | None:
    """Strip a recognized native prefix for diagnostics, not path identity."""

    upper = path.upper()
    if upper.startswith("\\\\?\\UNC\\"):
        logical = "\\\\" + path[8:]
    elif upper.startswith("\\\\?\\"):
        logical = path[4:]
    else:
        return None
    if logical.upper().startswith(("\\\\.\\", "\\??\\", "\\\\??\\")):
        return "<unsupported-device-path>"
    return logical


def from_extended_length_path(path: str) -> str:
    """Return the ordinary drive/UNC spelling for one filesystem path.

    NamiSync uses ordinary absolute paths for domain identity, persistence, and
    display.  Extended-length spellings belong only at the native Windows I/O
    boundary.  Other device namespaces are deliberately not filesystem roots
    and are refused instead of being reinterpreted as UNC paths.
    """

    raw = os.fspath(path)
    if not isinstance(raw, str):
        raise TypeError("path must be a string")
    if "\x00" in raw:
        raise PathValidationError("path contains NUL")
    upper = raw.upper()
    if upper.startswith(("\\\\.\\", "\\??\\", "\\\\??\\")):
        raise PathValidationError("path uses a device namespace")
    if upper.startswith("\\\\?\\") and "/" in raw[4:]:
        raise PathValidationError(
            "extended path uses a non-native separator"
        )
    if upper.startswith("\\\\?\\UNC\\"):
        unc_parts = raw[8:].replace("/", "\\").split("\\")
        logical = "\\\\" + raw[8:]
        if (
            len(unc_parts) < 2
            or not unc_parts[0]
            or not unc_parts[1]
            or not PureWindowsPath(logical).is_absolute()
        ):
            raise PathValidationError("extended UNC path is incomplete")
        _validate_absolute_path_spelling(logical)
        return logical
    if upper.startswith("\\\\?\\"):
        logical = raw[4:]
        if not (
            _DRIVE_PREFIX.match(logical)
            and len(logical) >= 3
            and logical[2] in {"\\", "/"}
        ):
            raise PathValidationError("unsupported extended device namespace")
        _validate_absolute_path_spelling(logical)
        return logical
    return raw


def lexical_absolute_path(path: str | os.PathLike[str]) -> str:
    """Return one logical absolute path without following filesystem links."""

    return from_extended_length_path(to_extended_length_path(os.fspath(path)))


def lexical_path_chain(
    path: str | os.PathLike[str],
    *,
    trusted_anchor: str | os.PathLike[str] | None = None,
) -> tuple[str, ...]:
    """Return each lexical component below a trusted absolute anchor.

    The anchor itself is deliberately excluded. Drive roots and UNC shares are
    the default trusted anchors; callers that already hold a mounted-volume
    root may provide it explicitly.
    """

    logical = lexical_absolute_path(path)
    if trusted_anchor is None:
        anchor = Path(logical).anchor
        if not anchor:
            raise PathValidationError("absolute path lacks a trusted anchor")
    else:
        anchor = lexical_absolute_path(trusted_anchor)
        if not is_path_below(logical, anchor):
            raise PathValidationError("path is outside its trusted anchor")
    relative = os.path.relpath(logical, anchor)
    if relative == os.curdir:
        return ()
    current = anchor
    chain: list[str] = []
    for component in Path(relative).parts:
        if component in {os.curdir, os.pardir}:
            raise PathValidationError("path escapes its trusted anchor")
        current = os.path.join(current, component)
        chain.append(current)
    return tuple(chain)


def trusted_volume_anchor(path: str | os.PathLike[str]) -> str:
    """Compatibility alias for the shared native root-authority probe."""

    from .root_authority import current_volume_anchor

    return current_volume_anchor(path)


def to_extended_length_path(path: str) -> str:
    """Return a Windows extended-length spelling without changing identity."""

    raw = os.fspath(path)
    logical = from_extended_length_path(raw)
    if logical != raw:
        # A valid extended drive/UNC spelling is already at the native boundary.
        return raw
    if os.name == "nt" and PureWindowsPath(logical).is_absolute():
        # Validate before ``abspath`` can normalize an ambiguous Win32 spelling
        # onto a different ordinary filesystem object.
        _validate_absolute_path_spelling(logical)
    absolute = os.path.abspath(logical)
    if os.name != "nt":
        return absolute
    _validate_absolute_path_spelling(absolute)
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute[2:]
    return "\\\\?\\" + absolute


def logical_error_text(error: BaseException) -> str:
    """Render an exception without leaking native extended path spelling.

    Only exact ``OSError`` filename fields are replaced. Arbitrary message text
    is left untouched, so a diagnostic that merely discusses ``\\\\?\\`` is not
    reinterpreted as filesystem identity.
    """

    detail = str(error)
    for attribute in ("filename", "filename2"):
        filename = getattr(error, attribute, None)
        if not isinstance(filename, str):
            continue
        try:
            logical = from_extended_length_path(filename)
        except PathValidationError:
            logical = _display_extended_length_path(filename)
            if logical is None:
                continue
        if logical == filename:
            continue
        detail = detail.replace(repr(filename), repr(logical))
        detail = detail.replace(filename, logical)
    return detail
