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
    "execution_confirmation.js",
    "inventory_review.js",
    "table_columns.js",
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
    "button_clear",
    "dropdown",
    "tri_state_checkbox",
    "progress_determinate",
    "progress_indeterminate",
    "text_input",
    "toggle",
    "toggle_off",
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
    "capacity": ("yellow", "fill"),
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
        "copying",
        "completed",
        "capacity",
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
    {"folder", "verifying", "completed", *_INTEGRITY_CASES}
)
_PLAN_ROW_PRIMARY = {
    "plain": ("", "", ""),
    "copying": ("lifecycle", "executing", "progress"),
    "completed": ("lifecycle", "completed", "text"),
    "capacity": ("lifecycle", "capacity", "fill"),
    **{
        key: ("intent", key, form)
        for key, (_hue, form) in _INTENT_CASES.items()
    },
}
_INTEGRITY_ROW_PRIMARY = {
    "folder": ("integrity", "unverified", "text"),
    "verifying": ("lifecycle", "verifying", "progress"),
    "completed": ("lifecycle", "completed", "text"),
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
_FAILURE_STEPS = frozenset(
    {
        "not_started",
        "plan_list_construction",
        "plan_review_construction",
        "inventory_panel",
        "plan_review_initial_render",
        "plan_review_static_contract",
        "plan_review_filter_spacing",
        "plan_review_path_alignment",
        "plan_review_reset_geometry",
        "plan_review_status_typography",
        "plan_review_caption_typography",
        "plan_review_setting_alignment",
        "plan_review_path_label_gap",
        "plan_review_setting_states",
        "plan_review_session_states",
        "plan_review_filter_menu",
        "plan_review_row_menu",
        "diagnostic_default_folded_empty",
        "diagnostic_default_folded_populated",
        "diagnostic_default_expanded_empty",
        "diagnostic_default_expanded_populated",
        "pseudo_state_settlement",
        "control_styles",
        "file_list_specimen",
        "hierarchy_selection",
        "master_selection",
        "column_resize",
        "file_rows",
        "file_list_structure",
        "icon_registry",
        "dialog_exit",
        "confirmation_preview",
        "combobox_layout",
        "task_rail_layout",
        "native_minimum_request",
        "native_minimum_layout",
        "native_minimum_keyboard",
        "execution_axes",
        "segmented_state",
        "report_assembly",
        "recent_ui_specimens",
        "child",
    }
)
_FAILURE_REASONS = frozenset(
    {
        "stage_failure",
        "watchdog_timeout",
        "native_pseudo_pending",
        "control_invariant",
        "hierarchy_invariant",
        "selection_invariant",
        "column_resize_invariant",
        "file_row_invariant",
        "file_list_invariant",
        "icon_invariant",
        "dialog_invariant",
        "combobox_invariant",
        "task_rail_invariant",
        "native_wheel_pending",
        "native_minimum_pending",
        "native_minimum_dimensions",
        "layout_invariant",
        "execution_axes_invariant",
        "segmented_state_invariant",
        "report_invariant",
        "child_failure",
    }
)
_NATIVE_FAILURE_REASONS = frozenset(
    {
        "native_pseudo_pending",
        "native_wheel_pending",
        "native_minimum_pending",
        "native_minimum_dimensions",
    }
)
_NATIVE_PENDING = frozenset(
    {"none", "pseudo_states", "wheel_content", "wheel_backdrop", "minimum_window"}
)
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
    + ("lifecycle_progress", "diagnostic_layout", "inventory_panel", "control_contract", "motion", "icons")
)


class _Recorder:
    def __init__(self, evidence_paths: EvidencePaths, mode: str) -> None:
        self._publisher = EvidencePublisher(evidence_paths)
        self._rejected_report_path = evidence_paths.root / "rejected-complete-report.json"
        self._lock = threading.Lock()
        self._initial: str | None = None
        self._post_ready_failure: dict[str, object] | None = None
        self._data: dict[str, Any] = {
            "schema_version": 6,
            "mode": mode,
            "startup_errors": [],
        }

    def set(self, name: str, value: Any) -> None:
        with self._lock:
            self._data[name] = value

    def append(self, name: str, value: Any) -> None:
        with self._lock:
            self._data.setdefault(name, []).append(value)

    def rejected_report(self, report: dict[str, object]) -> None:
        self._rejected_report_path.write_text(
            json.dumps(report, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )

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
                "step": "child",
                "reason": "child_failure",
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

    def _failure_locked(self) -> dict[str, object] | None:
        report = self._data.get("report")
        if type(report) is dict and report.get("phase") == "failure":
            failure = report.get("failure")
            if type(failure) is dict:
                stage = failure.get("stage")
                result: dict[str, object] = {
                    "stage": (
                        stage
                        if type(stage) is str
                        and stage in _EVIDENCE_FAILURE_STAGES
                        else "report"
                    ),
                    "type": _sanitized_type_name(failure.get("type")),
                    "step": _sanitized_failure_token(
                        failure.get("step"), _FAILURE_STEPS, "not_started"
                    ),
                    "reason": _sanitized_failure_token(
                        failure.get("reason"), _FAILURE_REASONS, "stage_failure"
                    ),
                }
                native = failure.get("native")
                if (
                    result["reason"] in _NATIVE_FAILURE_REASONS
                    and _valid_native_failure_snapshot(native)
                ):
                    result["native"] = dict(native)
                return result
        if "pseudo_state_failed" in self._data:
            return {
                "stage": "pseudo_states", "type": "Error",
                "step": "pseudo_state_settlement", "reason": "stage_failure",
            }
        if "media_emulation_failed" in self._data:
            return {
                "stage": "page_setup", "type": "Error",
                "step": "not_started", "reason": "stage_failure",
            }
        native_failure = self._data.get("native_script_failure")
        if type(native_failure) is dict:
            a1_methods = {
                "a1_keyboard_focus": "Runtime.evaluate",
                "a1_keyboard_down": "Input.dispatchKeyEvent",
                "a1_keyboard_up": "Input.dispatchKeyEvent",
                "a1_keyboard_after": "Runtime.evaluate",
                "a1_keyboard_capture-context": "Runtime.evaluate",
                "a1_keyboard_capture": "Page.captureScreenshot",
            }
            if (
                native_failure.get("stage") == "a1_keyboard"
                and a1_methods.get(native_failure.get("step"))
                == native_failure.get("method")
            ):
                return {
                    "stage": "measurement",
                    "type": _sanitized_type_name(native_failure.get("type")),
                    "step": "native_minimum_keyboard",
                    "reason": "stage_failure",
                }
            return {
                "stage": "page_setup",
                "type": _sanitized_type_name(native_failure.get("type")),
                "step": "not_started",
                "reason": "stage_failure",
            }
        return None


def _sanitized_error_type(error: BaseException) -> str:
    return _sanitized_type_name(type(error).__name__)


def _sanitized_failure_token(
    value: object, allowed: frozenset[str], fallback: str
) -> str:
    return value if type(value) is str and value in allowed else fallback


def _valid_native_failure_snapshot(value: object) -> bool:
    if type(value) is not dict or set(value) != {
        "pending", "owner_scale", "minimum_width", "minimum_height",
        "outer_width", "outer_height", "client_width", "client_height",
    }:
        return False
    return (
        type(value["pending"]) is str
        and value["pending"] in _NATIVE_PENDING
        and all(
            type(value[name]) in {int, float}
            and math.isfinite(value[name])
            and value[name] > 0
            for name in (
                "owner_scale", "minimum_width", "minimum_height",
                "outer_width", "outer_height", "client_width", "client_height",
            )
        )
    )


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
    schedule_wheel: object = None,
    schedule_minimum_window: object = None,
    read_minimum_window: object = None,
    read_native_diagnostic: object = None,
    schedule_a1_keyboard: object = None,
):
    from namisync.interfaces.web.commands import (
        CommandAccess,
        CommandPayloadError,
        CommandRetry,
        CommandSpec,
        CommandResponsePolicy,
        FieldRequirement,
    )

    parts: list[tuple[str, object]] = []
    completed = False
    wheel_targets: set[str] = set()
    minimum_window_requested = False
    a1_keyboard_requested = False

    def validate(payload: object) -> dict[str, object]:
        if type(payload) is not dict or type(payload.get("phase")) is not str:
            raise CommandPayloadError("component gallery report is invalid")
        if payload["phase"] == "preview_wheel" and set(payload) == {"phase", "target"}:
            if type(payload["target"]) is not str or payload["target"] not in {"content", "backdrop"}:
                raise CommandPayloadError("component gallery wheel target is invalid")
            return dict(payload)
        if payload["phase"] == "minimum_window" and set(payload) == {"phase"}:
            return dict(payload)
        if payload["phase"] == "minimum_window_status" and set(payload) == {"phase"}:
            return dict(payload)
        if payload["phase"] == "diagnostic_status" and set(payload) == {"phase"}:
            return dict(payload)
        if payload["phase"] == "a1_keyboard" and set(payload) == {"phase"}:
            return dict(payload)
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
                or not {"stage", "type", "step", "reason"}.issubset(failure)
                or not set(failure).issubset(
                    {"stage", "type", "step", "reason", "native"}
                )
                or type(failure["stage"]) is not str
                or type(failure["type"]) is not str
                or type(failure["step"]) is not str
                or type(failure["reason"]) is not str
                or failure["stage"] not in _FAILURE_STAGES
                or failure["type"] not in _FAILURE_TYPES
                or failure["step"] not in _FAILURE_STEPS
                or failure["reason"] not in _FAILURE_REASONS
                or (
                    "native" in failure
                    and (
                        failure["reason"] not in _NATIVE_FAILURE_REASONS
                        or not _valid_native_failure_snapshot(failure["native"])
                    )
                )
                or (
                    failure["reason"] in _NATIVE_FAILURE_REASONS
                    and "native" not in failure
                )
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
                        "diagnostic_layout",
                    }
                    and type(value) is not list
                )
                or (
                    name in {"inventory_panel", "control_contract", "motion", "icons"}
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
            if name == "control_contract" and {"diagnostic_layout", "inventory_panel"}.intersection(value):
                raise CommandPayloadError("component gallery report is invalid")
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
        nonlocal completed, minimum_window_requested, a1_keyboard_requested
        if type(payload) is not dict:
            raise TypeError("component gallery received unvalidated data")
        if payload["phase"] == "prepare":
            schedule_pseudos(payload["targets"])
            return {"accepted": True}
        if payload["phase"] == "minimum_window":
            if minimum_window_requested or not callable(schedule_minimum_window):
                raise CommandPayloadError(
                    "component gallery minimum window request is invalid"
                )
            minimum_window_requested = True
            schedule_minimum_window()
            return {"accepted": True}
        if payload["phase"] == "minimum_window_status":
            if not minimum_window_requested or not callable(read_minimum_window):
                raise CommandPayloadError(
                    "component gallery minimum window status is invalid"
                )
            return read_minimum_window()
        if payload["phase"] == "diagnostic_status":
            if not callable(read_native_diagnostic):
                raise CommandPayloadError(
                    "component gallery diagnostic status is invalid"
                )
            value = read_native_diagnostic()
            if not _valid_native_failure_snapshot(value):
                raise CommandPayloadError(
                    "component gallery diagnostic status is invalid"
                )
            return value
        if payload["phase"] == "a1_keyboard":
            if a1_keyboard_requested or not callable(schedule_a1_keyboard):
                raise CommandPayloadError("component gallery A1 keyboard request is invalid")
            a1_keyboard_requested = True
            schedule_a1_keyboard()
            return {"accepted": True}
        if completed:
            raise CommandPayloadError("component gallery report is invalid")
        if payload["phase"] == "preview_wheel":
            target = payload["target"]
            if target in wheel_targets or not callable(schedule_wheel):
                raise CommandPayloadError("component gallery wheel request is invalid")
            wheel_targets.add(target)
            schedule_wheel(target)
            return {"accepted": True}
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
            "control_contract": {
                **values["control_contract"], "diagnostic_layout": values["diagnostic_layout"],
                "inventory_panel": values["inventory_panel"],
            },
            "motion": values["motion"],
            "icons": values["icons"],
        }
        if not _valid_complete_report(complete, expected_mode=expected_mode):
            recorder.rejected_report(complete)
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
        response_policy=CommandResponsePolicy.INTERACTIVE,
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
        and set(media) == {"dark", "forced", "reduced", "hdr", "advanced_color"}
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
                or math.isclose(row["height"], 18.0, abs_tol=0.5)
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
        "background_image",
        "fill_background",
        "border",
        "border_width",
        "border_style",
        "border_block_start",
        "border_block_end",
        "border_block_start_width",
        "border_block_end_width",
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
        "control_width",
        "control_height",
        "thumb_background",
        "thumb_width",
        "thumb_height",
        "thumb_inset_block_start",
        "thumb_inset_inline_start",
        "thumb_transform",
        "thumb_center_block",
        "thumb_edge_start",
        "thumb_edge_end",
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
        rows[("text_input", state)]["border_block_start_width"]
    )
    text_input_bottom = _css_pixel_width(
        rows[("text_input", state)]["border_block_end_width"]
    )
    return (
        button is not None
        and button > 0
        and checkbox is not None
        and math.isclose(checkbox, button, abs_tol=0.01)
        and text_input is not None
        and math.isclose(text_input, button, abs_tol=0.01)
        and text_input_bottom is not None
        and text_input_bottom >= text_input
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


def _valid_recent_ui(value: object) -> bool:
    if type(value) is not dict or set(value) != {
        "refusals", "move", "pause", "cancel", "commands_after_arm",
        "commands", "retained_panels", "layout",
    }:
        return False
    def text(item: object) -> bool:
        return type(item) is str and len(item) <= 1024

    refusals = value["refusals"]
    move = value["move"]
    if not (
        type(refusals) is list and len(refusals) == 3
        and all(
            type(row) is dict and set(row) == {"origin", "codes", "message", "title"}
            and all(text(row[key]) for key in ("origin", "message", "title"))
            and type(row["codes"]) is list and len(row["codes"]) <= 2
            and all(text(code) for code in row["codes"])
            for row in refusals
        )
        and type(move) is dict and set(move) == {
            "destination", "title", "revealed_node", "expanded", "checkable", "message",
            "prior_child_visible", "destination_highlighted",
            "revealed_destination", "prior_action", "prior_metadata", "prior_selection_disabled",
            "hierarchy", "row_indexes", "initial_collapsed", "path_in_badge",
            "badge_matches_action_radius", "path_clipped", "moved_annotation",
            "renamed_annotation", "rename_action", "annotations_purple",
            "long_origin_keeps_filename", "long_origin_clipped",
        }
        and all(text(move[key]) for key in ("destination", "title", "revealed_node", "expanded", "message", "destination_highlighted", "revealed_destination", "prior_action", "prior_metadata"))
        and type(move["checkable"]) is bool
        and type(move["prior_child_visible"]) is bool
        and type(move["prior_selection_disabled"]) is bool
        and all(type(move[key]) is bool for key in ("initial_collapsed", "path_in_badge", "badge_matches_action_radius", "path_clipped", "annotations_purple", "long_origin_keeps_filename", "long_origin_clipped"))
        and all(text(move[key]) for key in ("moved_annotation", "renamed_annotation", "rename_action"))
        and type(move["hierarchy"]) is list and len(move["hierarchy"]) == 5
        and all(type(row) is list and len(row) == 6 and all(item is None or type(item) is int for item in row) for row in move["hierarchy"])
        and type(move["row_indexes"]) is list and len(move["row_indexes"]) == 5
        and all(text(item) for item in move["row_indexes"])
        and type(value["commands_after_arm"]) is int
        and 0 <= value["commands_after_arm"] <= 2
        and type(value["commands"]) is list and len(value["commands"]) <= 3
        and all(text(command) for command in value["commands"])
        and type(value["retained_panels"]) is int and 0 <= value["retained_panels"] <= 5
    ):
        return False
    layout = value["layout"]
    if type(layout) is not list or len(layout) != 5:
        return False
    for panel in layout:
        if type(panel) is not dict or set(panel) != {"panel", "status", "viewport", "horizontal_scroll", "controls", "rows"} or not text(panel["horizontal_scroll"]):
            return False
        if not all(type(panel[key]) is list and len(panel[key]) <= 5 for key in ("controls", "rows")):
            return False
        for bounds in [panel["panel"], panel["status"], panel["viewport"], *panel["controls"], *panel["rows"]]:
            if type(bounds) is not list or len(bounds) != 4 or not all(type(item) in {int, float} and math.isfinite(item) for item in bounds):
                return False
    return all(
        type(value[key]) is list and len(value[key]) == count
        and all(
            type(row) is dict and set(row) == {"label", "primary", "disabled", "mask"}
            and text(row["label"]) and text(row["mask"])
            and type(row["primary"]) is bool and type(row["disabled"]) is bool
            for row in value[key]
        )
        for key, count in (("pause", 3), ("cancel", 4))
    )


def _valid_control_contract(value: object) -> bool:
    if type(value) is not dict or set(value) != {
        "accent",
        "tri_state",
        "dialog_exit",
        "confirmation_preview",
        "diagnostic_layout",
        "inventory_panel",
        "minimum_window",
        "segmented",
        "combobox",
        "task_rail",
        "file_list",
        "integrity_list",
        "recent_ui",
    }:
        return False
    accent = value["accent"]
    tri_state = value["tri_state"]
    dialog_exit = value["dialog_exit"]
    confirmation_preview = value["confirmation_preview"]
    diagnostic_layout = value["diagnostic_layout"]
    minimum_window = value["minimum_window"]
    segmented = value["segmented"]
    combobox = value["combobox"]
    task_rail = value["task_rail"]
    file_list = value["file_list"]
    integrity_list = value["integrity_list"]
    return (
        _valid_recent_ui(value["recent_ui"])
        and _valid_inventory_panel(value["inventory_panel"])
        and type(accent) is dict
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
            "mixed_mask",
            "mixed_size",
            "checked_mask",
            "checked_size",
        }
        and tri_state["aria_checked"] == "mixed"
        and tri_state["indeterminate"] is True
        and type(tri_state["cue_content"]) is str
        and tri_state["cue_content"] not in {"", "none", "normal"}
        and type(tri_state["mixed_mask"]) is str
        and type(tri_state["mixed_size"]) is str
        and type(tri_state["checked_mask"]) is str
        and type(tri_state["checked_size"]) is str
        and tri_state["mixed_size"] == "12px 12px"
        and tri_state["checked_size"] == "12px 12px"
        and "subtract_16_regular.svg" in tri_state["mixed_mask"]
        and "checkmark_16_regular.svg" in tri_state["checked_mask"]
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
        and type(confirmation_preview) is dict
        and set(confirmation_preview) == {
            "initially_closed", "opened_from_button", "background_inert",
            "cancel_closed", "confirm_closed", "focus_restored", "wheel_blocked",
        }
        and all(item is True for item in confirmation_preview.values())
        and _valid_diagnostic_layout(diagnostic_layout)
        and type(minimum_window) is dict
        and set(minimum_window) == {
            "default_outer_width", "default_outer_height",
            "native_default_owner_scale", "native_default_outer_width",
            "native_default_outer_height",
            "outer_width", "outer_height", "inner_width", "inner_height",
            "native_owner_scale", "native_minimum_width", "native_minimum_height",
            "native_outer_width", "native_outer_height",
            "native_client_width", "native_client_height",
            "work_width", "work_content_width", "work_height",
            "review_width", "review_height",
            "work_content_aligned",
            "axes_wrapped", "long_trash_length", "filter_menu", "row_menu",
            "keyboard_scroll_before", "keyboard_scroll_after",
            "keyboard_capture_width", "keyboard_capture_height",
        }
        and all(
            type(minimum_window[name]) in {int, float}
            and math.isfinite(minimum_window[name])
            and minimum_window[name] > 0
            for name in (
                "default_outer_width", "default_outer_height",
                "native_default_owner_scale", "native_default_outer_width",
                "native_default_outer_height",
                "outer_width", "outer_height", "inner_width", "inner_height",
                "native_owner_scale", "native_minimum_width", "native_minimum_height",
                "native_outer_width", "native_outer_height",
                "native_client_width", "native_client_height",
                "work_width", "work_content_width", "work_height",
                "review_width", "review_height",
                "keyboard_capture_width", "keyboard_capture_height",
            )
        )
        and type(minimum_window["keyboard_scroll_before"]) in {int, float}
        and type(minimum_window["keyboard_scroll_after"]) in {int, float}
        and minimum_window["keyboard_scroll_before"] >= 0
        and minimum_window["keyboard_scroll_after"] > minimum_window["keyboard_scroll_before"]
        and type(minimum_window["filter_menu"]) is dict
        and type(minimum_window["row_menu"]) is dict
        and set(minimum_window["row_menu"]) == {
            "shared_style", "popup_inside", "committed_inert", "escape_focus",
            "keyboard_open", "end_focus", "resize_closed", "rectangles", "raw_rectangles",
        }
        and all(type(minimum_window["row_menu"][key]) is bool for key in (
            "shared_style", "popup_inside", "committed_inert", "escape_focus",
            "keyboard_open", "end_focus", "resize_closed",
        ))
        and type(minimum_window["row_menu"]["rectangles"]) is list
        and len(minimum_window["row_menu"]["rectangles"]) == 2
        and all(type(rect) is list and len(rect) == 4
                and all(type(value) in {int, float} and math.isfinite(value) for value in rect)
                for rect in minimum_window["row_menu"]["rectangles"])
        and type(minimum_window["row_menu"]["raw_rectangles"]) is list
        and len(minimum_window["row_menu"]["raw_rectangles"]) == 2
        and all(type(rect) is list and len(rect) == 4
                and all(type(value) in {int, float} and math.isfinite(value) for value in rect)
                for rect in minimum_window["row_menu"]["raw_rectangles"])
        and set(minimum_window["filter_menu"]) == {
            "accent_pair", "neutral_pair", "active_fill", "inactive_fill", "popup_inside",
            "first_reachable", "end_reachable", "rectangles", "internal_scroll_preserved", "resize_closed", "outside_scroll_closed",
        }
        and all(type(minimum_window["filter_menu"][key]) is bool for key in (
            "accent_pair", "neutral_pair", "popup_inside", "first_reachable", "end_reachable",
            "internal_scroll_preserved", "resize_closed", "outside_scroll_closed",
        ))
        and all(type(minimum_window["filter_menu"][key]) is str and len(minimum_window["filter_menu"][key]) <= 100
                for key in ("active_fill", "inactive_fill"))
        and type(minimum_window["filter_menu"]["rectangles"]) is list
        and len(minimum_window["filter_menu"]["rectangles"]) == 5
        and all(type(rect) is list and len(rect) == 4
                and all(type(value) in {int, float} and math.isfinite(value) for value in rect)
                for rect in minimum_window["filter_menu"]["rectangles"])
        and minimum_window["axes_wrapped"] is True
        and minimum_window["long_trash_length"] == 32767
        and minimum_window["work_content_aligned"] is True
        and math.isclose(
            minimum_window["native_default_outer_width"],
            1280 * minimum_window["native_default_owner_scale"],
            abs_tol=2,
        )
        and math.isclose(
            minimum_window["native_default_outer_height"],
            800 * minimum_window["native_default_owner_scale"],
            abs_tol=2,
        )
        and minimum_window["work_content_width"] <= minimum_window["work_width"]
        and math.isclose(
            minimum_window["review_width"],
            minimum_window["work_content_width"],
            abs_tol=1,
        )
        and math.isclose(
            minimum_window["native_minimum_width"],
            int(1024 * minimum_window["native_owner_scale"]),
            abs_tol=1,
        )
        and math.isclose(
            minimum_window["native_minimum_height"],
            int(640 * minimum_window["native_owner_scale"]),
            abs_tol=1,
        )
        and math.isclose(
            minimum_window["native_outer_width"],
            minimum_window["native_minimum_width"],
            abs_tol=1,
        )
        and math.isclose(
            minimum_window["native_outer_height"],
            minimum_window["native_minimum_height"],
            abs_tol=1,
        )
        and math.isclose(
            minimum_window["native_client_width"]
            / minimum_window["native_owner_scale"],
            minimum_window["inner_width"],
            abs_tol=2,
        )
        and math.isclose(
            minimum_window["native_client_height"]
            / minimum_window["native_owner_scale"],
            minimum_window["inner_height"],
            abs_tol=2,
        )
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
            "selected_marker_height",
            "current_marker_width",
            "current_marker_height",
            "rest_marker_content",
            "selected_marker_background",
        }
        and task_rail["card_count"] == 4
        and task_rail["outside_content_card"] is True
        and task_rail["left_of_work"] is True
        and task_rail["selected_count"] == 1
        and task_rail["current_count"] == 1
        and task_rail["selected_current_same_card"] is True
        and task_rail["transparent_boundaries"] is True
        and type(task_rail["selected_marker_width"]) in {int, float}
        and 2.5 <= task_rail["selected_marker_width"] <= 3.5
        and type(task_rail["selected_marker_height"]) in {int, float}
        and 31.5 <= task_rail["selected_marker_height"] <= 32.5
        and type(task_rail["current_marker_width"]) in {int, float}
        and 2.5 <= task_rail["current_marker_width"] <= 3.5
        and type(task_rail["current_marker_height"]) in {int, float}
        and 31.5 <= task_rail["current_marker_height"] <= 32.5
        and task_rail["rest_marker_content"] in {"none", "normal"}
        and type(task_rail["selected_marker_background"]) is str
        and bool(task_rail["selected_marker_background"])
        and _valid_plan_evidence(file_list)
        and _valid_integrity_evidence(integrity_list)
    )


def _native_minimum_matches_owner_scale(
    width: int,
    height: int,
    owner_scale: float,
) -> bool:
    return (
        math.isclose(width, int(1024 * owner_scale), abs_tol=1)
        and math.isclose(height, int(640 * owner_scale), abs_tol=1)
    )


class _MinimumWindowStatus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value: dict[str, object] = {"complete": False}
        self._diagnostic: dict[str, object] | None = None

    def read(self) -> dict[str, object]:
        with self._lock:
            return dict(self._value)

    def read_diagnostic(self) -> dict[str, object] | None:
        with self._lock:
            return (
                None if self._diagnostic is None else dict(self._diagnostic)
            )

    def set_pending(self, pending: str) -> None:
        if pending not in _NATIVE_PENDING:
            raise ValueError("component gallery native pending state is invalid")
        with self._lock:
            if self._diagnostic is not None:
                self._diagnostic["pending"] = pending

    def publish_diagnostic(
        self,
        *,
        pending: str,
        owner_scale: float,
        minimum_width: int,
        minimum_height: int,
        outer_width: int,
        outer_height: int,
        client_width: int,
        client_height: int,
    ) -> None:
        snapshot = {
            "pending": pending,
            "owner_scale": owner_scale,
            "minimum_width": minimum_width,
            "minimum_height": minimum_height,
            "outer_width": outer_width,
            "outer_height": outer_height,
            "client_width": client_width,
            "client_height": client_height,
        }
        if not _valid_native_failure_snapshot(snapshot):
            raise ValueError("component gallery native diagnostic is invalid")
        with self._lock:
            self._diagnostic = snapshot

    def publish(
        self,
        *,
        owner_scale: float,
        minimum_width: int,
        minimum_height: int,
        outer_width: int,
        outer_height: int,
        client_width: int,
        client_height: int,
    ) -> None:
        snapshot = {
            "complete": True,
            "owner_scale": owner_scale,
            "minimum_width": minimum_width,
            "minimum_height": minimum_height,
            "outer_width": outer_width,
            "outer_height": outer_height,
            "client_width": client_width,
            "client_height": client_height,
        }
        with self._lock:
            self._value = snapshot
            self._diagnostic = {
                "pending": "none",
                **{name: value for name, value in snapshot.items() if name != "complete"},
            }


def _install_minimum_window_scheduler(
    *,
    window: object,
    native: object,
    action: object,
    retained_delegates: list[object],
    scheduler: dict[str, object],
    status: _MinimumWindowStatus,
    recorder: object,
) -> None:
    status.publish_diagnostic(
        pending="none",
        owner_scale=float(native._scale),
        minimum_width=native.MinimumSize.Width,
        minimum_height=native.MinimumSize.Height,
        outer_width=native.Width,
        outer_height=native.Height,
        client_width=native.ClientSize.Width,
        client_height=native.ClientSize.Height,
    )

    def resize_minimum_window() -> None:
        owner_scale = float(native._scale)
        minimum = native.MinimumSize
        if not _native_minimum_matches_owner_scale(
            minimum.Width,
            minimum.Height,
            owner_scale,
        ):
            status.publish(
                owner_scale=owner_scale,
                minimum_width=minimum.Width,
                minimum_height=minimum.Height,
                outer_width=native.Width,
                outer_height=native.Height,
                client_width=native.ClientSize.Width,
                client_height=native.ClientSize.Height,
            )
            return
        native.Size = minimum
        recorder.set(
            "native_window_request",
            {
                "minimum": True,
                "logical_width": 1024,
                "logical_height": 640,
                "owner_scale": owner_scale,
                "minimum_width": minimum.Width,
                "minimum_height": minimum.Height,
            },
        )

        def observe_completed_resize() -> None:
            status.publish(
                owner_scale=owner_scale,
                minimum_width=native.MinimumSize.Width,
                minimum_height=native.MinimumSize.Height,
                outer_width=native.Width,
                outer_height=native.Height,
                client_width=native.ClientSize.Width,
                client_height=native.ClientSize.Height,
            )

        completion = action(observe_completed_resize)
        retained_delegates.append(completion)
        native.BeginInvoke(completion)

    def schedule_minimum_window() -> None:
        status.set_pending("minimum_window")
        resize = action(resize_minimum_window)
        retained_delegates.append(resize)
        native.BeginInvoke(resize)

    if window.native is not native:
        raise RuntimeError("component gallery native window ownership changed")
    scheduler["value"] = schedule_minimum_window


def _valid_inventory_panel(value: object) -> bool:
    if type(value) is not dict or set(value) != {
        "headers", "checkbox_count", "switcher", "labels", "checksum", "timestamps",
        "first_widths", "row_widths", "grown_widths", "manual_before", "manual_after",
        "header_positions", "row_positions", "status_rectangles", "scroll_owners",
        "details", "refresh_on_status", "root_fits", "viewport_height",
        "viewport_scroll_height", "adopted_offset", "window_requests", "row_height",
        "setup_heights", "status",
    }:
        return False
    details = value["details"]
    return (
        type(value["headers"]) is list and len(value["headers"]) == 5
        and all(type(text) is str and len(text) <= 32 for text in value["headers"])
        and type(value["checkbox_count"]) is int and 0 <= value["checkbox_count"] <= 10
        and type(value["switcher"]) is list and len(value["switcher"]) == 2
        and all(type(item) is dict and set(item) == {"text", "selected", "disabled"}
                and type(item["text"]) is str and item["selected"] in {"true", "false"}
                and type(item["disabled"]) is bool for item in value["switcher"])
        and type(value["labels"]) is list and len(value["labels"]) == 7
        and all(type(item) is dict and set(item) == {"case", "text", "foreground", "background", "height"}
                and all(type(item[key]) is str and len(item[key]) <= 128
                        for key in ("case", "text", "foreground", "background"))
                and _finite_number_matrix([[item["height"]]], 1, 1) for item in value["labels"])
        and type(value["checksum"]) is dict and set(value["checksum"]) == {"text", "title", "absent"}
        and all(type(text) is str and len(text) <= 128 for text in value["checksum"].values())
        and type(value["timestamps"]) is dict and set(value["timestamps"]) == {
            "modified", "subject", "observed", "expected_modified", "expected_observed",
        }
        and all(type(text) is str and len(text) <= 64 for text in value["timestamps"].values())
        and all(_finite_number_matrix([value[key]], 1, 5)
                for key in ("first_widths", "row_widths", "grown_widths", "manual_before", "manual_after"))
        and all(_finite_number_matrix(value[key], 5, 4) for key in ("header_positions", "row_positions"))
        and _finite_number_matrix(value["status_rectangles"], 4, 4)
        and _finite_number_matrix(value["setup_heights"], 2, 2)
        and type(value["status"]) is dict and set(value["status"]) == {
            "single_line", "loading_same_line", "active_animation", "active_indeterminate",
            "terminal_animation", "terminal_track_visible", "track_height", "terminal_value",
        }
        and all(type(value["status"][key]) is bool for key in
                ("single_line", "loading_same_line", "active_indeterminate", "terminal_track_visible"))
        and all(type(value["status"][key]) is str and len(value["status"][key]) <= 64 for key in
                ("active_animation", "terminal_animation", "terminal_value"))
        and _finite_number_matrix([[value["status"]["track_height"]]], 1, 1)
        and type(value["scroll_owners"]) is dict and set(value["scroll_owners"]) == {"outer_x", "body_x", "body_y"}
        and all(type(text) is str and len(text) <= 32 for text in value["scroll_owners"].values())
        and type(details) is dict and set(details) == {
            "initially_hidden", "expanded", "root_height", "column_height", "root_width", "column_width",
            "global_overflow", "item_overflow", "placeholder", "focus_restored",
            "card_rectangles", "rem_size",
        }
        and all(type(details[key]) is bool for key in ("initially_hidden", "expanded", "placeholder", "focus_restored"))
        and all(type(details[key]) is str and len(details[key]) <= 32 for key in ("global_overflow", "item_overflow"))
        and _finite_number_matrix([[details[key] for key in ("root_height", "column_height", "root_width", "column_width")]], 1, 4)
        and _finite_number_matrix(details["card_rectangles"], 2, 4)
        and _finite_number_matrix([[details["rem_size"]]], 1, 1)
        and all(type(value[key]) is bool for key in ("refresh_on_status", "root_fits"))
        and _finite_number_matrix([[value[key] for key in ("viewport_height", "viewport_scroll_height", "row_height")]], 1, 3)
        and type(value["adopted_offset"]) is int and 0 <= value["adopted_offset"] <= 300
        and type(value["window_requests"]) is list and len(value["window_requests"]) <= 100
        and all(type(offset) is int and 0 <= offset <= 300 for offset in value["window_requests"])
    )


def _valid_diagnostic_layout(value: object) -> bool:
    cases = {
        f"{size}-{disclosure}-{population}"
        for size in ("default", "minimum")
        for disclosure in ("folded", "expanded")
        for population in ("empty", "populated")
    }
    keys = {
        "case", "block_size", "root_fits", "table_usable",
        "expanded", "populated", "logical_rows", "loaded_rows",
        "disclosure_matches", "diagnostics_visible", "rows_overflow",
        "scroll_advanced", "window_requested", "window_adopted",
        "viewport_bounded", "row_height", "stale_facts_cleared",
        "header_aligned", "whole_row_reachable", "both_columns_reachable",
        "collapse_focus_restored", "table_state_preserved",
        "hidden_descendant_exempt", "visible_collapsed_rejected",
        "no_horizontal_control_clipping", "visible_count",
        "cardinality_exact", "issues_content_reachable", "trash_content_reachable",
        "detail_content_reachable", "issues_keyboard_reachable",
        "trash_keyboard_reachable", "detail_keyboard_reachable",
        "readable_body", "disclosure_reachable",
        "row_activation_reachable", "placeholder_present",
        "detail_matches_focused_row",
        "title_action_aligned", "status_details_same_row", "completion_local",
        "details_rectangles", "central_widths", "card_scroll_positions",
        "rem_size", "rail_widths", "rail_aligned",
        "header_scroll_observations", "global_content_rows",
    }
    return (
        type(value) is list
        and len(value) == len(cases)
        and all(type(item) is dict and type(item.get("case")) is str for item in value)
        and {item["case"] for item in value} == cases
        and all(
            type(item) is dict
            and set(item) == keys
            and type(item["block_size"]) in {int, float}
            and math.isfinite(item["block_size"])
            and item["block_size"] > 0
            and _finite_number_matrix(item["details_rectangles"], 6, 4)
            and _finite_number_matrix(item["central_widths"], 2, 3)
            and _finite_number_matrix(item["card_scroll_positions"], 3, 4)
            and _finite_number_matrix([item["rail_widths"]], 1, 2)
            and _finite_number_matrix(item["header_scroll_observations"], 3, 15)
            and _finite_number_matrix([item["global_content_rows"]], 1, 6)
            and type(item["rem_size"]) in {int, float}
            and math.isfinite(item["rem_size"])
            and item["rem_size"] > 0
            and type(item["visible_count"]) is int
            and 0 <= item["visible_count"] <= 2
            and type(item["expanded"]) is bool
            and type(item["populated"]) is bool
            and type(item["logical_rows"]) is int
            and 0 <= item["logical_rows"] <= 1000
            and type(item["loaded_rows"]) is int
            and 0 <= item["loaded_rows"] <= 64
            and type(item["row_height"]) in {int, float}
            and math.isfinite(item["row_height"])
            and 0 <= item["row_height"] <= 128
            and all(
                type(item[name]) is bool
                for name in keys - {
                    "case", "block_size", "visible_count", "expanded", "populated",
                    "logical_rows", "loaded_rows", "row_height",
                    "details_rectangles", "central_widths", "card_scroll_positions",
                    "rem_size", "rail_widths",
                    "header_scroll_observations", "global_content_rows",
                }
            )
            for item in value
        )
    )


def _finite_number_matrix(value: object, rows: int, columns: int) -> bool:
    return (
        type(value) is list and len(value) == rows
        and all(type(row) is list and len(row) == columns
                and all(type(number) in {int, float} and math.isfinite(number)
                        for number in row) for row in value)
    )


def _valid_file_list_evidence(
    value: object,
    *,
    expected_cases: frozenset[str],
    expected_headers: list[str],
) -> bool:
    column_count = len(expected_headers)
    resize_columns = (
        ["selection", "name", "primary", "secondary", "size"]
        if column_count == 7
        else ["selection", "name", "size", "primary", "secondary"]
    )
    if column_count == 7:
        resize_columns.append("modified")
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
        "resize_handle_columns",
        "resize_handle_roles",
        "resize_handle_labels",
        "notes_resizer_absent",
        "initial_layout_frozen",
        "normal_columns_align",
        "initial_column_widths",
        "initial_column_lefts",
        "initial_right",
        "frozen_column_widths",
        "frozen_column_lefts",
        "frozen_right",
        "frozen_layout_active",
        "pointer_column_widths",
        "pointer_column_lefts",
        "pointer_right",
        "column_resize_changes_width",
        "resized_columns_align",
        "requested_pointer_delta",
        "column_resize_delta",
        "column_notes_delta",
        "keyboard_column_widths",
        "keyboard_column_lefts",
        "keyboard_right",
        "keyboard_resize_delta",
        "keyboard_notes_delta",
        "viewport_resize_amount",
        "viewport_narrow_widths",
        "viewport_narrow_right",
        "viewport_narrow_right_span",
        "viewport_narrow_list_width",
        "narrow_columns_align",
        "viewport_restored_widths",
        "viewport_restored_right",
        "notes_minimum_widths",
        "name_minimum_widths",
        "name_minimum",
        "notes_minimum",
        "constrained_column_widths",
        "constrained_grid_width",
        "constrained_right_span",
        "constrained_columns_align",
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
        "vertical_body_overflows",
        "vertical_columns_align",
        "vertical_body_below_header",
        "vertical_header_client_width",
        "vertical_body_client_width",
        "header_inline_gutter_width",
        "body_inline_gutter_width",
        "empty_header_client_width",
        "empty_body_client_width",
        "header_scrollbar_width",
        "body_scrollbar_width",
        "header_scrollbar_gutter",
        "body_scrollbar_gutter",
        "outer_scroll_amount",
        "scroll_header_delta",
        "scroll_body_delta",
        "inner_horizontal_scroll_lefts",
        "max_scroll_header_right",
        "max_scroll_body_right",
        "max_scroll_viewport_right",
        "max_scroll_header_content_right",
        "max_scroll_body_content_right",
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
        "primary_width",
        "primary_cell_width",
        "primary_cell_padding_left",
        "primary_cell_padding_right",
        "primary_progress_value",
        "primary_progress_bar_width",
        "primary_progress_track",
        "primary_progress_fill",
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
        or value["resize_handle_count"] != column_count - 1
        or value["resize_handle_columns"] != resize_columns
        or value["resize_handle_roles"] != ["separator"] * (column_count - 1)
        or type(value["resize_handle_labels"]) is not list
        or len(value["resize_handle_labels"]) != column_count - 1
        or not all(
            type(label) is str and label.startswith("Resize ")
            for label in value["resize_handle_labels"]
        )
        or value["notes_resizer_absent"] is not True
        or value["initial_layout_frozen"] is not False
        or value["normal_columns_align"] is not True
        or value["frozen_layout_active"] is not True
        or value["column_resize_changes_width"] is not True
        or value["resized_columns_align"] is not True
        or value["narrow_columns_align"] is not True
        or value["constrained_columns_align"] is not True
        or any(
            type(value[name]) not in {int, float}
            or not math.isfinite(value[name])
            for name in (
                "initial_right",
                "frozen_right",
                "pointer_right",
                "column_resize_delta",
                "requested_pointer_delta",
                "column_notes_delta",
                "keyboard_right",
                "keyboard_resize_delta",
                "keyboard_notes_delta",
                "viewport_resize_amount",
                "viewport_narrow_right",
                "viewport_narrow_right_span",
                "viewport_narrow_list_width",
                "viewport_restored_right",
                "name_minimum",
                "notes_minimum",
                "constrained_grid_width",
                "constrained_right_span",
                "outer_scroll_amount",
                "scroll_header_delta",
                "scroll_body_delta",
                "max_scroll_header_right",
                "max_scroll_body_right",
                "max_scroll_viewport_right",
                "max_scroll_header_content_right",
                "max_scroll_body_content_right",
                "header_inline_gutter_width",
                "body_inline_gutter_width",
            )
        )
        or value["viewport_resize_amount"] <= 0
        or any(
            type(value[name]) is not list
            or len(value[name]) != column_count
            or not all(
                type(item) in {int, float} and math.isfinite(item)
                for item in value[name]
            )
            for name in (
                "initial_column_widths",
                "initial_column_lefts",
                "frozen_column_widths",
                "frozen_column_lefts",
                "pointer_column_widths",
                "pointer_column_lefts",
                "keyboard_column_widths",
                "keyboard_column_lefts",
                "viewport_narrow_widths",
                "viewport_restored_widths",
                "notes_minimum_widths",
                "name_minimum_widths",
                "constrained_column_widths",
            )
        )
        or any(
            item <= 0
            for name in (
                "initial_column_widths",
                "frozen_column_widths",
                "pointer_column_widths",
                "keyboard_column_widths",
                "viewport_narrow_widths",
                "viewport_restored_widths",
                "notes_minimum_widths",
                "name_minimum_widths",
                "constrained_column_widths",
            )
            for item in value[name]
        )
        or type(value["header_foreground"]) is not str
        or not value["header_foreground"]
        or type(value["header_background"]) is not str
        or not value["header_background"]
        or value["header_texts"] != expected_headers
        or value["header_cell_roles"] != ["columnheader"] * column_count
        or value["selection_header_label"] != "Selection"
        or value["column_count"] != column_count
        or value["row_count"] != expected_count
        or value["body_child_count"] != expected_count
        or value["checkbox_count"] != expected_count
        or value["body_ends_at_last_row"] is not True
        or value["body_height_matches_rows"] is not True
        or value["vertical_body_overflows"] is not True
        or value["vertical_columns_align"] is not True
        or value["vertical_body_below_header"] is not True
        or value["vertical_header_client_width"] != value["vertical_body_client_width"]
        or value["header_inline_gutter_width"] != value["body_inline_gutter_width"]
        or value["header_inline_gutter_width"] < 0
        or value["empty_header_client_width"] != value["vertical_header_client_width"]
        or value["empty_body_client_width"] != value["vertical_body_client_width"]
        or type(value["header_scrollbar_width"]) is not str
        or not value["header_scrollbar_width"]
        or value["header_scrollbar_width"] != value["body_scrollbar_width"]
        or value["header_scrollbar_gutter"] != "stable"
        or value["body_scrollbar_gutter"] != "stable"
        or value["outer_scroll_amount"] <= 0
        or abs(value["scroll_header_delta"] + value["outer_scroll_amount"]) > 0.75
        or abs(value["scroll_body_delta"] + value["outer_scroll_amount"]) > 0.75
        or value["inner_horizontal_scroll_lefts"] != [0, 0]
        or abs(value["max_scroll_header_right"] - value["max_scroll_body_right"]) > 0.75
        or value["max_scroll_header_right"] > value["max_scroll_viewport_right"] + 0.75
        or value["max_scroll_header_right"] > value["max_scroll_header_content_right"] + 0.75
        or value["max_scroll_body_right"] > value["max_scroll_body_content_right"] + 0.75
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
            or row["cell_roles"] != ["cell"] * column_count
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
            or primary_tone not in {"", "intent", "lifecycle", "integrity"}
            or secondary_tone not in {"", "intent", "lifecycle", "integrity"}
            or type(primary_key) is not str
            or type(secondary_key) is not str
            or (primary_tone == "") != (primary_key == "")
            or (secondary_tone == "") != (secondary_key == "")
            or row["primary_form"] not in {"", "text", "fill", "progress"}
            or (primary_tone == "") != (row["primary_form"] == "")
            or (primary_tone == "intent" and primary_key not in _INTENT_CASES)
            or (secondary_tone == "intent" and secondary_key not in _INTENT_CASES)
            or (
                primary_tone == "lifecycle"
                and primary_key not in _LIFECYCLE_CASES
            )
            or (
                secondary_tone == "lifecycle"
                and secondary_key not in _LIFECYCLE_CASES
            )
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
            or any(
                type(row[name]) not in {int, float}
                or not math.isfinite(row[name])
                or row[name] <= 0
                for name in ("primary_width", "primary_cell_width")
            )
            or any(
                type(row[name]) not in {int, float}
                or not math.isfinite(row[name])
                or row[name] < 0
                for name in (
                    "primary_cell_padding_left",
                    "primary_cell_padding_right",
                )
            )
            or row["primary_foreground"] != row["primary_alias_foreground"]
            or row["primary_background"] != row["primary_alias_background"]
            or _transparent_css_color(row["primary_background"])
            != (row["primary_form"] != "fill")
            or (
                row["primary_form"] == "fill"
                and not math.isclose(row["primary_height"], 18.0, abs_tol=0.5)
            )
            or (
                row["primary_form"] == "progress"
                and (
                    not math.isclose(row["primary_height"], 4.0, abs_tol=0.5)
                    or not math.isclose(
                        row["primary_width"]
                        + row["primary_cell_padding_left"]
                        + row["primary_cell_padding_right"],
                        row["primary_cell_width"],
                        abs_tol=0.5,
                    )
                    or not math.isclose(
                        row["primary_cell_padding_left"], 8.0, abs_tol=0.25
                    )
                    or not math.isclose(
                        row["primary_cell_padding_right"], 8.0, abs_tol=0.25
                    )
                    or type(row["primary_progress_value"]) not in {int, float}
                    or not 0 <= row["primary_progress_value"] <= 100
                    or type(row["primary_progress_bar_width"])
                    not in {int, float}
                    or not math.isfinite(row["primary_progress_bar_width"])
                    or row["primary_progress_bar_width"] < 0
                    or not math.isclose(
                        row["primary_progress_bar_width"]
                        / row["primary_width"]
                        * 100,
                        row["primary_progress_value"],
                        abs_tol=0.5,
                    )
                    or not all(
                        type(row[name]) is str and bool(row[name])
                        for name in (
                            "primary_progress_track",
                            "primary_progress_fill",
                        )
                    )
                    or row["primary_progress_track"]
                    == row["primary_progress_fill"]
                )
            )
            or (
                row["primary_form"] != "progress"
                and (
                    row["primary_progress_value"] is not None
                    or row["primary_progress_bar_width"] != 0
                    or row["primary_progress_track"] != ""
                    or row["primary_progress_fill"] != ""
                )
            )
            or type(row["cell_backgrounds"]) is not list
            or len(row["cell_backgrounds"]) != column_count
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
            or len(row["column_lefts"]) != column_count
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
            "Name",
            "Action",
            "Checksum",
            "Size",
            "Modified",
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
        "mask_loads",
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
        and type(value["mask_loads"]) is dict
        and set(value["mask_loads"]) == set(value["mask_images"])
        and all(type(item) is bool for item in value["mask_loads"].values())
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


def _schedule_preview_wheel(
    native: object,
    core: object,
    target: str,
    recorder: _Recorder,
    retained_delegates: list[object],
) -> None:
    from System import Action

    def on_ui(callback: object) -> None:
        action = Action(callback)
        retained_delegates.append(action)
        native.BeginInvoke(action)

    def fail() -> None:
        recorder.set("native_script_failure", {"stage": "preview_wheel", "type": "ScriptExecutionError"})
        recorder.write()

    def locate() -> None:
        expression = """(() => {
          const dialog = document.querySelector('#execution-confirmation');
          if (!dialog?.matches(':modal')) throw new Error('preview is not modal');
          const rect = dialog.querySelector('[data-confirm-execution]').getBoundingClientRect();
          return {x: (rect.left + rect.right) / 2, y: (rect.top + rect.bottom) / 2};
        })()""" if target == "content" else "({x: 4, y: innerHeight / 2})"
        task = core.CallDevToolsProtocolMethodAsync(
            "Runtime.evaluate", json.dumps({"expression": expression, "returnByValue": True}),
        )

        def located() -> None:
            if task.IsFaulted or task.IsCanceled:
                fail()
                return
            try:
                point = json.loads(str(task.Result))["result"]["value"]
                if set(point) != {"x", "y"} or any(
                    type(value) not in {int, float} or not math.isfinite(value)
                    for value in point.values()
                ):
                    raise ValueError("invalid preview coordinates")
            except (KeyError, TypeError, ValueError):
                fail()
                return

            def wheel() -> None:
                sent = core.CallDevToolsProtocolMethodAsync(
                    "Input.dispatchMouseEvent",
                    json.dumps({"type": "mouseWheel", **point, "deltaX": 0, "deltaY": 500}),
                )

                def finished() -> None:
                    if sent.IsFaulted or sent.IsCanceled:
                        fail()
                        return
                    on_ui(lambda: _execute_script_checked(
                        core, f"globalThis.__namiGalleryWheelTarget = {json.dumps(target)};",
                        stage="preview_wheel", recorder=recorder,
                        retained_delegates=retained_delegates,
                    ))

                completion = Action(finished)
                retained_delegates.append(completion)
                sent.GetAwaiter().OnCompleted(completion)

            on_ui(wheel)

        completion = Action(located)
        retained_delegates.append(completion)
        task.GetAwaiter().OnCompleted(completion)

    on_ui(locate)


def _schedule_a1_keyboard_capture(
    native: object,
    core: object,
    target: Path,
    recorder: _Recorder,
    retained_delegates: list[object],
) -> None:
    from System import Action
    from _headed_cdp import NativeCdp, decode_png

    def fail(error: BaseException, _task: object, step: str, method: str) -> None:
        recorder.set(
            "native_script_failure",
            {"stage": "a1_keyboard", "type": type(error).__name__, "step": step, "method": method},
        )
        recorder.write()

    cdp = NativeCdp(native, core, retained_delegates, fail)
    expression = """(() => {
      const region = document.querySelector('.nami-plan-review__detail:not([hidden])');
      if (!(region instanceof HTMLElement)) throw new Error('expanded detail is unavailable');
      region.scrollTop = 0;
      region.focus();
      return region.scrollTop;
    })()"""

    def complete(value: object, after: object) -> None:
        dimensions = decode_png(target)
        _execute_script_checked(
            core,
            "globalThis.__namiGalleryA1Keyboard = "
            + json.dumps({"before": value, "after": after, "capture": True, "dimensions": dimensions})
            + ";",
            stage="a1_keyboard", recorder=recorder,
            retained_delegates=retained_delegates,
        )

    def before(value: object) -> None:
        if type(value) not in {int, float}:
            raise TypeError("native keyboard start position is invalid")
        cdp.dispatch(
            {"type": "keyDown", "key": "PageDown", "code": "PageDown", "windowsVirtualKeyCode": 34},
            lambda: cdp.dispatch(
                {"type": "keyUp", "key": "PageDown", "code": "PageDown", "windowsVirtualKeyCode": 34},
                lambda: cdp.evaluate(
                    """(async () => {
                      const region = document.querySelector('.nami-plan-review__detail:not([hidden])');
                      if (!(region instanceof HTMLElement)) throw new Error('expanded detail is unavailable');
                      for (let frame = 0; frame < 120 && region.scrollTop <= """
                    + json.dumps(value)
                    + """; frame += 1) {
                        await new Promise((resolve) => requestAnimationFrame(resolve));
                      }
                      return region.scrollTop;
                    })()""",
                    lambda after: cdp.capture(
                        target,
                        lambda: complete(value, after),
                        "a1_keyboard_capture",
                    ),
                    "a1_keyboard_after",
                ),
                "a1_keyboard_up",
            ),
            "a1_keyboard_down",
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    start = Action(lambda: cdp.evaluate(expression, before, "a1_keyboard_focus"))
    retained_delegates.append(start)
    native.BeginInvoke(start)


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
    wheel_scheduler: dict[str, object] = {}
    a1_keyboard_scheduler: dict[str, object] = {}
    minimum_window_scheduler: dict[str, object] = {}
    minimum_window_status = _MinimumWindowStatus()

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
            minimum_window_status.set_pending("pseudo_states")
            callback(targets)

        def wheel(target: str) -> None:
            callback = wheel_scheduler.get("value")
            if not callable(callback):
                raise RuntimeError("component gallery wheel owner is pending")
            minimum_window_status.set_pending(f"wheel_{target}")
            callback(target)

        def minimum_window() -> None:
            callback = minimum_window_scheduler.get("value")
            if not callable(callback):
                raise RuntimeError("component gallery minimum window owner is pending")
            callback()

        def a1_keyboard() -> None:
            callback = a1_keyboard_scheduler.get("value")
            if not callable(callback):
                raise RuntimeError("component gallery A1 keyboard owner is pending")
            callback()

        def read_minimum_window() -> dict[str, object]:
            return minimum_window_status.read()

        def read_native_diagnostic() -> dict[str, object] | None:
            return minimum_window_status.read_diagnostic()

        return {
            "test_report": _test_report_spec(
                recorder,
                schedule,
                arguments.mode,
                wheel,
                minimum_window,
                read_minimum_window,
                read_native_diagnostic,
                a1_keyboard,
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
                    _install_minimum_window_scheduler(
                        window=window,
                        native=native,
                        action=Action,
                        retained_delegates=retained_delegates,
                        scheduler=minimum_window_scheduler,
                        status=minimum_window_status,
                        recorder=recorder,
                    )
                    core = native.browser.webview.CoreWebView2
                    wheel_scheduler["value"] = lambda target: _schedule_preview_wheel(
                        native, core, target, recorder, retained_delegates,
                    )
                    a1_keyboard_scheduler["value"] = lambda: _schedule_a1_keyboard_capture(
                        native,
                        core,
                        arguments.evidence_dir / "a1-native-minimum.png",
                        recorder,
                        retained_delegates,
                    )
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
