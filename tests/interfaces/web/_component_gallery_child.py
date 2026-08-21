"""Installed-wheel child composition for the GUI Break 1 component gallery."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata
import importlib.resources
import json
import math
import sys
import threading
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch

from _headed_evidence import EvidencePaths, EvidencePublisher
from _startup_test_support import headed_command_extension


_ASSET_NAMES = (
    "index.html",
    "tokens.css",
    "components.css",
    "app.css",
    "file_row.js",
    "integrity.js",
    "plan.js",
)
_MEDIA_FEATURES: dict[str, tuple[tuple[str, str], ...]] = {
    "light": (
        ("prefers-color-scheme", "light"),
        ("forced-colors", "none"),
        ("prefers-reduced-motion", "no-preference"),
    ),
    "dark": (
        ("prefers-color-scheme", "dark"),
        ("forced-colors", "none"),
        ("prefers-reduced-motion", "no-preference"),
    ),
    "forced": (
        ("prefers-color-scheme", "dark"),
        ("forced-colors", "active"),
        ("prefers-reduced-motion", "no-preference"),
    ),
    "reduced": (
        ("prefers-color-scheme", "light"),
        ("forced-colors", "none"),
        ("prefers-reduced-motion", "reduce"),
    ),
}
_CONTROL_KEYS = (
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
)
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
_PLAN_ROW_CASE_KEYS = frozenset(
    {
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
        "blocked",
    }
)
_INTEGRITY_ROW_CASE_KEYS = frozenset(
    {"folder", *_INTEGRITY_CASES}
)
_PLAN_ROW_PRIMARY = {
    "plain": ("", "", ""),
    **{
        key: ("intent", key, form)
        for key, (_hue, form) in _INTENT_CASES.items()
    },
}
_INTEGRITY_ROW_PRIMARY = {
    "folder": ("integrity", "unverified", "text"),
    **{
        key: ("integrity", key, form)
        for key, (_hue, form) in _INTEGRITY_CASES.items()
    },
}
_LIFECYCLE_PROGRESS_CASES = {
    "running": ("executing", "accent", False),
    "resumed": ("executing", "accent", False),
    "paused": ("paused", "yellow", True),
    "canceled": ("canceled", "neutral", True),
}
_CONTROL_STATES = frozenset({"rest", "hover", "pressed", "disabled", "focused"})
_EXPECTED_MEDIA = {
    "light": {"dark": False, "forced": False, "reduced": False},
    "dark": {"dark": True, "forced": False, "reduced": False},
    "forced": {"dark": True, "forced": True, "reduced": False},
    "reduced": {"dark": False, "forced": False, "reduced": True},
}
_EXPECTED_THEME = {
    "light": "light",
    "dark": "dark",
    "forced": "dark",
    "reduced": "light",
}
_FAILURE_STAGES = frozenset(
    {
        "module_import",
        "page_setup",
        "semantic_matrix",
        "plan_matrix",
        "control_matrix",
        "pseudo_states",
        "measurement",
        "report",
    }
)
_FAILURE_TYPES = frozenset(
    {
        "AbortError",
        "Error",
        "RangeError",
        "ReferenceError",
        "SecurityError",
        "SyntaxError",
        "TypeError",
    }
)
_EVIDENCE_FAILURE_STAGES = _FAILURE_STAGES | {"child"}
_EVIDENCE_FAILURE_TYPES = _FAILURE_TYPES | {
    "AssertionError",
    "AttributeError",
    "DesktopStartupError",
    "NativeWindowUnavailable",
    "RuntimeError",
    "ScriptExecutionError",
    "ValueError",
}
_SYSTEM_COLOR_NAMES = frozenset(
    {
        "Canvas",
        "CanvasText",
        "Highlight",
        "HighlightText",
        "GrayText",
        "LinkText",
        "ButtonText",
        "ButtonBorder",
    }
)
_PSEUDO_CLASSES = {
    "hover": ["hover"],
    "pressed": ["hover", "active"],
    "focused": ["focus", "focus-visible"],
}
_EXPECTED_PSEUDO_TARGETS = [
    {
        "selector": f"#gallery-control-{control}-{state}",
        "classes": classes,
    }
    for control in _CONTROL_KEYS
    for state, classes in _PSEUDO_CLASSES.items()
]


def _expected_pseudo_targets(mode: str) -> list[dict[str, object]]:
    if mode not in _EXPECTED_THEME:
        raise ValueError("component gallery mode is invalid")
    return [
        *_EXPECTED_PSEUDO_TARGETS,
        {"selector": "#gallery-theme-option-hover", "classes": ["hover"]},
        {
            "selector": "#gallery-theme-option-pressed",
            "classes": ["hover", "active"],
        },
    ]


_CONTROL_REPORT_CHUNK_ROWS = 10
_CONTROL_REPORT_ROW_COUNT = len(_CONTROL_KEYS) * len(_CONTROL_STATES)
_CONTROL_REPORT_CHUNK_COUNT = math.ceil(
    _CONTROL_REPORT_ROW_COUNT / _CONTROL_REPORT_CHUNK_ROWS
)
_REPORT_PART_NAMES = (
    ("lifecycles", "intents")
    + ("controls",) * _CONTROL_REPORT_CHUNK_COUNT
    + ("lifecycle_progress", "control_contract", "motion", "icons")
)


class _Recorder:
    def __init__(self, evidence_paths: EvidencePaths, mode: str) -> None:
        self._publisher = EvidencePublisher(evidence_paths)
        self._lock = threading.Lock()
        self._initial: str | None = None
        self._post_ready_failure: dict[str, str] | None = None
        self._data: dict[str, Any] = {
            "schema_version": 3,
            "mode": mode,
            "startup_errors": [],
        }

    def set(self, name: str, value: Any) -> None:
        with self._lock:
            self._data[name] = value

    def append(self, name: str, value: Any) -> None:
        with self._lock:
            self._data.setdefault(name, []).append(value)

    def startup_error(self, message: str) -> None:
        del message
        self.append("startup_errors", {"type": "DesktopStartupError"})

    def write(self) -> None:
        with self._lock:
            failure = self._failure_locked()
            if self._initial == "failure":
                return
            if self._initial == "ready":
                if failure is not None and self._post_ready_failure is None:
                    self._post_ready_failure = failure
                return
            if failure is not None:
                self._publisher.publish_failure({"failure": failure})
                self._initial = "failure"
                return
            report = self._data.get("report")
            if type(report) is dict and report.get("phase") == "complete":
                self._publisher.publish_ready(dict(self._data))
                self._initial = "ready"

    def failure(self, stage: str, error: BaseException) -> None:
        with self._lock:
            failure = {
                "stage": stage if stage in _EVIDENCE_FAILURE_STAGES else "child",
                "type": _sanitized_error_type(error),
            }
            if self._initial == "failure":
                return
            if self._initial == "ready":
                if self._post_ready_failure is None:
                    self._post_ready_failure = failure
                return
            self._data["child_failure"] = failure
            self._publisher.publish_failure({"failure": failure})
            self._initial = "failure"

    @property
    def settled(self) -> bool:
        with self._lock:
            return self._initial is not None

    def finish(self, exit_code: int, *, host_returned: bool) -> None:
        with self._lock:
            payload: dict[str, object] = {
                "host_returned": host_returned,
                "exit_code": exit_code,
            }
            if self._post_ready_failure is not None:
                payload["post_ready_failure"] = dict(
                    self._post_ready_failure
                )
            self._publisher.publish_final(payload)

    def _failure_locked(self) -> dict[str, str] | None:
        report = self._data.get("report")
        if type(report) is dict and report.get("phase") == "failure":
            failure = report.get("failure")
            if type(failure) is dict:
                stage = failure.get("stage")
                return {
                    "stage": (
                        stage
                        if type(stage) is str
                        and stage in _EVIDENCE_FAILURE_STAGES
                        else "report"
                    ),
                    "type": _sanitized_type_name(failure.get("type")),
                }
        if "pseudo_state_failed" in self._data:
            return {"stage": "pseudo_states", "type": "Error"}
        if "media_emulation_failed" in self._data:
            return {"stage": "page_setup", "type": "Error"}
        native_failure = self._data.get("native_script_failure")
        if type(native_failure) is dict:
            return {
                "stage": "page_setup",
                "type": _sanitized_type_name(native_failure.get("type")),
            }
        return None


def _sanitized_error_type(error: BaseException) -> str:
    return _sanitized_type_name(type(error).__name__)


def _sanitized_type_name(value: object) -> str:
    if type(value) is str and value in _EVIDENCE_FAILURE_TYPES:
        return value
    return "Error"


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=tuple(_MEDIA_FEATURES), required=True)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--mutex", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--scenario", required=True, type=Path)
    return parser.parse_args()


def _runtime_identity() -> dict[str, object]:
    import namisync

    return {
        "executable": sys.executable,
        "namisync_file": str(Path(namisync.__file__).resolve()),
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("namisync", "pywebview", "pythonnet")
        },
    }


def _installed_asset_evidence() -> dict[str, dict[str, object]]:
    asset_root = importlib.resources.files("namisync.interfaces.web") / "assets"
    evidence: dict[str, dict[str, object]] = {}
    for name in _ASSET_NAMES:
        resource = asset_root / name
        content = resource.read_bytes()
        evidence[name] = {
            "path": str(Path(str(resource)).resolve()),
            "bytes_b64": base64.b64encode(content).decode("ascii"),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    return evidence


def _seeded_ui_state_owner(
    path: Path,
    mode: str,
    recorder: _Recorder,
):
    from namisync.interfaces.ui_state import (
        APPEARANCE_VALUE_VERSION,
        AppearanceValue,
        ThemeMode,
        UiStateOwner,
    )

    theme = (
        ThemeMode.LIGHT
        if mode in {"light", "reduced"}
        else ThemeMode.DARK
    )
    owner = UiStateOwner(path)
    try:
        result = owner.replace_section(
            "appearance",
            APPEARANCE_VALUE_VERSION,
            0,
            AppearanceValue(theme),
        )
    except BaseException:
        owner.close()
        raise
    recorder.set(
        "seeded_cosmetic",
        {
            "section": result.section,
            "value_version": result.value_version,
            "revision": result.revision,
            "dirty": result.dirty,
            "value": {"theme": result.value.theme.value},
            "disposition": result.disposition.value,
        },
    )
    return owner


def _test_report_spec(
    recorder: _Recorder,
    schedule_pseudos: object,
    expected_mode: str,
):
    from namisync.interfaces.web.commands import (
        CommandAccess,
        CommandPayloadError,
        CommandRetry,
        CommandSpec,
        CommandTimeout,
        FieldRequirement,
    )

    parts: list[tuple[str, object]] = []
    completed = False

    def validate(payload: object) -> dict[str, object]:
        if type(payload) is not dict or type(payload.get("phase")) is not str:
            raise CommandPayloadError("component gallery report is invalid")
        if payload["phase"] == "prepare" and set(payload) == {
            "phase",
            "targets",
        }:
            expected_targets = _expected_pseudo_targets(expected_mode)
            if payload["targets"] != expected_targets:
                raise CommandPayloadError("component gallery report is invalid")
            return dict(payload)
        if payload["phase"] == "failure" and set(payload) == {
            "phase",
            "failure",
        }:
            failure = payload["failure"]
            if (
                type(failure) is not dict
                or set(failure) != {"stage", "type"}
                or type(failure["stage"]) is not str
                or type(failure["type"]) is not str
                or failure["stage"] not in _FAILURE_STAGES
                or failure["type"] not in _FAILURE_TYPES
            ):
                raise CommandPayloadError("component gallery report is invalid")
            return dict(payload)
        if payload["phase"] == "part" and set(payload) == {
            "phase",
            "sequence",
            "name",
            "value",
        }:
            sequence = payload["sequence"]
            name = payload["name"]
            value = payload["value"]
            if (
                type(sequence) is not int
                or not 0 <= sequence < len(_REPORT_PART_NAMES)
                or type(name) is not str
                or name != _REPORT_PART_NAMES[sequence]
                or (
                    name
                    in {
                        "lifecycles",
                        "intents",
                        "lifecycle_progress",
                        "controls",
                    }
                    and type(value) is not list
                )
                or (
                    name in {"control_contract", "motion", "icons"}
                    and type(value) is not dict
                )
            ):
                raise CommandPayloadError("component gallery report is invalid")
            if name == "controls":
                chunk_index = sequence - 2
                remaining = (
                    _CONTROL_REPORT_ROW_COUNT
                    - chunk_index * _CONTROL_REPORT_CHUNK_ROWS
                )
                expected_rows = min(_CONTROL_REPORT_CHUNK_ROWS, remaining)
                if len(value) != expected_rows:
                    raise CommandPayloadError(
                        "component gallery report is invalid"
                    )
            return dict(payload)
        if payload["phase"] != "complete" or set(payload) != {
            "phase",
            "mode",
            "media",
            "cosmetic",
            "part_count",
        }:
            raise CommandPayloadError("component gallery report is invalid")
        if (
            type(payload["mode"]) is not str
            or type(payload["media"]) is not dict
            or type(payload["cosmetic"]) is not dict
            or type(payload["part_count"]) is not int
            or payload["part_count"] != len(_REPORT_PART_NAMES)
        ):
            raise CommandPayloadError("component gallery report is invalid")
        return dict(payload)

    def report(payload: object) -> object:
        nonlocal completed
        if type(payload) is not dict:
            raise TypeError("component gallery received unvalidated data")
        if payload["phase"] == "prepare":
            schedule_pseudos(payload["targets"])
            return {"accepted": True}
        if completed:
            raise CommandPayloadError("component gallery report is invalid")
        if payload["phase"] == "failure":
            recorder.set("report_part_count", len(parts))
            recorder.set("report", payload)
            recorder.write()
            return {"accepted": True}
        if payload["phase"] == "part":
            if payload["sequence"] != len(parts):
                raise CommandPayloadError("component gallery report is invalid")
            parts.append((payload["name"], payload["value"]))
            return {"accepted": True}
        if (
            len(parts) != len(_REPORT_PART_NAMES)
            or tuple(name for name, _value in parts) != _REPORT_PART_NAMES
        ):
            raise CommandPayloadError("component gallery report is invalid")
        controls = [
            row
            for name, value in parts
            if name == "controls" and type(value) is list
            for row in value
        ]
        values = {
            name: value
            for name, value in parts
            if name != "controls"
        }
        complete = {
            "phase": "complete",
            "mode": payload["mode"],
            "media": payload["media"],
            "cosmetic": payload["cosmetic"],
            "lifecycles": values["lifecycles"],
            "intents": values["intents"],
            "controls": controls,
            "lifecycle_progress": values["lifecycle_progress"],
            "control_contract": values["control_contract"],
            "motion": values["motion"],
            "icons": values["icons"],
        }
        if not _valid_complete_report(complete, expected_mode=expected_mode):
            raise CommandPayloadError("component gallery report is invalid")
        completed = True
        recorder.set("report", complete)
        recorder.write()
        return {"accepted": True}

    return CommandSpec(
        validate_payload=validate,
        handler=report,
        access=CommandAccess.READ_ONLY,
        command_id=FieldRequirement.FORBIDDEN,
        revision=FieldRequirement.FORBIDDEN,
        timeout=CommandTimeout.INTERACTIVE,
        retry=CommandRetry.NONE,
    )


def _valid_complete_report(
    payload: dict[str, object],
    *,
    expected_mode: str | None = None,
) -> bool:
    media = payload["media"]
    cosmetic = payload["cosmetic"]
    motion = payload["motion"]
    icons = payload["icons"]
    lifecycles = payload["lifecycles"]
    intents = payload["intents"]
    lifecycle_progress = payload["lifecycle_progress"]
    controls = payload["controls"]
    control_contract = payload["control_contract"]
    return (
        type(payload["mode"]) is str
        and payload["mode"] in _EXPECTED_MEDIA
        and (expected_mode is None or payload["mode"] == expected_mode)
        and set(media) == {"dark", "forced", "reduced", "hdr"}
        and all(type(media[name]) is bool for name in media)
        and all(
            media[name] == expected
            for name, expected in _EXPECTED_MEDIA[payload["mode"]].items()
        )
        and _valid_cosmetic_evidence(
            cosmetic,
            expected_theme=_EXPECTED_THEME[payload["mode"]],
        )
        and _valid_semantic_rows(lifecycles, _LIFECYCLE_CASES)
        and _valid_semantic_rows(intents, _INTENT_CASES)
        and _valid_lifecycle_progress(lifecycle_progress, payload["mode"])
        and _valid_control_rows(controls)
        and _valid_control_contract(control_contract)
        and set(motion)
        == {"nonessential_max_ms", "indeterminate_iteration_count"}
        and type(motion["nonessential_max_ms"]) in {int, float}
        and math.isfinite(motion["nonessential_max_ms"])
        and motion["nonessential_max_ms"] >= 0
        and type(motion["indeterminate_iteration_count"]) is str
        and motion["indeterminate_iteration_count"]
        == ("1" if payload["mode"] == "reduced" else "infinite")
        and _valid_icon_evidence(icons)
    )


def _valid_cosmetic_evidence(
    value: object,
    *,
    expected_theme: str,
) -> bool:
    if type(value) is not dict or set(value) != {
        "initial",
        "after_change",
        "replacement",
        "final",
        "page_theme",
        "selector",
    }:
        return False
    initial = value["initial"]
    after_change = value["after_change"]
    replacement = value["replacement"]
    final = value["final"]
    alternate_theme = "light" if expected_theme == "dark" else "dark"
    if not (
        _valid_cosmetic_snapshot(initial, expected_theme=expected_theme)
        and _valid_cosmetic_snapshot(
            after_change,
            expected_theme=alternate_theme,
        )
        and _valid_cosmetic_snapshot(
            replacement,
            expected_theme=expected_theme,
            replacement=True,
        )
        and _valid_cosmetic_snapshot(final, expected_theme=expected_theme)
    ):
        return False
    return (
        after_change["revision"] == initial["revision"] + 1
        and replacement["revision"] == after_change["revision"] + 1
        and replacement["disposition"] == "noop"
        and final["revision"] == replacement["revision"]
        and value["page_theme"] == expected_theme
        and value["selector"]
        == {
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
    )


def _valid_cosmetic_snapshot(
    value: object,
    *,
    expected_theme: str,
    replacement: bool = False,
) -> bool:
    keys = {"section", "value_version", "revision", "dirty", "value"}
    if replacement:
        keys.add("disposition")
    return (
        type(value) is dict
        and set(value) == keys
        and value["section"] == "appearance"
        and value["value_version"] == 1
        and type(value["revision"]) is int
        and 0 <= value["revision"] <= 9_007_199_254_740_991
        and type(value["dirty"]) is bool
        and type(value["value"]) is dict
        and set(value["value"]) == {"theme"}
        and value["value"]["theme"] == expected_theme
        and (
            not replacement
            or value["disposition"] in {"applied", "noop", "conflict"}
        )
    )


def _valid_semantic_rows(
    rows: object,
    expected: dict[str, tuple[str, str]],
) -> bool:
    keys = {
        "key",
        "text",
        "hue",
        "form",
        "rendered_form",
        "icon",
        "shape",
        "cue",
        "visible_text",
        "shape_content",
        "shape_color",
        "shape_display",
        "shape_visibility",
        "shape_opacity",
        "shape_width",
        "shape_height",
        "height",
        "foreground",
        "background",
        "indicator",
        "border_width",
        "border_style",
        "alias_foreground",
        "alias_background",
        "alias_indicator",
        "aliases_consumed",
        "large_text",
        "icon_color",
        "mask_image",
    }
    return (
        type(rows) is list
        and len(rows) == len(expected)
        and all(
            type(row) is dict
            and set(row) == keys
            and type(row["key"]) is str
            and row["key"] in expected
            and (row["hue"], row["form"]) == expected[row["key"]]
            and row["rendered_form"] == row["form"]
            and _transparent_css_color(row["background"])
            == (row["form"] == "text")
            and all(
                type(row[name]) is str and bool(row[name])
                for name in keys
                - {
                    "key",
                    "aliases_consumed",
                    "large_text",
                    "shape_width",
                    "shape_height",
                    "height",
                }
            )
            and all(
                type(row[name]) in {int, float}
                and math.isfinite(row[name])
                and row[name] >= 0
                for name in ("shape_width", "shape_height", "height")
            )
            and (
                row["form"] != "fill"
                or math.isclose(row["height"], 20.0, abs_tol=0.5)
            )
            and _css_pixel_width(row["border_width"]) == 0
            and row["aliases_consumed"] is True
            and type(row["large_text"]) is bool
            for row in rows
        )
        and {row["key"] for row in rows} == set(expected)
    )


def _valid_lifecycle_progress(value: object, mode: object) -> bool:
    keys = {
        "case",
        "lifecycle",
        "hue",
        "expected_frozen",
        "motion_frozen",
        "track_background",
        "fill_background",
        "animation_name",
        "animation_duration",
        "animation_iteration_count",
        "animation_play_state",
    }
    if type(value) is not list or len(value) != len(_LIFECYCLE_PROGRESS_CASES):
        return False
    for row in value:
        if (
            type(row) is not dict
            or set(row) != keys
            or type(row["case"]) is not str
            or row["case"] not in _LIFECYCLE_PROGRESS_CASES
        ):
            return False
        lifecycle, hue, frozen = _LIFECYCLE_PROGRESS_CASES[row["case"]]
        expected_motion = frozen or mode == "reduced"
        if (
            row["lifecycle"] != lifecycle
            or row["hue"] != hue
            or row["expected_frozen"] is not frozen
            or row["motion_frozen"] is not expected_motion
            or any(
                type(row[name]) is not str or not row[name]
                for name in keys
                - {
                    "case",
                    "expected_frozen",
                    "motion_frozen",
                }
            )
        ):
            return False
    return {row["case"] for row in value} == set(_LIFECYCLE_PROGRESS_CASES)


def _valid_control_rows(rows: object) -> bool:
    keys = {
        "control",
        "state",
        "label",
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
        "surrounding",
        "visual_filter",
        "opacity",
        "transform",
        "transition_duration",
        "animation_duration",
        "animation_name",
    }
    expected = {
        (control, state)
        for control in _CONTROL_KEYS
        for state in _CONTROL_STATES
    }
    if not (
        type(rows) is list
        and len(rows) == len(expected)
        and all(
            type(row) is dict
            and set(row) == keys
            and all(type(row[name]) is str for name in keys)
            for row in rows
        )
        and {(row["control"], row["state"]) for row in rows} == expected
    ):
        return False
    by_control_state = {
        (row["control"], row["state"]): row for row in rows
    }
    return (
        all(
            _valid_control_boundary_widths(by_control_state, state)
            for state in _CONTROL_STATES
        )
        and all(
            by_control_state[(control, state)]["background"]
            == by_control_state[("button_primary", state)]["background"]
            for control in (
                "tri_state_checkbox",
                "toggle",
                "segmented_control",
            )
            for state in ("rest", "hover", "pressed")
        )
    )


def _valid_control_boundary_widths(
    rows: dict[tuple[str, str], dict[str, str]],
    state: str,
) -> bool:
    button = _css_pixel_width(rows[("button", state)]["border_width"])
    checkbox = _css_pixel_width(
        rows[("tri_state_checkbox", state)]["border_width"]
    )
    text_input = _css_pixel_width(
        rows[("text_input", state)]["border_width"]
    )
    return (
        button is not None
        and button > 0
        and checkbox is not None
        and math.isclose(checkbox, button, abs_tol=0.01)
        and text_input is not None
        and text_input >= checkbox * 1.75
        and text_input <= checkbox * 3.01
    )


def _css_pixel_width(value: object) -> float | None:
    if type(value) is not str or not value.endswith("px"):
        return None
    try:
        width = float(value[:-2])
    except ValueError:
        return None
    if not math.isfinite(width) or width < 0:
        return None
    return width


def _transparent_css_color(value: object) -> bool:
    if type(value) is not str:
        return False
    normalized = "".join(value.lower().split())
    if normalized == "transparent":
        return True
    if normalized.startswith("rgba(") and normalized.endswith(")"):
        try:
            return float(normalized[:-1].rsplit(",", 1)[1]) == 0
        except (IndexError, ValueError):
            return False
    if "/" in normalized and normalized.endswith(")"):
        alpha = normalized[:-1].rsplit("/", 1)[1]
        try:
            return float(alpha.removesuffix("%")) == 0
        except ValueError:
            return False
    return False


def _equal_positive_css_pixel_widths(left: object, right: object) -> bool:
    left_width = _css_pixel_width(left)
    right_width = _css_pixel_width(right)
    return (
        left_width is not None
        and left_width > 0
        and right_width is not None
        and math.isclose(left_width, right_width, abs_tol=0.01)
    )


def _valid_control_contract(value: object) -> bool:
    if type(value) is not dict or set(value) != {
        "accent",
        "tri_state",
        "dialog_exit",
        "segmented",
        "combobox",
        "task_rail",
        "file_list",
        "integrity_list",
    }:
        return False
    accent = value["accent"]
    tri_state = value["tri_state"]
    dialog_exit = value["dialog_exit"]
    segmented = value["segmented"]
    combobox = value["combobox"]
    task_rail = value["task_rail"]
    file_list = value["file_list"]
    integrity_list = value["integrity_list"]
    return (
        type(accent) is dict
        and set(accent) == {"fill", "fill_hover", "fill_pressed", "foreground"}
        and all(type(color) is str and bool(color) for color in accent.values())
        and type(tri_state) is dict
        and set(tri_state)
        == {
            "aria_checked",
            "indeterminate",
            "cue_content",
            "unchecked_border",
            "unchecked_border_width",
            "mixed_background",
            "mixed_foreground",
            "mixed_border",
            "mixed_border_width",
        }
        and tri_state["aria_checked"] == "mixed"
        and tri_state["indeterminate"] is True
        and type(tri_state["cue_content"]) is str
        and tri_state["cue_content"] not in {"", "none", "normal"}
        and all(
            type(tri_state[name]) is str and bool(tri_state[name])
            for name in (
                "unchecked_border",
                "unchecked_border_width",
                "mixed_background",
                "mixed_foreground",
                "mixed_border",
                "mixed_border_width",
            )
        )
        and _equal_positive_css_pixel_widths(
            tri_state["unchecked_border_width"],
            tri_state["mixed_border_width"],
        )
        and type(dialog_exit) is dict
        and set(dialog_exit)
        == {"opened", "retained_while_closing", "faded", "closed"}
        and all(value is True for value in dialog_exit.values())
        and segmented
        == {
            "group_role": "radiogroup",
            "selected_role": "radio",
            "selected_checked": "true",
            "unselected_role": "radio",
            "unselected_checked": "false",
        }
        and type(combobox) is dict
        and set(combobox)
        == {
            "trigger_role",
            "popup_role",
            "expanded",
            "selected",
            "option_count",
            "popup_width_delta",
            "popup_within_viewport",
            "selected_center_error",
            "placement_clamped",
            "trigger_background_image",
            "trigger_outline_style",
            "popup_background",
            "popup_border",
            "popup_border_width",
            "popup_shadow",
            "popup_backdrop_filter",
            "ordinary_option_background",
            "selected_option_background",
            "hovered_option_background",
            "pressed_option_background",
            "selected_pill_width",
            "selected_pill_background",
        }
        and combobox["trigger_role"] == "combobox"
        and combobox["popup_role"] == "listbox"
        and combobox["expanded"] == "true"
        and combobox["selected"] == "true"
        and combobox["option_count"] == 3
        and type(combobox["popup_width_delta"]) in {int, float}
        and 0 <= combobox["popup_width_delta"] < 0.5
        and combobox["popup_within_viewport"] is True
        and type(combobox["selected_center_error"]) in {int, float}
        and combobox["selected_center_error"] >= 0
        and type(combobox["placement_clamped"]) is bool
        and all(
            type(combobox[name]) is str and bool(combobox[name])
            for name in (
                "trigger_background_image",
                "trigger_outline_style",
                "popup_background",
                "popup_border",
                "popup_border_width",
                "popup_shadow",
                "popup_backdrop_filter",
                "ordinary_option_background",
                "selected_option_background",
                "hovered_option_background",
                "pressed_option_background",
                "selected_pill_background",
            )
        )
        and type(combobox["selected_pill_width"]) in {int, float}
        and 2.5 <= combobox["selected_pill_width"] <= 3.5
        and combobox["selected_option_background"]
        == combobox["hovered_option_background"]
        and type(task_rail) is dict
        and set(task_rail)
        == {
            "card_count",
            "outside_content_card",
            "left_of_work",
            "selected_count",
            "current_count",
            "selected_current_same_card",
            "transparent_boundaries",
            "selected_marker_width",
            "current_marker_width",
            "rest_marker_content",
            "selected_marker_background",
        }
        and task_rail["card_count"] == 3
        and task_rail["outside_content_card"] is True
        and task_rail["left_of_work"] is True
        and task_rail["selected_count"] == 1
        and task_rail["current_count"] == 1
        and task_rail["selected_current_same_card"] is True
        and task_rail["transparent_boundaries"] is True
        and type(task_rail["selected_marker_width"]) in {int, float}
        and 2.5 <= task_rail["selected_marker_width"] <= 3.5
        and type(task_rail["current_marker_width"]) in {int, float}
        and 2.5 <= task_rail["current_marker_width"] <= 3.5
        and task_rail["rest_marker_content"] in {"none", "normal"}
        and type(task_rail["selected_marker_background"]) is str
        and bool(task_rail["selected_marker_background"])
        and _valid_plan_evidence(file_list)
        and _valid_integrity_evidence(integrity_list)
    )


def _valid_file_list_evidence(
    value: object,
    *,
    expected_cases: frozenset[str],
    expected_headers: list[str],
) -> bool:
    keys = {
        "table_role",
        "header_role",
        "body_role",
        "gallery_uses_work_area",
        "gallery_fills_work_area",
        "collapse_hides_children",
        "collapse_restores_children",
        "child_selection_selects_folder",
        "child_selection_restores_mixed",
        "master_initially_mixed",
        "master_selects_all",
        "master_deselects_all",
        "master_label",
        "resize_handle_count",
        "column_resize_changes_width",
        "column_resize_delta",
        "header_foreground",
        "header_background",
        "header_texts",
        "header_cell_roles",
        "selection_header_label",
        "column_count",
        "row_count",
        "body_child_count",
        "checkbox_count",
        "body_ends_at_last_row",
        "body_height_matches_rows",
        "horizontal_overflow",
        "overflow_x",
        "client_width",
        "scroll_width",
        "rows",
    }
    row_keys = {
        "case",
        "role",
        "cell_roles",
        "checkbox_label",
        "checkbox_checked",
        "checkbox_disabled",
        "checkbox_indeterminate",
        "checkbox_aria_checked",
        "checkbox_width",
        "checkbox_height",
        "depth",
        "folder",
        "expanded",
        "name",
        "size",
        "primary",
        "primary_tone",
        "primary_key",
        "primary_form",
        "secondary",
        "secondary_tone",
        "secondary_key",
        "notes",
        "background",
        "primary_foreground",
        "primary_background",
        "primary_height",
        "primary_alias_foreground",
        "primary_alias_background",
        "secondary_color",
        "secondary_alias_color",
        "cell_backgrounds",
        "cells_transparent",
        "column_lefts",
        "name_padding_left",
        "row_height",
        "font_size",
    }
    if type(value) is not dict or set(value) != keys:
        return False
    rows = value["rows"]
    expected_count = len(expected_cases)
    if (
        value["table_role"] != "table"
        or value["header_role"] != "row"
        or value["body_role"] != "rowgroup"
        or value["gallery_uses_work_area"] is not True
        or value["gallery_fills_work_area"] is not True
        or value["collapse_hides_children"] is not True
        or value["collapse_restores_children"] is not True
        or value["child_selection_selects_folder"] is not True
        or value["child_selection_restores_mixed"] is not True
        or value["master_initially_mixed"] is not True
        or value["master_selects_all"] is not True
        or value["master_deselects_all"] is not True
        or type(value["master_label"]) is not str
        or not value["master_label"].startswith("Select all ")
        or value["resize_handle_count"] != 6
        or value["column_resize_changes_width"] is not True
        or type(value["column_resize_delta"]) not in {int, float}
        or not math.isfinite(value["column_resize_delta"])
        or not 39 < value["column_resize_delta"] < 41
        or type(value["header_foreground"]) is not str
        or not value["header_foreground"]
        or type(value["header_background"]) is not str
        or not value["header_background"]
        or value["header_texts"] != expected_headers
        or value["header_cell_roles"] != ["columnheader"] * 6
        or value["selection_header_label"] != "Selection"
        or value["column_count"] != 6
        or value["row_count"] != expected_count
        or value["body_child_count"] != expected_count
        or value["checkbox_count"] != expected_count
        or value["body_ends_at_last_row"] is not True
        or value["body_height_matches_rows"] is not True
        or value["horizontal_overflow"] is not True
        or value["overflow_x"] != "auto"
        or type(value["client_width"]) not in {int, float}
        or type(value["scroll_width"]) not in {int, float}
        or not math.isfinite(value["client_width"])
        or not math.isfinite(value["scroll_width"])
        or not 0 < value["client_width"] < value["scroll_width"]
        or type(rows) is not list
        or len(rows) != expected_count
    ):
        return False
    for row in rows:
        if type(row) is not dict or set(row) != row_keys:
            return False
        primary_tone = row["primary_tone"]
        primary_key = row["primary_key"]
        secondary_tone = row["secondary_tone"]
        secondary_key = row["secondary_key"]
        if (
            type(row["case"]) is not str
            or row["role"] != "row"
            or row["cell_roles"] != ["cell"] * 6
            or type(row["checkbox_label"]) is not str
            or not row["checkbox_label"]
            or type(row["checkbox_checked"]) is not bool
            or type(row["checkbox_disabled"]) is not bool
            or type(row["checkbox_indeterminate"]) is not bool
            or row["checkbox_aria_checked"] not in {None, "mixed"}
            or any(
                type(row[name]) not in {int, float}
                or not math.isfinite(row[name])
                or row[name] <= 0
                for name in (
                    "checkbox_width",
                    "checkbox_height",
                    "row_height",
                    "font_size",
                )
            )
            or type(row["depth"]) is not int
            or row["depth"] < 0
            or type(row["folder"]) is not bool
            or row["expanded"] not in {None, "true", "false"}
            or (row["folder"] and row["expanded"] is None)
            or (not row["folder"] and row["expanded"] is not None)
            or any(
                type(row[name]) is not str or not row[name]
                for name in (
                    "name",
                    "size",
                    "primary",
                    "secondary",
                    "notes",
                    "background",
                    "primary_foreground",
                    "primary_background",
                    "primary_alias_foreground",
                    "primary_alias_background",
                    "secondary_color",
                    "secondary_alias_color",
                )
            )
            or primary_tone not in {"", "intent", "integrity"}
            or secondary_tone not in {"", "intent", "integrity"}
            or type(primary_key) is not str
            or type(secondary_key) is not str
            or (primary_tone == "") != (primary_key == "")
            or (secondary_tone == "") != (secondary_key == "")
            or row["primary_form"] not in {"", "text", "fill"}
            or (primary_tone == "") != (row["primary_form"] == "")
            or (primary_tone == "intent" and primary_key not in _INTENT_CASES)
            or (secondary_tone == "intent" and secondary_key not in _INTENT_CASES)
            or (
                primary_tone == "integrity"
                and primary_key not in _INTEGRITY_CASES
            )
            or (
                secondary_tone == "integrity"
                and secondary_key not in _INTEGRITY_CASES
            )
            or type(row["primary_height"]) not in {int, float}
            or not math.isfinite(row["primary_height"])
            or row["primary_height"] <= 0
            or row["primary_foreground"] != row["primary_alias_foreground"]
            or row["primary_background"] != row["primary_alias_background"]
            or _transparent_css_color(row["primary_background"])
            != (row["primary_form"] != "fill")
            or (
                row["primary_form"] == "fill"
                and not math.isclose(row["primary_height"], 20.0, abs_tol=0.5)
            )
            or type(row["cell_backgrounds"]) is not list
            or len(row["cell_backgrounds"]) != 6
            or not all(
                type(background) is str and bool(background)
                for background in row["cell_backgrounds"]
            )
            or not all(
                _transparent_css_color(background)
                for background in row["cell_backgrounds"]
            )
            or row["cells_transparent"] is not True
            or type(row["column_lefts"]) is not list
            or len(row["column_lefts"]) != 6
            or not all(
                type(position) in {int, float} and math.isfinite(position)
                for position in row["column_lefts"]
            )
            or not all(
                left < right
                for left, right in zip(
                    row["column_lefts"], row["column_lefts"][1:]
                )
            )
            or type(row["name_padding_left"]) not in {int, float}
            or not math.isfinite(row["name_padding_left"])
            or row["name_padding_left"] < 0
            or not math.isclose(row["font_size"], 12.0, abs_tol=0.25)
        ):
            return False
    return {row["case"] for row in rows} == expected_cases


def _valid_plan_evidence(value: object) -> bool:
    if not _valid_file_list_evidence(
        value,
        expected_cases=_PLAN_ROW_CASE_KEYS,
        expected_headers=[
            "",
            "Filename",
            "Size",
            "Operation / status",
            "Checksum",
            "Notes",
        ],
    ):
        return False
    return all(
        (
            row["primary_tone"],
            row["primary_key"],
            row["primary_form"],
        )
        == _PLAN_ROW_PRIMARY[row["case"]]
        and row["secondary_tone"] == ""
        and (row["secondary"] == "—" or len(row["secondary"]) == 8)
        for row in value["rows"]
    )


def _valid_integrity_evidence(value: object) -> bool:
    if not _valid_file_list_evidence(
        value,
        expected_cases=_INTEGRITY_ROW_CASE_KEYS,
        expected_headers=[
            "",
            "Filename",
            "Size",
            "Presence",
            "Checksum",
            "Notes",
        ],
    ):
        return False
    return all(
        (
            row["primary_tone"],
            row["primary_key"],
            row["primary_form"],
        )
        == _INTEGRITY_ROW_PRIMARY[row["case"]]
        and row["secondary_tone"] == ""
        and (row["secondary"] == "—" or len(row["secondary"]) == 8)
        for row in value["rows"]
    )


def _valid_icon_evidence(value: object) -> bool:
    if type(value) is not dict or set(value) != {
        "registry_frozen",
        "registry_names",
        "all_registry_created",
        "all_current_color",
        "all_mask_images",
        "unexpected_svg_count",
        "unexpected_path_count",
        "sizes",
        "state_samples",
        "mask_images",
        "system_colors",
    }:
        return False
    return (
        all(
            type(value[name]) is bool
            for name in (
                "registry_frozen",
                "all_registry_created",
                "all_current_color",
                "all_mask_images",
            )
        )
        and all(
            type(value[name]) is int
            for name in ("unexpected_svg_count", "unexpected_path_count")
        )
        and type(value["registry_names"]) is list
        and all(type(name) is str for name in value["registry_names"])
        and type(value["sizes"]) is list
        and all(
            type(item) is dict
            and set(item) == {"size", "width", "height"}
            and all(type(part) is str for part in item.values())
            for item in value["sizes"]
        )
        and type(value["state_samples"]) is list
        and len(value["state_samples"]) == len(_CONTROL_STATES)
        and all(
            type(item) is dict
            and set(item) == {
                "state",
                "icon_color",
                "control_color",
                "control_background",
                "inherits",
            }
            and type(item["state"]) is str
            and type(item["icon_color"]) is str
            and type(item["control_color"]) is str
            and type(item["control_background"]) is str
            and type(item["inherits"]) is bool
            for item in value["state_samples"]
        )
        and {item["state"] for item in value["state_samples"]}
        == _CONTROL_STATES
        and type(value["mask_images"]) is dict
        and all(
            type(name) is str and type(item) is str
            for name, item in value["mask_images"].items()
        )
        and type(value["system_colors"]) is dict
        and set(value["system_colors"]) == _SYSTEM_COLOR_NAMES
        and all(
            type(name) is str and type(item) is str
            for name, item in value["system_colors"].items()
        )
    )


def _media_parameters(mode: str) -> str:
    return json.dumps(
        {
            "media": "screen",
            "features": [
                {"name": name, "value": value}
                for name, value in _MEDIA_FEATURES[mode]
            ],
        },
        separators=(",", ":"),
    )


def _schedule_pseudo_states(
    native: object,
    core: object,
    targets: list[dict[str, object]],
    recorder: _Recorder,
    retained_delegates: list[object],
) -> None:
    from System import Action

    def on_ui(callback: object) -> None:
        action = Action(callback)
        retained_delegates.append(action)
        native.BeginInvoke(action)

    def protocol(
        method: str,
        parameters: dict[str, object],
        callback: object,
    ) -> None:
        task = core.CallDevToolsProtocolMethodAsync(
            method,
            json.dumps(parameters, separators=(",", ":")),
        )

        def completed() -> None:
            if task.IsFaulted or task.IsCanceled:
                recorder.set("pseudo_state_failed", method)
                recorder.write()
                return
            try:
                value = json.loads(str(task.Result))
            except (TypeError, ValueError):
                recorder.set("pseudo_state_failed", method)
                recorder.write()
                return
            on_ui(lambda: callback(value))

        completion = Action(completed)
        retained_delegates.append(completion)
        task.GetAwaiter().OnCompleted(completion)

    def finish() -> None:
        recorder.set("pseudo_state_count", len(targets))
        _execute_script_checked(
            core,
            "globalThis.__namiGalleryPseudoReady = true;",
            stage="pseudo_ready_marker",
            recorder=recorder,
            retained_delegates=retained_delegates,
        )

    def apply_target(index: int, root_id: int) -> None:
        if index == len(targets):
            finish()
            return
        target = targets[index]

        def force(result: dict[str, object]) -> None:
            node_id = result.get("nodeId")
            if type(node_id) is not int or node_id <= 0:
                recorder.set("pseudo_state_failed", "DOM.querySelector")
                recorder.write()
                return
            protocol(
                "CSS.forcePseudoState",
                {
                    "nodeId": node_id,
                    "forcedPseudoClasses": target["classes"],
                },
                lambda _result: apply_target(index + 1, root_id),
            )

        protocol(
            "DOM.querySelector",
            {"nodeId": root_id, "selector": target["selector"]},
            force,
        )

    def document_ready(result: dict[str, object]) -> None:
        root = result.get("root")
        root_id = root.get("nodeId") if type(root) is dict else None
        if type(root_id) is not int or root_id <= 0:
            recorder.set("pseudo_state_failed", "DOM.getDocument")
            recorder.write()
            return
        apply_target(0, root_id)

    def css_enabled(_result: dict[str, object]) -> None:
        protocol("DOM.getDocument", {"depth": 0}, document_ready)

    def dom_enabled(_result: dict[str, object]) -> None:
        protocol("CSS.enable", {}, css_enabled)

    on_ui(lambda: protocol("DOM.enable", {}, dom_enabled))


def _execute_script_checked(
    core: object,
    source: str,
    *,
    stage: str,
    recorder: _Recorder,
    retained_delegates: list[object],
) -> None:
    from System import Action

    task = core.ExecuteScriptAsync(source)

    def completed() -> None:
        if task.IsFaulted or task.IsCanceled:
            recorder.set(
                "native_script_failure",
                {"stage": stage, "type": "ScriptExecutionError"},
            )
            recorder.write()

    completion = Action(completed)
    retained_delegates.append(completion)
    task.GetAwaiter().OnCompleted(completion)


def _run(arguments: argparse.Namespace, recorder: _Recorder) -> int:
    from namisync.interfaces.web import host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths

    scenario = arguments.scenario.resolve(strict=True).read_text(encoding="utf-8")
    recorder.set("runtime", _runtime_identity())
    recorder.set("installed_assets", _installed_asset_evidence())
    recorder.set("media_parameters", json.loads(_media_parameters(arguments.mode)))
    original_configure = host._configure_window_security
    original_background = host._opaque_window_background
    retained_delegates: list[object] = []
    pseudo_scheduler: dict[str, object] = {}

    def create_seeded_ui_state(path: Path):
        return _seeded_ui_state_owner(path, arguments.mode, recorder)

    def record_initial_background(*args: object, **kwargs: object) -> str:
        if len(args) != 1 or kwargs:
            raise RuntimeError("component gallery initial appearance is unavailable")
        snapshot = args[0]
        recorder.set(
            "native_initial_cosmetic",
            {
                "section": snapshot.section,
                "value_version": snapshot.value_version,
                "revision": snapshot.revision,
                "dirty": snapshot.dirty,
                "value": {"theme": snapshot.value.theme.value},
            },
        )
        value = original_background(*args, **kwargs)
        recorder.set("initial_background_color", value)
        return value

    def extension(_document: object, _registry: object) -> dict[str, object]:
        def schedule(targets: list[dict[str, object]]) -> None:
            callback = pseudo_scheduler.get("value")
            if not callable(callback):
                raise RuntimeError("component gallery pseudo-state owner is pending")
            callback(targets)

        return {
            "test_report": _test_report_spec(
                recorder,
                schedule,
                arguments.mode,
            )
        }

    def observe_composition(production: object, combined: object) -> None:
        recorder.set("production_command_names", sorted(production))
        recorder.set("combined_command_names", sorted(combined))
        recorder.set("combined_mapping_type", type(combined).__name__)

    def observe_dispatcher(value: object) -> None:
        recorder.set(
            "dispatcher_type",
            f"{type(value).__module__}.{type(value).__qualname__}",
        )

    def configure(
        window: object,
        trusted_url: str,
        document: object,
        renderer_callback: object,
    ) -> None:
        recorder.set("trusted_url", trusted_url)
        original_configure(
            window,
            trusted_url,
            document,
            renderer_callback,
        )

        def inject_after_load() -> None:
            from System import Action

            native = window.native
            if native is None:
                recorder.set(
                    "native_script_failure",
                    {
                        "stage": "loaded_ui_dispatch",
                        "type": "NativeWindowUnavailable",
                    },
                )
                recorder.write()
                return

            def begin_injection_on_ui() -> None:
                try:
                    if native.InvokeRequired:
                        raise RuntimeError(
                            "component gallery UI dispatch did not reach the UI thread"
                        )
                    core = native.browser.webview.CoreWebView2
                    pseudo_scheduler["value"] = lambda targets: (
                        _schedule_pseudo_states(
                            native,
                            core,
                            targets,
                            recorder,
                            retained_delegates,
                        )
                    )
                    task = core.CallDevToolsProtocolMethodAsync(
                        "Emulation.setEmulatedMedia",
                        _media_parameters(arguments.mode),
                    )

                    def after_media() -> None:
                        if task.IsFaulted or task.IsCanceled:
                            recorder.set("media_emulation_failed", True)
                            recorder.write()
                            return

                        def inject() -> None:
                            _execute_script_checked(
                                core,
                                scenario,
                                stage="scenario_injection",
                                recorder=recorder,
                                retained_delegates=retained_delegates,
                            )

                        injection = Action(inject)
                        retained_delegates.append(injection)
                        native.BeginInvoke(injection)

                    completion = Action(after_media)
                    retained_delegates.append(completion)
                    task.GetAwaiter().OnCompleted(completion)
                except BaseException as error:
                    recorder.set(
                        "native_script_failure",
                        {
                            "stage": "loaded_ui_dispatch",
                            "type": type(error).__name__,
                        },
                    )
                    recorder.write()

            injection_start = Action(begin_injection_on_ui)
            retained_delegates.append(injection_start)
            native.BeginInvoke(injection_start)

        window.events.loaded += inject_after_load

    with ExitStack() as stack:
        stack.enter_context(
            headed_command_extension(
                host,
                extension,
                observe_composition=observe_composition,
                observe_dispatcher=observe_dispatcher,
            )
        )
        stack.enter_context(
            patch.object(host, "_configure_window_security", configure)
        )
        stack.enter_context(
            patch.object(host, "_ui_state_owner", create_seeded_ui_state)
        )
        stack.enter_context(
            patch.object(
                host,
                "_opaque_window_background",
                record_initial_background,
            )
        )
        exit_code = host.run_desktop(
            AppPaths.from_root(arguments.data_dir),
            DesktopInstanceIdentity(arguments.mutex, arguments.title),
            startup_error=recorder.startup_error,
        )

    if not recorder.settled:
        recorder.failure(
            "child",
            RuntimeError("host returned before gallery evidence completed"),
        )
    recorder.finish(exit_code, host_returned=True)
    return exit_code


def main() -> int:
    arguments = _parse_arguments()
    recorder = _Recorder(
        EvidencePaths(arguments.evidence_dir.resolve()),
        arguments.mode,
    )
    try:
        return _run(arguments, recorder)
    except BaseException as error:
        recorder.failure("child", error)
        recorder.finish(1, host_returned=False)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
