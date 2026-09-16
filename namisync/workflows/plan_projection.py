"""Immutable, bounded facts for the desktop plan-review tree."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from functools import cmp_to_key
from hashlib import blake2b
from types import MappingProxyType
from typing import Mapping

from namisync.core.models import EntryKind, FileStat
from namisync.core.pathing import fold_validated_path
from namisync.core.planning import OpId, OperationKind, Plan, PlanOperation

from .models import PlanArtifact
from .node_tree import (
    NodeTree,
    NodeTreeKind,
    _ValidatedNodeTreeMember,
    _build_validated_node_tree,
)
from .selection import derive_execution_selection


class PlanSortColumn(StrEnum):
    PATH = "path"
    FILENAME = "filename"
    SIZE = "size"
    MTIME = "mtime"


class SortDirection(StrEnum):
    ASCENDING = "ascending"
    DESCENDING = "descending"


@dataclass(frozen=True, slots=True, init=False)
class CompactUnsignedIntegers(Sequence[int]):
    """An immutable, random-access unsigned integer buffer."""

    _storage: bytes
    byte_width: int
    _count: int

    def __init__(self, values: Sequence[int], *, maximum: int | None = None) -> None:
        count = len(values)
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("compact integers must be exact nonnegative integers")
        largest = max(values, default=0) if maximum is None else maximum
        if type(largest) is not int or largest < 0:
            raise ValueError("compact integer maximum must be nonnegative")
        if any(value > largest for value in values):
            raise ValueError("compact integer exceeds declared maximum")
        width = 1 if largest < 2**8 else 2 if largest < 2**16 else 4 if largest < 2**32 else 8
        if largest >= 2**64:
            raise ValueError("compact integers exceed the supported range")
        storage = bytearray(count * width)
        for index, value in enumerate(values):
            start = index * width
            storage[start : start + width] = value.to_bytes(width, "little")
        object.__setattr__(self, "_storage", bytes(storage))
        object.__setattr__(self, "byte_width", width)
        object.__setattr__(self, "_count", count)

    @property
    def byte_length(self) -> int:
        return len(self._storage)

    def __len__(self) -> int:
        return self._count

    def __getitem__(self, index: int | slice) -> int | tuple[int, ...]:
        if isinstance(index, slice):
            return tuple(self[position] for position in range(*index.indices(self._count)))
        if type(index) is not int:
            raise TypeError("compact integer index must be an integer or slice")
        if index < 0:
            index += self._count
        if not 0 <= index < self._count:
            raise IndexError(index)
        start = index * self.byte_width
        return int.from_bytes(self._storage[start : start + self.byte_width], "little")

    def __iter__(self) -> Iterator[int]:
        for index in range(self._count):
            yield self[index]


@dataclass(frozen=True, slots=True)
class PlanProjectionNode:
    node_id: str
    display: str
    rel_path_key: str
    position: int
    depth: int
    parent_index: int | None
    subtree_end: int
    is_container: bool
    row_kind: str
    operation_id: str | None
    operation_kind: str | None
    reason: str | None
    blocked_reason: str | None
    selection: str
    selectable_operation_count: int
    selected_operation_count: int
    operation_count: int
    size: int | None
    mtime_ns: int | None
    dependency_count: int
    risk: str
    move_peer_id: str | None = None
    notice: str | None = None
    selection_exclusion_reason: str | None = None
    filename_key: str | None = None


@dataclass(frozen=True, slots=True)
class PlanProjection:
    request_id: str
    nodes: tuple[PlanProjectionNode, ...]
    position_by_node_id: Mapping[str, int]
    operation_node_id_by_id: Mapping[str, str]
    selected_operation_ids: frozenset[str]
    preflight_ready: bool = True
    preflight_refusal_count: int = 0
    warning_count: int = 0

    def __post_init__(self) -> None:
        nodes = tuple(self.nodes)
        positions = dict(self.position_by_node_id)
        operations = dict(self.operation_node_id_by_id)
        if type(self.preflight_ready) is not bool:
            raise TypeError("plan projection preflight readiness must be a bool")
        if type(self.preflight_refusal_count) is not int or self.preflight_refusal_count < 0:
            raise ValueError("plan projection refusal count must be nonnegative")
        if type(self.warning_count) is not int or self.warning_count < 0:
            raise ValueError("plan projection warning count must be nonnegative")
        if len(positions) != len(nodes):
            raise ValueError("plan projection node index is incomplete")
        for position, node in enumerate(nodes):
            if node.position != position or positions.get(node.node_id) != position:
                raise ValueError("plan projection node index is inconsistent")
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "position_by_node_id", MappingProxyType(positions))
        object.__setattr__(
            self,
            "operation_node_id_by_id",
            MappingProxyType(operations),
        )
        object.__setattr__(
            self,
            "selected_operation_ids",
            frozenset(self.selected_operation_ids),
        )

    def node_for_id(self, node_id: str) -> PlanProjectionNode:
        try:
            return self.nodes[self.position_by_node_id[node_id]]
        except KeyError:
            raise KeyError(node_id) from None


@dataclass(frozen=True, slots=True)
class PlanProjectionOrder:
    """One sibling sort expressed as source positions and inverse ranks."""

    projection: PlanProjection
    ordered_source_positions: CompactUnsignedIntegers
    order_rank_by_source_position: CompactUnsignedIntegers

    def __post_init__(self) -> None:
        if type(self.projection) is not PlanProjection:
            raise TypeError("ordered projection must use an exact PlanProjection")
        if type(self.ordered_source_positions) is not CompactUnsignedIntegers:
            raise TypeError("ordered source positions must be compact integers")
        if type(self.order_rank_by_source_position) is not CompactUnsignedIntegers:
            raise TypeError("order ranks must be compact integers")
        _validate_projection_topology(self.projection)
        count = len(self.projection.nodes)
        if len(self.ordered_source_positions) != count or len(self.order_rank_by_source_position) != count:
            raise ValueError("plan order must cover every source node")
        seen = bytearray(count)
        for rank, source_position in enumerate(self.ordered_source_positions):
            if source_position >= count or seen[source_position]:
                raise ValueError("plan order must be a permutation")
            seen[source_position] = 1
            if self.order_rank_by_source_position[source_position] != rank:
                raise ValueError("plan order ranks must invert the permutation")
        if count and self.ordered_source_positions[0] != 0:
            raise ValueError("plan order must begin with the source root")
        open_ancestors: list[int] = []
        for source_position in self.ordered_source_positions:
            node = self.projection.nodes[source_position]
            while len(open_ancestors) > node.depth:
                open_ancestors.pop()
            if node.depth == 0:
                if source_position != 0 or open_ancestors:
                    raise ValueError("plan order has an invalid root")
            elif len(open_ancestors) != node.depth or open_ancestors[-1] != node.parent_index:
                raise ValueError("plan order breaks source parent/subtree closure")
            open_ancestors.append(source_position)

    def _rebind_selection(self, projection: PlanProjection) -> PlanProjectionOrder:
        """Rebind after the owner-preserving selection transform."""

        if type(projection) is not PlanProjection:
            raise TypeError("selection rebind requires an exact PlanProjection")
        if projection.request_id != self.projection.request_id or len(projection.nodes) != len(self.projection.nodes):
            raise ValueError("selection rebind changed projection identity")
        rebound = object.__new__(PlanProjectionOrder)
        object.__setattr__(rebound, "projection", projection)
        object.__setattr__(rebound, "ordered_source_positions", self.ordered_source_positions)
        object.__setattr__(rebound, "order_rank_by_source_position", self.order_rank_by_source_position)
        return rebound


def build_plan_projection(
    request_id: str,
    artifact: PlanArtifact,
    *,
    user_deselected: frozenset[OpId] = frozenset(),
) -> PlanProjection:
    """Project operations, old-path ancestry, and all informational notices."""

    if type(request_id) is not str or not request_id:
        raise ValueError("request_id must be a nonempty string")
    if type(artifact) is not PlanArtifact:
        raise TypeError("artifact must be an exact PlanArtifact")
    plan = artifact.plan
    operations = {str(item.op_id): item for item in plan.operations}
    safety_decision = derive_execution_selection(plan)
    decision = (
        safety_decision
        if not user_deselected
        else derive_execution_selection(plan, user_deselected=user_deselected)
    )
    selected = frozenset(str(item) for item in decision.selection)
    excluded = {str(item.op_id): item.reason for item in decision.exclusions}
    selectable = frozenset(str(item) for item in safety_decision.selection)

    target_tree = _operation_tree(request_id, plan.operations, prior=False)
    drafts: list[dict[str, object]] = []
    operation_draft_by_id: dict[str, int] = {}
    target_draft_by_tree_position: dict[int, int] = {}
    _append_operation_tree(
        drafts,
        target_tree,
        plan,
        operations,
        selected,
        selectable,
        excluded,
        target_draft_by_tree_position,
        operation_draft_by_id,
        parent_override=None,
        row_prefix="",
    )

    prior_operations = tuple(
        item for item in plan.operations if item.prior_target_rel_path is not None
    )
    peer_pairs: list[tuple[int, int]] = []
    if prior_operations:
        prior_group = len(drafts)
        drafts.append(
            _structural_draft(
                _projection_id(b"NamiSyncPriorV1", request_id),
                "Previous paths",
                "",
                1,
                0,
                row_kind="prior-group",
                is_container=True,
            )
        )
        prior_tree = _operation_tree(request_id + ":prior", prior_operations, prior=True)
        prior_draft_by_tree_position: dict[int, int] = {}
        prior_operation_draft_by_id: dict[str, int] = {}
        _append_operation_tree(
            drafts,
            prior_tree,
            plan,
            operations,
            selected,
            frozenset(),
            excluded,
            prior_draft_by_tree_position,
            prior_operation_draft_by_id,
            parent_override=prior_group,
            row_prefix="prior-",
        )
        for operation_id, target_draft in operation_draft_by_id.items():
            prior_draft = prior_operation_draft_by_id.get(operation_id)
            if prior_draft is not None:
                peer_pairs.append((target_draft, prior_draft))

    for side, warning in (
        *(("source", item) for item in artifact.source_scan.warnings),
        *(("target", item) for item in artifact.target_scan.warnings),
    ):
        display = f"{side}: {warning.rel_path or 'root'} — {warning.code.value}"
        if warning.detail:
            display += f" — {warning.detail}"
        drafts.append(_notice_draft(request_id, len(drafts), display))
    for refusal in artifact.verdict.refusals:
        drafts.append(
            _notice_draft(
                request_id,
                len(drafts),
                (
                    f"plan: {refusal.code.value}"
                    + (f" — {refusal.detail}" if refusal.detail else "")
                ),
            )
        )

    for target, prior in peer_pairs:
        drafts[target]["move_peer_id"] = drafts[prior]["node_id"]
        drafts[prior]["move_peer_id"] = drafts[target]["node_id"]

    return _materialize_projection(
        request_id,
        drafts,
        selected,
        operation_draft_by_id,
        preflight_ready=artifact.verdict.ok,
        preflight_refusal_count=len(artifact.verdict.refusals),
        warning_count=(
            len(artifact.source_scan.warnings) + len(artifact.target_scan.warnings)
        ),
    )


def sort_plan_projection(
    projection: PlanProjection,
    column: PlanSortColumn,
    direction: SortDirection,
) -> PlanProjectionOrder:
    """Sort complete sibling sets before any visible window is requested."""

    if type(projection) is not PlanProjection:
        raise TypeError("projection must be an exact PlanProjection")
    _validate_projection_topology(projection)
    if type(column) is not PlanSortColumn or type(direction) is not SortDirection:
        raise TypeError("plan sort must use exact enums")
    if column is PlanSortColumn.PATH and direction is not SortDirection.ASCENDING:
        raise ValueError("canonical path sort supports ascending only")
    nodes = projection.nodes
    children: dict[int, list[int]] = {}
    for index, node in enumerate(nodes[1:], 1):
        assert node.parent_index is not None
        children.setdefault(node.parent_index, []).append(index)
    key = cmp_to_key(lambda left, right: _compare_nodes(nodes[left], nodes[right], column, direction))
    for siblings in children.values():
        siblings.sort(key=key)

    ordered: list[int] = []
    stack = [0]
    while stack:
        current = stack.pop()
        ordered.append(current)
        stack.extend(reversed(children.get(current, ())))
    inverse = [0] * len(ordered)
    for rank, source_position in enumerate(ordered):
        inverse[source_position] = rank
    children.clear()
    return PlanProjectionOrder(
        projection,
        CompactUnsignedIntegers(ordered, maximum=max(len(nodes) - 1, 0)),
        CompactUnsignedIntegers(inverse, maximum=max(len(nodes) - 1, 0)),
    )


def _validate_projection_topology(projection: PlanProjection) -> None:
    count = len(projection.nodes)
    nodes = projection.nodes
    if not nodes or type(nodes[0]) is not PlanProjectionNode:
        raise ValueError("plan order requires one exact source root")
    open_containers: list[int] = []
    for source_position, node in enumerate(nodes):
        if type(node) is not PlanProjectionNode or node.position != source_position:
            raise ValueError("plan order source positions are inconsistent")
        if (
            type(node.position) is not int
            or type(node.depth) is not int
            or type(node.subtree_end) is not int
            or (node.parent_index is not None and type(node.parent_index) is not int)
            or type(node.is_container) is not bool
        ):
            raise TypeError("plan order source topology uses invalid field types")
        if node.subtree_end <= source_position or node.subtree_end > count:
            raise ValueError("plan order source subtree extent is invalid")
        if not node.is_container and node.subtree_end != source_position + 1:
            raise ValueError("plan order source leaf spans descendants")
        while open_containers and nodes[open_containers[-1]].subtree_end <= source_position:
            open_containers.pop()
        if source_position == 0:
            if node.depth != 0 or node.parent_index is not None or node.subtree_end != count:
                raise ValueError("plan order source root is invalid")
        else:
            if not open_containers or node.parent_index != open_containers[-1]:
                raise ValueError("plan order source parent/subtree closure is invalid")
            parent = nodes[node.parent_index]
            if node.depth != parent.depth + 1 or node.subtree_end > parent.subtree_end:
                raise ValueError("plan order source depth/subtree closure is invalid")
        if node.is_container and node.subtree_end > source_position + 1:
            open_containers.append(source_position)


def apply_plan_projection_selection(
    projection: PlanProjection,
    *,
    selected_operation_ids: frozenset[str],
    exclusion_reasons: Mapping[str, str | None],
) -> PlanProjection:
    """Replace selection facts without rebuilding immutable plan structure."""

    if type(projection) is not PlanProjection:
        raise TypeError("projection must be an exact PlanProjection")
    if not isinstance(selected_operation_ids, frozenset):
        raise TypeError("selected operation ids must be a frozenset")
    known = set(projection.operation_node_id_by_id)
    if not selected_operation_ids <= known:
        raise ValueError("selection contains an unknown operation")
    reasons = dict(exclusion_reasons)
    if not set(reasons) <= known:
        raise ValueError("selection exclusions contain an unknown operation")

    selected_counts = [0] * len(projection.nodes)
    for operation_id, node_id in projection.operation_node_id_by_id.items():
        node = projection.node_for_id(node_id)
        if operation_id in selected_operation_ids:
            if node.selectable_operation_count != 1:
                raise ValueError("selection contains an unavailable operation")
            selected_counts[node.position] = 1
    for position in range(len(projection.nodes) - 1, 0, -1):
        parent = projection.nodes[position].parent_index
        assert parent is not None
        selected_counts[parent] += selected_counts[position]

    operation_ids_by_node_id = {
        node_id: operation_id
        for operation_id, node_id in projection.operation_node_id_by_id.items()
    }
    nodes = tuple(
        replace(
            node,
            selected_operation_count=selected_counts[node.position],
            selection=(
                "disabled"
                if node.row_kind.startswith("prior-") or node.row_kind == "notice"
                else _selection_state(
                    node.selectable_operation_count,
                    selected_counts[node.position],
                    node.operation_count,
                )
            ),
            selection_exclusion_reason=(
                reasons.get(operation_ids_by_node_id[node.node_id])
                if node.node_id in operation_ids_by_node_id
                and operation_ids_by_node_id[node.node_id]
                not in selected_operation_ids
                else None
            ),
        )
        for node in projection.nodes
    )
    return PlanProjection(
        projection.request_id,
        nodes,
        projection.position_by_node_id,
        projection.operation_node_id_by_id,
        selected_operation_ids,
        projection.preflight_ready,
        projection.preflight_refusal_count,
        projection.warning_count,
    )


def _operation_tree(
    scope_identity: str,
    operations: tuple[PlanOperation, ...],
    *,
    prior: bool,
) -> NodeTree:
    def member(operation: PlanOperation) -> _ValidatedNodeTreeMember:
        rel_path = (
            operation.prior_target_rel_path if prior else operation.target_rel_path
        )
        assert rel_path is not None
        canonical = rel_path.replace("/", "\\")
        return _ValidatedNodeTreeMember(
            str(operation.op_id),
            rel_path,
            fold_validated_path(canonical),
            False if prior else operation.kind is OperationKind.MKDIR,
        )

    return _build_validated_node_tree(
        tree_kind=NodeTreeKind.PLAN,
        scope_identity=scope_identity,
        members=(member(operation) for operation in operations),
    )


def _append_operation_tree(
    drafts: list[dict[str, object]],
    tree: NodeTree,
    plan: Plan,
    operations: Mapping[str, PlanOperation],
    selected: frozenset[str],
    selectable: frozenset[str],
    excluded: Mapping[str, str],
    draft_by_tree_position: dict[int, int],
    operation_draft_by_id: dict[str, int],
    *,
    parent_override: int | None,
    row_prefix: str,
) -> None:
    start_position = 0 if parent_override is None else 1
    direct_selectable = [0] * len(tree.nodes)
    direct_selected = [0] * len(tree.nodes)
    subtree_selectable = [0] * len(tree.nodes)
    subtree_selected = [0] * len(tree.nodes)
    subtree_operations = [0] * len(tree.nodes)
    for node in tree.nodes:
        ids = node.member_ids
        direct_selectable[node.position] = sum(item in selectable for item in ids)
        direct_selected[node.position] = sum(item in selected for item in ids)
        subtree_selectable[node.position] = direct_selectable[node.position]
        subtree_selected[node.position] = direct_selected[node.position]
        subtree_operations[node.position] = len(ids)
    for position in range(len(tree.nodes) - 1, 0, -1):
        parent = tree.nodes[position].parent_index
        assert parent is not None
        subtree_selectable[parent] += subtree_selectable[position]
        subtree_selected[parent] += subtree_selected[position]
        subtree_operations[parent] += subtree_operations[position]

    for node in tree.nodes[start_position:]:
        if node.parent_index is None:
            parent = None
        elif parent_override is not None and node.parent_index == 0:
            parent = parent_override
        else:
            parent = draft_by_tree_position[node.parent_index]
        member_ids = node.member_ids
        singular = operations[member_ids[0]] if len(member_ids) == 1 else None
        draft_index = len(drafts)
        draft_by_tree_position[node.position] = draft_index
        drafts.append(
            _operation_draft(
                node.node_id,
                _basename(node.rel_path),
                node.rel_path_key,
                _basename(node.rel_path).casefold() if node.rel_path else None,
                node.depth + (1 if parent_override is not None else 0),
                parent,
                node.is_container or len(member_ids) > 1,
                (
                    row_prefix + "operation-group"
                    if len(member_ids) > 1
                    else row_prefix + "operation"
                    if singular is not None
                    else row_prefix + "folder"
                ),
                singular,
                _selection_state(
                    subtree_selectable[node.position],
                    subtree_selected[node.position],
                    subtree_operations[node.position],
                ),
                subtree_selectable[node.position],
                subtree_selected[node.position],
                subtree_operations[node.position],
                plan,
                None if singular is None else excluded.get(str(singular.op_id)),
            )
        )
        if singular is not None:
            operation_draft_by_id[str(singular.op_id)] = draft_index
        if len(member_ids) > 1:
            for operation_id in member_ids:
                operation = operations[operation_id]
                member_index = len(drafts)
                operation_draft_by_id[operation_id] = member_index
                drafts.append(
                    _operation_draft(
                        _member_node_id(tree.scope_identity, operation_id),
                        operation.kind.value.replace("_", " "),
                        node.rel_path_key,
                        _basename(node.rel_path).casefold() if node.rel_path else None,
                        node.depth + 1 + (1 if parent_override is not None else 0),
                        draft_index,
                        False,
                        row_prefix + "operation",
                        operation,
                        _selection_state(
                            int(operation_id in selectable),
                            int(operation_id in selected),
                            1,
                        ),
                        int(operation_id in selectable),
                        int(operation_id in selected),
                        1,
                        plan,
                        excluded.get(operation_id),
                    )
                )


def _operation_draft(
    node_id: str,
    display: str,
    rel_path_key: str,
    filename_key: str | None,
    depth: int,
    parent: int | None,
    is_container: bool,
    row_kind: str,
    operation: PlanOperation | None,
    selection: str,
    selectable_count: int,
    selected_count: int,
    operation_count: int,
    plan: Plan,
    selection_exclusion_reason: str | None,
) -> dict[str, object]:
    stat = None if operation is None else _operation_stat(operation)
    prior = row_kind.startswith("prior-")
    return {
        "node_id": node_id,
        "display": display or "Plan",
        "rel_path_key": rel_path_key,
        "depth": depth,
        "parent": parent,
        "is_container": is_container,
        "row_kind": row_kind,
        "operation_id": None if operation is None or prior else str(operation.op_id),
        "operation_kind": None if operation is None else operation.kind.value,
        "reason": None if operation is None else operation.reason.value,
        "blocked_reason": None if operation is None or operation.blocked_reason is None else operation.blocked_reason.value,
        "selection": "disabled" if prior else selection,
        "selectable_operation_count": 0 if prior else selectable_count,
        "selected_operation_count": 0 if prior else selected_count,
        "operation_count": operation_count,
        "size": None if prior or stat is None or stat.kind is not EntryKind.FILE else stat.size,
        "mtime_ns": None if prior or stat is None else stat.mtime_ns,
        "dependency_count": 0 if operation is None else len(operation.dependencies),
        "risk": "none" if operation is None else _operation_risk(operation, plan),
        "move_peer_id": None,
        "notice": None,
        "selection_exclusion_reason": (
            None if prior else selection_exclusion_reason
        ),
        "filename_key": filename_key,
    }


def _structural_draft(
    node_id: str,
    display: str,
    rel_path_key: str,
    depth: int,
    parent: int | None,
    *,
    row_kind: str,
    is_container: bool,
) -> dict[str, object]:
    return {
        "node_id": node_id, "display": display, "rel_path_key": rel_path_key,
        "depth": depth, "parent": parent, "is_container": is_container,
        "row_kind": row_kind, "operation_id": None, "operation_kind": None,
        "reason": None, "blocked_reason": None, "selection": "disabled",
        "selectable_operation_count": 0, "selected_operation_count": 0,
        "operation_count": 0, "size": None, "mtime_ns": None,
        "dependency_count": 0, "risk": "none", "move_peer_id": None,
        "notice": None, "selection_exclusion_reason": None,
        "filename_key": _basename(rel_path_key).casefold() if rel_path_key else None,
    }


def _notice_draft(request_id: str, ordinal: int, display: str) -> dict[str, object]:
    draft = _structural_draft(
        _projection_id(b"NamiSyncNoticeV1", request_id, str(ordinal)),
        display,
        "",
        1,
        0,
        row_kind="notice",
        is_container=False,
    )
    draft["notice"] = display
    return draft


def _materialize_projection(
    request_id: str,
    drafts: list[dict[str, object]],
    selected: frozenset[str],
    operation_draft_by_id: Mapping[str, int],
    *,
    preflight_ready: bool,
    preflight_refusal_count: int,
    warning_count: int,
) -> PlanProjection:
    subtree_ends = [index + 1 for index in range(len(drafts))]
    for index in range(len(drafts) - 1, 0, -1):
        parent = int(drafts[index]["parent"])
        subtree_ends[parent] = max(subtree_ends[parent], subtree_ends[index])
    nodes: list[PlanProjectionNode] = []
    for index, draft in enumerate(drafts):
        nodes.append(PlanProjectionNode(
            node_id=draft["node_id"],
            display=draft["display"],
            rel_path_key=draft["rel_path_key"],
            position=index,
            depth=draft["depth"],
            parent_index=None if draft["parent"] is None else int(draft["parent"]),
            subtree_end=subtree_ends[index],
            is_container=draft["is_container"],
            row_kind=draft["row_kind"],
            operation_id=draft["operation_id"],
            operation_kind=draft["operation_kind"],
            reason=draft["reason"],
            blocked_reason=draft["blocked_reason"],
            selection=draft["selection"],
            selectable_operation_count=draft["selectable_operation_count"],
            selected_operation_count=draft["selected_operation_count"],
            operation_count=draft["operation_count"],
            size=draft["size"],
            mtime_ns=draft["mtime_ns"],
            dependency_count=draft["dependency_count"],
            risk=draft["risk"],
            move_peer_id=draft["move_peer_id"],
            notice=draft["notice"],
            selection_exclusion_reason=draft["selection_exclusion_reason"],
            filename_key=draft["filename_key"],
        ))
        drafts[index] = None  # type: ignore[list-item]
    frozen_nodes = tuple(nodes)
    nodes.clear()
    drafts.clear()
    subtree_ends.clear()
    operation_lookup = {
        operation_id: frozen_nodes[index].node_id
        for operation_id, index in operation_draft_by_id.items()
    }
    return PlanProjection(
        request_id,
        frozen_nodes,
        {node.node_id: node.position for node in frozen_nodes},
        operation_lookup,
        selected,
        preflight_ready,
        preflight_refusal_count,
        warning_count,
    )


def _selection_state(selectable: int, selected: int, total: int) -> str:
    if selectable == 0:
        return "disabled"
    if selected == selectable and selectable == total:
        return "selected"
    if selected == 0 and selectable == total:
        return "unselected"
    return "mixed"


def _operation_stat(operation: PlanOperation) -> FileStat | None:
    return operation.intended or operation.source_expected or operation.target_expected or operation.prior_target_expected


def _operation_risk(operation: PlanOperation, plan: Plan) -> str:
    if operation.kind is OperationKind.UPDATE:
        return "reversible" if plan.trash_on_update else "irreversible"
    if operation.kind in {OperationKind.MOVE_UPDATE, OperationKind.TRASH}:
        return "reversible"
    if operation.kind is OperationKind.DELETE:
        return "irreversible"
    return "none"


def _compare_nodes(left: PlanProjectionNode, right: PlanProjectionNode, column: PlanSortColumn, direction: SortDirection) -> int:
    if column is PlanSortColumn.PATH:
        result = _compare((left.rel_path_key, left.node_id), (right.rel_path_key, right.node_id))
        return result
    if column is PlanSortColumn.FILENAME:
        left_value: object | None = left.filename_key
        right_value: object | None = right.filename_key
    elif column is PlanSortColumn.SIZE:
        left_value, right_value = left.size, right.size
    else:
        left_value, right_value = left.mtime_ns, right.mtime_ns
    if left_value is None or right_value is None:
        if left_value is None and right_value is None:
            return _compare((left.rel_path_key, left.node_id), (right.rel_path_key, right.node_id))
        return 1 if left_value is None else -1
    result = _compare(left_value, right_value)
    if direction is SortDirection.DESCENDING:
        result = -result
    return result or _compare((left.rel_path_key, left.node_id), (right.rel_path_key, right.node_id))


def _compare(left: object, right: object) -> int:
    return (left > right) - (left < right)


def _basename(path: str) -> str:
    return path.rsplit("\\", 1)[-1] if path else "Plan"


def _member_node_id(request_id: str, operation_id: str) -> str:
    return _projection_id(b"NamiSyncMemberV1", request_id, operation_id)


def _projection_id(person: bytes, *values: str) -> str:
    digest = blake2b(digest_size=16, person=person)
    for value in values:
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return f"node-{digest.hexdigest()}"


__all__ = [
    "CompactUnsignedIntegers",
    "PlanProjection",
    "PlanProjectionNode",
    "PlanProjectionOrder",
    "PlanSortColumn",
    "SortDirection",
    "apply_plan_projection_selection",
    "build_plan_projection",
    "sort_plan_projection",
]
