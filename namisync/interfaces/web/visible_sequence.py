"""Pure visible-tree derivation for desktop presentation adapters."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType


_MAX_SEARCH_BYTES = 256
_MAX_WINDOW_ROWS = 256


@dataclass(frozen=True, slots=True)
class VisibleSequenceNode:
    """One workflow-supplied node in an authoritative pre-order array."""

    node_id: str
    display: str
    position: int
    depth: int
    parent_index: int | None
    subtree_end: int
    is_container: bool

    def __post_init__(self) -> None:
        _require_text(self.node_id, "node_id", nonempty=True)
        _require_text(self.display, "display")
        _require_exact_nonnegative_int(self.position, "position")
        _require_exact_nonnegative_int(self.depth, "depth")
        if self.parent_index is not None:
            _require_exact_nonnegative_int(self.parent_index, "parent_index")
        _require_exact_nonnegative_int(self.subtree_end, "subtree_end")
        if self.subtree_end <= self.position:
            raise ValueError("subtree_end must follow position")
        if type(self.is_container) is not bool:
            raise TypeError("is_container must be a bool")


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
class VisibleSequence:
    """One immutable derivation over the complete original node tuple."""

    nodes: tuple[VisibleSequenceNode, ...]
    visible_positions: tuple[int, ...]
    visible_index_by_node_id: Mapping[str, int]
    filtered_item_count: int | None

    def __post_init__(self) -> None:
        nodes = tuple(self.nodes)
        if any(type(node) is not VisibleSequenceNode for node in nodes):
            raise TypeError("nodes must contain VisibleSequenceNode values")
        positions = tuple(self.visible_positions)
        expected_lookup: dict[str, int] = {}
        previous = -1
        for visible_index, position in enumerate(positions):
            _require_exact_nonnegative_int(position, "visible position")
            if position <= previous or position >= len(nodes):
                raise ValueError("visible positions must be ordered source indexes")
            node = nodes[position]
            expected_lookup[node.node_id] = visible_index
            previous = position
        if dict(self.visible_index_by_node_id) != expected_lookup:
            raise ValueError("visible node lookup does not match visible positions")
        if self.filtered_item_count is not None:
            _require_exact_nonnegative_int(
                self.filtered_item_count,
                "filtered_item_count",
            )
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "visible_positions", positions)
        object.__setattr__(
            self,
            "visible_index_by_node_id",
            MappingProxyType(expected_lookup),
        )


@dataclass(frozen=True, slots=True)
class VisibleWindow:
    """A bounded window into one derived visible sequence."""

    offset: int
    total: int
    nodes: tuple[VisibleSequenceNode, ...]

    def __post_init__(self) -> None:
        _require_exact_nonnegative_int(self.offset, "offset")
        _require_exact_nonnegative_int(self.total, "total")
        nodes = tuple(self.nodes)
        if len(nodes) > _MAX_WINDOW_ROWS:
            raise ValueError("visible window exceeds the row limit")
        if any(type(node) is not VisibleSequenceNode for node in nodes):
            raise TypeError("window nodes must be VisibleSequenceNode values")
        object.__setattr__(self, "nodes", nodes)


@dataclass(frozen=True, slots=True)
class VisibleAnchor:
    """A visible node identity and its index in the active derivation."""

    node_id: str
    index: int

    def __post_init__(self) -> None:
        _require_text(self.node_id, "node_id", nonempty=True)
        _require_exact_nonnegative_int(self.index, "index")


def derive_visible_sequence(
    nodes: Sequence[VisibleSequenceNode],
    parameters: VisibleSequenceParameters,
) -> VisibleSequence:
    """Validate and derive one visible sequence without retaining state."""

    if type(parameters) is not VisibleSequenceParameters:
        raise TypeError("parameters must be VisibleSequenceParameters")

    # This check deliberately precedes every access to the supplied node array.
    _require_search(parameters.search_query)
    original_nodes = tuple(nodes)
    _validate_structure(original_nodes)

    position_by_id = {node.node_id: node.position for node in original_nodes}
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
    search_matches = tuple(query in node.display.casefold() for node in original_nodes)
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

    lookup = {
        original_nodes[position].node_id: visible_index
        for visible_index, position in enumerate(visible_positions)
    }
    filtered_item_count = None
    if counts is not None:
        filtered_item_count = sum(
            counts.get(node.node_id, 0)
            for position, node in enumerate(original_nodes)
            if search_matches[position] and counts.get(node.node_id, 0) > 0
        )

    return VisibleSequence(
        nodes=original_nodes,
        visible_positions=tuple(visible_positions),
        visible_index_by_node_id=MappingProxyType(lookup),
        filtered_item_count=filtered_item_count,
    )


def window_visible_sequence(
    sequence: VisibleSequence,
    *,
    offset: int,
    limit: int,
) -> VisibleWindow:
    """Return an exact bounded window from one derived sequence."""

    if type(sequence) is not VisibleSequence:
        raise TypeError("sequence must be a VisibleSequence")
    _require_exact_nonnegative_int(offset, "offset")
    if type(limit) is not int:
        raise TypeError("limit must be an integer")
    if not 1 <= limit <= _MAX_WINDOW_ROWS:
        raise ValueError("limit must be from 1 through 256")

    total = len(sequence.visible_positions)
    positions = sequence.visible_positions[offset : offset + limit]
    return VisibleWindow(
        offset=offset,
        total=total,
        nodes=tuple(sequence.nodes[position] for position in positions),
    )


def resolve_visible_anchor(
    sequence: VisibleSequence,
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

    position_by_id = {node.node_id: node.position for node in sequence.nodes}
    positions: list[int] = []
    for node_id in candidates:
        _require_text(node_id, "anchor node id", nonempty=True)
        try:
            positions.append(position_by_id[node_id])
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


def _validate_structure(nodes: tuple[VisibleSequenceNode, ...]) -> None:
    if not nodes:
        raise ValueError("the node array must contain one root")
    if any(type(node) is not VisibleSequenceNode for node in nodes):
        raise TypeError("nodes must contain VisibleSequenceNode values")
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

        while open_containers and nodes[open_containers[-1]].subtree_end <= position:
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
    _require_text(value, "search_query")
    if len(value.encode("utf-8")) > _MAX_SEARCH_BYTES:
        raise ValueError("search_query exceeds 256 UTF-8 bytes")


def _require_text(value: object, name: str, *, nonempty: bool = False) -> None:
    if type(value) is not str:
        raise TypeError(f"{name} must be a string")
    if nonempty and not value:
        raise ValueError(f"{name} must not be empty")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must contain valid Unicode") from error


def _require_exact_nonnegative_int(value: object, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
