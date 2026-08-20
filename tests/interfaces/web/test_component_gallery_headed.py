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
from _headed_evidence import EvidencePaths, EvidenceReader, require_host_final
from conftest import HeadedInstalledWheel
from namisync.interfaces.web.commands import CommandPayloadError
from namisync.interfaces.web.readiness import CommandPhase, ReadinessContext
from namisync.version import VERSION
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


_CHILD = Path(__file__).with_name("_component_gallery_child.py")
_SCENARIO = Path(__file__).parents[2] / "assets" / "component_gallery" / "gallery.js"
_MODES = ("light", "dark", "forced", "reduced")
_ASSET_NAMES = (
    "index.html",
    "tokens.css",
    "components.css",
    "app.css",
    "plan.js",
)
_TEST_ONLY_MARKERS = (
    b"NAMISYNC_TEST_ONLY_COMPONENT_GALLERY_5CE45567A17F4D74",
    b"NAMISYNC_TEST_ONLY_PLAN_ROWS_45C8C53D55D34893",
)
_OPEN_CONTEXT = ReadinessContext(CommandPhase.OPEN, 0)
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
_OPERATION_MAIN_RGB = {
    "copy": "rgb(51, 170, 238)",
    "update": "rgb(51, 221, 153)",
    "move": "rgb(187, 136, 238)",
    "move_update": "rgb(187, 136, 238)",
    "recase": "rgb(51, 170, 238)",
    "mkdir": "rgb(51, 221, 153)",
    "trash": "rgb(255, 221, 68)",
    "delete": "rgb(238, 102, 102)",
}
_STATUS_MAIN_RGB = {
    "error": "rgb(238, 102, 102)",
    "blocked": "rgb(238, 102, 102)",
}
_PLAN_ROW_CASE_KEYS = {
    "plain",
    "copy",
    "update",
    "move",
    "move_update",
    "recase",
    "mkdir",
    "trash",
    "delete",
    "noop",
    "error",
    "unsupported",
}
_CONTROL_KEYS = {
    "button",
    "button_primary",
    "dropdown",
    "tri_state_checkbox",
    "progress_determinate",
    "progress_indeterminate",
    "text_input",
    "toggle",
    "chip",
    "filter_copy",
    "filter_copy_active",
    "filter_delete",
    "filter_delete_active",
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
    "button_primary",
    "dropdown",
    "text_input",
    "chip",
    "filter_copy",
    "filter_copy_active",
    "filter_delete",
    "filter_delete_active",
    "list_row",
    "tree_row",
    "card",
    "dialog",
    "context_menu",
    "segmented_control",
}
_SELECTED_TASK_CARD_KEYS = {
    "task_card_selected",
    "task_card_current",
}
_BOUNDARY_CONTROL_KEYS = {
    "dropdown",
    "tri_state_checkbox",
    "text_input",
    "toggle",
    "card",
    "dialog",
    "context_menu",
} | _SELECTED_TASK_CARD_KEYS
_OUTLINE_FREE_CONTROL_KEYS = {
    "button",
    "button_primary",
    "progress_determinate",
    "progress_indeterminate",
    "chip",
    "filter_copy",
    "filter_copy_active",
    "filter_delete",
    "filter_delete_active",
    "segmented_control",
}
_FORCED_STATIC_ACCENT_CONTROL_KEYS = {
    "button_primary",
    "filter_copy_active",
    "filter_delete_active",
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
    failures: dict[str, BaseException]

    def result(self, mode: str) -> dict[str, object]:
        if mode not in _MODES:
            raise ValueError("unknown component gallery mode")
        if mode in self.failures:
            raise self.failures[mode]
        if mode not in self.results:
            try:
                self.results[mode] = _run_gallery_mode(
                    self.installed,
                    mode=mode,
                    root=require_absolute_local_test_root(self.root / mode),
                    scenario=self.scenario,
                )
            except BaseException as error:
                self.failures[mode] = error
                raise
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
    return _GalleryEvidence(headed_installed_wheel, root, scenario, {}, {})


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
    failure = RuntimeError("gallery failed after creating its root")

    def run(
        observed_installed: HeadedInstalledWheel,
        *,
        mode: str,
        root: Path,
        scenario: Path,
    ) -> dict[str, object]:
        assert observed_installed is installed
        calls.append((mode, root, scenario))
        if mode == "forced":
            root.mkdir()
            raise failure
        return result

    monkeypatch.setitem(globals(), "_run_gallery_mode", run)
    evidence = _GalleryEvidence(installed, tmp_path, scenario, {}, {})

    assert calls == []
    assert evidence.result("dark") is result
    assert evidence.result("dark") is result
    assert calls == [("dark", tmp_path / "dark", scenario)]
    assert "light" not in evidence.results
    with pytest.raises(RuntimeError) as first:
        evidence.result("forced")
    with pytest.raises(RuntimeError) as second:
        evidence.result("forced")
    assert first.value is failure
    assert second.value is failure
    assert calls == [
        ("dark", tmp_path / "dark", scenario),
        ("forced", tmp_path / "forced", scenario),
    ]


def test_installed_asset_assertion_materializes_light_baseline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    installed = HeadedInstalledWheel(
        wheel=tmp_path / "namisync.whl",
        root=tmp_path / "installed",
        python=tmp_path / "python.exe",
        scripts=tmp_path / "Scripts",
    )
    calls: list[str] = []

    def run(*_args, mode: str, **_kwargs) -> dict[str, object]:
        calls.append(mode)
        return {"installed_assets": {}}

    class WheelValidationReached(RuntimeError):
        pass

    def stop_at_wheel(*_args, **_kwargs):
        raise WheelValidationReached

    monkeypatch.setitem(globals(), "_run_gallery_mode", run)
    monkeypatch.setattr(zipfile, "ZipFile", stop_at_wheel)
    evidence = _GalleryEvidence(
        installed,
        tmp_path / "evidence",
        tmp_path / "gallery.js",
        {},
        {},
    )

    with pytest.raises(WheelValidationReached):
        _assert_installed_assets(evidence)

    assert calls == ["light"]


def test_component_gallery_harness_uses_packaged_page_and_test_owned_script() -> None:
    child = _CHILD.read_text(encoding="utf-8")

    assert _SCENARIO.is_relative_to(Path(__file__).parents[2] / "assets")
    assert "importlib.resources.files" in child
    assert all(f'"{name}"' in child for name in _ASSET_NAMES)
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
    script = _SCENARIO.read_text(encoding="utf-8")

    assert "from _startup_test_support import headed_command_extension" in child
    assert "headed_command_extension(" in child
    assert '"test_report": _test_report_spec(' in child
    assert "arguments.mode," in child
    assert "original_configure(" in child
    assert "host.run_desktop(" in child
    assert 'patch.object(host, "_ui_state_owner", create_seeded_ui_state)' in child
    assert 'patch.object(\n                host,\n                "_opaque_window_background"' in child
    assert "ThemeMode.LIGHT" in child
    assert "ThemeMode.DARK" in child
    assert "EvidencePublisher(" in child
    assert 'parser.add_argument("--evidence-dir"' in child
    assert 'parser.add_argument("--output"' not in child
    assert "register" not in child.casefold()
    assert "extra_commands" not in child
    assert "readCosmeticSection" in script
    assert "replaceCosmeticSection" in script
    assert re.search(r"document\.documentElement\.dataset\.theme\s*=(?!=)", script) is None


def test_component_gallery_failure_evidence_is_sanitized(tmp_path: Path) -> None:
    paths = EvidencePaths(tmp_path.resolve())
    recorder = component_gallery_child._Recorder(paths, "light")

    recorder.failure("private-stage", RuntimeError("C:\\private\\sentinel"))

    failure = EvidenceReader(paths).read_failure()
    assert failure == {
        "failure": {
            "stage": "child",
            "type": "RuntimeError",
        }
    }
    assert _sanitized_failure_record(failure) == failure["failure"]
    encoded = json.dumps(failure).casefold()
    assert "private" not in encoded
    assert "sentinel" not in encoded


def test_component_gallery_write_retains_a_post_ready_failure(
    tmp_path: Path,
) -> None:
    paths = EvidencePaths(tmp_path.resolve())
    recorder = component_gallery_child._Recorder(paths, "light")
    recorder.set("report", {"phase": "complete"})
    recorder.write()

    recorder.set(
        "native_script_failure",
        {"stage": "C:\\private\\late", "type": "ScriptExecutionError"},
    )
    recorder.write()
    recorder.set("pseudo_state_failed", "discarded second failure")
    recorder.write()
    recorder.finish(0, host_returned=True)

    reader = EvidenceReader(paths)
    assert reader.read_ready() is not None
    final = reader.read_final()
    assert final == {
        "host_returned": True,
        "exit_code": 0,
        "post_ready_failure": {
            "stage": "page_setup",
            "type": "ScriptExecutionError",
        },
    }
    assert "private" not in json.dumps(final).casefold()
    reader.assert_consistent(require_final=True)


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
    assert "--evidence-dir" in source
    assert "--scenario" in source


@pytest.mark.parametrize(
    ("mode", "theme"),
    [
        ("light", "light"),
        ("dark", "dark"),
        ("forced", "dark"),
        ("reduced", "light"),
    ],
)
def test_component_gallery_seeds_real_cosmetic_owner_before_launch(
    tmp_path: Path,
    mode: str,
    theme: str,
) -> None:
    captured: dict[str, object] = {}

    class Recorder:
        def set(self, name: str, value: object) -> None:
            captured[name] = value

    path = tmp_path / mode / "ui-state.json"
    owner = component_gallery_child._seeded_ui_state_owner(
        path,
        mode,
        Recorder(),  # type: ignore[arg-type]
    )
    try:
        snapshot = owner.read_section("appearance", 1)
        assert snapshot.revision == 1
        assert snapshot.value.theme.value == theme
    finally:
        owner.close()

    assert captured["seeded_cosmetic"] == {
        "section": "appearance",
        "value_version": 1,
        "revision": 1,
        "dirty": True,
        "value": {"theme": theme},
        "disposition": "applied",
    }
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "sections": {
            "appearance": {
                "value_version": 1,
                "value": {"theme": theme},
            }
        },
    }


def test_component_gallery_seed_accepts_a_persisted_same_mode_relaunch(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    class Recorder:
        def set(self, name: str, value: object) -> None:
            captured[name] = value

    path = tmp_path / "light" / "ui-state.json"
    first = component_gallery_child._seeded_ui_state_owner(
        path,
        "light",
        Recorder(),  # type: ignore[arg-type]
    )
    first.close()

    second = component_gallery_child._seeded_ui_state_owner(
        path,
        "light",
        Recorder(),  # type: ignore[arg-type]
    )
    try:
        snapshot = second.read_section("appearance", 1)
        assert snapshot.revision == 0
        assert snapshot.dirty is False
        assert snapshot.value.theme.value == "light"
    finally:
        second.close()

    assert captured["seeded_cosmetic"] == {
        "section": "appearance",
        "value_version": 1,
        "revision": 0,
        "dirty": False,
        "value": {"theme": "light"},
        "disposition": "noop",
    }


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
            "border_width": "1px",
            "border_style": "solid",
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
            "fill_background": "rgb(255, 255, 255)",
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
    cosmetic_snapshot = {
        "section": "appearance",
        "value_version": 1,
        "revision": 1,
        "dirty": True,
        "value": {"theme": "light"},
    }
    changed_snapshot = {
        **cosmetic_snapshot,
        "revision": 2,
        "value": {"theme": "dark"},
    }
    restored_snapshot = {
        **cosmetic_snapshot,
        "revision": 3,
    }
    plan_cases = (
        "plain",
        "mkdir",
        "copy",
        "update",
        "move",
        "move_update",
        "recase",
        "trash",
        "delete",
        "noop",
        "error",
        "unsupported",
    )
    plan_rows = []
    for index, case in enumerate(plan_cases):
        tone = ""
        intent_key = ""
        if case in component_gallery_child._OPERATION_KEYS:
            tone = "operation"
            intent_key = case
        elif case in {"error", "unsupported"}:
            tone = "status"
            intent_key = "error" if case == "error" else "blocked"
        plan_rows.append(
            {
                "case": case,
                "role": "row",
                "cell_roles": ["cell"] * 5,
                "checkbox_label": f"Select {case}",
                "checkbox_checked": False,
                "checkbox_disabled": case in {"error", "unsupported"},
                "depth": 1 if case == "copy" else 0,
                "folder": case == "mkdir",
                "path": f"{case}.example",
                "intent": case,
                "tone": tone,
                "intent_key": intent_key,
                "checksum": (
                    "—" if case in {"mkdir", "error", "unsupported"} else "12345678"
                ),
                "notes": f"{case} notes",
                "background": "rgb(255, 255, 255)",
                "intent_color": "rgb(0, 0, 0)",
                "intent_alias_color": "rgb(0, 0, 0)",
                "cell_backgrounds": ["rgba(0, 0, 0, 0)"] * 5,
                "column_lefts": [float(index) for index in range(5)],
                "path_padding_left": 24.0 if case == "copy" else 8.0,
            }
        )
    report = {
        "phase": "complete",
        "mode": "light",
        "media": {"dark": False, "forced": False, "reduced": False},
        "cosmetic": {
            "initial": dict(cosmetic_snapshot),
            "after_change": dict(changed_snapshot),
            "replacement": {
                **restored_snapshot,
                "disposition": "noop",
            },
            "final": dict(restored_snapshot),
            "page_theme": "light",
            "selector": {
                "initial_value": "light",
                "initial_disabled": False,
                "change_immediate_value": "light",
                "change_immediate_disabled": True,
                "change_settled_value": "dark",
                "change_settled_disabled": False,
                "restore_immediate_value": "dark",
                "restore_immediate_disabled": True,
                "final_value": "light",
                "final_disabled": False,
            },
        },
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
            "segmented": {
                "group_role": "radiogroup",
                "selected_role": "radio",
                "selected_checked": "true",
                "unselected_role": "radio",
                "unselected_checked": "false",
            },
            "file_list": {
                "table_role": "table",
                "header_role": "row",
                "body_role": "rowgroup",
                "gallery_uses_work_area": True,
                "gallery_fills_work_area": True,
                "header_foreground": "rgb(0, 0, 0)",
                "header_background": "rgb(255, 255, 255)",
                "header_texts": [
                    "",
                    "Files / path",
                    "Intended op / status",
                    "Checksum",
                    "Reason / notes",
                ],
                "header_cell_roles": ["columnheader"] * 5,
                "selection_header_label": "Selection",
                "column_count": 5,
                "row_count": len(plan_rows),
                "body_child_count": len(plan_rows),
                "checkbox_count": len(plan_rows),
                "body_ends_at_last_row": True,
                "body_height_matches_rows": True,
                "horizontal_overflow": True,
                "overflow_x": "auto",
                "client_width": 576.0,
                "scroll_width": 864.0,
                "rows": plan_rows,
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
    report_root = tmp_path / "report"
    report_root.mkdir()
    report_paths = EvidencePaths(report_root.resolve())
    recorder = component_gallery_child._Recorder(report_paths, "light")
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
        assert spec.invoke(payload, context=_OPEN_CONTEXT) == {"accepted": True}
    assert spec.invoke(
        {
            "phase": "complete",
            "mode": "light",
            "media": {"dark": False, "forced": False, "reduced": False},
            "cosmetic": report["cosmetic"],
            "part_count": len(part_values),
        },
        context=_OPEN_CONTEXT,
    ) == {"accepted": True}
    recorded = EvidenceReader(report_paths).read_ready()
    assert recorded is not None
    assert recorded["report"] == report

    incomplete_root = tmp_path / "incomplete"
    incomplete_root.mkdir()
    incomplete = component_gallery_child._test_report_spec(
        component_gallery_child._Recorder(
            EvidencePaths(incomplete_root.resolve()),
            "light",
        ),
        lambda _targets: None,
        "light",
    )
    with pytest.raises(CommandPayloadError, match="report is invalid"):
        incomplete.invoke(
            {
                "phase": "complete",
                "mode": "light",
                "media": {"dark": False, "forced": False, "reduced": False},
                "cosmetic": report["cosmetic"],
                "part_count": len(part_values),
            },
            context=_OPEN_CONTEXT,
        )
    with pytest.raises(CommandPayloadError, match="report is invalid"):
        incomplete.invoke(
            {
                "phase": "part",
                "sequence": 1,
                "name": "operations",
                "value": report["operations"],
            },
            context=_OPEN_CONTEXT,
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
    report["cosmetic"]["replacement"]["disposition"] = "applied"
    assert component_gallery_child._valid_complete_report(report) is False
    report["cosmetic"]["replacement"]["disposition"] = "noop"
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
    assert _declared_keys(script, "PLAN_ROW_CASES") == _PLAN_ROW_CASE_KEYS
    assert _declared_keys(script, "CONTROL_CASES") == _CONTROL_KEYS
    assert _SELECTED_TASK_CARD_KEYS <= _BOUNDARY_CONTROL_KEYS
    assert "task_card" not in _BOUNDARY_CONTROL_KEYS
    assert _declared_keys(script, "CONTROL_STATES") == _CONTROL_STATES
    assert 'import("/bridge.js")' in script
    assert 'import("/render.js")' in script
    assert 'import("/icons.js")' in script
    assert 'import("/plan.js")' in script
    assert "renderPlanRow(row, rowView);" in script
    assert 'planSection.style.gridArea = "work";' in script
    assert 'planList.style.setProperty("inline-size", "36rem");' in script
    assert 'planList.style.removeProperty("inline-size");' in script
    assert not any(
        name in script
        for name in ("SyncPlan", "start_plan", "workflow", "dispatcher", "session")
    )
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
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    component_gallery_child._schedule_pseudo_states(
        Native(),
        core,
        [],
        component_gallery_child._Recorder(
            EvidencePaths(evidence_root.resolve()),
            "light",
        ),
        [],
    )

    assert core.methods == ["DOM.enable", "CSS.enable", "DOM.getDocument"]
    assert core.scripts == ["globalThis.__namiGalleryPseudoReady = true;"]


@pytest.mark.headed
def test_br_g_46_theme_selector_reconciles_only_accepted_state(
    component_gallery_evidence: _GalleryEvidence,
) -> None:
    for mode in _MODES:
        report = component_gallery_evidence.result(mode)["report"]
        expected_theme = component_gallery_child._EXPECTED_THEME[mode]
        alternate_theme = "light" if expected_theme == "dark" else "dark"
        cosmetic = report["cosmetic"]
        assert cosmetic["selector"] == {
            "initial_value": expected_theme,
            "initial_disabled": False,
            "change_immediate_value": expected_theme,
            "change_immediate_disabled": True,
            "change_settled_value": alternate_theme,
            "change_settled_disabled": False,
            "restore_immediate_value": alternate_theme,
            "restore_immediate_disabled": True,
            "final_value": expected_theme,
            "final_disabled": False,
        }
        assert cosmetic["after_change"]["revision"] == (
            cosmetic["initial"]["revision"] + 1
        )
        assert cosmetic["replacement"]["disposition"] == "noop"
        assert cosmetic["page_theme"] == expected_theme


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
        _assert_plan_list_evidence(
            report["control_contract"]["file_list"],
            dark=report["media"]["dark"],
            forced=report["media"]["forced"],
            system_colors=report["icons"]["system_colors"],
        )
        assert all(
            row["aliases_consumed"] is True
            for row in (*report["statuses"], *report["operations"])
        )
        assert all(
            row["border_width"] == "0px"
            for row in (*report["statuses"], *report["operations"])
        )
    for report in (light, dark):
        for row in (*report["statuses"], *report["operations"]):
            threshold = 3.0 if row["large_text"] else 4.5
            assert _contrast(row["foreground"], row["background"]) >= threshold
            assert _contrast(row["indicator"], row["background"]) >= 3.0
            assert _contrast(row["shape_color"], row["background"]) >= 3.0
        for control in report["controls"]:
            if control["control"] in _OUTLINE_FREE_CONTROL_KEYS:
                assert not _painted_border(
                    control["border_width"],
                    control["border_style"],
                )
                assert not _painted_border(
                    control["root_border_width"],
                    control["root_border_style"],
                )
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
        controls_by_key = {
            key: {
                row["state"]: row
                for row in report["controls"]
                if row["control"] == key
            }
            for key in _CONTROL_KEYS
        }
        assert (
            controls_by_key["button"]["rest"]["background"]
            != controls_by_key["button_primary"]["rest"]["background"]
        )
        assert (
            controls_by_key["button_primary"]["rest"]["background"]
            == controls_by_key["segmented_control"]["rest"]["background"]
        )
        inactive_filter_background = controls_by_key["chip"]["rest"]["background"]
        assert controls_by_key["filter_copy"]["rest"]["background"] == (
            inactive_filter_background
        )
        assert controls_by_key["filter_delete"]["rest"]["background"] == (
            inactive_filter_background
        )
        assert controls_by_key["filter_copy_active"]["rest"]["background"] == (
            "rgb(51, 170, 238)"
        )
        assert _contrast(
            controls_by_key["filter_copy_active"]["rest"]["foreground"],
            controls_by_key["filter_copy_active"]["rest"]["background"],
        ) >= 4.5
        assert controls_by_key["filter_delete_active"]["rest"]["background"] == (
            "rgb(238, 102, 102)"
        )
        assert controls_by_key["filter_delete_active"]["rest"]["foreground"] == (
            "rgb(85, 17, 17)"
        )
        assert controls_by_key["filter_delete"]["rest"]["foreground"] != (
            controls_by_key["filter_copy"]["rest"]["foreground"]
        )
        for filter_key in {
            "filter_copy",
            "filter_copy_active",
            "filter_delete",
            "filter_delete_active",
        }:
            assert controls_by_key[filter_key]["disabled"]["background"] == (
                controls_by_key["chip"]["disabled"]["background"]
            )
            assert controls_by_key[filter_key]["disabled"]["foreground"] == (
                controls_by_key["chip"]["disabled"]["foreground"]
            )
        for filter_key in {"filter_copy_active", "filter_delete_active"}:
            assert all(
                controls_by_key[filter_key][state]["opacity"] == "1"
                for state in _CONTROL_STATES
            )
        for progress_key in ("progress_determinate", "progress_indeterminate"):
            progress = controls_by_key[progress_key]
            assert progress["rest"]["background"] != progress["rest"]["fill_background"]
            assert progress["rest"]["fill_background"] == "rgb(51, 170, 238)"
            assert progress["hover"]["box_shadow"] == "none"
            assert progress["pressed"]["box_shadow"] == "none"
        by_control = {
            control: {
                row["state"]: row
                for row in report["controls"]
                if row["control"] == control
            }
            for control in {"task_card", *_SELECTED_TASK_CARD_KEYS}
        }
        transparent = by_control["task_card"]
        assert not _opaque_color(transparent["rest"]["background"])
        assert not _opaque_color(transparent["rest"]["border"])
        for control in _SELECTED_TASK_CARD_KEYS:
            for row in by_control[control].values():
                assert _opaque_color(row["background"])
                assert _opaque_color(row["border"])
    system_colors = set(forced["icons"]["system_colors"].values())
    assert system_colors
    forced_rest_controls = {
        row["control"]: row
        for row in forced["controls"]
        if row["state"] == "rest"
    }
    for control in _FORCED_STATIC_ACCENT_CONTROL_KEYS:
        assert forced_rest_controls[control]["background"] == (
            forced["icons"]["system_colors"]["Highlight"]
        )
        assert forced_rest_controls[control]["foreground"] == (
            forced["icons"]["system_colors"]["HighlightText"]
        )
    for row in (*forced["statuses"], *forced["operations"]):
        assert row["foreground"] in system_colors
        assert row["background"] in system_colors
        assert row["indicator"] in system_colors
        assert row["icon_color"] == row["foreground"]
        assert _contrast(row["icon_color"], row["background"]) >= 3.0
        assert row["shape_color"] in system_colors
        assert _contrast(row["shape_color"], row["background"]) >= 3.0
    for control in forced["controls"]:
        if control["control"] in _SELECTED_TASK_CARD_KEYS:
            assert (
                control["background"]
                == forced["icons"]["system_colors"]["Highlight"]
            )
            assert control["border"] in system_colors
            if control["state"] == "disabled":
                assert (
                    control["foreground"]
                    == forced["icons"]["system_colors"]["GrayText"]
                )
            else:
                assert (
                    control["foreground"]
                    == forced["icons"]["system_colors"]["HighlightText"]
                )
                assert (
                    _contrast(control["foreground"], control["background"])
                    >= 4.5
                )
                assert _control_boundary_contrast(control) >= 3.0
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


def _sanitized_failure_record(value: object) -> dict[str, str]:
    if type(value) is not dict or set(value) != {"failure"}:
        raise AssertionError("component gallery failure evidence is invalid")
    failure = value["failure"]
    if (
        type(failure) is not dict
        or set(failure) != {"stage", "type"}
        or failure.get("stage")
        not in component_gallery_child._EVIDENCE_FAILURE_STAGES
        or failure.get("type")
        not in component_gallery_child._EVIDENCE_FAILURE_TYPES
    ):
        raise AssertionError("component gallery failure evidence is invalid")
    return failure


def _run_gallery_mode(
    installed: HeadedInstalledWheel,
    *,
    mode: str,
    root: Path,
    scenario: Path,
) -> dict[str, object]:
    deadline = scenario_deadline(75.0)
    root.mkdir(parents=True)
    evidence_root = require_absolute_local_test_root(root / "evidence")
    evidence_root.mkdir()
    evidence_paths = EvidencePaths(evidence_root)
    evidence_reader = EvidenceReader(evidence_paths)
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
            "--evidence-dir",
            evidence_root,
            "--scenario",
            scenario,
        ),
        cwd=installed.root,
        environment=clean_child_environment(),
        deadline=deadline,
    )
    try:
        window = wait_for_window(process, title, deadline=deadline)
        milestone, initial = wait_for_initial_evidence(
            evidence_reader,
            process,
            deadline=deadline,
        )
        if milestone == "ready":
            assert initial["report"]["mode"] == mode
            wait_for_accessible_text(
                window,
                f"Gallery {mode} complete",
                python=installed.python,
                deadline=deadline,
            )
        close_window(window)
        completed = wait_for_process(process, deadline=deadline)
        final = evidence_reader.read_final()
        evidence_reader.assert_consistent(require_final=milestone == "ready")
    finally:
        if process.poll() is None:
            terminate_process_tree(process, deadline=deadline)
    if final is not None:
        require_host_final(final, exit_code=completed.returncode)
    if milestone == "failure":
        failure = _sanitized_failure_record(initial)
        raise AssertionError(f"component gallery failed: {failure!r}")
    assert final is not None
    assert final["host_returned"] is True
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout == ""
    assert completed.stderr == ""
    result = dict(initial)
    result["exit_code"] = final["exit_code"]
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
        "read_cosmetic_section",
        "readiness_echo",
        "release_terminal_session",
        "replace_cosmetic_section",
        "shell_ready",
        "start_plan",
    ]
    assert result["combined_mapping_type"] == "mappingproxy"
    assert result["combined_command_names"] == sorted(
        [*result["production_command_names"], "test_report"]
    )
    expected_theme = component_gallery_child._EXPECTED_THEME[mode]
    assert result["seeded_cosmetic"] == {
        "section": "appearance",
        "value_version": 1,
        "revision": 1,
        "dirty": True,
        "value": {"theme": expected_theme},
        "disposition": "applied",
    }
    assert result["native_initial_cosmetic"] == {
        "section": "appearance",
        "value_version": 1,
        "revision": 1,
        "dirty": True,
        "value": {"theme": expected_theme},
    }
    assert result["initial_background_color"] == (
        "#1F1F1F" if expected_theme == "dark" else "#F5F5F5"
    )
    assert (
        result["report"]["cosmetic"]["initial"]["revision"]
        == 1
    )
    assert result["report"]["cosmetic"]["initial"]["value"] == {
        "theme": expected_theme
    }
    assert result["report"]["cosmetic"]["replacement"][
        "disposition"
    ] == "noop"
    assert result["report"]["cosmetic"]["selector"] == {
        "initial_value": expected_theme,
        "initial_disabled": False,
        "change_immediate_value": expected_theme,
        "change_immediate_disabled": True,
        "change_settled_value": (
            "light" if expected_theme == "dark" else "dark"
        ),
        "change_settled_disabled": False,
        "restore_immediate_value": (
            "light" if expected_theme == "dark" else "dark"
        ),
        "restore_immediate_disabled": True,
        "final_value": expected_theme,
        "final_disabled": False,
    }
    assert result["report"]["cosmetic"]["page_theme"] == expected_theme
    trusted = urlsplit(result["trusted_url"])
    assert trusted.scheme == "http"
    assert trusted.hostname in {"127.0.0.1", "localhost"}
    assert trusted.port not in {None, 80}
    assert trusted.path.endswith("/index.html")
    assert result["pseudo_state_count"] == len(_CONTROL_KEYS) * 3
    return result


def _assert_installed_assets(evidence: _GalleryEvidence) -> None:
    light = evidence.result("light")
    wheel = evidence.installed.wheel
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert not any("component_gallery" in name for name in names)
        assert not any(name.rsplit("/", 1)[-1] == "gallery.js" for name in names)
        assert all(
            marker not in archive.read(name)
            for marker in _TEST_ONLY_MARKERS
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
    first = light["installed_assets"]
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


def _assert_plan_list_evidence(
    evidence: dict[str, object],
    *,
    dark: bool,
    forced: bool,
    system_colors: dict[str, str],
) -> None:
    expected_order = (
        "plain",
        "mkdir",
        "copy",
        "update",
        "move",
        "move_update",
        "recase",
        "trash",
        "delete",
        "noop",
        "error",
        "unsupported",
    )
    assert evidence["table_role"] == "table"
    assert evidence["header_role"] == "row"
    assert evidence["body_role"] == "rowgroup"
    assert evidence["gallery_uses_work_area"] is True
    assert evidence["gallery_fills_work_area"] is True
    assert _contrast(
        evidence["header_foreground"], evidence["header_background"]
    ) >= 4.5
    if forced:
        assert evidence["header_foreground"] == system_colors["HighlightText"]
        assert evidence["header_background"] == system_colors["Highlight"]
    assert evidence["header_texts"] == [
        "",
        "Files / path",
        "Intended op / status",
        "Checksum",
        "Reason / notes",
    ]
    assert evidence["header_cell_roles"] == ["columnheader"] * 5
    assert evidence["selection_header_label"] == "Selection"
    assert evidence["column_count"] == 5
    assert evidence["row_count"] == len(expected_order)
    assert evidence["body_child_count"] == len(expected_order)
    assert evidence["checkbox_count"] == len(expected_order)
    assert evidence["body_ends_at_last_row"] is True
    assert evidence["body_height_matches_rows"] is True
    assert evidence["horizontal_overflow"] is True
    assert evidence["overflow_x"] == "auto"
    assert evidence["scroll_width"] > evidence["client_width"] > 0

    rows = evidence["rows"]
    assert tuple(row["case"] for row in rows) == expected_order
    by_case = {row["case"]: row for row in rows}
    assert set(by_case) == _PLAN_ROW_CASE_KEYS
    assert {
        row["intent_key"]
        for row in rows
        if row["tone"] == "operation"
    } == _OPERATION_KEYS
    assert (by_case["error"]["tone"], by_case["error"]["intent_key"]) == (
        "status",
        "error",
    )
    assert (
        by_case["unsupported"]["tone"],
        by_case["unsupported"]["intent_key"],
    ) == ("status", "blocked")
    assert (by_case["plain"]["tone"], by_case["plain"]["intent_key"]) == (
        "",
        "",
    )
    assert by_case["mkdir"]["folder"] is True
    assert by_case["copy"]["folder"] is False
    assert by_case["copy"]["depth"] > by_case["mkdir"]["depth"]
    assert (
        by_case["copy"]["path_padding_left"]
        > by_case["mkdir"]["path_padding_left"]
    )
    assert by_case["error"]["checkbox_disabled"] is True
    assert by_case["unsupported"]["checkbox_disabled"] is True

    expected_columns = rows[0]["column_lefts"]
    for row in rows:
        assert row["role"] == "row"
        assert row["cell_roles"] == ["cell"] * 5
        assert row["checkbox_label"]
        assert row["path"]
        assert row["intent"]
        assert row["notes"]
        assert row["checksum"] == "—" or len(row["checksum"]) == 8
        colored_operation = (
            row["tone"] == "operation" and row["intent_key"] != "noop"
        )
        if forced:
            assert row["intent_color"] == system_colors["CanvasText"]
        elif dark and colored_operation:
            assert row["intent_color"] == _OPERATION_MAIN_RGB[row["intent_key"]]
        elif dark and row["tone"] == "status":
            assert row["intent_color"] == _STATUS_MAIN_RGB[row["intent_key"]]
        else:
            assert row["intent_color"] == row["intent_alias_color"]
        assert _contrast(row["intent_color"], row["background"]) >= 4.5
        assert all(
            not _opaque_color(background)
            for background in row["cell_backgrounds"]
        )
        assert row["column_lefts"] == pytest.approx(expected_columns, abs=0.5)

    if not forced:
        odd_backgrounds = {row["background"] for row in rows[::2]}
        even_backgrounds = {row["background"] for row in rows[1::2]}
        assert len(odd_backgrounds) == 1
        assert len(even_backgrounds) == 1
        assert odd_backgrounds != even_backgrounds
        assert by_case["mkdir"]["background"] in even_backgrounds


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
    assert report["control_contract"]["segmented"] == {
        "group_role": "radiogroup",
        "selected_role": "radio",
        "selected_checked": "true",
        "unselected_role": "radio",
        "unselected_checked": "false",
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
            if (
                control in {"progress_determinate", "progress_indeterminate"}
                and state in {"hover", "pressed"}
            ):
                continue
            if (
                report["media"]["forced"]
                and control in _FORCED_STATIC_ACCENT_CONTROL_KEYS
                and state in {"hover", "pressed"}
            ):
                continue
            assert _control_signature(rows[state]) != rest


def _control_signature(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        row[name]
        for name in (
            "foreground",
            "background",
            "fill_background",
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
