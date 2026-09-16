"""Pure visible-tree derivation for desktop presentation adapters."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Generic, Protocol, TypeVar


_MAX_SEARCH_BYTES = 65_536
_MAX_WINDOW_ROWS = 256


class VisibleNodeLike(Protocol):
    """Read-only structural view supplied by a workflow projection."""

    @property
    def node_id(self) -> str: ...

    @property
    def display(self) -> str: ...

    @property
    def position(self) -> int: ...

    @property
    def depth(self) -> int: ...

    @property
    def parent_index(self) -> int | None: ...

    @property
    def subtree_end(self) -> int: ...

    @property
    def is_container(self) -> bool: ...


_VisibleNodeT = TypeVar("_VisibleNodeT", bound=VisibleNodeLike)


@dataclass(frozen=True, slots=True)
class VisibleSequenceParameters:
    """Immutable collapse, display-search, and caller-decided filter inputs."""

    collapsed_node_ids: frozenset[str] = field(default_factory=frozenset)
    search_query: str = ""
    match_counts_by_node_id: Mapping[str, int] | None = None

    def __post_init__(self) -> None:
        _require_search(self.search_query)
        collapsed = _snapshot_node_ids(
            self.collapsed_node_ids,
            "collapsed_node_ids",
        )
        object.__setattr__(self, "collapsed_node_ids", collapsed)

        if self.match_counts_by_node_id is None:
            return
        if not isinstance(self.match_counts_by_node_id, Mapping):
            raise TypeError("match_counts_by_node_id must be a mapping or None")
        counts: dict[str, int] = {}
        for node_id, count in self.match_counts_by_node_id.items():
            _require_text(node_id, "match-count node id", nonempty=True)
            _require_exact_nonnegative_int(count, "match count")
            counts[node_id] = count
        object.__setattr__(
            self,
            "match_counts_by_node_id",
            MappingProxyType(counts),
        )


@dataclass(frozen=True, slots=True)
class VisibleSequence(Generic[_VisibleNodeT]):
    """One immutable derivation over the complete original node tuple."""

    nodes: tuple[_VisibleNodeT, ...]
    visible_source_positions: Sequence[int]
    source_position_by_node_id: Mapping[str, int]
    visible_index_by_source_position: Sequence[int]
    sibling_ordinals: Sequence[int]
    retained_direct_child_counts: Sequence[int]
    collapsed_node_ids: frozenset[str]
    filtered_item_count: int | None

    def __post_init__(self) -> None:
        nodes = tuple(self.nodes)
        from namisync.workflows import CompactUnsignedIntegers

        positions = self.visible_source_positions
        if type(positions) is not CompactUnsignedIntegers:
            raise TypeError("visible source positions must be compact integers")
        collapsed = _snapshot_node_ids(
            self.collapsed_node_ids,
            "collapsed_node_ids",
        )
        source_lookup = dict(self.source_position_by_node_id)
        if len(source_lookup) != len(nodes):
            raise ValueError("source node lookup does not match the node array")
        for position, node in enumerate(nodes):
            if node.node_id not in source_lookup:
                raise ValueError(
                    "source node lookup does not match the node array"
                )
            source_position = _require_exact_nonnegative_int(
                source_lookup[node.node_id],
                "source lookup position",
            )
            if source_position != position:
                raise ValueError(
                    "source node lookup does not match the node array"
                )

        inverse = self.visible_index_by_source_position
        ordinals = self.sibling_ordinals
        child_counts = self.retained_direct_child_counts
        if any(type(value) is not CompactUnsignedIntegers for value in (inverse, ordinals, child_counts)):
            raise TypeError("visible indexes and counts must be compact integers")
        if len(inverse) != len(nodes) or len(ordinals) != len(positions) or len(child_counts) != len(nodes):
            raise ValueError("compact visible metadata has inconsistent lengths")
        seen: set[int] = set()
        sibling_counts: dict[int | None, int] = {}
        visible_ancestors: list[int] = []
        for visible_index, position in enumerate(positions):
            _require_exact_nonnegative_int(position, "visible position")
            if position >= len(nodes) or position in seen or inverse[position] != visible_index:
                raise ValueError("visible source positions and inverse indexes disagree")
            seen.add(position)
            parent = nodes[position].parent_index
            while len(visible_ancestors) > nodes[position].depth:
                visible_ancestors.pop()
            if nodes[position].depth == 0:
                if visible_index != 0 or position != 0 or visible_ancestors:
                    raise ValueError("visible order has an invalid root")
            elif (
                len(visible_ancestors) != nodes[position].depth
                or visible_ancestors[-1] != parent
            ):
                raise ValueError("visible order breaks parent/subtree closure")
            if parent is not None:
                parent_visible = inverse[parent]
                if parent_visible >= visible_index:
                    raise ValueError("a visible node must retain its preceding parent")
            expected_ordinal = sibling_counts.get(parent, 0) + 1
            sibling_counts[parent] = expected_ordinal
            if ordinals[visible_index] != expected_ordinal:
                raise ValueError("sibling ordinals are inconsistent")
            visible_ancestors.append(position)
        sentinel = len(nodes)
        if any(inverse[position] != sentinel for position in range(len(nodes)) if position not in seen):
            raise ValueError("hidden source positions must use the inverse sentinel")
        source_child_counts = [0] * len(nodes)
        for node in nodes[1:]:
            assert node.parent_index is not None
            source_child_counts[node.parent_index] += 1
        for position, count in enumerate(child_counts):
            if count and not nodes[position].is_container:
                raise ValueError("only containers may retain direct children")
            if count > source_child_counts[position]:
                raise ValueError("retained child count exceeds source children")
        for parent, visible_count in sibling_counts.items():
            if parent is not None and visible_count > child_counts[parent]:
                raise ValueError("visible children exceed the retained child count")
        visible_child_counts: dict[int, int] = {}
        for source_position in positions:
            parent = nodes[source_position].parent_index
            if parent is not None:
                visible_child_counts[parent] = visible_child_counts.get(parent, 0) + 1
        for source_position in positions:
            visible_count = visible_child_counts.get(source_position, 0)
            retained_count = child_counts[source_position]
            if nodes[source_position].node_id in collapsed:
                if visible_count:
                    raise ValueError("a collapsed container cannot expose visible children")
            elif visible_count != retained_count:
                raise ValueError("expanded child metadata must equal visible children")
        for node_id in collapsed:
            try:
                node = nodes[source_lookup[node_id]]
            except KeyError as error:
                raise ValueError("collapsed node id is unknown") from error
            if not node.is_container:
                raise ValueError("only containers may be collapsed")
        if self.filtered_item_count is not None:
            _require_exact_nonnegative_int(
                self.filtered_item_count,
                "filtered_item_count",
            )

        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "visible_source_positions", positions)
        object.__setattr__(
            self,
            "source_position_by_node_id",
            MappingProxyType(source_lookup),
        )
        object.__setattr__(self, "collapsed_node_ids", collapsed)

    @property
    def visible_positions(self) -> Sequence[int]:
        return self.visible_source_positions

    def _rebind_nodes(
        self,
        nodes: tuple[_VisibleNodeT, ...],
        source_position_by_node_id: Mapping[str, int],
    ) -> VisibleSequence[_VisibleNodeT]:
        """Rebind after an owner-proven topology-preserving replacement."""

        if type(nodes) is not tuple or len(nodes) != len(self.nodes):
            raise ValueError("visible node rebind changed source topology")
        rebound = object.__new__(VisibleSequence)
        for name, value in (
            ("nodes", nodes),
            ("visible_source_positions", self.visible_source_positions),
            ("source_position_by_node_id", MappingProxyType(dict(source_position_by_node_id))),
            ("visible_index_by_source_position", self.visible_index_by_source_position),
            ("sibling_ordinals", self.sibling_ordinals),
            ("retained_direct_child_counts", self.retained_direct_child_counts),
            ("collapsed_node_ids", self.collapsed_node_ids),
            ("filtered_item_count", self.filtered_item_count),
        ):
            object.__setattr__(rebound, name, value)
        return rebound


@dataclass(frozen=True, slots=True)
class VisibleWindowRow(Generic[_VisibleNodeT]):
    """One bounded presentation row plus active-tree accessibility metadata."""

    node: _VisibleNodeT
    visible_index: int
    parent_visible_index: int | None
    first_child_visible_index: int | None
    position_in_set: int
    set_size: int
    expanded: bool | None

    def __post_init__(self) -> None:
        _validate_node_fields(self.node)
        _require_exact_nonnegative_int(self.visible_index, "visible_index")
        if self.parent_visible_index is not None:
            _require_exact_nonnegative_int(
                self.parent_visible_index,
                "parent_visible_index",
            )
            if self.parent_visible_index >= self.visible_index:
                raise ValueError("a visible parent must precede its child")
        if self.first_child_visible_index is not None:
            _require_exact_nonnegative_int(
                self.first_child_visible_index,
                "first_child_visible_index",
            )
            if self.first_child_visible_index <= self.visible_index:
                raise ValueError("a visible child must follow its parent")
        _require_exact_nonnegative_int(self.position_in_set, "position_in_set")
        _require_exact_nonnegative_int(self.set_size, "set_size")
        if self.position_in_set == 0 or self.position_in_set > self.set_size:
            raise ValueError("position_in_set must be within its sibling set")
        if self.expanded is not None:
            if type(self.expanded) is not bool:
                raise TypeError("expanded state must be a bool or None")
            if not self.node.is_container:
                raise ValueError("leaf expanded state must be None")
        if (self.first_child_visible_index is not None) != (
            self.expanded is True
        ):
            raise ValueError(
                "expanded state and visible-child metadata are inconsistent"
            )


@dataclass(frozen=True, slots=True)
class VisibleWindow(Generic[_VisibleNodeT]):
    """A bounded window into one derived visible sequence."""

    offset: int
    total: int
    rows: tuple[VisibleWindowRow[_VisibleNodeT], ...]

    def __post_init__(self) -> None:
        _require_exact_nonnegative_int(self.offset, "offset")
        _require_exact_nonnegative_int(self.total, "total")
        rows = tuple(self.rows)
        if len(rows) > _MAX_WINDOW_ROWS:
            raise ValueError("visible window exceeds the row limit")
        if any(type(row) is not VisibleWindowRow for row in rows):
            raise TypeError("window rows must be VisibleWindowRow values")
        for relative_index, row in enumerate(rows):
            if row.visible_index != self.offset + relative_index:
                raise ValueError("window row indexes must be contiguous")
            if row.visible_index >= self.total:
                raise ValueError("window row index exceeds the visible total")
            if (
                row.first_child_visible_index is not None
                and row.first_child_visible_index >= self.total
            ):
                raise ValueError("visible child index exceeds the visible total")
        object.__setattr__(self, "rows", rows)


@dataclass(frozen=True, slots=True)
class VisibleAnchor:
    """A visible node identity and its index in the active derivation."""

    node_id: str
    index: int

    def __post_init__(self) -> None:
        _require_text(self.node_id, "node_id", nonempty=True)
        _require_exact_nonnegative_int(self.index, "index")


def derive_visible_sequence(
    nodes: Sequence[_VisibleNodeT],
    parameters: VisibleSequenceParameters,
    *,
    ordered_source_positions: Sequence[int] | None = None,
) -> VisibleSequence[_VisibleNodeT]:
    """Validate and derive one visible sequence without retaining state."""

    if type(parameters) is not VisibleSequenceParameters:
        raise TypeError("parameters must be VisibleSequenceParameters")

    # This check deliberately precedes every access to the supplied node array.
    _require_search(parameters.search_query)
    original_nodes = tuple(nodes)
    _validate_structure(original_nodes)
    from namisync.workflows import CompactUnsignedIntegers

    order = CompactUnsignedIntegers(
        tuple(range(len(original_nodes))) if ordered_source_positions is None else tuple(ordered_source_positions),
        maximum=max(len(original_nodes) - 1, 0),
    )
    _validate_order(original_nodes, order)
    inverse_values = [0] * len(original_nodes)
    for rank, source_position in enumerate(order):
        inverse_values[source_position] = rank
    inverse_order = CompactUnsignedIntegers(
        inverse_values, maximum=max(len(original_nodes) - 1, 0)
    )

    position_by_id = {
        node.node_id: node.position for node in original_nodes
    }
    return _derive_visible_sequence_from_validated(
        original_nodes,
        position_by_id,
        parameters,
        ordered_source_positions=order,
        order_rank_by_source_position=inverse_order,
    )


def _derive_visible_sequence_from_validated(
    nodes: tuple[_VisibleNodeT, ...],
    position_by_id: Mapping[str, int],
    parameters: VisibleSequenceParameters,
    *,
    ordered_source_positions: Sequence[int] | None = None,
    order_rank_by_source_position: Sequence[int] | None = None,
    match_mask_by_position: bytes | None = None,
) -> VisibleSequence[_VisibleNodeT]:
    """Derive from exact immutable structure already validated by its owner."""

    if type(nodes) is not tuple:
        raise TypeError("validated nodes must be an exact tuple")
    if type(parameters) is not VisibleSequenceParameters:
        raise TypeError("parameters must be VisibleSequenceParameters")
    _require_search(parameters.search_query)
    from namisync.workflows import CompactUnsignedIntegers

    if ordered_source_positions is None:
        ordered_source_positions = CompactUnsignedIntegers(
            tuple(range(len(nodes))), maximum=max(len(nodes) - 1, 0)
        )
    if type(ordered_source_positions) is not CompactUnsignedIntegers:
        raise TypeError("validated order must be compact integers")
    if order_rank_by_source_position is None:
        inverse_values = [0] * len(nodes)
        for rank, source_position in enumerate(ordered_source_positions):
            inverse_values[source_position] = rank
        order_rank_by_source_position = CompactUnsignedIntegers(
            inverse_values, maximum=max(len(nodes) - 1, 0)
        )
    if type(order_rank_by_source_position) is not CompactUnsignedIntegers:
        raise TypeError("validated inverse order must be compact integers")
    original_nodes = nodes
    collapsed_positions: set[int] = set()
    for node_id in parameters.collapsed_node_ids:
        try:
            position = position_by_id[node_id]
        except KeyError as error:
            raise ValueError("collapsed node id is unknown") from error
        if not original_nodes[position].is_container:
            raise ValueError("only containers may be collapsed")
        collapsed_positions.add(position)

    counts = parameters.match_counts_by_node_id
    if match_mask_by_position is not None:
        if type(match_mask_by_position) is not bytes:
            raise TypeError("positional match mask must be exact bytes or None")
        if counts is not None:
            raise ValueError("positional match mask conflicts with id counts")
        if len(match_mask_by_position) != len(original_nodes):
            raise ValueError("positional match mask must match the node array")
        if any(value not in (0, 1) for value in match_mask_by_position):
            raise ValueError("positional match mask must contain only zero or one")
    if counts is not None:
        unknown_ids = counts.keys() - position_by_id.keys()
        if unknown_ids:
            raise ValueError("match-count node id is unknown")

    query = parameters.search_query.casefold()
    folded_query_is_ascii = query.isascii()
    filtered_item_count = (
        0 if counts is not None or match_mask_by_position is not None else None
    )
    all_nodes_retained = (
        not query and counts is None and match_mask_by_position is None
    )
    retained_positions: set[int] = set()
    retained_direct_child_counts = [0] * len(original_nodes)
    if not all_nodes_retained:
        for position, node in enumerate(original_nodes):
            if counts is not None:
                weight = counts.get(node.node_id, 0)
            elif match_mask_by_position is not None:
                weight = match_mask_by_position[position]
            else:
                weight = 1
            if weight == 0:
                continue
            if not query:
                search_match = True
            else:
                display = node.display
                if display.isascii():
                    if not folded_query_is_ascii:
                        continue
                    folded_display = (
                        display if display.islower() else display.lower()
                    )
                else:
                    folded_display = display.casefold()
                search_match = query in folded_display
            if not search_match:
                continue
            if filtered_item_count is not None:
                filtered_item_count += weight
            retained_position: int | None = position
            while (
                retained_position is not None
                and retained_position not in retained_positions
            ):
                retained_positions.add(retained_position)
                parent = original_nodes[retained_position].parent_index
                if parent is not None:
                    retained_direct_child_counts[parent] += 1
                retained_position = parent

    if all_nodes_retained:
        for node in original_nodes[1:]:
            assert node.parent_index is not None
            retained_direct_child_counts[node.parent_index] += 1

    visible_positions: list[int] = []
    collapsed_depth: int | None = None
    sibling_counts: dict[int | None, int] = {}
    sibling_ordinals: list[int] = []
    visible_candidates = (
        ordered_source_positions
        if all_nodes_retained
        else sorted(retained_positions, key=order_rank_by_source_position.__getitem__)
    )
    for position in visible_candidates:
        node = original_nodes[position]
        if collapsed_depth is not None:
            if node.depth > collapsed_depth:
                continue
            collapsed_depth = None
        if not all_nodes_retained and position not in retained_positions:
            continue
        visible_positions.append(position)
        ordinal = sibling_counts.get(node.parent_index, 0) + 1
        sibling_counts[node.parent_index] = ordinal
        sibling_ordinals.append(ordinal)
        if position in collapsed_positions:
            collapsed_depth = node.depth

    positions = CompactUnsignedIntegers(visible_positions, maximum=max(len(original_nodes), 0))
    sentinel = len(original_nodes)
    inverse = [sentinel] * len(original_nodes)
    for visible_index, position in enumerate(positions):
        inverse[position] = visible_index
    sequence = object.__new__(VisibleSequence)
    for name, value in (
        ("nodes", original_nodes),
        ("visible_source_positions", positions),
        ("source_position_by_node_id", MappingProxyType(position_by_id)),
        ("visible_index_by_source_position", CompactUnsignedIntegers(inverse, maximum=sentinel)),
        ("sibling_ordinals", CompactUnsignedIntegers(sibling_ordinals, maximum=max(sibling_ordinals, default=0))),
        ("retained_direct_child_counts", CompactUnsignedIntegers(retained_direct_child_counts, maximum=max(retained_direct_child_counts, default=0))),
        ("collapsed_node_ids", parameters.collapsed_node_ids),
        ("filtered_item_count", filtered_item_count),
    ):
        object.__setattr__(sequence, name, value)
    return sequence


def window_visible_sequence(
    sequence: VisibleSequence[_VisibleNodeT],
    *,
    offset: int,
    limit: int,
) -> VisibleWindow[_VisibleNodeT]:
    """Return an exact bounded window from one derived sequence."""

    if type(sequence) is not VisibleSequence:
        raise TypeError("sequence must be a VisibleSequence")
    _require_exact_nonnegative_int(offset, "offset")
    if type(limit) is not int:
        raise TypeError("limit must be an integer")
    if not 1 <= limit <= _MAX_WINDOW_ROWS:
        raise ValueError("limit must be from 1 through 256")

    total = len(sequence.visible_source_positions)
    stop = min(offset + limit, total)
    rows: list[VisibleWindowRow[_VisibleNodeT]] = []
    for visible_index in range(min(offset, total), stop):
        source_position = sequence.visible_source_positions[visible_index]
        node = sequence.nodes[source_position]
        parent_source = node.parent_index
        parent_visible = None if parent_source is None else sequence.visible_index_by_source_position[parent_source]
        next_index = visible_index + 1
        first_child = (
            next_index
            if next_index < total
            and sequence.nodes[sequence.visible_source_positions[next_index]].parent_index == source_position
            else None
        )
        retained_children = sequence.retained_direct_child_counts[source_position]
        rows.append(
            VisibleWindowRow(
                node=node,
                visible_index=visible_index,
                parent_visible_index=parent_visible,
                first_child_visible_index=first_child,
                position_in_set=sequence.sibling_ordinals[visible_index],
                set_size=(1 if parent_source is None else sequence.retained_direct_child_counts[parent_source]),
                expanded=(
                    node.node_id not in sequence.collapsed_node_ids
                    if retained_children
                    else None
                ),
            )
        )
    return VisibleWindow(offset=offset, total=total, rows=tuple(rows))


def to_visible_window_view(
    window: VisibleWindow[_VisibleNodeT],
) -> dict[str, object]:
    """Flatten one bounded window to its exact renderer-facing wire shape."""

    if type(window) is not VisibleWindow:
        raise TypeError("window must be a VisibleWindow")
    return {
        "offset": window.offset,
        "total": window.total,
        "rows": [
            {
                "node_id": row.node.node_id,
                "display": row.node.display,
                "depth": row.node.depth,
                "is_container": row.node.is_container,
                "visible_index": row.visible_index,
                "parent_visible_index": row.parent_visible_index,
                "first_child_visible_index": row.first_child_visible_index,
                "position_in_set": row.position_in_set,
                "set_size": row.set_size,
                "expanded": row.expanded,
            }
            for row in window.rows
        ],
    }


def resolve_visible_anchor(
    sequence: VisibleSequence[_VisibleNodeT],
    candidate_node_ids: Iterable[str],
) -> VisibleAnchor | None:
    """Resolve an exact deepest-to-root chain against one derivation."""

    if type(sequence) is not VisibleSequence:
        raise TypeError("sequence must be a VisibleSequence")
    if isinstance(candidate_node_ids, (str, bytes)):
        raise TypeError("candidate_node_ids must be an iterable of node ids")
    candidates = tuple(candidate_node_ids)
    if not candidates:
        return None

    positions: list[int] = []
    for node_id in candidates:
        _require_text(node_id, "anchor node id", nonempty=True)
        try:
            positions.append(sequence.source_position_by_node_id[node_id])
        except KeyError as error:
            raise ValueError("anchor node id is unknown") from error

    for child_position, parent_position in zip(positions, positions[1:]):
        if sequence.nodes[child_position].parent_index != parent_position:
            raise ValueError("anchor candidates must be an exact parent chain")
    if sequence.nodes[positions[-1]].parent_index is not None:
        raise ValueError("anchor candidate chain must end at the root")

    sentinel = len(sequence.nodes)
    for node_id, source_position in zip(candidates, positions):
        visible_index = sequence.visible_index_by_source_position[source_position]
        if visible_index != sentinel:
            return VisibleAnchor(node_id=node_id, index=visible_index)
    return None


def _validate_order(nodes: tuple[_VisibleNodeT, ...], order: Sequence[int]) -> None:
    if len(order) != len(nodes):
        raise ValueError("ordered source positions must cover every node")
    seen = bytearray(len(nodes))
    ancestors: list[int] = []
    for source_position in order:
        if type(source_position) is not int or source_position < 0 or source_position >= len(nodes) or seen[source_position]:
            raise ValueError("ordered source positions must be a permutation")
        seen[source_position] = 1
        node = nodes[source_position]
        while len(ancestors) > node.depth:
            ancestors.pop()
        if node.depth == 0:
            if source_position != 0 or ancestors:
                raise ValueError("ordered source positions must start at the root")
        elif len(ancestors) != node.depth or ancestors[-1] != node.parent_index:
            raise ValueError("ordered source positions break parent/subtree closure")
        ancestors.append(source_position)


def _validate_structure(nodes: tuple[_VisibleNodeT, ...]) -> None:
    if not nodes:
        raise ValueError("the node array must contain one root")
    for node in nodes:
        _validate_node_fields(node)
    if nodes[0].position != 0 or nodes[0].depth != 0:
        raise ValueError("index zero must be the sole root")
    if nodes[0].parent_index is not None or nodes[0].subtree_end != len(nodes):
        raise ValueError("the root must cover the complete node array")

    seen_ids: set[str] = set()
    open_containers: list[int] = []
    for position, node in enumerate(nodes):
        if node.position != position:
            raise ValueError("node positions must be contiguous indexes")
        if node.node_id in seen_ids:
            raise ValueError("node ids must be unique")
        seen_ids.add(node.node_id)
        if node.subtree_end > len(nodes):
            raise ValueError("subtree extent exceeds the node array")
        if not node.is_container and node.subtree_end != position + 1:
            raise ValueError("a non-container cannot span descendants")

        while (
            open_containers
            and nodes[open_containers[-1]].subtree_end <= position
        ):
            open_containers.pop()
        if position == 0:
            if node.is_container and node.subtree_end > 1:
                open_containers.append(position)
            continue
        if node.depth == 0 or node.parent_index is None:
            raise ValueError("only index zero may be a root")
        if not open_containers or node.parent_index != open_containers[-1]:
            raise ValueError("parent indexes must match pre-order subtree extents")
        parent = nodes[node.parent_index]
        if node.depth != parent.depth + 1:
            raise ValueError("a child must be exactly one depth below its parent")
        if node.subtree_end > parent.subtree_end:
            raise ValueError("a subtree must remain inside its parent extent")
        if node.is_container and node.subtree_end > position + 1:
            open_containers.append(position)


def _validate_node_fields(node: object) -> None:
    def field(name: str) -> object:
        try:
            return getattr(node, name)
        except AttributeError as error:
            raise TypeError(f"node must provide {name}") from error

    _require_text(field("node_id"), "node_id", nonempty=True)
    _require_text(field("display"), "display")
    position = _require_exact_nonnegative_int(field("position"), "position")
    _require_exact_nonnegative_int(field("depth"), "depth")
    parent_index = field("parent_index")
    if parent_index is not None:
        _require_exact_nonnegative_int(parent_index, "parent_index")
    subtree_end = _require_exact_nonnegative_int(
        field("subtree_end"),
        "subtree_end",
    )
    if subtree_end <= position:
        raise ValueError("subtree_end must follow position")
    if type(field("is_container")) is not bool:
        raise TypeError("is_container must be a bool")


def _snapshot_node_ids(values: Iterable[str], field_name: str) -> frozenset[str]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{field_name} must be an iterable of node ids")
    try:
        snapshot = frozenset(values)
    except TypeError as error:
        raise TypeError(f"{field_name} must be an iterable of node ids") from error
    for node_id in snapshot:
        _require_text(node_id, field_name, nonempty=True)
    return snapshot


def _require_search(value: object) -> None:
    search = _require_text(value, "search_query")
    if len(search.encode("utf-8")) > _MAX_SEARCH_BYTES:
        raise ValueError("search_query exceeds 65,536 UTF-8 bytes")


def _require_text(
    value: object,
    name: str,
    *,
    nonempty: bool = False,
) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be a string")
    if nonempty and not value:
        raise ValueError(f"{name} must not be empty")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must contain valid Unicode") from error
    return value


def _require_exact_nonnegative_int(value: object, name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value
