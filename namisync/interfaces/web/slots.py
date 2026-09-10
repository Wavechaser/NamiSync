"""Bounded process-local authority for native folder selections."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from uuid import uuid4

from namisync.workflows import (
    LocationBinding,
    LocationCandidate,
    LocationCandidateResult,
    LocationCandidateState,
    VolumeId,
)


_CAPACITY = 32
_TTL_SECONDS = 1_800.0
_TOKEN = re.compile(r"[0-9a-f]{32}")
_SLOT_ID = re.compile(r"slot-[0-9a-f]{32}")


class SlotUnavailableError(LookupError):
    """An opaque folder slot is absent, expired, or purpose-mismatched."""


@dataclass(slots=True)
class _FolderSlot:
    candidate: LocationCandidate
    purpose: str
    display: str
    expires_at: float
    last_used: float
    legacy_path: bool = False
    binding: LocationBinding | None = None
    candidates: tuple[str, ...] = ()


class FolderSlotTable:
    """Retain native paths behind fixed-lifetime, purpose-bound opaque ids."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        token: Callable[[], str] | None = None,
    ) -> None:
        if not callable(clock):
            raise TypeError("clock must be callable")
        if token is not None and not callable(token):
            raise TypeError("token must be callable")
        self._clock = clock
        self._token = token if token is not None else _new_token
        self._entries: dict[str, _FolderSlot] = {}
        self._lock = Lock()

    def store(
        self,
        candidate: LocationCandidate | str,
        *,
        purpose: str,
        display: str | None = None,
    ) -> tuple[str, str]:
        """Insert one native selection and return only opaque presentation data."""

        if type(purpose) is not str or purpose not in {
            "source",
            "target",
            "inventory",
        }:
            raise ValueError("folder slot purpose is invalid")
        legacy_path = type(candidate) is str
        if legacy_path:
            candidate = LocationCandidate.literal(candidate)
        if type(candidate) is not LocationCandidate:
            raise TypeError("folder slot candidate must be exact")
        candidate.__post_init__()
        if display is None:
            display = (
                candidate.path
                if candidate.path is not None
                else str(candidate.location_id)
            )
        _require_valid_text(display, label="display")

        with self._lock:
            now = self._clock()
            self._sweep(now)
            slot_id = self._mint_id()
            if len(self._entries) == _CAPACITY:
                evicted = min(
                    self._entries,
                    key=lambda candidate: (
                        self._entries[candidate].last_used,
                        candidate,
                    ),
                )
                del self._entries[evicted]
            self._entries[slot_id] = _FolderSlot(
                candidate=candidate,
                purpose=purpose,
                display=display,
                expires_at=now + _TTL_SECONDS,
                last_used=now,
                legacy_path=legacy_path,
            )
            return slot_id, display

    def resolve(self, slot_id: str, *, purpose: str) -> LocationCandidate:
        with self._lock:
            now = self._clock()
            self._sweep(now)
            if type(slot_id) is not str or _SLOT_ID.fullmatch(slot_id) is None:
                raise SlotUnavailableError("folder slot is unavailable")
            entry = self._entries.get(slot_id)
            if (
                entry is None
                or entry.purpose != purpose
                or entry.binding is not None
            ):
                raise SlotUnavailableError("folder slot is unavailable")
            entry.last_used = now
            return entry.candidate

    def store_continuation(
        self,
        candidate: LocationCandidate,
        result: LocationCandidateResult,
        *,
        purpose: str,
        admit: Callable[[str, dict[str, object]], object],
    ) -> str:
        """Retain one non-startable ambiguity in the shared slot population."""

        if purpose not in {"source", "target", "inventory"}:
            raise ValueError("folder slot purpose is invalid")
        if type(candidate) is not LocationCandidate:
            raise TypeError("folder slot candidate must be exact")
        if (
            type(result) is not LocationCandidateResult
            or result.state is not LocationCandidateState.AMBIGUOUS
            or type(result.binding) is not LocationBinding
            or not result.candidates
        ):
            raise ValueError("folder slot continuation must be ambiguous")
        if not callable(admit):
            raise TypeError("folder slot response admitter must be callable")
        candidate.__post_init__()
        result.__post_init__()
        retained_candidate = LocationCandidate(
            candidate.kind,
            candidate.path,
            candidate.location_id,
            candidate.selected_mount,
        )
        source_binding = result.binding
        retained_binding = LocationBinding(
            VolumeId(source_binding.volume_id.serial, source_binding.volume_id.fs_type),
            source_binding.volume_relative_path,
            source_binding.selected_mount,
            tuple(source_binding.expected_mounts),
            source_binding.explicit_ambiguity_choice,
            source_binding.location_id,
        )
        retained_candidates = tuple(result.candidates)
        projection = _continuation_projection(
            retained_candidate,
            retained_binding,
            retained_candidates,
        )
        with self._lock:
            now = self._clock()
            self._sweep(now)
            slot_id = self._mint_id()
            admitted = _continuation_from_projection(admit(slot_id, projection))
            if admitted != (
                retained_candidate,
                retained_binding,
                retained_candidates,
            ):
                raise RuntimeError(
                    "folder slot response admission changed continuation state"
                )
            retained_candidate, retained_binding, retained_candidates = admitted
            if len(self._entries) == _CAPACITY:
                evicted = min(
                    self._entries,
                    key=lambda item: (self._entries[item].last_used, item),
                )
                del self._entries[evicted]
            self._entries[slot_id] = _FolderSlot(
                retained_candidate,
                purpose,
                result.root_path or retained_candidate.path or "Remembered location",
                now + _TTL_SECONDS,
                now,
                binding=retained_binding,
                candidates=retained_candidates,
            )
        return slot_id

    def resolve_continuation(
        self,
        slot_id: str,
        *,
        purpose: str,
        mount_index: int,
    ) -> tuple[LocationCandidate, LocationBinding, tuple[str, ...], str]:
        with self._lock:
            now = self._clock()
            self._sweep(now)
            if (
                type(slot_id) is not str
                or _SLOT_ID.fullmatch(slot_id) is None
                or type(mount_index) is not int
                or mount_index < 0
            ):
                raise SlotUnavailableError("folder slot is unavailable")
            entry = self._entries.get(slot_id)
            if (
                entry is None
                or entry.purpose != purpose
                or entry.binding is None
                or mount_index >= len(entry.candidates)
            ):
                raise SlotUnavailableError("folder slot is unavailable")
            entry.last_used = now
            return (
                entry.candidate,
                entry.binding,
                entry.candidates,
                entry.candidates[mount_index],
            )

    def resolve_pair(
        self,
        source_id: str,
        target_id: str,
    ) -> tuple[LocationCandidate, LocationCandidate] | tuple[str, str]:
        """Atomically resolve one live purpose-correct pair without consuming it."""

        with self._lock:
            now = self._clock()
            self._sweep(now)
            if (
                type(source_id) is not str
                or _SLOT_ID.fullmatch(source_id) is None
                or type(target_id) is not str
                or _SLOT_ID.fullmatch(target_id) is None
            ):
                raise SlotUnavailableError("folder slot is unavailable")
            source = self._entries.get(source_id)
            target = self._entries.get(target_id)
            if (
                source is None
                or target is None
                or source.purpose != "source"
                or target.purpose != "target"
                or source.binding is not None
                or target.binding is not None
            ):
                raise SlotUnavailableError("folder slot is unavailable")
            source.last_used = now
            target.last_used = now
            if source.legacy_path and target.legacy_path:
                assert source.candidate.path is not None
                assert target.candidate.path is not None
                return source.candidate.path, target.candidate.path
            return source.candidate, target.candidate

    def _sweep(self, now: float) -> None:
        expired = tuple(
            slot_id
            for slot_id, entry in self._entries.items()
            if entry.expires_at <= now
        )
        for slot_id in expired:
            del self._entries[slot_id]

    def _mint_id(self) -> str:
        while True:
            token = self._token()
            if type(token) is not str or _TOKEN.fullmatch(token) is None:
                raise ValueError("folder slot token must be 32 lowercase hex digits")
            slot_id = f"slot-{token}"
            if slot_id not in self._entries:
                return slot_id


def _continuation_projection(
    candidate: LocationCandidate,
    binding: LocationBinding,
    candidates: tuple[str, ...],
) -> dict[str, object]:
    return {
        "candidate": {
            "kind": candidate.kind.value,
            "path": candidate.path,
            "location_id": candidate.location_id,
            "selected_mount": candidate.selected_mount,
        },
        "binding": {
            "volume_id": {
                "serial": binding.volume_id.serial,
                "fs_type": binding.volume_id.fs_type,
            },
            "volume_relative_path": binding.volume_relative_path,
            "selected_mount": binding.selected_mount,
            "expected_mounts": tuple(binding.expected_mounts),
            "explicit_ambiguity_choice": binding.explicit_ambiguity_choice,
            "location_id": binding.location_id,
        },
        "candidates": tuple(candidates),
    }


def _continuation_from_projection(
    value: object,
) -> tuple[LocationCandidate, LocationBinding, tuple[str, ...]]:
    message = "folder slot response admission returned invalid continuation state"
    if type(value) is not dict or set(value) != {
        "candidate", "binding", "candidates",
    }:
        raise RuntimeError(message)
    candidate_value = value["candidate"]
    binding_value = value["binding"]
    candidates = value["candidates"]
    if (
        type(candidate_value) is not dict
        or set(candidate_value) != {
            "kind", "path", "location_id", "selected_mount",
        }
        or type(binding_value) is not dict
        or set(binding_value) != {
            "volume_id",
            "volume_relative_path",
            "selected_mount",
            "expected_mounts",
            "explicit_ambiguity_choice",
            "location_id",
        }
        or type(candidates) is not tuple
    ):
        raise RuntimeError(message)
    volume_value = binding_value["volume_id"]
    if type(volume_value) is not dict or set(volume_value) != {"serial", "fs_type"}:
        raise RuntimeError(message)
    try:
        if candidate_value["kind"] == "literal_path":
            if candidate_value["location_id"] is not None:
                raise ValueError(message)
            candidate = LocationCandidate.literal(
                candidate_value["path"],
                selected_mount=candidate_value["selected_mount"],
            )
        elif candidate_value["kind"] == "remembered_location":
            if candidate_value["path"] is not None:
                raise ValueError(message)
            candidate = LocationCandidate.remembered(
                candidate_value["location_id"],
                selected_mount=candidate_value["selected_mount"],
            )
        else:
            raise ValueError(message)
        binding = LocationBinding(
            VolumeId(volume_value["serial"], volume_value["fs_type"]),
            binding_value["volume_relative_path"],
            binding_value["selected_mount"],
            binding_value["expected_mounts"],
            binding_value["explicit_ambiguity_choice"],
            binding_value["location_id"],
        )
        retained_candidates = tuple(candidates)
        for candidate_mount in retained_candidates:
            if type(candidate_mount) is not str:
                raise TypeError(message)
    except (TypeError, ValueError) as error:
        raise RuntimeError(message) from error
    return candidate, binding, retained_candidates


def _new_token() -> str:
    return uuid4().hex


def _require_valid_text(value: object, *, label: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"folder slot {label} must be a nonempty string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"folder slot {label} must be valid Unicode") from error


__all__ = ["FolderSlotTable", "SlotUnavailableError"]
