"""SH-G-12 ordinary and fault-injection evidence for native materials."""

from __future__ import annotations

import ctypes
import inspect
import sys
from threading import Event, Lock, Thread, current_thread
from types import SimpleNamespace
from typing import Any

import pytest

import namisync.interfaces.web.appearance as appearance
from namisync.interfaces.web.appearance import (
    SystemAppearance,
    configure_window_appearance,
    opaque_window_background,
)


class _Hook:
    def __init__(self) -> None:
        self.handlers: list[object] = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def __isub__(self, handler):
        self.handlers.remove(handler)
        return self

    def emit(self) -> None:
        for handler in tuple(self.handlers):
            handler()


class _RefusingHook(_Hook):
    def __iadd__(self, handler):
        del handler
        raise RuntimeError("injected event refusal")


class _Attributes:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []
        self.updated = Event()

    def update(self, values: dict[str, Any]) -> None:
        self.updates.append(dict(values))
        self.updated.set()


class _BlockingAttributes(_Attributes):
    def __init__(self) -> None:
        super().__init__()
        self.first_entered = Event()
        self.release_first = Event()
        self.second_updated = Event()
        self._state_lock = Lock()
        self._active = 0
        self.max_active = 0

    def update(self, values: dict[str, Any]) -> None:
        with self._state_lock:
            self._active += 1
            self.max_active = max(self.max_active, self._active)
            ordinal = len(self.updates)
        try:
            if ordinal == 0:
                self.first_entered.set()
                if not self.release_first.wait(1.0):
                    raise RuntimeError("test publication release timed out")
            super().update(values)
            if len(self.updates) >= 2:
                self.second_updated.set()
        finally:
            with self._state_lock:
                self._active -= 1


class _ExitWakeLock:
    def __init__(self, wake) -> None:
        self._lock = Lock()
        self._wake = wake
        self._publisher_exits = 0
        self._fired = False

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self._lock.release()
        if current_thread().name != "namisync-appearance-publish":
            return
        self._publisher_exits += 1
        if self._publisher_exits == 3 and not self._fired:
            self._fired = True
            self._wake()


class _Dom:
    def __init__(self) -> None:
        self.attributes = _Attributes()
        self.selectors: list[str] = []

    def get_element(self, selector: str):
        self.selectors.append(selector)
        return SimpleNamespace(attributes=self.attributes)


class _FakeNative:
    def __init__(self, system: SystemAppearance) -> None:
        self.system = system
        self.calls: list[object] = []
        self.preference_handlers: list[object] = []
        self.apply_result = "mica"
        self.apply_error: Exception | None = None
        self.read_error: Exception | None = None
        self.force_opaque_result = True

    def read(self) -> SystemAppearance:
        self.calls.append("read")
        if self.read_error is not None:
            raise self.read_error
        return self.system

    def opaque_background(self, system: SystemAppearance) -> str:
        self.calls.append(("opaque_background", system))
        return "#F3F3F3"

    def apply(self, native_window: object, system: SystemAppearance):
        self.calls.append(("apply", native_window, system))
        if self.apply_error is not None:
            raise self.apply_error
        return self.apply_result

    def force_opaque(
        self,
        native_window: object,
        system: SystemAppearance,
    ) -> bool:
        self.calls.append(("force_opaque", native_window, system))
        return self.force_opaque_result

    def invoke(self, native_window: object, callback) -> None:
        self.calls.append(("invoke", native_window))
        callback()

    def subscribe(self, callback):
        self.calls.append("subscribe")
        self.preference_handlers.append(callback)

        def unsubscribe() -> None:
            self.calls.append("unsubscribe")
            self.preference_handlers.remove(callback)

        return unsubscribe

    def emit_preference_change(self) -> None:
        for handler in tuple(self.preference_handlers):
            handler()


def _system(
    *,
    dark: bool = False,
    high_contrast: bool = False,
    build: int = 22621,
    accent: str = "#123ABC",
) -> SystemAppearance:
    return SystemAppearance(dark, high_contrast, accent, build)


def _window() -> SimpleNamespace:
    return SimpleNamespace(
        native=SimpleNamespace(InvokeRequired=False),
        events=SimpleNamespace(before_load=_Hook(), loaded=_Hook()),
        dom=_Dom(),
    )


def _patch_native_calls(
    monkeypatch: pytest.MonkeyPatch,
    native: appearance._WindowsAppearanceNative,
    *,
    transparent_succeeds: bool = True,
    glass_succeeds: bool = True,
    failed_dwm_call: tuple[int, int] | None = None,
) -> list[tuple[object, ...]]:
    calls: list[tuple[object, ...]] = []

    def background(
        _window: object,
        _system: SystemAppearance,
        *,
        transparent: bool,
    ) -> bool:
        calls.append(("controller", transparent))
        return transparent_succeeds if transparent else True

    def dwm(_window: object, attribute: int, value: int) -> bool:
        calls.append(("dwm", attribute, value))
        return (attribute, value) != failed_dwm_call

    def glass(_window: object, *, enabled: bool) -> bool:
        calls.append(("glass", enabled))
        return glass_succeeds if enabled else True

    monkeypatch.setattr(native, "_set_controller_background", background)
    monkeypatch.setattr(native, "_set_client_glass", glass)
    monkeypatch.setattr(native, "_set_dwm_attribute", dwm)
    return calls


@pytest.mark.parametrize("dark", (False, True))
def test_sh_g_12_progressively_applies_mica_after_transparency(
    monkeypatch: pytest.MonkeyPatch,
    dark: bool,
) -> None:
    native = appearance._WindowsAppearanceNative()
    calls = _patch_native_calls(monkeypatch, native)
    window = object()

    material = native.apply(window, _system(dark=dark))

    assert material == "mica"
    assert calls == [
        ("controller", True),
        ("glass", True),
        (
            "dwm",
            appearance._DWMWA_USE_IMMERSIVE_DARK_MODE,
            int(dark),
        ),
        (
            "dwm",
            appearance._DWMWA_SYSTEMBACKDROP_TYPE,
            appearance._DWMSBT_MAINWINDOW,
        ),
    ]


def test_sh_g_12_native_capable_order_is_alpha_glass_black_dark_then_mica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transparent = object()
    black = object()
    calls: list[tuple[object, ...]] = []

    class Color:
        Transparent = transparent
        Black = black

    class WebView:
        @property
        def DefaultBackgroundColor(self) -> object | None:
            return None

        @DefaultBackgroundColor.setter
        def DefaultBackgroundColor(self, value: object) -> None:
            calls.append(("controller", value))

    class NativeWindow:
        Handle = 0x1234
        browser = SimpleNamespace(webview=WebView())

        @property
        def BackColor(self) -> object | None:
            return None

        @BackColor.setter
        def BackColor(self, value: object) -> None:
            calls.append(("form", value))

    def extend(handle: int, margins_pointer: object) -> int:
        margins = ctypes.cast(
            margins_pointer,
            ctypes.POINTER(appearance._MARGINS),
        ).contents
        calls.append(
            (
                "glass",
                int(handle),
                margins.cxLeftWidth,
                margins.cxRightWidth,
                margins.cyTopHeight,
                margins.cyBottomHeight,
            )
        )
        return 0

    def set_attribute(
        handle: int,
        attribute: int,
        value_pointer: object,
        size: int,
    ) -> int:
        value = ctypes.cast(
            value_pointer,
            ctypes.POINTER(ctypes.c_int),
        ).contents.value
        calls.append(("dwm", int(handle), attribute, value, size))
        return 0

    monkeypatch.setitem(sys.modules, "System.Drawing", SimpleNamespace(Color=Color))
    monkeypatch.setattr(
        appearance.ctypes,
        "windll",
        SimpleNamespace(
            dwmapi=SimpleNamespace(
                DwmExtendFrameIntoClientArea=extend,
                DwmSetWindowAttribute=set_attribute,
            )
        ),
        raising=False,
    )

    assert appearance._WindowsAppearanceNative().apply(
        NativeWindow(),
        _system(dark=True),
    ) == "mica"
    assert calls == [
        ("controller", transparent),
        ("glass", 0x1234, -1, -1, -1, -1),
        ("form", black),
        (
            "dwm",
            0x1234,
            appearance._DWMWA_USE_IMMERSIVE_DARK_MODE,
            1,
            ctypes.sizeof(ctypes.c_int()),
        ),
        (
            "dwm",
            0x1234,
            appearance._DWMWA_SYSTEMBACKDROP_TYPE,
            appearance._DWMSBT_MAINWINDOW,
            ctypes.sizeof(ctypes.c_int()),
        ),
    ]


@pytest.mark.parametrize(
    ("system", "expected_dark"),
    (
        (_system(build=22000), 0),
        (_system(dark=True, build=22000), 1),
        (_system(dark=True, high_contrast=True), 0),
    ),
)
def test_sh_g_12_unsupported_or_high_contrast_is_opaque_and_system_owned(
    monkeypatch: pytest.MonkeyPatch,
    system: SystemAppearance,
    expected_dark: int,
) -> None:
    native = appearance._WindowsAppearanceNative()
    calls = _patch_native_calls(monkeypatch, native)

    material = native.apply(object(), system)

    assert material == "opaque"
    expected_calls = [
        ("glass", False),
        (
            "dwm",
            appearance._DWMWA_USE_IMMERSIVE_DARK_MODE,
            expected_dark,
        ),
        ("controller", False),
    ]
    if system.supports_mica:
        expected_calls.insert(
            0,
            (
                "dwm",
                appearance._DWMWA_SYSTEMBACKDROP_TYPE,
                appearance._DWMSBT_NONE,
            ),
        )
    assert calls == expected_calls


def test_sh_g_12_pre_material_opaque_skips_unsupported_backdrop_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Color:
        @staticmethod
        def FromArgb(alpha: int, red: int, green: int, blue: int):
            return alpha, red, green, blue

    control = SimpleNamespace(DefaultBackgroundColor=None)
    native_window = SimpleNamespace(
        BackColor=None,
        browser=SimpleNamespace(webview=control),
    )
    native = appearance._WindowsAppearanceNative()
    calls: list[tuple[object, ...]] = []

    def dwm(_window: object, attribute: int, value: int) -> bool:
        calls.append(("dwm", attribute, value))
        return attribute != appearance._DWMWA_SYSTEMBACKDROP_TYPE

    def glass(_window: object, *, enabled: bool) -> bool:
        calls.append(("glass", enabled))
        return True

    monkeypatch.setitem(sys.modules, "System.Drawing", SimpleNamespace(Color=Color))
    monkeypatch.setattr(appearance, "_system_color", lambda _index: "#010203")
    monkeypatch.setattr(native, "_set_dwm_attribute", dwm)
    monkeypatch.setattr(native, "_set_client_glass", glass)

    system = _system(dark=True, build=22000)
    assert native.apply(native_window, system) == "opaque"
    assert calls == [
        ("glass", False),
        (
            "dwm",
            appearance._DWMWA_USE_IMMERSIVE_DARK_MODE,
            1,
        ),
    ]
    assert native_window.BackColor == (255, 1, 2, 3)
    assert control.DefaultBackgroundColor == (255, 1, 2, 3)

    calls.clear()
    native_window.BackColor = None
    control.DefaultBackgroundColor = None
    assert native.force_opaque(native_window, system) is True
    assert calls == [
        ("glass", False),
        (
            "dwm",
            appearance._DWMWA_USE_IMMERSIVE_DARK_MODE,
            1,
        ),
    ]
    assert native_window.BackColor == (255, 1, 2, 3)
    assert control.DefaultBackgroundColor == (255, 1, 2, 3)


def test_sh_g_12_transparency_failure_never_attempts_mica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = appearance._WindowsAppearanceNative()
    calls = _patch_native_calls(
        monkeypatch,
        native,
        transparent_succeeds=False,
    )

    material = native.apply(object(), _system(dark=True))

    assert material == "opaque"
    assert calls == [
        ("controller", True),
        (
            "dwm",
            appearance._DWMWA_SYSTEMBACKDROP_TYPE,
            appearance._DWMSBT_NONE,
        ),
        ("glass", False),
        (
            "dwm",
            appearance._DWMWA_USE_IMMERSIVE_DARK_MODE,
            1,
        ),
        ("controller", False),
    ]
    assert (
        "dwm",
        appearance._DWMWA_SYSTEMBACKDROP_TYPE,
        appearance._DWMSBT_MAINWINDOW,
    ) not in calls


def test_sh_g_12_client_glass_failure_never_attempts_mica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = appearance._WindowsAppearanceNative()
    calls = _patch_native_calls(
        monkeypatch,
        native,
        glass_succeeds=False,
    )

    material = native.apply(object(), _system(dark=True))

    assert material == "opaque"
    assert calls == [
        ("controller", True),
        ("glass", True),
        (
            "dwm",
            appearance._DWMWA_SYSTEMBACKDROP_TYPE,
            appearance._DWMSBT_NONE,
        ),
        ("glass", False),
        (
            "dwm",
            appearance._DWMWA_USE_IMMERSIVE_DARK_MODE,
            1,
        ),
        ("controller", False),
    ]


@pytest.mark.parametrize(
    ("failed_call", "expected_calls"),
    (
        (
            (appearance._DWMWA_USE_IMMERSIVE_DARK_MODE, 1),
            [
                ("controller", True),
                ("glass", True),
                (
                    "dwm",
                    appearance._DWMWA_USE_IMMERSIVE_DARK_MODE,
                    1,
                ),
                (
                    "dwm",
                    appearance._DWMWA_SYSTEMBACKDROP_TYPE,
                    appearance._DWMSBT_NONE,
                ),
                ("glass", False),
                (
                    "dwm",
                    appearance._DWMWA_USE_IMMERSIVE_DARK_MODE,
                    1,
                ),
                ("controller", False),
            ],
        ),
        (
            (
                appearance._DWMWA_SYSTEMBACKDROP_TYPE,
                appearance._DWMSBT_MAINWINDOW,
            ),
            [
                ("controller", True),
                ("glass", True),
                (
                    "dwm",
                    appearance._DWMWA_USE_IMMERSIVE_DARK_MODE,
                    1,
                ),
                (
                    "dwm",
                    appearance._DWMWA_SYSTEMBACKDROP_TYPE,
                    appearance._DWMSBT_MAINWINDOW,
                ),
                (
                    "dwm",
                    appearance._DWMWA_SYSTEMBACKDROP_TYPE,
                    appearance._DWMSBT_NONE,
                ),
                ("glass", False),
                (
                    "dwm",
                    appearance._DWMWA_USE_IMMERSIVE_DARK_MODE,
                    1,
                ),
                ("controller", False),
            ],
        ),
    ),
)
def test_sh_g_12_dwm_failure_reverts_to_opaque_without_raising(
    monkeypatch: pytest.MonkeyPatch,
    failed_call: tuple[int, int],
    expected_calls: list[tuple[object, ...]],
) -> None:
    native = appearance._WindowsAppearanceNative()
    calls = _patch_native_calls(
        monkeypatch,
        native,
        failed_dwm_call=failed_call,
    )

    assert native.apply(object(), _system(dark=True)) == "opaque"
    assert calls == expected_calls


def test_incomplete_opaque_fallback_is_fixed_warning_and_not_confirmed(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    native = appearance._WindowsAppearanceNative()
    calls = _patch_native_calls(
        monkeypatch,
        native,
        failed_dwm_call=(
            appearance._DWMWA_SYSTEMBACKDROP_TYPE,
            appearance._DWMSBT_NONE,
        ),
    )

    assert native.force_opaque(object(), _system()) is False
    assert calls == [
        (
            "dwm",
            appearance._DWMWA_SYSTEMBACKDROP_TYPE,
            appearance._DWMSBT_NONE,
        ),
        ("glass", False),
        (
            "dwm",
            appearance._DWMWA_USE_IMMERSIVE_DARK_MODE,
            0,
        ),
        ("controller", False),
    ]
    assert "appearance.opaque_fallback_incomplete" in caplog.messages


def test_opaque_fallback_attempts_every_rollback_after_operation_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = appearance._WindowsAppearanceNative()
    calls: list[tuple[object, ...]] = []

    def dwm(_window: object, attribute: int, value: int) -> bool:
        calls.append(("dwm", attribute, value))
        if attribute == appearance._DWMWA_SYSTEMBACKDROP_TYPE:
            raise RuntimeError("injected reset exception")
        return True

    def glass(_window: object, *, enabled: bool) -> bool:
        calls.append(("glass", enabled))
        return True

    def controller(
        _window: object,
        _system: SystemAppearance,
        *,
        transparent: bool,
    ) -> bool:
        calls.append(("controller", transparent))
        return True

    monkeypatch.setattr(native, "_set_dwm_attribute", dwm)
    monkeypatch.setattr(native, "_set_client_glass", glass)
    monkeypatch.setattr(native, "_set_controller_background", controller)

    assert native.force_opaque(object(), _system()) is False
    assert calls == [
        (
            "dwm",
            appearance._DWMWA_SYSTEMBACKDROP_TYPE,
            appearance._DWMSBT_NONE,
        ),
        ("glass", False),
        (
            "dwm",
            appearance._DWMWA_USE_IMMERSIVE_DARK_MODE,
            0,
        ),
        ("controller", False),
    ]


def test_apply_does_not_claim_opaque_when_reset_cannot_be_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = appearance._WindowsAppearanceNative()
    calls = _patch_native_calls(
        monkeypatch,
        native,
        transparent_succeeds=False,
        failed_dwm_call=(
            appearance._DWMWA_SYSTEMBACKDROP_TYPE,
            appearance._DWMSBT_NONE,
        ),
    )

    assert native.apply(object(), _system()) is None
    assert calls == [
        ("controller", True),
        (
            "dwm",
            appearance._DWMWA_SYSTEMBACKDROP_TYPE,
            appearance._DWMSBT_NONE,
        ),
        ("glass", False),
        (
            "dwm",
            appearance._DWMWA_USE_IMMERSIVE_DARK_MODE,
            0,
        ),
        ("controller", False),
    ]


def test_sh_g_12_security_registration_remains_first_and_cleanup_unsubscribes() -> None:
    order: list[str] = []
    window = _window()
    window.events.before_load += lambda: order.append("security")
    native = _FakeNative(_system())
    original_apply = native.apply

    def apply(native_window: object, system: SystemAppearance):
        order.append("appearance")
        return original_apply(native_window, system)

    native.apply = apply
    controller = configure_window_appearance(window, native=native)

    window.events.before_load.emit()

    assert order == ["security", "appearance"]
    assert len(native.preference_handlers) == 1
    controller.close()
    assert native.preference_handlers == []
    assert len(window.events.before_load.handlers) == 1
    assert window.events.loaded.handlers == []
    window.events.before_load.emit()
    assert order == ["security", "appearance", "security"]
    controller.close()
    assert native.calls.count("unsubscribe") == 1


def test_partial_event_attachment_rolls_back_before_load_handler() -> None:
    window = _window()
    window.events.loaded = _RefusingHook()

    with pytest.raises(RuntimeError, match="event refusal"):
        configure_window_appearance(window, native=_FakeNative(_system()))

    assert window.events.before_load.handlers == []


def test_sh_g_12_loaded_document_gets_only_validated_inert_appearance_values() -> None:
    window = _window()
    native = _FakeNative(_system(dark=True, accent="#A1B2C3"))
    controller = configure_window_appearance(window, native=native)

    window.events.before_load.emit()
    assert window.dom.attributes.updates == []
    window.events.loaded.emit()

    assert window.dom.attributes.updated.wait(1.0)
    assert window.dom.selectors == [":root"]
    assert window.dom.attributes.updates == [
        {
            "data-theme": "dark",
            "data-window-material": "mica",
            "style": "--color-accent: #A1B2C3",
        }
    ]
    controller.close()


def test_document_publication_stays_off_the_native_ui_dispatcher() -> None:
    window = _window()
    native = _FakeNative(_system(dark=True, accent="#A1B2C3"))
    publisher_threads: list[str] = []
    original_update = window.dom.attributes.update

    def update(values: dict[str, Any]) -> None:
        publisher_threads.append(current_thread().name)
        original_update(values)

    def refuse_ui_reentry(_native_window: object, _callback: object) -> None:
        raise AssertionError("DOM publication re-entered the native UI dispatcher")

    window.dom.attributes.update = update
    native.invoke = refuse_ui_reentry
    controller = configure_window_appearance(window, native=native)

    window.events.before_load.emit()
    window.events.loaded.emit()

    assert window.dom.attributes.updated.wait(1.0)
    assert publisher_threads == ["namisync-appearance-publish"]
    assert window.dom.attributes.updates[-1] == {
        "data-theme": "dark",
        "data-window-material": "mica",
        "style": "--color-accent: #A1B2C3",
    }
    controller.close()


def test_preference_change_reasserts_native_state_after_existing_handler() -> None:
    order: list[str] = []
    window = _window()
    native = _FakeNative(_system())
    native.preference_handlers.append(lambda: order.append("pywebview"))
    original_apply = native.apply

    def apply(native_window: object, system: SystemAppearance):
        order.append("namisync")
        return original_apply(native_window, system)

    native.apply = apply
    controller = configure_window_appearance(window, native=native)
    window.events.before_load.emit()
    order.clear()
    native.system = _system(dark=True, accent="#ABCDEF")

    native.emit_preference_change()

    assert order == ["pywebview", "namisync"]
    controller.close()


def test_preference_change_republishes_after_loaded() -> None:
    window = _window()
    native = _FakeNative(_system())
    controller = configure_window_appearance(window, native=native)
    window.events.before_load.emit()
    window.events.loaded.emit()
    window.dom.attributes.updated.clear()
    native.system = _system(dark=True, accent="#ABCDEF")

    native.emit_preference_change()

    assert window.dom.attributes.updated.wait(1.0)
    assert window.dom.attributes.updates[-1] == {
        "data-theme": "dark",
        "data-window-material": "mica",
        "style": "--color-accent: #ABCDEF",
    }
    controller.close()


def test_publisher_serializes_and_finishes_with_latest_revision() -> None:
    window = _window()
    attributes = _BlockingAttributes()
    window.dom.attributes = attributes
    native = _FakeNative(_system(accent="#111111"))
    controller = configure_window_appearance(window, native=native)
    window.events.before_load.emit()

    window.events.loaded.emit()
    assert attributes.first_entered.wait(1.0)
    native.system = _system(dark=True, accent="#222222")
    native.emit_preference_change()
    attributes.release_first.set()

    assert attributes.second_updated.wait(1.0)
    assert attributes.max_active == 1
    assert attributes.updates == [
        {
            "data-theme": "light",
            "data-window-material": "mica",
            "style": "--color-accent: #111111",
        },
        {
            "data-theme": "dark",
            "data-window-material": "mica",
            "style": "--color-accent: #222222",
        },
    ]
    controller.close()


def test_publisher_does_not_lose_revision_at_worker_exit_boundary() -> None:
    window = _window()
    native = _FakeNative(_system(accent="#111111"))
    controller = configure_window_appearance(window, native=native)
    latest_updated = Event()
    original_update = window.dom.attributes.update

    def update(values: dict[str, Any]) -> None:
        original_update(values)
        if values["style"] == "--color-accent: #222222":
            latest_updated.set()

    window.dom.attributes.update = update

    def wake_at_exit_boundary() -> None:
        native.system = _system(dark=True, accent="#222222")
        native.emit_preference_change()

    controller._lock = _ExitWakeLock(wake_at_exit_boundary)
    window.events.before_load.emit()
    window.events.loaded.emit()

    assert latest_updated.wait(1.0)
    assert window.dom.attributes.updates[-1] == {
        "data-theme": "dark",
        "data-window-material": "mica",
        "style": "--color-accent: #222222",
    }
    controller.close()


def test_close_waits_for_active_publisher_to_settle() -> None:
    window = _window()
    attributes = _BlockingAttributes()
    window.dom.attributes = attributes
    native = _FakeNative(_system())
    controller = configure_window_appearance(window, native=native)
    window.events.before_load.emit()
    window.events.loaded.emit()
    assert attributes.first_entered.wait(1.0)

    close_done = Event()

    def close() -> None:
        controller.close()
        close_done.set()

    closer = Thread(target=close)
    closer.start()
    assert not close_done.wait(0.05)
    attributes.release_first.set()

    assert close_done.wait(1.0)
    closer.join(1.0)
    assert not closer.is_alive()
    assert controller._publish_thread is None
    assert not controller._publish_running
    assert appearance._PUBLISH_CLOSE_TIMEOUT_SECONDS == 1.0


def test_close_prevents_queued_read_failure_fallback_native_call() -> None:
    window = _window()
    native = _FakeNative(_system())
    queued: list[object] = []

    def queue_invoke(native_window: object, callback) -> None:
        native.calls.append(("invoke", native_window))
        queued.append(callback)

    native.invoke = queue_invoke
    controller = configure_window_appearance(window, native=native)
    window.events.before_load.emit()
    native.read_error = RuntimeError("injected preference read failure")

    native.emit_preference_change()
    assert len(queued) == 1
    controller.close()
    queued[0]()

    assert not any(
        isinstance(call, tuple) and call[0] == "force_opaque"
        for call in native.calls
    )


def test_preference_read_failure_restores_opaque_presentation() -> None:
    window = _window()
    native = _FakeNative(_system(dark=True))
    controller = configure_window_appearance(window, native=native)
    window.events.before_load.emit()
    window.events.loaded.emit()
    window.dom.attributes.updated.clear()
    native.read_error = RuntimeError("injected preference read failure")

    native.emit_preference_change()

    assert window.dom.attributes.updated.wait(1.0)
    assert any(
        isinstance(call, tuple) and call[0] == "force_opaque"
        for call in native.calls
    )
    assert window.dom.attributes.updates[-1]["data-window-material"] == "opaque"
    controller.close()


def test_unconfirmed_fallback_removes_material_claim() -> None:
    window = _window()
    native = _FakeNative(_system())
    native.apply_error = RuntimeError("injected DWM failure")
    native.force_opaque_result = False
    controller = configure_window_appearance(window, native=native)

    window.events.before_load.emit()
    window.events.loaded.emit()

    assert window.dom.attributes.updated.wait(1.0)
    assert window.dom.attributes.updates[-1] == {
        "data-theme": "light",
        "data-window-material": None,
        "style": "--color-accent: #123ABC",
    }
    controller.close()


def test_material_failure_is_nonfatal_and_forces_opaque() -> None:
    window = _window()
    native = _FakeNative(_system())
    native.apply_error = RuntimeError("injected DWM failure")
    controller = configure_window_appearance(window, native=native)

    window.events.before_load.emit()
    window.events.loaded.emit()

    assert window.dom.attributes.updated.wait(1.0)
    assert any(
        isinstance(call, tuple) and call[0] == "force_opaque"
        for call in native.calls
    )
    assert window.dom.attributes.updates[-1]["data-window-material"] == "opaque"
    controller.close()


def test_invalid_material_result_is_nonfatal_and_forces_opaque() -> None:
    window = _window()
    native = _FakeNative(_system())
    native.apply_result = "unexpected"
    controller = configure_window_appearance(window, native=native)

    window.events.before_load.emit()
    window.events.loaded.emit()

    assert window.dom.attributes.updated.wait(1.0)
    assert any(
        isinstance(call, tuple) and call[0] == "force_opaque"
        for call in native.calls
    )
    assert window.dom.attributes.updates[-1]["data-window-material"] == "opaque"
    controller.close()


def test_off_ui_before_load_leaves_initial_opaque_window_untouched() -> None:
    window = _window()
    window.native.InvokeRequired = True
    native = _FakeNative(_system())
    controller = configure_window_appearance(window, native=native)

    window.events.before_load.emit()

    assert native.calls == []
    assert native.preference_handlers == []
    controller.close()


def test_opaque_window_background_is_validated_and_fault_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = _FakeNative(_system())
    assert opaque_window_background(native=native) == "#F3F3F3"
    native.opaque_background = lambda _system: "not-a-color"

    monkeypatch.setattr(appearance, "_system_color", lambda _index: "#010203")
    assert opaque_window_background(native=native) == "#010203"


def test_opaque_background_uses_windows_system_color_in_every_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = appearance._WindowsAppearanceNative()
    indices: list[int] = []

    def system_color(index: int) -> str:
        indices.append(index)
        return "#010203"

    monkeypatch.setattr(appearance, "_system_color", system_color)

    assert native.opaque_background(_system()) == "#010203"
    assert native.opaque_background(_system(dark=True)) == "#010203"
    assert native.opaque_background(_system(high_contrast=True)) == "#010203"
    assert indices == [appearance._COLOR_WINDOW] * 3


def test_native_snapshot_reads_each_windows_appearance_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(appearance, "_read_dark_theme", lambda: True)
    monkeypatch.setattr(appearance, "_read_high_contrast", lambda: False)
    monkeypatch.setattr(appearance, "_read_accent", lambda: "#445566")
    monkeypatch.setattr(appearance, "_windows_build", lambda: 26100)

    assert appearance._WindowsAppearanceNative().read() == SystemAppearance(
        dark=True,
        high_contrast=False,
        accent="#445566",
        build=26100,
    )


def test_native_controller_background_uses_initialized_webview2_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transparent = object()

    class Color:
        Transparent = transparent

        @staticmethod
        def FromArgb(alpha: int, red: int, green: int, blue: int):
            return alpha, red, green, blue

    monkeypatch.setitem(
        sys.modules,
        "System.Drawing",
        SimpleNamespace(Color=Color),
    )
    control = SimpleNamespace(DefaultBackgroundColor=None)
    native_window = SimpleNamespace(
        BackColor=None,
        browser=SimpleNamespace(webview=control),
    )
    native = appearance._WindowsAppearanceNative()
    monkeypatch.setattr(
        native,
        "opaque_background",
        lambda _system: "#010203",
    )

    assert native._set_controller_background(
        native_window,
        _system(),
        transparent=True,
    )
    assert control.DefaultBackgroundColor is transparent
    assert native._set_controller_background(
        native_window,
        _system(dark=True),
        transparent=False,
    )
    assert control.DefaultBackgroundColor == (255, 1, 2, 3)
    assert native_window.BackColor == (255, 1, 2, 3)


@pytest.mark.parametrize(
    ("form_succeeds", "controller_succeeds", "expected"),
    (
        (True, False, True),
        (False, True, True),
        (False, False, False),
    ),
)
def test_native_opaque_background_confirms_either_occluding_path(
    monkeypatch: pytest.MonkeyPatch,
    form_succeeds: bool,
    controller_succeeds: bool,
    expected: bool,
) -> None:
    class Color:
        @staticmethod
        def FromArgb(alpha: int, red: int, green: int, blue: int):
            return alpha, red, green, blue

    class WebView:
        @property
        def DefaultBackgroundColor(self) -> object | None:
            return None

        @DefaultBackgroundColor.setter
        def DefaultBackgroundColor(self, value: object) -> None:
            del value
            if not controller_succeeds:
                raise RuntimeError("injected controller refusal")

    class NativeWindow:
        browser = SimpleNamespace(webview=WebView())

        @property
        def BackColor(self) -> object | None:
            return None

        @BackColor.setter
        def BackColor(self, value: object) -> None:
            del value
            if not form_succeeds:
                raise RuntimeError("injected form refusal")

    monkeypatch.setitem(sys.modules, "System.Drawing", SimpleNamespace(Color=Color))
    native = appearance._WindowsAppearanceNative()
    monkeypatch.setattr(
        native,
        "opaque_background",
        lambda _system: "#010203",
    )

    assert native._set_controller_background(
        NativeWindow(),
        _system(),
        transparent=False,
    ) is expected


def test_native_client_glass_uses_documented_reversible_full_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    black = object()

    class Color:
        Black = black

    calls: list[tuple[int, tuple[int, int, int, int]]] = []

    def extend(handle: int, margins_pointer: object) -> int:
        margins = ctypes.cast(
            margins_pointer,
            ctypes.POINTER(appearance._MARGINS),
        ).contents
        calls.append(
            (
                int(handle),
                (
                    margins.cxLeftWidth,
                    margins.cxRightWidth,
                    margins.cyTopHeight,
                    margins.cyBottomHeight,
                ),
            )
        )
        return 0

    monkeypatch.setitem(sys.modules, "System.Drawing", SimpleNamespace(Color=Color))
    monkeypatch.setattr(
        appearance.ctypes,
        "windll",
        SimpleNamespace(
            dwmapi=SimpleNamespace(DwmExtendFrameIntoClientArea=extend)
        ),
        raising=False,
    )
    native_window = SimpleNamespace(
        Handle=SimpleNamespace(ToInt64=lambda: 0x1234),
        BackColor=None,
    )
    native = appearance._WindowsAppearanceNative()

    assert native._set_client_glass(native_window, enabled=True)
    assert native_window.BackColor is black
    assert native._set_client_glass(native_window, enabled=False)
    assert calls == [
        (0x1234, (-1, -1, -1, -1)),
        (0x1234, (0, 0, 0, 0)),
    ]
    assert extend.argtypes == (
        appearance.wintypes.HWND,
        ctypes.POINTER(appearance._MARGINS),
    )
    assert extend.restype is ctypes.c_long


def test_native_client_glass_rejects_failing_hresult_before_black_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    black = object()

    class Color:
        Black = black

    def extend(_handle: int, _margins_pointer: object) -> int:
        return -1

    monkeypatch.setitem(sys.modules, "System.Drawing", SimpleNamespace(Color=Color))
    monkeypatch.setattr(
        appearance.ctypes,
        "windll",
        SimpleNamespace(
            dwmapi=SimpleNamespace(DwmExtendFrameIntoClientArea=extend)
        ),
        raising=False,
    )
    native_window = SimpleNamespace(Handle=42, BackColor=None)

    assert not appearance._WindowsAppearanceNative()._set_client_glass(
        native_window,
        enabled=True,
    )
    assert native_window.BackColor is None


def test_system_snapshot_rejects_non_inert_accent_values() -> None:
    with pytest.raises(ValueError, match="uppercase"):
        _system(accent="#aabbcc")
    with pytest.raises(ValueError, match="uppercase"):
        _system(accent="red; background: url(https://example.invalid)")


def test_documented_accent_read_and_no_application_javascript_channel() -> None:
    source = inspect.getsource(appearance)

    assert "DwmGetColorizationColor" in source
    assert "DwmSetWindowAttribute" in source
    assert "SetSysColors" not in source
    assert "winreg.SetValue" not in source
    assert "evaluate_js" not in source
    assert "run_js" not in source
    assert appearance._argb_color(0xCC12ABEF) == "#12ABEF"
