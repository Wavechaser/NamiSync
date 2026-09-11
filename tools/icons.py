"""Maintain committed Fluent icon assets and fixed registration, offline at runtime."""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
from urllib.request import urlopen
import xml.etree.ElementTree as ET


ASSETS = "namisync/interfaces/web/assets"
SIZES = {"sm": 16, "md": 20, "lg": 24}
REGISTRY_MARKERS = ("// BEGIN GENERATED ICON REGISTRY", "// END GENERATED ICON REGISTRY")
MASK_MARKERS = ("/* BEGIN GENERATED ICON MASKS */", "/* END GENERATED ICON MASKS */")
FILENAME = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*_(?:16|20|24)_regular\.svg")
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 256 * 1024


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _json(payload: bytes) -> dict:
    return json.loads(payload.decode("utf-8"), object_pairs_hook=_object)


def load_catalog(path: Path) -> dict:
    catalog = _json(path.read_bytes())
    _require(type(catalog) is dict and set(catalog) == {
        "schema_version", "upstream", "glyphs", "fallbacks",
    }, "Invalid catalog fields")
    _require(type(catalog["schema_version"]) is int and catalog["schema_version"] == 1,
             "Unsupported catalog schema")
    pin = catalog["upstream"]
    _require(type(pin) is dict and set(pin) == {
        "version", "git_commit", "integrity", "license_sha256",
    }, "Invalid upstream fields")
    for key, pattern in {
        "version": r"\d+\.\d+\.\d+", "git_commit": r"[0-9a-f]{40}",
        "license_sha256": r"[0-9a-f]{64}", "integrity": r"sha512-[A-Za-z0-9+/]{86}==",
    }.items():
        _require(type(pin[key]) is str and re.fullmatch(pattern, pin[key]) is not None,
                 f"Invalid upstream {key}")
    _require(base64.b64encode(base64.b64decode(pin["integrity"][7:], validate=True)).decode()
             == pin["integrity"][7:], "Noncanonical integrity")
    glyphs = catalog["glyphs"]
    _require(type(glyphs) is list and bool(glyphs), "Glyph list must be nonempty")
    _require(all(type(glyph) is str and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", glyph)
                 for glyph in glyphs), "Invalid glyph name")
    _require(len(glyphs) == len(set(glyphs)), "Duplicate glyph")
    fallbacks = catalog["fallbacks"]
    _require(type(fallbacks) is dict and set(fallbacks) <= set(glyphs), "Invalid fallback glyph")
    for glyph, sizes in fallbacks.items():
        _require(type(sizes) is dict and bool(sizes) and set(sizes) <= {"sm", "lg"},
                 f"Invalid fallback sizes: {glyph}")
        _require(all(type(value) is int and value == 20 for value in sizes.values()),
                 f"Fallback must select native 20: {glyph}")
    return catalog


def icon_mapping(catalog: dict) -> dict[str, str]:
    return {
        f"{glyph}:{size}": f"{glyph.replace('-', '_')}_{catalog['fallbacks'].get(glyph, {}).get(size, native)}_regular.svg"
        for glyph in catalog["glyphs"] for size, native in SIZES.items()
    }


def _path(root: Path, relative: str) -> Path:
    path = root / relative
    _require(path.resolve().is_relative_to(root.resolve()), f"Path leaves root: {relative}")
    current = root
    for part in Path(relative).parts:
        current = current / part
        _require(not current.is_symlink() and not current.is_junction(),
                 f"Redirected maintained path: {relative}")
    return path


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_svg(payload: bytes, filename: str) -> None:
    source = payload.decode("ascii")
    _require("<!" not in source and "<?" not in source, f"SVG declaration: {filename}")
    root = ET.fromstring(source)
    namespace = "{http://www.w3.org/2000/svg}"
    size = filename.split("_")[-2]
    _require(root.tag == namespace + "svg" and root.attrib == {
        "width": size, "height": size, "viewBox": f"0 0 {size} {size}",
    }, f"Invalid SVG canvas: {filename}")
    for element in root.iter():
        _require(element is root or element.tag == namespace + "path",
                 f"Unsafe SVG element: {filename}")
        if element.tag == namespace + "path":
            _require(set(element.attrib) <= {"d", "fill", "fill-rule", "clip-rule"},
                     f"Unsafe SVG attribute: {filename}")
            fill = element.attrib.get("fill", "black")
            _require(fill in {"none", "currentColor", "black"}
                     or re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", fill)
                     is not None,
                     f"Unexpected SVG fill: {filename}")
            _require(all(element.attrib.get(key, "nonzero") in {"nonzero", "evenodd"}
                         for key in ("fill-rule", "clip-rule")), f"Invalid SVG rule: {filename}")
            _require(re.fullmatch(r"[MmZzLlHhVvCcSsQqTtAaEe0-9.,+\s-]+", element.attrib.get("d", ""))
                     is not None, f"Invalid SVG path: {filename}")


def _replace_region(payload: bytes, markers: tuple[str, str], body: str) -> bytes:
    begin, end = (marker.encode("ascii") for marker in markers)
    _require(payload.count(begin) == payload.count(end) == 1, "Missing/duplicate generated markers")
    start, finish = payload.index(begin), payload.index(end)
    _require(start < finish, "Reversed generated markers")
    return payload[:start] + begin + b"\n" + body.encode("utf-8") + end + payload[finish + len(end):]


def plan_outputs(root: Path, catalog: dict, archive_bytes: bytes) -> dict[str, bytes]:
    """Validate the complete input before returning the proposed file bytes."""
    _require(len(archive_bytes) <= MAX_ARCHIVE_BYTES, "Archive exceeds 64 MiB limit")
    pin = catalog["upstream"]
    actual = "sha512-" + base64.b64encode(hashlib.sha512(archive_bytes).digest()).decode()
    _require(actual == pin["integrity"], "Archive integrity mismatch")
    mapping = icon_mapping(catalog)
    required = set(mapping.values())
    native_paths = {
        f"{glyph.replace('-', '_')}_{native}_regular.svg"
        for glyph in catalog["glyphs"] for native in SIZES.values()
    }
    members = {}
    package_metadata = None
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
        for member in archive:
            if member.name == "package/package.json":
                _require(package_metadata is None, "Duplicate archive package metadata")
                _require(member.isfile(), "Nonregular archive package metadata")
                _require(member.size <= MAX_MEMBER_BYTES, "Package metadata exceeds 256 KiB limit")
                package_metadata = _json(archive.extractfile(member).read())
                _require(type(package_metadata) is dict, "Invalid archive package metadata")
                continue
            name = member.name.removeprefix("package/icons/")
            if member.name != "package/icons/" + name or name not in native_paths:
                continue
            _require(name not in members, f"Duplicate archive entry: {name}")
            _require(member.isfile(), f"Nonregular archive entry: {name}")
            _require(member.size <= MAX_MEMBER_BYTES, f"SVG exceeds 256 KiB limit: {name}")
            members[name] = archive.extractfile(member).read()
    _require(package_metadata is not None
             and package_metadata.get("name") == "@fluentui/svg-icons"
             and package_metadata.get("version") == pin["version"]
             and package_metadata.get("gitHead", pin["git_commit"]) == pin["git_commit"],
             "Archive package identity does not match pin")
    for glyph in catalog["glyphs"]:
        for size, native in SIZES.items():
            name = f"{glyph.replace('-', '_')}_{native}_regular.svg"
            fallback = size in catalog["fallbacks"].get(glyph, {})
            _require((name not in members) == fallback, f"Missing or stale fallback: {glyph}:{size}")
    _require(required <= members.keys(), "Missing selected native SVG")
    outputs = {}
    records = {}
    for filename in sorted(required):
        upstream = members[filename]
        _safe_svg(upstream, filename)
        normalized = upstream.rstrip(b"\r\n") + b"\n"
        outputs[f"{ASSETS}/icons/{filename}"] = normalized
        records[filename] = {
            "source_url": f"https://unpkg.com/@fluentui/svg-icons@{pin['version']}/icons/{filename}",
            "upstream_sha256": _sha(upstream), "packaged_sha256": _sha(normalized),
        }
    license_path = f"{ASSETS}/icons/LICENSE.txt"
    license_bytes = _path(root, license_path).read_bytes()
    _require(_sha(license_bytes) == pin["license_sha256"], "License hash mismatch; restore pinned LICENSE.txt")
    outputs[license_path] = license_bytes
    receipt = {
        "schema_version": 1, "package": "@fluentui/svg-icons", "version": pin["version"],
        "git_commit": pin["git_commit"],
        "package_url": f"https://www.npmjs.com/package/@fluentui/svg-icons/v/{pin['version']}",
        "package_tarball_url": archive_url(catalog), "package_integrity": pin["integrity"],
        "license": "MIT",
        "license_source_url": f"https://raw.githubusercontent.com/microsoft/fluentui-system-icons/{pin['git_commit']}/LICENSE",
        "license_sha256": pin["license_sha256"],
        "normalization": "Published ASCII SVG bytes have trailing CR/LF bytes removed and one LF appended in the wheel.",
        "files": records,
    }
    outputs[f"{ASSETS}/icons/SOURCE.json"] = (json.dumps(receipt, indent=2) + "\n").encode("utf-8")
    registry = "const GLYPH_CLASSES = Object.freeze({\n" + "".join(
        f'  "{glyph}": "nami-icon--{glyph}",\n' for glyph in catalog["glyphs"]
    ) + "});\n"
    masks = "".join(
        f".nami-icon--{glyph} {{\n" + "".join(
            f'  --nami-icon-mask-{size}: url("./icons/{mapping[f"{glyph}:{size}"]}");\n'
            for size in SIZES
        ) + "}\n\n" for glyph in catalog["glyphs"]
    )
    for filename, markers, body in (("icons.js", REGISTRY_MARKERS, registry),
                                    ("components.css", MASK_MARKERS, masks)):
        relative = f"{ASSETS}/{filename}"
        outputs[relative] = _replace_region(_path(root, relative).read_bytes(), markers, body)
    return outputs


def archive_url(catalog: dict) -> str:
    return f"https://registry.npmjs.org/@fluentui/svg-icons/-/svg-icons-{catalog['upstream']['version']}.tgz"


def _removals(root: Path, outputs: dict[str, bytes]) -> list[Path]:
    directory = _path(root, f"{ASSETS}/icons")
    receipt_path = _path(root, f"{ASSETS}/icons/SOURCE.json")
    previous_receipt = _json(receipt_path.read_bytes())
    _require(type(previous_receipt) is dict, "Invalid previous icon receipt")
    previous = previous_receipt["files"]
    _require(type(previous) is dict, "Invalid previous icon receipt")
    for name, record in previous.items():
        _require(FILENAME.fullmatch(name) is not None, "Invalid previous receipt filename")
        _require(type(record) is dict and type(record.get("packaged_sha256")) is str
                 and re.fullmatch(r"[0-9a-f]{64}", record["packaged_sha256"]) is not None,
                 f"Invalid previous receipt hash: {name}")
    expected = {Path(name).name for name in outputs if name.startswith(f"{ASSETS}/icons/")}
    allowed = {"LICENSE.txt", "SOURCE.json"} | previous.keys()
    _require({path.name for path in directory.iterdir()} <= allowed, "Unrelated file in icon directory")
    removals = []
    for name, record in previous.items():
        if name in expected:
            continue
        path = _path(root, f"{ASSETS}/icons/{name}")
        if path.exists():
            _require(path.is_file() and _sha(path.read_bytes()) == record["packaged_sha256"],
                     f"Refusing removal of locally modified icon: {name}")
            removals.append(path)
    return removals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("sync", "check"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archive", type=Path, help="Pinned npm tarball for offline use")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve(strict=True)
        catalog = load_catalog(_path(root, "tools/icons.json"))
        if args.archive is None:
            with urlopen(archive_url(catalog), timeout=30) as response:
                archive_bytes = response.read(MAX_ARCHIVE_BYTES + 1)
        else:
            with args.archive.open("rb") as archive:
                archive_bytes = archive.read(MAX_ARCHIVE_BYTES + 1)
        outputs = plan_outputs(root, catalog, archive_bytes)
        removals = _removals(root, outputs)
        changed = [(_path(root, name), payload) for name, payload in outputs.items()
                   if not _path(root, name).exists() or _path(root, name).read_bytes() != payload]
        if args.command == "check":
            for path in [item[0] for item in changed] + removals:
                print(f"Drift: {path.relative_to(root)}")
            return int(bool(changed or removals))
        for path, payload in changed:
            path.write_bytes(payload)
        for path in removals:
            path.unlink()
        print(f"Icons synchronized: {len(changed)} changed, {len(removals)} removed")
        return 0
    except (ValueError, OSError, KeyError, tarfile.TarError, ET.ParseError) as error:
        print(f"Icon maintenance refused: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
