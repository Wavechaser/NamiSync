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
    visible_positions: tuple[int, ...]
    source_position_by_node_id: Mapping[str, int]
    visible_index_by_node_id: Mapping[str, int]
    parent_visible_indexes: tuple[int | None, ...]
    first_child_visible_indexes: tuple[int | None, ...]
    positions_in_set: tuple[int, ...]
    set_sizes: tuple[int, ...]
    collapsed_node_ids: frozenset[str]
    filtered_item_count: int | None

    def __post_init__(self) -> None:
        nodes = tuple(self.nodes)
        positions = tuple(self.visible_positions)
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

        visible_lookup = dict(self.visible_index_by_node_id)
        if len(visible_lookup) != len(positions):
            raise ValueError(
                "visible node lookup does not match visible positions"
            )
        previous = -1
        for visible_index, position in enumerate(positions):
            _require_exact_nonnegative_int(position, "visible position")
            if position <= previous or position >= len(nodes):
                raise ValueError(
                    "visible positions must be ordered source indexes"
                )
            node_id = nodes[position].node_id
            if node_id not in visible_lookup:
                raise ValueError(
                    "visible node lookup does not match visible positions"
                )
            lookup_index = _require_exact_nonnegative_int(
                visible_lookup[node_id],
                "visible lookup index",
            )
            if lookup_index != visible_index:
                raise ValueError(
                    "visible node lookup does not match visible positions"
                )
            previous = position

        metadata = (
            tuple(self.parent_visible_indexes),
            tuple(self.first_child_visible_indexes),
            tuple(self.positions_in_set),
            tuple(self.set_sizes),
        )
        if any(len(values) != len(positions) for values in metadata):
            raise ValueError("visible metadata must match visible positions")
        _validate_visible_metadata(
            nodes,
            positions,
            visible_lookup,
            *metadata,
        )
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
        object.__setattr__(self, "visible_positions", positions)
        object.__setattr__(
            self,
            "source_position_by_node_id",
            MappingProxyType(source_lookup),
        )
        object.__setattr__(
            self,
            "visible_index_by_node_id",
            MappingProxyType(visible_lookup),
        )
        object.__setattr__(self, "parent_visible_indexes", metadata[0])
        object.__setattr__(self, "first_child_visible_indexes", metadata[1])
        object.__setattr__(self, "positions_in_set", metadata[2])
        object.__setattr__(self, "set_sizes", metadata[3])
        object.__setattr__(self, "collapsed_node_ids", collapsed)


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
        if self.node.is_container:
            if type(self.expanded) is not bool:
                raise TypeError("container expanded state must be a bool")
        elif self.expanded is not None:
            raise ValueError("leaf expanded state must be None")


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
) -> VisibleSequence[_VisibleNodeT]:
    """Validate and derive one visible sequence without retaining state."""

    if type(parameters) is not VisibleSequenceParameters:
        raise TypeError("parameters must be VisibleSequenceParameters")

    # This check deliberately precedes every access to the supplied node array.
    _require_search(parameters.search_query)
    original_nodes = tuple(nodes)
    _validate_structure(original_nodes)

    position_by_id = {
        node.node_id: node.position for node in original_nodes
    }
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
    if counts is not None:
        unknown_ids = counts.keys() - position_by_id.keys()
        if unknown_ids:
            raise ValueError("match-count node id is unknown")

    query = parameters.search_query.casefold()
    search_matches = tuple(
        query in node.display.casefold() for node in original_nodes
    )
    direct_matches = tuple(
        search_matches[position]
        and (counts is None or counts.get(node.node_id, 0) > 0)
        for position, node in enumerate(original_nodes)
    )
    retained = list(direct_matches)
    for position in range(len(original_nodes) - 1, 0, -1):
        if retained[position]:
            parent = original_nodes[position].parent_index
            assert parent is not None
            retained[parent] = True

    visible_positions: list[int] = []
    hidden_until = 0
    for position, node in enumerate(original_nodes):
        if position < hidden_until or not retained[position]:
            continue
        visible_positions.append(position)
        if position in collapsed_positions:
            hidden_until = node.subtree_end

    positions = tuple(visible_positions)
    visible_lookup = {
        original_nodes[position].node_id: visible_index
        for visible_index, position in enumerate(positions)
    }
    metadata = _derive_visible_metadata(
        original_nodes,
        positions,
        visible_lookup,
    )
    filtered_item_count = None
    if counts is not None:
        filtered_item_count = sum(
            counts.get(node.node_id, 0)
            for position, node in enumerate(original_nodes)
            if search_matches[position] and counts.get(node.node_id, 0) > 0
        )

    return VisibleSequence(
        nodes=original_nodes,
        visible_positions=positions,
        source_position_by_node_id=position_by_id,
        visible_index_by_node_id=visible_lookup,
        parent_visible_indexes=metadata[0],
        first_child_visible_indexes=metadata[1],
        positions_in_set=metadata[2],
        set_sizes=metadata[3],
        collapsed_node_ids=parameters.collapsed_node_ids,
        filtered_item_count=filtered_item_count,
    )


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

    total = len(sequence.visible_positions)
    stop = min(offset + limit, total)
    rows: list[VisibleWindowRow[_VisibleNodeT]] = []
    for visible_index in range(min(offset, total), stop):
        node = sequence.nodes[sequence.visible_positions[visible_index]]
        rows.append(
            VisibleWindowRow(
                node=node,
                visible_index=visible_index,
                parent_visible_index=(
                    sequence.parent_visible_indexes[visible_index]
                ),
                first_child_visible_index=(
                    sequence.first_child_visible_indexes[visible_index]
                ),
                position_in_set=sequence.positions_in_set[visible_index],
                set_size=sequence.set_sizes[visible_index],
                expanded=(
                    node.node_id not in sequence.collapsed_node_ids
                    if node.is_container
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

    for node_id in candidates:
        visible_index = sequence.visible_index_by_node_id.get(node_id)
        if visible_index is not None:
            return VisibleAnchor(node_id=node_id, index=visible_index)
    return None


def _derive_visible_metadata(
    nodes: tuple[_VisibleNodeT, ...],
    visible_positions: tuple[int, ...],
    visible_index_by_node_id: Mapping[str, int],
) -> tuple[
    tuple[int | None, ...],
    tuple[int | None, ...],
    tuple[int, ...],
    tuple[int, ...],
]:
    parent_indexes: list[int | None] = []
    first_child_indexes: list[int | None] = [None] * len(visible_positions)
    sibling_counts: dict[int | None, int] = {}
    for visible_index, source_position in enumerate(visible_positions):
        node = nodes[source_position]
        if node.parent_index is None:
            parent_visible_index = None
        else:
            parent_id = nodes[node.parent_index].node_id
            try:
                parent_visible_index = visible_index_by_node_id[parent_id]
            except KeyError as error:
                raise ValueError("a visible node must retain its parent") from error
            if first_child_indexes[parent_visible_index] is None:
                first_child_indexes[parent_visible_index] = visible_index
        parent_indexes.append(parent_visible_index)
        sibling_counts[parent_visible_index] = (
            sibling_counts.get(parent_visible_index, 0) + 1
        )

    seen_siblings: dict[int | None, int] = {}
    positions_in_set: list[int] = []
    set_sizes: list[int] = []
    for parent_visible_index in parent_indexes:
        position_in_set = seen_siblings.get(parent_visible_index, 0) + 1
        seen_siblings[parent_visible_index] = position_in_set
        positions_in_set.append(position_in_set)
        set_sizes.append(sibling_counts[parent_visible_index])

    return (
        tuple(parent_indexes),
        tuple(first_child_indexes),
        tuple(positions_in_set),
        tuple(set_sizes),
    )


def _validate_visible_metadata(
    nodes: tuple[_VisibleNodeT, ...],
    visible_positions: tuple[int, ...],
    visible_index_by_node_id: Mapping[str, int],
    parent_visible_indexes: tuple[int | None, ...],
    first_child_visible_indexes: tuple[int | None, ...],
    positions_in_set: tuple[int, ...],
    set_sizes: tuple[int, ...],
) -> None:
    sibling_counts: dict[int | None, int] = {}
    for visible_index, source_position in enumerate(visible_positions):
        node = nodes[source_position]
        supplied_parent = parent_visible_indexes[visible_index]
        if supplied_parent is not None:
            _require_exact_nonnegative_int(
                supplied_parent,
                "parent visible index",
            )
        supplied_child = first_child_visible_indexes[visible_index]
        if supplied_child is not None:
            _require_exact_nonnegative_int(
                supplied_child,
                "first child visible index",
            )
        if node.parent_index is None:
            expected_parent = None
        else:
            parent_id = nodes[node.parent_index].node_id
            try:
                expected_parent = visible_index_by_node_id[parent_id]
            except KeyError as error:
                raise ValueError("a visible node must retain its parent") from error
        if supplied_parent != expected_parent:
            raise ValueError("visible accessibility metadata is inconsistent")

        expected_child = None
        if visible_index + 1 < len(visible_positions):
            next_source_position = visible_positions[visible_index + 1]
            if nodes[next_source_position].parent_index == source_position:
                expected_child = visible_index + 1
        if supplied_child != expected_child:
            raise ValueError("visible accessibility metadata is inconsistent")

        _require_exact_nonnegative_int(
            positions_in_set[visible_index],
            "position in set",
        )
        _require_exact_nonnegative_int(
            set_sizes[visible_index],
            "set size",
        )
        sibling_counts[expected_parent] = (
            sibling_counts.get(expected_parent, 0) + 1
        )

    sibling_positions: dict[int | None, int] = {}
    for visible_index, parent_visible_index in enumerate(parent_visible_indexes):
        expected_position = sibling_positions.get(parent_visible_index, 0) + 1
        sibling_positions[parent_visible_index] = expected_position
        if (
            positions_in_set[visible_index] != expected_position
            or set_sizes[visible_index] != sibling_counts[parent_visible_index]
        ):
            raise ValueError("visible accessibility metadata is inconsistent")


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
