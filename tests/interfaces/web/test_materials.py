"""SH-G-12 ordinary and fault-injection evidence for native materials."""

from __future__ import annotations

import ctypes
import inspect
import json
import sys
from threading import Event, Thread, get_ident
from types import SimpleNamespace

import pytest

import namisync.interfaces.web.appearance as appearance
from namisync.interfaces.ui_state import (
    AppearanceValue,
    CosmeticSectionSnapshot,
    CosmeticSubscription,
    ThemeMode,
)
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

    def emit(self, *args: object) -> None:
        for handler in tuple(self.handlers):
            handler(*args)


class _RefusingHook(_Hook):
    def __iadd__(self, handler):
        del handler
        raise RuntimeError("injected event refusal")


class _RefusingRemovalHook(_Hook):
    def __isub__(self, handler):
        del handler
        raise RuntimeError("injected event removal refusal")


class _Core:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []
        self.updated = Event()

    def PostWebMessageAsJson(self, value: str) -> None:
        payload = json.loads(value)
        assert type(payload) is dict
        self.messages.append(payload)
        self.updated.set()


class _FakeNative:
    def __init__(self, system: SystemAppearance) -> None:
        self.system = system
        self.calls: list[object] = []
        self.preference_handlers: list[object] = []
        self.apply_result = "mica"
        self.apply_error: Exception | None = None
        self.read_error: Exception | None = None
        self.subscribe_error: Exception | None = None
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

    def defer(self, native_window: object, callback) -> None:
        self.calls.append(("defer", native_window))
        callback()

    def subscribe(self, callback):
        self.calls.append("subscribe")
        if self.subscribe_error is not None:
            raise self.subscribe_error
        self.preference_handlers.append(callback)

        def unsubscribe() -> None:
            self.calls.append("unsubscribe")
            self.preference_handlers.remove(callback)

        return unsubscribe

    def emit_preference_change(self) -> None:
        for handler in tuple(self.preference_handlers):
            handler()


class _FakeCosmetics:
    def __init__(
        self,
        snapshot: CosmeticSectionSnapshot,
        *,
        before_return: CosmeticSectionSnapshot | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.before_return = before_return
        self.callbacks: list[object] = []
        self.close_count = 0

    def subscribe(self, section: str, callback) -> CosmeticSubscription:
        assert section == "appearance"
        self.callbacks.append(callback)
        if self.before_return is not None:
            callback(self.before_return)

        def close() -> None:
            self.close_count += 1
            if callback in self.callbacks:
                self.callbacks.remove(callback)

        return CosmeticSubscription(self.snapshot, close)

    def emit(self, snapshot: CosmeticSectionSnapshot) -> None:
        for callback in tuple(self.callbacks):
            callback(snapshot)


def _system(
    *,
    dark: bool = False,
    high_contrast: bool = False,
    build: int = 22621,
    accent: str = "#123ABC",
) -> SystemAppearance:
    return SystemAppearance(dark, high_contrast, accent, build)


def _cosmetic(
    revision: int,
    theme: ThemeMode,
) -> CosmeticSectionSnapshot:
    return CosmeticSectionSnapshot(
        section="appearance",
        value_version=1,
        revision=revision,
        dirty=False,
        value=AppearanceValue(theme),
    )


def _window() -> SimpleNamespace:
    core = _Core()
    return SimpleNamespace(
        native=SimpleNamespace(
            InvokeRequired=False,
            browser=SimpleNamespace(
                webview=SimpleNamespace(CoreWebView2=core),
            ),
        ),
        events=SimpleNamespace(before_load=_Hook(), loaded=_Hook()),
        appearance_messages=core,
    )


def _request_initial(controller: object) -> list[Exception | None]:
    results: list[Exception | None] = []
    controller.request_initial_surface_settlement(results.append)
    return results


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
    ) -> appearance._BackgroundLanding:
        calls.append(("controller", transparent))
        return (
            appearance._BackgroundLanding(False, transparent_succeeds)
            if transparent
            else appearance._BackgroundLanding(True, True)
        )

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
    assert native_window.BackColor == (255, 31, 31, 31)
    assert control.DefaultBackgroundColor == (255, 31, 31, 31)

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
    assert native_window.BackColor == (255, 31, 31, 31)
    assert control.DefaultBackgroundColor == (255, 31, 31, 31)


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


def test_form_only_opaque_landing_requires_a_confirmed_glass_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = appearance._WindowsAppearanceNative()
    monkeypatch.setattr(native, "_set_dwm_attribute", lambda *_args: True)
    monkeypatch.setattr(native, "_set_client_glass", lambda *_args, **_kw: False)
    monkeypatch.setattr(
        native,
        "_set_controller_background",
        lambda *_args, **_kw: appearance._BackgroundLanding(True, False),
    )

    assert native.force_opaque(object(), _system()) is False


def test_controller_opaque_landing_does_not_depend_on_glass_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = appearance._WindowsAppearanceNative()
    monkeypatch.setattr(native, "_set_dwm_attribute", lambda *_args: True)
    monkeypatch.setattr(native, "_set_client_glass", lambda *_args, **_kw: False)
    monkeypatch.setattr(
        native,
        "_set_controller_background",
        lambda *_args, **_kw: appearance._BackgroundLanding(False, True),
    )

    assert native.force_opaque(object(), _system()) is True


def test_opaque_fallback_refuses_untyped_background_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = appearance._WindowsAppearanceNative()
    monkeypatch.setattr(native, "_set_dwm_attribute", lambda *_args: True)
    monkeypatch.setattr(native, "_set_client_glass", lambda *_args, **_kw: True)
    monkeypatch.setattr(
        native,
        "_set_controller_background",
        lambda *_args, **_kw: True,
    )

    with pytest.raises(TypeError, match="_BackgroundLanding"):
        native.force_opaque(object(), _system())


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
    ) -> appearance._BackgroundLanding:
        calls.append(("controller", transparent))
        return appearance._BackgroundLanding(True, True)

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


def test_apply_reports_unsafe_surface_when_reset_cannot_be_confirmed(
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

    with pytest.raises(appearance.UnsafeSurfaceError, match="opaque rollback"):
        native.apply(object(), _system())
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


def test_apply_reports_unsafe_surface_when_rollback_itself_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = appearance._WindowsAppearanceNative()
    _patch_native_calls(monkeypatch, native, transparent_succeeds=False)

    def fail_rollback(_window: object, _system: SystemAppearance) -> bool:
        raise RuntimeError("injected rollback failure")

    monkeypatch.setattr(native, "force_opaque", fail_rollback)

    with pytest.raises(appearance.UnsafeSurfaceError, match="complete") as raised:
        native.apply(object(), _system())

    assert isinstance(raised.value.__cause__, RuntimeError)


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


def test_initial_subscription_failure_degrades_over_safe_opaque_baseline() -> None:
    window = _window()
    native = _FakeNative(_system())
    native.subscribe_error = RuntimeError("injected observation refusal")
    controller = configure_window_appearance(window, native=native)
    results = _request_initial(controller)

    window.events.before_load.emit()

    assert results == [None]
    assert controller.surface_safety_failure is None
    assert native.preference_handlers == []
    controller.close()


def test_initial_read_failure_rolls_back_observation_and_settles_safe() -> None:
    window = _window()
    native = _FakeNative(_system())
    native.read_error = RuntimeError("injected initial read refusal")
    controller = configure_window_appearance(window, native=native)
    results = _request_initial(controller)

    window.events.before_load.emit()

    assert native.calls[:3] == ["subscribe", "read", "unsubscribe"]
    assert native.preference_handlers == []
    assert results == [None]
    assert controller.surface_safety_failure is None
    controller.close()


def test_subscription_gap_change_is_included_in_the_initial_snapshot() -> None:
    window = _window()

    class GapNative(_FakeNative):
        def subscribe(self, callback):
            unsubscribe = super().subscribe(callback)
            self.system = _system(dark=True, accent="#ABCDEF")
            callback()
            return unsubscribe

    native = GapNative(_system(accent="#111111"))
    controller = configure_window_appearance(window, native=native)

    window.events.before_load.emit()

    applied = [
        call[2]
        for call in native.calls
        if isinstance(call, tuple) and call[0] == "apply"
    ]
    assert native.calls.index("subscribe") < native.calls.index("read")
    assert native.calls.count("read") == 1
    assert applied == [_system(dark=True, accent="#ABCDEF")]
    controller.close()


def test_cosmetic_subscription_snapshot_cannot_regress_a_racing_callback() -> None:
    window = _window()
    native = _FakeNative(_system(dark=False, accent="#112233"))
    initial = _cosmetic(0, ThemeMode.SYSTEM)
    cosmetics = _FakeCosmetics(
        initial,
        before_return=_cosmetic(2, ThemeMode.DARK),
    )

    controller = configure_window_appearance(
        window,
        native=native,
        cosmetics=cosmetics,
        initial_cosmetic=initial,
    )
    window.events.before_load.emit()
    window.events.loaded.emit()

    applied = [
        call[2]
        for call in native.calls
        if isinstance(call, tuple) and call[0] == "apply"
    ]
    assert applied == [_system(dark=True, accent="#112233")]
    assert window.appearance_messages.messages[-1]["theme"] == "dark"
    controller.close()


def test_reversed_cosmetic_callbacks_cannot_regress_effective_appearance() -> None:
    window = _window()
    native = _FakeNative(_system(dark=False, accent="#112233"))
    initial = _cosmetic(0, ThemeMode.SYSTEM)
    cosmetics = _FakeCosmetics(initial)
    controller = configure_window_appearance(
        window,
        native=native,
        cosmetics=cosmetics,
        initial_cosmetic=initial,
    )
    window.events.before_load.emit()
    queued: list[object] = []
    native.invoke = lambda _window, callback: queued.append(callback)

    cosmetics.emit(_cosmetic(2, ThemeMode.DARK))
    cosmetics.emit(_cosmetic(1, ThemeMode.LIGHT))

    assert len(queued) == 1
    queued[0]()
    applied = [
        call[2]
        for call in native.calls
        if isinstance(call, tuple) and call[0] == "apply"
    ]
    assert applied[-1] == _system(dark=True, accent="#112233")
    controller.close()


def test_cosmetic_change_during_native_read_skips_the_superseded_mode() -> None:
    window = _window()
    native = _FakeNative(_system(dark=False, accent="#112233"))
    initial = _cosmetic(0, ThemeMode.SYSTEM)
    cosmetics = _FakeCosmetics(initial)
    controller = configure_window_appearance(
        window,
        native=native,
        cosmetics=cosmetics,
        initial_cosmetic=initial,
    )
    window.events.before_load.emit()
    initial_apply_count = sum(
        isinstance(call, tuple) and call[0] == "apply" for call in native.calls
    )
    deferred: list[object] = []
    native.defer = lambda _window, callback: deferred.append(callback)
    original_read = native.read
    emitted = False

    def read() -> SystemAppearance:
        nonlocal emitted
        raw = original_read()
        if not emitted:
            emitted = True
            cosmetics.emit(_cosmetic(2, ThemeMode.DARK))
        return raw

    native.read = read

    cosmetics.emit(_cosmetic(1, ThemeMode.LIGHT))

    assert len(deferred) == 1
    assert sum(
        isinstance(call, tuple) and call[0] == "apply" for call in native.calls
    ) == initial_apply_count
    deferred[0]()
    applied = [
        call[2]
        for call in native.calls
        if isinstance(call, tuple) and call[0] == "apply"
    ]
    assert applied[-1] == _system(dark=True, accent="#112233")
    controller.close()


def test_cosmetic_change_during_native_apply_publishes_only_the_newest_mode() -> None:
    window = _window()
    native = _FakeNative(_system(dark=False, accent="#112233"))
    initial = _cosmetic(0, ThemeMode.SYSTEM)
    cosmetics = _FakeCosmetics(initial)
    controller = configure_window_appearance(
        window,
        native=native,
        cosmetics=cosmetics,
        initial_cosmetic=initial,
    )
    window.events.before_load.emit()
    window.events.loaded.emit()
    deferred: list[object] = []
    native.defer = lambda _window, callback: deferred.append(callback)
    original_apply = native.apply
    emitted = False

    def apply(native_window: object, system: SystemAppearance):
        nonlocal emitted
        result = original_apply(native_window, system)
        if not emitted:
            emitted = True
            cosmetics.emit(_cosmetic(2, ThemeMode.DARK))
        return result

    native.apply = apply

    cosmetics.emit(_cosmetic(1, ThemeMode.LIGHT))

    assert len(deferred) == 1
    assert [
        message["theme"] for message in window.appearance_messages.messages
    ] == ["light"]
    deferred[0]()
    applied = [
        call[2]
        for call in native.calls
        if isinstance(call, tuple) and call[0] == "apply"
    ]
    assert applied[-2:] == [
        _system(dark=False, accent="#112233"),
        _system(dark=True, accent="#112233"),
    ]
    assert [
        message["theme"] for message in window.appearance_messages.messages
    ] == ["light", "dark"]
    controller.close()


def test_cosmetic_callback_after_close_is_inert_and_closes_each_owner_once() -> None:
    window = _window()
    native = _FakeNative(_system())
    initial = _cosmetic(0, ThemeMode.SYSTEM)
    cosmetics = _FakeCosmetics(initial)
    controller = configure_window_appearance(
        window,
        native=native,
        cosmetics=cosmetics,
        initial_cosmetic=initial,
    )
    captured_callback = cosmetics.callbacks[0]
    window.events.before_load.emit()
    apply_count = sum(
        isinstance(call, tuple) and call[0] == "apply" for call in native.calls
    )

    controller.close()
    controller.close()
    captured_callback(_cosmetic(1, ThemeMode.DARK))

    assert cosmetics.close_count == 1
    assert native.calls.count("unsubscribe") == 1
    assert sum(
        isinstance(call, tuple) and call[0] == "apply" for call in native.calls
    ) == apply_count


def test_cosmetic_subscription_rolls_back_once_when_event_attachment_fails() -> None:
    window = _window()
    window.events.loaded = _RefusingHook()
    initial = _cosmetic(0, ThemeMode.LIGHT)
    cosmetics = _FakeCosmetics(initial)

    with pytest.raises(RuntimeError, match="event refusal"):
        configure_window_appearance(
            window,
            native=_FakeNative(_system(dark=True)),
            cosmetics=cosmetics,
            initial_cosmetic=initial,
        )

    assert cosmetics.close_count == 1
    assert cosmetics.callbacks == []
    assert window.events.before_load.handlers == []


def test_cosmetic_attachment_rollback_survives_event_removal_failure() -> None:
    window = _window()
    window.events.before_load = _RefusingRemovalHook()
    window.events.loaded = _RefusingHook()
    initial = _cosmetic(0, ThemeMode.LIGHT)
    cosmetics = _FakeCosmetics(initial)
    native = _FakeNative(_system(dark=True))

    with pytest.raises(RuntimeError, match="event refusal"):
        configure_window_appearance(
            window,
            native=native,
            cosmetics=cosmetics,
            initial_cosmetic=initial,
        )

    assert cosmetics.close_count == 1
    assert cosmetics.callbacks == []
    assert len(window.events.before_load.handlers) == 1
    window.events.before_load.emit()
    assert "read" not in native.calls


def test_deferred_initial_generation_finishes_before_loaded_publication() -> None:
    window = _window()
    native = _FakeNative(_system(accent="#111111"))
    deferred: list[object] = []
    native.defer = lambda _window, callback: deferred.append(callback)
    original_read = native.read
    reads = 0

    def read() -> SystemAppearance:
        nonlocal reads
        snapshot = original_read()
        reads += 1
        if reads == 1:
            native.system = _system(dark=True, accent="#222222")
            native.emit_preference_change()
        return snapshot

    native.read = read
    controller = configure_window_appearance(window, native=native)
    results = _request_initial(controller)

    window.events.before_load.emit()
    assert len(deferred) == 1
    assert window.appearance_messages.messages == []
    deferred[0]()
    assert window.appearance_messages.messages == []
    window.events.loaded.emit()

    assert controller.surface_safety_failure is None
    assert results == [None]
    assert [message["accent"] for message in window.appearance_messages.messages] == [
        "#222222"
    ]
    controller.close()


def test_loaded_before_deferred_initial_generation_waits_for_final_state() -> None:
    window = _window()
    native = _FakeNative(_system(accent="#111111"))
    deferred: list[object] = []
    native.defer = lambda _window, callback: deferred.append(callback)
    original_read = native.read
    reads = 0

    def read() -> SystemAppearance:
        nonlocal reads
        snapshot = original_read()
        reads += 1
        if reads == 1:
            native.system = _system(dark=True, accent="#222222")
            native.emit_preference_change()
        return snapshot

    native.read = read
    controller = configure_window_appearance(window, native=native)

    window.events.before_load.emit()
    window.events.loaded.emit()
    results = _request_initial(controller)
    assert window.appearance_messages.messages == []
    deferred[0]()

    assert controller.surface_safety_failure is None
    assert results == [None]
    assert [message["accent"] for message in window.appearance_messages.messages] == [
        "#222222"
    ]
    controller.close()


def test_failed_deferred_refresh_settles_from_last_confirmed_safe_surface() -> None:
    window = _window()
    native = _FakeNative(_system(accent="#111111"))
    original_read = native.read
    emitted = False

    def read() -> SystemAppearance:
        nonlocal emitted
        snapshot = original_read()
        if not emitted:
            emitted = True
            native.system = _system(dark=True, accent="#222222")
            native.emit_preference_change()
        return snapshot

    native.read = read
    def refuse_defer(_window: object, _callback: object) -> None:
        raise RuntimeError("injected deferred dispatch refusal")

    native.defer = refuse_defer
    controller = configure_window_appearance(window, native=native)
    results = _request_initial(controller)

    window.events.before_load.emit()

    assert results == [None]
    assert controller.surface_safety_failure is None
    controller.close()


def test_deferred_initial_refresh_latches_unconfirmed_surface_failure() -> None:
    window = _window()
    native = _FakeNative(_system(accent="#111111"))
    deferred: list[object] = []
    native.defer = lambda _window, callback: deferred.append(callback)
    original_read = native.read
    emitted = False

    def read() -> SystemAppearance:
        nonlocal emitted
        snapshot = original_read()
        if not emitted:
            emitted = True
            native.system = _system(dark=True, accent="#222222")
            native.emit_preference_change()
        return snapshot

    native.read = read
    controller = configure_window_appearance(window, native=native)
    results = _request_initial(controller)
    window.events.before_load.emit()
    assert len(deferred) == 1
    assert results == []
    unsafe = appearance.UnsafeSurfaceError("injected deferred rollback refusal")
    native.apply_error = unsafe

    deferred[0]()

    assert results == [unsafe]
    assert controller.surface_safety_failure is unsafe
    controller.close()


def test_reload_before_surface_settlement_completes_all_generation_waiters() -> None:
    window = _window()
    native = _FakeNative(_system(accent="#111111"))
    deferred: list[object] = []
    native.defer = lambda _window, callback: deferred.append(callback)
    original_read = native.read
    reads = 0

    def read() -> SystemAppearance:
        nonlocal reads
        snapshot = original_read()
        reads += 1
        if reads == 1:
            native.system = _system(dark=True, accent="#222222")
            native.emit_preference_change()
        return snapshot

    native.read = read
    controller = configure_window_appearance(window, native=native)
    first = _request_initial(controller)
    window.events.before_load.emit()
    assert len(deferred) == 1

    window.events.before_load.emit()
    second = _request_initial(controller)
    assert first == []
    assert second == []
    deferred[0]()

    assert first == [None]
    assert second == [None]
    controller.close()


def test_reload_automatically_publishes_to_the_new_receiver() -> None:
    window = _window()
    native = _FakeNative(_system(accent="#123456"))
    controller = configure_window_appearance(window, native=native)

    window.events.before_load.emit()
    first = _request_initial(controller)
    window.events.loaded.emit()
    assert first == [None]
    assert len(window.appearance_messages.messages) == 1

    window.events.before_load.emit()
    window.events.loaded.emit()

    assert [
        (message["revision"], message["accent"])
        for message in window.appearance_messages.messages
    ] == [(1, "#123456"), (2, "#123456")]
    controller.close()


def test_reload_invalidates_a_queued_prior_generation_publication() -> None:
    window = _window()
    native = _FakeNative(_system(accent="#123456"))
    queued: list[object] = []
    queue_posts = False
    immediate_invoke = native.invoke

    def invoke(native_window: object, callback: object) -> None:
        if queue_posts:
            queued.append(callback)
        else:
            immediate_invoke(native_window, callback)

    native.invoke = invoke
    controller = configure_window_appearance(window, native=native)
    window.events.before_load.emit()
    _request_initial(controller)
    window.events.loaded.emit()
    assert len(window.appearance_messages.messages) == 1
    queue_posts = True

    window.events.before_load.emit()
    window.events.loaded.emit()
    assert len(queued) == 1
    window.events.before_load.emit()
    window.events.loaded.emit()
    assert len(queued) == 2

    queued[0]()
    queued[1]()

    assert len(window.appearance_messages.messages) == 2
    controller.close()


def test_initial_surface_settlement_is_a_stable_controller_fact() -> None:
    window = _window()
    native = _FakeNative(_system())
    controller = configure_window_appearance(window, native=native)
    window.events.before_load.emit()
    window.events.loaded.emit()
    first = _request_initial(controller)
    second = _request_initial(controller)

    assert first == [None]
    assert second == [None]
    assert len(window.appearance_messages.messages) == 1
    controller.close()


def test_sh_g_12_loaded_document_gets_only_validated_inert_appearance_values() -> None:
    window = _window()
    native = _FakeNative(_system(dark=True, accent="#A1B2C3"))
    controller = configure_window_appearance(window, native=native)
    _request_initial(controller)

    window.events.before_load.emit()
    assert window.appearance_messages.messages == []
    window.events.loaded.emit()

    assert window.appearance_messages.messages == [
        {
            "kind": "namisync.appearance.v1",
            "revision": 1,
            "theme": "dark",
            "highContrast": False,
            "material": "mica",
            "accent": "#A1B2C3",
            "accentHover": "#0091F8",
            "accentPressed": "#0067C0",
            "accentForeground": "#000000",
            "accentHoverForeground": "#000000",
            "accentPressedForeground": "#FFFFFF",
        }
    ]
    controller.close()


def test_document_publication_uses_the_native_ui_dispatcher_without_dom_eval() -> None:
    window = _window()
    native = _FakeNative(_system(dark=True, accent="#A1B2C3"))
    controller = configure_window_appearance(window, native=native)
    _request_initial(controller)

    window.events.before_load.emit()
    window.events.loaded.emit()

    assert ("invoke", window.native) in native.calls
    assert window.appearance_messages.messages[-1]["accent"] == "#A1B2C3"
    assert not hasattr(controller, "_publish_thread")
    controller.close()


def test_document_post_failure_degrades_without_changing_surface_settlement() -> None:
    window = _window()
    native = _FakeNative(_system())
    attempts = 0

    def refuse_post(_value: str) -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("injected document post refusal")

    window.native.browser.webview.CoreWebView2.PostWebMessageAsJson = refuse_post
    controller = configure_window_appearance(window, native=native)
    results = _request_initial(controller)

    window.events.before_load.emit()
    window.events.loaded.emit()
    native.emit_preference_change()

    assert attempts == 2
    assert results == [None]
    assert controller.surface_safety_failure is None
    assert window.appearance_messages.messages == []
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
    _request_initial(controller)
    window.events.before_load.emit()
    window.events.loaded.emit()
    native.system = _system(dark=True, accent="#ABCDEF")

    native.emit_preference_change()

    assert [value["revision"] for value in window.appearance_messages.messages] == [
        1,
        2,
    ]
    assert window.appearance_messages.messages[-1]["theme"] == "dark"
    assert window.appearance_messages.messages[-1]["accent"] == "#ABCDEF"
    controller.close()


def test_preference_notifications_coalesce_before_the_ui_snapshot() -> None:
    window = _window()
    native = _FakeNative(_system(accent="#111111"))
    controller = configure_window_appearance(window, native=native)
    _request_initial(controller)
    window.events.before_load.emit()
    queued: list[object] = []
    native.invoke = lambda _window, callback: queued.append(callback)

    native.system = _system(dark=True, accent="#222222")
    native.emit_preference_change()
    native.system = _system(dark=False, accent="#333333")
    native.emit_preference_change()

    assert len(queued) == 1
    queued[0]()
    applied = [
        call[2]
        for call in native.calls
        if isinstance(call, tuple) and call[0] == "apply"
    ]
    assert applied[-1] == _system(dark=False, accent="#333333")
    assert _system(dark=True, accent="#222222") not in applied
    assert native.calls.count("read") == 2
    controller.close()


def test_notification_during_ui_read_requeues_on_the_ui_owner() -> None:
    window = _window()
    native = _FakeNative(_system(accent="#111111"))
    controller = configure_window_appearance(window, native=native)
    window.events.before_load.emit()
    ui_thread = get_ident()
    queued: list[object] = []
    callback_queued = Event()

    def queue_invoke(_window: object, callback: object) -> None:
        assert get_ident() != ui_thread
        queued.append(callback)
        callback_queued.set()

    native.invoke = queue_invoke
    original_read = native.read
    original_apply = native.apply
    first_live_read_entered = Event()
    second_notification_done = Event()
    live_reads = 0
    read_threads: list[int] = []
    apply_threads: list[int] = []

    def read() -> SystemAppearance:
        nonlocal live_reads
        snapshot = original_read()
        read_threads.append(get_ident())
        live_reads += 1
        if live_reads == 1:
            first_live_read_entered.set()
            assert second_notification_done.wait(1.0)
        return snapshot

    def apply(native_window: object, system: SystemAppearance):
        apply_threads.append(get_ident())
        return original_apply(native_window, system)

    native.read = read
    native.apply = apply
    native.system = _system(dark=True, accent="#222222")
    first_notification = Thread(target=native.emit_preference_change)
    first_notification.start()
    assert callback_queued.wait(1.0)
    first_notification.join(1.0)
    assert not first_notification.is_alive()

    def send_second_notification() -> None:
        assert first_live_read_entered.wait(1.0)
        native.system = _system(dark=False, accent="#333333")
        native.emit_preference_change()
        second_notification_done.set()

    second_notification = Thread(target=send_second_notification)
    second_notification.start()
    assert len(queued) == 1
    queued[0]()
    second_notification.join(1.0)

    assert not second_notification.is_alive()
    applied = [
        call[2]
        for call in native.calls
        if isinstance(call, tuple) and call[0] == "apply"
    ]
    assert applied[-2:] == [
        _system(dark=True, accent="#222222"),
        _system(dark=False, accent="#333333"),
    ]
    assert live_reads == 2
    assert read_threads == [ui_thread, ui_thread]
    assert apply_threads == [ui_thread, ui_thread]
    controller.close()


def test_preference_change_during_apply_defers_latest_state_to_next_ui_turn() -> None:
    window = _window()
    native = _FakeNative(_system(accent="#111111"))
    controller = configure_window_appearance(window, native=native)
    _request_initial(controller)
    window.events.before_load.emit()
    window.events.loaded.emit()
    deferred: list[object] = []
    native.defer = lambda _window, callback: deferred.append(callback)
    original_apply = native.apply
    emitted = False

    def apply(native_window: object, system: SystemAppearance):
        nonlocal emitted
        result = original_apply(native_window, system)
        if system.accent == "#222222" and not emitted:
            emitted = True
            native.system = _system(dark=False, accent="#333333")
            native.emit_preference_change()
            native.system = _system(dark=True, accent="#444444")
            native.emit_preference_change()
        return result

    native.apply = apply
    native.system = _system(dark=True, accent="#222222")

    native.emit_preference_change()

    assert len(deferred) == 1
    applied = [
        call[2]
        for call in native.calls
        if isinstance(call, tuple) and call[0] == "apply"
    ]
    assert applied[-1] == _system(dark=True, accent="#222222")
    assert [message["accent"] for message in window.appearance_messages.messages] == [
        "#111111"
    ]

    deferred[0]()

    applied = [
        call[2]
        for call in native.calls
        if isinstance(call, tuple) and call[0] == "apply"
    ]
    assert applied[-2:] == [
        _system(dark=True, accent="#222222"),
        _system(dark=True, accent="#444444"),
    ]
    assert _system(dark=False, accent="#333333") not in applied
    assert native.calls.count("read") == 3
    assert [message["accent"] for message in window.appearance_messages.messages] == [
        "#111111",
        "#444444",
    ]
    controller.close()


def test_defer_failure_retries_the_already_known_pending_generation() -> None:
    window = _window()
    native = _FakeNative(_system(accent="#111111"))
    controller = configure_window_appearance(window, native=native)
    window.events.before_load.emit()
    original_apply = native.apply
    emitted = False
    defer_attempts = 0

    def apply(native_window: object, system: SystemAppearance):
        nonlocal emitted
        result = original_apply(native_window, system)
        if system.accent == "#222222" and not emitted:
            emitted = True
            native.system = _system(dark=False, accent="#333333")
            native.emit_preference_change()
        return result

    def defer(_native_window: object, callback) -> None:
        nonlocal defer_attempts
        defer_attempts += 1
        if defer_attempts == 1:
            raise RuntimeError("injected deferred dispatch refusal")
        callback()

    native.apply = apply
    native.defer = defer
    native.system = _system(dark=True, accent="#222222")

    native.emit_preference_change()

    applied = [
        call[2]
        for call in native.calls
        if isinstance(call, tuple) and call[0] == "apply"
    ]
    assert defer_attempts == 2
    assert applied[-1] == _system(dark=False, accent="#333333")
    controller.close()


def test_ui_dispatch_failure_allows_the_next_notification_to_recover() -> None:
    window = _window()
    native = _FakeNative(_system(accent="#111111"))
    controller = configure_window_appearance(window, native=native)
    window.events.before_load.emit()
    attempts = 0
    first_dispatch_entered = Event()
    release_first_dispatch = Event()

    def invoke(_native_window: object, callback) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            first_dispatch_entered.set()
            assert release_first_dispatch.wait(1.0)
            raise RuntimeError("injected UI dispatch refusal")
        callback()

    native.invoke = invoke
    native.system = _system(dark=True, accent="#222222")
    first_notification = Thread(target=native.emit_preference_change)
    first_notification.start()
    assert first_dispatch_entered.wait(1.0)
    native.system = _system(dark=False, accent="#333333")
    native.emit_preference_change()
    release_first_dispatch.set()
    first_notification.join(1.0)

    applied = [
        call[2]
        for call in native.calls
        if isinstance(call, tuple) and call[0] == "apply"
    ]
    assert not first_notification.is_alive()
    assert attempts == 2
    assert applied[-1] == _system(dark=False, accent="#333333")
    assert _system(dark=True, accent="#222222") not in applied
    controller.close()


def test_queued_stale_publication_is_ignored_and_latest_revision_wins() -> None:
    window = _window()
    native = _FakeNative(_system(accent="#111111"))
    queued: list[object] = []

    def queue_invoke(native_window: object, callback: object) -> None:
        native.calls.append(("invoke", native_window))
        queued.append(callback)

    native.invoke = queue_invoke
    controller = configure_window_appearance(window, native=native)
    results = _request_initial(controller)
    window.events.before_load.emit()
    window.events.loaded.emit()
    native.system = _system(dark=True, accent="#222222")
    native.emit_preference_change()
    assert len(queued) == 2
    queued[1]()
    assert len(queued) == 2
    assert results == [None]
    queued[0]()
    assert len(queued) == 3
    assert results == [None]
    queued[2]()

    assert [value["revision"] for value in window.appearance_messages.messages] == [2]
    assert window.appearance_messages.messages[0]["accent"] == "#222222"
    assert results == [None]
    controller.close()


def test_surface_settlement_callback_runs_outside_the_controller_lock() -> None:
    window = _window()
    native = _FakeNative(_system())
    controller = configure_window_appearance(window, native=native)
    completed = Event()

    def settled(error: Exception | None) -> None:
        assert error is None
        assert controller.surface_safety_failure is None
        controller.close()
        completed.set()

    controller.request_initial_surface_settlement(settled)
    worker = Thread(target=window.events.before_load.emit, daemon=True)
    worker.start()
    worker.join(1.0)

    assert not worker.is_alive()
    assert completed.is_set()


def test_close_invalidates_queued_publication_without_waiting() -> None:
    window = _window()
    native = _FakeNative(_system())
    queued: list[object] = []
    native.invoke = lambda _window, callback: queued.append(callback)
    controller = configure_window_appearance(window, native=native)
    _request_initial(controller)
    window.events.before_load.emit()
    window.events.loaded.emit()
    assert len(queued) == 1
    controller.close()
    queued[0]()
    assert window.appearance_messages.messages == []


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
    _request_initial(controller)
    window.events.before_load.emit()
    window.events.loaded.emit()
    native.read_error = RuntimeError("injected preference read failure")

    native.emit_preference_change()

    assert any(
        isinstance(call, tuple) and call[0] == "force_opaque"
        for call in native.calls
    )
    assert window.appearance_messages.messages[-1]["material"] == "opaque"
    native.read_error = None
    native.system = _system(dark=False, accent="#ABCDEF")
    native.emit_preference_change()
    assert window.appearance_messages.messages[-1]["material"] == "mica"
    assert window.appearance_messages.messages[-1]["accent"] == "#ABCDEF"
    controller.close()


def test_unconfirmed_initial_fallback_refuses_a_readable_material_claim() -> None:
    window = _window()
    native = _FakeNative(_system())
    native.apply_error = appearance.UnsafeSurfaceError(
        "injected unconfirmed rollback"
    )
    controller = configure_window_appearance(window, native=native)
    results = _request_initial(controller)

    window.events.before_load.emit()
    window.events.loaded.emit()

    assert window.appearance_messages.messages == []
    assert len(results) == 1
    assert isinstance(results[0], appearance.UnsafeSurfaceError)
    assert controller.surface_safety_failure is results[0]
    controller.close()


def test_indeterminate_initial_material_failure_requires_confirmed_rollback() -> None:
    window = _window()
    native = _FakeNative(_system())
    native.apply_error = RuntimeError("injected appearance logic failure")
    native.force_opaque_result = False
    controller = configure_window_appearance(window, native=native)
    results = _request_initial(controller)

    window.events.before_load.emit()
    window.events.loaded.emit()

    assert len(results) == 1
    assert isinstance(results[0], appearance.UnsafeSurfaceError)
    assert controller.surface_safety_failure is results[0]
    assert window.appearance_messages.messages == []
    controller.close()


def test_unavailable_initial_enhancement_keeps_safe_opaque_baseline() -> None:
    window = _window()
    native = _FakeNative(_system())
    native.apply_result = None
    controller = configure_window_appearance(window, native=native)
    results = _request_initial(controller)

    window.events.before_load.emit()
    window.events.loaded.emit()

    assert results == [None]
    assert controller.surface_safety_failure is None
    assert window.appearance_messages.messages == []
    controller.close()


def test_unsafe_initial_surface_result_is_never_erased_by_later_success() -> None:
    window = _window()
    native = _FakeNative(_system())
    unsafe = appearance.UnsafeSurfaceError("injected unconfirmed rollback")
    native.apply_error = unsafe
    controller = configure_window_appearance(window, native=native)
    results = _request_initial(controller)

    window.events.before_load.emit()
    native.apply_error = None
    native.system = _system(dark=True, accent="#ABCDEF")
    native.emit_preference_change()
    repeated = _request_initial(controller)

    assert results == [unsafe]
    assert repeated == [unsafe]
    assert controller.surface_safety_failure is unsafe
    controller.close()


def test_unconfirmed_live_fallback_publishes_degraded_opaque_page_state() -> None:
    window = _window()
    native = _FakeNative(_system())
    controller = configure_window_appearance(window, native=native)
    _request_initial(controller)
    window.events.before_load.emit()
    window.events.loaded.emit()
    native.system = _system(dark=True, accent="#ABCDEF")
    native.apply_error = RuntimeError("injected live DWM failure")
    native.force_opaque_result = False

    native.emit_preference_change()

    assert window.appearance_messages.messages[-1] == {
        "kind": "namisync.appearance.v1",
        "revision": 2,
        "theme": "dark",
        "highContrast": False,
        "material": "degraded",
        "accent": "#ABCDEF",
        "accentHover": "#0091F8",
        "accentPressed": "#0067C0",
        "accentForeground": "#000000",
        "accentHoverForeground": "#000000",
        "accentPressedForeground": "#FFFFFF",
    }
    controller.close()


def test_material_failure_is_nonfatal_and_forces_opaque() -> None:
    window = _window()
    native = _FakeNative(_system())
    native.apply_error = RuntimeError("injected DWM failure")
    controller = configure_window_appearance(window, native=native)
    _request_initial(controller)

    window.events.before_load.emit()
    window.events.loaded.emit()

    assert any(
        isinstance(call, tuple) and call[0] == "force_opaque"
        for call in native.calls
    )
    assert window.appearance_messages.messages[-1]["material"] == "opaque"
    controller.close()


def test_invalid_material_result_is_nonfatal_and_forces_opaque() -> None:
    window = _window()
    native = _FakeNative(_system())
    native.apply_result = "unexpected"
    controller = configure_window_appearance(window, native=native)
    _request_initial(controller)

    window.events.before_load.emit()
    window.events.loaded.emit()

    assert any(
        isinstance(call, tuple) and call[0] == "force_opaque"
        for call in native.calls
    )
    assert window.appearance_messages.messages[-1]["material"] == "opaque"
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


@pytest.mark.parametrize(
    ("raw_dark", "high_contrast", "theme_mode", "expected_dark"),
    (
        (False, False, ThemeMode.SYSTEM, False),
        (True, False, ThemeMode.SYSTEM, True),
        (True, False, ThemeMode.LIGHT, False),
        (False, False, ThemeMode.DARK, True),
        (False, True, ThemeMode.DARK, False),
        (True, True, ThemeMode.LIGHT, True),
    ),
)
def test_effective_theme_matrix_preserves_raw_windows_authority(
    raw_dark: bool,
    high_contrast: bool,
    theme_mode: ThemeMode,
    expected_dark: bool,
) -> None:
    raw = SystemAppearance(
        dark=raw_dark,
        high_contrast=high_contrast,
        accent="#123456",
        build=26100,
        accent_hover="#345678",
        accent_pressed="#012345",
    )

    effective = appearance._effective_system_appearance(raw, theme_mode)

    assert raw.dark is raw_dark
    assert effective.dark is expected_dark
    assert effective.high_contrast is high_contrast
    assert effective.accent == raw.accent
    assert effective.accent_hover == raw.accent_hover
    assert effective.accent_pressed == raw.accent_pressed
    assert effective.build == raw.build


@pytest.mark.parametrize(
    ("raw", "theme_mode", "expected_dark"),
    (
        (_system(dark=True), ThemeMode.LIGHT, False),
        (_system(dark=False), ThemeMode.DARK, True),
        (_system(dark=True, high_contrast=True), ThemeMode.LIGHT, True),
    ),
)
def test_precreate_background_uses_the_effective_theme(
    raw: SystemAppearance,
    theme_mode: ThemeMode,
    expected_dark: bool,
) -> None:
    native = _FakeNative(raw)
    raw_dark = raw.dark

    assert (
        opaque_window_background(native=native, theme_mode=theme_mode)
        == "#F3F3F3"
    )

    background_call = next(
        call
        for call in native.calls
        if isinstance(call, tuple) and call[0] == "opaque_background"
    )
    effective = background_call[1]
    assert isinstance(effective, SystemAppearance)
    assert effective.dark is expected_dark
    assert raw.dark is raw_dark


def test_opaque_window_background_is_validated_and_fault_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = _FakeNative(_system())
    assert opaque_window_background(native=native) == "#F3F3F3"
    native.opaque_background = lambda _system: "not-a-color"

    monkeypatch.setattr(appearance, "_system_color", lambda _index: "#010203")
    assert opaque_window_background(native=native) == "#010203"


def test_opaque_background_uses_fluent_canvas_except_in_high_contrast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = appearance._WindowsAppearanceNative()
    indices: list[int] = []

    def system_color(index: int) -> str:
        indices.append(index)
        return "#010203"

    monkeypatch.setattr(appearance, "_system_color", system_color)

    assert native.opaque_background(_system()) == appearance._FLUENT_LIGHT_CANVAS
    assert native.opaque_background(_system(dark=True)) == appearance._FLUENT_DARK_CANVAS
    assert native.opaque_background(_system(high_contrast=True)) == "#010203"
    assert indices == [appearance._COLOR_WINDOW]


def test_native_snapshot_reads_each_windows_appearance_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(appearance, "_read_dark_theme", lambda: True)
    monkeypatch.setattr(appearance, "_read_high_contrast", lambda: False)
    monkeypatch.setattr(
        appearance,
        "_read_accent_palette",
        lambda _settings: ("#445566", "#667788", "#223344"),
    )
    monkeypatch.setattr(appearance, "_windows_build", lambda: 26100)
    native = appearance._WindowsAppearanceNative()
    monkeypatch.setattr(native, "_get_ui_settings", lambda: object())

    assert native.read() == SystemAppearance(
        dark=True,
        high_contrast=False,
        accent="#445566",
        build=26100,
        accent_hover="#667788",
        accent_pressed="#223344",
    )


def test_windows_accent_palette_uses_all_three_ui_settings_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Enum:
        @staticmethod
        def Parse(_type: object, name: str) -> str:
            return name

    colors = {
        "Accent": SimpleNamespace(R=1, G=2, B=3),
        "AccentLight1": SimpleNamespace(R=4, G=5, B=6),
        "AccentDark1": SimpleNamespace(R=7, G=8, B=9),
    }
    getter = SimpleNamespace(
        Invoke=lambda _settings, arguments: colors[arguments[0]],
    )
    settings_type = SimpleNamespace(GetMethod=lambda _name: getter)
    settings = SimpleNamespace(GetType=lambda: settings_type)
    fake_type = SimpleNamespace(GetType=lambda _name: object())
    monkeypatch.setitem(
        sys.modules,
        "System",
        SimpleNamespace(Enum=Enum, Type=fake_type),
    )

    assert appearance._read_accent_palette(settings) == (
        "#010203",
        "#040506",
        "#070809",
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows UISettings is native")
def test_pinned_runtime_reads_the_live_ui_settings_palette() -> None:
    settings = appearance._create_ui_settings()
    from System import Enum, Type

    color_type = Type.GetType(
        "Windows.UI.ViewManagement.UIColorType, Windows.UI.ViewManagement, "
        "ContentType=WindowsRuntime"
    )
    getter = settings.GetType().GetMethod("GetColorValue")
    assert color_type is not None
    assert getter is not None

    def direct(name: str) -> str:
        value = getter.Invoke(settings, (Enum.Parse(color_type, name),))
        return f"#{int(value.R):02X}{int(value.G):02X}{int(value.B):02X}"

    assert settings.GetType().FullName == "Windows.UI.ViewManagement.UISettings"
    assert appearance._read_accent_palette(settings) == tuple(
        direct(name) for name in ("Accent", "AccentLight1", "AccentDark1")
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows UISettings is native")
def test_pinned_runtime_native_observer_attaches_and_detaches_exactly() -> None:
    native = appearance._WindowsAppearanceNative()
    settings = native._get_ui_settings()
    assert settings is not None
    assert settings.GetType().FullName == "Windows.UI.ViewManagement.UISettings"

    unsubscribe = native.subscribe(lambda: None)
    unsubscribe()


def test_native_subscription_observes_theme_and_accent_and_unsubscribes_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preferences = _Hook()
    colors = _Hook()
    system_events = SimpleNamespace(UserPreferenceChanged=preferences)
    monkeypatch.setitem(
        sys.modules,
        "Microsoft.Win32",
        SimpleNamespace(SystemEvents=system_events),
    )
    native = appearance._WindowsAppearanceNative()
    settings = SimpleNamespace()
    monkeypatch.setattr(
        native,
        "_get_ui_settings",
        lambda: settings,
    )
    def subscribe_colors(actual_settings: object, callback):
        assert actual_settings is settings
        colors.handlers.append(callback)

        def unsubscribe() -> None:
            colors.handlers.remove(callback)

        return unsubscribe

    monkeypatch.setattr(appearance, "_subscribe_color_values", subscribe_colors)
    calls: list[str] = []

    unsubscribe = native.subscribe(lambda: calls.append("changed"))
    preferences.emit(None, None)
    colors.emit(None, None)

    assert calls == ["changed", "changed"]
    unsubscribe()
    preferences.emit(None, None)
    colors.emit(None, None)
    assert calls == ["changed", "changed"]


def test_failed_accent_subscription_rolls_back_theme_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preferences = _Hook()
    system_events = SimpleNamespace(UserPreferenceChanged=preferences)
    monkeypatch.setitem(
        sys.modules,
        "Microsoft.Win32",
        SimpleNamespace(SystemEvents=system_events),
    )
    native = appearance._WindowsAppearanceNative()
    monkeypatch.setattr(native, "_get_ui_settings", lambda: object())
    monkeypatch.setattr(
        appearance,
        "_subscribe_color_values",
        lambda _settings, _callback: (_ for _ in ()).throw(
            RuntimeError("injected accent subscription failure")
        ),
    )

    with pytest.raises(RuntimeError, match="accent subscription failure"):
        native.subscribe(lambda: None)

    assert preferences.handlers == []


def test_coincident_ui_settings_palette_values_are_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Enum:
        @staticmethod
        def Parse(_type: object, name: str) -> str:
            return name

    color = SimpleNamespace(R=1, G=2, B=3)
    getter = SimpleNamespace(Invoke=lambda _settings, _arguments: color)
    settings = SimpleNamespace(
        GetType=lambda: SimpleNamespace(GetMethod=lambda _name: getter)
    )
    monkeypatch.setitem(
        sys.modules,
        "System",
        SimpleNamespace(
            Enum=Enum,
            Type=SimpleNamespace(GetType=lambda _name: object()),
        ),
    )

    assert appearance._read_accent_palette(settings) == (
        "#010203",
        "#010203",
        "#010203",
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
    ) == appearance._BackgroundLanding(False, True)
    assert control.DefaultBackgroundColor is transparent
    assert native._set_controller_background(
        native_window,
        _system(dark=True),
        transparent=False,
    ) == appearance._BackgroundLanding(True, True)
    assert control.DefaultBackgroundColor == (255, 1, 2, 3)
    assert native_window.BackColor == (255, 1, 2, 3)


@pytest.mark.parametrize(
    ("form_succeeds", "controller_succeeds"),
    (
        (True, False),
        (False, True),
        (False, False),
    ),
)
def test_native_opaque_background_reports_each_occluding_path(
    monkeypatch: pytest.MonkeyPatch,
    form_succeeds: bool,
    controller_succeeds: bool,
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
    ) == appearance._BackgroundLanding(form_succeeds, controller_succeeds)


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


def test_documented_accent_read_and_no_direct_document_sink() -> None:
    source = inspect.getsource(appearance)

    assert "UISettings" in source
    assert 'read("AccentLight1")' in source
    assert 'read("AccentDark1")' in source
    assert "DwmSetWindowAttribute" in source
    assert "SetSysColors" not in source
    assert "winreg.SetValue" not in source
    assert "evaluate_js" not in source
    assert "run_js" not in source
    assert "PostWebMessageAsJson" not in source
