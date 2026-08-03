from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
import webview

import namisync.interfaces.web.pywebview_runtime as runtime


class RegistryKey:
    def __init__(self, hive: object, path: str) -> None:
        self.hive = hive
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        del args


class FakeRegistry:
    HKEY_CURRENT_USER = object()
    HKEY_LOCAL_MACHINE = object()
    KEY_READ = 0x20019

    def __init__(self, values: dict[tuple[object, str, str], object]) -> None:
        self.values = values
        self.opens: list[tuple[object, str, int, int | None]] = []

    def OpenKey(
        self,
        hive: object,
        path: str,
        reserved: int = 0,
        access: int | None = None,
    ) -> RegistryKey:
        self.opens.append((hive, path, reserved, access))
        if not any(key[:2] == (hive, path) for key in self.values):
            raise FileNotFoundError(path)
        return RegistryKey(hive, path)

    def QueryValueEx(self, key: RegistryKey, name: str):
        try:
            return self.values[(key.hive, key.path, name)], 1
        except KeyError as error:
            raise FileNotFoundError(name) from error

    def CloseKey(self, key: RegistryKey) -> None:
        del key


def _upstream_detector(fake: FakeRegistry, *, architecture: str, fixed=None):
    source_path = Path(webview.__file__).parent / "platforms" / "winforms.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"_is_new_version", "_is_chromium"}
    ]
    assert [node.name for node in functions] == [
        "_is_new_version",
        "_is_chromium",
    ]
    namespace = {
        "logger": SimpleNamespace(exception=lambda error: None),
        "machine": lambda: architecture,
        "settings": {"WEBVIEW2_RUNTIME_PATH": fixed},
        "winreg": fake,
    }
    exec(
        compile(ast.Module(body=functions, type_ignores=[]), source_path, "exec"),
        namespace,
    )
    return namespace["_is_chromium"]()


def _values(
    fake: FakeRegistry,
    *,
    client: str,
    version: str,
    hive: object | None = None,
    machine_path: str | None = None,
) -> dict[tuple[object, str, str], object]:
    selected_hive = fake.HKEY_CURRENT_USER if hive is None else hive
    path = machine_path or f"SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\{client}"
    return {
        (
            fake.HKEY_LOCAL_MACHINE,
            runtime.DOTNET_RELEASE_REGISTRY_PATH,
            "Release",
        ): runtime.MINIMUM_DOTNET_RELEASE,
        (selected_hive, path, "pv"): version,
    }


@pytest.mark.parametrize(
    ("architecture", "channel_index", "hive_name"),
    [
        ("AMD64", 0, "user"),
        ("AMD64", 1, "machine"),
        ("AMD64", 2, "user"),
        ("AMD64", 3, "machine"),
        ("x86", 0, "machine"),
    ],
)
def test_side_effect_free_detector_matches_pinned_pywebview_registry_choices(
    monkeypatch: pytest.MonkeyPatch,
    architecture: str,
    channel_index: int,
    hive_name: str,
) -> None:
    fake = FakeRegistry({})
    client = runtime.WEBVIEW2_CLIENTS[channel_index]
    hive = (
        fake.HKEY_CURRENT_USER
        if hive_name == "user"
        else fake.HKEY_LOCAL_MACHINE
    )
    machine_path = None
    if hive_name == "machine":
        prefix = "" if architecture == "x86" else "WOW6432Node\\"
        machine_path = f"SOFTWARE\\{prefix}Microsoft\\EdgeUpdate\\Clients\\{client}"
    fake.values = _values(
        fake,
        client=client,
        version="150.0.4078.105",
        hive=hive,
        machine_path=machine_path,
    )
    monkeypatch.setattr(runtime, "winreg", fake)

    ours = runtime.has_webview2_runtime(
        {"WEBVIEW2_RUNTIME_PATH": None}, architecture=architecture
    )
    upstream = _upstream_detector(fake, architecture=architecture)

    assert ours
    assert ours is upstream
    assert all(access in {None, fake.KEY_READ} for *_, access in fake.opens)


def test_detector_matches_fixed_runtime_and_missing_dotnet_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeRegistry(
        {
            (
                FakeRegistry.HKEY_LOCAL_MACHINE,
                runtime.DOTNET_RELEASE_REGISTRY_PATH,
                "Release",
            ): runtime.MINIMUM_DOTNET_RELEASE - 1,
        }
    )
    monkeypatch.setattr(runtime, "winreg", fake)

    assert runtime.has_webview2_runtime(
        {"WEBVIEW2_RUNTIME_PATH": r"runtime\\WebView2"}, architecture="AMD64"
    )
    assert _upstream_detector(
        fake, architecture="AMD64", fixed=r"runtime\\WebView2"
    )
    assert not runtime.has_webview2_runtime(
        {"WEBVIEW2_RUNTIME_PATH": None}, architecture="AMD64"
    )
    assert not _upstream_detector(fake, architecture="AMD64")


def test_absent_dotnet_key_is_the_one_deliberate_upstream_divergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Upstream crashes where the mirror refuses; pin that we diverge on purpose.

    ``_is_chromium`` closes ``net_key`` in a ``finally`` that also runs when the
    opening ``OpenKey`` raised, so an absent .NET release key raises
    ``UnboundLocalError`` out of pywebview instead of returning False. Windows 11
    ships .NET Framework 4.8 in-box, so this state is unreachable on a supported
    installation, but the mirror must still refuse cleanly and name the real
    prerequisite.
    """

    fake = FakeRegistry({})
    monkeypatch.setattr(runtime, "winreg", fake)

    assert not runtime.has_webview2_runtime(
        {"WEBVIEW2_RUNTIME_PATH": None}, architecture="AMD64"
    )
    assert runtime.missing_dotnet_framework()
    with pytest.raises(UnboundLocalError):
        _upstream_detector(fake, architecture="AMD64")


def test_present_dotnet_key_does_not_report_a_prerequisite_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeRegistry(
        {
            (
                FakeRegistry.HKEY_LOCAL_MACHINE,
                runtime.DOTNET_RELEASE_REGISTRY_PATH,
                "Release",
            ): runtime.MINIMUM_DOTNET_RELEASE,
        }
    )
    monkeypatch.setattr(runtime, "winreg", fake)

    assert not runtime.missing_dotnet_framework()
    assert not runtime.has_webview2_runtime(
        {"WEBVIEW2_RUNTIME_PATH": None}, architecture="AMD64"
    )
    assert not _upstream_detector(fake, architecture="AMD64")


def test_malformed_earlier_channel_aborts_like_the_upstream_detector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeRegistry({})
    stable, beta, *_ = runtime.WEBVIEW2_CLIENTS
    fake.values = {
        (
            fake.HKEY_LOCAL_MACHINE,
            runtime.DOTNET_RELEASE_REGISTRY_PATH,
            "Release",
        ): runtime.MINIMUM_DOTNET_RELEASE,
        (
            fake.HKEY_CURRENT_USER,
            f"SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\{stable}",
            "pv",
        ): "not-a-version",
        (
            fake.HKEY_CURRENT_USER,
            f"SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\{beta}",
            "pv",
        ): "150.0.4078.105",
    }
    monkeypatch.setattr(runtime, "winreg", fake)

    ours = runtime.has_webview2_runtime(
        {"WEBVIEW2_RUNTIME_PATH": None}, architecture="AMD64"
    )
    upstream = _upstream_detector(fake, architecture="AMD64")

    assert not ours
    assert ours is upstream


@pytest.mark.parametrize(
    ("version", "supported"),
    [
        ("85.0.9999.999", False),
        ("86.0.621.999", True),
        ("86.0.622", True),
        ("150.0.4078.105", True),
        ("not-a-version", False),
        (None, False),
    ],
)
def test_webview2_runtime_version_helper(version: object, supported: bool) -> None:
    assert runtime.is_supported_webview2_version(version) is supported


@pytest.mark.parametrize(
    "version",
    ["85.0.9999.999", "86.0.621.999", "86.0.622.0", "150.0.4078.105"],
)
def test_version_gate_matches_pinned_pywebview_helper(
    monkeypatch: pytest.MonkeyPatch,
    version: str,
) -> None:
    fake = FakeRegistry({})
    fake.values = _values(
        fake,
        client=runtime.WEBVIEW2_CLIENTS[0],
        version=version,
    )
    monkeypatch.setattr(runtime, "winreg", fake)

    ours = runtime.has_webview2_runtime(
        {"WEBVIEW2_RUNTIME_PATH": None}, architecture="AMD64"
    )
    upstream = _upstream_detector(fake, architecture="AMD64")

    assert ours is upstream
