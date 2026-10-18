"""Independent exposure and policy expectations; never assembled from product specs."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import NamedTuple


class CommandPolicy(NamedTuple):
    access: str
    command_id: str
    revision: str
    work: str
    response_policy: str
    retry: str
    phase: str


COMMAND_POLICY = MappingProxyType({
    "shell_ready": CommandPolicy("read-only", "forbidden", "forbidden", "direct",
        "startup-5-seconds", "none", "bootstrap"),
    "readiness_echo": CommandPolicy("read-only", "forbidden", "forbidden", "direct",
        "startup-5-seconds", "same-payload-once", "bootstrap"),
    "pick_folder": CommandPolicy("read-only", "forbidden", "forbidden", "direct",
        "interactive", "none", "open"),
    "read_setup": CommandPolicy("read-only", "forbidden", "forbidden", "direct",
        "local-5-seconds", "same-payload-once", "open"),
    "probe_recent_pairs": CommandPolicy("read-only", "forbidden", "forbidden", "async-small",
        "local-5-seconds", "none", "open"),
    "prepare_setup": CommandPolicy("read-only", "forbidden", "forbidden", "direct",
        "local-5-seconds", "same-payload-once", "open"),
    "admit_location": CommandPolicy("read-only", "forbidden", "forbidden", "direct",
        "feedback-only", "none", "open"),
    "create_task": CommandPolicy("mutating", "required", "forbidden", "async-small",
        "mutation-observed", "none", "open"),
    "list_tasks": CommandPolicy("read-only", "forbidden", "forbidden", "direct",
        "local-5-seconds", "same-payload-once", "open"),
    "start_plan": CommandPolicy("mutating", "required", "forbidden", "async-small",
        "mutation-observed", "none", "open"),
    "start_inventory": CommandPolicy("mutating", "required", "forbidden", "async-small",
        "mutation-observed", "none", "open"),
    "plan_again": CommandPolicy("mutating", "required", "forbidden", "async-small",
        "mutation-observed", "none", "open"),
    "open_plan_view": CommandPolicy("read-only", "forbidden", "forbidden", "direct",
        "local-5-seconds", "same-payload-once", "open"),
    "open_inventory_view": CommandPolicy("read-only", "forbidden", "forbidden", "direct",
        "local-5-seconds", "same-payload-once", "open"),
    "refresh_inventory": CommandPolicy("mutating", "required", "required", "async-small",
        "mutation-observed", "none", "open"),
    "start_inventory_integrity": CommandPolicy("mutating", "required", "required", "async-small",
        "mutation-observed", "none", "open"),
    "control_integrity": CommandPolicy("mutating", "forbidden", "forbidden", "direct",
        "mutation-observed", "none", "open"),
    "acknowledge_inventory": CommandPolicy("mutating", "required", "required", "async-small",
        "mutation-observed", "none", "open"),
    "restore_inventory": CommandPolicy("mutating", "required", "required", "async-small",
        "mutation-observed", "none", "open"),
    "update_inventory_view": CommandPolicy("read-only", "forbidden", "required", "direct",
        "feedback-only", "none", "open"),
    "set_inventory_selection": CommandPolicy("read-only", "forbidden", "required", "direct",
        "feedback-only", "none", "open"),
    "mutate_inventory_highlight": CommandPolicy("read-only", "forbidden", "required", "direct",
        "feedback-only", "none", "open"),
    "set_inventory_highlighted_selection": CommandPolicy("read-only", "forbidden", "required", "direct",
        "feedback-only", "none", "open"),
    "get_inventory_window": CommandPolicy("read-only", "forbidden", "required", "direct",
        "local-5-seconds", "same-payload-once", "open"),
    "get_inventory_detail": CommandPolicy("read-only", "forbidden", "required", "direct",
        "local-5-seconds", "same-payload-once", "open"),
    "update_plan_view": CommandPolicy("read-only", "forbidden", "required", "direct",
        "feedback-only", "none", "open"),
    "get_plan_detail": CommandPolicy("read-only", "forbidden", "required", "direct",
        "local-5-seconds", "same-payload-once", "open"),
    "get_plan_window": CommandPolicy("read-only", "forbidden", "required", "direct",
        "local-5-seconds", "same-payload-once", "open"),
    "get_execution_detail": CommandPolicy("read-only", "forbidden", "required", "direct",
        "local-5-seconds", "same-payload-once", "open"),
    "reveal_plan_move": CommandPolicy("read-only", "forbidden", "required", "direct",
        "feedback-only", "none", "open"),
    "get_inventory_anchor": CommandPolicy("read-only", "forbidden", "required", "direct",
        "local-5-seconds", "same-payload-once", "open"),
    "get_plan_anchor": CommandPolicy("read-only", "forbidden", "required", "direct",
        "local-5-seconds", "same-payload-once", "open"),
    "mutate_plan_selection": CommandPolicy("mutating", "required", "required", "direct",
        "mutation-observed", "none", "open"),
    "mutate_plan_scope": CommandPolicy("mutating", "required", "required", "direct",
        "mutation-observed", "none", "open"),
    "mutate_plan_highlight": CommandPolicy("read-only", "forbidden", "required", "direct",
        "feedback-only", "none", "open"),
    "mutate_plan_highlighted_selection": CommandPolicy("mutating", "required", "required", "direct",
        "mutation-observed", "none", "open"),
    "start_execution": CommandPolicy("mutating", "required", "required", "async-small",
        "mutation-observed", "none", "open"),
    "control_execution": CommandPolicy("mutating", "forbidden", "forbidden", "direct",
        "mutation-observed", "none", "open"),
    "next_events": CommandPolicy("read-only", "forbidden", "forbidden", "direct",
        "drain-30-seconds", "none", "open"),
    "release_terminal_session": CommandPolicy("mutating", "forbidden", "forbidden", "async-small",
        "mutation-observed", "none", "open"),
    "close_task": CommandPolicy("mutating", "forbidden", "forbidden", "async-small",
        "mutation-observed", "none", "open"),
    "read_cosmetic_section": CommandPolicy("read-only", "forbidden", "forbidden", "direct",
        "local-5-seconds", "same-payload-once", "open"),
    "replace_cosmetic_section": CommandPolicy("mutating", "forbidden", "required", "direct",
        "feedback-only", "none", "open"),
})
COMMAND_NAMES = tuple(COMMAND_POLICY)
SORTED_COMMAND_NAMES = tuple(sorted(COMMAND_POLICY))


def browser_command_policy() -> dict[str, dict[str, str]]:
    return {
        name: {"response_policy": policy.response_policy, "retry": policy.retry, "phase": policy.phase}
        for name, policy in COMMAND_POLICY.items()
    }


def assert_command_catalog(actual: Mapping[str, CommandPolicy]) -> None:
    assert tuple(actual) == COMMAND_NAMES
    assert actual == COMMAND_POLICY


def assert_browser_command_policy(actual: object) -> None:
    assert actual == browser_command_policy()
