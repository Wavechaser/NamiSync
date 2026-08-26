"""Ephemeral reviewed-root evidence and native admission primitives."""

from __future__ import annotations

import os
import stat as stat_module
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PureWindowsPath

from .models import VolumeEvidence, VolumeId
from .pathing import (
    PathValidationError,
    from_extended_length_path,
    is_path_below,
    lexical_absolute_path,
    lexical_path_chain,
    logical_error_text,
    to_extended_length_path,
    validate_relative_path,
)
from .scalars import require_safe_int


FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_ATTRIBUTE_OFFLINE = 0x00001000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x00040000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000
_MAX_DWORD = (1 << 32) - 1
_VOLUME_PATH_BUFFER_CHARS = 32_768
_VOLUME_TEXT_BUFFER_CHARS = 261


@dataclass(frozen=True, slots=True)
class RootAuthority:
    """Reviewed root facts; never a cached authorization to use the root."""

    logical_root: str
    reviewed_anchor: str | None = None
    expected_volume_id: VolumeId | None = None

    def __post_init__(self) -> None:
        logical_root = lexical_absolute_path(self.logical_root)
        object.__setattr__(self, "logical_root", logical_root)
        if self.reviewed_anchor is not None:
            reviewed_anchor = lexical_absolute_path(self.reviewed_anchor)
            if not is_path_below(logical_root, reviewed_anchor):
                raise PathValidationError(
                    "reviewed root is outside its reviewed volume anchor"
                )
            object.__setattr__(self, "reviewed_anchor", reviewed_anchor)
        if (
            self.expected_volume_id is not None
            and type(self.expected_volume_id) is not VolumeId
        ):
            raise TypeError("expected root volume has the wrong type")
        if self.expected_volume_id is not None:
            VolumeId(
                self.expected_volume_id.serial,
                self.expected_volume_id.fs_type,
            )


@dataclass(frozen=True, slots=True)
class NativeVolumeInfo:
    """Transient native volume facts shared by filesystem-facing adapters."""

    volume_id: VolumeId
    evidence: VolumeEvidence
    max_component_length: int
    filesystem_flags: int

    def __post_init__(self) -> None:
        if type(self.volume_id) is not VolumeId:
            raise TypeError("native volume identity has the wrong type")
        if type(self.evidence) is not VolumeEvidence:
            raise TypeError("native volume evidence has the wrong type")
        VolumeId(self.volume_id.serial, self.volume_id.fs_type)
        VolumeEvidence(
            self.evidence.label,
            self.evidence.device_id,
            self.evidence.clone_ambiguous,
        )
        require_safe_int(
            self.max_component_length,
            "maximum volume component length",
        )
        require_safe_int(self.filesystem_flags, "volume filesystem flags")
        if self.max_component_length > _MAX_DWORD:
            raise ValueError("maximum volume component length exceeds DWORD")
        if self.filesystem_flags > _MAX_DWORD:
            raise ValueError("volume filesystem flags exceed DWORD")


class RootAuthorityIssue(StrEnum):
    ANCHOR_UNAVAILABLE = "anchor_unavailable"
    ANCHOR_CHANGED = "anchor_changed"
    COMPONENT_UNAVAILABLE = "component_unavailable"
    PLACEHOLDER_COMPONENT = "placeholder_component"
    REPARSE_COMPONENT = "reparse_component"
    NON_DIRECTORY_COMPONENT = "non_directory_component"
    VOLUME_UNAVAILABLE = "volume_unavailable"
    VOLUME_CHANGED = "volume_changed"


class RootAuthorityError(OSError):
    """Typed failure to freshly admit a reviewed root or path component."""

    def __init__(
        self,
        issue: RootAuthorityIssue,
        logical_path: str,
        detail: str,
    ) -> None:
        super().__init__(detail)
        self.issue = issue
        self.logical_path = logical_path


AnchorProbe = Callable[[str], str]
VolumeProbe = Callable[[str], NativeVolumeInfo]
NoFollowStat = Callable[[str], os.stat_result]


def is_directory_stat(observed: os.stat_result) -> bool:
    """Return whether no-follow evidence describes a directory."""

    attributes = int(getattr(observed, "st_file_attributes", 0))
    return bool(
        stat_module.S_ISDIR(observed.st_mode)
        or attributes & FILE_ATTRIBUTE_DIRECTORY
    )


def is_reparse_stat(observed: os.stat_result) -> bool:
    """Return whether no-follow evidence describes any redirected entry."""

    attributes = int(getattr(observed, "st_file_attributes", 0))
    return bool(
        stat_module.S_ISLNK(observed.st_mode)
        or attributes & FILE_ATTRIBUTE_REPARSE_POINT
        or getattr(observed, "st_reparse_tag", 0)
    )


def is_placeholder_stat(observed: os.stat_result) -> bool:
    """Return whether no-follow evidence describes a recalled/offline entry."""

    attributes = int(getattr(observed, "st_file_attributes", 0))
    return bool(
        is_reparse_stat(observed)
        and attributes
        & (
            FILE_ATTRIBUTE_OFFLINE
            | FILE_ATTRIBUTE_RECALL_ON_OPEN
            | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
        )
    )


def current_volume_anchor(path: str | os.PathLike[str]) -> str:
    """Return the current lexical native volume root for one logical path.

    The non-Windows branch supplies only a development/test fallback for the
    Windows-targeted contract; its host root is not Windows mount authority.
    """

    logical = lexical_absolute_path(path)
    if os.name != "nt":
        # NamiSync does not treat this host-only fallback as production mount
        # boundary evidence.
        anchor = Path(logical).anchor
        if not anchor:
            raise PathValidationError("absolute path lacks a volume anchor")
        return anchor

    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    volume_path = ctypes.create_unicode_buffer(_VOLUME_PATH_BUFFER_CHARS)
    if not kernel32.GetVolumePathNameW(
        to_extended_length_path(logical),
        volume_path,
        len(volume_path),
    ):
        raise OSError(
            ctypes.get_last_error(),
            "GetVolumePathNameW failed",
            logical,
        )
    anchor = lexical_absolute_path(volume_path.value)
    if not is_path_below(logical, anchor):
        raise PathValidationError(
            "native volume root is outside the configured lexical path"
        )
    return anchor


def observe_native_volume(path: str | os.PathLike[str]) -> NativeVolumeInfo:
    """Freshly observe identity, mount evidence, and raw filesystem flags.

    Non-Windows identity/evidence exists only to keep development and portable
    contract tests usable; NamiSync's production authority is Windows-native.
    """

    logical = lexical_absolute_path(path)
    if os.name != "nt":
        observed = os.stat(
            to_extended_length_path(logical),
            follow_symlinks=False,
        )
        return NativeVolumeInfo(
            VolumeId(f"{observed.st_dev:x}", "UNKNOWN"),
            VolumeEvidence(device_id=current_volume_anchor(logical)),
            255,
            0,
        )

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    volume_path = ctypes.create_unicode_buffer(_VOLUME_PATH_BUFFER_CHARS)
    if not kernel32.GetVolumePathNameW(
        to_extended_length_path(logical),
        volume_path,
        len(volume_path),
    ):
        raise OSError(
            ctypes.get_last_error(),
            "GetVolumePathNameW failed",
            logical,
        )

    label = ctypes.create_unicode_buffer(_VOLUME_TEXT_BUFFER_CHARS)
    filesystem = ctypes.create_unicode_buffer(_VOLUME_TEXT_BUFFER_CHARS)
    serial = wintypes.DWORD()
    max_component = wintypes.DWORD()
    flags = wintypes.DWORD()
    if not kernel32.GetVolumeInformationW(
        volume_path.value,
        label,
        len(label),
        ctypes.byref(serial),
        ctypes.byref(max_component),
        ctypes.byref(flags),
        filesystem,
        len(filesystem),
    ):
        raise OSError(
            ctypes.get_last_error(),
            "GetVolumeInformationW failed",
            logical,
        )
    return NativeVolumeInfo(
        VolumeId(
            f"{serial.value:08X}",
            filesystem.value.upper() or "UNKNOWN",
        ),
        VolumeEvidence(
            label.value or None,
            from_extended_length_path(volume_path.value),
        ),
        int(max_component.value),
        int(flags.value),
    )


def admit_root_chain(
    authority: RootAuthority,
    *,
    lstat: NoFollowStat | None = None,
    anchor_probe: AnchorProbe | None = None,
) -> str:
    """Freshly admit a configured root's anchor and no-follow chain.

    This chain-only boundary deliberately performs no volume observation. It
    returns the admitted current/reviewed anchor for a caller that will perform
    a later volume-bound admission in the same operation.
    """

    stat_path = _native_lstat if lstat is None else lstat
    find_anchor = current_volume_anchor if anchor_probe is None else anchor_probe
    try:
        current_anchor = lexical_absolute_path(
            find_anchor(authority.logical_root)
        )
    except (OSError, ValueError) as error:
        raise RootAuthorityError(
            RootAuthorityIssue.ANCHOR_UNAVAILABLE,
            authority.logical_root,
            logical_error_text(error),
        ) from error

    admitted_anchor = current_anchor
    if authority.reviewed_anchor is not None:
        admitted_anchor = authority.reviewed_anchor
        if not _same_logical_path(current_anchor, admitted_anchor):
            raise RootAuthorityError(
                RootAuthorityIssue.ANCHOR_CHANGED,
                authority.logical_root,
                "reviewed root volume anchor changed",
            )

    try:
        root_chain = lexical_path_chain(
            authority.logical_root,
            trusted_anchor=admitted_anchor,
        )
    except (OSError, ValueError) as error:
        raise RootAuthorityError(
            RootAuthorityIssue.ANCHOR_UNAVAILABLE,
            authority.logical_root,
            logical_error_text(error),
        ) from error
    for component in root_chain:
        observed = _observe_component(component, stat_path)
        _require_ordinary_directory(component, observed)
    return admitted_anchor


def admit_root(
    authority: RootAuthority,
    *,
    lstat: NoFollowStat | None = None,
    anchor_probe: AnchorProbe | None = None,
    volume_probe: VolumeProbe | None = None,
) -> NativeVolumeInfo:
    """Freshly admit a configured root against its reviewed authority."""

    admitted_anchor = admit_root_chain(
        authority,
        lstat=lstat,
        anchor_probe=anchor_probe,
    )
    find_volume = observe_native_volume if volume_probe is None else volume_probe

    try:
        volume = find_volume(authority.logical_root)
    except (OSError, ValueError) as error:
        raise RootAuthorityError(
            RootAuthorityIssue.VOLUME_UNAVAILABLE,
            authority.logical_root,
            logical_error_text(error),
        ) from error
    if type(volume) is not NativeVolumeInfo:
        raise RootAuthorityError(
            RootAuthorityIssue.VOLUME_UNAVAILABLE,
            authority.logical_root,
            "volume observation returned an invalid value",
        )
    try:
        NativeVolumeInfo(
            volume.volume_id,
            volume.evidence,
            volume.max_component_length,
            volume.filesystem_flags,
        )
    except (TypeError, ValueError) as error:
        raise RootAuthorityError(
            RootAuthorityIssue.VOLUME_UNAVAILABLE,
            authority.logical_root,
            "volume observation returned invalid fields",
        ) from error
    evidence_anchor = volume.evidence.device_id
    if not isinstance(evidence_anchor, str) or not evidence_anchor:
        raise RootAuthorityError(
            RootAuthorityIssue.ANCHOR_UNAVAILABLE,
            authority.logical_root,
            "volume observation did not report its current anchor",
        )
    try:
        if not os.path.isabs(evidence_anchor):
            raise PathValidationError(
                "volume observation anchor is not absolute"
            )
        observed_anchor = lexical_absolute_path(evidence_anchor)
    except (OSError, ValueError) as error:
        raise RootAuthorityError(
            RootAuthorityIssue.ANCHOR_UNAVAILABLE,
            authority.logical_root,
            logical_error_text(error),
        ) from error
    if not _same_logical_path(observed_anchor, admitted_anchor):
        raise RootAuthorityError(
            RootAuthorityIssue.ANCHOR_CHANGED,
            authority.logical_root,
            "volume observation anchor changed during root admission",
        )
    if (
        authority.expected_volume_id is not None
        and volume.volume_id != authority.expected_volume_id
    ):
        raise RootAuthorityError(
            RootAuthorityIssue.VOLUME_CHANGED,
            authority.logical_root,
            "reviewed root volume identity changed",
        )
    return volume


def admit_existing_relative_chain(
    authority: RootAuthority,
    relative_path: str,
    *,
    lstat: NoFollowStat | None = None,
    include_leaf: bool = True,
) -> bool:
    """No-follow admit every existing component below an admitted root.

    A missing component ends inspection because every deeper component is also
    absent and returns ``False``. The caller retains policy for whether that
    absence is acceptable. Callers that already classify the final subject may
    exclude it while still requiring every admitted ancestor to be a directory.
    """

    canonical = validate_relative_path(relative_path)
    stat_path = _native_lstat if lstat is None else lstat
    parts = PureWindowsPath(canonical).parts
    inspected_parts = parts if include_leaf else parts[:-1]
    current = authority.logical_root
    for index, part in enumerate(inspected_parts):
        current = os.path.join(current, part)
        try:
            observed = stat_path(current)
        except FileNotFoundError:
            return False
        except (OSError, ValueError) as error:
            raise RootAuthorityError(
                RootAuthorityIssue.COMPONENT_UNAVAILABLE,
                current,
                logical_error_text(error),
            ) from error
        _require_unredirected(current, observed)
        if index < len(parts) - 1 and not is_directory_stat(observed):
            raise RootAuthorityError(
                RootAuthorityIssue.NON_DIRECTORY_COMPONENT,
                current,
                "path contains a nondirectory intermediate component",
            )
    return True


def _native_lstat(path: str) -> os.stat_result:
    return os.stat(
        to_extended_length_path(path),
        follow_symlinks=False,
    )


def _observe_component(
    path: str,
    lstat: NoFollowStat,
) -> os.stat_result:
    try:
        return lstat(path)
    except (OSError, ValueError) as error:
        raise RootAuthorityError(
            RootAuthorityIssue.COMPONENT_UNAVAILABLE,
            path,
            logical_error_text(error),
        ) from error


def _require_unredirected(path: str, observed: os.stat_result) -> None:
    if is_placeholder_stat(observed):
        raise RootAuthorityError(
            RootAuthorityIssue.PLACEHOLDER_COMPONENT,
            path,
            "path contains a placeholder component",
        )
    if is_reparse_stat(observed):
        raise RootAuthorityError(
            RootAuthorityIssue.REPARSE_COMPONENT,
            path,
            "path contains a reparse component",
        )


def _require_ordinary_directory(
    path: str,
    observed: os.stat_result,
) -> None:
    _require_unredirected(path, observed)
    if not is_directory_stat(observed):
        raise RootAuthorityError(
            RootAuthorityIssue.NON_DIRECTORY_COMPONENT,
            path,
            "reviewed root chain contains a nondirectory component",
        )


def _same_logical_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(
        os.path.normpath(right)
    )
