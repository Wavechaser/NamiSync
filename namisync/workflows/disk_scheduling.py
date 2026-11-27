"""Physical-disk scheduling keys for registered workflow checkpoints (M2-A8).

The dispatcher calls :func:`read_disk_scheduling_keys` with a session's current
checkpoint before each start attempt. It names the local roots that start will
touch, reads which physical disks back each root's volume afresh, and answers
one plain ``("disk", number)`` key per disk that counts as spinning, so sessions
sharing a spinning disk start one at a time within one dispatcher.
Each product process composes one service and so one dispatcher.

Roots are resolved from the checkpoint's paths at read time rather than from a
volume name captured at admission: no checkpoint has a place for one, and a
stale or unreadable root costs only speed. An inventory or integrity binding's
volume is found by its recorded volume identity, so a volume that moved to
another letter is still keyed by its own disks. A root that core does not read as a
local volume (UNC, mapped network or ``subst`` roots), a root that cannot be
read and an unknown checkpoint contribute no keys; reading never refuses.
Nothing here is stored, recorded or published.
"""

from __future__ import annotations

import os

from namisync.core.disk_topology import counts_as_spinning, disk_facts, volume_name
from namisync.core.root_authority import observe_native_volume
from namisync.workflows.inventory import (
    IntegrityWorkflowRequest,
    InventoryWorkflowRequest,
    LocationBinding,
    _logical_drive_roots,
)
from namisync.workflows.models import ExecutionCheckpoint, PlanRequest

DISK_KEY = "disk"


def read_disk_scheduling_keys(checkpoint: object) -> frozenset[tuple[str, int]]:
    """Return a ``("disk", number)`` key for each spinning disk under the roots."""

    keys: set[tuple[str, int]] = set()
    volumes: set[str] = set()
    for root in _roots(checkpoint):
        try:
            name = volume_name(root)
            if name in volumes:
                continue
            volumes.add(name)
            facts = disk_facts(name)
        except (OSError, ValueError):
            continue
        keys.update(
            (DISK_KEY, fact.disk_number)
            for fact in facts
            if counts_as_spinning(fact)
        )
    return frozenset(keys)


def _roots(checkpoint: object) -> tuple[str, ...]:
    kind = type(checkpoint)
    if kind is PlanRequest:
        roots = (checkpoint.source_path, checkpoint.target_path)
    elif kind is ExecutionCheckpoint:
        plan = checkpoint.plan
        roots = (plan.source_root.path, plan.target_root.path)
    elif kind is InventoryWorkflowRequest or kind is IntegrityWorkflowRequest:
        roots = _current_mount(checkpoint.binding)
    else:
        return ()
    return tuple(dict.fromkeys(os.path.normcase(root) for root in roots))


def _current_mount(binding: LocationBinding) -> tuple[str, ...]:
    """Find where the binding's volume is mounted now, by its volume identity.

    A binding keeps the mounts it was reviewed at, and its volume may since
    have moved to another letter, as the workflow's own resolution allows. The
    selected mount is tried first, then the other recorded mounts and the
    current drive letters. Only a candidate that core reads as a local volume
    is observed, so a network letter is never touched.
    """

    candidates = [binding.selected_mount, *binding.expected_mounts]
    try:
        candidates.extend(_logical_drive_roots())
    except OSError:
        pass
    for mount in dict.fromkeys(candidates):
        try:
            volume_name(mount)
            if observe_native_volume(mount).volume_id == binding.volume_id:
                return (mount,)
        except (OSError, ValueError):
            continue
    return ()


