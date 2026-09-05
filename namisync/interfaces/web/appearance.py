"""Progressive Windows appearance for the pinned pywebview/WebView2 host."""

from __future__ import annotations

import ctypes
import logging
import re
import sys
import winreg
from ctypes import wintypes
from dataclasses import dataclass, replace
from threading import Lock
from typing import Callable, Literal, Protocol

from namisync.interfaces.ui_state import (
    APPEARANCE_VALUE_VERSION,
    MAX_JAVASCRIPT_SAFE_INTEGER,
    AppearanceValue,
    CosmeticSectionSnapshot,
    CosmeticSubscription,
    ThemeMode,
)
from namisync.interfaces.web.document_channel import (
    DocumentChannel,
    DocumentPostKind,
    DocumentRetiredError,
    DocumentStaleError,
)


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
_DEFAULT_ACCENT_LIGHT_1 = "#0091F8"
_DEFAULT_ACCENT_LIGHT_2 = "#4CC2FF"
_DEFAULT_ACCENT_DARK_1 = "#0067C0"
_APPEARANCE_MESSAGE_KIND = "namisync.appearance.v2"


class UnsafeSurfaceError(RuntimeError):
    """The controller cannot confirm a readable native window surface."""


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


@dataclass(frozen=True, slots=True)
class _AccentPalette:
    accent: str
    light_1: str
    light_2: str
    dark_1: str


@dataclass(frozen=True)
class SystemAppearance:
    """A validated, inert snapshot of Windows-owned appearance state."""

    dark: bool
    high_contrast: bool
    accent: str
    build: int
    accent_light_1: str = _DEFAULT_ACCENT_LIGHT_1
    accent_light_2: str = _DEFAULT_ACCENT_LIGHT_2
    accent_dark_1: str = _DEFAULT_ACCENT_DARK_1

    def __post_init__(self) -> None:
        if type(self.dark) is not bool or type(self.high_contrast) is not bool:
            raise TypeError("appearance flags must be Boolean")
        if type(self.build) is not int:
            raise TypeError("Windows build must be an integer")
        if self.build < 0:
            raise ValueError("Windows build must be non-negative")
        for name in (
            "accent",
            "accent_light_1",
            "accent_light_2",
            "accent_dark_1",
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

    @property
    def accent_fill(self) -> str:
        return self.accent_light_2 if self.dark else self.accent_dark_1

    @property
    def accent_fill_hover(self) -> str:
        return f"{self.accent_fill}E6"

    @property
    def accent_fill_pressed(self) -> str:
        return f"{self.accent_fill}CC"

    @property
    def accent_fill_foreground(self) -> str:
        return _contrast_foreground(self.accent_fill)


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


class AppearanceNative(Protocol):
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


class _CosmeticAuthority(Protocol):
    def subscribe(
        self,
        section: str,
        callback: Callable[[CosmeticSectionSnapshot], None],
    ) -> CosmeticSubscription: ...


class _WindowsAppearanceNative:
    """Small native boundary around documented DWM and managed control APIs."""

    def __init__(self) -> None:
        self._ui_settings: object | None = None
        self._ui_settings_attempted = False

    def read(self) -> SystemAppearance:
        palette = _read_accent_palette(self._get_ui_settings())
        return SystemAppearance(
            dark=_read_dark_theme(),
            high_contrast=_read_high_contrast(),
            accent=palette.accent,
            build=_windows_build(),
            accent_light_1=palette.light_1,
            accent_light_2=palette.light_2,
            accent_dark_1=palette.dark_1,
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
        def recover_after_enhancement() -> Literal["opaque"]:
            try:
                if self.force_opaque(native_window, system):
                    return "opaque"
            except Exception as error:
                raise UnsafeSurfaceError(
                    "NamiSync could not complete an opaque rollback after "
                    "changing the native window surface"
                ) from error
            raise UnsafeSurfaceError(
                "NamiSync could not confirm an opaque rollback after "
                "changing the native window surface"
            )

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
            return recover_after_enhancement()
        if not self._set_client_glass(native_window, enabled=True):
            return recover_after_enhancement()

        if not self._set_dwm_attribute(
            native_window,
            _DWMWA_USE_IMMERSIVE_DARK_MODE,
            int(system.dark),
        ):
            return recover_after_enhancement()
        if not self._set_dwm_attribute(
            native_window,
            _DWMWA_SYSTEMBACKDROP_TYPE,
            _DWMSBT_MAINWINDOW,
        ):
            return recover_after_enhancement()
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

    def __init__(
        self,
        window: object,
        native: AppearanceNative,
        *,
        initial_cosmetic: CosmeticSectionSnapshot | None = None,
    ) -> None:
        self._window = window
        self._native = native
        self._native_window: object | None = None
        self._document_channel: DocumentChannel | None = None
        self._owns_document_channel = False
        self._document_publication_open = True
        self._document_publication_generation: int | None = None
        self._lock = Lock()
        self._attempted = False
        self._closed = False
        self._loaded = False
        self._presentation: _Presentation | None = None
        self._presentation_revision = 0
        self._presentation_revision_exhausted = False
        self._surface_safety_failure: UnsafeSurfaceError | None = None
        self._unsubscribe: Callable[[], None] | None = None
        self._cosmetic_subscription: CosmeticSubscription | None = None
        if initial_cosmetic is None:
            self._theme_mode = ThemeMode.SYSTEM
            self._cosmetic_revision = -1
        else:
            self._theme_mode = _cosmetic_theme(initial_cosmetic)
            self._cosmetic_revision = initial_cosmetic.revision
        self._observation_active = False
        self._observation_token = object()
        self._observation_scheduled = False
        self._initial_observation_pending = False
        self._surface_settlement_known = False
        self._surface_settlement_callback: (
            Callable[[Exception | None], None] | None
        ) = None
        self._document_epoch = object()
        self._publication_in_flight: tuple[object, int] | None = None

    @property
    def surface_safety_failure(self) -> UnsafeSurfaceError | None:
        with self._lock:
            return self._surface_safety_failure

    def bind_cosmetics(self, cosmetics: _CosmeticAuthority) -> None:
        """Subscribe atomically without making cosmetics a readiness input."""

        try:
            subscription = cosmetics.subscribe(
                "appearance",
                self._on_cosmetic_changed,
            )
        except Exception as error:
            _log_failure("appearance.cosmetic_subscribe_failed", error)
            return
        with self._lock:
            if self._closed:
                keep_subscription = False
            else:
                self._cosmetic_subscription = subscription
                keep_subscription = True
        if not keep_subscription:
            self._close_cosmetic_subscription(subscription)
            return
        self._on_cosmetic_changed(subscription.snapshot)

    def _bind_document_channel(self, channel: DocumentChannel) -> None:
        """Use the host's sole document-post owner for this window."""

        if type(channel) is not DocumentChannel:
            raise TypeError("appearance document channel has the wrong type")
        with self._lock:
            if self._closed:
                raise RuntimeError("appearance controller is closed")
            if self._document_channel is not None:
                if self._document_channel is channel:
                    return
                raise RuntimeError("appearance document channel is already bound")
            self._document_channel = channel
            self._document_publication_open = False
            self._document_publication_generation = None

    def _open_document_publication(self, generation: int) -> bool:
        """Allow the current acknowledged document to receive appearance."""

        if type(generation) is not int or generation < 0:
            return False
        with self._lock:
            if (
                self._closed
                or generation != self._document_publication_generation
            ):
                return False
            self._document_publication_open = True
        self._schedule_publish()
        return True

    def _revoke_document_publication(self, generation: int) -> None:
        """Prevent prior-document appearance from entering a successor."""

        if type(generation) is not int or generation < 0:
            raise ValueError("document publication generation is invalid")
        with self._lock:
            if self._document_channel is not None and not self._owns_document_channel:
                self._document_publication_open = False
                self._document_publication_generation = generation

    def attach(self) -> None:
        before_attached = False
        try:
            self._window.events.before_load += self._before_load
            before_attached = True
            self._window.events.loaded += self._on_loaded
        except Exception:
            if before_attached:
                self._remove_event_handler("before_load", self._before_load)
            self._abort_attachment()
            raise

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            unsubscribe = self._unsubscribe
            self._unsubscribe = None
            cosmetic_subscription = self._cosmetic_subscription
            self._cosmetic_subscription = None
            self._observation_active = False
            self._observation_token = object()
            self._observation_scheduled = False
            self._initial_observation_pending = False
            self._publication_in_flight = None
            surface_callback = self._surface_settlement_callback
            self._surface_settlement_callback = None
            owned_channel = (
                self._document_channel if self._owns_document_channel else None
            )
            self._document_channel = None
            self._owns_document_channel = False
        if owned_channel is not None:
            owned_channel.close()
        if surface_callback is not None:
            self._notify_surface_settlement(
                surface_callback,
                DocumentStaleError(
                    "appearance controller closed before surface settlement"
                ),
            )
        if cosmetic_subscription is not None:
            self._close_cosmetic_subscription(cosmetic_subscription)
        if unsubscribe is not None:
            try:
                unsubscribe()
            except Exception as error:
                _log_failure("appearance.preference_unsubscribe_failed", error)
        self._remove_event_handler("before_load", self._before_load)
        self._remove_event_handler("loaded", self._on_loaded)

    def _abort_attachment(self) -> None:
        with self._lock:
            self._closed = True
            self._observation_token = object()
            surface_callback = self._surface_settlement_callback
            self._surface_settlement_callback = None
            subscription = self._cosmetic_subscription
            self._cosmetic_subscription = None
            owned_channel = (
                self._document_channel if self._owns_document_channel else None
            )
            self._document_channel = None
            self._owns_document_channel = False
        if owned_channel is not None:
            owned_channel.close()
        if surface_callback is not None:
            self._notify_surface_settlement(
                surface_callback,
                DocumentStaleError(
                    "appearance attachment failed before surface settlement"
                ),
            )
        if subscription is not None:
            self._close_cosmetic_subscription(subscription)

    @staticmethod
    def _close_cosmetic_subscription(
        subscription: CosmeticSubscription,
    ) -> None:
        try:
            subscription.close()
        except Exception as error:
            _log_failure("appearance.cosmetic_unsubscribe_failed", error)

    def request_initial_surface_settlement(
        self,
        callback: Callable[[Exception | None], None],
    ) -> None:
        """Report once the initial native surface is confirmed readable."""

        if not callable(callback):
            raise TypeError("surface settlement callback must be callable")
        with self._lock:
            if self._closed:
                raise RuntimeError("appearance controller is closed")
            if self._surface_settlement_known:
                outcome = self._surface_safety_failure
                superseded = None
            else:
                superseded = self._surface_settlement_callback
                self._surface_settlement_callback = callback
                outcome = None
                callback = None
        if superseded is not None:
            self._notify_surface_settlement(
                superseded,
                DocumentStaleError(
                    "surface settlement waiter was superseded"
                ),
            )
        if callback is not None:
            self._notify_surface_settlement(callback, outcome)

    def _before_load(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._document_epoch = object()
            self._loaded = False
            if self._document_channel is not None and not self._owns_document_channel:
                self._document_publication_open = False
            already_attempted = self._attempted
            report_exhaustion = False
            if already_attempted:
                if self._presentation is not None:
                    _advanced, report_exhaustion = (
                        self._advance_presentation_revision_locked()
                    )
                self._publication_in_flight = None
            else:
                self._attempted = True
        if report_exhaustion:
            self._report_presentation_revision_exhausted()
        if already_attempted:
            return
        try:
            native_window = self._window.native
            if native_window.InvokeRequired:
                raise RuntimeError(
                    "appearance callback did not run on the UI thread"
                )
        except Exception as error:
            _log_failure("appearance.ui_thread_unavailable", error)
            self._settle_initial_surface(None)
            return

        with self._lock:
            if self._closed:
                return
            self._native_window = native_window
            if self._document_channel is None:
                self._document_channel = DocumentChannel(
                    native_window,
                    invoke=self._native.invoke,
                )
                self._owns_document_channel = True
            self._observation_active = True
            self._observation_token = object()
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
            self._settle_initial_surface(None)
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
            dispatch = self._advance_observation_locked()
        if dispatch is None:
            return
        native_window, generation = dispatch
        self._dispatch_observation(native_window, generation, deferred=False)

    def _on_cosmetic_changed(
        self,
        snapshot: CosmeticSectionSnapshot,
    ) -> None:
        try:
            theme_mode = _cosmetic_theme(snapshot)
        except (TypeError, ValueError) as error:
            _log_failure("appearance.cosmetic_notification_invalid", error)
            return
        with self._lock:
            if self._closed or snapshot.revision <= self._cosmetic_revision:
                return
            self._cosmetic_revision = snapshot.revision
            self._theme_mode = theme_mode
            if not self._observation_active:
                return
            dispatch = self._advance_observation_locked()
        if dispatch is None:
            return
        native_window, generation = dispatch
        self._dispatch_observation(native_window, generation, deferred=False)

    def _advance_observation_locked(self) -> tuple[object, object] | None:
        self._observation_token = object()
        if self._observation_scheduled:
            return None
        self._observation_scheduled = True
        native_window = self._native_window
        generation = self._observation_token
        if native_window is None:
            self._observation_scheduled = False
            return None
        return native_window, generation

    def _dispatch_observation(
        self,
        native_window: object,
        generation: object,
        *,
        deferred: bool,
        retry_newer: bool = True,
    ) -> None:
        with self._lock:
            if self._closed or not self._observation_active:
                self._observation_scheduled = False
                return
        try:
            dispatch = self._native.defer if deferred else self._native.invoke
            dispatch(native_window, self._drain_observation)
        except Exception as error:
            _log_failure("appearance.ui_dispatch_failed", error)
            with self._lock:
                newer = (
                    not self._closed
                    and self._observation_active
                    and generation is not self._observation_token
                )
                self._observation_scheduled = False
                if newer and retry_newer:
                    self._observation_scheduled = True
                    retry_generation = self._observation_token
                else:
                    retry_generation = None
                settle_safe = (
                    retry_generation is None
                    and self._initial_observation_pending
                )
                if settle_safe:
                    self._initial_observation_pending = False
            if retry_generation is not None:
                self._dispatch_observation(
                    native_window,
                    retry_generation,
                    deferred=deferred,
                    retry_newer=False,
                )
            elif settle_safe:
                self._settle_initial_surface(None)

    def _drain_observation(self) -> None:
        with self._lock:
            if self._closed or not self._observation_active:
                self._observation_scheduled = False
                return
            generation = self._observation_token
            cosmetic_revision = self._cosmetic_revision
            theme_mode = self._theme_mode
            initial = self._initial_observation_pending
            native_window = self._native_window
        if native_window is None:
            with self._lock:
                self._observation_scheduled = False
            if initial:
                self._settle_initial_surface(None)
            return
        surface_error: UnsafeSurfaceError | None = None
        try:
            raw_system = self._native.read()
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
            system = _effective_system_appearance(raw_system, theme_mode)
            with self._lock:
                current_cosmetic = (
                    not self._closed
                    and self._observation_active
                    and cosmetic_revision == self._cosmetic_revision
                )
            if current_cosmetic:
                surface_error = self._apply(
                    native_window,
                    system,
                    publish=False,
                    startup=initial,
                )

        if surface_error is not None:
            self._settle_initial_surface(surface_error)

        with self._lock:
            if self._closed or not self._observation_active:
                self._observation_scheduled = False
                return
            if generation is self._observation_token:
                self._observation_scheduled = False
                self._initial_observation_pending = False
                publish = self._loaded
                defer_pending = False
            else:
                publish = False
                defer_pending = True
        if publish:
            self._schedule_publish()
        if initial and not defer_pending:
            self._settle_initial_surface(surface_error)
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

    def _fail_initial_observation(self) -> None:
        with self._lock:
            if self._closed:
                self._observation_scheduled = False
                return
            self._observation_active = False
            self._observation_scheduled = False
            self._initial_observation_pending = False
            unsubscribe = self._unsubscribe
            self._unsubscribe = None
        if unsubscribe is not None:
            try:
                unsubscribe()
            except Exception as error:
                _log_failure("appearance.preference_unsubscribe_failed", error)
        self._settle_initial_surface(None)
        self._schedule_publish()

    def _apply(
        self,
        native_window: object,
        system: SystemAppearance,
        *,
        publish: bool,
        startup: bool,
    ) -> UnsafeSurfaceError | None:
        with self._lock:
            if self._closed:
                return None
        try:
            material = self._native.apply(native_window, system)
        except UnsafeSurfaceError as error:
            _log_failure("appearance.surface_rollback_unconfirmed", error)
            self._record_presentation(
                system,
                None,
                publish=publish,
                startup=startup,
            )
            return error
        except Exception as error:
            _log_failure("appearance.material_apply_failed", error)
            return self._force_opaque(
                native_window,
                system,
                publish=publish,
                startup=startup,
                unsafe_if_unconfirmed=startup,
            )
        if material not in ("mica", "opaque"):
            if material is None:
                self._record_presentation(
                    system,
                    None,
                    publish=publish,
                    startup=startup,
                )
                return None
            _log_failure(
                "appearance.material_result_invalid",
                RuntimeError("invalid material result"),
            )
            return self._force_opaque(
                native_window,
                system,
                publish=publish,
                startup=startup,
                unsafe_if_unconfirmed=startup,
            )
        self._record_presentation(
            system,
            material,
            publish=publish,
            startup=startup,
        )
        return None

    def _force_opaque(
        self,
        native_window: object,
        system: SystemAppearance,
        *,
        publish: bool,
        startup: bool,
        unsafe_if_unconfirmed: bool = False,
    ) -> UnsafeSurfaceError | None:
        with self._lock:
            if self._closed:
                return None
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
        if not confirmed and unsafe_if_unconfirmed:
            return UnsafeSurfaceError(
                "NamiSync could not confirm an opaque rollback after "
                "an indeterminate native appearance failure"
            )
        return None

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
            advanced, report_exhaustion = (
                self._advance_presentation_revision_locked()
            )
            should_publish = advanced and publish and self._loaded
        if report_exhaustion:
            self._report_presentation_revision_exhausted()
        if should_publish:
            self._schedule_publish()

    def _advance_presentation_revision_locked(self) -> tuple[bool, bool]:
        if self._presentation_revision >= MAX_JAVASCRIPT_SAFE_INTEGER:
            report = not self._presentation_revision_exhausted
            self._presentation_revision_exhausted = True
            return False, report
        self._presentation_revision += 1
        return True, False

    @staticmethod
    def _report_presentation_revision_exhausted() -> None:
        logging.getLogger("namisync").error(
            "appearance.presentation_revision_exhausted"
        )

    def _schedule_publish(self) -> None:
        with self._lock:
            generation = self._document_epoch
            if (
                self._closed
                or self._presentation_revision_exhausted
                or not self._document_publication_open
                or self._publication_in_flight is not None
                or not self._loaded
                or self._initial_observation_pending
                or self._presentation is None
                or self._presentation.material is None
            ):
                channel = None
                presentation = None
                revision = None
            else:
                channel = self._document_channel
                presentation = self._presentation
                revision = self._presentation_revision
                self._publication_in_flight = (generation, revision)
        if channel is None or presentation is None or revision is None:
            return
        system = presentation.system
        payload = {
            "kind": _APPEARANCE_MESSAGE_KIND,
            "revision": revision,
            "theme": system.theme,
            "highContrast": system.high_contrast,
            "material": presentation.material,
            "accentFill": system.accent_fill,
            "accentFillHover": system.accent_fill_hover,
            "accentFillPressed": system.accent_fill_pressed,
            "accentFillForeground": system.accent_fill_foreground,
        }

        channel.post(
            payload,
            still_current=lambda: self._publication_is_current(
                generation,
                revision,
            ),
            completion=lambda error: self._publication_finished(
                generation,
                revision,
                error,
            ),
            kind=DocumentPostKind.REPLACEABLE,
            acknowledgment=revision,
        )

    def _publication_is_current(
        self,
        generation: object,
        revision: int,
    ) -> bool:
        with self._lock:
            return (
                not self._closed
                and not self._presentation_revision_exhausted
                and self._document_publication_open
                and self._loaded
                and generation is self._document_epoch
                and revision == self._presentation_revision
                and self._publication_in_flight == (generation, revision)
            )

    def _publication_finished(
        self,
        generation: object,
        revision: int,
        error: Exception | None,
    ) -> None:
        with self._lock:
            if self._publication_in_flight != (generation, revision):
                return
            self._publication_in_flight = None
            retry_current = (
                not self._closed
                and not self._presentation_revision_exhausted
                and self._document_publication_open
                and generation is self._document_epoch
                and revision != self._presentation_revision
                and not isinstance(error, DocumentRetiredError)
            )
        if (
            error is not None
            and not retry_current
            and not isinstance(error, DocumentRetiredError)
        ):
            _log_failure("appearance.document_publish_failed", error)
        if retry_current:
            self._schedule_publish()

    def _settle_initial_surface(
        self,
        error: UnsafeSurfaceError | None,
    ) -> None:
        with self._lock:
            if self._closed or self._surface_settlement_known:
                return
            if error is not None:
                self._surface_safety_failure = error
            self._surface_settlement_known = True
            outcome = self._surface_safety_failure
            callback = self._surface_settlement_callback
            self._surface_settlement_callback = None
        if callback is not None:
            self._notify_surface_settlement(callback, outcome)

    def _notify_surface_settlement(
        self,
        callback: Callable[[Exception | None], None],
        error: Exception | None,
    ) -> None:
        try:
            callback(error)
        except Exception as callback_error:
            _log_failure(
                "appearance.surface_settlement_callback_failed",
                callback_error,
            )

    def _remove_event_handler(
        self,
        event_name: str,
        handler: Callable[[], None],
    ) -> None:
        try:
            event = getattr(self._window.events, event_name)
            event -= handler
        except Exception as error:
            _log_failure("appearance.event_unsubscribe_failed", error)


def _cosmetic_theme(snapshot: CosmeticSectionSnapshot) -> ThemeMode:
    if not isinstance(snapshot, CosmeticSectionSnapshot):
        raise TypeError("appearance snapshot has the wrong type")
    if snapshot.section != "appearance":
        raise ValueError("appearance snapshot has the wrong section")
    if snapshot.value_version != APPEARANCE_VALUE_VERSION:
        raise ValueError("appearance snapshot has the wrong value version")
    if (
        type(snapshot.revision) is not int
        or snapshot.revision < 0
        or not isinstance(snapshot.value, AppearanceValue)
    ):
        raise ValueError("appearance snapshot is invalid")
    return snapshot.value.theme


def _effective_system_appearance(
    raw_system: SystemAppearance,
    theme_mode: ThemeMode,
) -> SystemAppearance:
    """Compose a cosmetic color mode without altering Windows-owned evidence."""

    if not isinstance(theme_mode, ThemeMode):
        raise TypeError("theme mode must be a ThemeMode")
    if raw_system.high_contrast or theme_mode is ThemeMode.SYSTEM:
        return raw_system
    dark = theme_mode is ThemeMode.DARK
    return raw_system if raw_system.dark is dark else replace(raw_system, dark=dark)


def opaque_window_background(
    *,
    native: AppearanceNative | None = None,
    theme_mode: ThemeMode = ThemeMode.SYSTEM,
) -> str:
    """Return the opaque public-window background used before enhancement."""

    implementation = native or _WindowsAppearanceNative()
    try:
        raw_system = implementation.read()
        system = _effective_system_appearance(raw_system, theme_mode)
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
    native: AppearanceNative | None = None,
    cosmetics: _CosmeticAuthority | None = None,
    initial_cosmetic: CosmeticSectionSnapshot | None = None,
) -> WindowAppearanceController:
    """Register appearance after security at the same synchronous native seam."""

    controller = WindowAppearanceController(
        window,
        native or _WindowsAppearanceNative(),
        initial_cosmetic=initial_cosmetic,
    )
    if cosmetics is not None:
        controller.bind_cosmetics(cosmetics)
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
) -> _AccentPalette:
    if settings is None:
        return _AccentPalette(
            accent=_DEFAULT_ACCENT,
            light_1=_DEFAULT_ACCENT_LIGHT_1,
            light_2=_DEFAULT_ACCENT_LIGHT_2,
            dark_1=_DEFAULT_ACCENT_DARK_1,
        )
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

        palette = _AccentPalette(
            accent=read("Accent"),
            light_1=read("AccentLight1"),
            light_2=read("AccentLight2"),
            dark_1=read("AccentDark1"),
        )
        if any(
            _RGB.fullmatch(value) is None
            for value in (
                palette.accent,
                palette.light_1,
                palette.light_2,
                palette.dark_1,
            )
        ):
            raise ValueError("Windows returned an invalid accent palette")
        return palette
    except Exception as error:
        _log_failure("appearance.accent_palette_fallback", error)
        return _AccentPalette(
            accent=_DEFAULT_ACCENT,
            light_1=_DEFAULT_ACCENT_LIGHT_1,
            light_2=_DEFAULT_ACCENT_LIGHT_2,
            dark_1=_DEFAULT_ACCENT_DARK_1,
        )


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
