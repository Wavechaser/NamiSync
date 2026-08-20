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


_ASSET_NAMES = ("index.html", "tokens.css", "components.css")
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
_STATUS_KEYS = frozenset(
    {
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
)
_OPERATION_KEYS = frozenset(
    {
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
)
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
_CONTROL_REPORT_CHUNK_ROWS = 10
_CONTROL_REPORT_ROW_COUNT = len(_CONTROL_KEYS) * len(_CONTROL_STATES)
_CONTROL_REPORT_CHUNK_COUNT = math.ceil(
    _CONTROL_REPORT_ROW_COUNT / _CONTROL_REPORT_CHUNK_ROWS
)
_REPORT_PART_NAMES = (
    ("statuses", "operations")
    + ("controls",) * _CONTROL_REPORT_CHUNK_COUNT
    + ("control_contract", "motion", "icons")
)


class _Recorder:
    def __init__(self, evidence_paths: EvidencePaths, mode: str) -> None:
        self._publisher = EvidencePublisher(evidence_paths)
        self._lock = threading.Lock()
        self._initial: str | None = None
        self._post_ready_failure: dict[str, str] | None = None
        self._data: dict[str, Any] = {
            "schema_version": 1,
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
            if payload["targets"] != _EXPECTED_PSEUDO_TARGETS:
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
                    name in {"statuses", "operations", "controls"}
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
            "statuses": values["statuses"],
            "operations": values["operations"],
            "controls": controls,
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
    statuses = payload["statuses"]
    operations = payload["operations"]
    controls = payload["controls"]
    control_contract = payload["control_contract"]
    return (
        type(payload["mode"]) is str
        and payload["mode"] in _EXPECTED_MEDIA
        and (expected_mode is None or payload["mode"] == expected_mode)
        and set(media) == {"dark", "forced", "reduced"}
        and all(type(media[name]) is bool for name in media)
        and media == _EXPECTED_MEDIA[payload["mode"]]
        and _valid_cosmetic_evidence(
            cosmetic,
            expected_theme=_EXPECTED_THEME[payload["mode"]],
        )
        and _valid_semantic_rows(statuses, _STATUS_KEYS)
        and _valid_semantic_rows(operations, _OPERATION_KEYS)
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
    expected: frozenset[str],
) -> bool:
    keys = {
        "key",
        "text",
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
            and all(
                type(row[name]) is str and bool(row[name])
                for name in keys
                - {
                    "key",
                    "aliases_consumed",
                    "large_text",
                    "shape_width",
                    "shape_height",
                }
            )
            and all(
                type(row[name]) in {int, float}
                and math.isfinite(row[name])
                and row[name] >= 0
                for name in ("shape_width", "shape_height")
            )
            and type(row["aliases_consumed"]) is bool
            and type(row["large_text"]) is bool
            for row in rows
        )
        and {row["key"] for row in rows} == expected
    )


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
    return (
        type(rows) is list
        and len(rows) == len(expected)
        and all(
            type(row) is dict
            and set(row) == keys
            and all(type(row[name]) is str for name in keys)
            for row in rows
        )
        and {(row["control"], row["state"]) for row in rows} == expected
    )


def _valid_control_contract(value: object) -> bool:
    if type(value) is not dict or set(value) != {
        "tri_state",
        "dialog_exit",
        "segmented",
    }:
        return False
    tri_state = value["tri_state"]
    dialog_exit = value["dialog_exit"]
    segmented = value["segmented"]
    return (
        type(tri_state) is dict
        and set(tri_state) == {"aria_checked", "indeterminate", "cue_content"}
        and tri_state["aria_checked"] == "mixed"
        and tri_state["indeterminate"] is True
        and type(tri_state["cue_content"]) is str
        and tri_state["cue_content"] not in {"", "none", "normal"}
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
                    pseudo_scheduler["value"] = (
                        lambda targets: _schedule_pseudo_states(
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
