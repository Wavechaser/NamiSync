"""Side-effect-free mirror of pywebview's WinForms runtime detector."""

from __future__ import annotations

import winreg
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


def has_webview2_runtime(
    settings: Mapping[str, object],
    *,
    architecture: str | None = None,
) -> bool:
    """Mirror pywebview 6.2.1's detector without importing its backend.

    Importing ``webview.platforms.winforms`` would itself select a renderer and
    can import the registry-writing MSHTML fallback. The compatibility tests
    execute the pinned upstream functions directly so detector drift fails CI.

    The mirror is exact for every reachable registry state on the supported
    platform except one, where it deliberately diverges: when the .NET release
    key is entirely absent, upstream ``_is_chromium`` raises ``UnboundLocalError``
    from its ``finally`` because ``net_key`` was never bound, while this
    function refuses cleanly. Windows 11 ships .NET Framework 4.8 in-box, so
    that state is not reachable on a supported installation;
    ``missing_dotnet_framework`` exists so a refusal can still name the real
    prerequisite rather than blaming WebView2.
    """

    if settings["WEBVIEW2_RUNTIME_PATH"]:
        return True
    if not _has_required_dotnet():
        return False

    selected_architecture = machine() if architecture is None else architecture
    for client in WEBVIEW2_CLIENTS:
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            path = _client_path(hive, client, selected_architecture)
            try:
                with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as key:
                    version, _ = winreg.QueryValueEx(key, "pv")
            except Exception:
                continue
            try:
                if _is_supported_webview2_version(version):
                    return True
            except (TypeError, ValueError):
                return False
    return False


def missing_dotnet_framework() -> bool:
    """Report the prerequisite gap that a WebView2 refusal would misattribute."""

    return not _has_required_dotnet()


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


def _has_required_dotnet() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            DOTNET_RELEASE_REGISTRY_PATH,
            0,
            winreg.KEY_READ,
        ) as key:
            release, _ = winreg.QueryValueEx(key, "Release")
        return int(release) >= MINIMUM_DOTNET_RELEASE
    except Exception:
        return False


def _client_path(hive: object, client: str, architecture: str) -> str:
    machine_prefix = (
        ""
        if architecture == "x86" or hive == winreg.HKEY_CURRENT_USER
        else "WOW6432Node\\"
    )
    return f"SOFTWARE\\{machine_prefix}Microsoft\\EdgeUpdate\\Clients\\{client}"
