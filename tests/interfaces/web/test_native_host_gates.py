"""Durable real-WebView2 evidence for BR-G-30 and BR-G-31."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

import _native_gate_child as native_gate_child
from conftest import HeadedInstalledWheel
from _headed_native import (
    clean_child_environment,
    close_window,
    read_text,
    require_absolute_local_test_root,
    scenario_deadline,
    start_headed_process,
    terminate_process_tree,
    wait_for_accessible_text,
    wait_for_process,
    wait_for_window,
)


_CHILD = Path(__file__).with_name("_native_gate_child.py")
_INDEX = Path(__file__).parents[2] / "assets" / "native_host_gate" / "index.html"
_SCRIPT = _INDEX.with_name("probe.js")
_REQUIRED_SETTINGS = {
    "OPEN_EXTERNAL_LINKS_IN_BROWSER": False,
    "ALLOW_FILE_URLS": False,
    "ALLOW_DOWNLOADS": False,
    "REMOTE_DEBUGGING_PORT": None,
}
_POISONED_SETTINGS = {
    "OPEN_EXTERNAL_LINKS_IN_BROWSER": True,
    "ALLOW_FILE_URLS": True,
    "ALLOW_DOWNLOADS": True,
    "REMOTE_DEBUGGING_PORT": 9222,
}


@dataclass(frozen=True, slots=True)
class _NativeLiveEvidence:
    installed_root: Path
    live_data_root: Path
    live_index: Path
    live: dict[str, object]
    packaged_popup: dict[str, object]


@dataclass(frozen=True, slots=True)
class _NativeFailureEvidence:
    attachment_failure: dict[str, object]
    runtime_refusal: dict[str, object]


@pytest.fixture(scope="session")
def native_live_gate_evidence(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path_factory: pytest.TempPathFactory,
) -> _NativeLiveEvidence:
    root = require_absolute_local_test_root(
        tmp_path_factory.mktemp("native-host-gates")
    )
    index = _stage_live_page(headed_installed_wheel, root)
    live_root = require_absolute_local_test_root(root / "live")
    live = _run_live_probe(
        headed_installed_wheel,
        data_root=live_root,
        index=index,
        output=root / "live.json",
    )
    packaged_popup = _run_packaged_popup_probe(
        headed_installed_wheel,
        data_root=require_absolute_local_test_root(root / "packaged-popup"),
        index=index,
        output=root / "packaged-popup.json",
    )
    return _NativeLiveEvidence(
        installed_root=headed_installed_wheel.root.resolve(),
        live_data_root=live_root,
        live_index=index,
        live=live,
        packaged_popup=packaged_popup,
    )


@pytest.fixture(scope="session")
def native_failure_gate_evidence(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path_factory: pytest.TempPathFactory,
) -> _NativeFailureEvidence:
    root = require_absolute_local_test_root(
        tmp_path_factory.mktemp("native-host-failure-gates")
    )
    index = require_absolute_local_test_root(_INDEX)
    attachment_failure = _run_noninteractive_probe(
        headed_installed_wheel,
        mode="attachment-failure",
        data_root=require_absolute_local_test_root(root / "attachment-failure"),
        index=index,
        output=root / "attachment-failure.json",
        expected_returncode=1,
    )
    runtime_refusal = _run_noninteractive_probe(
        headed_installed_wheel,
        mode="runtime-refusal",
        data_root=require_absolute_local_test_root(root / "runtime-refusal"),
        index=index,
        output=root / "runtime-refusal.json",
        expected_returncode=1,
    )
    return _NativeFailureEvidence(
        attachment_failure=attachment_failure,
        runtime_refusal=runtime_refusal,
    )


def test_native_host_gate_page_keeps_the_probe_in_inert_page_data() -> None:
    html = _INDEX.read_text(encoding="utf-8")
    script = _SCRIPT.read_text(encoding="utf-8")
    child = _CHILD.read_text(encoding="utf-8")
    runtime = native_gate_child._runtime_identity()
    transport = native_gate_child._transport_evidence()

    compile(child, str(_CHILD), "exec")
    assert "script-src 'self'" in html
    assert "unsafe-inline" not in html
    assert '<script type="module" src="probe.js"></script>' in html
    assert 'from "./appearance.js"' in script
    assert "await becomePresentationReady();" in script
    assert 'dispatchCommand("shell_ready", {})' in script
    assert "await appearance.whenAppliedAfter(baseline);" in script
    assert "window.pywebview.api.dispatch" in script
    assert "window.location.assign(NAVIGATION_TARGET)" in script
    assert "window.open(POPUP_TARGET)" in script
    assert "document.getElementById(\"status\").textContent" in script
    assert runtime["versions"]["pywebview"] == "6.2.1"
    assert runtime["versions"]["pythonnet"] == "3.1.0"
    assert transport["uses_window_evaluate_js"] is True
    assert transport["uses_return_callback_table"] is True
    packaged_probe = native_gate_child._PACKAGED_POPUP_SCRIPT
    assert "if (window.__namiPackagedPopupGate)" in packaged_probe
    assert "window.addEventListener(\"pywebviewready\", onReady)" in packaged_probe
    assert "if (window.pywebview?.api?.dispatch)" in packaged_probe
    assert 'await import("./bridge.js")' in packaged_probe
    assert "await bridge.whenBridgeReady();" in packaged_probe
    assert "await bridge.dispatchInteractive(" in packaged_probe
    assert child.count("startup_gate: object,") == 2
    assert child.count(
        "original_dispatcher(document, combined, startup_gate)"
    ) == 2
    assert child.count("combined = MappingProxyType(") == 2


@pytest.mark.headed
def test_br_g_30_real_installed_host_assumptions_are_measured(
    native_live_gate_evidence: _NativeLiveEvidence,
) -> None:
    evidence = native_live_gate_evidence.live
    runtime = evidence["runtime"]
    versions = runtime["versions"]
    transport = evidence["transport"]
    page = evidence["page"]
    observations = page["observations"]
    events = evidence["events"]

    assert evidence["schema_version"] == 1
    assert evidence["exit_code"] == 0
    assert evidence["startup_errors"] == []
    assert runtime["python_info"][:2] == [3, 13]
    assert versions["pywebview"] == "6.2.1"
    assert versions["pythonnet"] == "3.1.0"
    assert Path(runtime["executable"]).resolve().is_relative_to(
        native_live_gate_evidence.installed_root
    )
    assert Path(runtime["namisync_file"]).resolve().is_relative_to(
        native_live_gate_evidence.installed_root
    )
    assert Path(transport["webview_file"]).resolve().is_relative_to(
        native_live_gate_evidence.installed_root
    )

    trusted = urlsplit(evidence["trusted_url"])
    assert trusted.scheme == "http"
    assert trusted.hostname in {"127.0.0.1", "localhost"}
    assert trusted.port not in {None, 80}
    assert trusted.path.endswith("/index.html")
    assert evidence["browser_version"]
    assert "Microsoft.Web.WebView2.Core.CoreWebView2" in evidence["native_core_type"]
    assert evidence["pythonnet_event_subscription"] == {
        "add": True,
        "remove": True,
    }

    configure_end = _only_event(events, "configure_security.end")
    before_load_enter = _first_event(events, "before_load.enter")
    before_load = _first_event(events, "before_load.after")
    guard_attach = _only_event(events, "guard_attach.begin")
    guard_attached = _only_event(events, "guard_attach.end")
    baseline_dispatch = _phase_event(events, "baseline")
    assert before_load["invoke_required"] is False
    assert _same_origin(before_load["source"], evidence["trusted_url"])
    assert _same_origin(
        observations["baseline"]["page_url"],
        evidence["trusted_url"],
    )
    assert guard_attach["thread"] == before_load["thread"]
    assert guard_attached["thread"] == before_load["thread"]
    assert (
        configure_end["at"]
        < before_load_enter["at"]
        < guard_attach["at"]
        < guard_attached["at"]
        < before_load["at"]
        < baseline_dispatch["at"]
    )
    assert observations["baseline"]["handler_thread"] != before_load["thread"]

    frame = _target_event(evidence["frame_navigation"], "/frame")
    navigation = _target_event(evidence["top_level_navigation"], "/navigation")
    assert frame["cancel"] is True
    assert navigation["cancel"] is True
    nami_frame_begin = _named_target_event(events, "nami_frame.begin", "/frame")
    nami_frame_end = _named_target_event(events, "nami_frame.end", "/frame")
    assert nami_frame_begin["cancel"] is False
    assert nami_frame_end["cancel"] is True
    nami_navigation_begin = _named_target_event(
        events,
        "nami_navigation.begin",
        "/navigation",
    )
    nami_navigation_end = _named_target_event(
        events,
        "nami_navigation.end",
        "/navigation",
    )
    assert nami_navigation_begin["cancel"] is False
    assert nami_navigation_end["cancel"] is True

    after_navigation = observations["afterNavigation"]
    measured_current_url = evidence["off_thread_current_url_after_cancel"]
    assert measured_current_url["thread"] != before_load["thread"]
    assert isinstance(measured_current_url["value"], str)
    assert after_navigation["managed_url"] == (
        "https://example.invalid/managed-url-poison"
    )
    assert _phase_event(events, "after_navigation")["thread"] != before_load[
        "thread"
    ]
    assert _same_origin(after_navigation["native_cached_url"], evidence["trusted_url"])
    assert after_navigation["document_attached"] is True
    assert evidence["delayed_handler_completed"] is True
    delayed_transport = observations["delayedTransport"]
    assert delayed_transport["delayed_evaluate_observed"] is True
    delayed_evaluate_begin = _only_event(events, "delayed_return.evaluate.begin")
    delayed_evaluate_end = _only_event(events, "delayed_return.evaluate.end")
    delayed_transport_ack = _only_event(events, "delayed_transport.ack")
    second_ready = next(
        event
        for event in events
        if event["name"] == "pywebviewready" and event["count"] == 2
    )
    assert (
        navigation["at"]
        < second_ready["at"]
        < delayed_evaluate_begin["at"]
        < delayed_evaluate_end["at"]
        < delayed_transport_ack["at"]
        < _phase_event(events, "after_navigation")["at"]
    )
    assert page["lost_settled"] is False
    assert observations["afterNavigation"]["page_ready_count"] == 2
    assert observations["afterPopup"]["page_ready_count"] == 3
    assert page["ready_count"] == 3
    presentation_revisions = observations["presentationRevisions"]
    assert len(presentation_revisions) == 3
    assert presentation_revisions == sorted(set(presentation_revisions))
    assert all(revision > 0 for revision in presentation_revisions)
    assert evidence["production_command_names"] == [
        "close_task",
        "next_events",
        "pick_folder",
        "release_terminal_session",
        "shell_ready",
        "start_plan",
    ]
    assert evidence["combined_command_names"] == sorted(
        [*evidence["production_command_names"], "native_probe"]
    )
    assert evidence["combined_mapping_type"] == "mappingproxy"

    assert transport["uses_js_bridge_call"] is True
    assert transport["uses_window_evaluate_js"] is True
    assert transport["uses_return_callback_table"] is True
    assert transport["uses_structured_json_result"] is True
    assert len(transport["js_bridge_call_sha256"]) == 64
    assert len(transport["api_js_sha256"]) == 64
    assert len(transport["edge_backend_sha256"]) == 64
    for phase, result in (
        ("baseline", observations["baseline"]),
        ("after_frame", observations["afterFrame"]),
        ("after_navigation", observations["afterNavigation"]),
        ("after_popup", observations["afterPopup"]),
    ):
        assert result["token"] == f"returned-{phase}"

    popup = _target_event(evidence["new_window"], "/popup")
    popup_navigation = _target_event(
        evidence["top_level_navigation"],
        "/popup",
    )
    assert popup["handled"] is True
    assert popup_navigation["cancel"] is True
    pywebview_popup_begin = _named_target_event(
        events,
        "pywebview_popup.begin",
        "/popup",
    )
    pywebview_popup_end = _named_target_event(
        events,
        "pywebview_popup.end",
        "/popup",
    )
    nami_popup_begin = _named_target_event(events, "nami_popup.begin", "/popup")
    nami_popup_end = _named_target_event(events, "nami_popup.end", "/popup")
    assert pywebview_popup_begin["handled"] is False
    assert pywebview_popup_end["handled"] is True
    assert nami_popup_end["handled"] is True
    assert (
        pywebview_popup_begin["at"]
        < pywebview_popup_end["at"]
        < nami_popup_begin["at"]
        < nami_popup_end["at"]
        < popup["at"]
    )
    assert evidence["system_browser_calls"] == []
    assert page["initial_url"] == page["final_url"]
    assert observations["afterPopup"]["popup_return"] in {"null", "object"}
    assert observations["afterPopup"]["page_document_token"] == page[
        "document_token"
    ]
    assert observations["afterPopup"]["document_attached"] is True
    assert observations["afterPopup"]["managed_url"] == (
        "https://example.invalid/managed-url-poison"
    )
    assert _same_origin(
        observations["afterPopup"]["native_cached_url"],
        evidence["trusted_url"],
    )
    _assert_packaged_popup_evidence(
        native_live_gate_evidence.packaged_popup,
        installed_root=native_live_gate_evidence.installed_root,
    )


@pytest.mark.headed
def test_br_g_31_installed_host_composition_preserves_security_boundaries(
    native_live_gate_evidence: _NativeLiveEvidence,
    native_failure_gate_evidence: _NativeFailureEvidence,
) -> None:
    evidence = native_live_gate_evidence.live
    runtime = evidence["runtime"]
    page = evidence["page"]
    observations = page["observations"]
    events = evidence["events"]
    event_names = [event["name"] for event in events]

    first_prepare_end = event_names.index("prepare.end")
    create_begin = event_names.index("create_window.begin")
    start_index = event_names.index("webview.start")
    prepare_ends = [
        index for index, name in enumerate(event_names) if name == "prepare.end"
    ]
    assert len(prepare_ends) >= 2
    assert first_prepare_end < create_begin
    assert any(create_begin < index < start_index for index in prepare_ends)
    assert evidence["settings_before_prepare"] == _POISONED_SETTINGS
    assert all(
        settings == _REQUIRED_SETTINGS
        for settings in evidence["prepare_settings"]
    )
    create_event = _only_event(events, "create_window.begin")
    start_event = _only_event(events, "webview.start")
    assert create_event["settings"] == _REQUIRED_SETTINGS
    assert start_event["settings"] == _REQUIRED_SETTINGS
    assert start_event["gui"] == "edgechromium"
    assert start_event["debug"] is False
    assert start_event["http_server"] is True
    assert start_event["private_mode"] is True
    assert Path(start_event["storage_path"]).resolve().is_relative_to(
        native_live_gate_evidence.live_data_root
    )
    assert evidence["renderer"] == "edgechromium"
    assert Path(evidence["input_index"]).resolve() == (
        native_live_gate_evidence.live_index.resolve()
    )

    guard_attach = _only_event(events, "guard_attach.begin")
    assert guard_attach["at"] < _phase_event(events, "baseline")["at"]
    source_probe = [
        event
        for event in events
        if event["name"] == "nami_source.begin"
        and event["source"].endswith("#source-probe")
    ]
    assert source_probe
    source_probe_end = [
        event
        for event in events
        if event["name"] == "nami_source.end"
        and event["source"].endswith("#source-probe")
    ]
    assert source_probe_end
    assert source_probe_end[-1]["document_url"].endswith("#source-probe")
    assert _target_event(evidence["top_level_navigation"], "/navigation")[
        "cancel"
    ] is True
    assert _target_event(evidence["frame_navigation"], "/frame")["cancel"] is True
    assert _target_event(evidence["new_window"], "/popup")["handled"] is True
    assert _target_event(evidence["top_level_navigation"], "/popup")[
        "cancel"
    ] is True

    refusal = observations["offOriginRefusal"][
        "injected_committed_source_refusal"
    ]
    assert refusal == {
        "response": {
            "schema_version": 1,
            "request_id": None,
            "ok": False,
            "error": {
                "code": "bridge_unavailable",
                "message": (
                    "NamiSync is closing or this desktop page is no longer trusted."
                ),
            },
        },
        "inner_handler_called": False,
    }
    assert page["initial_url"] == page["final_url"]
    assert page["document_token"]
    assert evidence["system_browser_calls"] == []
    assert observations["afterPopup"]["token"] == "returned-after_popup"
    _assert_packaged_popup_evidence(
        native_live_gate_evidence.packaged_popup,
        installed_root=native_live_gate_evidence.installed_root,
    )

    failure = native_failure_gate_evidence.attachment_failure
    assert failure["exit_code"] == 1
    assert failure["attachment_error"] == "native gate injected attachment failure"
    assert failure["window_closed"] is True
    assert len(failure["startup_errors"]) == 1
    assert "WebView2 security guards could not attach" in failure["startup_errors"][0]
    assert "native gate injected attachment failure" in failure["startup_errors"][0]
    failure_events = failure["events"]
    assert (
        _only_event(failure_events, "attachment.configure.end")["at"]
        < _only_event(failure_events, "attachment.before_load.enter")["at"]
        < _only_event(failure_events, "attachment.guard.fail")["at"]
        < _only_event(failure_events, "attachment.before_load.after")["at"]
        < _only_event(failure_events, "attachment.window.destroy")["at"]
        < _only_event(failure_events, "attachment.window.native_close")["at"]
    )
    assert len(
        [
            event
            for event in failure_events
            if event["name"] == "attachment.window.destroy"
        ]
    ) == 1
    assert len(
        [
            event
            for event in failure_events
            if event["name"] == "attachment.window.native_close"
        ]
    ) == 1
    assert Path(failure["runtime"]["executable"]).resolve().is_relative_to(
        native_live_gate_evidence.installed_root
    )
    assert Path(failure["transport"]["util_file"]).resolve().is_relative_to(
        native_live_gate_evidence.installed_root
    )
    assert Path(failure["transport"]["window_file"]).resolve().is_relative_to(
        native_live_gate_evidence.installed_root
    )

    refusal_probe = native_failure_gate_evidence.runtime_refusal
    assert refusal_probe["exit_code"] == 1
    assert refusal_probe["create_window_called"] is False
    assert refusal_probe["platform_modules"] == []
    assert len(refusal_probe["startup_errors"]) == 1
    assert "Microsoft Edge WebView2 Runtime" in refusal_probe["startup_errors"][0]
    assert "install it and restart NamiSync" in refusal_probe["startup_errors"][0]
    assert refusal_probe["real_runtime_probe"] == {
        "available": True,
        "refusal_reason": None,
    }
    assert refusal_probe["settings_before_prepare"] == _POISONED_SETTINGS
    assert refusal_probe["settings_at_runtime_probe"] == _REQUIRED_SETTINGS
    registry_opens = refusal_probe["registry_opens"]
    assert registry_opens
    assert all(
        entry["reserved"] == 0
        and entry["access"] == refusal_probe["registry_key_read"]
        for entry in registry_opens
    )
    assert any(
        entry["hive"] == "HKLM"
        and entry["path"].endswith(r"NET Framework Setup\NDP\v4\Full")
        for entry in registry_opens
    )
    assert Path(refusal_probe["runtime"]["executable"]).resolve().is_relative_to(
        native_live_gate_evidence.installed_root
    )
    assert Path(refusal_probe["transport"]["util_file"]).resolve().is_relative_to(
        native_live_gate_evidence.installed_root
    )
    assert Path(refusal_probe["transport"]["window_file"]).resolve().is_relative_to(
        native_live_gate_evidence.installed_root
    )

    assert runtime["entry_points"] == [
        {
            "group": "console_scripts",
            "name": "nami-sync",
            "value": "namisync.interfaces.launcher:main",
        },
        {
            "group": "gui_scripts",
            "name": "nami-sync-gui",
            "value": "namisync.interfaces.launcher:gui_main",
        },
    ]


def _run_live_probe(
    installed: HeadedInstalledWheel,
    *,
    data_root: Path,
    index: Path,
    output: Path,
) -> dict[str, object]:
    deadline = scenario_deadline(60.0)
    process = _start_probe(
        installed,
        mode="live",
        data_root=data_root,
        index=index,
        output=output,
        deadline=deadline,
    )
    title = str(process.args[process.args.index("--title") + 1])
    try:
        handle = wait_for_window(process, title, deadline=deadline)
        wait_for_accessible_text(
            handle,
            "Native host gates passed",
            python=installed.python,
            deadline=deadline,
        )
        close_window(handle)
        completed = wait_for_process(process, deadline=deadline)
    finally:
        if process.poll() is None:
            terminate_process_tree(process, deadline=deadline)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(read_text(output, deadline=deadline))


def _stage_live_page(
    installed: HeadedInstalledWheel,
    root: Path,
) -> Path:
    page = require_absolute_local_test_root(root / "live-page")
    shutil.copytree(_INDEX.parent, page)
    installed_asset = (
        installed.root
        / "Lib"
        / "site-packages"
        / "namisync"
        / "interfaces"
        / "web"
        / "assets"
        / "appearance.js"
    ).resolve(strict=True)
    assert installed_asset.is_relative_to(installed.root.resolve())
    destination = page / "appearance.js"
    shutil.copy2(installed_asset, destination)
    assert destination.read_bytes() == installed_asset.read_bytes()
    return require_absolute_local_test_root(page / "index.html")


def _run_noninteractive_probe(
    installed: HeadedInstalledWheel,
    *,
    mode: str,
    data_root: Path,
    index: Path,
    output: Path,
    expected_returncode: int,
) -> dict[str, object]:
    deadline = scenario_deadline(60.0)
    process = _start_probe(
        installed,
        mode=mode,
        data_root=data_root,
        index=index,
        output=output,
        deadline=deadline,
    )
    try:
        completed = wait_for_process(process, deadline=deadline)
    finally:
        if process.poll() is None:
            terminate_process_tree(process, deadline=deadline)
    assert completed.returncode == expected_returncode, (
        completed.stdout + completed.stderr
    )
    return json.loads(read_text(output, deadline=deadline))


def _run_packaged_popup_probe(
    installed: HeadedInstalledWheel,
    *,
    data_root: Path,
    index: Path,
    output: Path,
) -> dict[str, object]:
    deadline = scenario_deadline(60.0)
    process = _start_probe(
        installed,
        mode="packaged-popup",
        data_root=data_root,
        index=index,
        output=output,
        deadline=deadline,
    )
    title = str(process.args[process.args.index("--title") + 1])
    try:
        handle = wait_for_window(process, title, deadline=deadline)
        wait_for_accessible_text(
            handle,
            "Packaged popup gate passed",
            python=installed.python,
            deadline=deadline,
        )
        close_window(handle)
        completed = wait_for_process(process, deadline=deadline)
    finally:
        if process.poll() is None:
            terminate_process_tree(process, deadline=deadline)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(read_text(output, deadline=deadline))


def _start_probe(
    installed: HeadedInstalledWheel,
    *,
    mode: str,
    data_root: Path,
    index: Path,
    output: Path,
    deadline,
):
    token = uuid4().hex
    return start_headed_process(
        (
            installed.python,
            _CHILD,
            "--mode",
            mode,
            "--data-dir",
            data_root,
            "--index",
            index,
            "--mutex",
            rf"Local\NamiSync.Test.NativeGate.{token}",
            "--title",
            f"NamiSync Native Gate {token}",
            "--output",
            output,
        ),
        cwd=installed.root,
        environment=clean_child_environment(),
        deadline=deadline,
    )


def _only_event(
    events: list[dict[str, object]],
    name: str,
) -> dict[str, object]:
    matches = [event for event in events if event["name"] == name]
    assert len(matches) == 1, (name, matches)
    return matches[0]


def _first_event(
    events: list[dict[str, object]],
    name: str,
) -> dict[str, object]:
    matches = [event for event in events if event["name"] == name]
    assert matches, (name, events)
    return matches[0]


def _phase_event(
    events: list[dict[str, object]],
    phase: str,
) -> dict[str, object]:
    matches = [
        event
        for event in events
        if event["name"] == "dispatch" and event["phase"] == phase
    ]
    assert len(matches) == 1, (phase, matches)
    return matches[0]


def _target_event(
    events: list[dict[str, object]],
    suffix: str,
) -> dict[str, object]:
    matches = [event for event in events if urlsplit(event["uri"]).path == suffix]
    assert matches, (suffix, events)
    return matches[-1]


def _named_target_event(
    events: list[dict[str, object]],
    name: str,
    suffix: str,
) -> dict[str, object]:
    matches = [
        event
        for event in events
        if event["name"] == name and urlsplit(event["uri"]).path == suffix
    ]
    assert matches, (name, suffix, events)
    return matches[-1]


def _assert_packaged_popup_evidence(
    evidence: dict[str, object],
    *,
    installed_root: Path,
) -> None:
    assert evidence["exit_code"] == 0
    assert evidence["startup_errors"] == []
    assert evidence["renderer"] == "edgechromium"
    events = evidence["events"]
    create = _only_event(events, "create_window.begin")
    index = Path(create["index"]).resolve()
    assert index.is_relative_to(installed_root)
    assert index.parts[-3:] == ("web", "assets", "index.html")
    execute = _only_event(events, "packaged_probe.execute")
    dispatch = _phase_event(events, "packaged_popup")
    popup = _target_event(evidence["new_window"], "/packaged-popup")
    pywebview_begin = _named_target_event(
        events,
        "pywebview_popup.begin",
        "/packaged-popup",
    )
    pywebview_end = _named_target_event(
        events,
        "pywebview_popup.end",
        "/packaged-popup",
    )
    nami_begin = _named_target_event(
        events,
        "nami_popup.begin",
        "/packaged-popup",
    )
    nami_end = _named_target_event(
        events,
        "nami_popup.end",
        "/packaged-popup",
    )
    assert pywebview_begin["handled"] is False
    assert pywebview_end["handled"] is True
    assert nami_end["handled"] is True
    assert (
        execute["at"]
        < pywebview_begin["at"]
        < pywebview_end["at"]
        < nami_begin["at"]
        < nami_end["at"]
        < popup["at"]
        < dispatch["at"]
    )
    ready_events = [
        event for event in events if event["name"] == "pywebviewready"
    ]
    assert len(ready_events) >= 2
    assert ready_events[1]["at"] < dispatch["at"]
    page = evidence["packaged_page"]
    assert page["initial_url"] == page["final_url"]
    assert page["document_token"].startswith("packaged-")
    assert page["ready_count"] >= 2
    assert evidence["production_command_names"] == [
        "close_task",
        "next_events",
        "pick_folder",
        "release_terminal_session",
        "shell_ready",
        "start_plan",
    ]
    assert evidence["combined_command_names"] == sorted(
        [*evidence["production_command_names"], "packaged_probe"]
    )
    assert evidence["combined_mapping_type"] == "mappingproxy"
    assert evidence["system_browser_calls"] == []


def _same_origin(first: str, second: str) -> bool:
    left = urlsplit(first)
    right = urlsplit(second)
    return (left.scheme, left.hostname, left.port) == (
        right.scheme,
        right.hostname,
        right.port,
    )
