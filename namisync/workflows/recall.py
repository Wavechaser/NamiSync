"""Scan-time availability advisories, independent of execution admission."""

from dataclasses import dataclass
from itertools import chain

from namisync.core.models import EntryKind, ScanResult, has_recall_on_data_access
from namisync.core.scalars import MAX_SIGNED_64


@dataclass(frozen=True, slots=True)
class RecallSummary:
    file_count: int = 0
    size: int | None = 0
    size_overflow: bool = False
    size_partial: bool = False


def scan_recall_summary(scan: ScanResult) -> RecallSummary:
    """Count known files with positive evidence, once per retained scan record."""
    count = total = 0
    partial = False
    for record in scan.files:
        if has_recall_on_data_access(record.metadata.attributes):
            count += 1
            total += record.size
    for record in scan.unsupported:
        if record.kind is EntryKind.FILE and has_recall_on_data_access(record.observed_attributes):
            count += 1
            if record.observed_size is None:
                partial = True
            else:
                total += record.observed_size
    overflow = total > MAX_SIGNED_64
    return RecallSummary(count, None if overflow else total, overflow, partial)


def recall_paths(scan: ScanResult) -> frozenset[str]:
    """Return actual positive observations, including directories/unknown kinds."""
    return frozenset(chain(
        (record.rel_path_key for record in chain(scan.files, scan.directories)
         if has_recall_on_data_access(record.metadata.attributes)),
        (record.rel_path_key for record in scan.unsupported
         if has_recall_on_data_access(record.observed_attributes)),
    ))
