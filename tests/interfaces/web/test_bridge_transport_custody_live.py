"""Current-source drift guard for SH-G-8 transport custody."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

import pytest


FROZEN_VALIDATOR = Path(__file__).with_name(
    "test_bridge_transport_custody.py"
)

_CEILING_BYTES = 1_966_080


def _frozen_validator():
    name = "bridge_transport_custody_live_guard"
    specification = importlib.util.spec_from_file_location(
        name, FROZEN_VALIDATOR
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def test_current_v5_ordinary_fixture_models_attempt_and_settlement() -> None:
    frozen = _frozen_validator()
    child = frozen._child_module()
    events = []

    class PassGate:
        def wait(self) -> None:
            return None

        def set(self) -> None:
            return None

    class StopAfterFirstTick:
        def wait(self) -> None:
            raise RuntimeError("stop after first logical tick")

    state = SimpleNamespace(
        task_index=0,
        variant=frozen.VARIANT,
        ordinary_releases=(PassGate(), StopAfterFirstTick()),
        ordinary_done=(PassGate(),),
        ordinary_continue=(PassGate(),),
    )
    invocation = child._CustodyInvocation(state)
    context = SimpleNamespace(emit=events.append)

    with pytest.raises(RuntimeError, match="stop after first logical tick"):
        invocation._run_ordinary(context)

    progress = events[:25]
    outcomes = events[25:]
    assert len(progress) == 25
    assert len(outcomes) == 3
    assert {event.phase for event in progress} == {"execute"}
    assert {event.items_done for event in progress} == {0}
    assert {event.items_total for event in progress} == {150}
    assert [event.bytes_done for event in progress] == list(range(1, 26))
    assert {event.bytes_total for event in progress} == {1_500}
    assert {event.item_type for event in progress} == {"operation"}
    assert {event.item_id for event in progress} == {outcomes[0].item_id}
    assert len({event.item_attempt_id for event in progress}) == 1
    assert len(progress[0].item_attempt_id) == 32
    assert [event.item_bytes_done for event in progress] == list(range(1, 26))
    assert {event.item_bytes_total for event in progress} == {25}
    assert len({outcome.item_id for outcome in outcomes}) == 3
    assert {outcome.recording.value for outcome in outcomes} == {"degraded"}
    assert all(outcome.recording_reason is not None for outcome in outcomes)


def test_current_v5_progress_representation_overlay_is_complete() -> None:
    frozen = _frozen_validator()
    child = frozen._child_module()
    from namisync.core.events import Envelope, Progress
    from namisync.workflows.views import SessionEventView

    overlay = child.CURRENT_V5_TRANSPORT_REPRESENTATION
    assert set(overlay) == {
        "scope",
        "typed_envelope",
        "session_event_view",
        "progress_body",
        "mapping_families",
        "reliable_bodies",
        "maximum_no_gap",
        "aliasing",
    }
    assert set(overlay["typed_envelope"]["fields"]) == {
        field.name for field in fields(Envelope)
    }
    assert set(overlay["session_event_view"]["fields"]) == {
        field.name for field in fields(SessionEventView)
    }
    assert set(overlay["progress_body"]) == {
        field.name for field in fields(Progress)
    }
    assert set(overlay["reliable_bodies"]) == {
        "StateChanged",
        "ItemOutcome",
        "Terminal",
        "Gap",
    }
    assert set(overlay["maximum_no_gap"]) == {
        "Progress",
        "Envelope.schema_version",
        "SessionEventView.schema_version",
        "ItemOutcome",
    }
    for family in (
        overlay["typed_envelope"]["fields"],
        overlay["session_event_view"]["fields"],
        overlay["progress_body"],
        overlay["mapping_families"],
        overlay["reliable_bodies"],
        overlay["maximum_no_gap"],
        overlay["aliasing"],
    ):
        assert all(
            type(description) is str and description
            for description in family.values()
        )


def test_current_source_transport_custody_stays_within_frozen_ceiling(
    tmp_path: Path,
) -> None:
    frozen = _frozen_validator()
    parent = frozen._parent_module()
    child = frozen._child_module()
    output = tmp_path / "current-source-custody.json"
    completed = parent._run_child(
        tmp_path / "fixture",
        output,
        variant=frozen.VARIANT,
        tested_commit=frozen.TESTED_COMMIT,
        dependency_root=parent._dependency_root(),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    artifact = json.loads(output.read_text(encoding="utf-8"))
    receipt = parent._read_child_receipt(
        completed.stdout,
        variant=frozen.VARIANT,
        tested_commit=frozen.TESTED_COMMIT,
    )
    parent._validate_child_receipt(receipt, artifact)
    parent._validate_run_artifact(
        artifact,
        child,
        variant=frozen.VARIANT,
        source_authority=frozen._artifact_source_authority(artifact),
        dependency_authority=frozen._artifact_dependency_authority(artifact),
        expected_pycache_prefix=frozen._artifact_pycache_prefix(artifact),
    )

    contract, _calibration = frozen._load_transport_custody_ceiling_contract(
        parent, child
    )
    ceiling = contract["ceiling"]["transport_custody_bytes"]
    assert ceiling == _CEILING_BYTES
    measurements = {
        "ordinary": artifact["ordinary"]["ordinary_quiescent_peak"][
            "transport_custody_bytes"
        ],
        "maximum-no-Gap": artifact["maximum_no_gap"]["custody"][
            "transport_custody_bytes"
        ],
    }
    for name, measured in measurements.items():
        assert measured <= ceiling, (
            f"{name} current-source transport custody {measured:,} bytes "
            f"exceeds the frozen {ceiling:,}-byte ceiling"
        )
