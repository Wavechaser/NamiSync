"""Side-effect-free mirror of pywebview's WinForms runtime detector."""

from __future__ import annotations

import winreg
from dataclasses import dataclass
from enum import StrEnum
from platform import machine
from typing import Mapping


WEBVIEW2_CLIENTS = (
    "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",  # stable runtime
    "{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}",  # beta
    "{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}",  # dev
    "{65C35B14-6C1D-4122-AC46-7148CC9D6497}",  # canary
)
# This is the exact argument used by pywebview 6.2.1's WinForms detector.
MINIMUM_WEBVIEW2_VERSION = "86.0.622.0"
DOTNET_RELEASE_REGISTRY_PATH = (
    r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full"
)
MINIMUM_DOTNET_RELEASE = 394802


class WebView2RefusalReason(StrEnum):
    """Actionable reason the pinned Chromium detector cannot be approved."""

    DOTNET_FRAMEWORK = "dotnet-framework"
    WEBVIEW2_RUNTIME = "webview2-runtime"
    DETECTION_FAILED = "detection-failed"


@dataclass(frozen=True, slots=True)
class WebView2RuntimeProbe:
    """One side-effect-free snapshot of WebView2 runtime availability."""

    available: bool
    refusal_reason: WebView2RefusalReason | None


def probe_webview2_runtime(
    settings: Mapping[str, object],
    *,
    architecture: str | None = None,
) -> WebView2RuntimeProbe:
    """Mirror pywebview 6.2.1's detector without importing its backend.

    Importing ``webview.platforms.winforms`` would itself select a renderer and
    can import the registry-writing MSHTML fallback. The compatibility tests
    execute the pinned upstream functions directly so detector drift fails CI.

    The availability decision mirrors every reachable registry state on the
    supported platform. It deliberately refuses cleanly when upstream crashes
    because the .NET release key is absent, and it also retains enough failure
    context to distinguish a missing prerequisite from an unreadable or
    malformed registry value without probing the registry a second time.
    """

    if settings["WEBVIEW2_RUNTIME_PATH"]:
        return WebView2RuntimeProbe(available=True, refusal_reason=None)
    dotnet_refusal = _dotnet_refusal_reason()
    if dotnet_refusal is not None:
        return WebView2RuntimeProbe(
            available=False,
            refusal_reason=dotnet_refusal,
        )

    selected_architecture = machine() if architecture is None else architecture
    detection_failed = False
    for client in WEBVIEW2_CLIENTS:
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            path = _client_path(hive, client, selected_architecture)
            try:
                with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as key:
                    version, _ = winreg.QueryValueEx(key, "pv")
            except FileNotFoundError:
                continue
            except Exception:
                detection_failed = True
                continue
            try:
                if _is_supported_webview2_version(version):
                    return WebView2RuntimeProbe(
                        available=True,
                        refusal_reason=None,
                    )
            except (TypeError, ValueError):
                return WebView2RuntimeProbe(
                    available=False,
                    refusal_reason=WebView2RefusalReason.DETECTION_FAILED,
                )
    refusal_reason = (
        WebView2RefusalReason.DETECTION_FAILED
        if detection_failed
        else WebView2RefusalReason.WEBVIEW2_RUNTIME
    )
    return WebView2RuntimeProbe(
        available=False,
        refusal_reason=refusal_reason,
    )


def is_supported_webview2_version(value: object) -> bool:
    """Apply the pinned pywebview backend's version-helper behavior exactly."""

    try:
        return _is_supported_webview2_version(value)
    except (TypeError, ValueError):
        return False


def _is_supported_webview2_version(value: object) -> bool:
    minimum = MINIMUM_WEBVIEW2_VERSION.split(".")
    candidate = str(value).split(".")
    for index, _ in enumerate(minimum):
        if len(candidate) > index:
            return int(candidate[index]) >= int(minimum[index])
    return False


def _dotnet_refusal_reason() -> WebView2RefusalReason | None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            DOTNET_RELEASE_REGISTRY_PATH,
            0,
            winreg.KEY_READ,
        ) as key:
            release, _ = winreg.QueryValueEx(key, "Release")
    except FileNotFoundError:
        return WebView2RefusalReason.DOTNET_FRAMEWORK
    except Exception:
        return WebView2RefusalReason.DETECTION_FAILED
    try:
        if release < MINIMUM_DOTNET_RELEASE:
            return WebView2RefusalReason.DOTNET_FRAMEWORK
    except Exception:
        return WebView2RefusalReason.DETECTION_FAILED
    return None


def _client_path(hive: object, client: str, architecture: str) -> str:
    machine_prefix = (
        ""
        if architecture == "x86" or hive == winreg.HKEY_CURRENT_USER
        else "WOW6432Node\\"
    )
    return f"SOFTWARE\\{machine_prefix}Microsoft\\EdgeUpdate\\Clients\\{client}"
