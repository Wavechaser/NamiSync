"""Installed-wheel headed evidence for frozen Setup and location flows."""

from __future__ import annotations

from contextlib import nullcontext
import inspect
import json
import os
from pathlib import Path

import pytest

import _setup_headed_child as child
from _headed_evidence import EvidencePaths, EvidenceReader, require_host_final
from _headed_native import (
    clean_child_environment,
    close_window,
    require_absolute_local_test_root,
    scenario_deadline,
    start_headed_process,
    terminate_process_tree,
    wait_for_accessible_text,
    wait_for_initial_evidence,
    wait_for_process,
    wait_for_window,
)
from conftest import HeadedInstalledWheel
from _plan_again_trace import (
    installed_plan_again_trace, validate_trace_snapshot, verify_restored_assets,
)


_CHILD = Path(__file__).with_name("_setup_headed_child.py")


def test_setup_child_keeps_the_production_host_and_captures_real_screenshots() -> None:
    source = _CHILD.read_text(encoding="utf-8")
    launch = inspect.getsource(_run_setup_scenario)

    assert "host.run_desktop(" in source
    assert '"_production_commands"' in source
    assert "CallDevToolsProtocolMethodAsync" in source
    assert '"Page.captureScreenshot"' in source
    assert 'document.querySelector(".nami-plan-review")' in source
    assert "[data-action=\"plan-again\"]" in source
    assert '"original completed Plan review navigation"' in source
    assert '"reloaded completed Plan review"' in source
    assert 'screenshot_dir / "plan-review.png"' in source
    assert '"original frozen task navigation"' not in source
    assert '.nami-setup__actions .nami-button:last-child' not in source
    assert 'observe("start_plan_again_error", type(error).__name__)' in source
    assert 'observe("start_plan_again_result", "started")' in source
    assert "evaluate_js" not in source
    assert "ExecuteScriptAsync" not in source
    assert "scenario_deadline(120.0)" in launch


@pytest.mark.headed
def test_m1_6_installed_setup_flow(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path: Path,
) -> None:
    result = _run_setup_scenario(headed_installed_wheel, tmp_path)
    assert result["editable"] is True
    assert result["typed_refusal"] in {"invalid_path", "missing", "unavailable"}
    assert result["typed_retry_resolved"] is True
    assert result["routine_ready_hint_hidden"] is True
    assert result["host_ready_hidden"] is True
    assert result["empty_path_hint_hidden"] is True
    assert result["refusal_hint_visible"] is True
    assert result["hostile_filter_inert"] is True
    assert result["two_setup_cards"] is True
    assert result["card_heading_hierarchy"] is True
    assert result["segmented_keyboard"] is True
    assert result["recent_dropdown_keyboard"] is True
    assert result["disclosure_open"] is True
    assert result["disclosure_closed_initially"] is True
    assert result["setup_aligned_top"] is True
    assert result["primary_options_one_line"] is True
    assert result["primary_options_gap"] == pytest.approx(16, abs=1)
    assert result["primary_options_stable_open"] is True, result["primary_options_bounds"]
    assert result["advanced_below_full_width"] is True
    assert result["expanded_options_padding"] is True
    assert result["expanded_option_row_gaps"]
    assert all(gap == pytest.approx(8, abs=1) for gap in result["expanded_option_row_gaps"])
    assert result["form_label_track"] == "64px"
    assert result["more_idle_transparent"] is True
    assert result["clear_shared_variant"] is True
    assert result["refresh_icon_transparent"] is True
    assert result["refresh_square"] is True
    assert result["recent_row_height"] == pytest.approx(56, abs=1)
    assert result["recent_viewport_height"] == pytest.approx(308, abs=1)
    assert result["recent_header_height"] == pytest.approx(28, abs=1)
    assert result["recent_header_fixed"] is True
    assert result["recent_slots_bounded"] is True
    assert result["recent_folder_inset"] == pytest.approx(12, abs=1)
    assert result["advanced_filters_visible"] is True
    assert result["advanced_labels_follow_toggles"] is True
    assert result["add_filter_inline"] is True
    assert result["path_uses_standard_idle_style"] is True
    assert result["path_matches_standard_focus"] is True
    assert result["path_has_standard_focus_ring"] is True
    assert result["path_pointer_focus_has_no_outer_ring"] is True
    assert result["path_fills_rounded_control"] is True
    assert result["caret_inside_path_with_text_space"] is True
    assert result["clear_immediately_before_caret"] is True
    assert result["clear_invalidates_immediately"] is True
    assert result["clear_pointer_local"] is True
    assert result["pair_pointer_states"] is True, result["pair_pointer_detail"]
    assert result["table_gallery_style"] is True
    geometry = result["table_geometry"]
    assert geometry["viewport_x"] == "auto"
    assert geometry["viewport_y"] == "hidden"
    assert geometry["header_y"] == "hidden"
    assert geometry["body_y"] == "auto"
    assert geometry["header_gutter"] == geometry["body_gutter"] == "stable"
    assert geometry["viewport_height"] == pytest.approx(308, abs=0.5)
    assert geometry["header_height"] == pytest.approx(28, abs=0.5)
    assert geometry["body_height"] == pytest.approx(280, abs=0.5)
    assert geometry["body_starts_below_header"] is True
    assert geometry["default_columns_align"] is True
    assert geometry["narrow_columns_align"] is True
    assert geometry["narrow_horizontal"] is True
    assert geometry["narrow_table_height"] == pytest.approx(308, abs=0.5)
    assert geometry["narrow_body_height"] == pytest.approx(280, abs=0.5)
    assert geometry["narrow_viewport_height"] > geometry["narrow_table_height"]
    assert geometry["empty_width"] == geometry["default_width"] == geometry["overflow_width"]
    assert geometry["body_overflows"] is True
    assert geometry["header_fixed_during_body_scroll"] is True
    accessibility = result["table_accessibility"]
    assert accessibility["table"] >= 1
    assert accessibility["rowgroup"] >= 1
    assert accessibility["row"] >= 2
    assert accessibility["columnheader"] >= 2
    assert accessibility["cell"] >= 2
    assert result["browse_square"] is True
    assert result["pair_actions_right_aligned"] is True
    assert result["inline_location_controls"] is True
    assert result["browse_outside_path_control"] is True
    assert result["dropdown_anchored"] is True
    assert result["dropdown_rerender_focus_restored"] is True
    assert result["popup_options_borderless"] is True
    assert result["popup_focus_is_exclusive"] is True
    assert result["picker_icon_only"] is True
    assert result["advanced_switches"] is True
    assert result["primary_options_visible"] is True
    assert result["sync_inapplicable_actions_hidden"] is True
    assert result["recent_pair_online_offline"] is True
    assert result["mixed_pair_endpoint_truths"] == [
        ["source", "offline", "Offline"],
        ["target", "online", "Online"],
    ]
    assert result["recent_pair_two_columns"] is True
    assert result["recent_path_button_fills_column"] is True
    assert result["endpoint_statuses_align_with_paths"] is True
    assert result["offline_pair_disabled"] is True
    assert result["pair_two_line_paths"] is True
    assert result["pair_paths_aligned"] is True
    assert result["pair_paths_truncated"] is True
    assert result["availability_dots_distinct"] is True
    assert result["availability_dots_shifted"] is True
    assert result["availability_text_neutral"] is True
    assert result["pointer_open_neutral"] is True
    assert result["pointer_handoff_neutral"] is True
    assert result["keyboard_resumes_after_pointer"] is True
    assert result["recent_chevron_geometry"] is True
    assert result["more_chevron_geometry"] is True
    assert result["pointer_focus_hidden"] is True
    assert result["keyboard_focus_visible"] is True
    assert result["pair_row_focus_whole"] is True
    assert result["pair_button_focused"] is True
    assert result["frozen"] is True
    assert result["plan_again_visible"] is True
    assert result["plan_again_new_task"] is True
    assert result["picker_resolved"] is True
    assert result["frozen_switches_disabled"] is True
    assert result["frozen_pairs_disabled"] is True
    assert result["frozen_mode_hidden"] is True
    assert result["disabled_icon_controls_transparent"] is True
    assert result["recent_activated"] is True
    assert result["recent_pair_activated"] is True
    assert result["recent_pair_native_button"] is True
    assert result["inventory_without_pair"] is True
    assert result["inventory_action_visibility"] is True
    assert result["inventory_inapplicable_hidden"] is True
    assert result["mixed_batch"] is True
    assert result["batch_paths_visible"] is True
    assert result["batch_paths_aligned"] is True
    assert result["batch_slots_bounded"] is True
    assert result["batch_column_widths"] is True
    assert result["batch_no_horizontal_overflow"] is True
    assert result["batch_action_placement"] is True
    assert result["batch_clear_left_create_right"] is True
    assert result["batch_footer_actions_retained"] is True
    assert result["batch_clear_hides_settled"] is True
    assert result["queued_batch_removable"] is True
    assert result["navigation_retains_completed_plan"] is True
    assert result["picker_ambiguous"] is True
    assert result["picker_mount_index"] == 1
    assert result["picker_continued"] is True
    assert result["start_refused_before_choice"] is True
    assert result["plan_review_before_capture"] is True
    assert result["reload_task_count"] == result["task_count_before_reload"]
    assert result["reload_plan_review_reconstructed"] is True
    assert result["reload_selected_task"] == "Task 1"
    assert set(result["screenshots"]) == {"editable", "editable-expanded", "plan-review"}


def _run_setup_scenario(
    installed: HeadedInstalledWheel,
    root: Path,
) -> dict[str, object]:
    deadline = scenario_deadline(120.0)
    root = require_absolute_local_test_root(root)
    data_root = require_absolute_local_test_root(root / "data")
    evidence_root = require_absolute_local_test_root(root / "evidence")
    screenshot_root = require_absolute_local_test_root(root / "screenshots")
    source = require_absolute_local_test_root(root / "source")
    target = require_absolute_local_test_root(root / "target")
    for directory in (root, data_root, evidence_root, screenshot_root, source, target):
        directory.mkdir(parents=True, exist_ok=True)
    paths = EvidencePaths(evidence_root)
    reader = EvidenceReader(paths)
    trace_enabled = os.environ.get("NAMISYNC_PLAN_AGAIN_TRACE") == "1"
    trace_context = installed_plan_again_trace(installed.root) if trace_enabled else nullcontext(None)
    with trace_context as trace_assets:
        if trace_assets is not None:
            (evidence_root / "plan-again-trace-assets.json").write_text(
                json.dumps(trace_assets, sort_keys=True), encoding="utf-8",
            )
        child_arguments = (
            installed.python, _CHILD,
            "--data-dir", data_root,
            "--mutex", "Local\\NamiSync.SetupHeaded",
            "--title", "NamiSync Setup headed",
            "--evidence-dir", evidence_root,
            "--screenshot-dir", screenshot_root,
            "--source", source,
            "--target", target,
        ) + (("--plan-again-trace",) if trace_enabled else ())
        process = start_headed_process(
            child_arguments, cwd=installed.root,
            environment=clean_child_environment(), deadline=deadline,
        )
        try:
            window = wait_for_window(process, "NamiSync Setup headed", deadline=deadline)
            milestone, initial = wait_for_initial_evidence(reader, process, deadline=deadline)
            if milestone == "ready":
                wait_for_accessible_text(window, child._COMPLETE_TEXT, python=installed.python, deadline=deadline)
            close_window(window)
            completed = wait_for_process(process, deadline=deadline)
            final = reader.read_final()
        finally:
            if process.poll() is None:
                terminate_process_tree(process, deadline=deadline)
    if trace_enabled:
        verify_restored_assets(installed.root, trace_assets)
        validate_trace_snapshot(initial["plan_again_browser_trace"], {"setup"})
        validate_trace_snapshot(initial["plan_again_host_trace"], {"setup"}, allow_empty=True)
    if milestone == "failure":
        raise AssertionError(f"setup headed gate failed: {initial!r}")
    assert final is not None
    require_host_final(final, exit_code=completed.returncode)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    for name in initial["screenshots"]:
        assert (screenshot_root / f"{name}.png").is_file()
    return initial


_TRACE_ASSET_NAMES = ("bridge.js", "plan_review.js", "app.js")


def _copy_plan_again_trace_assets(root: Path) -> tuple[Path, dict[str, bytes]]:
    source_root = Path(__file__).resolve().parents[3] / "namisync/interfaces/web/assets"
    asset_root = (
        root / "Lib/site-packages/namisync/interfaces/web/assets"
    )
    asset_root.mkdir(parents=True)
    originals = {
        name: (source_root / name).read_bytes()
        for name in _TRACE_ASSET_NAMES
    }
    for name, content in originals.items():
        (asset_root / name).write_bytes(content)
    return asset_root, originals


@pytest.mark.parametrize("raise_inside", [False, True])
def test_plan_again_trace_transforms_exact_assets_and_restores_bytes(
    tmp_path: Path,
    raise_inside: bool,
) -> None:
    import hashlib
    import _plan_again_trace as trace_helper

    asset_root, originals = _copy_plan_again_trace_assets(tmp_path)

    class ExpectedFailure(Exception):
        pass

    def exercise() -> None:
        with installed_plan_again_trace(tmp_path) as hashes:
            assert tuple(hashes) == _TRACE_ASSET_NAMES
            for name in _TRACE_ASSET_NAMES:
                import re

                expected = originals[name].decode("utf-8")
                for anchor, replacement in trace_helper._ASSET_PATCHES[name]:
                    pattern = re.compile(
                        re.escape(anchor).replace(re.escape("\n"), r"\r?\n")
                    )
                    matches = list(pattern.finditer(expected))
                    assert len(matches) == 1
                    match = matches[0]
                    local = match.group(0) + expected[max(0, match.start() - 256):match.start()]
                    newline = "\r\n" if "\r\n" in local else "\n"
                    expected = (
                        expected[:match.start()]
                        + replacement.replace("\n", newline)
                        + expected[match.end():]
                    )
                instrumented = (asset_root / name).read_bytes()
                assert instrumented == expected.encode("utf-8")
                assert hashes[name] == {
                    "original": hashlib.sha256(originals[name]).hexdigest(),
                    "instrumented": hashlib.sha256(instrumented).hexdigest(),
                    "anchors": len(trace_helper._ASSET_PATCHES[name]),
                }
            if raise_inside:
                raise ExpectedFailure

    if raise_inside:
        with pytest.raises(ExpectedFailure):
            exercise()
    else:
        exercise()
    assert {
        name: (asset_root / name).read_bytes()
        for name in _TRACE_ASSET_NAMES
    } == originals


def test_plan_again_trace_anchor_failure_makes_no_partial_mutation(
    tmp_path: Path,
) -> None:
    import _plan_again_trace as trace_helper

    asset_root, _originals = _copy_plan_again_trace_assets(tmp_path)
    app_path = asset_root / "app.js"
    anchor = trace_helper._ASSET_PATCHES["app.js"][-1][0]
    text = app_path.read_text(encoding="utf-8")
    assert text.count(anchor) == 1
    app_path.write_text(text.replace(anchor, "// removed trace anchor\n", 1), encoding="utf-8")
    before = {
        name: (asset_root / name).read_bytes()
        for name in _TRACE_ASSET_NAMES
    }

    with pytest.raises(AssertionError, match="anchor drifted in app.js"):
        with installed_plan_again_trace(tmp_path):
            raise AssertionError("context must not open")

    assert {
        name: (asset_root / name).read_bytes()
        for name in _TRACE_ASSET_NAMES
    } == before


def test_plan_again_host_trace_records_exact_phases_and_closed_entries() -> None:
    from _plan_again_trace import PHASES, PlanAgainHostTrace

    trace = PlanAgainHostTrace()
    trace.record("registry", "entered")
    assert trace.snapshot() == {"cases": {}}
    for phase in sorted(PHASES):
        trace.begin(phase)
        trace.record("registry", "entered")
        trace.end(phase)
        trace.record("registry", "returned")
    snapshot = trace.snapshot()
    assert snapshot == {
        "cases": {
            phase: {
                "entries": [{
                    "sequence": 1,
                    "stage": "registry",
                    "value": "entered",
                }],
                "overflow": False,
            }
            for phase in sorted(PHASES)
        }
    }
    validate_trace_snapshot(snapshot, set(PHASES))
    with pytest.raises(ValueError, match="unknown Plan-again trace phase"):
        trace.begin("outside")
    trace.begin("setup")
    with pytest.raises(ValueError, match="phase does not match"):
        trace.end("task-47-48")


@pytest.mark.parametrize(
    ("stage", "value"),
    (("unknown-stage", "entered"), ("registry", "unknown-value")),
)
def test_plan_again_trace_validator_rejects_open_stage_or_value(
    stage: str,
    value: str,
) -> None:
    from _plan_again_trace import PlanAgainHostTrace

    trace = PlanAgainHostTrace()
    trace.begin("setup")
    trace.record(stage, value)
    with pytest.raises(AssertionError, match="entry shape"):
        validate_trace_snapshot(trace.snapshot(), {"setup"})


def test_plan_again_trace_validator_handles_empty_host_case_and_overflow() -> None:
    from _plan_again_trace import TRACE_LIMIT, PlanAgainHostTrace

    empty = PlanAgainHostTrace()
    empty.begin("setup")
    validate_trace_snapshot(empty.snapshot(), {"setup"}, allow_empty=True)
    with pytest.raises(AssertionError, match="case bounds"):
        validate_trace_snapshot(empty.snapshot(), {"setup"})

    overflow = PlanAgainHostTrace()
    overflow.begin("task-47-48")
    for _index in range(TRACE_LIMIT + 1):
        overflow.record("registry", "entered")
    case = overflow.snapshot()["cases"]["task-47-48"]
    assert len(case["entries"]) == TRACE_LIMIT
    assert case["overflow"] is True
    with pytest.raises(AssertionError, match="case bounds"):
        validate_trace_snapshot(overflow.snapshot(), {"task-47-48"})


def test_plan_again_command_wrappers_delegate_once_and_preserve_results() -> None:
    from dataclasses import dataclass
    from _plan_again_trace import PlanAgainHostTrace, traced_plan_again_commands

    calls: list[tuple[str, object]] = []
    payload = object()
    validated = object()
    handled = object()

    def validate(value: object) -> object:
        calls.append(("validate", value))
        return validated

    def handle(value: object) -> object:
        calls.append(("handle", value))
        return handled

    @dataclass(frozen=True)
    class Spec:
        validate_payload: object
        handler: object
        retained: object

    retained = object()
    other = object()
    trace = PlanAgainHostTrace()
    trace.begin("setup")
    wrapped = traced_plan_again_commands(
        {
            "other": other,
            "plan_again": Spec(validate, handle, retained),
        },
        trace,
    )
    spec = wrapped["plan_again"]
    assert wrapped["other"] is other
    assert spec.retained is retained
    assert spec.validate_payload(payload) is validated
    assert spec.handler(payload) is handled
    assert calls == [("validate", payload), ("handle", payload)]
    validate_trace_snapshot(trace.snapshot(), {"setup"})


def test_plan_again_command_wrappers_rethrow_original_exceptions() -> None:
    from dataclasses import dataclass
    from _plan_again_trace import PlanAgainHostTrace, traced_plan_again_commands

    @dataclass(frozen=True)
    class Spec:
        validate_payload: object
        handler: object

    for member in ("validate_payload", "handler"):
        calls: list[tuple[str, object]] = []
        failure = RuntimeError(member)

        def fail(value: object, *, _member: str = member) -> object:
            calls.append((_member, value))
            raise failure

        trace = PlanAgainHostTrace()
        trace.begin("setup")
        spec = Spec(
            fail if member == "validate_payload" else lambda value: value,
            fail if member == "handler" else lambda value: value,
        )
        wrapped = traced_plan_again_commands({"plan_again": spec}, trace)
        payload = object()
        with pytest.raises(RuntimeError) as raised:
            getattr(wrapped["plan_again"], member)(payload)
        assert raised.value is failure
        assert calls == [(member, payload)]


def test_plan_again_registry_wrapper_preserves_call_and_rethrow() -> None:
    from _plan_again_trace import PlanAgainHostTrace, trace_registry_plan_again

    class Registry:
        def __init__(
            self, result: object, failure: BaseException | None = None,
            *, replay: object = None, replay_failure: BaseException | None = None,
        ) -> None:
            self.result = result
            self.failure = failure
            self.replay = replay
            self.replay_failure = replay_failure
            self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
            self.replay_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def replay_start(self, *args: object, **kwargs: object) -> object:
            self.replay_calls.append((args, kwargs))
            if self.replay_failure is not None:
                raise self.replay_failure
            return self.replay

        def start_plan_again(self, *args: object, **kwargs: object) -> object:
            self.calls.append((args, kwargs))
            if self.failure is not None:
                raise self.failure
            return self.result

    result = object()
    trace = PlanAgainHostTrace()
    trace.begin("task-47-48")
    registry = Registry(result)
    trace_registry_plan_again(registry, trace)
    assert registry.replay_start("command", ("intent",)) is None
    assert registry.replay_calls == [(("command", ("intent",)), {})]
    assert registry.start_plan_again("task-47", expected_revision=8) is result
    assert registry.calls == [(('task-47',), {"expected_revision": 8})]
    validate_trace_snapshot(trace.snapshot(), {"task-47-48"})

    failure = RuntimeError("registry")
    failed_trace = PlanAgainHostTrace()
    failed_trace.begin("task-48-49")
    failed = Registry(object(), failure)
    trace_registry_plan_again(failed, failed_trace)
    with pytest.raises(RuntimeError) as raised:
        failed.start_plan_again("task-48", expected_revision=9)
    assert raised.value is failure
    assert failed.calls == [(('task-48',), {"expected_revision": 9})]
    validate_trace_snapshot(failed_trace.snapshot(), {"task-48-49"})

    replay_result = object()
    hit_trace = PlanAgainHostTrace()
    hit_trace.begin("setup")
    hit = Registry(object(), replay=replay_result)
    trace_registry_plan_again(hit, hit_trace)
    assert hit.replay_start("command", ("intent",)) is replay_result
    assert hit.replay_calls == [(("command", ("intent",)), {})]
    validate_trace_snapshot(hit_trace.snapshot(), {"setup"})

    replay_failure = RuntimeError("replay")
    replay_error_trace = PlanAgainHostTrace()
    replay_error_trace.begin("setup")
    replay_error = Registry(object(), replay_failure=replay_failure)
    trace_registry_plan_again(replay_error, replay_error_trace)
    with pytest.raises(RuntimeError) as replay_raised:
        replay_error.replay_start("command", ("intent",))
    assert replay_raised.value is replay_failure
    assert replay_error.replay_calls == [(("command", ("intent",)), {})]
    validate_trace_snapshot(replay_error_trace.snapshot(), {"setup"})
