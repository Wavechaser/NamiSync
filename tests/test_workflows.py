from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from namisync.core.execution import Commitment, ExecutionSet, validated_run_id
from namisync.core.models import CapabilityProfile, Root
from namisync.core.planning import (
    Assignment,
    DeletionPolicy,
    FilterSet,
    Plan,
    PlanFingerprint,
    PreservationPolicy,
    plan_fingerprint,
    selection_digest,
)
from namisync.core.session import Disposition, RunContext, SessionState
from namisync.workflows.sync import run_execution


NOW = datetime(2026, 7, 19, tzinfo=timezone.utc)


def _empty_plan() -> Plan:
    profile = CapabilityProfile("NTFS", 100, True, False, 32767, True, True)
    placeholder = Plan(
        source_root=Root(r"C:\source", "source"),
        target_root=Root(r"D:\target", "target"),
        source_volume_id=None,
        target_volume_id=None,
        source_volume_evidence=None,
        target_volume_evidence=None,
        source_profile=profile,
        target_profile=profile,
        source_complete=True,
        target_complete=True,
        operations=(),
        assignment=Assignment("identity", "1", ()),
        preservation=PreservationPolicy(),
        filter_snapshot=FilterSet(),
        deletion_policy=DeletionPolicy.TRASH,
        trash_on_update=True,
        policy_fingerprint="p" * 64,
        worker_count=1,
        required_volumes=frozenset(),
        required_bytes=0,
        fingerprint=PlanFingerprint("0" * 64),
    )
    return replace(placeholder, fingerprint=plan_fingerprint(placeholder))


def test_execution_refuses_uncommitted_set_before_preflight() -> None:
    saved = []
    xset = ExecutionSet(
        _empty_plan(), frozenset(), validated_run_id("1" * 32)
    )
    deps = SimpleNamespace(save_execution_details=saved.append)

    result = run_execution(xset, RunContext(lambda _: None, lambda: None), deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert saved[0].commitment_error == "execution set is not committed"


def test_execution_refuses_changed_selection_digest_before_preflight() -> None:
    saved = []
    plan = _empty_plan()
    xset = ExecutionSet(
        plan,
        frozenset(),
        validated_run_id("2" * 32),
        commitment=Commitment(plan.fingerprint, b"x" * 32, NOW),
    )
    deps = SimpleNamespace(save_execution_details=saved.append)

    result = run_execution(xset, RunContext(lambda _: None, lambda: None), deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert "selection digest" in saved[0].commitment_error


def test_execution_refuses_changed_plan_fingerprint_before_preflight() -> None:
    saved = []
    plan = _empty_plan()
    xset = ExecutionSet(
        plan,
        frozenset(),
        validated_run_id("3" * 32),
        commitment=Commitment(PlanFingerprint("e" * 64), b"x" * 32, NOW),
    )
    deps = SimpleNamespace(save_execution_details=saved.append)

    result = run_execution(xset, RunContext(lambda _: None, lambda: None), deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert "plan fingerprint" in saved[0].commitment_error


def test_execution_refuses_plan_content_that_no_longer_matches_fingerprint() -> None:
    saved = []
    plan = _empty_plan()
    tampered = replace(plan, deletion_policy=DeletionPolicy.ADDITIVE)
    xset = ExecutionSet(
        tampered,
        frozenset(),
        validated_run_id("4" * 32),
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(frozenset()),
            NOW,
        ),
    )
    deps = SimpleNamespace(save_execution_details=saved.append)

    result = run_execution(xset, RunContext(lambda _: None, lambda: None), deps)

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert "plan content" in saved[0].commitment_error
