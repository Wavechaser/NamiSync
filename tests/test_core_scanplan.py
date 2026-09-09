"""Shared path and immutable evidence contract tests."""

from __future__ import annotations

from dataclasses import dataclass, fields, make_dataclass, replace
import hashlib
import json
import os
from pathlib import Path

import pytest

import namisync.core.models as model_contracts
import namisync.core.pathing as path_contracts
import namisync.core.planning as planning_contracts
import namisync.core.scalars as scalar_contracts
from namisync.core.models import IgnoreSet
from namisync.core.pathing import (
    PathValidationError,
    fold_validated_path,
    from_extended_length_path,
    lexical_absolute_path,
    lexical_path_chain,
    logical_error_text,
    normalize_relative_path,
    to_extended_length_path,
    validate_relative_path,
)
from namisync.core.planning import (
    canonical_json_bytes,
    plan_fingerprint,
    policy_fingerprint,
    serialize_plan,
)

from _identity_epoch5 import frozen_vector
from _identity_hash_fixtures import (
    MAX_FILE_INDEX,
    custom_options,
    hash_fixtures,
    two_copy_plan,
)


@pytest.mark.parametrize(
    "value",
    [
        r"C:\escape.txt",
        r"\\server\share\escape.txt",
        r"\\?\C:\escape.txt",
        r"\\.\C:\escape.txt",
        r"..\escape.txt",
        r"folder\..\escape.txt",
        r"folder\\file.txt",
        r"folder\file.txt.",
        r"folder\NUL.txt",
        "folder\x00file.txt",
        "bad_" + chr(0xDCFF) + ".txt",
    ],
)
def test_relative_path_validation_rejects_windows_escape_and_ambiguity(value: str) -> None:
    with pytest.raises(PathValidationError):
        validate_relative_path(value)


@pytest.mark.parametrize(
    "basename",
    [
        "conin$",
        "ConOut$",
        "cOm¹",
        "COM²",
        "com³",
        "lPt¹",
        "LPT²",
        "lpt³",
    ],
)
@pytest.mark.parametrize("suffix", ["", ".txt"])
def test_relative_path_validation_rejects_additional_documented_windows_devices(
    basename: str,
    suffix: str,
) -> None:
    with pytest.raises(PathValidationError, match="Windows device"):
        validate_relative_path(f"folder\\{basename}{suffix}")


def test_relative_path_key_normalizes_separator_and_ordinary_case_without_casefold_expansion() -> None:
    assert normalize_relative_path("Folder/file.txt") == normalize_relative_path(r"folder\FILE.TXT")
    assert normalize_relative_path("Straße.txt") != normalize_relative_path("strasse.txt")


@pytest.mark.parametrize(
    ("value", "allow_root"),
    (
        ("Folder/file.txt", False),
        ("Straße/ß.txt", False),
        ("", True),
    ),
)
def test_validated_path_fold_matches_normalizing_entry_point(
    value: str,
    allow_root: bool,
) -> None:
    canonical = validate_relative_path(value, allow_root=allow_root)

    assert fold_validated_path(canonical) == normalize_relative_path(
        value,
        allow_root=allow_root,
    )


def test_source_records_and_mapping_pair_validate_each_path_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_validate = model_contracts.validate_relative_path
    planning_validate = planning_contracts.validate_relative_path
    model_calls: list[str] = []
    path_calls: list[str] = []
    planning_calls: list[str] = []

    def observe_model(value: str, *, allow_root: bool = False) -> str:
        model_calls.append(value)
        return model_validate(value, allow_root=allow_root)

    def observe_planning(value: str, *, allow_root: bool = False) -> str:
        planning_calls.append(value)
        return planning_validate(value, allow_root=allow_root)

    def observe_path(value: str, *, allow_root: bool = False) -> str:
        path_calls.append(value)
        return path_validate(value, allow_root=allow_root)

    monkeypatch.setattr(
        model_contracts,
        "validate_relative_path",
        observe_model,
    )
    monkeypatch.setattr(
        planning_contracts,
        "validate_relative_path",
        observe_planning,
    )
    path_validate = path_contracts.validate_relative_path
    monkeypatch.setattr(
        path_contracts,
        "validate_relative_path",
        observe_path,
    )
    metadata = model_contracts.MetadataSnapshot(0, None)
    model_contracts.FileRecord(
        "file.txt",
        "FILE.TXT",
        1,
        1,
        None,
        1,
        metadata,
    )
    model_contracts.DirRecord(
        "folder",
        "FOLDER",
        1,
        metadata,
        None,
    )
    model_contracts.UnsupportedRecord(
        "other",
        "OTHER",
        model_contracts.UnsupportedReason.UNKNOWN_TYPE,
    )
    planning_contracts.MappingPair(
        "SOURCE",
        "target.txt",
        "TARGET.TXT",
        model_contracts.FileIdentity("serial", 1),
        None,
    )

    assert model_calls == ["file.txt", "folder", "other"]
    assert path_calls == []
    assert planning_calls == ["target.txt"]


def test_long_relative_path_is_valid() -> None:
    path = "\\".join(["directory" * 10] * 4 + ["file.bin"])
    assert len(path) > 260
    assert validate_relative_path(path) == path


def test_relative_path_accepts_complete_utf16_limit_and_rejects_next_unit() -> None:
    exact = "a" * 32_767

    assert validate_relative_path(exact) is exact
    with pytest.raises(PathValidationError, match="UTF-16 path bound"):
        validate_relative_path(exact + "a")


def test_volume_root_profile_and_warning_source_bounds_are_exact() -> None:
    assert model_contracts.MAX_ROOT_ID_UTF8_BYTES == (
        scalar_contracts.MAX_REQUEST_ID_UTF8_BYTES
        + len("inventory:".encode("utf-8"))
        + len(":refresh:".encode("utf-8"))
        + len(str(scalar_contracts.MAX_SAFE_INTEGER).encode("ascii"))
    )
    volume_text = "\U0001f600" * 130
    model_contracts.VolumeId(volume_text, volume_text)
    model_contracts.VolumeEvidence(volume_text, "p" * 32_767, False)
    model_contracts.CapabilityProfile(
        volume_text,
        1,
        True,
        None,
        32_767,
        False,
        True,
    )
    model_contracts.Root(
        r"C:\root", "r" * model_contracts.MAX_ROOT_ID_UTF8_BYTES
    )
    warning = model_contracts.ScanWarning(
        model_contracts.ScanWarningCode.ACCESS_DENIED,
        None,
        "\u00e9" * 512,
    )

    assert warning.detail == "\u00e9" * 512
    with pytest.raises(ValueError, match="UTF-16 text bound"):
        model_contracts.VolumeId(volume_text + "x", "NTFS")
    with pytest.raises(ValueError, match="UTF-16 path bound"):
        model_contracts.VolumeEvidence(device_id="p" * 32_768)
    with pytest.raises(ValueError, match="maximum path"):
        model_contracts.CapabilityProfile(
            "NTFS", 1, True, None, 32_768, False, False
        )
    with pytest.raises(ValueError, match="UTF-8 text bound"):
        model_contracts.Root(
            r"C:\root", "r" * (model_contracts.MAX_ROOT_ID_UTF8_BYTES + 1)
        )
    assert model_contracts.ScanWarning(
        model_contracts.ScanWarningCode.ACCESS_DENIED,
        None,
        ("\u00e9" * 512) + "x",
    ).detail == ""


def _assert_declared_slots(value: object) -> None:
    assert not hasattr(value, "__dict__")
    assert type(value).__slots__ == tuple(field.name for field in fields(value))
    with pytest.raises(AttributeError):
        object.__setattr__(value, "_undeclared", object())


def _file_stat_with(**changes: object) -> model_contracts.FileStat:
    fields = {
        "kind": model_contracts.EntryKind.FILE,
        "size": 1,
        "mtime_ns": 1,
        "file_identity": None,
        "nlink": 1,
        "metadata": model_contracts.MetadataSnapshot(0, None),
    }
    fields.update(changes)
    return model_contracts.FileStat(**fields)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "construct",
    (
        pytest.param(
            lambda: model_contracts.FileIdentity("", 1), id="identity-empty"
        ),
        pytest.param(
            lambda: model_contracts.FileIdentity(1, 1), id="identity-nontext"
        ),
        pytest.param(
            lambda: model_contracts.FileIdentity("serial", True),
            id="identity-bool-index",
        ),
        pytest.param(
            lambda: model_contracts.FileIdentity("serial", -1),
            id="identity-negative-index",
        ),
        pytest.param(
            lambda: model_contracts.FileIdentity(
                "serial", scalar_contracts.MAX_FILE_INDEX_128 + 1
            ),
            id="identity-over-128",
        ),
        pytest.param(
            lambda: model_contracts.MetadataSnapshot(True, None),
            id="metadata-bool-attributes",
        ),
        pytest.param(
            lambda: model_contracts.MetadataSnapshot(0, True),
            id="metadata-bool-created",
        ),
        pytest.param(
            lambda: model_contracts.MetadataSnapshot(0, -1),
            id="metadata-created-negative",
        ),
        pytest.param(
            lambda: model_contracts.MetadataSnapshot(
                0, scalar_contracts.MAX_SIGNED_64 + 1
            ),
            id="metadata-created-over-s64",
        ),
        pytest.param(lambda: _file_stat_with(kind="file"), id="stat-wrong-kind"),
        pytest.param(lambda: _file_stat_with(size=True), id="stat-bool-size"),
        pytest.param(lambda: _file_stat_with(size=-1), id="stat-negative-size"),
        pytest.param(
            lambda: _file_stat_with(
                mtime_ns=scalar_contracts.MAX_SIGNED_64 + 1
            ),
            id="stat-over-s64-mtime",
        ),
        pytest.param(lambda: _file_stat_with(nlink=True), id="stat-bool-nlink"),
        pytest.param(lambda: _file_stat_with(nlink=0), id="stat-zero-nlink"),
        pytest.param(
            lambda: _file_stat_with(file_identity=object()),
            id="stat-wrong-identity-type",
        ),
        pytest.param(
            lambda: _file_stat_with(metadata=object()),
            id="stat-wrong-metadata-type",
        ),
    ),
)
def test_file_stat_leaf_constructors_reject_invalid_inputs(construct) -> None:
    with pytest.raises((TypeError, ValueError)):
        construct()


@pytest.mark.parametrize(
    ("kind", "identity", "created_ns"),
    (
        (
            model_contracts.EntryKind.FILE,
            model_contracts.FileIdentity("serial", 1),
            2,
        ),
        (
            model_contracts.EntryKind.FILE,
            model_contracts.FileIdentity("serial", 1),
            None,
        ),
        (model_contracts.EntryKind.FILE, None, 2),
        (model_contracts.EntryKind.FILE, None, None),
        (
            model_contracts.EntryKind.DIRECTORY,
            model_contracts.FileIdentity("serial", 1),
            2,
        ),
    ),
    ids=(
        "identity-created",
        "identity-no-created",
        "no-identity-created",
        "no-identity-no-created",
        "directory",
    ),
)
def test_snapshot_file_stat_adopts_exact_base_without_reconstruction(
    kind,
    identity,
    created_ns,
) -> None:
    stat = model_contracts.FileStat(
        kind,
        3,
        4,
        identity,
        5,
        model_contracts.MetadataSnapshot(6, created_ns),
    )

    assert model_contracts.snapshot_file_stat(stat) == stat


@pytest.mark.parametrize("field", ("identity", "metadata", "stat-subclass"))
def test_snapshot_file_stat_rejects_wrong_nested_exact_types(field: str) -> None:
    class IdentitySubclass(model_contracts.FileIdentity):
        pass

    class MetadataSubclass(model_contracts.MetadataSnapshot):
        pass

    class StatSubclass(model_contracts.FileStat):
        pass

    identity = model_contracts.FileIdentity("serial", 1)
    metadata = model_contracts.MetadataSnapshot(2, 3)
    stat = model_contracts.FileStat(
        model_contracts.EntryKind.FILE, 4, 5, identity, 6, metadata
    )
    if field == "identity":
        object.__setattr__(stat, "file_identity", IdentitySubclass("serial", 1))
    elif field == "metadata":
        object.__setattr__(stat, "metadata", MetadataSubclass(2, 3))
    else:
        stat = StatSubclass(
            model_contracts.EntryKind.FILE, 4, 5, identity, 6, metadata
        )

    with pytest.raises(TypeError):
        model_contracts.snapshot_file_stat(stat)


@pytest.mark.parametrize(
    "expected",
    (
        (model_contracts.EntryKind.FILE, 1, 2, "serial", 3, 4, 5, 6),
        (model_contracts.EntryKind.FILE, 1, 2, "serial", 3, 4, 5, None),
        (model_contracts.EntryKind.FILE, 1, 2, None, None, 4, 5, 6),
        (model_contracts.EntryKind.DIRECTORY, 1, 2, None, None, 4, 5, None),
        (
            model_contracts.EntryKind.FILE,
            scalar_contracts.MAX_SIGNED_64,
            scalar_contracts.MAX_SIGNED_64,
            "serial",
            scalar_contracts.MAX_FILE_INDEX_128,
            scalar_contracts.MAX_SAFE_INTEGER,
            scalar_contracts.MAX_SAFE_INTEGER,
            scalar_contracts.MAX_SIGNED_64,
        ),
    ),
    ids=(
        "identity-created-file",
        "identity-no-created-file",
        "no-identity-created-file",
        "no-identity-no-created-directory",
        "scalar-boundaries",
    ),
)
def test_file_stat_fact_preserves_all_eight_facts(expected) -> None:
    kind, size, mtime_ns, serial, file_index, nlink, attributes, created_ns = expected
    identity = (
        None
        if serial is None
        else model_contracts.FileIdentity(serial, file_index)
    )
    stat = model_contracts.FileStat(
        kind,
        size,
        mtime_ns,
        identity,
        nlink,
        model_contracts.MetadataSnapshot(attributes, created_ns),
    )

    assert model_contracts.file_stat_fact(stat) == expected


def test_scan_model_contracts_are_exactly_slotted() -> None:
    volume = model_contracts.VolumeId("serial", "NTFS")
    evidence = model_contracts.VolumeEvidence("source", None, False)
    profile = model_contracts.CapabilityProfile(
        "NTFS", 1, True, None, 32_767, True, True
    )
    identity = model_contracts.FileIdentity("serial", 1)
    metadata = model_contracts.MetadataSnapshot(0, None)
    stat = model_contracts.FileStat(
        model_contracts.EntryKind.FILE,
        1,
        1,
        identity,
        1,
        metadata,
    )
    root = model_contracts.Root(r"C:\source", "source")
    file_record = model_contracts.FileRecord(
        "file.bin", "FILE.BIN", 1, 1, identity, 1, metadata
    )
    directory_record = model_contracts.DirRecord(
        "folder", "FOLDER", 1, metadata, identity
    )
    unsupported_record = model_contracts.UnsupportedRecord(
        "link.bin",
        "LINK.BIN",
        model_contracts.UnsupportedReason.REPARSE_POINT,
    )
    warning = model_contracts.ScanWarning(
        model_contracts.ScanWarningCode.DISAPPEARED,
        "gone.bin",
    )
    scope = model_contracts.ScanScope.full()
    ignores = model_contracts.IgnoreSet()
    result = model_contracts.ScanResult(
        root,
        volume,
        evidence,
        profile,
        (file_record,),
        (directory_record,),
        (unsupported_record,),
        (warning,),
        scope,
        True,
    )

    values = (
        volume,
        evidence,
        profile,
        identity,
        metadata,
        stat,
        root,
        file_record,
        directory_record,
        unsupported_record,
        warning,
        scope,
        ignores,
        result,
    )
    assert tuple(type(value).__name__ for value in values) == (
        "VolumeId",
        "VolumeEvidence",
        "CapabilityProfile",
        "FileIdentity",
        "MetadataSnapshot",
        "FileStat",
        "Root",
        "FileRecord",
        "DirRecord",
        "UnsupportedRecord",
        "ScanWarning",
        "ScanScope",
        "IgnoreSet",
        "ScanResult",
    )
    for value in values:
        _assert_declared_slots(value)


def _valid_scan_result() -> model_contracts.ScanResult:
    metadata = model_contracts.MetadataSnapshot(0, None)
    identity = model_contracts.FileIdentity("serial", 1)
    return model_contracts.ScanResult(
        model_contracts.Root(r"C:\source", "source"),
        model_contracts.VolumeId("serial", "NTFS"),
        model_contracts.VolumeEvidence("source", None, False),
        model_contracts.CapabilityProfile(
            "NTFS", 1, True, None, 32_767, True, True
        ),
        (
            model_contracts.FileRecord(
                "file.bin", "FILE.BIN", 1, 1, identity, 1, metadata
            ),
        ),
        (model_contracts.DirRecord("folder", "FOLDER", 1, metadata, identity),),
        (
            model_contracts.UnsupportedRecord(
                "link.bin", "LINK.BIN", model_contracts.UnsupportedReason.REPARSE_POINT
            ),
        ),
        (
            model_contracts.ScanWarning(
                model_contracts.ScanWarningCode.DISAPPEARED, "gone.bin"
            ),
        ),
        model_contracts.ScanScope.full(),
        True,
    )


@pytest.mark.parametrize("population", ("files", "directories", "unsupported", "warnings"))
def test_scan_result_constructor_rejects_invalid_population_member(
    population: str,
) -> None:
    value = _valid_scan_result()
    values = [getattr(value, field.name) for field in fields(value)]
    index = {field.name: position for position, field in enumerate(fields(value))}
    values[index[population]] = (object(),)

    with pytest.raises(TypeError):
        model_contracts.ScanResult(*values)


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    (
        ("root", object()),
        ("volume_id", object()),
        ("volume_evidence", object()),
        ("profile", object()),
        ("files", []),
        ("directories", []),
        ("unsupported", []),
        ("warnings", []),
        ("scope", object()),
        ("complete", 1),
    ),
    ids=(
        "root",
        "volume-id",
        "volume-evidence",
        "profile",
        "files-tuple",
        "directories-tuple",
        "unsupported-tuple",
        "warnings-tuple",
        "scope",
        "complete",
    ),
)
def test_scan_result_constructor_rejects_invalid_top_level_shape(
    field_name: str,
    replacement: object,
) -> None:
    value = _valid_scan_result()
    values = [getattr(value, field.name) for field in fields(value)]
    index = {field.name: position for position, field in enumerate(fields(value))}
    values[index[field_name]] = replacement

    with pytest.raises(TypeError):
        model_contracts.ScanResult(*values)


def test_planning_contracts_are_exactly_slotted() -> None:
    plans, _ = hash_fixtures(True)
    reviewed = plans["all_fields"]
    values = (
        planning_contracts.PreservationPolicy(),
        planning_contracts.FilterSet(),
        planning_contracts.DestinationAssignment(
            "a.txt", "A.TXT", "a.txt", "A.TXT"
        ),
        planning_contracts.Assignment("identity", "1", ()),
        planning_contracts.IdentityDestinationPolicy(),
        planning_contracts.SyncOptions(),
        planning_contracts.MappingPair(
            "A.TXT",
            "a.txt",
            "A.TXT",
            model_contracts.FileIdentity("A", 1),
            None,
        ),
        planning_contracts.MappingSnapshot.empty(),
        planning_contracts.Scope.everything(),
        reviewed.operations[0],
        reviewed,
    )
    assert tuple(type(value).__name__ for value in values) == (
        "PreservationPolicy",
        "FilterSet",
        "DestinationAssignment",
        "Assignment",
        "IdentityDestinationPolicy",
        "SyncOptions",
        "MappingPair",
        "MappingSnapshot",
        "Scope",
        "PlanOperation",
        "Plan",
    )
    for value in values:
        _assert_declared_slots(value)


def test_source_contracts_reject_coercible_scalar_fields() -> None:
    class Text(str):
        pass

    with pytest.raises(TypeError):
        model_contracts.VolumeId(Text("serial"), "NTFS")
    with pytest.raises(TypeError):
        model_contracts.VolumeEvidence(clone_ambiguous=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        model_contracts.CapabilityProfile(
            "NTFS", 1, 1, None, 32_767, False, False  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        model_contracts.ScanWarning(
            "access_denied", None  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("record_factory", "message"),
    (
        pytest.param(
            lambda key, metadata: model_contracts.FileRecord(
                "file.txt", key, 1, 1, None, 1, metadata
            ),
            "file path key",
            id="file",
        ),
        pytest.param(
            lambda key, metadata: model_contracts.DirRecord(
                "folder", key, 1, metadata, None
            ),
            "directory path key",
            id="directory",
        ),
        pytest.param(
            lambda key, _metadata: model_contracts.UnsupportedRecord(
                "other", key, model_contracts.UnsupportedReason.UNKNOWN_TYPE
            ),
            "unsupported path key",
            id="unsupported",
        ),
    ),
)
def test_source_records_reject_coercible_path_keys(record_factory, message: str) -> None:
    class Text(str):
        pass

    with pytest.raises(TypeError, match=message):
        record_factory(Text("FORGED"), model_contracts.MetadataSnapshot(0, None))


def test_source_projections_revalidate_forged_exact_dataclasses() -> None:
    root = model_contracts.Root(r"C:\root", "source")
    volume = model_contracts.VolumeId("serial", "NTFS")
    object.__setattr__(
        root,
        "root_id",
        "r" * (model_contracts.MAX_ROOT_ID_UTF8_BYTES + 1),
    )
    object.__setattr__(volume, "fs_type", "f" * 261)

    with pytest.raises(ValueError, match="UTF-8 text bound"):
        model_contracts.root_projection(root)
    with pytest.raises(ValueError, match="UTF-16 text bound"):
        model_contracts.volume_id_projection(volume)


def test_filter_contract_charges_raw_shape_before_canonicalization() -> None:
    exact = tuple(f"{index:02x}" + ("x" * 1_022) for index in range(16))
    assert sum(len(value.encode("utf-8")) for value in exact) == 16_384
    assert planning_contracts.FilterSet(exact).patterns == tuple(sorted(exact))

    with pytest.raises(ValueError, match="total limit"):
        planning_contracts.FilterSet((*exact, "x"))
    with pytest.raises(ValueError, match="64-pattern"):
        planning_contracts.FilterSet(tuple(str(index) for index in range(65)))
    with pytest.raises(ValueError, match="total limit"):
        planning_contracts.FilterSet(("x" * 1_024,) * 17)
    with pytest.raises(ValueError, match="UTF-8 text bound"):
        planning_contracts.FilterSet(("/" * 1_025,))


def test_scan_scope_combined_source_population_has_exact_preallocation_wall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exact = ("a",) * model_contracts.SCAN_SCOPE_ENTRY_LIMIT
    assert model_contracts.ScanScope.selected(exact).selected_paths == ("a",)

    def forbidden_normalize(*_args, **_kwargs):
        raise AssertionError("excess scope must not normalize any path")

    monkeypatch.setattr(
        model_contracts,
        "normalize_relative_path",
        forbidden_normalize,
    )
    with pytest.raises(ValueError, match="120000-entry limit"):
        model_contracts.ScanScope.scoped(
            selected_paths=("a",) * 60_000,
            subtree_roots=("b",) * 60_001,
        )


def test_filter_and_assignment_contracts_reject_aliasable_shapes() -> None:
    class Text(str):
        pass

    class TupleAlias(tuple):
        pass

    with pytest.raises(TypeError, match="tuple"):
        planning_contracts.FilterSet(TupleAlias(("*.tmp",)))
    with pytest.raises(TypeError, match="filter pattern"):
        planning_contracts.FilterSet((Text("*.tmp"),))
    with pytest.raises(TypeError, match="source assignment path"):
        planning_contracts.DestinationAssignment(
            Text("a.txt"), "A.TXT", "a.txt", "A.TXT"
        )
    with pytest.raises(TypeError, match="tuple"):
        planning_contracts.Assignment(
            "identity", "1", TupleAlias(())
        )


def test_assignment_rejects_n_plus_one_items_before_item_traversal() -> None:
    item = planning_contracts.DestinationAssignment(
        "a.txt", "A.TXT", "a.txt", "A.TXT"
    )

    with pytest.raises(ValueError, match="plan row limit"):
        planning_contracts.Assignment(
            "identity",
            "1",
            (item,) * (planning_contracts.ASSIGNMENT_ITEM_LIMIT + 1),
        )


def test_policy_fingerprint_snapshots_each_hostile_property_once() -> None:
    class HostilePolicy:
        def __init__(self) -> None:
            self.name_reads = 0
            self.version_reads = 0

        @property
        def name(self) -> str:
            self.name_reads += 1
            if self.name_reads == 1:
                return "identity"
            return type("Text", (str,), {})("identity")

        @property
        def version(self) -> str:
            self.version_reads += 1
            return "1"

        def assign(self, records, meta, target):
            raise AssertionError("fingerprinting must not invoke assignment")

    policy = HostilePolicy()
    options = planning_contracts.SyncOptions(destination_policy=policy)

    policy_fingerprint(options)
    assert (policy.name_reads, policy.version_reads) == (1, 1)
    with pytest.raises(TypeError, match="policy version"):
        planning_contracts.policy_fingerprint(
            planning_contracts.SyncOptions(
                destination_policy=type(
                    "InvalidPolicy",
                    (),
                    {
                        "name": "identity",
                        "version": type("Text", (str,), {})("1"),
                    },
                )(),
            )
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows native path spelling")
@pytest.mark.parametrize(
    ("logical", "native"),
    [
        (r"C:\folder\file.bin", r"\\?\C:\folder\file.bin"),
        (
            r"\\server\share\folder\file.bin",
            r"\\?\UNC\server\share\folder\file.bin",
        ),
    ],
)
def test_extended_length_path_round_trips_without_changing_logical_identity(
    logical: str,
    native: str,
) -> None:
    assert to_extended_length_path(logical) == native
    assert to_extended_length_path(native) == native
    assert from_extended_length_path(native) == logical
    assert from_extended_length_path(logical) == logical


def test_lexical_absolute_path_normalizes_without_requiring_an_existing_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    assert lexical_absolute_path("configured-root") == str(
        tmp_path / "configured-root"
    )


def test_lexical_path_chain_excludes_a_trusted_mount_but_includes_every_child(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "mounted-volume"
    root = mount / "parent" / "managed"

    assert lexical_path_chain(root, trusted_anchor=mount) == (
        str(mount / "parent"),
        str(root),
    )
    assert lexical_path_chain(mount, trusted_anchor=mount) == ()


def test_lexical_path_chain_refuses_a_path_outside_its_trusted_anchor(
    tmp_path: Path,
) -> None:
    with pytest.raises(PathValidationError, match="trusted anchor"):
        lexical_path_chain(
            tmp_path / "other" / "managed",
            trusted_anchor=tmp_path / "mounted-volume",
        )


@pytest.mark.skipif(os.name != "nt", reason="requires Windows reparse points")
def test_lexical_absolute_path_does_not_follow_a_final_root_reparse(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    configured = tmp_path / "configured-root"
    try:
        configured.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory reparse creation is unavailable: {error}")

    assert lexical_absolute_path(configured) == str(configured)
    assert lexical_absolute_path(configured) != str(target)


@pytest.mark.parametrize(
    "path",
    [
        r"\\.\C:\folder\file.bin",
        r"\??\C:\folder\file.bin",
        r"\\??\C:\folder\file.bin",
        r"\\?\GLOBALROOT\Device\HarddiskVolume1\file.bin",
        r"\\?\UNC\server",
    ],
)
def test_extended_length_conversion_refuses_non_filesystem_device_namespaces(
    path: str,
) -> None:
    with pytest.raises(PathValidationError):
        to_extended_length_path(path)


def test_os_error_rendering_rewrites_only_exact_extended_filename_fields() -> None:
    native = r"\\?\C:\deep\payload.bin"
    error = FileNotFoundError(2, "missing", native)
    rendered = logical_error_text(error)
    assert repr(r"C:\deep\payload.bin") in rendered
    assert "\\\\?\\" not in rendered

    arbitrary = RuntimeError(r"documentation mentions \\?\C:\deep\payload.bin")
    assert logical_error_text(arbitrary) == str(arbitrary)


@pytest.mark.parametrize(
    "path",
    [
        r"\\?\C:\safe\root.",
        r"\\?\UNC\.\C$\folder",
        r"\\?\UNC\?\C$\folder",
        r"\\?\C:\safe/folder",
        r"\\?\UNC\server/share\folder",
    ],
)
def test_extended_conversion_refuses_ambiguous_absolute_components(
    path: str,
) -> None:
    with pytest.raises(PathValidationError):
        to_extended_length_path(path)
    if path.startswith("\\\\?\\"):
        with pytest.raises(PathValidationError):
            from_extended_length_path(path)


@pytest.mark.skipif(os.name != "nt", reason="Windows absolute path rules")
@pytest.mark.parametrize(
    "path",
    [r"C:\safe\root.", r"C:\safe\root ", r"C:\safe\CON"],
)
def test_native_conversion_refuses_ambiguous_ordinary_absolute_components(
    path: str,
) -> None:
    with pytest.raises(PathValidationError):
        to_extended_length_path(path)


def test_canonical_json_preserves_valid_unicode_bytes() -> None:
    valid = {"path": "caf\u00e9-\U0001f600.txt", "literal": r"\ud800"}
    assert canonical_json_bytes(valid) == json.dumps(
        valid,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@pytest.mark.parametrize("text", ("\ud800", "\udcff", "\ud83d\ude00"))
@pytest.mark.parametrize("position", ("key", "value"))
def test_canonical_json_rejects_surrogate_code_units(text: str, position: str) -> None:
    value = {text: "scalar"} if position == "key" else {"scalar": text}
    with pytest.raises(UnicodeEncodeError):
        canonical_json_bytes({"nested": [value]})


@pytest.mark.parametrize("text", ("\ud800", "\udcff", "\ud83d\ude00"))
def test_scan_warning_omits_only_malformed_optional_unicode(text: str) -> None:
    warning = model_contracts.ScanWarning(
        model_contracts.ScanWarningCode.PATH_UNREPRESENTABLE, None, "bad-" + text,
    )
    assert warning.code is model_contracts.ScanWarningCode.PATH_UNREPRESENTABLE
    assert warning.rel_path is None
    assert warning.detail == ""


def test_scan_warning_retains_complete_valid_detail_and_rejects_nontext() -> None:
    detail = "\u00e9\U0001f600" * 2_000 + r"\ud800"
    warning = model_contracts.ScanWarning(
        model_contracts.ScanWarningCode.ACCESS_DENIED, "folder", detail,
    )
    assert warning.rel_path == "folder"
    assert warning.detail == ""
    with pytest.raises(TypeError):
        model_contracts.ScanWarning(
            model_contracts.ScanWarningCode.ACCESS_DENIED, "folder", 7,
        )


@dataclass(frozen=True)
class _UnprojectedHashValue:
    file_index: int = MAX_FILE_INDEX


class _StringKey(str):
    pass


class _JsonList(list):
    pass


class _JsonDict(dict):
    pass


@pytest.mark.parametrize(
    "value",
    (
        pytest.param(_UnprojectedHashValue(), id="dataclass"),
        pytest.param({"nested": [_UnprojectedHashValue()]}, id="nested-dataclass"),
        pytest.param({"nested": object()}, id="unknown-type"),
        pytest.param({1: "value"}, id="integer-key"),
        pytest.param({"nested": {False: "value"}}, id="nested-boolean-key"),
        pytest.param({_StringKey("field"): "value"}, id="string-subclass-key"),
        pytest.param({"nested": _StringKey("value")}, id="string-subclass-value"),
        pytest.param({"nested": _JsonList([1])}, id="list-subclass"),
        pytest.param({"nested": _JsonDict(field=1)}, id="dict-subclass"),
        pytest.param({"nested": (1, 2)}, id="unprojected-tuple"),
        pytest.param({"nested": frozenset({1, 2})}, id="unprojected-set"),
        pytest.param({"nested": b"digest"}, id="unprojected-bytes"),
        pytest.param({"nested": planning_contracts.OperationKind.COPY}, id="unprojected-enum"),
        pytest.param({"number": float("nan")}, id="nan"),
        pytest.param({"number": float("inf")}, id="infinity"),
        pytest.param({"number": -float("inf")}, id="negative-infinity"),
    ),
)
def test_canonical_json_refuses_unprojected_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        canonical_json_bytes(value)


@dataclass(frozen=True)
class _UnprojectedRoot:
    path: str
    root_id: str


@pytest.mark.parametrize("encode", (plan_fingerprint, serialize_plan))
def test_plan_hash_boundary_refuses_an_unknown_nested_dataclass(encode) -> None:
    reviewed = two_copy_plan(False)
    unknown = _UnprojectedRoot(reviewed.source_root.path, reviewed.source_root.root_id)
    malformed = replace(reviewed, source_root=unknown)

    with pytest.raises(TypeError):
        encode(malformed)


def test_serialized_plan_quotes_identity_without_stringifying_known_integers() -> None:
    plans, _ = hash_fixtures(True)
    encoded = json.loads(serialize_plan(plans["all_fields"]))
    operation = encoded["operations"][1]

    assert operation["source_expected"]["file_identity"]["file_index"] == str(MAX_FILE_INDEX)
    assert operation["intended"]["file_identity"]["file_index"] == str(MAX_FILE_INDEX)
    assert operation["target_expected"]["file_identity"]["file_index"] == "0"
    assert operation["prior_target_expected"]["file_identity"]["file_index"] == "0"
    assert type(operation["content_bytes"]) is int
    assert operation["content_bytes"] == (1 << 53) + 7
    assert type(operation["source_expected"]["mtime_ns"]) is int
    assert operation["source_expected"]["mtime_ns"] == (1 << 53) + 11


@pytest.mark.parametrize("name", ("two_copy", "all_fields"))
def test_plan_fingerprint_uses_explicit_identity_text(name: str) -> None:
    plans, _ = hash_fixtures(True)
    expected = json.loads(frozen_vector(f"plan/{name}/full128/fingerprint"))
    # Transform only the named identity fields of the frozen plan shape.
    for operation in expected["operations"]:
        for field in ("source_expected", "target_expected", "intended", "prior_target_expected"):
            stat = operation[field]
            if stat is not None and stat["file_identity"] is not None:
                identity = stat["file_identity"]
                identity["file_index"] = str(identity["file_index"])
    canonical = json.dumps(
        expected, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")

    expected_fingerprint = hashlib.sha256(canonical).hexdigest()
    assert plan_fingerprint(plans[name]) == expected_fingerprint
    expected["fingerprint"] = expected_fingerprint
    assert serialize_plan(plans[name]) == json.dumps(
        expected, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


@pytest.mark.parametrize("name", ("two_copy", "all_fields"))
def test_identityless_plan_bytes_preserve_the_epoch5_capture(name: str) -> None:
    plans, _ = hash_fixtures(False)
    reviewed = plans[name]

    assert serialize_plan(reviewed) == frozen_vector(f"plan/{name}/identityless/serialize")
    assert plan_fingerprint(reviewed) == hashlib.sha256(
        frozen_vector(f"plan/{name}/identityless/fingerprint")
    ).hexdigest()


def test_custom_policy_hash_keeps_only_name_and_version_semantics() -> None:
    options = custom_options()
    expected = hashlib.sha256(
        frozen_vector("policy/custom_name_version")
    ).hexdigest()
    assert policy_fingerprint(options) == expected
    options.destination_policy.ignored_state = {"unprojected": object()}
    assert policy_fingerprint(options) == expected
    assert policy_fingerprint(replace(options, internal_mirror_authorized=True)) == expected
    options.destination_policy.name = "changed-policy"
    assert policy_fingerprint(options) != expected


def test_policy_field_coverage_names_its_one_nonsemantic_authorization_field() -> None:
    hashed_fields = set(json.loads(frozen_vector("policy/custom_name_version")))
    assert {field.name for field in fields(planning_contracts.SyncOptions)} == (
        hashed_fields | {"internal_mirror_authorized"}
    )


def test_core_hash_projections_cover_exact_known_dataclasses() -> None:
    plans, _ = hash_fixtures(True)
    reviewed = plans["all_fields"]
    operation = reviewed.operations[1]
    cases = (
        (model_contracts.file_identity_projection, operation.source_expected.file_identity),
        (model_contracts.metadata_projection, operation.metadata),
        (model_contracts.file_stat_projection, operation.source_expected),
        (model_contracts.root_projection, reviewed.source_root),
        (model_contracts.volume_id_projection, reviewed.source_volume_id),
        (model_contracts.volume_evidence_projection, reviewed.source_volume_evidence),
        (model_contracts.capability_profile_projection, reviewed.source_profile),
        (planning_contracts._preservation_projection, reviewed.preservation),
        (planning_contracts._filter_projection, reviewed.filter_snapshot),
        (planning_contracts._destination_assignment_projection, reviewed.assignment.items[1]),
        (planning_contracts._assignment_projection, reviewed.assignment),
        (planning_contracts.operation_projection, operation),
        (planning_contracts.plan_projection, reviewed),
    )
    for project, value in cases:
        # Reflection is a test-only completeness alarm, never a wire encoder.
        declared = {field.name for field in fields(value)}
        assert set(project(value)) == declared, type(value).__name__
        lookalike_type = make_dataclass("Unprojected" + type(value).__name__, sorted(declared))
        lookalike = lookalike_type(**{name: getattr(value, name) for name in declared})
        with pytest.raises(TypeError):
            project(lookalike)
        subclass_type = make_dataclass(
            "Extended" + type(value).__name__,
            [("future_file_index", int, MAX_FILE_INDEX)],
            bases=(type(value),), frozen=True,
        )
        extended = subclass_type(**{name: getattr(value, name) for name in declared})
        with pytest.raises(TypeError):
            project(extended)


def test_plan_projection_preserves_sequence_and_historical_volume_set_order() -> None:
    plans, _ = hash_fixtures(False)
    reviewed = plans["all_fields"]
    encoded = json.loads(serialize_plan(reviewed))
    assert encoded["required_volumes"] == [
        {"fs_type": "NTFS", "serial": "FFFFFFFF"},
        {"fs_type": "REFS", "serial": "00000001"},
    ]
    assert [volume.serial for volume in sorted(reviewed.required_volumes)] == [
        "00000001", "FFFFFFFF",
    ]
    assert [operation["op_id"] for operation in encoded["operations"]] == [
        str(operation.op_id) for operation in reviewed.operations
    ]
    assert encoded["operations"][1]["dependencies"] == [str(reviewed.operations[0].op_id)]
    assert encoded["assignment"]["items"][0]["source_rel_path"] == "b.txt"
    operation = replace(reviewed.operations[1], dependencies=("f" * 32, "0" * 32))
    assert planning_contracts.operation_projection(operation)["dependencies"] == [
        "f" * 32, "0" * 32,
    ]


@pytest.mark.parametrize(
    ("name", "value"),
    (
        ("primitives", {"none": None, "bool": True, "integer": (1 << 63) - 1,
                        "finite_float": 1.5, "list": ["é", "源", 0]}),
        ("literal_escape", {"text": r"bad-\udcff"}),
    ),
)
def test_canonical_json_preserves_frozen_control_bytes(name: str, value: object) -> None:
    assert canonical_json_bytes(value) == frozen_vector(f"core/{name}")


def test_frozen_surrogate_preimage_is_historical_not_current_input() -> None:
    value = json.loads(frozen_vector("core/surrogate"))
    assert value == {"text": "bad-\udcff"}
    with pytest.raises(UnicodeEncodeError):
        canonical_json_bytes(value)


def test_operation_id_and_selection_digest_preserve_frozen_control_hashes() -> None:
    operation_id = planning_contracts.deterministic_operation_id(
        planning_contracts.OperationKind.MOVE_UPDATE,
        "é.txt", r"folder\é.txt", "old.txt",
        planning_contracts.OperationReason.IDENTITY_RENAME_CHANGED,
    )
    assert operation_id == hashlib.sha256(frozen_vector("operation_id/intent")).hexdigest()[:32]
    expected_selection = hashlib.sha256(frozen_vector("selection/sorted")).digest()
    assert planning_contracts.selection_digest(("f" * 32, "0" * 32)) == expected_selection
    assert planning_contracts.selection_digest(frozenset({"0" * 32, "f" * 32})) == expected_selection


def test_ignore_set_matches_only_built_in_shapes() -> None:
    ignores = IgnoreSet()
    assert ignores.excludes("desktop.ini", is_directory=False)
    assert ignores.excludes("THUMBS.DB", is_directory=False)
    assert ignores.excludes(".synctrash", is_directory=True)
    assert ignores.excludes("movie.bin.synctmp-" + "a" * 32 + "-" + "b" * 32, is_directory=False)
    assert not ignores.excludes(r".namisync\ledger.db", is_directory=False)
    assert not ignores.excludes("customer.db", is_directory=False)
    assert not ignores.excludes("my.synctmp-notes.txt", is_directory=False)
    assert not ignores.excludes("customer.sha256", is_directory=False)
