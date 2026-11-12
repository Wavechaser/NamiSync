from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

import namisync.workflows.inventory_projection as projection_module
from namisync.core.evidence import Provenance
from namisync.core.integrity import VerificationInvalidation, VerificationInvalidationReason
from namisync.core.models import EntryKind, ScanWarning, ScanWarningCode
from namisync.core.pathing import normalize_relative_path, validate_relative_path
from namisync.core.scalars import MAX_SIGNED_64
from namisync.db.repositories import InventoryPresence, InventorySnapshot
from namisync.workflows import (
    InventoryProjectionPopulationLimitError,
    PlanSortColumn,
    SortDirection,
    build_inventory_projection,
    sort_inventory_projection,
)

from _db_fixtures import NOW, attestation, file_stat


def _row(row_id: str, path: str, *, size: int = 7, mtime: int = 11, **changes) -> InventorySnapshot:
    normalized, key = validate_relative_path(path), normalize_relative_path(path)
    row = InventorySnapshot(
        row_id, 1, normalized, key, EntryKind.FILE, InventoryPresence.PRESENT,
        file_stat(size=size, mtime_ns=mtime), None, NOW, None, "scope",
        None, None, None, None, None,
    )
    return replace(row, **changes)


def _paths(order):
    return [order.projection.nodes[position].rel_path for position in order.ordered_source_positions if position]


def test_inventory_hierarchy_scope_identity_and_domain_indexes() -> None:
    rows = (_row("1", r"a\deep\one.txt"), _row("2", r"a\two.txt", size=13))
    projection = build_inventory_projection(1, reversed(rows))
    folder = projection.nodes[projection.position_by_path_key["A"]]
    assert folder.rollup.domain_count == folder.rollup.file_count == 2
    assert folder.rollup.size == 20
    assert projection.domain_row_ids(folder.node_id) == ("1", "2")
    assert projection.row_for_id("1") is rows[0]
    for node in projection.nodes:
        if node.parent_index is not None:
            parent = projection.nodes[node.parent_index]
            assert parent.position < node.position < parent.subtree_end
            assert node.depth == parent.depth + 1
    other = build_inventory_projection(2, (replace(row, location_id=2) for row in rows))
    assert set(projection.position_by_node_id).isdisjoint(other.position_by_node_id)
    assert tuple(node.node_id for node in projection.nodes) == tuple(node.node_id for node in build_inventory_projection(1, rows).nodes)
    with pytest.raises(TypeError):
        projection.node_id_by_row_id["new"] = "node"
    with pytest.raises(FrozenInstanceError):
        folder.size = 8


def test_warning_identity_attachment_and_complete_domain_exclusion() -> None:
    warning = ScanWarning(ScanWarningCode.ACCESS_DENIED, r"a\one.txt", "Cannot read")
    projection = build_inventory_projection(1, (_row("1", r"a\one.txt"),), (warning, warning))
    notices = [node for node in projection.nodes if node.warning is not None]
    assert len({node.node_id for node in notices}) == 2
    assert projection.warning_count == 2
    assert all(node.parent_index == 0 and node.rollup.domain_count == 0 for node in notices)
    assert set(projection.position_by_path_key) == {"", "A", r"A\ONE.TXT"}
    assert projection.domain_row_ids(projection.nodes[0].node_id) == ("1",)
    assert projection.nodes[0].rollup.domain_count == 1
    for node in notices:
        with pytest.raises(ValueError, match="warnings"):
            projection.domain_row_ids(node.node_id)
    rebuilt = build_inventory_projection(1, (_row("1", r"a\one.txt"),), (warning, warning))
    assert [node.node_id for node in notices] == [node.node_id for node in rebuilt.nodes if node.warning]
    for column in PlanSortColumn:
        for direction in SortDirection:
            if column is PlanSortColumn.PATH and direction is SortDirection.DESCENDING:
                continue
            order = sort_inventory_projection(projection, column, direction)
            assert list(order.ordered_source_positions)[-2:] == [node.position for node in notices]


def test_inventory_retains_raw_current_attested_evidence_and_sticky_mismatch() -> None:
    original = file_stat(size=17, mtime_ns=19, identity_index=(1 << 100) + 1)
    evidence = attestation(original, provenance=Provenance.VERIFY_ATTESTED)
    row = _row("1", "changed.txt", size=23, mtime=29, attestation=evidence, last_verified_at=NOW,
        invalidation=VerificationInvalidation(NOW, VerificationInvalidationReason.HASH_MISMATCH))
    projection = build_inventory_projection(1, (row,))
    retained = projection.row_for_id("1")
    assert retained.observed.size == 23
    assert retained.attestation is evidence
    assert retained.attestation.subject.size == 17
    assert retained.attestation.subject.file_identity.file_index == (1 << 100) + 1
    assert retained.attestation.content.provenance is Provenance.VERIFY_ATTESTED
    assert retained.verification_state.value == "mismatched"
    assert projection.nodes[0].rollup.mismatched == 1


def test_inventory_acknowledged_missing_rows_remain_in_complete_rollups() -> None:
    rows = (
        _row("1", "missing.txt", size=13, presence=InventoryPresence.MISSING, missing_since=NOW),
        _row("2", "acknowledged.txt", size=17, presence=InventoryPresence.MISSING, missing_since=NOW, acknowledged_at=NOW),
    )
    projection = build_inventory_projection(1, rows)
    root = projection.nodes[0]
    assert root.rollup.domain_count == 2 and root.rollup.file_count == 2
    assert root.rollup.missing == root.rollup.acknowledged == 1
    assert root.rollup.size == 30
    assert set(projection.domain_row_ids(root.node_id)) == {"1", "2"}


def test_inventory_overflow_propagates_and_keeps_siblings_exact() -> None:
    projection = build_inventory_projection(1, (
        _row("1", r"a\one", size=MAX_SIGNED_64), _row("2", r"a\deep\two", size=1),
        _row("3", r"b\three", size=7),
    ))
    for key in ("", "A"):
        rollup = projection.nodes[projection.position_by_path_key[key]].rollup
        assert rollup.size is None and rollup.size_overflow
    sibling = projection.nodes[projection.position_by_path_key["B"]].rollup
    assert sibling.size == 7 and not sibling.size_overflow


@pytest.mark.parametrize("column", (PlanSortColumn.FILENAME, PlanSortColumn.SIZE, PlanSortColumn.MTIME))
@pytest.mark.parametrize("direction", tuple(SortDirection))
def test_inventory_sorts_complete_siblings_raw_values_ties_and_reset(column, direction) -> None:
    directory = _row("4", "folder", entry_kind=EntryKind.DIRECTORY, observed=replace(file_stat(size=0, mtime_ns=31), kind=EntryKind.DIRECTORY))
    unavailable = _row("5", "unknown", presence=InventoryPresence.UNSUPPORTED, entry_kind=None, observed=None)
    projection = build_inventory_projection(1, (
        _row("1", "a", size=2, mtime=9), _row("2", "B", size=10, mtime=3),
        _row("3", "c", size=2, mtime=9), directory, unavailable, _row("6", r"folder\child", size=100, mtime=100),
    ))
    order = sort_inventory_projection(projection, column, direction)
    direct = [projection.nodes[position].rel_path for position in order.ordered_source_positions if projection.nodes[position].parent_index == 0]
    descending = direction is SortDirection.DESCENDING
    if column is PlanSortColumn.SIZE:
        assert direct == (["B", "a", "c", "unknown", "folder"] if descending else ["a", "c", "B", "unknown", "folder"])
    elif column is PlanSortColumn.MTIME:
        assert direct == (["folder", "a", "c", "B", "unknown"] if descending else ["B", "a", "c", "folder", "unknown"])
    else:
        assert direct == (["unknown", "folder", "c", "B", "a"] if descending else ["a", "B", "c", "folder", "unknown"])
    assert order.order_rank_by_source_position[projection.position_by_path_key[r"FOLDER\CHILD"]] == order.order_rank_by_source_position[projection.position_by_path_key["FOLDER"]] + 1
    assert _paths(sort_inventory_projection(projection, PlanSortColumn.PATH, SortDirection.ASCENDING)) == ["a", "B", "c", "folder", r"folder\child", "unknown"]
    assert projection.domain_row_ids(projection.nodes[0].node_id) == ("1", "2", "3", "4", "6", "5")


def test_inventory_synthetic_ancestors_have_no_invented_own_sort_facts() -> None:
    projection = build_inventory_projection(1, (_row("1", r"a\child", size=100, mtime=200),))
    ancestor = projection.nodes[projection.position_by_path_key["A"]]
    assert ancestor.size is None and ancestor.mtime_ns is None
    assert ancestor.rollup.size == 100


def test_inventory_filename_sort_uses_real_row_spelling_before_ancestor_canonicalization() -> None:
    directory = _row("1", "ı", entry_kind=EntryKind.DIRECTORY,
        observed=replace(file_stat(size=0), kind=EntryKind.DIRECTORY))
    projection = build_inventory_projection(1, (
        directory, _row("2", r"I\child"), _row("3", "j"),
    ))
    folder = projection.node_for_id(projection.node_id_by_row_id["1"])
    assert folder.rel_path == "I"
    assert folder.row.rel_path == "ı"
    assert folder.filename_key == "ı".casefold()
    assert projection.domain_row_ids(folder.node_id) == ("1", "2")
    for direction, expected in (
        (SortDirection.ASCENDING, ["j", "I"]),
        (SortDirection.DESCENDING, ["I", "j"]),
    ):
        order = sort_inventory_projection(projection, PlanSortColumn.FILENAME, direction)
        assert [projection.nodes[position].rel_path for position in order.ordered_source_positions if projection.nodes[position].parent_index == 0] == expected
        assert order.projection is projection
    assert _paths(sort_inventory_projection(projection, PlanSortColumn.PATH, SortDirection.ASCENDING)) == ["I", r"I\child", "j"]
    assert projection.domain_row_ids(folder.node_id) == ("1", "2")


def test_inventory_unknown_subject_bytes_mark_only_containing_rollups_partial() -> None:
    projection = build_inventory_projection(1, (
        _row("1", r"a\unknown", entry_kind=None, presence=InventoryPresence.UNSUPPORTED, observed=None),
        _row("2", r"b\known", size=7),
    ))
    assert projection.nodes[0].rollup.size == 7
    assert projection.nodes[0].rollup.size_partial
    assert projection.nodes[projection.position_by_path_key["A"]].rollup.size_partial
    assert not projection.nodes[projection.position_by_path_key["B"]].rollup.size_partial


def test_inventory_empty_projection_retains_only_a_domain_root() -> None:
    projection = build_inventory_projection(1, ())
    assert len(projection.nodes) == 1
    assert projection.domain_row_ids(projection.nodes[0].node_id) == ()
    assert projection.nodes[0].rollup.domain_count == 0
    assert list(sort_inventory_projection(projection, PlanSortColumn.PATH, SortDirection.ASCENDING).ordered_source_positions) == [0]


@pytest.mark.parametrize("location", ((1 << 53) + 1, MAX_SIGNED_64))
def test_inventory_location_ids_preserve_full_signed_64_domain(location) -> None:
    projection = build_inventory_projection(location, (_row("1", "one", location_id=location),))
    assert projection.location_id == location


def test_inventory_rejects_wrong_location_duplicate_subjects_and_invalid_sort() -> None:
    row = _row("1", "one")
    with pytest.raises(ValueError, match="another location"):
        build_inventory_projection(2, (row,))
    for rows in ((row, row), (row, replace(row, row_id="2"))):
        with pytest.raises(ValueError, match="unique"):
            build_inventory_projection(1, rows)
    projection = build_inventory_projection(1, (row,))
    with pytest.raises(ValueError, match="ascending"):
        sort_inventory_projection(projection, PlanSortColumn.PATH, SortDirection.DESCENDING)
    with pytest.raises(TypeError, match="enums"):
        sort_inventory_projection(projection, "size", SortDirection.ASCENDING)


def test_inventory_admits_source_populations_separately_before_retaining_first_excess(monkeypatch) -> None:
    monkeypatch.setattr(projection_module, "MAX_PLAN_REVIEW_ROWS", 2)
    warning = ScanWarning(ScanWarningCode.ACCESS_DENIED, None)
    rows = (_row("1", "one"), _row("2", "two"))
    projection = build_inventory_projection(1, rows, (warning, warning))
    assert len(projection.nodes) == 5
    with pytest.raises(InventoryProjectionPopulationLimitError) as domain:
        build_inventory_projection(1, (*rows, object()))
    assert domain.value.population == "domain"
    with pytest.raises(InventoryProjectionPopulationLimitError) as informational:
        build_inventory_projection(1, rows, (warning, warning, object()))
    assert informational.value.population == "informational"


def test_inventory_projection_supports_base_and_information_heavy_fixture_populations() -> None:
    # 100,000 files plus 20,000 implicit folders, excluding the internal root.
    stat = file_stat(size=7)
    rows = (_row(str(index + 1), f"folder{index // 5:05d}\\file{index:06d}", observed=stat) for index in range(100_000))
    warning = ScanWarning(ScanWarningCode.ACCESS_DENIED, None, "Information")
    projection = build_inventory_projection(1, rows, (warning for _ in range(120_000)))
    assert len(projection.nodes) - projection.warning_count - 1 == 120_000
    assert len(projection.nodes) - 1 == 240_000
    assert projection.nodes[0].rollup.domain_count == 100_000
    assert projection.nodes[0].rollup.size == 700_000
    assert len(projection.node_id_by_row_id) == 100_000
    assert len(projection.position_by_path_key) == 120_001
    order = sort_inventory_projection(projection, PlanSortColumn.SIZE, SortDirection.DESCENDING)
    assert len(order.ordered_source_positions) == 240_001
    assert projection.nodes[order.ordered_source_positions[-1]].warning is warning
