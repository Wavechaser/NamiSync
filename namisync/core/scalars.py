"""Checked scalar grammars shared by core, persistence, and interfaces."""

from __future__ import annotations

import re


MAX_SAFE_INTEGER = (1 << 53) - 1
MAX_SIGNED_64 = (1 << 63) - 1
MAX_FILE_INDEX_128 = (1 << 128) - 1

_CANONICAL_DECIMAL = re.compile(r"0|[1-9][0-9]*\Z")


class ScalarDomainError(ValueError):
    """A value cannot enter NamiSync's nonnegative signed-64 domain."""


def require_safe_int(value: object, field_name: str) -> int:
    """Return one exact non-Boolean JavaScript-safe integer."""

    if type(value) is not int:
        raise TypeError(f"{field_name} must be a non-Boolean integer")
    if not 0 <= value <= MAX_SAFE_INTEGER:
        raise ValueError(f"{field_name} is outside the SafeInt domain")
    return value


def require_signed_64(value: object, field_name: str) -> int:
    """Return one exact nonnegative signed-64 integer."""

    if type(value) is not int:
        raise TypeError(f"{field_name} must be a non-Boolean integer")
    if not 0 <= value <= MAX_SIGNED_64:
        raise ScalarDomainError(
            f"{field_name} is outside the nonnegative signed-64 domain"
        )
    return value


def checked_add_signed_64(left: object, right: object, field_name: str) -> int:
    """Add two accepted scalars without wrapping or widening the domain."""

    first = require_signed_64(left, field_name)
    second = require_signed_64(right, field_name)
    if first > MAX_SIGNED_64 - second:
        raise ScalarDomainError(
            f"{field_name} exceeds the nonnegative signed-64 domain"
        )
    return first + second


def scalar_64_to_text(value: object, field_name: str) -> str:
    """Encode one internal signed-64 quantity as canonical decimal text."""

    return str(require_signed_64(value, field_name))


def scalar_64_from_text(value: object, field_name: str) -> int:
    """Decode canonical decimal text without accepting JSON-number coercion."""

    if type(value) is not str:
        raise TypeError(f"{field_name} must be a canonical decimal string")
    if _CANONICAL_DECIMAL.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a canonical decimal string")
    maximum = str(MAX_SIGNED_64)
    if len(value) > len(maximum) or (len(value) == len(maximum) and value > maximum):
        raise ScalarDomainError(f"{field_name} exceeds the signed-64 domain")
    return int(value)


def file_index_128_to_text(value: object, field_name: str = "file index") -> str:
    """Encode one opaque Windows file index as canonical unsigned text."""

    if type(value) is not int:
        raise TypeError(f"{field_name} must be a non-Boolean integer")
    if not 0 <= value <= MAX_FILE_INDEX_128:
        raise ValueError(f"{field_name} is outside the FileIndex128 domain")
    return str(value)


def file_index_128_from_text(value: object, field_name: str = "file index") -> int:
    """Decode one canonical opaque Windows file index."""

    if type(value) is not str:
        raise TypeError(f"{field_name} must be canonical unsigned-decimal text")
    if _CANONICAL_DECIMAL.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be canonical unsigned-decimal text")
    maximum = str(MAX_FILE_INDEX_128)
    if len(value) > len(maximum) or (len(value) == len(maximum) and value > maximum):
        raise ValueError(f"{field_name} exceeds the FileIndex128 domain")
    return int(value)


def require_json_unicode(value: object) -> None:
    """Refuse surrogate code units in a decoded JSON tree's strings and keys."""

    if isinstance(value, str):
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise ValueError("JSON text must be valid Unicode") from error
    elif isinstance(value, dict):
        for key, item in value.items():
            require_json_unicode(key)
            require_json_unicode(item)
    elif isinstance(value, list):
        for item in value:
            require_json_unicode(item)


def bounded_utf8_text(
    value: object,
    field_name: str,
    *,
    maximum_bytes: int = 1_024,
) -> str | None:
    """Return complete diagnostic text, or ``None`` when it cannot fit."""

    if value is None:
        return None
    if type(value) is not str:
        raise TypeError(f"{field_name} must be text or None")
    if len(value) > maximum_bytes:
        return None
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        return None
    return value if len(encoded) <= maximum_bytes else None


def require_utf16_path(
    value: object,
    field_name: str,
    *,
    maximum_units: int = 32_767,
) -> str:
    """Validate one complete path-like string without truncation."""

    if type(value) is not str:
        raise TypeError(f"{field_name} must be text")
    if "\x00" in value:
        raise ValueError(f"{field_name} cannot contain NUL")
    try:
        units = len(value.encode("utf-16-le")) // 2
    except UnicodeEncodeError as error:
        raise ValueError(f"{field_name} must be valid Unicode") from error
    if units > maximum_units:
        raise ValueError(f"{field_name} exceeds the UTF-16 path bound")
    return value
