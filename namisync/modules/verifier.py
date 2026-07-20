"""Cache-honest baseline and integrity verification.

The verifier owns classification and hashing only.  Inventory refresh, ledger
transactions, session terminals, and audit persistence remain injected through
core protocols and the workflow/dispatcher layers.
"""

from __future__ import annotations

import ctypes
import ntpath
import os
from contextlib import contextmanager
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path, PureWindowsPath
from typing import Iterator

from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    Provenance,
    RecordingStatus,
)
from namisync.core.events import Progress
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityOutcome,
    IntegrityReason,
    IntegrityRecorder,
    IntegrityRecordCommand,
    IntegrityResult,
    IntegrityRunResult,
    IntegritySelection,
    IntegritySelectionItem,
    InventoryState,
    ReadStrategy,
    RecordDisposition,
    UnsupportedVerification,
    VerificationReader,
    VerifierContext,
)
from namisync.core.models import EntryKind, FileIdentity, FileStat, MetadataSnapshot
from namisync.core.pathing import normalize_relative_path, validate_relative_path
from namisync.core.session import Canceled, PauseRequested


_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_GENERIC_READ = 0x80000000
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_SHARE_DELETE = 0x00000004
_OPEN_EXISTING = 3
_FILE_FLAG_NO_BUFFERING = 0x20000000
_FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_MEM_COMMIT = 0x00001000
_MEM_RESERVE = 0x00002000
_MEM_RELEASE = 0x00008000
_PAGE_READWRITE = 0x04
_ERROR_FILE_NOT_FOUND = 2
_ERROR_PATH_NOT_FOUND = 3
_ERROR_ACCESS_DENIED = 5
_ERROR_INVALID_PARAMETER = 87
_WINDOWS_EPOCH_TICKS = 116_444_736_000_000_000


def baseline(
    selection: IntegritySelection,
    ctx: VerifierContext,
    recorder: IntegrityRecorder,
    reader: VerificationReader | None = None,
) -> IntegrityRunResult:
    """Create evidence only for freshly selected rows without a baseline."""

    return _run(selection, ctx, recorder, reader, IntegrityMode.BASELINE)


def verify(
    selection: IntegritySelection,
    ctx: VerifierContext,
    recorder: IntegrityRecorder,
    reader: VerificationReader | None = None,
) -> IntegrityRunResult:
    """Classify selected rows against retained stat and SHA-256 evidence."""

    return _run(selection, ctx, recorder, reader, IntegrityMode.VERIFY)


def rebaseline(
    selection: IntegritySelection,
    ctx: VerifierContext,
    recorder: IntegrityRecorder,
    reader: VerificationReader | None = None,
) -> IntegrityRunResult:
    """Explicitly accept freshly inventoried current content as new evidence."""

    return _run(selection, ctx, recorder, reader, IntegrityMode.REBASELINE)


@dataclass(frozen=True)
class _ProcessedItem:
    outcome: IntegrityOutcome
    bytes_read: int = 0


class _ProgressReporter:
    def __init__(self, selection: IntegritySelection, ctx: VerifierContext) -> None:
        self._selection = selection
        self._ctx = ctx
        self._last_emitted_at: float | None = None
        self._bytes_total = selection.processed_bytes + sum(
            item.expected_stat.size
            for item in selection.pending
            if item.expected_state is InventoryState.PRESENT
            and item.expected_stat is not None
        )
        self.emit(current_path=None, force=True)

    def bytes_processed(self, size: int, current_path: str) -> None:
        self._selection.note_bytes_processed(size)
        if self._selection.processed_bytes > self._bytes_total:
            # A subject that grows during the read will later classify as drift,
            # but its lossy progress snapshots must remain constructible first.
            self._bytes_total = self._selection.processed_bytes
        self.emit(current_path=current_path, force=False)

    def item_completed(self, current_path: str) -> None:
        self.emit(current_path=current_path, force=True)

    def emit(self, current_path: str | None, force: bool) -> None:
        now = self._ctx.monotonic()
        if not force and self._last_emitted_at is not None:
            if now - self._last_emitted_at < self._ctx.progress_interval_seconds:
                return
        self._ctx.run.emit(
            Progress(
                items_done=self._selection.completed_count,
                items_total=len(self._selection.items),
                bytes_done=self._selection.processed_bytes,
                bytes_total=self._bytes_total,
                current_path=current_path,
            )
        )
        self._last_emitted_at = now


def _run(
    selection: IntegritySelection,
    ctx: VerifierContext,
    recorder: IntegrityRecorder,
    reader: VerificationReader | None,
    mode: IntegrityMode,
) -> IntegrityRunResult:
    actual_reader = reader if reader is not None else WindowsUnbufferedReader()
    emitted: list[IntegrityOutcome] = []
    reporter = _ProgressReporter(selection, ctx)

    try:
        for item in selection.pending:
            ctx.run.checkpoint()
            processed = _process_item(
                item, mode, ctx, recorder, actual_reader, reporter
            )
            _emit_and_complete(selection, ctx, reporter, processed, emitted)
    except PauseRequested:
        # Pending and in-flight items stay pending.  Their reliable outcomes are
        # emitted only when a resumed pass actually settles them.
        raise
    except Canceled:
        # The runner aggregates reliable events and cannot inspect module state.
        # Complete every still-pending row before the payload-free unwind leaves.
        for item in selection.pending:
            processed = _ProcessedItem(
                _outcome(
                    item,
                    IntegrityResult.CANCELED,
                    IntegrityReason.CANCELED,
                )
            )
            _emit_and_complete(
                selection, ctx, reporter, processed, emitted, emit_progress=False
            )
        reporter.emit(current_path=None, force=True)
        raise

    recording = (
        RecordingStatus.DEGRADED
        if any(outcome.recording is RecordingStatus.DEGRADED for outcome in emitted)
        else RecordingStatus.OK
    )
    return IntegrityRunResult(tuple(emitted), recording)


def _emit_and_complete(
    selection: IntegritySelection,
    ctx: VerifierContext,
    reporter: _ProgressReporter,
    processed: _ProcessedItem,
    emitted: list[IntegrityOutcome],
    *,
    emit_progress: bool = True,
) -> None:
    # Outcome first, continuation second: after a pause, completed status can
    # never exist without the reliable result that justifies skipping the row.
    ctx.run.emit(processed.outcome)
    selection.mark_completed(processed.outcome.item_id, processed.bytes_read)
    emitted.append(processed.outcome)
    if emit_progress:
        reporter.item_completed(processed.outcome.path)


def _process_item(
    item: IntegritySelectionItem,
    mode: IntegrityMode,
    ctx: VerifierContext,
    recorder: IntegrityRecorder,
    reader: VerificationReader,
    reporter: _ProgressReporter,
) -> _ProcessedItem:
    try:
        validated_path = validate_relative_path(item.display_path)
        if normalize_relative_path(validated_path) != item.rel_path_key:
            raise ValueError("display path does not match the selected canonical key")
    except (OSError, ValueError) as exc:
        return _ProcessedItem(
            _outcome(
                item,
                IntegrityResult.ERROR,
                IntegrityReason.PATH_INVALID,
                _error_detail(exc),
            )
        )

    if item.expected_state is InventoryState.MISSING:
        return _ProcessedItem(
            _outcome(
                item,
                IntegrityResult.MISSING,
                IntegrityReason.INVENTORY_MISSING,
            )
        )
    if item.expected_state is InventoryState.UNSUPPORTED:
        return _ProcessedItem(
            _outcome(
                item,
                IntegrityResult.UNSUPPORTED,
                IntegrityReason.INVENTORY_UNSUPPORTED,
            )
        )
    if mode is IntegrityMode.BASELINE and item.baseline is not None:
        return _ProcessedItem(
            _outcome(
                item,
                IntegrityResult.ERROR,
                IntegrityReason.BASELINE_EXISTS,
            )
        )

    expected_stat = item.expected_stat
    if expected_stat is None:  # guarded by IntegritySelectionItem; defensive only
        return _ProcessedItem(
            _outcome(item, IntegrityResult.ERROR, IntegrityReason.STAT_CHANGED)
        )

    try:
        with reader.open(item.root, validated_path) as stream:
            before = stream.stat()
            if not _matches_expected_stat(expected_stat, before):
                return _ProcessedItem(
                    _outcome(
                        item,
                        IntegrityResult.MODIFIED,
                        IntegrityReason.STAT_CHANGED,
                        read_strategy=stream.strategy,
                    )
                )
            if (
                mode is IntegrityMode.VERIFY
                and item.baseline is not None
                and not _matches_expected_stat(item.baseline.subject, before)
            ):
                return _ProcessedItem(
                    _outcome(
                        item,
                        IntegrityResult.MODIFIED,
                        IntegrityReason.STAT_CHANGED,
                        read_strategy=stream.strategy,
                    )
                )

            digest = sha256()
            bytes_read = 0
            for chunk in stream.iter_chunks(ctx.chunk_size):
                ctx.run.checkpoint()
                if not chunk:
                    continue
                digest.update(chunk)
                bytes_read += len(chunk)
                reporter.bytes_processed(len(chunk), item.display_path)

            after = stream.stat()
            if not _same_open_subject(before, after):
                return _ProcessedItem(
                    _outcome(
                        item,
                        IntegrityResult.MODIFIED,
                        IntegrityReason.READ_DRIFT,
                        read_strategy=stream.strategy,
                    ),
                    bytes_read,
                )
            if bytes_read != before.size:
                return _ProcessedItem(
                    _outcome(
                        item,
                        IntegrityResult.ERROR,
                        IntegrityReason.READ_ERROR,
                        f"read {bytes_read} bytes from a {before.size}-byte subject",
                        read_strategy=stream.strategy,
                    ),
                    bytes_read,
                )

            actual_digest = digest.digest()
            if (
                mode is IntegrityMode.VERIFY
                and item.baseline is not None
                and actual_digest != item.baseline.content.digest
            ):
                return _ProcessedItem(
                    _outcome(
                        item,
                        IntegrityResult.MISMATCHED,
                        IntegrityReason.HASH_MISMATCH,
                        read_strategy=stream.strategy,
                    ),
                    bytes_read,
                )

            observed_at = ctx.clock.now()
            content = ContentEvidence(
                algorithm="sha256",
                digest=actual_digest,
                size=bytes_read,
                provenance=Provenance.VERIFY_ATTESTED,
                observed_at=observed_at,
            )
            subject = (
                after
                if expected_stat.file_identity is not None
                else replace(after, file_identity=None)
            )
            attestation = Attestation(content=content, subject=subject)
            result = (
                IntegrityResult.VERIFIED
                if mode is IntegrityMode.VERIFY and item.baseline is not None
                else IntegrityResult.BASELINED
            )
            command_mode = (
                IntegrityMode.REBASELINE
                if mode is IntegrityMode.REBASELINE
                else (
                    IntegrityMode.VERIFY
                    if result is IntegrityResult.VERIFIED
                    else IntegrityMode.BASELINE
                )
            )
            command = IntegrityRecordCommand(
                mode=command_mode,
                item_id=item.item_id,
                row_id=item.row_id,
                location_id=item.location_id,
                rel_path_key=item.rel_path_key,
                scope_token=item.scope_token,
                expected_state=item.expected_state,
                expected_stat=expected_stat,
                expected_baseline=item.baseline,
                attestation=attestation,
                advances_last_verified=result is IntegrityResult.VERIFIED,
                clear_reappeared=item.reappeared_at is not None,
            )
            return _record_outcome(
                item,
                result,
                stream.strategy,
                command,
                recorder,
                bytes_read,
            )
    except (Canceled, PauseRequested):
        raise
    except FileNotFoundError as exc:
        return _ProcessedItem(
            _outcome(
                item,
                IntegrityResult.MISSING,
                IntegrityReason.NOT_FOUND,
                _error_detail(exc),
            )
        )
    except UnsupportedVerification as exc:
        return _ProcessedItem(
            _outcome(
                item,
                IntegrityResult.UNSUPPORTED,
                IntegrityReason.UNSUPPORTED_READ,
                _error_detail(exc),
            )
        )
    except Exception as exc:
        return _ProcessedItem(
            _outcome(
                item,
                IntegrityResult.ERROR,
                IntegrityReason.READ_ERROR,
                _error_detail(exc),
            )
        )


def _record_outcome(
    item: IntegritySelectionItem,
    result: IntegrityResult,
    strategy: ReadStrategy,
    command: IntegrityRecordCommand,
    recorder: IntegrityRecorder,
    bytes_read: int,
) -> _ProcessedItem:
    try:
        disposition = recorder.record_integrity(command)
    except Exception as exc:
        return _ProcessedItem(
            _outcome(
                item,
                result,
                IntegrityReason.RECORDING_ERROR,
                _error_detail(exc),
                read_strategy=strategy,
                recording=RecordingStatus.DEGRADED,
            ),
            bytes_read,
        )

    if disposition is RecordDisposition.STALE:
        return _ProcessedItem(
            _outcome(
                item,
                result,
                IntegrityReason.RECORDING_STALE,
                read_strategy=strategy,
                recording=RecordingStatus.DEGRADED,
                record_disposition=disposition,
            ),
            bytes_read,
        )
    if disposition is RecordDisposition.CONFLICT:
        return _ProcessedItem(
            _outcome(
                item,
                result,
                IntegrityReason.RECORDING_CONFLICT,
                read_strategy=strategy,
                recording=RecordingStatus.DEGRADED,
                record_disposition=disposition,
            ),
            bytes_read,
        )
    return _ProcessedItem(
        _outcome(
            item,
            result,
            read_strategy=strategy,
            record_disposition=disposition,
        ),
        bytes_read,
    )


def _outcome(
    item: IntegritySelectionItem,
    result: IntegrityResult,
    reason: IntegrityReason | None = None,
    detail: str | None = None,
    *,
    read_strategy: ReadStrategy | None = None,
    recording: RecordingStatus = RecordingStatus.OK,
    record_disposition: RecordDisposition | None = None,
) -> IntegrityOutcome:
    return IntegrityOutcome(
        item_id=item.item_id,
        row_id=item.row_id,
        location_id=item.location_id,
        path=item.display_path,
        result=result,
        reason=reason,
        detail=detail,
        read_strategy=read_strategy,
        recording=recording,
        record_disposition=record_disposition,
    )


def _matches_expected_stat(expected: FileStat, actual: FileStat) -> bool:
    if expected.kind is not actual.kind:
        return False
    if expected.size != actual.size or expected.mtime_ns != actual.mtime_ns:
        return False
    return expected.file_identity is None or expected.file_identity == actual.file_identity


def _same_open_subject(before: FileStat, after: FileStat) -> bool:
    if before.kind is not after.kind:
        return False
    if before.size != after.size or before.mtime_ns != after.mtime_ns:
        return False
    if before.file_identity is None and after.file_identity is None:
        return True
    return before.file_identity == after.file_identity


def _error_detail(exc: BaseException) -> str:
    detail = str(exc)
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


class WindowsUnbufferedReader:
    """Read one Windows file through ``FILE_FLAG_NO_BUFFERING``.

    There is deliberately no buffered fallback.  A filesystem, subject, or
    alignment condition that cannot honor the declared strategy produces
    ``UnsupportedVerification`` and can never be rendered as verified.
    """

    @contextmanager
    def open(self, root: Path, relative_path: str) -> Iterator[_WindowsStream]:
        if os.name != "nt":
            raise UnsupportedVerification(
                "cache-honest verification is implemented only for Windows"
            )

        normalized = validate_relative_path(relative_path)
        root_path = root.resolve(strict=True)
        candidate = root_path.joinpath(*PureWindowsPath(normalized).parts)
        _reject_reparse_components(root_path, normalized)

        api = _WindowsApi()
        sector_size = api.sector_size(candidate)
        handle = api.open_file(candidate)
        try:
            api.require_expected_final_path(root_path, normalized, handle)
            stream = _WindowsStream(api, handle, sector_size)
            stream.stat()  # reject directories/reparse points before yielding
            yield stream
        finally:
            api.close(handle)


def _reject_reparse_components(root: Path, normalized_path: str) -> None:
    current = root
    for component in PureWindowsPath(normalized_path).parts:
        current = current / component
        stat_result = os.lstat(current)
        attributes = getattr(stat_result, "st_file_attributes", 0)
        if attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            raise UnsupportedVerification(
                f"verification refuses reparse component: {component}"
            )


class _FileTime(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]


class _ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", ctypes.c_uint32),
        ("ftCreationTime", _FileTime),
        ("ftLastAccessTime", _FileTime),
        ("ftLastWriteTime", _FileTime),
        ("dwVolumeSerialNumber", ctypes.c_uint32),
        ("nFileSizeHigh", ctypes.c_uint32),
        ("nFileSizeLow", ctypes.c_uint32),
        ("nNumberOfLinks", ctypes.c_uint32),
        ("nFileIndexHigh", ctypes.c_uint32),
        ("nFileIndexLow", ctypes.c_uint32),
    ]


class _WindowsApi:
    def __init__(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32 = kernel32
        self._configure_signatures()

    def _configure_signatures(self) -> None:
        k32 = self._kernel32
        k32.CreateFileW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        k32.CreateFileW.restype = ctypes.c_void_p
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        k32.CloseHandle.restype = ctypes.c_int
        k32.GetFileInformationByHandle.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_ByHandleFileInformation),
        ]
        k32.GetFileInformationByHandle.restype = ctypes.c_int
        k32.ReadFile.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_void_p,
        ]
        k32.ReadFile.restype = ctypes.c_int
        k32.VirtualAlloc.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_uint32,
            ctypes.c_uint32,
        ]
        k32.VirtualAlloc.restype = ctypes.c_void_p
        k32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
        k32.VirtualFree.restype = ctypes.c_int
        k32.GetFinalPathNameByHandleW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
        ]
        k32.GetFinalPathNameByHandleW.restype = ctypes.c_uint32
        k32.GetVolumePathNameW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
        ]
        k32.GetVolumePathNameW.restype = ctypes.c_int
        k32.GetDiskFreeSpaceW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
        ]
        k32.GetDiskFreeSpaceW.restype = ctypes.c_int

    def open_file(self, path: Path) -> int:
        handle = self._kernel32.CreateFileW(
            _extended_path(path),
            _GENERIC_READ,
            # Keep the attested path bound to this subject for the whole read.
            # Existing or new writers/deleters must not be able to replace the
            # selected name while this handle still refers to the old file.
            _FILE_SHARE_READ,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_NO_BUFFERING
            | _FILE_FLAG_SEQUENTIAL_SCAN
            | _FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        if handle == ctypes.c_void_p(-1).value:
            self._raise_open_error(path)
        return handle

    def open_directory(self, path: Path) -> int:
        handle = self._kernel32.CreateFileW(
            _extended_path(path),
            0,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if handle == ctypes.c_void_p(-1).value:
            self._raise_open_error(path)
        return handle

    def _raise_open_error(self, path: Path) -> None:
        error = ctypes.get_last_error()
        if error in (_ERROR_FILE_NOT_FOUND, _ERROR_PATH_NOT_FOUND):
            raise FileNotFoundError(error, os.strerror(error), str(path))
        if error == _ERROR_ACCESS_DENIED:
            raise PermissionError(error, os.strerror(error), str(path))
        raise OSError(error, os.strerror(error), str(path))

    def close(self, handle: int) -> None:
        self._kernel32.CloseHandle(handle)

    def stat(self, handle: int) -> FileStat:
        info = _ByHandleFileInformation()
        if not self._kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            error = ctypes.get_last_error()
            raise OSError(error, os.strerror(error))
        if info.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            raise UnsupportedVerification("verification refuses a reparse subject")
        if info.dwFileAttributes & _FILE_ATTRIBUTE_DIRECTORY:
            raise UnsupportedVerification("verification selections must name files")

        size = (info.nFileSizeHigh << 32) | info.nFileSizeLow
        file_index = (info.nFileIndexHigh << 32) | info.nFileIndexLow
        identity = FileIdentity(
            volume_serial=f"{info.dwVolumeSerialNumber:08X}",
            file_index=file_index,
        )
        return FileStat(
            kind=EntryKind.FILE,
            size=size,
            mtime_ns=_filetime_to_unix_ns(info.ftLastWriteTime),
            file_identity=identity,
            nlink=info.nNumberOfLinks,
            metadata=MetadataSnapshot(
                attributes=info.dwFileAttributes,
                created_ns=_filetime_to_unix_ns(info.ftCreationTime),
            ),
        )

    def sector_size(self, path: Path) -> int:
        volume_buffer = ctypes.create_unicode_buffer(32768)
        if not self._kernel32.GetVolumePathNameW(
            _extended_path(path), volume_buffer, len(volume_buffer)
        ):
            error = ctypes.get_last_error()
            raise UnsupportedVerification(
                f"cannot identify the verification volume (Windows error {error})"
            )
        sectors_per_cluster = ctypes.c_uint32()
        bytes_per_sector = ctypes.c_uint32()
        free_clusters = ctypes.c_uint32()
        total_clusters = ctypes.c_uint32()
        if not self._kernel32.GetDiskFreeSpaceW(
            volume_buffer.value,
            ctypes.byref(sectors_per_cluster),
            ctypes.byref(bytes_per_sector),
            ctypes.byref(free_clusters),
            ctypes.byref(total_clusters),
        ):
            error = ctypes.get_last_error()
            raise UnsupportedVerification(
                f"cannot determine unbuffered-read alignment (Windows error {error})"
            )
        if bytes_per_sector.value <= 0:
            raise UnsupportedVerification("volume reported an invalid sector size")
        return bytes_per_sector.value

    def require_expected_final_path(
        self, root: Path, relative_path: str, file_handle: int
    ) -> None:
        root_handle = self.open_directory(root)
        try:
            root_final = self.final_path(root_handle).rstrip("\\/")
        finally:
            self.close(root_handle)
        expected = root_final + "\\" + relative_path
        actual = self.final_path(file_handle)
        if ntpath.normcase(expected) != ntpath.normcase(actual):
            raise UnsupportedVerification(
                "the opened handle does not resolve to the selected root-relative path"
            )

    def final_path(self, handle: int) -> str:
        size = 512
        while True:
            buffer = ctypes.create_unicode_buffer(size)
            length = self._kernel32.GetFinalPathNameByHandleW(handle, buffer, size, 0)
            if length == 0:
                error = ctypes.get_last_error()
                raise OSError(error, os.strerror(error))
            if length < size:
                return buffer.value
            size = length + 1

    def read(self, handle: int, address: int, size: int) -> int:
        bytes_read = ctypes.c_uint32()
        if not self._kernel32.ReadFile(
            handle, address, size, ctypes.byref(bytes_read), None
        ):
            error = ctypes.get_last_error()
            if error == _ERROR_INVALID_PARAMETER:
                raise UnsupportedVerification(
                    "the volume rejected an aligned unbuffered read"
                )
            raise OSError(error, os.strerror(error))
        return bytes_read.value

    def allocate(self, size: int) -> int:
        address = self._kernel32.VirtualAlloc(
            None, size, _MEM_COMMIT | _MEM_RESERVE, _PAGE_READWRITE
        )
        if not address:
            error = ctypes.get_last_error()
            raise OSError(error, os.strerror(error))
        return address

    def release(self, address: int) -> None:
        if not self._kernel32.VirtualFree(address, 0, _MEM_RELEASE):
            error = ctypes.get_last_error()
            raise OSError(error, os.strerror(error))


class _WindowsStream:
    strategy = ReadStrategy.WINDOWS_UNBUFFERED

    def __init__(self, api: _WindowsApi, handle: int, sector_size: int) -> None:
        self._api = api
        self._handle = handle
        self._sector_size = sector_size

    def stat(self) -> FileStat:
        return self._api.stat(self._handle)

    def iter_chunks(self, chunk_size: int) -> Iterator[bytes]:
        subject_size = self.stat().size
        if subject_size == 0:
            return
        aligned_size = _align_up(chunk_size, self._sector_size)
        address = self._api.allocate(aligned_size)
        total = 0
        try:
            while total < subject_size:
                count = self._api.read(self._handle, address, aligned_size)
                if count == 0:
                    break
                total += count
                yield ctypes.string_at(address, count)
        finally:
            self._api.release(address)


def _align_up(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _filetime_to_unix_ns(value: _FileTime) -> int:
    ticks = (value.dwHighDateTime << 32) | value.dwLowDateTime
    return (ticks - _WINDOWS_EPOCH_TICKS) * 100


def _extended_path(path: Path) -> str:
    raw = str(path)
    if raw.startswith("\\\\?\\"):
        return raw
    if raw.startswith("\\\\"):
        return "\\\\?\\UNC\\" + raw[2:]
    return "\\\\?\\" + raw
