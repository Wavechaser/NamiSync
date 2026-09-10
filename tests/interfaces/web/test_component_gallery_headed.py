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
    "file_row.js",
    "integrity.js",
    "plan.js",
)
_TEST_ONLY_MARKERS = (
    b"NAMISYNC_TEST_ONLY_COMPONENT_GALLERY_5CE45567A17F4D74",
    b"NAMISYNC_TEST_ONLY_PLAN_ROWS_45C8C53D55D34893",
    b"NAMISYNC_TEST_ONLY_INTEGRITY_ROWS_7A26DB6506CC49D8",
)
_OPEN_CONTEXT = ReadinessContext(CommandPhase.OPEN, 0)
_LIFECYCLE_CASES = {
    "new": ("neutral", "text"),
    "planned": ("neutral", "text"),
    "queued": ("neutral", "text"),
    "executing": ("accent", "text"),
    "verifying": ("accent", "text"),
    "completed": ("green", "text"),
    "partial": ("yellow", "text"),
    "degraded": ("yellow", "text"),
    "incomplete": ("yellow", "text"),
    "pausing": ("accent", "text"),
    "canceling": ("accent", "text"),
    "paused": ("yellow", "text"),
    "interrupted": ("yellow", "text"),
    "canceled": ("neutral", "fill"),
    "canceled_after_publish": ("yellow", "fill"),
    "canceled_after_mutation": ("yellow", "fill"),
    "refused": ("yellow", "fill"),
    "failed": ("red", "fill"),
    "errored": ("red", "fill"),
}
_INTENT_CASES = {
    "copy": ("blue", "text"),
    "mkdir": ("blue", "text"),
    "move": ("purple", "text"),
    "recase": ("purple", "text"),
    "update": ("yellow", "text"),
    "move_update": ("yellow", "text"),
    "trash": ("red", "text"),
    "delete": ("red", "fill"),
    "noop": ("neutral", "text"),
    "error": ("yellow", "fill"),
    "unsupported": ("yellow", "fill"),
    "blocked": ("yellow", "fill"),
}
_INTEGRITY_CASES = {
    "verified": ("green", "text"),
    "baselined": ("green", "text"),
    "unverified": ("neutral", "text"),
    "modified": ("yellow", "text"),
    "reappeared": ("yellow", "fill"),
    "unsupported": ("yellow", "fill"),
    "canceled": ("neutral", "text"),
    "missing": ("red", "fill"),
    "mismatched": ("red", "fill"),
    "error": ("red", "fill"),
}
_MAIN_HUE_RGB = {
    "blue": "rgb(51, 170, 238)",
    "green": "rgb(51, 221, 153)",
    "yellow": "rgb(255, 170, 34)",
    "red": "rgb(238, 102, 102)",
    "purple": "rgb(136, 68, 204)",
}
_PURPLE_TEXT_RGB = {
    "light": _MAIN_HUE_RGB["purple"],
    "dark": "rgb(187, 136, 238)",
}
_BADGE_BACKGROUND_RGB = {
    "light": {
        "red": "rgb(255, 170, 204)",
        "yellow": "rgb(255, 221, 68)",
    },
    "dark": {
        "red": "rgb(85, 17, 17)",
        "yellow": "rgb(85, 51, 0)",
    },
}
_BADGE_FOREGROUND_RGB = {
    "light": {
        "red": "rgb(85, 17, 17)",
        "yellow": "rgb(85, 51, 0)",
    },
    "dark": {
        "red": _MAIN_HUE_RGB["red"],
        "yellow": _MAIN_HUE_RGB["yellow"],
    },
}
_MAIN_TEXT_CONTRAST_EXCEPTIONS = {
    ("light", "blue"),
    ("light", "green"),
    ("light", "yellow"),
    ("light", "red"),
}
_THEME_CANVAS_RGB = {
    "light": "rgb(245, 245, 245)",
    "dark": "rgb(31, 31, 31)",
}
_PLAN_ROW_CASE_KEYS = {
    "plain",
    "copy",
    "copying",
    "completed",
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
    "blocked",
}
_INTEGRITY_ROW_CASE_KEYS = {
    "folder",
    "verifying",
    "completed",
    *_INTEGRITY_CASES,
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
    "dialog",
    "context_menu",
    "segmented_control",
}
_SELECTED_TASK_CARD_KEYS = {
    "task_card_selected",
    "task_card_current",
}
_BOUNDARY_CONTROL_KEYS = {
    "button",
    "tri_state_checkbox",
    "text_input",
    "toggle",
}
_OUTLINE_FREE_CONTROL_KEYS = {
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
    "task_card_selected",
    "task_card_current",
}
_FORCED_STATE_COLLAPSE_CONTROL_KEYS = _FORCED_STATIC_ACCENT_CONTROL_KEYS | {
    "tri_state_checkbox",
    "toggle",
}
_ACCENT_INTERACTIVE_CONTROL_KEYS = {
    "button_primary",
    "tri_state_checkbox",
    "toggle",
    "segmented_control",
}
_CONTROL_FILL_RGB = {
    "light": {
        "rest": "rgb(251, 251, 251)",
        "hover": "rgb(246, 246, 246)",
        "pressed": "rgb(245, 245, 245)",
        "border": "rgb(229, 229, 229)",
    },
    "dark": {
        "rest": "rgb(56, 56, 56)",
        "hover": "rgb(50, 50, 50)",
        "pressed": "rgb(39, 39, 39)",
        "border": "rgb(53, 53, 53)",
    },
}
_CHECKBOX_STRONG_STROKE = {
    "light": ((0.0, 0.0, 0.0), 0x72 / 0xFF),
    "dark": ((255.0, 255.0, 255.0), 0x8B / 0xFF),
}
_SELECTION_HIGHLIGHT = {
    "light": ((0.0, 0.0, 0.0), 0.04, 0.02),
    "dark": ((255.0, 255.0, 255.0), 0.08, 0.04),
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
    def semantic(
        key: str,
        cases: dict[str, tuple[str, str]],
    ) -> dict[str, object]:
        hue, form = cases[key]
        filled = form == "fill"
        foreground = "rgb(255, 255, 255)" if filled else "rgb(0, 0, 0)"
        background = "rgb(0, 0, 0)" if filled else "rgba(0, 0, 0, 0)"
        return {
            "key": key,
            "text": key,
            "hue": hue,
            "form": form,
            "rendered_form": form,
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
            "height": 18.0,
            "foreground": foreground,
            "background": background,
            "indicator": foreground,
            "border_width": "0px",
            "border_style": "none",
            "alias_foreground": foreground,
            "alias_background": background,
            "alias_indicator": foreground,
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
            "visual_filter": "none",
            "opacity": "1",
            "transform": "none",
            "transition_duration": "0.1s",
            "animation_duration": "0s",
            "animation_name": "none",
        }
        for control in component_gallery_child._CONTROL_KEYS
        for state in component_gallery_child._CONTROL_STATES
    ]
    for control in controls:
        if control["control"] == "text_input":
            control["border_width"] = "2px"
        if control["control"] == "text_input":
            control["box_shadow"] = (
                "rgba(0, 0, 0, 0.45) 0px -2px 0px 0px inset"
            )
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
        "copying",
        "completed",
        "move",
        "move_update",
        "recase",
        "trash",
        "delete",
        "noop",
        "error",
        "unsupported",
        "blocked",
    )
    plan_primary = {
        "plain": ("", "", ""),
        "copying": ("lifecycle", "executing", "progress"),
        "completed": ("lifecycle", "completed", "text"),
        **{
            key: ("intent", key, form)
            for key, (_hue, form) in _INTENT_CASES.items()
        },
    }
    plan_rows = []
    for index, case in enumerate(plan_cases):
        tone, intent_key, form = plan_primary[case]
        filled = form == "fill"
        primary_foreground = (
            "rgb(255, 255, 255)" if filled else "rgb(0, 0, 0)"
        )
        primary_background = (
            "rgb(0, 0, 0)" if filled else "rgba(0, 0, 0, 0)"
        )
        plan_rows.append(
            {
                "case": case,
                "role": "row",
                "cell_roles": ["cell"] * 6,
                "checkbox_label": f"Select {case}",
                "checkbox_checked": False,
                "checkbox_disabled": case in {"error", "unsupported", "blocked"},
                "checkbox_indeterminate": case == "mkdir",
                "checkbox_aria_checked": "mixed" if case == "mkdir" else None,
                "checkbox_width": 16.0,
                "checkbox_height": 16.0,
                "depth": 1 if case in {"copy", "update"} else 0,
                "folder": case == "mkdir",
                "expanded": "true" if case == "mkdir" else None,
                "name": f"{case}.example",
                "size": "1 KB",
                "primary": case,
                "primary_tone": tone,
                "primary_key": intent_key,
                "primary_form": form,
                "secondary": (
                    "—"
                    if case in {"mkdir", "error", "unsupported", "blocked"}
                    else "12345678"
                ),
                "secondary_tone": "",
                "secondary_key": "",
                "notes": f"{case} notes",
                "background": "rgb(255, 255, 255)",
                "primary_foreground": primary_foreground,
                "primary_background": primary_background,
                "primary_height": 4.0 if form == "progress" else 18.0,
                "primary_width": 84.0 if form == "progress" else 20.0,
                "primary_cell_width": 100.0,
                "primary_cell_padding_left": 8.0,
                "primary_cell_padding_right": 8.0,
                "primary_progress_value": 42.0 if form == "progress" else None,
                "primary_progress_bar_width": (
                    35.28 if form == "progress" else 0.0
                ),
                "primary_progress_track": (
                    "rgb(255, 255, 255)" if form == "progress" else ""
                ),
                "primary_progress_fill": (
                    "rgb(0, 0, 0)" if form == "progress" else ""
                ),
                "primary_alias_foreground": primary_foreground,
                "primary_alias_background": primary_background,
                "secondary_color": "rgb(0, 0, 0)",
                "secondary_alias_color": "rgb(0, 0, 0)",
                "cell_backgrounds": ["rgba(0, 0, 0, 0)"] * 6,
                "cells_transparent": True,
                "column_lefts": [float(index) for index in range(6)],
                "name_padding_left": 24.0 if case in {"copy", "update"} else 8.0,
                "row_height": 24.0,
                "font_size": 12.0,
            }
        )

    integrity_cases = (
        "folder",
        "verified",
        "baselined",
        "verifying",
        "completed",
        "unverified",
        "modified",
        "reappeared",
        "unsupported",
        "canceled",
        "missing",
        "mismatched",
        "error",
    )
    integrity_primary = {
        "folder": ("integrity", "unverified", "text"),
        "verifying": ("lifecycle", "verifying", "progress"),
        "completed": ("lifecycle", "completed", "text"),
        **{
            key: ("integrity", key, form)
            for key, (_hue, form) in _INTEGRITY_CASES.items()
        },
    }
    integrity_rows = []
    for case in integrity_cases:
        tone, integrity_key, form = integrity_primary[case]
        filled = form == "fill"
        primary_foreground = (
            "rgb(255, 255, 255)" if filled else "rgb(0, 0, 0)"
        )
        primary_background = (
            "rgb(0, 0, 0)" if filled else "rgba(0, 0, 0, 0)"
        )
        integrity_rows.append(
            {
                "case": case,
                "role": "row",
                "cell_roles": ["cell"] * 6,
                "checkbox_label": f"Select {case}",
                "checkbox_checked": case in {"verified", "modified", "mismatched"},
                "checkbox_disabled": case in {"unsupported", "error"},
                "checkbox_indeterminate": case == "folder",
                "checkbox_aria_checked": "mixed" if case == "folder" else None,
                "checkbox_width": 16.0,
                "checkbox_height": 16.0,
                "depth": 1 if case in {"verified", "baselined"} else 0,
                "folder": case == "folder",
                "expanded": "true" if case == "folder" else None,
                "name": f"{case}.example",
                "size": "1 KB",
                "primary": case,
                "primary_tone": tone,
                "primary_key": integrity_key,
                "primary_form": form,
                "secondary": (
                    "12345678"
                    if case in {"verified", "baselined", "modified", "reappeared", "mismatched"}
                    else "—"
                ),
                "secondary_tone": "",
                "secondary_key": "",
                "notes": f"{case} notes",
                "background": "rgb(255, 255, 255)",
                "primary_foreground": primary_foreground,
                "primary_background": primary_background,
                "primary_height": 4.0 if form == "progress" else 18.0,
                "primary_width": 84.0 if form == "progress" else 20.0,
                "primary_cell_width": 100.0,
                "primary_cell_padding_left": 8.0,
                "primary_cell_padding_right": 8.0,
                "primary_progress_value": 67.0 if form == "progress" else None,
                "primary_progress_bar_width": (
                    56.28 if form == "progress" else 0.0
                ),
                "primary_progress_track": (
                    "rgb(255, 255, 255)" if form == "progress" else ""
                ),
                "primary_progress_fill": (
                    "rgb(0, 0, 0)" if form == "progress" else ""
                ),
                "primary_alias_foreground": primary_foreground,
                "primary_alias_background": primary_background,
                "secondary_color": "rgb(0, 0, 0)",
                "secondary_alias_color": "rgb(0, 0, 0)",
                "cell_backgrounds": ["rgba(0, 0, 0, 0)"] * 6,
                "cells_transparent": True,
                "column_lefts": [float(index) for index in range(6)],
                "name_padding_left": 24.0 if case in {"verified", "baselined"} else 8.0,
                "row_height": 24.0,
                "font_size": 12.0,
            }
        )

    def file_list(rows: list[dict[str, object]], headers: list[str]) -> dict[str, object]:
        return {
            "table_role": "table",
            "header_role": "row",
            "body_role": "rowgroup",
            "gallery_uses_work_area": True,
            "gallery_fills_work_area": True,
            "collapse_hides_children": True,
            "collapse_restores_children": True,
            "child_selection_selects_folder": True,
            "child_selection_restores_mixed": True,
            "master_initially_mixed": True,
            "master_selects_all": True,
            "master_deselects_all": True,
            "master_label": "Select all projected rows",
            "resize_handle_count": 5,
            "resize_handle_columns": [
                "selection",
                "name",
                "size",
                "primary",
                "secondary",
            ],
            "resize_handle_roles": ["separator"] * 5,
            "resize_handle_labels": [
                "Resize selection column",
                "Resize Filename column",
                "Resize Size column",
                "Resize status column",
                "Resize Checksum column",
            ],
            "notes_resizer_absent": True,
            "initial_layout_frozen": False,
            "initial_column_widths": [32.0, 304.0, 80.0, 120.0, 96.0, 240.0],
            "initial_column_lefts": [0.0, 32.0, 336.0, 416.0, 536.0, 632.0],
            "initial_right": 872.0,
            "frozen_column_widths": [32.0, 304.0, 80.0, 120.0, 96.0, 240.0],
            "frozen_column_lefts": [0.0, 32.0, 336.0, 416.0, 536.0, 632.0],
            "frozen_right": 872.0,
            "frozen_layout_active": True,
            "pointer_column_widths": [32.0, 296.0, 80.0, 120.0, 96.0, 248.0],
            "pointer_column_lefts": [0.0, 32.0, 328.0, 408.0, 528.0, 624.0],
            "pointer_right": 872.0,
            "column_resize_changes_width": True,
            "requested_pointer_delta": -8.0,
            "column_resize_delta": -8.0,
            "column_notes_delta": 8.0,
            "keyboard_column_widths": [40.0, 296.0, 80.0, 120.0, 96.0, 240.0],
            "keyboard_column_lefts": [0.0, 40.0, 336.0, 416.0, 536.0, 632.0],
            "keyboard_right": 872.0,
            "keyboard_resize_delta": 8.0,
            "keyboard_notes_delta": -8.0,
            "viewport_resize_amount": 32.0,
            "viewport_narrow_widths": [40.0, 264.0, 80.0, 120.0, 96.0, 240.0],
            "viewport_narrow_right": 840.0,
            "viewport_narrow_right_span": 840.0,
            "viewport_narrow_list_width": 840.0,
            "viewport_restored_widths": [40.0, 296.0, 80.0, 120.0, 96.0, 240.0],
            "viewport_restored_right": 872.0,
            "notes_minimum_widths": [40.0, 312.0, 80.0, 120.0, 96.0, 224.0],
            "name_minimum_widths": [40.0, 192.0, 80.0, 120.0, 96.0, 344.0],
            "name_minimum": 192.0,
            "notes_minimum": 224.0,
            "floor_minimum": 768.0,
            "effective_minimum": 872.0,
            "constrained_column_widths": [40.0, 192.0, 80.0, 120.0, 96.0, 344.0],
            "constrained_grid_width": 872.0,
            "constrained_right_span": 872.0,
            "header_foreground": "rgb(0, 0, 0)",
            "header_background": "rgb(255, 255, 255)",
            "header_texts": headers,
            "header_cell_roles": ["columnheader"] * 6,
            "selection_header_label": "Selection",
            "column_count": 6,
            "row_count": len(rows),
            "body_child_count": len(rows),
            "checkbox_count": len(rows),
            "body_ends_at_last_row": True,
            "body_height_matches_rows": True,
            "horizontal_overflow": True,
            "overflow_x": "auto",
            "client_width": 576.0,
            "scroll_width": 960.0,
            "rows": rows,
        }
    report = {
        "phase": "complete",
        "mode": "light",
        "media": {
            "dark": False,
            "forced": False,
            "reduced": False,
            "hdr": False,
        },
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
        "lifecycles": [
            semantic(key, _LIFECYCLE_CASES) for key in _LIFECYCLE_CASES
        ],
        "intents": [
            semantic(key, _INTENT_CASES) for key in _INTENT_CASES
        ],
        "controls": controls,
        "lifecycle_progress": [
            {
                "case": case,
                "lifecycle": lifecycle,
                "hue": hue,
                "expected_frozen": frozen,
                "motion_frozen": frozen,
                "track_background": "rgb(245, 245, 245)",
                "fill_background": {
                    "accent": "rgb(0, 103, 192)",
                    "yellow": "rgb(255, 170, 34)",
                    "neutral": "rgb(96, 94, 92)",
                }[hue],
                "animation_name": "nami-progress-indeterminate",
                "animation_duration": "1s",
                "animation_iteration_count": "infinite",
                "animation_play_state": "paused" if frozen else "running",
            }
            for case, (lifecycle, hue, frozen) in (
                component_gallery_child._LIFECYCLE_PROGRESS_CASES.items()
            )
        ],
        "control_contract": {
            "accent": {
                "fill": "rgb(0, 103, 192)",
                "fill_hover": "rgba(0, 103, 192, 0.9)",
                "fill_pressed": "rgba(0, 103, 192, 0.8)",
                "foreground": "rgb(255, 255, 255)",
            },
            "tri_state": {
                "aria_checked": "mixed",
                "indeterminate": True,
                "cue_content": '"−"',
                "unchecked_border": "rgba(0, 0, 0, 0.447059)",
                "unchecked_border_width": "1px",
                "mixed_background": "rgb(0, 103, 192)",
                "mixed_foreground": "rgb(255, 255, 255)",
                "mixed_border": "rgb(0, 103, 192)",
                "mixed_border_width": "1px",
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
            "combobox": {
                "trigger_role": "combobox",
                "popup_role": "listbox",
                "expanded": "true",
                "selected": "true",
                "option_count": 3,
                "popup_width_delta": 0.0,
                "popup_within_viewport": True,
                "selected_center_error": 0.0,
                "placement_clamped": False,
                "trigger_background_image": "linear-gradient(rgb(1, 1, 1), rgb(1, 1, 1))",
                "trigger_outline_style": "none",
                "popup_background": "rgb(255, 255, 255)",
                "popup_border": "rgba(0, 0, 0, 0.06)",
                "popup_border_width": "1px",
                "popup_shadow": "rgba(0, 0, 0, 0.22) 0px 8px 16px 0px",
                "popup_backdrop_filter": "none",
                "ordinary_option_background": "rgba(0, 0, 0, 0)",
                "selected_option_background": "rgba(0, 0, 0, 0.04)",
                "hovered_option_background": "rgba(0, 0, 0, 0.04)",
                "pressed_option_background": "rgba(0, 0, 0, 0.02)",
                "selected_pill_width": 3.0,
                "selected_pill_background": "rgb(0, 120, 212)",
            },
            "task_rail": {
                "card_count": 3,
                "outside_content_card": True,
                "left_of_work": True,
                "selected_count": 1,
                "current_count": 1,
                "selected_current_same_card": True,
                "transparent_boundaries": True,
                "selected_marker_width": 3.0,
                "current_marker_width": 3.0,
                "rest_marker_content": "none",
                "selected_marker_background": "rgb(0, 120, 212)",
            },
            "file_list": file_list(
                plan_rows,
                ["", "Filename", "Size", "Operation / status", "Checksum", "Notes"],
            ),
            "integrity_list": file_list(
                integrity_rows,
                ["", "Filename", "Size", "Presence", "Checksum", "Notes"],
            ),
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
        ("lifecycles", report["lifecycles"]),
        ("intents", report["intents"]),
        *(
            ("controls", controls[offset : offset + chunk_rows])
            for offset in range(0, len(controls), chunk_rows)
        ),
        ("lifecycle_progress", report["lifecycle_progress"]),
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
    scheduled: list[list[dict[str, object]]] = []
    spec = component_gallery_child._test_report_spec(
        recorder,
        scheduled.append,
        "light",
    )
    pseudo_targets = component_gallery_child._expected_pseudo_targets("light")
    assert spec.invoke(
        {"phase": "prepare", "targets": pseudo_targets},
        context=_OPEN_CONTEXT,
    ) == {"accepted": True}
    assert scheduled == [pseudo_targets]
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
            "media": {
                "dark": False,
                "forced": False,
                "reduced": False,
                "hdr": False,
            },
            "cosmetic": report["cosmetic"],
            "part_count": len(part_values),
        },
        context=_OPEN_CONTEXT,
    ) == {"accepted": True}
    recorded = EvidenceReader(report_paths).read_ready()
    assert recorded is not None
    assert recorded["schema_version"] == 6
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
                "media": {
                    "dark": False,
                    "forced": False,
                    "reduced": False,
                    "hdr": False,
                },
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
                "value": report["intents"],
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

    assert _declared_keys(script, "LIFECYCLE_CASES") == set(_LIFECYCLE_CASES)
    assert _declared_keys(script, "INTENT_CASES") == set(_INTENT_CASES)
    assert _declared_keys(script, "PLAN_ROW_CASES") == _PLAN_ROW_CASE_KEYS
    assert _declared_keys(script, "INTEGRITY_ROW_CASES") == _INTEGRITY_ROW_CASE_KEYS
    assert _declared_keys(script, "LIFECYCLE_PROGRESS_CASES") == {
        "running",
        "resumed",
        "paused",
        "canceled",
    }
    assert _declared_keys(script, "CONTROL_CASES") == _CONTROL_KEYS
    assert _SELECTED_TASK_CARD_KEYS.isdisjoint(_BOUNDARY_CONTROL_KEYS)
    assert "task_card" not in _BOUNDARY_CONTROL_KEYS
    assert _declared_keys(script, "CONTROL_STATES") == _CONTROL_STATES
    assert 'import("/bridge.js")' in script
    assert 'import("/render.js")' in script
    assert 'import("/icons.js")' in script
    assert 'import("/plan.js")' in script
    assert 'import("/integrity.js")' in script
    assert 'import("/rail.js")' in script
    assert "const galleryRail = createTaskRail({" in script
    assert "galleryRail.render([], null, false);" in script
    assert "app.append(galleryRail.element);" in script
    assert "PLAN_ROW_CASES,\n    renderPlanRow," in script
    assert "INTEGRITY_ROW_CASES,\n    renderIntegrityRow," in script
    assert "renderer(row, definition.rowView);" in script
    assert "intentTone" not in script
    assert 'presenceStatus: "reappeared"' in script
    assert 'planSection.style.gridArea = "work";' in script
    assert 'list.style.setProperty("inline-size", "36rem");' in script
    assert 'list.style.removeProperty("inline-size");' in script
    assert 'resizer.addEventListener("pointerdown"' in script
    assert 'window.addEventListener("pointermove", move);' in script
    assert 'resizer.addEventListener("keydown"' in script
    assert "if (index < headers.length - 1)" in script
    assert '"--nami-file-column-name: minmax(12rem, 1fr)"' in script
    assert "grid.style.cssText = [" in script
    assert "resizeState.widths = headerCells.map(" in script
    assert "nextWidths[5] = startWidths[5] - delta;" in script
    assert script.count("ensureFrozen();") == 2
    assert 'data-column="notes"' in script
    assert "640" not in script
    assert 'masterCheckbox.addEventListener("change"' in script
    assert 'surface.dataset.galleryHdrIsolate = isolate;' in script
    assert 'surface.style.boxShadow = "var(--elevation-8)";' in script
    assert '["Translucent surface without shadow", "shadowless"]' in script
    assert '["Opaque surface with shadow", "opaque"]' in script
    assert 'document.createElement("select")' not in script
    assert "replaceWith(" not in script
    assert 'ordinaryThemeOption.cloneNode(true)' in script
    assert 'pressedThemeOptionSource.cloneNode(true)' in script
    assert 'hoveredThemeOption.id = "gallery-theme-option-hover";' in script
    assert 'pressedThemeOption.id = "gallery-theme-option-pressed";' in script
    assert "optionStatePopup.remove();" in script
    assert "localStorage" not in script
    assert "sessionStorage" not in script
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
    assert core.methods == [
        "DOM.enable",
        "CSS.enable",
        "DOM.getDocument",
    ]
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

    media_names = ("dark", "forced", "reduced")
    assert {name: light["media"][name] for name in media_names} == {
        "dark": False,
        "forced": False,
        "reduced": False,
    }
    assert {name: dark["media"][name] for name in media_names} == {
        "dark": True,
        "forced": False,
        "reduced": False,
    }
    assert {name: forced["media"][name] for name in media_names} == {
        "dark": True,
        "forced": True,
        "reduced": False,
    }
    assert all(
        type(report["media"]["hdr"]) is bool
        for report in (light, dark, forced)
    )
    for report in (light, dark, forced):
        theme = "dark" if report["media"]["dark"] else "light"
        _assert_complete_gallery_matrix(report)
        _assert_icon_registry_evidence(
            report["icons"],
            forced=report["media"]["forced"],
        )
        _assert_plan_list_evidence(
            report["control_contract"]["file_list"],
            forced=report["media"]["forced"],
            system_colors=report["icons"]["system_colors"],
            theme=theme,
        )
        _assert_integrity_list_evidence(
            report["control_contract"]["integrity_list"],
            forced=report["media"]["forced"],
            system_colors=report["icons"]["system_colors"],
            theme=theme,
        )
        assert all(
            row["aliases_consumed"] is True
            for row in (*report["lifecycles"], *report["intents"])
        )
        assert all(
            row["border_width"] == "0px"
            for row in (*report["lifecycles"], *report["intents"])
        )
        _assert_semantic_channels(report)
        _assert_lifecycle_progress(report)
    for report in (light, dark):
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
                and control["control"] != "filter_delete"
                and not (
                    control["state"] in {"hover", "pressed"}
                    and control["control"] in {
                        "button_primary",
                        "filter_copy_active",
                        "filter_delete_active",
                        "segmented_control",
                    }
                )
                and control["state"] != "disabled"
            ):
                assert _contrast(control["foreground"], control["background"]) >= 4.5
            if (
                control["control"] in _BOUNDARY_CONTROL_KEYS
                and control["state"] != "disabled"
            ):
                assert _painted_border(
                    control["border_width"],
                    control["border_style"],
                ) or _painted_border(
                    control["root_border_width"],
                    control["root_border_style"],
                )
                if control["control"] in {"tri_state_checkbox", "toggle"}:
                    assert _control_boundary_contrast(control) >= 3.0
                elif control["control"] == "text_input":
                    underline_colors = _inset_shadow_colors(control)
                    assert underline_colors
                    assert max(
                        _composited_contrast(color, control["background"])
                        for color in underline_colors
                    ) >= 3.0
            if control["state"] == "focused":
                assert (
                    control["box_shadow"] != "none"
                    or control["outline_width"] not in {"0px", "0"}
                )
                focus_color = _rendered_focus_color(control)
                assert _contrast(focus_color, control["surrounding"]) >= 3.0
                if control["outline_style"] == "none":
                    focus_colors = _focus_shadow_colors(control)
                    assert len(focus_colors) == 2
                    assert _contrast(focus_colors[0], focus_colors[1]) >= 3.0
        controls_by_key = {
            key: {
                row["state"]: row
                for row in report["controls"]
                if row["control"] == key
            }
            for key in _CONTROL_KEYS
        }
        theme = "dark" if report["media"]["dark"] else "light"
        normal_button = controls_by_key["button"]
        for state in ("rest", "hover", "pressed"):
            assert normal_button[state]["background"] == (
                _CONTROL_FILL_RGB[theme][state]
            )
            assert normal_button[state]["border"] == (
                _CONTROL_FILL_RGB[theme]["border"]
            )
        for state in _CONTROL_STATES:
            button_width = _css_pixel_width(normal_button[state]["border_width"])
            checkbox_width = _css_pixel_width(
                controls_by_key["tri_state_checkbox"][state]["border_width"]
            )
            input_width = _css_pixel_width(
                controls_by_key["text_input"][state]["border_width"]
            )
            assert button_width > 0
            assert checkbox_width == pytest.approx(button_width, abs=0.01)
            assert input_width >= button_width * 1.75
            # Static evidence owns the authored 1:2 logical-pixel contract.
            # WebView2 reports device-snapped widths (for example 1:3 device
            # pixels at 175%), so headed evidence permits that upper rung.
            assert input_width <= checkbox_width * 3.01
        expected_flyout_alpha = 0.2 if report["media"]["dark"] else 0.06
        assert _color_alpha(
            controls_by_key["dialog"]["rest"]["border"]
        ) == pytest.approx(expected_flyout_alpha)
        assert _color_alpha(
            controls_by_key["context_menu"]["rest"]["root_border"]
        ) == pytest.approx(expected_flyout_alpha)
        assert (
            controls_by_key["button"]["rest"]["background"]
            != controls_by_key["button_primary"]["rest"]["background"]
        )
        assert (
            controls_by_key["button_primary"]["rest"]["background"]
            == controls_by_key["segmented_control"]["rest"]["background"]
        )
        assert _contrast(
            controls_by_key["button_primary"]["rest"]["foreground"],
            controls_by_key["button_primary"]["rest"]["background"],
        ) >= 4.5
        assert controls_by_key["button_primary"]["rest"]["foreground"] == (
            controls_by_key["segmented_control"]["rest"]["foreground"]
        )
        assert controls_by_key["button_primary"]["hover"]["foreground"] == (
            controls_by_key["button_primary"]["rest"]["foreground"]
        )
        assert controls_by_key["button_primary"]["pressed"]["foreground"] == (
            controls_by_key["button_primary"]["rest"]["foreground"]
        )
        assert controls_by_key["button_primary"]["hover"]["visual_filter"] == (
            "none"
        )
        assert controls_by_key["button_primary"]["pressed"]["visual_filter"] == (
            "none"
        )
        accent = report["control_contract"]["accent"]
        accent_rgb = _color_rgb(accent["fill"])
        accent_states = {
            "rest": ("fill", 1.0),
            "hover": ("fill_hover", 0.9),
            "pressed": ("fill_pressed", 0.8),
        }
        assert controls_by_key["button_primary"]["rest"]["foreground"] == (
            accent["foreground"]
        )
        for state, (semantic_role, alpha) in accent_states.items():
            semantic_fill = accent[semantic_role]
            assert _color_rgb(semantic_fill) == pytest.approx(accent_rgb)
            assert _color_alpha(semantic_fill) == pytest.approx(alpha)
            primary_background = controls_by_key["button_primary"][state][
                "background"
            ]
            assert primary_background == semantic_fill
            for control in _ACCENT_INTERACTIVE_CONTROL_KEYS - {
                "button_primary"
            }:
                assert controls_by_key[control][state]["background"] == (
                    primary_background
                )
        tri_state = report["control_contract"]["tri_state"]
        checkbox_stroke_rgb, checkbox_stroke_alpha = _CHECKBOX_STRONG_STROKE[
            theme
        ]
        assert _color_rgb(tri_state["unchecked_border"]) == pytest.approx(
            checkbox_stroke_rgb
        )
        assert _color_alpha(tri_state["unchecked_border"]) == pytest.approx(
            checkbox_stroke_alpha,
            abs=0.001,
        )
        assert tri_state["mixed_background"] == (
            controls_by_key["button_primary"]["rest"]["background"]
        )
        assert tri_state["mixed_border"] == tri_state["mixed_background"]
        assert _css_pixel_width(
            tri_state["unchecked_border_width"]
        ) == pytest.approx(
            _css_pixel_width(normal_button["rest"]["border_width"]),
            abs=0.01,
        )
        assert _css_pixel_width(
            tri_state["mixed_border_width"]
        ) == pytest.approx(
            _css_pixel_width(tri_state["unchecked_border_width"]),
            abs=0.01,
        )
        input_states = controls_by_key["text_input"]
        assert all("inset" in input_states[state]["box_shadow"] for state in (
            "rest",
            "hover",
            "pressed",
            "focused",
        ))
        rest_underline = _inset_shadow_colors(input_states["rest"])
        focused_underline = _inset_shadow_colors(input_states["focused"])
        assert len(rest_underline) == 1
        assert len(focused_underline) == 1
        assert focused_underline[0] == (
            controls_by_key["button_primary"]["rest"]["background"]
        )
        assert rest_underline != focused_underline
        assert controls_by_key["button_primary"]["disabled"]["background"] == (
            controls_by_key["button"]["disabled"]["background"]
        )
        assert controls_by_key["button_primary"]["disabled"]["foreground"] == (
            controls_by_key["button"]["disabled"]["foreground"]
        )
        inactive_filter_background = controls_by_key["chip"]["rest"]["background"]
        assert controls_by_key["filter_copy"]["rest"]["background"] == (
            inactive_filter_background
        )
        assert controls_by_key["filter_delete"]["rest"]["background"] == (
            inactive_filter_background
        )
        for state in ("hover", "pressed"):
            assert controls_by_key["filter_delete"][state]["background"] == (
                controls_by_key["filter_copy"][state]["background"]
            )
        assert (
            controls_by_key["filter_delete"]["hover"]["background"]
            != controls_by_key["filter_delete"]["pressed"]["background"]
        )
        assert controls_by_key["filter_copy_active"]["rest"]["background"] == (
            _MAIN_HUE_RGB["blue"]
        )
        assert _contrast(
            controls_by_key["filter_copy_active"]["rest"]["foreground"],
            controls_by_key["filter_copy_active"]["rest"]["background"],
        ) >= 4.5
        assert controls_by_key["filter_delete_active"]["rest"]["background"] == (
            _MAIN_HUE_RGB["red"]
        )
        assert all(
            controls_by_key["filter_delete"][state]["foreground"]
            == _MAIN_HUE_RGB["red"]
            for state in {"rest", "hover", "pressed", "focused"}
        )
        semantic_intents = {row["key"]: row for row in report["intents"]}
        assert controls_by_key["filter_copy_active"]["rest"]["background"] == (
            semantic_intents["copy"]["foreground"]
        )
        assert controls_by_key["filter_delete_active"]["rest"]["foreground"] != (
            semantic_intents["delete"]["foreground"]
        )
        assert _contrast(
            controls_by_key["filter_delete_active"]["rest"]["foreground"],
            controls_by_key["filter_delete_active"]["rest"]["background"],
        ) >= 4.5
        assert controls_by_key["filter_delete"]["rest"]["foreground"] == (
            semantic_intents["trash"]["foreground"]
        )
        assert all(
            _contrast(
                controls_by_key["filter_delete_active"][state]["foreground"],
                controls_by_key["filter_delete_active"][state]["background"],
            )
            >= 4.5
            for state in {"rest", "focused"}
        )
        assert len(
            {
                controls_by_key["filter_delete_active"][state]["foreground"]
                for state in {"rest", "hover", "pressed", "focused"}
            }
        ) == 1
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
            assert all(
                controls_by_key[filter_key][state]["transform"] == "none"
                for state in _CONTROL_STATES
            )
            base = controls_by_key[filter_key]["rest"]["background"]
            assert controls_by_key[filter_key]["focused"]["background"] == base
            assert _color_alpha(base) == pytest.approx(1.0)
            for state, strength in (("hover", 0.9), ("pressed", 0.8)):
                interaction = controls_by_key[filter_key][state]["background"]
                assert _color_rgb(interaction) == pytest.approx(_color_rgb(base))
                assert _color_alpha(interaction) == pytest.approx(strength)
                assert controls_by_key[filter_key][state]["foreground"] == (
                    controls_by_key[filter_key]["rest"]["foreground"]
                )
        for progress_key in ("progress_determinate", "progress_indeterminate"):
            progress = controls_by_key[progress_key]
            assert progress["rest"]["background"] != progress["rest"]["fill_background"]
            assert progress["rest"]["fill_background"] == (
                controls_by_key["button_primary"]["rest"]["background"]
            )
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
        assert all(row["border_width"] == "0px" for row in transparent.values())
        card = controls_by_key["card"]
        assert len({row["background"] for row in card.values()}) == 1
        assert len({row["border"] for row in card.values()}) == 1
        assert all(
            _painted_border(row["border_width"], row["border_style"])
            for row in card.values()
        )
        assert _color_alpha(card["rest"]["background"]) == pytest.approx(
            0.05 if report["media"]["dark"] else 0.7,
            abs=0.005,
        )
        assert _color_alpha(card["rest"]["border"]) == pytest.approx(
            0.10 if report["media"]["dark"] else 0.06,
            abs=0.005,
        )
        selection_rgb, selected_alpha, pressed_alpha = _SELECTION_HIGHLIGHT[theme]
        assert _color_rgb(transparent["hover"]["background"]) == pytest.approx(
            selection_rgb
        )
        assert _color_alpha(transparent["hover"]["background"]) == pytest.approx(
            selected_alpha
        )
        assert _color_rgb(transparent["pressed"]["background"]) == pytest.approx(
            selection_rgb
        )
        assert _color_alpha(transparent["pressed"]["background"]) == pytest.approx(
            pressed_alpha
        )
        combobox = report["control_contract"]["combobox"]
        assert combobox["selected_option_background"] == (
            combobox["hovered_option_background"]
        )
        assert combobox["selected_option_background"] == (
            transparent["hover"]["background"]
        )
        assert combobox["pressed_option_background"] == (
            transparent["pressed"]["background"]
        )
        assert combobox["selected_pill_background"] == (
            controls_by_key["button_primary"]["rest"]["background"]
        )
        for control in _SELECTED_TASK_CARD_KEYS:
            selected = by_control[control]
            assert selected["rest"]["background"] == transparent["hover"]["background"]
            assert selected["focused"]["background"] == selected["rest"]["background"]
            assert selected["hover"]["background"] == selected["rest"]["background"]
            assert selected["pressed"]["background"] == transparent["pressed"]["background"]
            assert all(row["border_width"] == "0px" for row in selected.values())
    system_colors = set(forced["icons"]["system_colors"].values())
    assert system_colors
    forced_rest_controls = {
        row["control"]: row
        for row in forced["controls"]
        if row["state"] == "rest"
    }
    assert forced_rest_controls["dialog"]["border"] == (
        forced["icons"]["system_colors"]["ButtonBorder"]
    )
    assert forced_rest_controls["context_menu"]["root_border"] == (
        forced["icons"]["system_colors"]["ButtonBorder"]
    )
    for control in _FORCED_STATIC_ACCENT_CONTROL_KEYS:
        assert forced_rest_controls[control]["background"] == (
            forced["icons"]["system_colors"]["Highlight"]
        )
        assert forced_rest_controls[control]["foreground"] == (
            forced["icons"]["system_colors"]["HighlightText"]
        )
    for control in {"tri_state_checkbox", "toggle"}:
        assert forced_rest_controls[control]["background"] == (
            forced["icons"]["system_colors"]["Highlight"]
        )
    for control in forced["controls"]:
        if control["control"] in _SELECTED_TASK_CARD_KEYS:
            assert control["border_width"] == "0px"
            if control["state"] == "disabled":
                assert (
                    control["foreground"]
                    == forced["icons"]["system_colors"]["GrayText"]
                )
            else:
                assert (
                    control["background"]
                    == forced["icons"]["system_colors"]["Highlight"]
                )
                assert (
                    control["foreground"]
                    == forced["icons"]["system_colors"]["HighlightText"]
                )
                assert (
                    _contrast(control["foreground"], control["background"])
                    >= 4.5
                )
        if control["state"] == "focused":
            assert (
                control["box_shadow"] != "none"
                or (
                    control["outline_width"] not in {"0px", "0"}
                    and control["outline_style"] != "none"
                )
            ), control["control"]
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
    _assert_complete_gallery_matrix(reduced)
    _assert_semantic_channels(reduced)
    _assert_lifecycle_progress(reduced)
    _assert_plan_list_evidence(
        reduced["control_contract"]["file_list"],
        forced=False,
        system_colors=reduced["icons"]["system_colors"],
        theme="light",
    )
    _assert_integrity_list_evidence(
        reduced["control_contract"]["integrity_list"],
        forced=False,
        system_colors=reduced["icons"]["system_colors"],
        theme="light",
    )
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
    assert result["schema_version"] == 6
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
        "create_task",
        "list_tasks",
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
    assert result["pseudo_state_count"] == len(
        component_gallery_child._expected_pseudo_targets(mode)
    )
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


def _assert_semantic_channels(report: dict[str, object]) -> None:
    forced = report["media"]["forced"]
    theme = "dark" if report["media"]["dark"] else "light"
    accent_fill = report["control_contract"]["accent"]["fill"]
    system_colors = report["icons"]["system_colors"]
    for channel, expected in (
        ("lifecycles", _LIFECYCLE_CASES),
        ("intents", _INTENT_CASES),
    ):
        rows = report[channel]
        assert {row["key"] for row in rows} == set(expected)
        assert len(rows) == len(expected)
        for row in rows:
            hue, form = expected[row["key"]]
            assert (row["hue"], row["form"], row["rendered_form"]) == (
                hue,
                form,
                form,
            )
            assert row["aliases_consumed"] is True
            assert row["foreground"] == row["alias_foreground"]
            assert row["background"] == row["alias_background"]
            assert row["indicator"] == row["alias_indicator"]
            assert row["shape_color"] == row["indicator"]
            assert row["icon_color"] == row["foreground"]
            assert not _painted_border(
                row["border_width"], row["border_style"]
            )
            if form == "fill":
                assert row["height"] == pytest.approx(18.0, abs=0.5)
                assert _opaque_color(row["background"])
                _assert_filled_semantic_colors(
                    theme=theme,
                    hue=hue,
                    foreground=row["foreground"],
                    background=row["background"],
                    forced=forced,
                    system_colors=system_colors,
                )
                continue

            assert not _opaque_color(row["background"])
            if forced:
                assert row["foreground"] == system_colors["CanvasText"]
                assert _contrast(
                    row["foreground"], system_colors["Canvas"]
                ) >= 4.5
            elif hue == "accent":
                assert row["foreground"] == accent_fill
                assert _contrast(
                    row["foreground"], _THEME_CANVAS_RGB[theme]
                ) >= 4.5
            elif hue in _MAIN_HUE_RGB:
                assert row["foreground"] == _expected_hue_text(theme, hue)
                _assert_main_text_contrast(
                    theme,
                    hue,
                    row["foreground"],
                    _THEME_CANVAS_RGB[theme],
                )
            else:
                assert hue == "neutral"
                assert _contrast(
                    row["foreground"], _THEME_CANVAS_RGB[theme]
                ) >= 4.5


def _assert_lifecycle_progress(report: dict[str, object]) -> None:
    rows = report["lifecycle_progress"]
    expected = component_gallery_child._LIFECYCLE_PROGRESS_CASES
    assert {row["case"] for row in rows} == set(expected)
    assert len(rows) == len(expected)
    by_case = {row["case"]: row for row in rows}
    lifecycles = {row["key"]: row for row in report["lifecycles"]}
    forced = report["media"]["forced"]
    reduced = report["media"]["reduced"]
    system_colors = report["icons"]["system_colors"]
    accent_fill = report["control_contract"]["accent"]["fill"]
    for case, (lifecycle, hue, frozen) in expected.items():
        row = by_case[case]
        assert (row["lifecycle"], row["hue"]) == (lifecycle, hue)
        assert row["expected_frozen"] is frozen
        assert row["motion_frozen"] is (frozen or reduced)
        assert row["track_background"] != row["fill_background"]
        if forced:
            assert row["track_background"] == system_colors["Canvas"]
            assert row["fill_background"] == system_colors["Highlight"]
        elif hue == "accent":
            assert row["fill_background"] == accent_fill
        elif hue == "yellow":
            assert row["fill_background"] == _MAIN_HUE_RGB["yellow"]
        else:
            assert hue == "neutral"
            assert row["fill_background"] == lifecycles["canceled"]["foreground"]
        if reduced:
            assert row["animation_name"] == "none"
        else:
            assert row["animation_name"] == "nami-progress-indeterminate"
            assert row["animation_iteration_count"] == "infinite"
            assert _maximum_duration_ms(row["animation_duration"]) > 0
            assert row["animation_play_state"] == (
                "paused" if frozen else "running"
            )
    if not forced:
        assert by_case["running"]["fill_background"] == (
            by_case["resumed"]["fill_background"]
        )
        assert by_case["paused"]["fill_background"] == _MAIN_HUE_RGB["yellow"]
        assert by_case["canceled"]["fill_background"] not in {
            accent_fill,
            _MAIN_HUE_RGB["yellow"],
        }


def _assert_main_text_contrast(
    theme: str,
    hue: str,
    foreground: str,
    background: str,
) -> None:
    ratio = _contrast(foreground, background)
    if (theme, hue) in _MAIN_TEXT_CONTRAST_EXCEPTIONS:
        # Main hues intentionally retain class identity as ordinary text. Their
        # icon, shape, and visible cue carry the redundant non-color channel.
        assert 1.0 < ratio < 4.5
    else:
        assert ratio >= 4.5


def _expected_hue_text(theme: str, hue: str) -> str:
    if hue == "purple":
        return _PURPLE_TEXT_RGB[theme]
    return _MAIN_HUE_RGB[hue]


def _assert_filled_semantic_colors(
    *,
    theme: str,
    hue: str,
    foreground: str,
    background: str,
    forced: bool,
    system_colors: dict[str, str],
) -> None:
    if forced:
        assert background == system_colors["Highlight"]
        assert foreground == system_colors["HighlightText"]
        return
    if hue in _BADGE_BACKGROUND_RGB[theme]:
        assert background == _BADGE_BACKGROUND_RGB[theme][hue]
        assert foreground == _BADGE_FOREGROUND_RGB[theme][hue]
        assert _contrast(foreground, background) >= 4.5
        return
    assert hue == "neutral"
    assert _contrast(foreground, background) >= 4.5


def _assert_inline_row_progress(
    row: dict[str, object],
    *,
    expected_value: float,
    forced: bool,
    system_colors: dict[str, str],
    accent_fill: str,
) -> None:
    assert row["primary_form"] == "progress"
    assert row["primary_height"] == pytest.approx(4.0, abs=0.5)
    assert row["primary_cell_padding_left"] == pytest.approx(8.0, abs=0.25)
    assert row["primary_cell_padding_right"] == pytest.approx(8.0, abs=0.25)
    assert (
        row["primary_width"]
        + row["primary_cell_padding_left"]
        + row["primary_cell_padding_right"]
    ) == pytest.approx(row["primary_cell_width"], abs=0.5)
    assert row["primary_progress_value"] == pytest.approx(expected_value)
    assert row["primary_progress_bar_width"] / row["primary_width"] * 100 == (
        pytest.approx(expected_value, abs=0.5)
    )
    assert row["primary_progress_track"] != row["primary_progress_fill"]
    assert not _opaque_color(row["primary_background"])
    if forced:
        assert row["primary_progress_track"] == system_colors["Canvas"]
        assert row["primary_progress_fill"] == system_colors["Highlight"]
    else:
        assert row["primary_progress_fill"] == accent_fill


def _assert_plan_list_evidence(
    evidence: dict[str, object],
    *,
    forced: bool,
    system_colors: dict[str, str],
    theme: str,
) -> None:
    expected_order = (
        "plain",
        "mkdir",
        "copy",
        "update",
        "copying",
        "completed",
        "move",
        "move_update",
        "recase",
        "trash",
        "delete",
        "noop",
        "error",
        "unsupported",
        "blocked",
    )
    rows = _assert_file_list_evidence(
        evidence,
        expected_order=expected_order,
        expected_headers=[
            "",
            "Filename",
            "Size",
            "Operation / status",
            "Checksum",
            "Notes",
        ],
        forced=forced,
        system_colors=system_colors,
    )
    assert tuple(row["case"] for row in rows) == expected_order
    by_case = {row["case"]: row for row in rows}
    assert set(by_case) == _PLAN_ROW_CASE_KEYS
    assert {
        case: (
            row["primary_tone"],
            row["primary_key"],
            row["primary_form"],
        )
        for case, row in by_case.items()
    } == {
        "plain": ("", "", ""),
        "copying": ("lifecycle", "executing", "progress"),
        "completed": ("lifecycle", "completed", "text"),
        **{
            key: ("intent", key, form)
            for key, (_hue, form) in _INTENT_CASES.items()
        },
    }
    assert by_case["mkdir"]["folder"] is True
    assert by_case["copy"]["folder"] is False
    assert by_case["copy"]["depth"] > by_case["mkdir"]["depth"]
    assert (
        by_case["copy"]["name_padding_left"]
        > by_case["mkdir"]["name_padding_left"]
    )
    assert by_case["copy"]["name"] == "DSC_1000.jpeg"
    assert by_case["update"]["name"] == "DSC_1001.jpeg"
    assert "\\" not in by_case["copy"]["name"]
    assert by_case["mkdir"]["checkbox_indeterminate"] is True
    assert by_case["mkdir"]["checkbox_aria_checked"] == "mixed"
    assert by_case["mkdir"]["expanded"] == "true"
    assert by_case["error"]["checkbox_disabled"] is True
    assert by_case["unsupported"]["checkbox_disabled"] is True
    assert by_case["blocked"]["checkbox_disabled"] is True

    for row in rows:
        assert row["secondary"] == "—" or len(row["secondary"]) == 8
        assert row["secondary_tone"] == ""
        assert row["secondary_key"] == ""
        assert row["secondary_color"] == row["secondary_alias_color"]
        assert _contrast(row["secondary_color"], row["background"]) >= 4.5
        if row["primary_tone"] == "":
            assert row["primary_form"] == ""
            assert not _opaque_color(row["primary_background"])
            assert _contrast(
                row["primary_foreground"], row["background"]
            ) >= 4.5
            continue
        if row["primary_form"] == "progress":
            _assert_inline_row_progress(
                row,
                expected_value=42.0,
                forced=forced,
                system_colors=system_colors,
                accent_fill=row["primary_alias_foreground"],
            )
            continue
        hue, form = (
            _LIFECYCLE_CASES[row["primary_key"]]
            if row["primary_tone"] == "lifecycle"
            else _INTENT_CASES[row["primary_key"]]
        )
        assert row["primary_form"] == form
        if forced and form != "fill":
            assert not _opaque_color(row["primary_background"])
            assert row["primary_foreground"] == system_colors["CanvasText"]
        elif form == "fill":
            _assert_filled_semantic_colors(
                theme=theme,
                hue=hue,
                foreground=row["primary_foreground"],
                background=row["primary_background"],
                forced=forced,
                system_colors=system_colors,
            )
        else:
            assert not _opaque_color(row["primary_background"])
            if hue in _MAIN_HUE_RGB:
                assert row["primary_foreground"] == _expected_hue_text(theme, hue)
                _assert_main_text_contrast(
                    theme,
                    hue,
                    row["primary_foreground"],
                    row["background"],
                )
            else:
                assert _contrast(
                    row["primary_foreground"], row["background"]
                ) >= 4.5
        if form == "fill":
            assert row["primary_height"] == pytest.approx(18.0, abs=0.5)


def _assert_integrity_list_evidence(
    evidence: dict[str, object],
    *,
    forced: bool,
    system_colors: dict[str, str],
    theme: str,
) -> None:
    expected_order = (
        "folder",
        "verified",
        "baselined",
        "verifying",
        "completed",
        "unverified",
        "modified",
        "reappeared",
        "unsupported",
        "canceled",
        "missing",
        "mismatched",
        "error",
    )
    rows = _assert_file_list_evidence(
        evidence,
        expected_order=expected_order,
        expected_headers=["", "Filename", "Size", "Presence", "Checksum", "Notes"],
        forced=forced,
        system_colors=system_colors,
    )
    by_case = {row["case"]: row for row in rows}
    assert set(by_case) == _INTEGRITY_ROW_CASE_KEYS
    assert by_case["folder"]["checkbox_indeterminate"] is True
    assert by_case["folder"]["checkbox_aria_checked"] == "mixed"
    assert by_case["verified"]["name"] == "report.pdf"
    assert by_case["baselined"]["name"] == "draft.docx"
    assert by_case["verified"]["depth"] > by_case["folder"]["depth"]
    assert by_case["baselined"]["depth"] > by_case["folder"]["depth"]
    assert (
        by_case["reappeared"]["primary_tone"],
        by_case["reappeared"]["primary_key"],
        by_case["reappeared"]["primary_form"],
    ) == ("integrity", "reappeared", "fill")
    for row in rows:
        if row["case"] == "folder":
            tone, key = "integrity", "unverified"
        elif row["case"] in {"verifying", "completed"}:
            tone, key = "lifecycle", row["case"]
        else:
            tone, key = "integrity", row["case"]
        hue, form = (
            _LIFECYCLE_CASES[key]
            if tone == "lifecycle"
            else _INTEGRITY_CASES[key]
        )
        if row["case"] == "verifying":
            form = "progress"
        assert (row["primary_tone"], row["primary_key"]) == (tone, key)
        assert row["primary_form"] == form
        assert row["secondary_tone"] == ""
        assert row["secondary_key"] == ""
        assert row["secondary"] == "—" or len(row["secondary"]) == 8
        if form == "progress":
            _assert_inline_row_progress(
                row,
                expected_value=67.0,
                forced=forced,
                system_colors=system_colors,
                accent_fill=row["primary_alias_foreground"],
            )
        elif forced and form != "fill":
            assert not _opaque_color(row["primary_background"])
            assert row["primary_foreground"] == system_colors["CanvasText"]
        elif form == "fill":
            _assert_filled_semantic_colors(
                theme=theme,
                hue=hue,
                foreground=row["primary_foreground"],
                background=row["primary_background"],
                forced=forced,
                system_colors=system_colors,
            )
        else:
            assert not _opaque_color(row["primary_background"])
            if hue in _MAIN_HUE_RGB:
                assert row["primary_foreground"] == _expected_hue_text(theme, hue)
                _assert_main_text_contrast(
                    theme,
                    hue,
                    row["primary_foreground"],
                    row["background"],
                )
            else:
                assert _contrast(
                    row["primary_foreground"], row["background"]
                ) >= 4.5
        assert row["secondary_color"] == row["secondary_alias_color"]
        assert _contrast(row["secondary_color"], row["background"]) >= 4.5
        if form == "fill":
            assert row["primary_height"] == pytest.approx(18.0, abs=0.5)


def _assert_file_list_evidence(
    evidence: dict[str, object],
    *,
    expected_order: tuple[str, ...],
    expected_headers: list[str],
    forced: bool,
    system_colors: dict[str, str],
) -> list[dict[str, object]]:
    assert evidence["table_role"] == "table"
    assert evidence["header_role"] == "row"
    assert evidence["body_role"] == "rowgroup"
    assert evidence["gallery_uses_work_area"] is True
    assert evidence["gallery_fills_work_area"] is True
    assert evidence["collapse_hides_children"] is True
    assert evidence["collapse_restores_children"] is True
    assert evidence["child_selection_selects_folder"] is True
    assert evidence["child_selection_restores_mixed"] is True
    assert evidence["master_initially_mixed"] is True
    assert evidence["master_selects_all"] is True
    assert evidence["master_deselects_all"] is True
    assert evidence["master_label"].startswith("Select all ")
    assert evidence["resize_handle_count"] == 5
    assert evidence["resize_handle_columns"] == [
        "selection",
        "name",
        "size",
        "primary",
        "secondary",
    ]
    assert evidence["resize_handle_roles"] == ["separator"] * 5
    assert all(
        label.startswith("Resize ")
        for label in evidence["resize_handle_labels"]
    )
    assert evidence["notes_resizer_absent"] is True
    assert evidence["initial_layout_frozen"] is False
    assert evidence["frozen_layout_active"] is True
    initial_widths = evidence["initial_column_widths"]
    initial_lefts = evidence["initial_column_lefts"]
    frozen_widths = evidence["frozen_column_widths"]
    frozen_lefts = evidence["frozen_column_lefts"]
    assert frozen_widths == pytest.approx(initial_widths, abs=0.5)
    assert frozen_lefts == pytest.approx(initial_lefts, abs=0.5)
    assert evidence["frozen_right"] == pytest.approx(
        evidence["initial_right"],
        abs=0.5,
    )

    pointer_widths = evidence["pointer_column_widths"]
    pointer_lefts = evidence["pointer_column_lefts"]
    pointer_delta = evidence["column_resize_delta"]
    assert -8.5 <= evidence["requested_pointer_delta"] < -0.5
    assert evidence["column_resize_changes_width"] is True
    assert -8.5 <= pointer_delta < -0.5
    assert pointer_widths[1] - frozen_widths[1] == pytest.approx(
        pointer_delta,
        abs=0.5,
    )
    assert evidence["column_notes_delta"] == pytest.approx(
        -pointer_delta,
        abs=0.5,
    )
    assert pointer_widths[5] - frozen_widths[5] == pytest.approx(
        -pointer_delta,
        abs=0.5,
    )
    for index in (0, 2, 3, 4):
        assert pointer_widths[index] == pytest.approx(
            frozen_widths[index],
            abs=0.5,
        )
    assert pointer_lefts[:2] == pytest.approx(frozen_lefts[:2], abs=0.5)
    for index in (2, 3, 4, 5):
        assert pointer_lefts[index] - frozen_lefts[index] == pytest.approx(
            pointer_delta,
            abs=0.5,
        )
    assert evidence["pointer_right"] == pytest.approx(
        evidence["frozen_right"],
        abs=0.5,
    )

    keyboard_widths = evidence["keyboard_column_widths"]
    keyboard_lefts = evidence["keyboard_column_lefts"]
    keyboard_delta = evidence["keyboard_resize_delta"]
    assert 0.5 < keyboard_delta <= 8.5
    assert keyboard_widths[0] - pointer_widths[0] == pytest.approx(
        keyboard_delta,
        abs=0.5,
    )
    assert evidence["keyboard_notes_delta"] == pytest.approx(
        -keyboard_delta,
        abs=0.5,
    )
    assert keyboard_widths[5] - pointer_widths[5] == pytest.approx(
        -keyboard_delta,
        abs=0.5,
    )
    for index in (1, 2, 3, 4):
        assert keyboard_widths[index] == pytest.approx(
            pointer_widths[index],
            abs=0.5,
        )
    assert keyboard_lefts[0] == pytest.approx(pointer_lefts[0], abs=0.5)
    for index in (1, 2, 3, 4, 5):
        assert keyboard_lefts[index] - pointer_lefts[index] == pytest.approx(
            keyboard_delta,
            abs=0.5,
        )
    assert evidence["keyboard_right"] == pytest.approx(
        evidence["pointer_right"],
        abs=0.5,
    )

    viewport_widths = evidence["viewport_narrow_widths"]
    restored_widths = evidence["viewport_restored_widths"]
    viewport_delta = evidence["viewport_resize_amount"]
    assert viewport_delta > 0
    assert viewport_widths[1] - keyboard_widths[1] == pytest.approx(
        -viewport_delta,
        abs=0.75,
    )
    for index in (0, 2, 3, 4, 5):
        assert viewport_widths[index] == pytest.approx(
            keyboard_widths[index],
            abs=0.5,
        )
    assert evidence["viewport_narrow_right_span"] == pytest.approx(
        evidence["viewport_narrow_list_width"],
        abs=0.75,
    )
    assert restored_widths == pytest.approx(keyboard_widths, abs=0.5)
    assert evidence["viewport_restored_right"] == pytest.approx(
        evidence["keyboard_right"],
        abs=0.5,
    )

    notes_minimum_widths = evidence["notes_minimum_widths"]
    name_minimum_widths = evidence["name_minimum_widths"]
    assert notes_minimum_widths[5] == pytest.approx(
        evidence["notes_minimum"],
        abs=0.5,
    )
    assert name_minimum_widths[1] == pytest.approx(
        evidence["name_minimum"],
        abs=0.5,
    )
    for index in (0, 2, 3, 4):
        assert name_minimum_widths[index] == pytest.approx(
            keyboard_widths[index],
            abs=0.5,
        )
    expected_minimum = max(
        evidence["floor_minimum"],
        name_minimum_widths[0]
        + evidence["name_minimum"]
        + sum(name_minimum_widths[2:]),
    )
    assert evidence["effective_minimum"] == pytest.approx(
        expected_minimum,
        abs=0.75,
    )
    assert evidence["constrained_column_widths"] == pytest.approx(
        name_minimum_widths,
        abs=0.5,
    )
    assert evidence["constrained_grid_width"] == pytest.approx(
        evidence["effective_minimum"],
        abs=0.75,
    )
    assert evidence["constrained_right_span"] == pytest.approx(
        evidence["scroll_width"],
        abs=1.0,
    )
    assert _contrast(
        evidence["header_foreground"], evidence["header_background"]
    ) >= 4.5
    if forced:
        assert evidence["header_foreground"] == system_colors["HighlightText"]
        assert evidence["header_background"] == system_colors["Highlight"]
    assert evidence["header_texts"] == expected_headers
    assert evidence["header_cell_roles"] == ["columnheader"] * 6
    assert evidence["selection_header_label"] == "Selection"
    assert evidence["column_count"] == 6
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
    expected_columns = rows[0]["column_lefts"]
    for row in rows:
        assert row["role"] == "row"
        assert row["cell_roles"] == ["cell"] * 6
        assert row["checkbox_label"]
        assert row["name"]
        assert row["size"]
        assert row["primary"]
        assert row["secondary"]
        assert row["notes"]
        assert row["checkbox_width"] == pytest.approx(16.0, abs=0.5)
        assert row["checkbox_height"] == pytest.approx(16.0, abs=0.5)
        assert row["row_height"] == pytest.approx(24.0, abs=0.5)
        assert row["font_size"] == pytest.approx(12.0, abs=0.25)
        assert row["primary_height"] > 0
        assert row["primary_foreground"] == row["primary_alias_foreground"]
        assert row["primary_background"] == row["primary_alias_background"]
        assert row["cells_transparent"] is True
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
    return rows


def _assert_complete_gallery_matrix(report: dict[str, object]) -> None:
    assert set(report) == {
        "phase",
        "mode",
        "media",
        "cosmetic",
        "lifecycles",
        "intents",
        "controls",
        "lifecycle_progress",
        "control_contract",
        "motion",
        "icons",
    }
    lifecycles = report["lifecycles"]
    intents = report["intents"]
    controls = report["controls"]
    assert {
        row["key"]: (row["hue"], row["form"])
        for row in lifecycles
    } == _LIFECYCLE_CASES
    assert {
        row["key"]: (row["hue"], row["form"])
        for row in intents
    } == _INTENT_CASES
    assert {
        row["case"]: (
            row["lifecycle"],
            row["hue"],
            row["expected_frozen"],
        )
        for row in report["lifecycle_progress"]
    } == component_gallery_child._LIFECYCLE_PROGRESS_CASES
    assert {(row["control"], row["state"]) for row in controls} == {
        (control, state)
        for control in _CONTROL_KEYS
        for state in _CONTROL_STATES
    }
    assert len(lifecycles) == len(_LIFECYCLE_CASES)
    assert len(intents) == len(_INTENT_CASES)
    assert len(controls) == len(_CONTROL_KEYS) * len(_CONTROL_STATES)
    accent = report["control_contract"]["accent"]
    assert set(accent) == {"fill", "fill_hover", "fill_pressed", "foreground"}
    assert all(type(color) is str and color for color in accent.values())
    for row in (*lifecycles, *intents):
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
        assert row["rendered_form"] == row["form"]
        assert row["aliases_consumed"] is True
        assert row["foreground"] == row["alias_foreground"]
        assert row["background"] == row["alias_background"]
        assert row["indicator"] == row["alias_indicator"]
        assert not _painted_border(row["border_width"], row["border_style"])
        assert not _opaque_color(row["background"]) == (row["form"] == "text")
        if row["form"] == "fill":
            assert row["height"] == pytest.approx(18.0, abs=0.5)
    tri_state = report["control_contract"]["tri_state"]
    assert tri_state["aria_checked"] == "mixed"
    assert tri_state["indeterminate"] is True
    assert tri_state["cue_content"] not in {"", "none", "normal"}
    unchecked_width = _css_pixel_width(tri_state["unchecked_border_width"])
    mixed_width = _css_pixel_width(tri_state["mixed_border_width"])
    assert unchecked_width > 0
    assert mixed_width == pytest.approx(unchecked_width, abs=0.01)
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
    combobox = report["control_contract"]["combobox"]
    task_rail = report["control_contract"]["task_rail"]
    assert task_rail == {
        "card_count": 3,
        "outside_content_card": True,
        "left_of_work": True,
        "selected_count": 1,
        "current_count": 1,
        "selected_current_same_card": True,
        "transparent_boundaries": True,
        "selected_marker_width": 3.0,
        "current_marker_width": 3.0,
        "rest_marker_content": "none",
        "selected_marker_background": combobox["selected_pill_background"],
    }
    assert combobox["trigger_role"] == "combobox"
    assert combobox["popup_role"] == "listbox"
    assert combobox["expanded"] == "true"
    assert combobox["selected"] == "true"
    assert combobox["option_count"] == 3
    assert combobox["popup_width_delta"] == pytest.approx(0.0, abs=0.5)
    assert combobox["popup_within_viewport"] is True
    assert combobox["placement_clamped"] or (
        combobox["selected_center_error"] == pytest.approx(0.0, abs=1.0)
    )
    assert combobox["trigger_outline_style"] == "none"
    popup_border_width = float(
        combobox["popup_border_width"].removesuffix("px")
    )
    assert 0 < popup_border_width <= 1.0
    assert combobox["selected_pill_width"] == pytest.approx(3.0, abs=0.5)
    if report["media"]["forced"]:
        system_colors = report["icons"]["system_colors"]
        assert combobox["trigger_background_image"] == "none"
        assert combobox["popup_background"] == system_colors["Canvas"]
        assert combobox["popup_border"] == system_colors["ButtonBorder"]
        assert combobox["popup_shadow"] == "none"
        assert combobox["popup_backdrop_filter"] == "none"
        assert combobox["ordinary_option_background"] == system_colors["Canvas"]
        assert combobox["selected_option_background"] == system_colors["Highlight"]
        assert combobox["hovered_option_background"] == system_colors["Highlight"]
        assert combobox["pressed_option_background"] == system_colors["Highlight"]
    else:
        assert not _opaque_color(combobox["ordinary_option_background"])
        assert "linear-gradient" in combobox["trigger_background_image"]
        assert _opaque_color(combobox["popup_background"])
        assert combobox["selected_option_background"] == (
            combobox["hovered_option_background"]
        )
        assert combobox["pressed_option_background"] != (
            combobox["selected_option_background"]
        )
        expected_stroke_alpha = 0.2 if report["media"]["dark"] else 0.06
        assert _color_alpha(combobox["popup_border"]) == pytest.approx(
            expected_stroke_alpha
        )
        if report["media"]["dark"] and report["media"]["hdr"]:
            assert combobox["popup_shadow"] == "none"
        else:
            assert combobox["popup_shadow"] != "none"
        assert combobox["popup_backdrop_filter"] == "none"
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
            if control == "card":
                continue
            if (
                report["media"]["forced"]
                and control == "dropdown"
                and state in {"hover", "pressed"}
            ):
                continue
            if (
                report["media"]["forced"]
                and control in _FORCED_STATE_COLLAPSE_CONTROL_KEYS
                and (
                    state in {"hover", "pressed"}
                    or (
                        control in _SELECTED_TASK_CARD_KEYS
                        and state == "focused"
                    )
                )
            ):
                continue
            if control in _SELECTED_TASK_CARD_KEYS and state == "hover":
                continue
            assert _control_signature(rows[state]) != rest, (control, state)


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
            "visual_filter",
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
    ]
    assert painted, f"no painted control boundary: {row!r}"
    return max(
        _composited_contrast(color, row["surrounding"])
        for color in painted
    )


def _painted_border(width: str, style: str) -> bool:
    widths = _expand_css_sides(width)
    styles = _expand_css_sides(style)
    return any(
        (float(side_width.removesuffix("px")) > 0)
        and side_style not in {"none", "hidden"}
        for side_width, side_style in zip(widths, styles, strict=True)
    )


def _css_pixel_width(value: str) -> float:
    assert value.endswith("px")
    width = float(value.removesuffix("px"))
    assert math.isfinite(width)
    return width


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
    matches = list(_RGB.finditer(row["box_shadow"]))
    assert matches, f"focused control has no rendered ring: {row!r}"
    match = matches[-1]
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


def _focus_shadow_colors(row: dict[str, str]) -> list[str]:
    return _shadow_colors(row, inset=False)


def _inset_shadow_colors(row: dict[str, str]) -> list[str]:
    return _shadow_colors(row, inset=True)


def _shadow_colors(row: dict[str, str], *, inset: bool) -> list[str]:
    value = row["box_shadow"]
    matches = list(_RGB.finditer(value))
    return [
        match.group(0)
        for index, match in enumerate(matches)
        if (
            "inset"
            in value[
                match.end() : (
                    matches[index + 1].start()
                    if index + 1 < len(matches)
                    else len(value)
                )
            ]
        )
        is inset
    ]


def _opaque_color(value: str) -> bool:
    match = _RGB.fullmatch(value)
    if match is None:
        return False
    return match.group(4) is None or math.isclose(float(match.group(4)), 1.0)


def _color_alpha(value: str) -> float:
    match = _RGB.fullmatch(value)
    assert match is not None, value
    return 1.0 if match.group(4) is None else float(match.group(4))


def _color_rgb(value: str) -> tuple[float, float, float]:
    match = _RGB.fullmatch(value)
    assert match is not None, value
    return tuple(float(match.group(index)) for index in range(1, 4))


def _composited_contrast(foreground: str, background: str) -> float:
    alpha = _color_alpha(foreground)
    foreground_rgb = tuple(channel / 255.0 for channel in _color_rgb(foreground))
    background_rgb = _rgb(background)
    composite = tuple(
        source * alpha + base * (1.0 - alpha)
        for source, base in zip(foreground_rgb, background_rgb, strict=True)
    )
    low, high = sorted((_luminance(composite), _luminance(background_rgb)))
    return (high + 0.05) / (low + 0.05)


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
