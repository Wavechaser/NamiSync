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

from _frontend_test_support import (
    ASSET_ROOT, ICON_CATALOG, ICON_CATALOG_PATH, ICON_FILES, ICON_GLYPHS,
    ICON_MASK_FILES, _node_executable,
)


PROJECT_ROOT = Path(__file__).parents[3]
ASSETS = PROJECT_ROOT / "namisync" / "interfaces" / "web" / "assets"
ICON_ROOT = ASSETS / "icons"
ICON_DIRECTORY_FILES = {*ICON_FILES, "LICENSE.txt", "SOURCE.json"}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@pytest.mark.supplemental_node
def test_supplemental_node_icon_registry_rejects_unknown_authority() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the supplemental icon probe")

    completed = subprocess.run(
        [
            node,
            PROJECT_ROOT / "tests" / "assets" / "icon_registry_probe.mjs",
            ASSETS / "icons.js",
            ICON_CATALOG_PATH,
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert completed.returncode == 0, completed.stderr


def test_sh_g_14_receipt_matches_catalog_and_packaged_bytes() -> None:
    assert {path.name for path in ICON_ROOT.iterdir()} == ICON_DIRECTORY_FILES
    provenance = json.loads((ICON_ROOT / "SOURCE.json").read_text(encoding="utf-8"))
    upstream = ICON_CATALOG["upstream"]
    version = upstream["version"]

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
    assert provenance["version"] == version
    assert provenance["git_commit"] == upstream["git_commit"]
    assert provenance["package_url"] == (
        f"https://www.npmjs.com/package/@fluentui/svg-icons/v/{version}"
    )
    assert provenance["package_tarball_url"] == (
        f"https://registry.npmjs.org/@fluentui/svg-icons/-/svg-icons-{version}.tgz"
    )
    assert provenance["package_integrity"] == upstream["integrity"]
    assert provenance["license"] == "MIT"
    assert provenance["license_source_url"] == (
        "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/"
        f"{upstream['git_commit']}/LICENSE"
    )
    assert provenance["license_sha256"] == upstream["license_sha256"] == _sha256(
        (ICON_ROOT / "LICENSE.txt").read_bytes()
    )
    assert provenance["normalization"] == (
        "Published ASCII SVG bytes have trailing CR/LF bytes removed and one LF "
        "appended in the wheel."
    )
    assert set(provenance["files"]) == set(ICON_FILES)

    for filename in ICON_FILES:
        payload = (ICON_ROOT / filename).read_bytes()
        record = provenance["files"][filename]
        assert set(record) == {"source_url", "upstream_sha256", "packaged_sha256"}
        assert record["source_url"] == (
            f"https://unpkg.com/@fluentui/svg-icons@{version}/icons/{filename}"
        )
        # Upstream bytes may have different terminal newlines; icons.py check
        # authenticates these against the archive, not reconstructed file bytes.
        assert re.fullmatch(r"[0-9a-f]{64}", record["upstream_sha256"])
        assert record["packaged_sha256"] == _sha256(payload)
        assert payload.endswith(b"\n")
        assert not payload.endswith(b"\n\n")


def test_sh_g_14_svg_assets_are_static_local_and_non_executable() -> None:
    svg_namespace = "http://www.w3.org/2000/svg"
    allowed_tags = {f"{{{svg_namespace}}}svg", f"{{{svg_namespace}}}path"}

    for filename in ICON_FILES:
        payload = (ICON_ROOT / filename).read_bytes()
        root = ET.fromstring(payload)
        assert root.tag == f"{{{svg_namespace}}}svg"
        size = filename.split("_")[-2]
        assert root.attrib == {
            "width": size,
            "height": size,
            "viewBox": f"0 0 {size} {size}",
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
    assert set(ICON_MASK_FILES.values()) == set(ICON_FILES)
    assert components.count('url("./icons/') == len(ICON_MASK_FILES)
    for key, filename in ICON_MASK_FILES.items():
        glyph, size = key.split(":")
        block = re.search(rf"\.nami-icon--{glyph} \{{([^}}]+)\}}", components)
        assert block is not None
        assert f'--nami-icon-mask-{size}: url("./icons/{filename}");' in block[1]
    for size in ("sm", "md", "lg"):
        assert f"--nami-icon-mask: var(--nami-icon-mask-{size});" in components
    assert re.findall(r'  "([a-z0-9-]+)": "nami-icon--[a-z0-9-]+",', registry.split("const SIZE_CLASSES")[0]) == list(ICON_GLYPHS)
    assert '[aria-disabled="true"] .nami-icon' in components

    assert "http://" not in registry
    assert "https://" not in registry
    assert "<svg" not in registry.casefold()
    assert ".svg" not in registry.casefold()
    assert "innerHTML" not in registry
    assert "insertAdjacentHTML" not in registry
    assert "DOMParser" not in registry
    assert "url(" not in registry
    assert "Object.prototype.hasOwnProperty.call" in registry
    assert "Object.hasOwn(" not in registry


def test_sh_g_14_built_wheel_contains_exact_icon_foundation(
    built_wheel: BuiltWheel,
) -> None:
    expected = {
        f"icons/{filename}": (ICON_ROOT / filename).read_bytes()
        for filename in ICON_DIRECTORY_FILES
    }
    expected["icons.js"] = (ASSETS / "icons.js").read_bytes()

    with zipfile.ZipFile(built_wheel.path) as wheel:
        assert "tools/icons.py" not in wheel.namelist()
        assert "tools/icons.json" not in wheel.namelist()
        packaged = {
            name.removeprefix(ASSET_ROOT): wheel.read(name)
            for name in wheel.namelist()
            if name.startswith(f"{ASSET_ROOT}icons") and not name.endswith("/")
        }

    assert packaged == expected
