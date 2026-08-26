"""Allocation-first guards for opaque workflow JSON envelopes."""

from __future__ import annotations

from dataclasses import dataclass


# These are the predeclared analytical catalog's conservative CPython
# coefficients.  This helper neither freezes nor validates BR-G-45; the named
# reservation artifact and independent validator remain that model's authority.
# Codecs use the catalog to price every projected occurrence without inferring
# an allowance from identity-deduplicated domain custody.
JSON_TEXT_FIXED_CHARGE = 128
JSON_TEXT_UTF8_MULTIPLIER = 5
JSON_SCALAR_CHARGE = 64
JSON_LIST_FIXED_CHARGE = 128
JSON_LIST_SLOT_CHARGE = 16
JSON_OBJECT_FIXED_CHARGE = 256
JSON_OBJECT_ENTRY_CHARGE = 160


@dataclass(frozen=True, slots=True)
class JsonObjectLayout:
    entries: int
    canonical_syntax_bytes: int
    key_occurrence_charge: int


def object_layout(*keys: str) -> JsonObjectLayout:
    """Return the fixed canonical syntax owned by one exact object schema."""

    key_bytes = sum(_json_text_lengths(key)[1] for key in keys)
    key_occurrence_charge = sum(
        model_text_charge(_json_text_lengths(key)[0]) for key in keys
    )
    separators = 0 if not keys else (2 * len(keys)) - 1
    return JsonObjectLayout(
        len(keys),
        2 + key_bytes + separators,
        key_occurrence_charge,
    )


class JsonEnvelopeCounter:
    """Count one typed projection without constructing JSON dicts or lists."""

    __slots__ = ("canonical_bytes", "occurrence_charge")

    def __init__(self) -> None:
        self.canonical_bytes = 0
        self.occurrence_charge = 0

    def object(self, layout: JsonObjectLayout) -> None:
        self.canonical_bytes += layout.canonical_syntax_bytes
        self.occurrence_charge += model_object_charge(layout)

    def mapping(self, length: int) -> None:
        """Charge an object whose dynamic text keys are charged by the caller."""

        if type(length) is not int or length < 0:
            raise ValueError("JSON mapping length must be nonnegative")
        self.canonical_bytes += 2 + (0 if not length else (2 * length) - 1)
        self.occurrence_charge += model_mapping_charge(length)

    def array(self, length: int) -> None:
        if type(length) is not int or length < 0:
            raise ValueError("JSON array length must be nonnegative")
        self.canonical_bytes += 2 + max(0, length - 1)
        self.occurrence_charge += (
            JSON_LIST_FIXED_CHARGE + length * JSON_LIST_SLOT_CHARGE
        )

    def text(
        self,
        value: object,
        context: str,
        *,
        maximum_utf8_bytes: int,
        minimum_utf8_bytes: int = 0,
    ) -> str:
        if type(value) is not str:
            raise TypeError(f"{context} must be text")
        utf8_bytes, canonical_bytes = _json_text_lengths(value)
        if not minimum_utf8_bytes <= utf8_bytes <= maximum_utf8_bytes:
            raise ValueError(f"{context} exceeds its source text bound")
        self.canonical_bytes += canonical_bytes
        self.occurrence_charge += model_text_charge(utf8_bytes)
        return value

    def integer(self, value: object, context: str) -> int:
        if type(value) is not int:
            raise TypeError(f"{context} must be an integer")
        self.canonical_bytes += len(str(value))
        self.occurrence_charge += JSON_SCALAR_CHARGE
        return value

    def boolean(self, value: object, context: str) -> bool:
        if type(value) is not bool:
            raise TypeError(f"{context} must be a bool")
        self.canonical_bytes += 4 if value else 5
        self.occurrence_charge += JSON_SCALAR_CHARGE
        return value

    def null(self) -> None:
        self.canonical_bytes += 4
        self.occurrence_charge += JSON_SCALAR_CHARGE

    def optional_text(
        self,
        value: object,
        context: str,
        *,
        maximum_utf8_bytes: int,
        minimum_utf8_bytes: int = 0,
    ) -> str | None:
        if value is None:
            self.null()
            return None
        return self.text(
            value,
            context,
            maximum_utf8_bytes=maximum_utf8_bytes,
            minimum_utf8_bytes=minimum_utf8_bytes,
        )

    def require_within(self, maximum_charge: int, context: str) -> int:
        if self.occurrence_charge > maximum_charge:
            raise ValueError(f"{context} exceeds its JSON occurrence bound")
        return self.canonical_bytes


def model_text_charge(maximum_utf8_bytes: int) -> int:
    return (
        JSON_TEXT_FIXED_CHARGE
        + JSON_TEXT_UTF8_MULTIPLIER * maximum_utf8_bytes
    )


def model_array_charge(maximum_length: int) -> int:
    return JSON_LIST_FIXED_CHARGE + JSON_LIST_SLOT_CHARGE * maximum_length


def model_object_charge(layout: JsonObjectLayout) -> int:
    return (
        JSON_OBJECT_FIXED_CHARGE
        + JSON_OBJECT_ENTRY_CHARGE * layout.entries
        + layout.key_occurrence_charge
    )


def model_mapping_charge(maximum_entries: int) -> int:
    return (
        JSON_OBJECT_FIXED_CHARGE
        + JSON_OBJECT_ENTRY_CHARGE * maximum_entries
    )


def canonical_byte_ceiling(maximum_occurrence_charge: int) -> int:
    """Bound canonical JSON bytes from the declared model charge.

    Two charge bytes cover every canonical output byte: the string coefficient
    covers the six-byte escape of a one-byte control scalar, while container
    and scalar coefficients dominate their syntax and decimal spellings.
    """

    return 2 * maximum_occurrence_charge


def encode_canonical_json(
    value: object,
    *,
    expected_bytes: int,
    byte_ceiling: int,
    encoder,
    context: str,
) -> bytes:
    encoded = encoder(value)
    if len(encoded) != expected_bytes:
        raise RuntimeError(f"{context} changed after JSON admission")
    if len(encoded) > byte_ceiling:
        raise RuntimeError(f"{context} exceeded its source-derived byte ceiling")
    return encoded


def require_payload_bytes(
    payload: object,
    *,
    byte_ceiling: int,
    context: str,
) -> bytes:
    """Reject type or size before UTF-8 decoding and JSON parser allocation."""

    if type(payload) is not bytes:
        raise TypeError(f"{context} must be exact bytes")
    if len(payload) > byte_ceiling:
        raise ValueError(f"{context} exceeds its source-derived byte ceiling")
    return payload


def _json_text_lengths(value: str) -> tuple[int, int]:
    """Return UTF-8 and canonical JSON byte lengths without encoded copies."""

    utf8_bytes = 0
    canonical_bytes = 2
    for character in value:
        codepoint = ord(character)
        if 0xD800 <= codepoint <= 0xDFFF:
            raise ValueError("JSON text must be valid Unicode")
        if codepoint in (0x22, 0x5C):
            utf8_bytes += 1
            canonical_bytes += 2
        elif codepoint in (0x08, 0x09, 0x0A, 0x0C, 0x0D):
            utf8_bytes += 1
            canonical_bytes += 2
        elif codepoint < 0x20:
            utf8_bytes += 1
            canonical_bytes += 6
        elif codepoint < 0x80:
            utf8_bytes += 1
            canonical_bytes += 1
        elif codepoint < 0x800:
            utf8_bytes += 2
            canonical_bytes += 2
        elif codepoint < 0x10000:
            utf8_bytes += 3
            canonical_bytes += 3
        else:
            utf8_bytes += 4
            canonical_bytes += 4
    return utf8_bytes, canonical_bytes
