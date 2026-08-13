"""Installed-wheel child process for the SH-G-12 native material gate."""

from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import importlib.metadata
import json
import sys
import threading
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch


_SCENARIOS = (
    "capable",
    "controller-failure",
    "main-window-failure",
    "light-no-material",
    "dark-no-material",
    "high-contrast",
)
_FAILURE_STAGES = frozenset(
    {
        "appearance_observer",
        "page_probe",
        "screenshot_capture",
        "screenshot_analysis",
        "child",
    }
)
_PAGE_PROBE = r"""
(async () => {
  "use strict";
  const expectedMaterial = __EXPECTED_MATERIAL__;
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const root = document.documentElement;
    const material = root.getAttribute("data-window-material");
    const dispatchReady = typeof window.pywebview?.api?.dispatch === "function";
    if (material === expectedMaterial && dispatchReady) {
      break;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 50));
  }
  const root = document.documentElement;
  if (root.getAttribute("data-window-material") !== expectedMaterial) {
    throw new Error("material publication unavailable");
  }
  if (typeof window.pywebview?.api?.dispatch !== "function") {
    throw new Error("production dispatch unavailable");
  }
  const dispatchResponse = await window.pywebview.api.dispatch(JSON.stringify({
    schema_version: 1,
    request_id: "12121212121212121212121212121212",
    command: "materials_probe",
    payload: {},
  }));
  if (dispatchResponse?.ok !== false ||
      dispatchResponse?.error?.code !== "unknown_command") {
    throw new Error("production dispatch refusal unavailable");
  }
  const app = document.querySelector("#app");
  const status = document.querySelector("#host-status");
  if (!(app instanceof HTMLElement) || !(status instanceof HTMLElement)) {
    throw new Error("packaged page unavailable");
  }
  app.replaceChildren();
  app.style.display = "grid";
  app.style.gap = "24px";
  app.style.inlineSize = "min(640px, calc(100vw - 128px))";
  app.style.textAlign = "start";
  const heading = document.createElement("h1");
  heading.textContent = "NamiSync material gate";
  const first = document.createElement("article");
  first.className = "nami-card";
  first.id = "materials-card-primary";
  const firstHeading = document.createElement("h2");
  firstHeading.textContent = "Known opaque card";
  const firstBody = document.createElement("p");
  firstBody.textContent = "The surrounding gutter remains the window base.";
  first.append(firstHeading, firstBody);
  const second = document.createElement("article");
  second.className = "nami-card";
  second.id = "materials-card-secondary";
  const secondHeading = document.createElement("h2");
  secondHeading.textContent = "Second surface";
  const secondBody = document.createElement("p");
  secondBody.textContent = "This specimen makes the base-to-card seam visible.";
  second.append(secondHeading, secondBody);
  status.textContent = __COMPLETE_TEXT__;
  app.append(heading, first, second, status);
  await new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const rootStyle = getComputedStyle(root);
  const bodyStyle = getComputedStyle(document.body);
  const cardStyle = getComputedStyle(first);
  const cardRect = first.getBoundingClientRect();
  return {
    ready_state: document.readyState,
    dispatch_type: typeof window.pywebview.api.dispatch,
    dispatch_refusal: dispatchResponse.error.code,
    material: root.getAttribute("data-window-material"),
    theme: root.getAttribute("data-theme"),
    high_contrast: root.getAttribute("data-high-contrast"),
    inline_accent: root.style.getPropertyValue("--color-accent").trim(),
    inline_accent_hover: root.style
      .getPropertyValue("--color-accent-hover").trim(),
    inline_accent_pressed: root.style
      .getPropertyValue("--color-accent-pressed").trim(),
    inline_accent_foreground: root.style
      .getPropertyValue("--color-accent-foreground").trim(),
    inline_accent_hover_foreground: root.style
      .getPropertyValue("--color-accent-hover-foreground").trim(),
    inline_accent_pressed_foreground: root.style
      .getPropertyValue("--color-accent-pressed-foreground").trim(),
    root_background: rootStyle.backgroundColor,
    body_background: bodyStyle.backgroundColor,
    window_base: rootStyle.getPropertyValue("--color-window-base").trim(),
    card_background: cardStyle.backgroundColor,
    card_rect: {
      left: cardRect.left,
      top: cardRect.top,
      right: cardRect.right,
      bottom: cardRect.bottom,
    },
    card_sample: { x: cardRect.right - 24, y: cardRect.bottom - 16 },
    viewport: { width: innerWidth, height: innerHeight },
    gutter_points: [
      { x: 16, y: 16 },
      { x: innerWidth - 17, y: 16 },
      { x: 16, y: innerHeight - 17 },
    ],
    status: status.textContent,
  };
})()
"""


class _Recorder:
    def __init__(self, output: Path, scenario: str) -> None:
        self._output = output
        self._lock = threading.Lock()
        self._failed = False
        self._data: dict[str, Any] = {
            "schema_version": 1,
            "scenario": scenario,
            "phase": "starting",
            "startup_errors": [],
            "native_operations": [],
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

    def failure(self, stage: str, error: BaseException) -> None:
        if stage not in _FAILURE_STAGES:
            stage = "child"
        with self._lock:
            if self._failed or self._data["phase"] == "complete":
                return
            self._failed = True
            self._data["failure"] = {
                "stage": stage,
                "type": _sanitized_error_type(error),
            }
            self._data["phase"] = "failure"
            self._write_locked()

    @property
    def failed(self) -> bool:
        with self._lock:
            return self._failed

    def complete(self) -> bool:
        with self._lock:
            if self._failed:
                return False
            self._data["phase"] = "complete"
            self._write_locked()
            return True

    def write(self) -> None:
        with self._lock:
            self._write_locked()

    def _write_locked(self) -> None:
        encoded = json.dumps(self._data, indent=2, sort_keys=True)
        temporary = self._output.with_suffix(self._output.suffix + ".tmp")
        temporary.write_text(encoded, encoding="utf-8")
        temporary.replace(self._output)


def _sanitized_error_type(error: BaseException) -> str:
    name = type(error).__name__
    if name in {
        "AssertionError",
        "AttributeError",
        "RuntimeError",
        "TypeError",
        "ValueError",
    }:
        return name
    return "Error"


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=_SCENARIOS, required=True)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--mutex", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--screenshot", required=True, type=Path)
    return parser.parse_args()


def _runtime_identity() -> dict[str, object]:
    import namisync
    from namisync.interfaces.web import appearance, host

    return {
        "executable": str(Path(sys.executable).resolve()),
        "namisync_file": str(Path(namisync.__file__).resolve()),
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("namisync", "pywebview", "pythonnet")
        },
        "sources": {
            name: _source_evidence(module)
            for name, module in (("appearance.py", appearance), ("host.py", host))
        },
    }


def _source_evidence(module: object) -> dict[str, object]:
    path = Path(str(module.__file__)).resolve()
    content = path.read_bytes()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
    }


def _appearance_snapshot(value: object) -> dict[str, object]:
    return {
        "dark": bool(value.dark),
        "high_contrast": bool(value.high_contrast),
        "accent": str(value.accent),
        "accent_hover": str(value.accent_hover),
        "accent_pressed": str(value.accent_pressed),
        "accent_foreground": str(value.accent_foreground),
        "accent_hover_foreground": str(value.accent_hover_foreground),
        "accent_pressed_foreground": str(value.accent_pressed_foreground),
        "build": int(value.build),
        "supports_mica": bool(value.supports_mica),
    }


def _color_snapshot(value: object) -> dict[str, int]:
    return {
        "a": int(value.A),
        "r": int(value.R),
        "g": int(value.G),
        "b": int(value.B),
    }


def _window_handle(native_window: object) -> int:
    handle = native_window.Handle
    return int(handle.ToInt64() if hasattr(handle, "ToInt64") else handle)


def _dwm_attribute(
    native_window: object,
    attribute: int,
) -> dict[str, object]:
    value = ctypes.c_int()
    getter = ctypes.windll.dwmapi.DwmGetWindowAttribute
    getter.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_void_p,
        ctypes.c_uint,
    )
    getter.restype = ctypes.c_long
    result = int(
        getter(
            _window_handle(native_window),
            attribute,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
    )
    return {"hresult": result, "value": value.value if result >= 0 else None}


def _window_style(native_window: object) -> dict[str, object]:
    user32 = ctypes.windll.user32
    getter = user32.GetWindowLongPtrW
    getter.argtypes = (ctypes.c_void_p, ctypes.c_int)
    getter.restype = ctypes.c_ssize_t
    style = int(getter(_window_handle(native_window), -16)) & 0xFFFFFFFF
    required = {
        "caption": 0x00C00000,
        "thickframe": 0x00040000,
        "sysmenu": 0x00080000,
    }
    return {
        "value": style,
        "caption": style & required["caption"] == required["caption"],
        "thickframe": bool(style & required["thickframe"]),
        "sysmenu": bool(style & required["sysmenu"]),
    }


def _native_snapshot(native_window: object) -> dict[str, object]:
    return {
        "ui_thread": not bool(native_window.InvokeRequired),
        "controller_background": _color_snapshot(
            native_window.browser.webview.DefaultBackgroundColor
        ),
        "form_background": _color_snapshot(native_window.BackColor),
        "dwm_dark_mode": _dwm_attribute(native_window, 20),
        "dwm_backdrop": _dwm_attribute(native_window, 38),
        "window_style": _window_style(native_window),
    }


def _protocol_value(task: object) -> dict[str, object]:
    if task.IsFaulted or task.IsCanceled:
        raise RuntimeError("native CDP task failed")
    envelope = json.loads(str(task.Result))
    if type(envelope) is not dict or "exceptionDetails" in envelope:
        raise RuntimeError("native CDP expression failed")
    remote = envelope.get("result")
    if type(remote) is not dict or remote.get("type") != "object":
        raise TypeError("native CDP result is invalid")
    value = remote.get("value")
    if type(value) is not dict:
        raise TypeError("native CDP result is invalid")
    return value


def _sample_screenshot(
    content: bytes,
    page: dict[str, object],
) -> dict[str, object]:
    import clr

    clr.AddReference("System.Drawing")
    from System import Array, Byte
    from System.Drawing import Bitmap
    from System.IO import MemoryStream

    stream = MemoryStream(Array[Byte](content))
    bitmap = Bitmap(stream)
    try:
        viewport = page["viewport"]
        if type(viewport) is not dict:
            raise AssertionError("screenshot viewport mismatch")
        scale_x = bitmap.Width / float(viewport["width"])
        scale_y = bitmap.Height / float(viewport["height"])
        if not (0.5 <= scale_x <= 4.0 and 0.5 <= scale_y <= 4.0):
            raise AssertionError("screenshot viewport mismatch")

        def sample(x: float, y: float) -> dict[str, int]:
            horizontal = min(bitmap.Width - 1, max(0, round(x * scale_x)))
            vertical = min(bitmap.Height - 1, max(0, round(y * scale_y)))
            return _color_snapshot(bitmap.GetPixel(horizontal, vertical))

        gutter_points = page["gutter_points"]
        if type(gutter_points) is not list or len(gutter_points) != 3:
            raise TypeError("gutter points are invalid")
        gutters = [
            sample(float(point["x"]), float(point["y"]))
            for point in gutter_points
            if type(point) is dict
        ]
        if len(gutters) != 3:
            raise TypeError("gutter points are invalid")
        card = page["card_sample"]
        if type(card) is not dict:
            raise TypeError("card sample is invalid")
        card_pixel = sample(float(card["x"]), float(card["y"]))
        return {
            "width": int(bitmap.Width),
            "height": int(bitmap.Height),
            "scale_x": scale_x,
            "scale_y": scale_y,
            "gutter_pixels": gutters,
            "card_pixel": card_pixel,
        }
    finally:
        bitmap.Dispose()
        stream.Dispose()


def _begin_page_probe(
    window: object,
    *,
    scenario: str,
    expected_material: str,
    screenshot: Path,
    recorder: _Recorder,
    retained: list[object],
) -> None:
    from System import Action

    native_window = window.native
    if native_window.InvokeRequired:
        raise RuntimeError("loaded observer left the UI thread")
    recorder.set(
        "load_health",
        {
            "ui_thread": True,
            "source": str(native_window.browser.webview.CoreWebView2.Source),
        },
    )
    core = native_window.browser.webview.CoreWebView2
    complete_text = f"Materials {scenario} complete"
    expression = _PAGE_PROBE.replace(
        "__EXPECTED_MATERIAL__",
        json.dumps(expected_material),
    ).replace("__COMPLETE_TEXT__", json.dumps(complete_text))
    task = core.CallDevToolsProtocolMethodAsync(
        "Runtime.evaluate",
        json.dumps(
            {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
            separators=(",", ":"),
        ),
    )

    def page_completed() -> None:
        def on_ui() -> None:
            try:
                page = _protocol_value(task)
                recorder.set("page", page)
                recorder.set("native_final", _native_snapshot(native_window))
                capture = core.CallDevToolsProtocolMethodAsync(
                    "Page.captureScreenshot",
                    '{"format":"png","fromSurface":true,"captureBeyondViewport":false}',
                )

                def screenshot_completed() -> None:
                    def finish_on_ui() -> None:
                        try:
                            if capture.IsFaulted or capture.IsCanceled:
                                raise RuntimeError("native screenshot task failed")
                            response = json.loads(str(capture.Result))
                            if type(response) is not dict or type(
                                response.get("data")
                            ) is not str:
                                raise TypeError("native screenshot result is invalid")
                            content = base64.b64decode(
                                response["data"],
                                validate=True,
                            )
                            if not content.startswith(b"\x89PNG\r\n\x1a\n"):
                                raise ValueError("native screenshot is not PNG")
                            screenshot.write_bytes(content)
                            recorder.set(
                                "screenshot",
                                {
                                    "path": str(screenshot.resolve()),
                                    "sha256": hashlib.sha256(content).hexdigest(),
                                    "size": len(content),
                                    "samples": _sample_screenshot(content, page),
                                },
                            )
                            recorder.complete()
                        except BaseException as error:
                            recorder.failure("screenshot_analysis", error)

                    action = Action(finish_on_ui)
                    retained.append(action)
                    native_window.BeginInvoke(action)

                completion = Action(screenshot_completed)
                retained.append(completion)
                capture.GetAwaiter().OnCompleted(completion)
            except BaseException as error:
                recorder.failure("page_probe", error)

        action = Action(on_ui)
        retained.append(action)
        native_window.BeginInvoke(action)

    completion = Action(page_completed)
    retained.append(completion)
    task.GetAwaiter().OnCompleted(completion)


def _install_native_boundary_observers(
    stack: ExitStack,
    *,
    scenario: str,
    recorder: _Recorder,
    screenshot: Path,
) -> list[object]:
    from namisync.interfaces.web import appearance

    retained: list[object] = []
    observations: dict[str, Any] = {}
    original_read = appearance._WindowsAppearanceNative.read
    original_controller = appearance._WindowsAppearanceNative._set_controller_background
    original_glass = appearance._WindowsAppearanceNative._set_client_glass
    original_dwm = appearance._WindowsAppearanceNative._set_dwm_attribute
    from namisync.interfaces.web.appearance import (
        configure_window_appearance as original_configure,
    )

    def read(native: object):
        actual = original_read(native)
        recorder.set("actual_system", _appearance_snapshot(actual))
        observations["actual_system"] = actual
        if scenario == "capable":
            selected = actual
        elif scenario == "light-no-material":
            selected = appearance.SystemAppearance(
                dark=False,
                high_contrast=False,
                accent=actual.accent,
                build=appearance._MICA_MINIMUM_BUILD - 1,
                accent_hover=actual.accent_hover,
                accent_pressed=actual.accent_pressed,
            )
        elif scenario == "dark-no-material":
            selected = appearance.SystemAppearance(
                dark=True,
                high_contrast=False,
                accent=actual.accent,
                build=appearance._MICA_MINIMUM_BUILD - 1,
                accent_hover=actual.accent_hover,
                accent_pressed=actual.accent_pressed,
            )
        elif scenario == "high-contrast":
            selected = appearance.SystemAppearance(
                dark=actual.dark,
                high_contrast=True,
                accent=actual.accent,
                build=max(actual.build, appearance._MICA_MINIMUM_BUILD),
                accent_hover=actual.accent_hover,
                accent_pressed=actual.accent_pressed,
            )
        else:
            selected = appearance.SystemAppearance(
                dark=actual.dark,
                high_contrast=False,
                accent=actual.accent,
                build=max(actual.build, appearance._MICA_MINIMUM_BUILD),
                accent_hover=actual.accent_hover,
                accent_pressed=actual.accent_pressed,
            )
        recorder.set("selected_system", _appearance_snapshot(selected))
        recorder.set("opaque_system_color", native.opaque_background(selected))
        return selected

    def controller(
        native: object,
        native_window: object,
        system: object,
        *,
        transparent: bool,
    ) -> object:
        injected = scenario == "controller-failure" and transparent
        if injected:
            result = appearance._BackgroundLanding(False, False)
        else:
            result = original_controller(
                native,
                native_window,
                system,
                transparent=transparent,
            )
        landed = appearance._require_background_landing(result)
        succeeded = (
            landed.controller
            if transparent
            else landed.form and landed.controller
        )
        recorder.append(
            "native_operations",
            {
                "operation": "controller_background",
                "transparent": transparent,
                "injected_failure": injected,
                "result": succeeded,
                "form_landed": landed.form,
                "controller_landed": landed.controller,
            },
        )
        return result

    def glass(
        native: object,
        native_window: object,
        *,
        enabled: bool,
    ) -> bool:
        result = original_glass(native, native_window, enabled=enabled)
        recorder.append(
            "native_operations",
            {
                "operation": "client_glass",
                "enabled": enabled,
                "injected_failure": False,
                "result": bool(result),
            },
        )
        return bool(result)

    def dwm(
        native: object,
        native_window: object,
        attribute: int,
        value: int,
    ) -> bool:
        injected = (
            scenario == "main-window-failure"
            and attribute == appearance._DWMWA_SYSTEMBACKDROP_TYPE
            and value == appearance._DWMSBT_MAINWINDOW
        )
        if injected:
            result = False
        else:
            result = original_dwm(native, native_window, attribute, value)
        recorder.append(
            "native_operations",
            {
                "operation": "dwm_attribute",
                "attribute": attribute,
                "value": value,
                "injected_failure": injected,
                "result": bool(result),
            },
        )
        return bool(result)

    def configure(window: object, *args: object, **kwargs: object):
        controller_owner = original_configure(window, *args, **kwargs)

        def after_appearance() -> None:
            try:
                native_window = window.native
                observations["native_window"] = native_window
                recorder.set("native_after_apply", _native_snapshot(native_window))
            except BaseException as error:
                recorder.failure("appearance_observer", error)

        def after_loaded() -> None:
            def begin_page_probe_on_ui() -> None:
                try:
                    if recorder.failed:
                        return
                    actual_system = observations.get("actual_system")
                    if actual_system is None:
                        raise RuntimeError("appearance snapshot is unavailable")
                    expected_material = (
                        "mica"
                        if scenario == "capable"
                        and actual_system.supports_mica
                        and not actual_system.high_contrast
                        else "opaque"
                    )
                    _begin_page_probe(
                        window,
                        scenario=scenario,
                        expected_material=expected_material,
                        screenshot=screenshot,
                        recorder=recorder,
                        retained=retained,
                    )
                except BaseException as error:
                    recorder.failure("page_probe", error)

            try:
                if recorder.failed:
                    return
                native_window = observations.get("native_window")
                if native_window is None:
                    raise RuntimeError("native window is unavailable")
                from System import Action

                action = Action(begin_page_probe_on_ui)
                retained.append(action)
                native_window.BeginInvoke(action)
            except BaseException as error:
                recorder.failure("page_probe", error)

        retained.extend((after_appearance, after_loaded))
        window.events.before_load += after_appearance
        window.events.loaded += after_loaded
        return controller_owner

    stack.enter_context(
        patch.object(appearance._WindowsAppearanceNative, "read", read)
    )
    stack.enter_context(
        patch.object(
            appearance._WindowsAppearanceNative,
            "_set_controller_background",
            controller,
        )
    )
    stack.enter_context(
        patch.object(
            appearance._WindowsAppearanceNative,
            "_set_client_glass",
            glass,
        )
    )
    stack.enter_context(
        patch.object(
            appearance._WindowsAppearanceNative,
            "_set_dwm_attribute",
            dwm,
        )
    )
    from namisync.interfaces.web import host

    stack.enter_context(patch.object(host, "_configure_window_appearance", configure))
    return retained


def _run(arguments: argparse.Namespace, recorder: _Recorder) -> int:
    from namisync.interfaces.web import host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths

    recorder.set("runtime", _runtime_identity())
    screenshot = arguments.screenshot.resolve()
    with ExitStack() as stack:
        _retained = _install_native_boundary_observers(
            stack,
            scenario=arguments.scenario,
            recorder=recorder,
            screenshot=screenshot,
        )
        exit_code = host.run_desktop(
            AppPaths.from_root(arguments.data_dir),
            DesktopInstanceIdentity(arguments.mutex, arguments.title),
            startup_error=recorder.startup_error,
        )

    del _retained
    recorder.set("exit_code", exit_code)
    recorder.write()
    return exit_code


def main() -> int:
    arguments = _parse_arguments()
    recorder = _Recorder(arguments.output, arguments.scenario)
    try:
        return _run(arguments, recorder)
    except BaseException as error:
        recorder.failure("child", error)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
