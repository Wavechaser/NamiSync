"""Fixed Fluent icon registry, provenance, safety, and package evidence."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from conftest import BuiltWheel

from test_transport import _node_executable
from test_wheel_assets import ASSET_ROOT


PROJECT_ROOT = Path(__file__).parents[3]
ASSETS = PROJECT_ROOT / "namisync" / "interfaces" / "web" / "assets"
ICON_ROOT = ASSETS / "icons"
ICON_FILES = (
    "checkmark_circle_20_regular.svg",
    "dismiss_circle_20_regular.svg",
    "warning_20_regular.svg",
    "info_20_regular.svg",
)
ICON_DIRECTORY_FILES = {*ICON_FILES, "LICENSE.txt", "SOURCE.json"}
UPSTREAM_HASHES = {
    "checkmark_circle_20_regular.svg": (
        "d63cfc815002a8f665bb3ab56aa92f59b578ea64e842fa36b0398296f2d4feea"
    ),
    "dismiss_circle_20_regular.svg": (
        "83398a47666a71bf096691167dd627c21d950a4efb4760d1c3a111aab3d44ca6"
    ),
    "warning_20_regular.svg": (
        "3c00472172d82455b32c8b177fe8e1cf8ba794ac7e7a1b95e42116725354e574"
    ),
    "info_20_regular.svg": (
        "7d7665044432502f39e25427858d7d2ff60a3d993ccb526750c1e9c09d848e01"
    ),
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def test_sh_g_14_registry_is_fixed_and_rejects_unregistered_authority() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the no-dependency icon probe")

    completed = subprocess.run(
        [
            node,
            PROJECT_ROOT / "tests" / "assets" / "icon_registry_probe.mjs",
            ASSETS / "icons.js",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert completed.returncode == 0, completed.stderr


def test_sh_g_14_fluent_sources_have_exact_pinned_provenance() -> None:
    assert {path.name for path in ICON_ROOT.iterdir()} == ICON_DIRECTORY_FILES
    provenance = json.loads((ICON_ROOT / "SOURCE.json").read_text(encoding="utf-8"))

    assert set(provenance) == {
        "schema_version",
        "package",
        "version",
        "git_commit",
        "package_url",
        "package_tarball_url",
        "package_integrity",
        "license",
        "license_source_url",
        "license_sha256",
        "normalization",
        "files",
    }
    assert provenance["schema_version"] == 1
    assert provenance["package"] == "@fluentui/svg-icons"
    assert provenance["version"] == "1.1.334"
    assert provenance["git_commit"] == (
        "d7e5f224125e5638df10610d7c2755d709113e55"
    )
    assert provenance["package_url"] == (
        "https://www.npmjs.com/package/@fluentui/svg-icons/v/1.1.334"
    )
    assert provenance["package_tarball_url"] == (
        "https://registry.npmjs.org/@fluentui/svg-icons/-/svg-icons-1.1.334.tgz"
    )
    assert provenance["package_integrity"] == (
        "sha512-VeKTChgi+iyMj4ecbuKRTGlzzTf6x5v5mD25l8+4DVf7f85dydrmEsWmVITRaoKWxGPMDZsiXqWUSCcXPukvEw=="
    )
    assert provenance["license"] == "MIT"
    assert provenance["license_source_url"] == (
        "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/"
        "d7e5f224125e5638df10610d7c2755d709113e55/LICENSE"
    )
    assert provenance["license_sha256"] == _sha256(
        (ICON_ROOT / "LICENSE.txt").read_bytes()
    )
    assert provenance["normalization"] == (
        "The published ASCII SVG bytes are retained with one trailing LF in the "
        "wheel."
    )
    assert set(provenance["files"]) == set(ICON_FILES)

    for filename in ICON_FILES:
        payload = (ICON_ROOT / filename).read_bytes()
        record = provenance["files"][filename]
        assert record == {
            "source_url": (
                "https://unpkg.com/@fluentui/svg-icons@1.1.334/icons/"
                f"{filename}"
            ),
            "upstream_sha256": UPSTREAM_HASHES[filename],
            "packaged_sha256": _sha256(payload),
        }
        assert payload.endswith(b"\n")
        assert _sha256(payload.removesuffix(b"\n")) == UPSTREAM_HASHES[filename]


def test_sh_g_14_svg_assets_are_static_local_and_non_executable() -> None:
    svg_namespace = "http://www.w3.org/2000/svg"
    allowed_tags = {f"{{{svg_namespace}}}svg", f"{{{svg_namespace}}}path"}

    for filename in ICON_FILES:
        payload = (ICON_ROOT / filename).read_bytes()
        root = ET.fromstring(payload)
        assert root.tag == f"{{{svg_namespace}}}svg"
        assert root.attrib == {
            "width": "20",
            "height": "20",
            "viewBox": "0 0 20 20",
        }
        assert {element.tag for element in root.iter()} <= allowed_tags
        for element in root.iter():
            assert all(not name.casefold().startswith("on") for name in element.attrib)
            assert all("href" not in name.casefold() for name in element.attrib)
            assert all("url(" not in value.casefold() for value in element.attrib.values())
        source = payload.decode("ascii")
        assert "<!doctype" not in source.casefold()
        assert "<?xml-stylesheet" not in source.casefold()
        assert "<script" not in source.casefold()
        assert "foreignObject" not in source
        assert "http://www.w3.org/2000/svg" in source
        assert "http://" not in source.replace("http://www.w3.org/2000/svg", "")
        assert "https://" not in source


def test_sh_g_14_tokens_and_components_own_size_color_and_fixed_masks() -> None:
    tokens = (ASSETS / "tokens.css").read_text(encoding="utf-8")
    components = (ASSETS / "components.css").read_text(encoding="utf-8")
    registry = (ASSETS / "icons.js").read_text(encoding="utf-8")

    assert re.findall(r"--icon-size-(sm|md|lg):\s*([^;]+);", tokens) == [
        ("sm", "16px"),
        ("md", "20px"),
        ("lg", "24px"),
    ]
    assert "background-color: currentColor;" in components
    assert "mask-image: var(--nami-icon-mask);" in components
    assert "-webkit-mask-image: var(--nami-icon-mask);" in components
    assert components.count('url("./icons/') == 4
    for filename in ICON_FILES:
        assert components.count(f'url("./icons/{filename}")') == 1
    assert '[aria-disabled="true"] .nami-icon' in components

    assert "http://" not in registry
    assert "https://" not in registry
    assert "<svg" not in registry.casefold()
    assert ".svg" not in registry.casefold()
    assert "innerHTML" not in registry
    assert "insertAdjacentHTML" not in registry
    assert "DOMParser" not in registry
    assert "url(" not in registry
    assert "Object.hasOwn" in registry


def test_sh_g_14_built_wheel_contains_exact_icon_foundation(
    built_wheel: BuiltWheel,
) -> None:
    expected = {
        f"icons/{filename}": (ICON_ROOT / filename).read_bytes()
        for filename in ICON_DIRECTORY_FILES
    }
    expected["icons.js"] = (ASSETS / "icons.js").read_bytes()

    with zipfile.ZipFile(built_wheel.path) as wheel:
        packaged = {
            name.removeprefix(ASSET_ROOT): wheel.read(name)
            for name in wheel.namelist()
            if name.startswith(f"{ASSET_ROOT}icons") and not name.endswith("/")
        }

    assert packaged == expected
