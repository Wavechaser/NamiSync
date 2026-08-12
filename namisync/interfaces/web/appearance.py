"""Progressive Windows appearance for the pinned pywebview/WebView2 host."""

from __future__ import annotations

import ctypes
import logging
import re
import sys
import winreg
from ctypes import wintypes
from dataclasses import dataclass
from threading import Lock, Thread, current_thread
from typing import Callable, Literal, Protocol


_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_SYSTEMBACKDROP_TYPE = 38
_DWMSBT_NONE = 1
_DWMSBT_MAINWINDOW = 2
_MICA_MINIMUM_BUILD = 22621

_SPI_GETHIGHCONTRAST = 0x0042
_HCF_HIGHCONTRASTON = 0x00000001
_COLOR_WINDOW = 5
_COLOR_HIGHLIGHT = 13

_RGB = re.compile(r"#[0-9A-F]{6}\Z")
_PUBLISH_CLOSE_TIMEOUT_SECONDS = 1.0


class _HIGHCONTRASTW(ctypes.Structure):
    _fields_ = (
        ("cbSize", wintypes.UINT),
        ("dwFlags", wintypes.DWORD),
        ("lpszDefaultScheme", wintypes.LPWSTR),
    )


class _MARGINS(ctypes.Structure):
    _fields_ = (
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    )


@dataclass(frozen=True)
class SystemAppearance:
    """A validated, inert snapshot of Windows-owned appearance state."""

    dark: bool
    high_contrast: bool
    accent: str
    build: int

    def __post_init__(self) -> None:
        if type(self.dark) is not bool or type(self.high_contrast) is not bool:
            raise TypeError("appearance flags must be Boolean")
        if not isinstance(self.build, int) or isinstance(self.build, bool):
            raise TypeError("Windows build must be an integer")
        if self.build < 0:
            raise ValueError("Windows build must be non-negative")
        if not isinstance(self.accent, str) or _RGB.fullmatch(self.accent) is None:
            raise ValueError("accent must be an uppercase #RRGGBB color")

    @property
    def theme(self) -> Literal["light", "dark"]:
        return "dark" if self.dark else "light"

    @property
    def supports_mica(self) -> bool:
        return self.build >= _MICA_MINIMUM_BUILD


@dataclass(frozen=True)
class _Presentation:
    system: SystemAppearance
    material: Literal["mica", "opaque"] | None


class _AppearanceNative(Protocol):
    def read(self) -> SystemAppearance: ...

    def opaque_background(self, system: SystemAppearance) -> str: ...

    def apply(
        self,
        native_window: object,
        system: SystemAppearance,
    ) -> Literal["mica", "opaque"] | None: ...

    def force_opaque(
        self,
        native_window: object,
        system: SystemAppearance,
    ) -> bool: ...

    def invoke(
        self,
        native_window: object,
        callback: Callable[[], None],
    ) -> None: ...

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]: ...


class _WindowsAppearanceNative:
    """Small native boundary around documented DWM and managed control APIs."""

    def read(self) -> SystemAppearance:
        return SystemAppearance(
            dark=_read_dark_theme(),
            high_contrast=_read_high_contrast(),
            accent=_read_accent(),
            build=_windows_build(),
        )

    def opaque_background(self, system: SystemAppearance) -> str:
        del system
        return _system_color(_COLOR_WINDOW)

    def apply(
        self,
        native_window: object,
        system: SystemAppearance,
    ) -> Literal["mica", "opaque"] | None:
        if system.high_contrast or not system.supports_mica:
            return (
                "opaque"
                if self.force_opaque(native_window, system)
                else None
            )

        if not self._set_controller_background(
            native_window,
            system,
            transparent=True,
        ):
            return (
                "opaque"
                if self.force_opaque(native_window, system)
                else None
            )
        if not self._set_client_glass(native_window, enabled=True):
            return (
                "opaque"
                if self.force_opaque(native_window, system)
                else None
            )

        if not self._set_dwm_attribute(
            native_window,
            _DWMWA_USE_IMMERSIVE_DARK_MODE,
            int(system.dark),
        ):
            return (
                "opaque"
                if self.force_opaque(native_window, system)
                else None
            )
        if not self._set_dwm_attribute(
            native_window,
            _DWMWA_SYSTEMBACKDROP_TYPE,
            _DWMSBT_MAINWINDOW,
        ):
            return (
                "opaque"
                if self.force_opaque(native_window, system)
                else None
            )
        return "mica"

    def force_opaque(
        self,
        native_window: object,
        system: SystemAppearance,
    ) -> bool:
        operations = (
            lambda: self._set_dwm_attribute(
                native_window,
                _DWMWA_SYSTEMBACKDROP_TYPE,
                _DWMSBT_NONE,
            ),
            lambda: self._set_client_glass(native_window, enabled=False),
            lambda: self._set_dwm_attribute(
                native_window,
                _DWMWA_USE_IMMERSIVE_DARK_MODE,
                int(system.dark and not system.high_contrast),
            ),
            lambda: self._set_controller_background(
                native_window,
                system,
                transparent=False,
            ),
        )
        results: list[bool] = []
        for operation in operations:
            try:
                results.append(bool(operation()))
            except Exception as error:
                _log_failure("appearance.opaque_fallback_operation_failed", error)
                results.append(False)
        if not all(results):
            logging.getLogger("namisync").warning(
                "appearance.opaque_fallback_incomplete"
            )
        backdrop_reset, _glass_reset, _dark_mode_set, opaque_landed = results
        return backdrop_reset and opaque_landed

    def invoke(
        self,
        native_window: object,
        callback: Callable[[], None],
    ) -> None:
        if not native_window.InvokeRequired:
            callback()
            return
        from System import Action

        native_window.BeginInvoke(Action(callback))

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        from Microsoft.Win32 import SystemEvents

        def on_preference_changed(_sender: object, _event: object) -> None:
            callback()

        SystemEvents.UserPreferenceChanged += on_preference_changed

        def unsubscribe() -> None:
            SystemEvents.UserPreferenceChanged -= on_preference_changed

        return unsubscribe

    def _set_dwm_attribute(
        self,
        native_window: object,
        attribute: int,
        value: int,
    ) -> bool:
        try:
            hwnd = _window_handle(native_window)
            data = ctypes.c_int(value)
            setter = ctypes.windll.dwmapi.DwmSetWindowAttribute
            setter.argtypes = (
                wintypes.HWND,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
            )
            setter.restype = ctypes.c_long
            return setter(
                hwnd,
                attribute,
                ctypes.byref(data),
                ctypes.sizeof(data),
            ) >= 0
        except Exception as error:
            _log_failure("appearance.dwm_attribute_failed", error)
            return False

    def _set_client_glass(
        self,
        native_window: object,
        *,
        enabled: bool,
    ) -> bool:
        try:
            from System.Drawing import Color

            margins = _MARGINS(
                -1 if enabled else 0,
                -1 if enabled else 0,
                -1 if enabled else 0,
                -1 if enabled else 0,
            )
            extender = ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea
            extender.argtypes = (wintypes.HWND, ctypes.POINTER(_MARGINS))
            extender.restype = ctypes.c_long
            if extender(_window_handle(native_window), ctypes.byref(margins)) < 0:
                return False
            if enabled:
                native_window.BackColor = Color.Black
            return True
        except Exception as error:
            _log_failure("appearance.client_glass_failed", error)
            return False

    def _set_controller_background(
        self,
        native_window: object,
        system: SystemAppearance,
        *,
        transparent: bool,
    ) -> bool:
        if transparent:
            try:
                from System.Drawing import Color

                native_window.browser.webview.DefaultBackgroundColor = (
                    Color.Transparent
                )
                return True
            except Exception as error:
                _log_failure("appearance.controller_background_failed", error)
                return False

        try:
            from System.Drawing import Color

            red, green, blue = _hex_components(self.opaque_background(system))
            color = Color.FromArgb(255, red, green, blue)
        except Exception as error:
            _log_failure("appearance.controller_background_failed", error)
            return False

        landed = False
        try:
            native_window.BackColor = color
            landed = True
        except Exception as error:
            _log_failure("appearance.form_background_failed", error)
        try:
            native_window.browser.webview.DefaultBackgroundColor = color
            landed = True
        except Exception as error:
            _log_failure("appearance.controller_background_failed", error)
        return landed


class WindowAppearanceController:
    """Own native material observation and inert document-token publication."""

    def __init__(self, window: object, native: _AppearanceNative) -> None:
        self._window = window
        self._native = native
        self._native_window: object | None = None
        self._lock = Lock()
        self._attempted = False
        self._closed = False
        self._loaded = False
        self._presentation: _Presentation | None = None
        self._presentation_revision = 0
        self._publish_running = False
        self._publish_thread: Thread | None = None
        self._unsubscribe: Callable[[], None] | None = None

    def attach(self) -> None:
        self._window.events.before_load += self._before_load
        try:
            self._window.events.loaded += self._on_loaded
        except Exception:
            event = self._window.events.before_load
            event -= self._before_load
            raise

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            unsubscribe = self._unsubscribe
            self._unsubscribe = None
            publish_thread = self._publish_thread
        if unsubscribe is not None:
            try:
                unsubscribe()
            except Exception as error:
                _log_failure("appearance.preference_unsubscribe_failed", error)
        self._remove_event_handler("before_load", self._before_load)
        self._remove_event_handler("loaded", self._on_loaded)
        if publish_thread is not None and publish_thread is not current_thread():
            publish_thread.join(_PUBLISH_CLOSE_TIMEOUT_SECONDS)
            if publish_thread.is_alive():
                logging.getLogger("namisync").warning(
                    "appearance.publisher_close_timeout"
                )

    def _before_load(self) -> None:
        with self._lock:
            if self._attempted or self._closed:
                return
            self._attempted = True
        try:
            native_window = self._window.native
            if native_window.InvokeRequired:
                raise RuntimeError(
                    "appearance callback did not run on the UI thread"
                )
        except Exception as error:
            _log_failure("appearance.ui_thread_unavailable", error)
            return

        with self._lock:
            if self._closed:
                return
            self._native_window = native_window

        self._read_and_apply(native_window, publish=False)
        try:
            unsubscribe = self._native.subscribe(self._on_preference_changed)
        except Exception as error:
            _log_failure("appearance.preference_subscribe_failed", error)
            return
        with self._lock:
            if self._closed:
                keep_subscription = False
            else:
                self._unsubscribe = unsubscribe
                keep_subscription = True
        if not keep_subscription:
            try:
                unsubscribe()
            except Exception as error:
                _log_failure("appearance.preference_unsubscribe_failed", error)

    def _on_preference_changed(self) -> None:
        with self._lock:
            if self._closed:
                return
        try:
            system = self._native.read()
        except Exception as error:
            _log_failure("appearance.system_read_failed", error)
            with self._lock:
                if self._closed:
                    return
                previous = self._presentation
                native_window = self._native_window
            if previous is not None and native_window is not None:
                try:
                    self._native.invoke(
                        native_window,
                        lambda: self._force_opaque(
                            native_window,
                            previous.system,
                            publish=True,
                        ),
                    )
                except Exception as fallback_error:
                    _log_failure(
                        "appearance.ui_dispatch_failed",
                        fallback_error,
                    )
            return

        with self._lock:
            if self._closed:
                return
            native_window = self._native_window
        if native_window is None:
            return

        def reassert() -> None:
            with self._lock:
                if self._closed:
                    return
            self._apply(native_window, system, publish=True)

        try:
            self._native.invoke(native_window, reassert)
        except Exception as error:
            _log_failure("appearance.ui_dispatch_failed", error)

    def _on_loaded(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._loaded = True
        self._schedule_publish()

    def _read_and_apply(self, native_window: object, *, publish: bool) -> None:
        try:
            system = self._native.read()
        except Exception as error:
            _log_failure("appearance.system_read_failed", error)
            return
        self._apply(native_window, system, publish=publish)

    def _apply(
        self,
        native_window: object,
        system: SystemAppearance,
        *,
        publish: bool,
    ) -> None:
        with self._lock:
            if self._closed:
                return
        try:
            material = self._native.apply(native_window, system)
        except Exception as error:
            _log_failure("appearance.material_apply_failed", error)
            self._force_opaque(native_window, system, publish=publish)
            return
        if material not in ("mica", "opaque"):
            if material is None:
                self._record_presentation(system, None, publish=publish)
                return
            _log_failure(
                "appearance.material_result_invalid",
                RuntimeError("invalid material result"),
            )
            self._force_opaque(native_window, system, publish=publish)
            return
        self._record_presentation(system, material, publish=publish)

    def _force_opaque(
        self,
        native_window: object,
        system: SystemAppearance,
        *,
        publish: bool,
    ) -> None:
        with self._lock:
            if self._closed:
                return
        try:
            confirmed = self._native.force_opaque(native_window, system)
        except Exception as error:
            _log_failure("appearance.opaque_fallback_failed", error)
            confirmed = False
        self._record_presentation(
            system,
            "opaque" if confirmed else None,
            publish=publish,
        )

    def _record_presentation(
        self,
        system: SystemAppearance,
        material: Literal["mica", "opaque"] | None,
        *,
        publish: bool,
    ) -> None:
        with self._lock:
            if self._closed:
                return
            self._presentation = _Presentation(system, material)
            self._presentation_revision += 1
            should_publish = publish and self._loaded
        if should_publish:
            self._schedule_publish()

    def _schedule_publish(self) -> None:
        with self._lock:
            if (
                self._closed
                or not self._loaded
                or self._presentation is None
                or self._publish_running
            ):
                return
            thread = Thread(
                target=self._publish_loop,
                name="namisync-appearance-publish",
                daemon=True,
            )
            self._publish_running = True
            self._publish_thread = thread
            try:
                thread.start()
            except Exception:
                self._publish_running = False
                self._publish_thread = None
                raise

    def _publish_loop(self) -> None:
        while True:
            with self._lock:
                if self._closed or not self._loaded:
                    self._publish_running = False
                    self._publish_thread = None
                    return
                presentation = self._presentation
                revision = self._presentation_revision
                native_window = self._native_window
                if presentation is None or native_window is None:
                    self._publish_running = False
                    self._publish_thread = None
                    return
            try:
                self._native.invoke(
                    native_window,
                    lambda: self._publish_on_ui(presentation, revision),
                )
            except Exception as error:
                _log_failure("appearance.ui_dispatch_failed", error)
            with self._lock:
                if self._closed or revision == self._presentation_revision:
                    self._publish_running = False
                    self._publish_thread = None
                    return

    def _publish_on_ui(
        self,
        presentation: _Presentation,
        revision: int,
    ) -> None:
        with self._lock:
            if self._closed or revision != self._presentation_revision:
                return
        try:
            root = self._window.dom.get_element(":root")
            if root is None:
                raise RuntimeError("document root is unavailable")
            root.attributes.update(
                {
                    "data-theme": presentation.system.theme,
                    "data-window-material": presentation.material,
                    "style": "--color-accent: " + presentation.system.accent,
                }
            )
        except Exception as error:
            _log_failure("appearance.document_publish_failed", error)

    def _remove_event_handler(
        self,
        event_name: str,
        handler: Callable[[], None],
    ) -> None:
        try:
            event = getattr(self._window.events, event_name)
            event -= handler
        except (AttributeError, ValueError) as error:
            _log_failure("appearance.event_unsubscribe_failed", error)


def opaque_window_background(
    *,
    native: _AppearanceNative | None = None,
) -> str:
    """Return the opaque public-window background used before enhancement."""

    implementation = native or _WindowsAppearanceNative()
    try:
        system = implementation.read()
        background = implementation.opaque_background(system)
        if _RGB.fullmatch(background) is None:
            raise ValueError("opaque background must be uppercase #RRGGBB")
        return background
    except Exception as error:
        _log_failure("appearance.initial_background_failed", error)
        background = _system_color(_COLOR_WINDOW)
        if _RGB.fullmatch(background) is None:
            raise ValueError("system window color must be uppercase #RRGGBB")
        return background


def configure_window_appearance(
    window: object,
    *,
    native: _AppearanceNative | None = None,
) -> WindowAppearanceController:
    """Register appearance after security at the same synchronous native seam."""

    controller = WindowAppearanceController(
        window,
        native or _WindowsAppearanceNative(),
    )
    controller.attach()
    return controller


def _read_dark_theme() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return int(value) == 0
    except (OSError, TypeError, ValueError):
        return False


def _read_high_contrast() -> bool:
    info = _HIGHCONTRASTW()
    info.cbSize = ctypes.sizeof(info)
    try:
        success = ctypes.windll.user32.SystemParametersInfoW(
            _SPI_GETHIGHCONTRAST,
            info.cbSize,
            ctypes.byref(info),
            0,
        )
    except Exception:
        return True
    if not success:
        return True
    return bool(info.dwFlags & _HCF_HIGHCONTRASTON)


def _windows_build() -> int:
    try:
        return int(sys.getwindowsversion().build)
    except (AttributeError, TypeError, ValueError):
        return 0


def _read_accent() -> str:
    try:
        color = wintypes.DWORD()
        opaque = wintypes.BOOL()
        reader = ctypes.windll.dwmapi.DwmGetColorizationColor
        reader.argtypes = (
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.BOOL),
        )
        reader.restype = ctypes.c_long
        if reader(ctypes.byref(color), ctypes.byref(opaque)) >= 0:
            return _argb_color(color.value)
    except Exception as error:
        _log_failure("appearance.accent_read_failed", error)
    return _system_color(_COLOR_HIGHLIGHT)


def _argb_color(value: int) -> str:
    return f"#{value & 0x00FFFFFF:06X}"


def _system_color(index: int) -> str:
    try:
        value = int(ctypes.windll.user32.GetSysColor(index))
    except Exception as error:
        _log_failure("appearance.system_color_read_failed", error)
        raise
    red = value & 0xFF
    green = (value >> 8) & 0xFF
    blue = (value >> 16) & 0xFF
    return f"#{red:02X}{green:02X}{blue:02X}"


def _hex_components(value: str) -> tuple[int, int, int]:
    if _RGB.fullmatch(value) is None:
        raise ValueError("color must be uppercase #RRGGBB")
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def _window_handle(native_window: object) -> int:
    handle = native_window.Handle
    return int(handle.ToInt64() if hasattr(handle, "ToInt64") else handle)


def _log_failure(event: str, error: Exception) -> None:
    logging.getLogger("namisync").error(
        "%s exception_type=%s",
        event,
        type(error).__name__,
    )
