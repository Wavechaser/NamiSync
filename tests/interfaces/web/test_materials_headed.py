"""Real installed-wheel headed evidence for SH-G-12 native materials."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest

import _materials_gate_child as materials_gate_child
from conftest import HeadedInstalledWheel
from namisync.version import VERSION
from _headed_native import (
    clean_child_environment,
    close_window,
    read_bytes,
    read_text,
    require_absolute_local_test_root,
    scenario_deadline,
    start_headed_process,
    terminate_process_tree,
    wait_for_accessible_text,
    wait_for_process,
    wait_for_window,
)


_CHILD = Path(__file__).with_name("_materials_gate_child.py")
_SCENARIOS = ("capable", "controller-failure", "main-window-failure")
_DWMSBT_NONE = 1
_DWMSBT_MAINWINDOW = 2
_DWMWA_SYSTEMBACKDROP_TYPE = 38
_REQUIRED_FRAME = ("caption", "thickframe", "sysmenu")
_RGB = re.compile(
    r"rgba?\(\s*([0-9.]+)(?:\s*,|\s+)\s*([0-9.]+)"
    r"(?:\s*,|\s+)\s*([0-9.]+)(?:\s*(?:,|/)\s*([0-9.]+))?\s*\)"
)


@dataclass(frozen=True, slots=True)
class _MaterialsGate:
    installed: HeadedInstalledWheel
    root: Path
    results: dict[str, dict[str, object]]

    def result(self, scenario: str) -> dict[str, object]:
        if scenario not in _SCENARIOS:
            raise ValueError("unknown materials scenario")
        if scenario not in self.results:
            self.results[scenario] = _run_materials_scenario(
                self.installed,
                scenario=scenario,
                root=require_absolute_local_test_root(self.root / scenario),
            )
        return self.results[scenario]


@pytest.fixture(scope="session")
def materials_gate_evidence(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path_factory: pytest.TempPathFactory,
) -> _MaterialsGate:
    root = require_absolute_local_test_root(
        tmp_path_factory.mktemp("materials-gate")
    )
    return _MaterialsGate(headed_installed_wheel, root, {})


def test_materials_gate_child_is_test_owned_and_preserves_production_stack() -> None:
    source = _CHILD.read_text(encoding="utf-8")
    launch_source = inspect.getsource(_run_materials_scenario)
    fixture_source = inspect.getsource(materials_gate_evidence)
    gate_source = inspect.getsource(_MaterialsGate.result)
    tree = ast.parse(source)
    patched = {
        node.args[1].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "object"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    }

    assert "host.run_desktop(" in source
    assert "AppPaths.from_root(arguments.data_dir)" in source
    assert "DesktopInstanceIdentity(arguments.mutex, arguments.title)" in source
    assert "CallDevToolsProtocolMethodAsync" in source
    assert "Page.captureScreenshot" in source
    assert "evaluate_js" not in source
    assert "set_foreground" not in source.casefold()
    assert "SetForegroundWindow" not in source
    assert "create_window" not in patched
    assert "_configure_window_security" not in patched
    assert "_bridge_dispatcher" not in patched
    assert patched == {
        "read",
        "_set_controller_background",
        "_set_client_glass",
        "_set_dwm_attribute",
        "_configure_window_appearance",
    }
    assert launch_source.count("require_absolute_local_test_root(") == 3
    assert fixture_source.count("require_absolute_local_test_root(") == 1
    assert gate_source.count("require_absolute_local_test_root(") == 1
    assert "_run_materials_scenario(" not in fixture_source
    assert "scenario_deadline(75.0)" in launch_source
    assert "start_headed_process(" in launch_source
    assert "cwd=installed.root" in launch_source
    assert "uuid4().hex" in launch_source
    assert "close_window(window)" in launch_source
    assert "terminate_process_tree(process, deadline=deadline)" in launch_source


def test_materials_gate_skips_unsupported_build_before_scenario_launch() -> None:
    for test in (
        test_sh_g_12_capable_window_uses_real_mica_and_transparent_seam,
        test_sh_g_12_controller_failure_lands_opaque_before_glass,
        test_sh_g_12_mainwindow_failure_unwinds_glass_and_lands_opaque,
    ):
        source = inspect.getsource(test)
        assert source.index("_require_material_build()") < source.index(
            ".result("
        )


def test_materials_gate_build_guard_refuses_pre_material_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "getwindowsversion",
        lambda: type("Version", (), {"build": 22000})(),
    )

    with pytest.raises(pytest.skip.Exception, match="predates"):
        _require_material_build()


def test_materials_gate_faults_are_exact_and_delegate_other_native_calls() -> None:
    source = inspect.getsource(materials_gate_child)

    assert set(materials_gate_child._SCENARIOS) == set(_SCENARIOS)
    assert 'scenario == "controller-failure" and transparent' in source
    assert 'scenario == "main-window-failure"' in source
    assert "attribute == appearance._DWMWA_SYSTEMBACKDROP_TYPE" in source
    assert "value == appearance._DWMSBT_MAINWINDOW" in source
    assert "original_controller(" in source
    assert "original_glass(native, native_window, enabled=enabled)" in source
    assert "original_dwm(native, native_window, attribute, value)" in source
    assert "original_configure(window, *args, **kwargs)" in source
    assert 'scenario == "capable"' in source
    assert "selected = actual" in source


def test_materials_gate_report_and_page_probe_are_bounded_and_sanitized() -> None:
    recorder = materials_gate_child._Recorder(Path("ignored.json"), "capable")
    recorder._write_locked = lambda: None
    recorder.failure("private-path", RuntimeError("C:\\private\\secret"))

    assert recorder._data["failure"] == {
        "stage": "child",
        "type": "RuntimeError",
    }
    assert "private" not in json.dumps(recorder._data).casefold()
    assert "for (let attempt = 0; attempt < 100; attempt += 1)" in (
        materials_gate_child._PAGE_PROBE
    )
    assert "window.setTimeout(resolve, 50)" in materials_gate_child._PAGE_PROBE
    assert "document.documentElement" in materials_gate_child._PAGE_PROBE
    assert 'document.querySelector("#app")' in materials_gate_child._PAGE_PROBE
    assert 'typeof window.pywebview?.api?.dispatch === "function"' in (
        materials_gate_child._PAGE_PROBE
    )
    assert 'command: "materials_probe"' in materials_gate_child._PAGE_PROBE
    assert 'error?.code !== "unknown_command"' in materials_gate_child._PAGE_PROBE
    observer_source = inspect.getsource(
        materials_gate_child._install_native_boundary_observers
    )
    assert "def begin_page_probe_on_ui()" in observer_source
    assert "native_window.BeginInvoke(action)" in observer_source
    assert 'observations["native_window"] = native_window' in observer_source
    assert "recorder.write()" not in observer_source


def test_materials_gate_page_report_rejects_malformed_protocol_values() -> None:
    class Task:
        IsFaulted = False
        IsCanceled = False
        Result = '{}'

    with pytest.raises(TypeError, match="native CDP result is invalid"):
        materials_gate_child._protocol_value(Task())

    Task.Result = json.dumps(
        {"result": {"type": "object", "value": {"material": "mica"}}}
    )
    assert materials_gate_child._protocol_value(Task()) == {"material": "mica"}

    with pytest.raises(AssertionError):
        _assert_fixed_report_schema({})


def test_materials_gate_renderer_alpha_matches_the_material_layer() -> None:
    transparent = {"a": 0, "r": 0, "g": 0, "b": 0}
    opaque = {"a": 255, "r": 0, "g": 0, "b": 0}
    card = {"a": 255, "r": 0, "g": 0, "b": 0}

    def result(material: str, gutter: dict[str, int]) -> dict[str, object]:
        return {
            "page": {
                "material": material,
                "card_background": "rgb(18, 18, 18)",
            },
            "screenshot": {
                "samples": {
                    "width": 640,
                    "height": 480,
                    "scale_x": 1.0,
                    "scale_y": 1.0,
                    "gutter_pixels": [gutter, gutter, gutter],
                    "card_pixel": card,
                }
            },
        }

    _assert_renderer_surfaces(result("mica", transparent))
    _assert_renderer_surfaces(result("opaque", opaque))
    with pytest.raises(AssertionError):
        _assert_renderer_surfaces(result("mica", opaque))
    with pytest.raises(AssertionError):
        _assert_renderer_surfaces(result("opaque", transparent))


@pytest.mark.headed
def test_sh_g_12_capable_window_uses_real_mica_and_transparent_seam(
    materials_gate_evidence: _MaterialsGate,
) -> None:
    _require_material_build()
    result = materials_gate_evidence.result("capable")
    _assert_installed_sources(materials_gate_evidence.installed, result)
    actual = result["actual_system"]
    if actual["high_contrast"] is True:
        pytest.skip("Windows high contrast intentionally forces opaque system colors")

    assert result["selected_system"] == actual
    assert result["page"]["material"] == "mica"
    assert result["native_final"]["controller_background"]["a"] == 0
    assert result["native_final"]["form_background"] == {
        "a": 255,
        "r": 0,
        "g": 0,
        "b": 0,
    }
    assert result["native_final"]["dwm_backdrop"] == {
        "hresult": 0,
        "value": _DWMSBT_MAINWINDOW,
    }
    assert result["native_final"]["dwm_dark_mode"] == {
        "hresult": 0,
        "value": int(actual["dark"]),
    }
    assert _transparent_css(result["page"]["root_background"])
    assert _transparent_css(result["page"]["body_background"])
    assert result["page"]["window_base"] == "transparent"
    _assert_native_operation_sequence(
        result,
        [
            ("controller_background", True),
            ("client_glass", True),
            ("dwm_attribute", 20, int(actual["dark"])),
            ("dwm_attribute", 38, _DWMSBT_MAINWINDOW),
        ],
    )
    _assert_common_health(result)
    _assert_renderer_surfaces(result)


@pytest.mark.headed
def test_sh_g_12_controller_failure_lands_opaque_before_glass(
    materials_gate_evidence: _MaterialsGate,
) -> None:
    _require_material_build()
    result = materials_gate_evidence.result("controller-failure")
    _assert_installed_sources(materials_gate_evidence.installed, result)
    operations = result["native_operations"]

    assert operations[0] == {
        "operation": "controller_background",
        "transparent": True,
        "injected_failure": True,
        "result": False,
    }
    assert not any(
        row["operation"] == "client_glass" and row["enabled"] is True
        for row in operations
    )
    _assert_native_operation_sequence(
        result,
        [
            ("controller_background", True),
            ("dwm_attribute", 38, _DWMSBT_NONE),
            ("client_glass", False),
            ("dwm_attribute", 20, int(result["selected_system"]["dark"])),
            ("controller_background", False),
        ],
        allow_one_injected=True,
    )
    assert not any(
        row["operation"] == "dwm_attribute"
        and row["value"] == _DWMSBT_MAINWINDOW
        for row in operations
    )
    _assert_opaque_landed(result)
    _assert_common_health(result)
    _assert_renderer_surfaces(result)


@pytest.mark.headed
def test_sh_g_12_mainwindow_failure_unwinds_glass_and_lands_opaque(
    materials_gate_evidence: _MaterialsGate,
) -> None:
    _require_material_build()
    result = materials_gate_evidence.result("main-window-failure")
    _assert_installed_sources(materials_gate_evidence.installed, result)
    operations = result["native_operations"]

    assert operations[0]["operation"] == "controller_background"
    assert operations[0]["transparent"] is True
    assert operations[0]["result"] is True
    assert [
        (row["operation"], row.get("enabled"))
        for row in operations
        if row["operation"] == "client_glass"
    ][:2] == [("client_glass", True), ("client_glass", False)]
    injected = [row for row in operations if row["injected_failure"]]
    assert injected
    assert all(
        row
        == {
            "operation": "dwm_attribute",
            "attribute": _DWMWA_SYSTEMBACKDROP_TYPE,
            "value": _DWMSBT_MAINWINDOW,
            "injected_failure": True,
            "result": False,
        }
        for row in injected
    )
    assert any(
        row["operation"] == "dwm_attribute"
        and row["attribute"] == _DWMWA_SYSTEMBACKDROP_TYPE
        and row["value"] == _DWMSBT_NONE
        and row["result"] is True
        for row in operations
    )
    _assert_native_operation_sequence(
        result,
        [
            ("controller_background", True),
            ("client_glass", True),
            ("dwm_attribute", 20, int(result["selected_system"]["dark"])),
            ("dwm_attribute", 38, _DWMSBT_MAINWINDOW),
            ("dwm_attribute", 38, _DWMSBT_NONE),
            ("client_glass", False),
            ("dwm_attribute", 20, int(result["selected_system"]["dark"])),
            ("controller_background", False),
        ],
        allow_one_injected=True,
    )
    _assert_opaque_landed(result)
    _assert_common_health(result)
    _assert_renderer_surfaces(result)


def _require_material_build() -> None:
    try:
        build = int(sys.getwindowsversion().build)
    except (AttributeError, TypeError, ValueError):
        pytest.skip("actual Windows build is unavailable")
    if build < 22621:
        pytest.skip("Windows build predates documented Mica support")


def _run_materials_scenario(
    installed: HeadedInstalledWheel,
    *,
    scenario: str,
    root: Path,
) -> dict[str, object]:
    deadline = scenario_deadline(75.0)
    root.mkdir(parents=True)
    data_root = require_absolute_local_test_root(root / "data")
    output = require_absolute_local_test_root(root / "result.json")
    screenshot = require_absolute_local_test_root(root / f"{scenario}.png")
    token = uuid4().hex
    title = f"NamiSync Materials {scenario} {token}"
    process = start_headed_process(
        (
            installed.python,
            _CHILD,
            "--scenario",
            scenario,
            "--data-dir",
            data_root,
            "--mutex",
            rf"Local\NamiSync.Materials.{scenario}.{token}",
            "--title",
            title,
            "--output",
            output,
            "--screenshot",
            screenshot,
        ),
        cwd=installed.root,
        environment=clean_child_environment(),
        deadline=deadline,
    )
    try:
        window = wait_for_window(process, title, deadline=deadline)
        while not output.exists():
            deadline.remaining()
            if process.poll() is not None:
                completed = wait_for_process(process, deadline=deadline)
                raise AssertionError(
                    "materials child exited before completing its report; "
                    f"returncode={completed.returncode}"
                )
            time.sleep(0.025)
        interim = json.loads(read_text(output, deadline=deadline))
        if interim.get("phase") == "failure":
            raise AssertionError(
                f"materials gate failed: {interim.get('failure')!r}"
            )
        assert interim.get("phase") == "complete", interim
        wait_for_accessible_text(
            window,
            f"Materials {scenario} complete",
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
    _assert_fixed_report_schema(result)
    assert result["phase"] == "complete"
    assert result["exit_code"] == 0
    assert result["startup_errors"] == []
    assert result["scenario"] == scenario
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
    assert Path(result["screenshot"]["path"]).resolve() == screenshot.resolve()
    content = read_bytes(screenshot, deadline=deadline)
    assert content.startswith(b"\x89PNG\r\n\x1a\n")
    assert hashlib.sha256(content).hexdigest() == result["screenshot"]["sha256"]
    assert len(content) == result["screenshot"]["size"]
    return result


def _assert_installed_sources(
    installed: HeadedInstalledWheel,
    result: dict[str, object],
) -> None:
    members = {
        "appearance.py": "namisync/interfaces/web/appearance.py",
        "host.py": "namisync/interfaces/web/host.py",
    }
    with zipfile.ZipFile(installed.wheel) as archive:
        for name, member in members.items():
            content = archive.read(member)
            evidence = result["runtime"]["sources"][name]
            assert hashlib.sha256(content).hexdigest() == evidence["sha256"]
            assert len(content) == evidence["size"]
            assert Path(evidence["path"]).resolve().is_relative_to(
                installed.root.resolve()
            )
            assert Path(evidence["path"]).read_bytes() == content

        host_tree = ast.parse(archive.read(members["host.py"]).decode("utf-8"))
    calls = [
        node
        for node in ast.walk(host_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "create_window"
    ]
    assert len(calls) == 1
    keywords = {keyword.arg: keyword.value for keyword in calls[0].keywords}
    assert isinstance(keywords["transparent"], ast.Constant)
    assert keywords["transparent"].value is False
    background = keywords["background_color"]
    assert isinstance(background, ast.Call)
    assert isinstance(background.func, ast.Name)
    assert background.func.id == "_opaque_window_background"


def _assert_common_health(result: dict[str, object]) -> None:
    assert result["load_health"]["ui_thread"] is True
    assert result["load_health"]["source"].startswith("http://127.0.0.1:")
    assert result["load_health"]["source"].endswith("/index.html")
    assert result["page"]["ready_state"] == "complete"
    assert result["page"]["dispatch_type"] == "function"
    assert result["page"]["dispatch_refusal"] == "unknown_command"
    assert result["page"]["status"] == (
        f"Materials {result['scenario']} complete"
    )
    assert result["native_final"]["ui_thread"] is True
    assert all(result["native_final"]["window_style"][name] for name in _REQUIRED_FRAME)


def _assert_fixed_report_schema(result: dict[str, object]) -> None:
    assert set(result) == {
        "schema_version",
        "scenario",
        "phase",
        "startup_errors",
        "native_operations",
        "runtime",
        "actual_system",
        "selected_system",
        "opaque_system_color",
        "native_after_apply",
        "load_health",
        "page",
        "native_final",
        "screenshot",
        "exit_code",
    }
    assert result["schema_version"] == 1
    assert result["scenario"] in _SCENARIOS
    assert result["phase"] == "complete"
    assert type(result["startup_errors"]) is list
    assert type(result["native_operations"]) is list
    assert set(result["runtime"]) == {
        "executable",
        "namisync_file",
        "versions",
        "sources",
    }
    assert set(result["runtime"]["versions"]) == {
        "namisync",
        "pywebview",
        "pythonnet",
    }
    assert set(result["runtime"]["sources"]) == {"appearance.py", "host.py"}
    for evidence in result["runtime"]["sources"].values():
        assert set(evidence) == {"path", "sha256", "size"}
    for name in ("actual_system", "selected_system"):
        assert set(result[name]) == {
            "dark",
            "high_contrast",
            "accent",
            "build",
            "supports_mica",
        }
    for name in ("native_after_apply", "native_final"):
        _assert_native_snapshot_schema(result[name])
    assert set(result["load_health"]) == {"ui_thread", "source"}
    assert set(result["page"]) == {
        "ready_state",
        "dispatch_type",
        "dispatch_refusal",
        "material",
        "theme",
        "root_background",
        "body_background",
        "window_base",
        "card_background",
        "card_rect",
        "card_sample",
        "viewport",
        "gutter_points",
        "status",
    }
    assert set(result["page"]["card_rect"]) == {
        "left",
        "top",
        "right",
        "bottom",
    }
    assert set(result["page"]["card_sample"]) == {"x", "y"}
    assert set(result["page"]["viewport"]) == {"width", "height"}
    assert type(result["page"]["gutter_points"]) is list
    assert len(result["page"]["gutter_points"]) == 3
    assert all(set(point) == {"x", "y"} for point in result["page"]["gutter_points"])
    assert set(result["screenshot"]) == {"path", "sha256", "size", "samples"}
    samples = result["screenshot"]["samples"]
    assert set(samples) == {
        "width",
        "height",
        "scale_x",
        "scale_y",
        "gutter_pixels",
        "card_pixel",
    }
    assert type(samples["gutter_pixels"]) is list
    assert len(samples["gutter_pixels"]) == 3
    for color in (*samples["gutter_pixels"], samples["card_pixel"]):
        assert set(color) == {"a", "r", "g", "b"}
    for operation in result["native_operations"]:
        shared = {"operation", "injected_failure", "result"}
        if operation["operation"] == "controller_background":
            assert set(operation) == shared | {"transparent"}
        elif operation["operation"] == "client_glass":
            assert set(operation) == shared | {"enabled"}
        else:
            assert operation["operation"] == "dwm_attribute"
            assert set(operation) == shared | {"attribute", "value"}


def _assert_native_snapshot_schema(value: dict[str, object]) -> None:
    assert set(value) == {
        "ui_thread",
        "controller_background",
        "form_background",
        "dwm_dark_mode",
        "dwm_backdrop",
        "window_style",
    }
    assert set(value["controller_background"]) == {"a", "r", "g", "b"}
    assert set(value["form_background"]) == {"a", "r", "g", "b"}
    assert set(value["dwm_dark_mode"]) == {"hresult", "value"}
    assert set(value["dwm_backdrop"]) == {"hresult", "value"}
    assert set(value["window_style"]) == {
        "value",
        "caption",
        "thickframe",
        "sysmenu",
    }


def _assert_opaque_landed(result: dict[str, object]) -> None:
    assert result["page"]["material"] == "opaque"
    assert result["native_final"]["dwm_backdrop"] == {
        "hresult": 0,
        "value": _DWMSBT_NONE,
    }
    expected = _hex_color(result["opaque_system_color"])
    assert result["native_final"]["controller_background"] == expected
    assert result["native_final"]["form_background"] == expected
    assert result["native_final"]["controller_background"]["a"] == 255
    assert not _transparent_css(result["page"]["body_background"])
    assert result["page"]["window_base"] != "transparent"


def _assert_renderer_surfaces(result: dict[str, object]) -> None:
    """Prove renderer transparency/cards; this is not compositor proof of Mica."""
    samples = result["screenshot"]["samples"]
    gutters = samples["gutter_pixels"]
    card = samples["card_pixel"]
    assert samples["width"] >= 640
    assert samples["height"] >= 480
    assert 0.5 <= samples["scale_x"] <= 4.0
    assert 0.5 <= samples["scale_y"] <= 4.0
    assert len(gutters) == 3
    if result["page"]["material"] == "mica":
        assert all(pixel["a"] == 0 for pixel in gutters)
    else:
        assert all(pixel["a"] == 255 for pixel in gutters)
    assert card["a"] == 255
    assert _opaque_css(result["page"]["card_background"])


def _assert_native_operation_sequence(
    result: dict[str, object],
    expected: list[tuple[object, ...]],
    allow_one_injected: bool = False,
) -> None:
    observed: list[tuple[object, ...]] = []
    rows = result["native_operations"][: len(expected)]
    for row in rows:
        if row["operation"] == "controller_background":
            observed.append((row["operation"], row["transparent"]))
        elif row["operation"] == "client_glass":
            observed.append((row["operation"], row["enabled"]))
        else:
            observed.append((row["operation"], row["attribute"], row["value"]))
        if row["injected_failure"]:
            assert allow_one_injected is True
            allow_one_injected = False
            assert row["result"] is False
        else:
            assert row["result"] is True
    assert observed == expected
    assert allow_one_injected is False


def _transparent_css(value: str) -> bool:
    match = _RGB.fullmatch(value)
    return (
        match is not None
        and match.group(4) is not None
        and float(match.group(4)) == 0
    )


def _opaque_css(value: str) -> bool:
    match = _RGB.fullmatch(value)
    return match is not None and (
        match.group(4) is None or float(match.group(4)) == 1
    )


def _hex_color(value: str) -> dict[str, int]:
    assert re.fullmatch(r"#[0-9A-F]{6}", value)
    return {
        "a": 255,
        "r": int(value[1:3], 16),
        "g": int(value[3:5], 16),
        "b": int(value[5:7], 16),
    }
