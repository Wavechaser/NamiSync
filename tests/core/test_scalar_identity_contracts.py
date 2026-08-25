from __future__ import annotations

import ctypes
import os
from pathlib import Path

import pytest

import namisync.core.file_identity as identity_module
import namisync.modules.executor.native as executor_native
import namisync.modules.preflight as preflight_module
import namisync.modules.scanner as scanner_module
import namisync.modules.verifier.native as verifier_native
from namisync.core.file_identity import (
    FILE_ID_INFO_CLASS,
    file_identity_from_stat,
    file_identity_from_windows_handle,
    file_identity_from_windows_parts,
    file_index_128_from_bytes,
)
from namisync.core.models import FileIdentity
from namisync.core.review import (
    ReviewFactLimitExceeded,
    ReviewLimitAxis,
    ReviewPopulation,
)
from namisync.core.root_authority import observe_native_volume
from namisync.core.scalars import (
    MAX_FILE_INDEX_128,
    MAX_SAFE_INTEGER,
    MAX_SIGNED_64,
    ScalarDomainError,
    checked_add_signed_64,
    file_index_128_from_text,
    file_index_128_to_text,
    require_safe_int,
    require_signed_64,
    scalar_64_from_text,
    scalar_64_to_text,
)


@pytest.mark.parametrize("value", (0, MAX_SAFE_INTEGER))
def test_safe_int_accepts_its_exact_nonboolean_bounds(value: int) -> None:
    assert require_safe_int(value, "value") == value


@pytest.mark.parametrize("value", (True, False, -1, MAX_SAFE_INTEGER + 1, 1.0, "1"))
def test_safe_int_rejects_coercible_and_out_of_domain_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        require_safe_int(value, "value")


@pytest.mark.parametrize("value", (0, MAX_SIGNED_64))
def test_scalar64_round_trip_accepts_its_exact_bounds(value: int) -> None:
    encoded = scalar_64_to_text(value, "value")
    assert encoded == str(value)
    assert scalar_64_from_text(encoded, "value") == value


@pytest.mark.parametrize(
    "value",
    (True, False, -1, MAX_SIGNED_64 + 1, 1.0, "1"),
)
def test_internal_scalar64_rejects_coercible_and_out_of_domain_values(
    value: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        require_signed_64(value, "value")


@pytest.mark.parametrize(
    "value",
    (0, True, -1, "+1", "-1", "00", "01", "1.0", "1e0", str(MAX_SIGNED_64 + 1)),
)
def test_external_scalar64_rejects_raw_or_noncanonical_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        scalar_64_from_text(value, "value")


def test_checked_scalar64_addition_accepts_the_limit_and_refuses_overflow() -> None:
    assert checked_add_signed_64(MAX_SIGNED_64 - 1, 1, "total") == MAX_SIGNED_64
    with pytest.raises(ScalarDomainError, match="exceeds"):
        checked_add_signed_64(MAX_SIGNED_64, 1, "total")


@pytest.mark.parametrize("value", (0, (1 << 64) + 17, MAX_FILE_INDEX_128))
def test_file_index128_text_round_trip_preserves_full_width(value: int) -> None:
    encoded = file_index_128_to_text(value)
    assert encoded == str(value)
    assert file_index_128_from_text(encoded) == value


@pytest.mark.parametrize(
    "value",
    (0, True, -1, "+1", "-1", "00", "01", "1.0", str(MAX_FILE_INDEX_128 + 1)),
)
def test_file_index128_decoder_rejects_numeric_and_noncanonical_values(
    value: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        file_index_128_from_text(value)


@pytest.mark.parametrize(
    ("volume_serial", "file_index"),
    ((1, 1), ("A1B2C3D4", True)),
)
def test_file_identity_rejects_coercible_fields(
    volume_serial: object,
    file_index: object,
) -> None:
    with pytest.raises(ValueError, match="invalid file identity"):
        FileIdentity(volume_serial, file_index)  # type: ignore[arg-type]


def test_review_fact_rejects_untyped_closed_fields() -> None:
    with pytest.raises(TypeError, match="tree_kind"):
        ReviewFactLimitExceeded(
            reason="review_fact_limit_exceeded",
            tree_kind="plan",  # type: ignore[arg-type]
            population=ReviewPopulation.DOMAIN,
            axis=ReviewLimitAxis.LOGICAL_BYTES,
            row_limit=None,
            byte_limit=MAX_SIGNED_64,
        )


def test_file_id128_bytes_use_complete_little_endian_identity() -> None:
    raw = bytes(range(16))
    expected = int.from_bytes(raw, "little")

    assert expected > (1 << 64) - 1
    assert file_index_128_from_bytes(raw) == expected
    assert file_index_128_from_bytes(memoryview(raw)) == expected
    with pytest.raises(ValueError, match="exactly 16 bytes"):
        file_index_128_from_bytes(raw[:-1])


@pytest.mark.parametrize("fs_type", ("NTFS", "ReFS", "refs"))
def test_stat_and_handle_adapters_are_equivalent_on_witnessed_filesystems(
    fs_type: str,
) -> None:
    raw = bytes.fromhex("1032547698badcfe0123456789abcdef")
    from_handle = file_identity_from_windows_parts(0xA1B2C3D4, raw)
    from_stat = file_identity_from_stat(
        "A1B2C3D4",
        fs_type,
        int.from_bytes(raw, "little"),
    )

    assert from_stat == from_handle
    assert from_handle.file_index > (1 << 64) - 1


def test_stat_adapter_refuses_unwitnessed_or_incomplete_identity() -> None:
    full_width = (1 << 96) + 3

    assert file_identity_from_stat("A1B2C3D4", "exFAT", full_width) is None
    assert file_identity_from_stat("A1B2C3D4", "NTFS", True) is None
    assert (
        file_identity_from_stat("A1B2C3D4", "NTFS", MAX_FILE_INDEX_128 + 1)
        is None
    )


def test_zero_file_id_is_equivalent_across_stat_and_handle_adapters() -> None:
    assert file_identity_from_stat("A1B2C3D4", "NTFS", 0) == (
        file_identity_from_windows_parts(0xA1B2C3D4, bytes(16))
    )


def test_handle_adapter_requests_file_id_info_and_keeps_all_128_bits() -> None:
    raw = bytes.fromhex("ffeeddccbbaa99887766554433221100")
    calls: list[tuple[int, int, int]] = []

    def get_file_information(
        handle: int,
        info_class: int,
        pointer: object,
        size: int,
    ) -> int:
        calls.append((handle, info_class, size))
        info = ctypes.cast(
            pointer,
            ctypes.POINTER(identity_module._FileIdInfo),
        ).contents
        info.volume_serial_number = 0x11223344
        for index, value in enumerate(raw):
            info.file_id.identifier[index] = value
        return 1

    identity = file_identity_from_windows_handle(73, get_file_information)

    assert calls == [(73, FILE_ID_INFO_CLASS, ctypes.sizeof(identity_module._FileIdInfo))]
    assert identity.volume_serial == "11223344"
    assert identity.file_index == int.from_bytes(raw, "little")
    assert identity.file_index > (1 << 64) - 1


@pytest.mark.skipif(os.name != "nt", reason="requires native Windows handles")
def test_cpython_stat_and_handle_file_ids_match_on_supported_windows_volume(
    tmp_path: Path,
) -> None:
    subject = tmp_path / "identity-witness.bin"
    subject.write_bytes(b"identity")
    volume = observe_native_volume(subject)
    if volume.volume_id.fs_type.upper() not in {"NTFS", "REFS"}:
        pytest.skip("witness requires NTFS or ReFS")

    filesystem = executor_native.NativeFileSystem()
    handle = filesystem._open_metadata_handle(subject)
    try:
        assert executor_native._WINDOWS is not None
        handle_identity = file_identity_from_windows_handle(
            handle,
            executor_native._WINDOWS.get_file_information_ex,
        )
    finally:
        filesystem._close_handle(handle)

    stat_identity = file_identity_from_stat(
        volume.volume_id.serial,
        volume.volume_id.fs_type,
        subject.stat().st_ino,
    )
    assert stat_identity == handle_identity


def test_every_native_identity_consumer_uses_the_core_owned_adapter() -> None:
    assert scanner_module.file_identity_from_stat is file_identity_from_stat
    assert preflight_module.file_identity_from_stat is file_identity_from_stat
    assert executor_native.file_identity_from_stat is file_identity_from_stat
    assert (
        executor_native.file_identity_from_windows_handle
        is file_identity_from_windows_handle
    )
    assert verifier_native.file_identity_from_windows_handle is file_identity_from_windows_handle
