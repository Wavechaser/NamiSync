"""Progressive Windows appearance for the pinned pywebview/WebView2 host."""

from __future__ import annotations

import ctypes
import json
import logging
import re
import sys
import winreg
from ctypes import wintypes
from dataclasses import dataclass
from threading import Lock
from typing import Callable, Literal, Protocol


_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_SYSTEMBACKDROP_TYPE = 38
_DWMSBT_NONE = 1
_DWMSBT_MAINWINDOW = 2
_MICA_MINIMUM_BUILD = 22621

_SPI_GETHIGHCONTRAST = 0x0042
_HCF_HIGHCONTRASTON = 0x00000001
_COLOR_WINDOW = 5

_RGB = re.compile(r"#[0-9A-F]{6}\Z")
_FLUENT_LIGHT_CANVAS = "#F5F5F5"
_FLUENT_DARK_CANVAS = "#1F1F1F"
_DEFAULT_ACCENT = "#0078D4"
_DEFAULT_ACCENT_HOVER = "#0091F8"
_DEFAULT_ACCENT_PRESSED = "#0067C0"
_APPEARANCE_MESSAGE_KIND = "namisync.appearance.v1"


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
    accent_hover: str = _DEFAULT_ACCENT_HOVER
    accent_pressed: str = _DEFAULT_ACCENT_PRESSED
    accent_foreground: str | None = None
    accent_hover_foreground: str | None = None
    accent_pressed_foreground: str | None = None

    def __post_init__(self) -> None:
        if type(self.dark) is not bool or type(self.high_contrast) is not bool:
            raise TypeError("appearance flags must be Boolean")
        if type(self.build) is not int:
            raise TypeError("Windows build must be an integer")
        if self.build < 0:
            raise ValueError("Windows build must be non-negative")
        for color_name, foreground_name in (
            ("accent", "accent_foreground"),
            ("accent_hover", "accent_hover_foreground"),
            ("accent_pressed", "accent_pressed_foreground"),
        ):
            if getattr(self, foreground_name) is None:
                object.__setattr__(
                    self,
                    foreground_name,
                    _contrast_foreground(getattr(self, color_name)),
                )
        for name in (
            "accent",
            "accent_hover",
            "accent_pressed",
            "accent_foreground",
            "accent_hover_foreground",
            "accent_pressed_foreground",
        ):
            value = getattr(self, name)
            if type(value) is not str or _RGB.fullmatch(value) is None:
                raise ValueError(f"{name} must be an uppercase #RRGGBB color")

    @property
    def theme(self) -> Literal["light", "dark"]:
        return "dark" if self.dark else "light"

    @property
    def supports_mica(self) -> bool:
        return self.build >= _MICA_MINIMUM_BUILD


@dataclass(frozen=True)
class _Presentation:
    system: SystemAppearance
    material: Literal["mica", "opaque", "degraded"] | None


@dataclass(frozen=True, slots=True)
class _BackgroundLanding:
    form: bool
    controller: bool


@dataclass(frozen=True, slots=True)
class _OpaqueEvidence:
    backdrop_reset: bool
    glass_reset: bool
    form_opaque: bool
    controller_opaque: bool

    @property
    def confirmed(self) -> bool:
        return self.backdrop_reset and (
            self.controller_opaque or (self.glass_reset and self.form_opaque)
        )


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

    def defer(
        self,
        native_window: object,
        callback: Callable[[], None],
    ) -> None: ...

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]: ...


class _WindowsAppearanceNative:
    """Small native boundary around documented DWM and managed control APIs."""

    def __init__(self) -> None:
        self._ui_settings: object | None = None
        self._ui_settings_attempted = False

    def read(self) -> SystemAppearance:
        accent, accent_hover, accent_pressed = _read_accent_palette(
            self._get_ui_settings()
        )
        return SystemAppearance(
            dark=_read_dark_theme(),
            high_contrast=_read_high_contrast(),
            accent=accent,
            build=_windows_build(),
            accent_hover=accent_hover,
            accent_pressed=accent_pressed,
            accent_foreground=_contrast_foreground(accent),
            accent_hover_foreground=_contrast_foreground(accent_hover),
            accent_pressed_foreground=_contrast_foreground(accent_pressed),
        )

    def opaque_background(self, system: SystemAppearance) -> str:
        if system.high_contrast:
            return _system_color(_COLOR_WINDOW)
        return _FLUENT_DARK_CANVAS if system.dark else _FLUENT_LIGHT_CANVAS

    def apply(
        self,
        native_window: object,
        system: SystemAppearance,
    ) -> Literal["mica", "opaque"] | None:
        if not system.supports_mica:
            return (
                "opaque"
                if self.force_opaque(native_window, system)
                else None
            )
        if system.high_contrast:
            return (
                "opaque"
                if self.force_opaque(native_window, system)
                else None
            )

        transparent_landing = _require_background_landing(
            self._set_controller_background(
                native_window,
                system,
                transparent=True,
            )
        )
        if not transparent_landing.controller:
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
        return self._force_opaque(
            native_window,
            system,
            require_backdrop_reset=system.supports_mica,
        )

    def _force_opaque(
        self,
        native_window: object,
        system: SystemAppearance,
        *,
        require_backdrop_reset: bool,
    ) -> bool:
        def attempt(operation: Callable[[], object]) -> object | None:
            try:
                return operation()
            except Exception as error:
                _log_failure("appearance.opaque_fallback_operation_failed", error)
                return None

        backdrop_reset = True
        if require_backdrop_reset:
            backdrop_reset = bool(
                attempt(
                    lambda: self._set_dwm_attribute(
                        native_window,
                        _DWMWA_SYSTEMBACKDROP_TYPE,
                        _DWMSBT_NONE,
                    )
                )
            )
        glass_reset = bool(
            attempt(lambda: self._set_client_glass(native_window, enabled=False))
        )
        # Dark-mode title-bar state is independent of whether client opacity landed.
        attempt(
            lambda: self._set_dwm_attribute(
                native_window,
                _DWMWA_USE_IMMERSIVE_DARK_MODE,
                int(system.dark and not system.high_contrast),
            )
        )
        landing_value = attempt(
            lambda: self._set_controller_background(
                native_window,
                system,
                transparent=False,
            )
        )
        landing = _require_background_landing(landing_value)
        evidence = _OpaqueEvidence(
            backdrop_reset=backdrop_reset,
            glass_reset=glass_reset,
            form_opaque=landing.form,
            controller_opaque=landing.controller,
        )
        if not evidence.confirmed:
            logging.getLogger("namisync").warning(
                "appearance.opaque_fallback_incomplete"
            )
        return evidence.confirmed

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

    def defer(
        self,
        native_window: object,
        callback: Callable[[], None],
    ) -> None:
        from System import Action

        native_window.BeginInvoke(Action(callback))

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        from Microsoft.Win32 import SystemEvents

        def on_preference_changed(_sender: object, _event: object) -> None:
            callback()

        def on_colors_changed(_sender: object, _event: object) -> None:
            callback()

        SystemEvents.UserPreferenceChanged += on_preference_changed
        try:
            ui_settings = self._get_ui_settings()
            if ui_settings is None:
                raise RuntimeError("Windows UISettings observation is unavailable")
            unsubscribe_colors = _subscribe_color_values(
                ui_settings,
                on_colors_changed,
            )
        except Exception:
            try:
                SystemEvents.UserPreferenceChanged -= on_preference_changed
            except Exception as rollback_error:
                _log_failure(
                    "appearance.preference_subscribe_rollback_failed",
                    rollback_error,
                )
            raise

        def unsubscribe() -> None:
            failure: Exception | None = None
            try:
                SystemEvents.UserPreferenceChanged -= on_preference_changed
            except Exception as error:
                failure = error
            try:
                unsubscribe_colors()
            except Exception as error:
                if failure is None:
                    failure = error
            if failure is not None:
                raise failure

        return unsubscribe

    def _get_ui_settings(self) -> object | None:
        if not self._ui_settings_attempted:
            self._ui_settings_attempted = True
            try:
                self._ui_settings = _create_ui_settings()
            except Exception as error:
                _log_failure("appearance.ui_settings_unavailable", error)
        return self._ui_settings

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
    ) -> _BackgroundLanding:
        if transparent:
            try:
                from System.Drawing import Color

                native_window.browser.webview.DefaultBackgroundColor = (
                    Color.Transparent
                )
                return _BackgroundLanding(False, True)
            except Exception as error:
                _log_failure("appearance.controller_background_failed", error)
                return _BackgroundLanding(False, False)

        try:
            from System.Drawing import Color

            red, green, blue = _hex_components(self.opaque_background(system))
            color = Color.FromArgb(255, red, green, blue)
        except Exception as error:
            _log_failure("appearance.controller_background_failed", error)
            return _BackgroundLanding(False, False)

        form_landed = False
        try:
            native_window.BackColor = color
            form_landed = True
        except Exception as error:
            _log_failure("appearance.form_background_failed", error)
        controller_landed = False
        try:
            native_window.browser.webview.DefaultBackgroundColor = color
            controller_landed = True
        except Exception as error:
            _log_failure("appearance.controller_background_failed", error)
        return _BackgroundLanding(form_landed, controller_landed)


class WindowAppearanceController:
    """Own native material observation and one-way appearance publication."""

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
        self._startup_failure: RuntimeError | None = None
        self._unsubscribe: Callable[[], None] | None = None
        self._observation_active = False
        self._observation_generation = 0
        self._observation_scheduled = False
        self._initial_observation_pending = False
        self._initial_publication_requested = False
        self._initial_publication_complete = False
        self._initial_publication_failed = False
        self._initial_publication_callback: (
            Callable[[Exception | None], None] | None
        ) = None
        self._document_generation = 0
        self._publication_in_flight: tuple[int, int] | None = None

    @property
    def startup_failure(self) -> RuntimeError | None:
        with self._lock:
            return self._startup_failure

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
            self._observation_active = False
            self._observation_scheduled = False
            self._initial_observation_pending = False
            self._publication_in_flight = None
            self._initial_publication_callback = None
        if unsubscribe is not None:
            try:
                unsubscribe()
            except Exception as error:
                _log_failure("appearance.preference_unsubscribe_failed", error)
        self._remove_event_handler("before_load", self._before_load)
        self._remove_event_handler("loaded", self._on_loaded)

    def request_initial_publication(
        self,
        generation: int,
        callback: Callable[[Exception | None], None],
    ) -> None:
        if not callable(callback):
            raise TypeError("initial publication callback must be callable")
        with self._lock:
            if self._closed:
                raise RuntimeError("appearance controller is closed")
            if (
                type(generation) is not int
                or generation != self._document_generation
            ):
                raise RuntimeError("appearance document generation is stale")
            if self._initial_publication_requested:
                raise RuntimeError("initial appearance publication was already requested")
            self._initial_publication_requested = True
            self._initial_publication_callback = callback
        self._schedule_publish()

    def _before_load(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._document_generation += 1
            self._loaded = False
            if self._attempted:
                if self._presentation is not None:
                    self._presentation_revision += 1
                self._initial_publication_requested = False
                self._initial_publication_complete = False
                self._initial_publication_failed = False
                self._initial_publication_callback = None
                self._publication_in_flight = None
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
            self._record_startup_failure(
                "Windows appearance could not attach on the UI thread"
            )
            return

        with self._lock:
            if self._closed:
                return
            self._native_window = native_window
            self._observation_active = True
            self._observation_generation += 1
            self._observation_scheduled = True
            self._initial_observation_pending = True

        try:
            unsubscribe = self._native.subscribe(self._on_preference_changed)
        except Exception as error:
            _log_failure("appearance.preference_subscribe_failed", error)
            with self._lock:
                self._observation_active = False
                self._observation_scheduled = False
                self._initial_observation_pending = False
            self._record_startup_failure(
                "Windows appearance observation could not start"
            )
            return
        with self._lock:
            if self._closed:
                keep_subscription = False
                self._observation_active = False
                self._observation_scheduled = False
                self._initial_observation_pending = False
            else:
                self._unsubscribe = unsubscribe
                keep_subscription = True
        if not keep_subscription:
            try:
                unsubscribe()
            except Exception as error:
                _log_failure("appearance.preference_unsubscribe_failed", error)
            return
        self._drain_observation()

    def _on_preference_changed(self) -> None:
        with self._lock:
            if self._closed or not self._observation_active:
                return
            self._observation_generation += 1
            if self._observation_scheduled:
                return
            self._observation_scheduled = True
            native_window = self._native_window
            generation = self._observation_generation
        if native_window is None:
            with self._lock:
                self._observation_scheduled = False
            return
        self._dispatch_observation(native_window, generation, deferred=False)

    def _dispatch_observation(
        self,
        native_window: object,
        generation: int,
        *,
        deferred: bool,
        retry_newer: bool = True,
    ) -> None:
        try:
            dispatch = self._native.defer if deferred else self._native.invoke
            dispatch(native_window, self._drain_observation)
        except Exception as error:
            _log_failure("appearance.ui_dispatch_failed", error)
            with self._lock:
                newer = (
                    not self._closed
                    and self._observation_active
                    and generation != self._observation_generation
                )
                self._observation_scheduled = False
                if newer and retry_newer:
                    self._observation_scheduled = True
                    retry_generation = self._observation_generation
                else:
                    retry_generation = None
            if retry_generation is not None:
                self._dispatch_observation(
                    native_window,
                    retry_generation,
                    deferred=deferred,
                    retry_newer=False,
                )

    def _drain_observation(self) -> None:
        with self._lock:
            if self._closed or not self._observation_active:
                self._observation_scheduled = False
                return
            generation = self._observation_generation
            initial = self._initial_observation_pending
            native_window = self._native_window
        if native_window is None:
            with self._lock:
                self._observation_scheduled = False
            return
        try:
            system = self._native.read()
        except Exception as error:
            _log_failure("appearance.system_read_failed", error)
            if initial:
                self._fail_initial_observation()
                return
            with self._lock:
                if self._closed or not self._observation_active:
                    self._observation_scheduled = False
                    return
                previous = self._presentation
            if previous is not None:
                self._force_opaque(
                    native_window,
                    previous.system,
                    publish=False,
                    startup=False,
                )
        else:
            self._apply(
                native_window,
                system,
                publish=False,
                startup=initial,
            )

        with self._lock:
            if self._closed or not self._observation_active:
                self._observation_scheduled = False
                return
            if generation == self._observation_generation:
                self._observation_scheduled = False
                self._initial_observation_pending = False
                publish = self._loaded
                defer_pending = False
            else:
                publish = False
                defer_pending = True
        if publish:
            self._schedule_publish()
        if not defer_pending:
            return
        self._dispatch_observation(
            native_window,
            generation,
            deferred=True,
        )

    def _on_loaded(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._loaded = True
        self._schedule_publish()

    def _fail_initial_observation(
        self,
        message: str = "Windows appearance state could not be read",
    ) -> None:
        with self._lock:
            if self._closed:
                self._observation_scheduled = False
                return
            self._observation_active = False
            self._observation_scheduled = False
            self._initial_observation_pending = False
            unsubscribe = self._unsubscribe
            self._unsubscribe = None
            self._startup_failure = RuntimeError(message)
        if unsubscribe is not None:
            try:
                unsubscribe()
            except Exception as error:
                _log_failure("appearance.preference_unsubscribe_failed", error)
        self._schedule_publish()

    def _apply(
        self,
        native_window: object,
        system: SystemAppearance,
        *,
        publish: bool,
        startup: bool,
    ) -> None:
        with self._lock:
            if self._closed:
                return
        try:
            material = self._native.apply(native_window, system)
        except Exception as error:
            _log_failure("appearance.material_apply_failed", error)
            self._force_opaque(
                native_window,
                system,
                publish=publish,
                startup=startup,
            )
            return
        if material not in ("mica", "opaque"):
            if material is None:
                self._record_presentation(
                    system,
                    None,
                    publish=publish,
                    startup=startup,
                )
                return
            _log_failure(
                "appearance.material_result_invalid",
                RuntimeError("invalid material result"),
            )
            self._force_opaque(
                native_window,
                system,
                publish=publish,
                startup=startup,
            )
            return
        self._record_presentation(
            system,
            material,
            publish=publish,
            startup=startup,
        )

    def _force_opaque(
        self,
        native_window: object,
        system: SystemAppearance,
        *,
        publish: bool,
        startup: bool,
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
            startup=startup,
        )

    def _record_presentation(
        self,
        system: SystemAppearance,
        material: Literal["mica", "opaque"] | None,
        *,
        publish: bool,
        startup: bool,
    ) -> None:
        with self._lock:
            if self._closed:
                return
            startup_observation = startup or not self._loaded
            presented_material = (
                "degraded"
                if self._loaded
                and not startup_observation
                and material is None
                else material
            )
            self._presentation = _Presentation(system, presented_material)
            self._presentation_revision += 1
            if startup_observation:
                self._startup_failure = (
                    RuntimeError(
                        "NamiSync could not establish a readable window material"
                    )
                    if presented_material is None
                    else None
                )
            should_publish = publish and self._loaded
        if should_publish:
            self._schedule_publish()

    def _schedule_publish(self) -> None:
        initial_error: Exception | None = None
        with self._lock:
            generation = self._document_generation
            initial = (
                self._initial_publication_requested
                and not self._initial_publication_complete
                and not self._initial_publication_failed
            )
            if (
                initial
                and not self._initial_observation_pending
                and self._startup_failure is not None
            ):
                initial_error = self._startup_failure
            if (
                self._closed
                or not self._initial_publication_requested
                or self._initial_publication_failed
                or self._publication_in_flight is not None
                or not self._loaded
                or self._initial_observation_pending
                or self._presentation is None
                or self._presentation.material is None
            ):
                native_window = None
                revision = None
            elif not initial and not self._initial_publication_complete:
                native_window = None
                revision = None
            else:
                native_window = self._native_window
                revision = self._presentation_revision
                self._publication_in_flight = (generation, revision)
        if initial_error is not None:
            self._finish_initial_publication(generation, initial_error)
            return
        if native_window is None or revision is None:
            return
        try:
            self._native.invoke(
                native_window,
                lambda: self._publish_document(
                    native_window,
                    generation,
                    revision,
                    initial=initial,
                ),
            )
        except Exception as error:
            _log_failure("appearance.ui_dispatch_failed", error)
            with self._lock:
                if self._publication_in_flight == (generation, revision):
                    self._publication_in_flight = None
            if initial:
                self._finish_initial_publication(generation, error)

    def _publish_document(
        self,
        native_window: object,
        generation: int,
        revision: int,
        *,
        initial: bool,
    ) -> None:
        retry_current = False
        with self._lock:
            if self._publication_in_flight != (generation, revision):
                return
            if self._closed:
                self._publication_in_flight = None
                return
            if generation != self._document_generation:
                self._publication_in_flight = None
                return
            if (
                revision != self._presentation_revision
                or self._presentation is None
                or self._presentation.material is None
            ):
                self._publication_in_flight = None
                retry_current = True
                presentation = None
            else:
                presentation = self._presentation
        if retry_current:
            self._schedule_publish()
            return
        if presentation is None:
            return
        system = presentation.system
        payload = {
            "kind": _APPEARANCE_MESSAGE_KIND,
            "revision": revision,
            "theme": system.theme,
            "highContrast": system.high_contrast,
            "material": presentation.material,
            "accent": system.accent,
            "accentHover": system.accent_hover,
            "accentPressed": system.accent_pressed,
            "accentForeground": system.accent_foreground,
            "accentHoverForeground": system.accent_hover_foreground,
            "accentPressedForeground": system.accent_pressed_foreground,
        }
        try:
            core = native_window.browser.webview.CoreWebView2
            core.PostWebMessageAsJson(
                json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
            )
        except Exception as error:
            _log_failure("appearance.document_publish_failed", error)
            with self._lock:
                if self._publication_in_flight == (generation, revision):
                    self._publication_in_flight = None
            if initial:
                self._finish_initial_publication(generation, error)
            return
        with self._lock:
            if self._publication_in_flight == (generation, revision):
                self._publication_in_flight = None
            retry_current = (
                not self._closed
                and generation == self._document_generation
                and revision != self._presentation_revision
            )
        if initial and not retry_current:
            completed = self._finish_initial_publication(
                generation,
                None,
                expected_revision=revision,
            )
            if completed is False:
                self._schedule_publish()
        if retry_current:
            self._schedule_publish()

    def _finish_initial_publication(
        self,
        generation: int,
        error: Exception | None,
        *,
        expected_revision: int | None = None,
    ) -> bool | None:
        with self._lock:
            if (
                self._closed
                or generation != self._document_generation
                or not self._initial_publication_requested
                or self._initial_publication_complete
                or self._initial_publication_failed
            ):
                return None
            if (
                error is None
                and expected_revision is not None
                and expected_revision != self._presentation_revision
            ):
                return False
            if error is None:
                self._initial_publication_complete = True
            else:
                self._initial_publication_failed = True
            callback = self._initial_publication_callback
            self._initial_publication_callback = None
        if callback is not None:
            try:
                callback(error)
            except Exception as callback_error:
                _log_failure(
                    "appearance.initial_publication_callback_failed",
                    callback_error,
                )
        return True

    def _record_startup_failure(self, message: str) -> None:
        with self._lock:
            if not self._closed and not self._loaded:
                self._startup_failure = RuntimeError(message)

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


def _create_ui_settings() -> object:
    __import__("clr")
    from System import Activator, Type

    settings_type = Type.GetType(
        "Windows.UI.ViewManagement.UISettings, Windows.UI.ViewManagement, "
        "ContentType=WindowsRuntime"
    )
    if settings_type is None:
        raise RuntimeError("Windows UISettings type is unavailable")
    return Activator.CreateInstance(settings_type)


def _read_accent_palette(
    settings: object | None,
) -> tuple[str, str, str]:
    if settings is None:
        return _DEFAULT_ACCENT, _DEFAULT_ACCENT_HOVER, _DEFAULT_ACCENT_PRESSED
    try:
        from System import Enum, Type

        color_type = Type.GetType(
            "Windows.UI.ViewManagement.UIColorType, Windows.UI.ViewManagement, "
            "ContentType=WindowsRuntime"
        )
        settings_type = settings.GetType()
        getter = settings_type.GetMethod("GetColorValue")
        if color_type is None or getter is None:
            raise RuntimeError("Windows UISettings color API is unavailable")

        def read(name: str) -> str:
            member = Enum.Parse(color_type, name)
            color = getter.Invoke(settings, (member,))
            return f"#{int(color.R):02X}{int(color.G):02X}{int(color.B):02X}"

        palette = read("Accent"), read("AccentLight1"), read("AccentDark1")
        if any(_RGB.fullmatch(value) is None for value in palette):
            raise ValueError("Windows returned an invalid accent palette")
        return palette
    except Exception as error:
        _log_failure("appearance.accent_palette_fallback", error)
        return _DEFAULT_ACCENT, _DEFAULT_ACCENT_HOVER, _DEFAULT_ACCENT_PRESSED


def _subscribe_color_values(
    settings: object,
    callback: Callable[[object, object], None],
) -> Callable[[], None]:
    from System import Object
    from Windows.Foundation import TypedEventHandler
    from Windows.UI.ViewManagement import UISettings

    event = settings.GetType().GetEvent("ColorValuesChanged")
    if event is None:
        raise RuntimeError("Windows UISettings color event is unavailable")
    add = event.GetAddMethod()
    remove = event.GetRemoveMethod()
    if add is None or remove is None:
        raise RuntimeError("Windows UISettings color event accessors are unavailable")
    handler = TypedEventHandler[UISettings, Object](callback)
    token = add.Invoke(settings, (handler,))

    def unsubscribe() -> None:
        # The WinRT remove accessor consumes the exact token returned by add.
        # Retaining the typed delegate here also keeps the callback alive until
        # that token is retired.
        _ = handler
        remove.Invoke(settings, (token,))

    return unsubscribe


def _contrast_foreground(background: str) -> str:
    red, green, blue = _hex_components(background)

    def channel(value: int) -> float:
        normalized = value / 255
        return (
            normalized / 12.92
            if normalized <= 0.04045
            else ((normalized + 0.055) / 1.055) ** 2.4
        )

    luminance = (
        0.2126 * channel(red)
        + 0.7152 * channel(green)
        + 0.0722 * channel(blue)
    )
    white_contrast = 1.05 / (luminance + 0.05)
    black_contrast = (luminance + 0.05) / 0.05
    return "#FFFFFF" if white_contrast >= black_contrast else "#000000"


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


def _require_background_landing(value: object) -> _BackgroundLanding:
    if type(value) is not _BackgroundLanding:
        raise TypeError("native background result must be _BackgroundLanding")
    return value


def _window_handle(native_window: object) -> int:
    handle = native_window.Handle
    return int(handle.ToInt64() if hasattr(handle, "ToInt64") else handle)


def _log_failure(event: str, error: Exception) -> None:
    logging.getLogger("namisync").error(
        "%s exception_type=%s",
        event,
        type(error).__name__,
    )
