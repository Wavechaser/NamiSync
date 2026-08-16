"""Installed-wheel headed evidence for the GUI Break 1 component gallery."""

from __future__ import annotations

import base64
import hashlib
import inspect
import json
import math
import re
import sys
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

import _component_gallery_child as component_gallery_child
from conftest import HeadedInstalledWheel
from namisync.interfaces.web.commands import CommandPayloadError
from namisync.version import VERSION
from _headed_native import (
    clean_child_environment,
    close_window,
    read_text,
    require_absolute_local_test_root,
    scenario_deadline,
    start_headed_process,
    terminate_process_tree,
    wait_for_accessible_text,
    wait_for_path,
    wait_for_process,
    wait_for_window,
)


_CHILD = Path(__file__).with_name("_component_gallery_child.py")
_SCENARIO = Path(__file__).parents[2] / "assets" / "component_gallery" / "gallery.js"
_MODES = ("light", "dark", "forced", "reduced")
_ASSET_NAMES = ("index.html", "tokens.css", "components.css")
_TEST_ONLY_MARKER = b"NAMISYNC_TEST_ONLY_COMPONENT_GALLERY_5CE45567A17F4D74"
_STATUS_KEYS = {
    "complete",
    "success",
    "failure",
    "error",
    "warning",
    "degraded",
    "incomplete",
    "active",
    "paused",
    "canceled",
    "mismatch",
    "blocked",
    "deferred",
    "neutral",
    "noop",
}
_OPERATION_KEYS = {
    "copy",
    "update",
    "move",
    "move_update",
    "recase",
    "mkdir",
    "trash",
    "delete",
    "noop",
}
_CONTROL_KEYS = {
    "button",
    "dropdown",
    "tri_state_checkbox",
    "progress_determinate",
    "progress_indeterminate",
    "text_input",
    "toggle",
    "chip",
    "list_row",
    "tree_row",
    "card",
    "task_card",
    "task_card_selected",
    "task_card_current",
    "dialog",
    "context_menu",
    "segmented_control",
}
_CONTROL_STATES = {"rest", "hover", "pressed", "disabled", "focused"}
_TEXT_CONTROL_KEYS = {
    "button",
    "dropdown",
    "text_input",
    "chip",
    "list_row",
    "tree_row",
    "card",
    "dialog",
    "context_menu",
    "segmented_control",
}
_BOUNDARY_CONTROL_KEYS = {
    "button",
    "dropdown",
    "tri_state_checkbox",
    "progress_determinate",
    "progress_indeterminate",
    "text_input",
    "toggle",
    "chip",
    "card",
    "dialog",
    "context_menu",
    "segmented_control",
}
_RGB = re.compile(
    r"rgba?\(\s*([0-9.]+)(?:\s*,|\s+)\s*([0-9.]+)"
    r"(?:\s*,|\s+)\s*([0-9.]+)(?:\s*(?:,|/)\s*([0-9.]+))?\s*\)"
)


@dataclass(frozen=True, slots=True)
class _GalleryEvidence:
    installed: HeadedInstalledWheel
    root: Path
    scenario: Path
    results: dict[str, dict[str, object]]

    def result(self, mode: str) -> dict[str, object]:
        if mode not in _MODES:
            raise ValueError("unknown component gallery mode")
        if mode not in self.results:
            self.results[mode] = _run_gallery_mode(
                self.installed,
                mode=mode,
                root=require_absolute_local_test_root(self.root / mode),
                scenario=self.scenario,
            )
        return self.results[mode]


@pytest.fixture(scope="session")
def component_gallery_evidence(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path_factory: pytest.TempPathFactory,
) -> _GalleryEvidence:
    root = require_absolute_local_test_root(
        tmp_path_factory.mktemp("component-gallery")
    )
    scenario = require_absolute_local_test_root(_SCENARIO)
    return _GalleryEvidence(headed_installed_wheel, root, scenario, {})


def test_component_gallery_evidence_runs_only_requested_mode_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    installed = HeadedInstalledWheel(
        wheel=tmp_path / "namisync.whl",
        root=tmp_path / "installed",
        python=tmp_path / "python.exe",
        scripts=tmp_path / "Scripts",
    )
    scenario = tmp_path / "gallery.js"
    calls: list[tuple[str, Path, Path]] = []
    result = {"mode": "dark"}

    def run(
        observed_installed: HeadedInstalledWheel,
        *,
        mode: str,
        root: Path,
        scenario: Path,
    ) -> dict[str, object]:
        assert observed_installed is installed
        calls.append((mode, root, scenario))
        return result

    monkeypatch.setitem(globals(), "_run_gallery_mode", run)
    evidence = _GalleryEvidence(installed, tmp_path, scenario, {})

    assert calls == []
    assert evidence.result("dark") is result
    assert evidence.result("dark") is result
    assert calls == [("dark", tmp_path / "dark", scenario)]
    assert "light" not in evidence.results


def test_component_gallery_harness_uses_packaged_page_and_test_owned_script() -> None:
    child = _CHILD.read_text(encoding="utf-8")

    assert _SCENARIO.is_relative_to(Path(__file__).parents[2] / "assets")
    assert "importlib.resources.files" in child
    assert '"index.html", "tokens.css", "components.css"' in child
    assert "index_path=" not in child
    assert "_execute_script_checked(" in child
    assert 'stage="scenario_injection"' in child
    assert "evaluate_js" not in child
    assert "CallDevToolsProtocolMethodAsync" in child
    assert '"Emulation.setEmulatedMedia"' in child
    assert 'protocol("DOM.enable", {}, dom_enabled)' in child
    assert 'protocol("CSS.enable", {}, css_enabled)' in child
    assert 'protocol("DOM.getDocument", {"depth": 0}, document_ready)' in child
    assert "def begin_injection_on_ui()" in child
    assert "native.BeginInvoke(injection_start)" in child
    assert "component gallery injection left the UI thread" not in child


def test_component_gallery_child_preserves_production_host_and_bridge() -> None:
    child = _CHILD.read_text(encoding="utf-8")

    assert "production = dict(commands)" in child
    assert 'if "test_report" in production:' in child
    assert "combined = MappingProxyType(" in child
    assert '"test_report": _test_report_spec(' in child
    assert "arguments.mode," in child
    assert "original_dispatcher(document, combined)" in child
    assert "original_configure(" in child
    assert "host.run_desktop(" in child
    assert "register" not in child.casefold()
    assert "extra_commands" not in child


def test_component_gallery_media_modes_are_exact_and_scenario_bounded() -> None:
    source = inspect.getsource(component_gallery_child)

    assert set(component_gallery_child._MEDIA_FEATURES) == set(_MODES)
    assert dict(component_gallery_child._MEDIA_FEATURES["light"])[
        "prefers-color-scheme"
    ] == "light"
    assert dict(component_gallery_child._MEDIA_FEATURES["dark"])[
        "prefers-color-scheme"
    ] == "dark"
    assert dict(component_gallery_child._MEDIA_FEATURES["forced"])[
        "forced-colors"
    ] == "active"
    assert dict(component_gallery_child._MEDIA_FEATURES["forced"])[
        "prefers-color-scheme"
    ] == "dark"
    assert dict(component_gallery_child._MEDIA_FEATURES["reduced"])[
        "prefers-reduced-motion"
    ] == "reduce"
    assert "--data-dir" in source
    assert "--scenario" in source


def test_component_gallery_report_parser_is_exact_and_nested(
    tmp_path: Path,
) -> None:
    def semantic(key: str) -> dict[str, object]:
        return {
            "key": key,
            "text": key,
            "icon": "info",
            "shape": "circle",
            "cue": "Visible cue",
            "visible_text": key,
            "shape_content": '"!"',
            "shape_color": "rgb(0, 0, 0)",
            "shape_display": "inline-grid",
            "shape_visibility": "visible",
            "shape_opacity": "1",
            "shape_width": 16.0,
            "shape_height": 16.0,
            "foreground": "rgb(0, 0, 0)",
            "background": "rgb(255, 255, 255)",
            "indicator": "rgb(0, 0, 0)",
            "alias_foreground": "rgb(0, 0, 0)",
            "alias_background": "rgb(255, 255, 255)",
            "alias_indicator": "rgb(0, 0, 0)",
            "aliases_consumed": True,
            "large_text": False,
            "icon_color": "rgb(0, 0, 0)",
            "mask_image": 'url("http://127.0.0.1/icons/info_20_regular.svg")',
        }

    controls = [
        {
            "control": control,
            "state": state,
            "label": f"{control} {state}",
            "foreground": "rgb(0, 0, 0)",
            "background": "rgb(255, 255, 255)",
            "border": "rgb(0, 0, 0)",
            "border_width": "1px",
            "border_style": "solid",
            "root_border": "rgb(0, 0, 0)",
            "root_border_width": "1px",
            "root_border_style": "solid",
            "root_background": "rgb(255, 255, 255)",
            "boundary": "rgb(0, 0, 0)",
            "outline_width": "1px",
            "outline_color": "rgb(0, 0, 0)",
            "outline_style": "solid",
            "box_shadow": "rgb(0, 0, 0) 0px 0px 0px 2px",
            "surrounding": "rgb(255, 255, 255)",
            "opacity": "1",
            "transform": "none",
            "transition_duration": "0.1s",
            "animation_duration": "0s",
            "animation_name": "none",
        }
        for control in component_gallery_child._CONTROL_KEYS
        for state in component_gallery_child._CONTROL_STATES
    ]
    report = {
        "phase": "complete",
        "mode": "light",
        "media": {"dark": False, "forced": False, "reduced": False},
        "statuses": [semantic(key) for key in component_gallery_child._STATUS_KEYS],
        "operations": [
            semantic(key) for key in component_gallery_child._OPERATION_KEYS
        ],
        "controls": controls,
        "control_contract": {
            "tri_state": {
                "aria_checked": "mixed",
                "indeterminate": True,
                "cue_content": '"−"',
            },
            "dialog_exit": {
                "opened": True,
                "retained_while_closing": True,
                "faded": True,
                "closed": True,
            },
        },
        "motion": {
            "nonessential_max_ms": 100,
            "indeterminate_iteration_count": "infinite",
        },
        "icons": {
            "registry_frozen": True,
            "registry_names": ["checkmark-circle", "dismiss-circle", "warning", "info"],
            "all_registry_created": True,
            "all_current_color": True,
            "all_mask_images": True,
            "unexpected_svg_count": 0,
            "unexpected_path_count": 0,
            "sizes": [
                {"size": "sm", "width": "16px", "height": "16px"},
                {"size": "md", "width": "20px", "height": "20px"},
                {"size": "lg", "width": "24px", "height": "24px"},
            ],
            "state_samples": [
                {
                    "state": state,
                    "icon_color": "rgb(0, 0, 0)",
                    "control_color": "rgb(0, 0, 0)",
                    "control_background": "rgb(255, 255, 255)",
                    "inherits": True,
                }
                for state in component_gallery_child._CONTROL_STATES
            ],
            "mask_images": {"info": 'url("/icons/info_20_regular.svg")'},
            "system_colors": {
                name: "rgb(255, 255, 255)"
                for name in component_gallery_child._SYSTEM_COLOR_NAMES
            },
        },
    }
    assert component_gallery_child._valid_complete_report(report) is True

    chunk_rows = component_gallery_child._CONTROL_REPORT_CHUNK_ROWS
    part_values = [
        ("statuses", report["statuses"]),
        ("operations", report["operations"]),
        *(
            ("controls", controls[offset : offset + chunk_rows])
            for offset in range(0, len(controls), chunk_rows)
        ),
        ("control_contract", report["control_contract"]),
        ("motion", report["motion"]),
        ("icons", report["icons"]),
    ]
    assert tuple(name for name, _value in part_values) == (
        component_gallery_child._REPORT_PART_NAMES
    )
    recorder = component_gallery_child._Recorder(
        tmp_path / "report.json",
        "light",
    )
    spec = component_gallery_child._test_report_spec(
        recorder,
        lambda _targets: None,
        "light",
    )
    for sequence, (name, value) in enumerate(part_values):
        payload = {
            "phase": "part",
            "sequence": sequence,
            "name": name,
            "value": value,
        }
        envelope = {
            "schema_version": 1,
            "request_id": "0" * 32,
            "command": "test_report",
            "payload": payload,
        }
        assert len(json.dumps(envelope).encode("utf-8")) <= 65_536
        assert spec.invoke(payload) == {"accepted": True}
    assert spec.invoke(
        {
            "phase": "complete",
            "mode": "light",
            "media": {"dark": False, "forced": False, "reduced": False},
            "part_count": len(part_values),
        }
    ) == {"accepted": True}
    recorded = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert recorded["report"] == report

    incomplete = component_gallery_child._test_report_spec(
        component_gallery_child._Recorder(tmp_path / "incomplete.json", "light"),
        lambda _targets: None,
        "light",
    )
    with pytest.raises(CommandPayloadError, match="report is invalid"):
        incomplete.invoke(
            {
                "phase": "complete",
                "mode": "light",
                "media": {"dark": False, "forced": False, "reduced": False},
                "part_count": len(part_values),
            }
        )
    with pytest.raises(CommandPayloadError, match="report is invalid"):
        incomplete.invoke(
            {
                "phase": "part",
                "sequence": 1,
                "name": "operations",
                "value": report["operations"],
            }
        )
    with pytest.raises(CommandPayloadError, match="report is invalid"):
        incomplete.validate_payload(
            {
                "phase": "part",
                "sequence": 2,
                "name": "controls",
                "value": controls[: chunk_rows - 1],
            }
        )

    assert (
        component_gallery_child._valid_complete_report(
            report,
            expected_mode="dark",
        )
        is False
    )

    report["media"]["unknown"] = False
    assert component_gallery_child._valid_complete_report(report) is False
    del report["media"]["unknown"]
    report["controls"][0]["state"] = "invented"
    assert component_gallery_child._valid_complete_report(report) is False

    boundary = controls[1]
    assert _control_boundary_contrast(boundary) == pytest.approx(21.0)
    boundary["border_width"] = "0px"
    boundary["root_border_width"] = "0px"
    with pytest.raises(AssertionError, match="no painted control boundary"):
        _control_boundary_contrast(boundary)
    boundary["border_width"] = "1px"
    boundary["root_border_width"] = "1px"
    boundary["border_style"] = "none"
    boundary["root_border_style"] = "none"
    with pytest.raises(AssertionError, match="no painted control boundary"):
        _control_boundary_contrast(boundary)


def test_component_gallery_script_declares_exact_required_matrix() -> None:
    script = _SCENARIO.read_text(encoding="utf-8")

    assert _declared_keys(script, "STATUS_CASES") == _STATUS_KEYS
    assert _declared_keys(script, "OPERATION_CASES") == _OPERATION_KEYS
    assert _declared_keys(script, "CONTROL_CASES") == _CONTROL_KEYS
    assert _declared_keys(script, "CONTROL_STATES") == _CONTROL_STATES
    assert 'import("/bridge.js")' in script
    assert 'import("/render.js")' in script
    assert 'import("/icons.js")' in script
    assert "const PSEUDO_STATE_SETTLE_MS = 350;" in script
    assert "setTimeout(resolve, PSEUDO_STATE_SETTLE_MS)" in script
    assert 'dialog.dataset.closing = "true";' in script
    assert "dialog.showModal();" in script
    assert "dialog.close();" in script
    assert "window.pywebview" not in script
    assert "innerHTML" not in script


def test_component_gallery_enables_dom_before_css_pseudo_state_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = ModuleType("System")
    setattr(system, "Action", lambda callback: callback)
    monkeypatch.setitem(sys.modules, "System", system)

    class CompletedTask:
        IsFaulted = False
        IsCanceled = False

        def __init__(self, result: str) -> None:
            self.Result = result

        def GetAwaiter(self) -> CompletedTask:
            return self

        def OnCompleted(self, callback: Callable[[], None]) -> None:
            callback()

    class Core:
        def __init__(self) -> None:
            self.methods: list[str] = []
            self.scripts: list[str] = []

        def CallDevToolsProtocolMethodAsync(
            self,
            method: str,
            _parameters: str,
        ) -> CompletedTask:
            self.methods.append(method)
            result = '{"root":{"nodeId":1}}' if method == "DOM.getDocument" else "{}"
            return CompletedTask(result)

        def ExecuteScriptAsync(self, source: str) -> CompletedTask:
            self.scripts.append(source)
            return CompletedTask("null")

    class Native:
        @staticmethod
        def BeginInvoke(callback: Callable[[], None]) -> None:
            callback()

    core = Core()
    component_gallery_child._schedule_pseudo_states(
        Native(),
        core,
        [],
        component_gallery_child._Recorder(tmp_path / "result.json", "light"),
        [],
    )

    assert core.methods == ["DOM.enable", "CSS.enable", "DOM.getDocument"]
    assert core.scripts == ["globalThis.__namiGalleryPseudoReady = true;"]


@pytest.mark.headed
def test_sh_g_11_component_gallery_uses_installed_tokens_and_non_color_cues(
    component_gallery_evidence: _GalleryEvidence,
) -> None:
    light = component_gallery_evidence.result("light")["report"]
    dark = component_gallery_evidence.result("dark")["report"]
    forced = component_gallery_evidence.result("forced")["report"]
    _assert_installed_assets(component_gallery_evidence)

    assert light["media"] == {
        "dark": False,
        "forced": False,
        "reduced": False,
    }
    assert dark["media"] == {
        "dark": True,
        "forced": False,
        "reduced": False,
    }
    assert forced["media"] == {
        "dark": True,
        "forced": True,
        "reduced": False,
    }
    for report in (light, dark, forced):
        _assert_complete_gallery_matrix(report)
        _assert_icon_registry_evidence(
            report["icons"],
            forced=report["media"]["forced"],
        )
        assert all(
            row["aliases_consumed"] is True
            for row in (*report["statuses"], *report["operations"])
        )
    for report in (light, dark):
        for row in (*report["statuses"], *report["operations"]):
            threshold = 3.0 if row["large_text"] else 4.5
            assert _contrast(row["foreground"], row["background"]) >= threshold
            assert _contrast(row["indicator"], row["background"]) >= 3.0
            assert _contrast(row["shape_color"], row["background"]) >= 3.0
        for control in report["controls"]:
            if (
                control["control"] in _TEXT_CONTROL_KEYS
                and control["state"] != "disabled"
            ):
                assert _contrast(control["foreground"], control["background"]) >= 4.5
            if (
                control["control"] in _BOUNDARY_CONTROL_KEYS
                and control["state"] != "disabled"
            ):
                assert _control_boundary_contrast(control) >= 3.0
            if control["state"] == "focused":
                assert (
                    control["box_shadow"] != "none"
                    or control["outline_width"] not in {"0px", "0"}
                )
                assert (
                    _contrast(
                        _rendered_focus_color(control),
                        control["surrounding"],
                    )
                    >= 3.0
                )
    system_colors = set(forced["icons"]["system_colors"].values())
    assert system_colors
    for row in (*forced["statuses"], *forced["operations"]):
        assert row["foreground"] in system_colors
        assert row["background"] in system_colors
        assert row["indicator"] in system_colors
        assert row["icon_color"] == row["foreground"]
        assert _contrast(row["icon_color"], row["background"]) >= 3.0
        assert row["shape_color"] in system_colors
        assert _contrast(row["shape_color"], row["background"]) >= 3.0
    for control in forced["controls"]:
        if control["state"] == "focused":
            assert control["outline_width"] not in {"0px", "0"}
            assert control["outline_style"] != "none"
            assert control["outline_color"] in system_colors
            assert (
                _contrast(control["outline_color"], control["surrounding"])
                >= 3.0
            )
    for sample in forced["icons"]["state_samples"]:
        assert sample["icon_color"] in system_colors
        assert _contrast(sample["icon_color"], sample["control_background"]) >= 3.0


@pytest.mark.headed
def test_sh_g_13_component_gallery_honors_reduced_motion(
    component_gallery_evidence: _GalleryEvidence,
) -> None:
    light = component_gallery_evidence.result("light")["report"]
    reduced = component_gallery_evidence.result("reduced")["report"]

    assert light["media"]["reduced"] is False
    assert reduced["media"]["reduced"] is True
    assert light["motion"]["nonessential_max_ms"] > 1.0
    assert light["motion"]["indeterminate_iteration_count"] == "infinite"
    assert reduced["motion"]["nonessential_max_ms"] <= 1.0
    assert reduced["motion"]["indeterminate_iteration_count"] == "1"
    reduced_controls = {
        (row["control"], row["state"]): row
        for row in reduced["controls"]
    }
    light_controls = {
        (row["control"], row["state"]): row
        for row in light["controls"]
    }
    assert all(
        _maximum_duration_ms(
            light_controls[("dialog", state)]["transition_duration"]
        ) > 1.0
        for state in _CONTROL_STATES
    )
    assert all(
        light_controls[("dialog", state)]["animation_name"]
        == "nami-dialog-enter"
        for state in _CONTROL_STATES
    )
    assert all(
        reduced_controls[("progress_indeterminate", state)]["animation_name"]
        == "none"
        for state in _CONTROL_STATES
    )
    assert all(
        reduced_controls[("dialog", state)]["animation_name"] == "none"
        for state in _CONTROL_STATES
    )


def _maximum_duration_ms(value: str) -> float:
    maximum = 0.0
    for raw in value.split(","):
        part = raw.strip()
        amount = float(part.removesuffix("ms").removesuffix("s"))
        maximum = max(maximum, amount if part.endswith("ms") else amount * 1000)
    return maximum


@pytest.mark.headed
def test_sh_g_14_component_gallery_uses_closed_local_icon_registry(
    component_gallery_evidence: _GalleryEvidence,
) -> None:
    results = [
        component_gallery_evidence.result(mode)
        for mode in _MODES
    ]
    _assert_installed_assets(component_gallery_evidence)
    for result in results:
        report = result["report"]
        icons = report["icons"]
        _assert_icon_registry_evidence(
            icons,
            forced=report["media"]["forced"],
        )
        assert {sample["state"] for sample in icons["state_samples"]} == (
            _CONTROL_STATES
        )


def _run_gallery_mode(
    installed: HeadedInstalledWheel,
    *,
    mode: str,
    root: Path,
    scenario: Path,
) -> dict[str, object]:
    deadline = scenario_deadline(75.0)
    root.mkdir(parents=True)
    output = require_absolute_local_test_root(root / "result.json")
    data_root = require_absolute_local_test_root(root / "data")
    token = uuid4().hex
    title = f"NamiSync Gallery {mode} {token}"
    process = start_headed_process(
        (
            installed.python,
            _CHILD,
            "--mode",
            mode,
            "--data-dir",
            data_root,
            "--mutex",
            rf"Local\NamiSync.Gallery.{mode}.{token}",
            "--title",
            title,
            "--output",
            output,
            "--scenario",
            scenario,
        ),
        cwd=installed.root,
        environment=clean_child_environment(),
        deadline=deadline,
    )
    try:
        window = wait_for_window(process, title, deadline=deadline)
        wait_for_path(output, deadline=deadline)
        interim = json.loads(read_text(output, deadline=deadline))
        phase = interim.get("report", {}).get("phase")
        if phase != "complete":
            failure = interim.get("report", {}).get("failure")
            failure = failure or interim.get("pseudo_state_failed")
            failure = failure or interim.get("media_emulation_failed")
            failure = failure or interim.get("native_script_failure")
            raise AssertionError(f"component gallery failed: {failure!r}")
        assert interim["report"]["mode"] == mode
        wait_for_accessible_text(
            window,
            f"Gallery {mode} complete",
            python=installed.python,
            deadline=deadline,
        )
        close_window(window)
        completed = wait_for_process(process, deadline=deadline)
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert completed.stdout == ""
        assert completed.stderr == ""
    finally:
        if process.poll() is None:
            terminate_process_tree(process, deadline=deadline)
    result = json.loads(read_text(output, deadline=deadline))
    assert result["exit_code"] == 0
    assert result["startup_errors"] == []
    assert result["runtime"]["versions"] == {
        "namisync": VERSION,
        "pywebview": "6.2.1",
        "pythonnet": "3.1.0",
    }
    assert Path(result["runtime"]["executable"]).resolve().is_relative_to(
        installed.root.resolve()
    )
    assert Path(result["runtime"]["namisync_file"]).resolve().is_relative_to(
        installed.root.resolve()
    )
    assert result["dispatcher_type"] == (
        "namisync.interfaces.web.bridge.BridgeDispatcher"
    )
    assert result["production_command_names"] == [
        "close_task",
        "next_events",
        "pick_folder",
        "release_terminal_session",
        "start_plan",
    ]
    assert result["combined_mapping_type"] == "mappingproxy"
    assert result["combined_command_names"] == sorted(
        [*result["production_command_names"], "test_report"]
    )
    trusted = urlsplit(result["trusted_url"])
    assert trusted.scheme == "http"
    assert trusted.hostname in {"127.0.0.1", "localhost"}
    assert trusted.port not in {None, 80}
    assert trusted.path.endswith("/index.html")
    assert result["pseudo_state_count"] == len(_CONTROL_KEYS) * 3
    return result


def _assert_installed_assets(evidence: _GalleryEvidence) -> None:
    wheel = evidence.installed.wheel
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert not any("component_gallery" in name for name in names)
        assert not any(name.rsplit("/", 1)[-1] == "gallery.js" for name in names)
        assert all(
            _TEST_ONLY_MARKER not in archive.read(name)
            for name in names
            if not name.endswith("/")
        )
        for mode, result in evidence.results.items():
            del mode
            for name in _ASSET_NAMES:
                record = result["installed_assets"][name]
                content = base64.b64decode(record["bytes_b64"], validate=True)
                member = f"namisync/interfaces/web/assets/{name}"
                assert member in names
                assert content == archive.read(member)
                assert hashlib.sha256(content).hexdigest() == record["sha256"]
                assert Path(record["path"]).resolve().is_relative_to(
                    evidence.installed.root.resolve()
                )
    first = evidence.results["light"]["installed_assets"]
    for result in evidence.results.values():
        for name in _ASSET_NAMES:
            assert result["installed_assets"][name]["bytes_b64"] == first[name][
                "bytes_b64"
            ]
    index = base64.b64decode(first["index.html"]["bytes_b64"]).decode("utf-8")
    assert 'href="/tokens.css"' in index
    assert 'href="/components.css"' in index
    assert index.index('href="/tokens.css"') < index.index(
        'href="/components.css"'
    )


def _assert_complete_gallery_matrix(report: dict[str, object]) -> None:
    statuses = report["statuses"]
    operations = report["operations"]
    controls = report["controls"]
    assert {row["key"] for row in statuses} == _STATUS_KEYS
    assert {row["key"] for row in operations} == _OPERATION_KEYS
    assert {(row["control"], row["state"]) for row in controls} == {
        (control, state)
        for control in _CONTROL_KEYS
        for state in _CONTROL_STATES
    }
    assert len(statuses) == len(_STATUS_KEYS)
    assert len(operations) == len(_OPERATION_KEYS)
    assert len(controls) == len(_CONTROL_KEYS) * len(_CONTROL_STATES)
    for row in (*statuses, *operations):
        assert row["text"]
        assert row["icon"]
        assert row["shape"]
        assert row["cue"]
        assert row["visible_text"]
        assert row["text"] in row["visible_text"]
        assert row["cue"] in row["visible_text"]
        assert row["shape_content"] not in {"", "none", "normal"}
        assert row["shape_display"] != "none"
        assert row["shape_visibility"] == "visible"
        assert float(row["shape_opacity"]) > 0
        assert row["shape_width"] > 0
        assert row["shape_height"] > 0
    tri_state = report["control_contract"]["tri_state"]
    assert tri_state["aria_checked"] == "mixed"
    assert tri_state["indeterminate"] is True
    assert tri_state["cue_content"] not in {"", "none", "normal"}
    assert report["control_contract"]["dialog_exit"] == {
        "opened": True,
        "retained_while_closing": True,
        "faded": True,
        "closed": True,
    }
    for control in _CONTROL_KEYS:
        rows = {
            row["state"]: row
            for row in controls
            if row["control"] == control
        }
        rest = _control_signature(rows["rest"])
        for state in _CONTROL_STATES - {"rest"}:
            assert rows[state]["label"]
            assert _control_signature(rows[state]) != rest


def _control_signature(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        row[name]
        for name in (
            "foreground",
            "background",
            "border",
            "border_width",
            "border_style",
            "root_border",
            "root_border_width",
            "root_border_style",
            "root_background",
            "boundary",
            "outline_width",
            "outline_color",
            "outline_style",
            "box_shadow",
            "opacity",
            "transform",
        )
    )


def _control_boundary_contrast(row: dict[str, str]) -> float:
    painted = [
        row[color]
        for color, width, style in (
            ("border", "border_width", "border_style"),
            (
                "root_border",
                "root_border_width",
                "root_border_style",
            ),
        )
        if _painted_border(row[width], row[style])
        and _opaque_color(row[color])
    ]
    assert painted, f"no painted control boundary: {row!r}"
    return max(_contrast(color, row["surrounding"]) for color in painted)


def _painted_border(width: str, style: str) -> bool:
    widths = _expand_css_sides(width)
    styles = _expand_css_sides(style)
    return any(
        (float(side_width.removesuffix("px")) > 0)
        and side_style not in {"none", "hidden"}
        for side_width, side_style in zip(widths, styles, strict=True)
    )


def _expand_css_sides(value: str) -> tuple[str, str, str, str]:
    parts = value.split()
    assert 1 <= len(parts) <= 4, f"invalid computed border value: {value!r}"
    if len(parts) == 1:
        return (parts[0],) * 4
    if len(parts) == 2:
        return (parts[0], parts[1], parts[0], parts[1])
    if len(parts) == 3:
        return (parts[0], parts[1], parts[2], parts[1])
    return tuple(parts)


def _rendered_focus_color(row: dict[str, str]) -> str:
    if (
        row["outline_style"] != "none"
        and row["outline_width"] not in {"0", "0px"}
    ):
        return row["outline_color"]
    match = _RGB.search(row["box_shadow"])
    assert match is not None, f"focused control has no rendered ring: {row!r}"
    geometry = tuple(
        float(value)
        for value in re.findall(
            r"(-?[0-9]+(?:\.[0-9]+)?)px",
            row["box_shadow"][match.end() :],
        )
    )
    assert geometry and any(
        not math.isclose(value, 0.0) for value in geometry
    ), f"focused control has zero-size rendered ring: {row!r}"
    return match.group(0)


def _opaque_color(value: str) -> bool:
    match = _RGB.fullmatch(value)
    if match is None:
        return False
    return match.group(4) is None or math.isclose(float(match.group(4)), 1.0)


def _assert_icon_registry_evidence(
    icons: dict[str, object],
    *,
    forced: bool,
) -> None:
    assert icons["registry_frozen"] is True
    expected_names = {
        "checkmark-circle",
        "dismiss-circle",
        "warning",
        "info",
    }
    assert set(icons["registry_names"]) == expected_names
    assert len(icons["registry_names"]) == len(expected_names)
    assert icons["all_registry_created"] is True
    assert icons["all_current_color"] is True
    assert icons["all_mask_images"] is True
    assert icons["unexpected_svg_count"] == 0
    assert icons["unexpected_path_count"] == 0
    assert icons["sizes"] == [
        {"size": "sm", "width": "16px", "height": "16px"},
        {"size": "md", "width": "20px", "height": "20px"},
        {"size": "lg", "width": "24px", "height": "24px"},
    ]
    assert {sample["state"] for sample in icons["state_samples"]} == (
        _CONTROL_STATES
    )
    if forced:
        samples = {
            sample["state"]: sample for sample in icons["state_samples"]
        }
        assert all(
            samples[state]["inherits"] is True
            for state in {"rest", "disabled", "focused"}
        )
        for state in {"hover", "pressed"}:
            assert (
                samples[state]["icon_color"]
                == icons["system_colors"]["HighlightText"]
            )
            assert (
                samples[state]["control_background"]
                == icons["system_colors"]["Highlight"]
            )
    else:
        assert all(
            sample["inherits"] is True
            for sample in icons["state_samples"]
        )
    # Inactive controls are exempt from non-text contrast; their currentColor
    # inheritance and fixed local mask remain required above.
    assert all(
        _contrast(sample["icon_color"], sample["control_background"]) >= 3.0
        for sample in icons["state_samples"]
        if sample["state"] != "disabled"
    )
    expected_files = {
        "checkmark-circle": "checkmark_circle_20_regular.svg",
        "dismiss-circle": "dismiss_circle_20_regular.svg",
        "warning": "warning_20_regular.svg",
        "info": "info_20_regular.svg",
    }
    assert set(icons["mask_images"]) == set(expected_files)
    for name, filename in expected_files.items():
        match = re.fullmatch(
            r'''url\(["']?([^"')]+)["']?\)''',
            icons["mask_images"][name],
        )
        assert match is not None
        assert match.group(1).endswith(f"/{filename}")


def _declared_keys(script: str, name: str) -> set[str]:
    match = re.search(
        rf"const {re.escape(name)} = Object\.freeze\(\[(.*?)\]\);",
        script,
        re.DOTALL,
    )
    assert match is not None, f"{name} declaration is missing"
    return set(re.findall(r'key:\s*"([a-z0-9_]+)"', match.group(1)))


def _contrast(first: str, second: str) -> float:
    bright = _luminance(_rgb(first))
    dark = _luminance(_rgb(second))
    high, low = max(bright, dark), min(bright, dark)
    return (high + 0.05) / (low + 0.05)


def _rgb(value: str) -> tuple[float, float, float]:
    match = _RGB.fullmatch(value)
    assert match is not None, f"computed color is not opaque RGB: {value!r}"
    alpha = 1.0 if match.group(4) is None else float(match.group(4))
    assert math.isclose(alpha, 1.0)
    return tuple(float(match.group(index)) / 255.0 for index in range(1, 4))


def _luminance(value: tuple[float, float, float]) -> float:
    def linear(channel: float) -> float:
        if channel <= 0.04045:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in value)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue
