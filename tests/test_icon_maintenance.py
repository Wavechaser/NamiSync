from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile

import pytest

from tools import icons


ASSETS = Path("namisync/interfaces/web/assets")
LICENSE = b"MIT license fixture\n"


def _svg(size: int) -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" '
        f'height="{size}" viewBox="0 0 {size} {size}">'
        '<path d="M1 1H8V8H1Z" fill="#242424"/></svg>'
    ).encode("ascii")


def _archive(members: list[tuple[str, bytes, bytes]], metadata: dict | None = None) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        package = json.dumps(metadata or {"name": "@fluentui/svg-icons", "version": "1.1.334", "gitHead": "a" * 40}).encode()
        for name, data, kind in [("package/package.json", package, tarfile.REGTYPE), *members]:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.size = len(data) if kind == tarfile.REGTYPE else 0
            member.linkname = "../../outside.svg" if kind == tarfile.SYMTYPE else ""
            archive.addfile(member, io.BytesIO(data) if member.size else None)
    return stream.getvalue()


def _members(glyph: str = "add") -> list[tuple[str, bytes, bytes]]:
    return [
        (f"package/icons/{glyph}_{size}_regular.svg", _svg(size), tarfile.REGTYPE)
        for size in (16, 20, 24)
    ]


def _catalog(archive: bytes, glyphs: list[str] | None = None) -> dict:
    return {
        "schema_version": 1,
        "upstream": {
            "version": "1.1.334",
            "git_commit": "a" * 40,
            "integrity": "sha512-" + base64.b64encode(hashlib.sha512(archive).digest()).decode(),
            "license_sha256": hashlib.sha256(LICENSE).hexdigest(),
        },
        "glyphs": glyphs or ["add"],
        "fallbacks": {},
    }


def _save_catalog(root: Path, catalog: dict) -> None:
    path = root / "tools/icons.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog), encoding="utf-8")


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    directory = tmp_path / ASSETS / "icons"
    directory.mkdir(parents=True)
    (directory / "LICENSE.txt").write_bytes(LICENSE)
    (directory / "SOURCE.json").write_text('{"files":{}}', encoding="utf-8")
    for filename, begin, end in (
        ("icons.js", "// BEGIN GENERATED ICON REGISTRY", "// END GENERATED ICON REGISTRY"),
        ("components.css", "/* BEGIN GENERATED ICON MASKS */", "/* END GENERATED ICON MASKS */"),
    ):
        (tmp_path / ASSETS / filename).write_bytes(
            f"/* café 日本語 */\r\n{begin}\nold\n{end}\n/* untouched */\r\n".encode("utf-8")
        )
    archive = _archive(_members())
    (tmp_path / "upstream.tgz").write_bytes(archive)
    _save_catalog(tmp_path, _catalog(archive))
    return tmp_path


def _run(root: Path, command: str) -> int:
    return icons.main([command, "--root", str(root), "--archive", str(root / "upstream.tgz")])


def test_native_generation_preserves_bytes_and_has_independent_provenance(workspace: Path) -> None:
    archive = (workspace / "upstream.tgz").read_bytes()
    catalog = icons.load_catalog(workspace / "tools/icons.json")
    before = _snapshot(workspace)

    outputs = icons.plan_outputs(workspace, catalog, archive)

    assert _snapshot(workspace) == before
    assert outputs == icons.plan_outputs(workspace, catalog, archive)
    assert icons.icon_mapping(catalog) == {
        "add:sm": "add_16_regular.svg", "add:md": "add_20_regular.svg", "add:lg": "add_24_regular.svg",
    }
    receipt = json.loads(outputs[(ASSETS / "icons/SOURCE.json").as_posix()])
    assert set(receipt["files"]) == {f"add_{size}_regular.svg" for size in (16, 20, 24)}
    for size in (16, 20, 24):
        filename = f"add_{size}_regular.svg"
        payload = outputs[(ASSETS / "icons" / filename).as_posix()]
        assert payload == _svg(size) + b"\n"
        assert receipt["files"][filename] == {
            "source_url": f"https://unpkg.com/@fluentui/svg-icons@1.1.334/icons/{filename}",
            "upstream_sha256": hashlib.sha256(_svg(size)).hexdigest(),
            "packaged_sha256": hashlib.sha256(payload).hexdigest(),
        }
    for filename in ("icons.js", "components.css"):
        payload = outputs[(ASSETS / filename).as_posix()]
        assert payload.startswith("/* café 日本語 */\r\n".encode("utf-8"))
        assert payload.endswith(b"\n/* untouched */\r\n")
    assert b'"add": "nami-icon--add"' in outputs[(ASSETS / "icons.js").as_posix()]
    css = outputs[(ASSETS / "components.css").as_posix()]
    for name, size in (("sm", 16), ("md", 20), ("lg", 24)):
        assert f'--nami-icon-mask-{name}: url("./icons/add_{size}_regular.svg");'.encode() in css


def test_missing_native_requires_explicit_fallback_and_does_not_copy_invented_asset(workspace: Path) -> None:
    archive = _archive(_members()[1:])
    catalog = _catalog(archive)
    with pytest.raises(ValueError, match="fallback"):
        icons.plan_outputs(workspace, catalog, archive)

    catalog["fallbacks"] = {"add": {"sm": 20}}
    outputs = icons.plan_outputs(workspace, catalog, archive)
    assert (ASSETS / "icons/add_16_regular.svg").as_posix() not in outputs
    assert icons.icon_mapping(catalog)["add:sm"] == "add_20_regular.svg"

    native_archive = _archive(_members())
    catalog["upstream"] = _catalog(native_archive)["upstream"]
    with pytest.raises(ValueError, match="fallback"):
        icons.plan_outputs(workspace, catalog, native_archive)


@pytest.mark.parametrize("corruption", ["archive", "license", "markers", "duplicate", "symlink", "script", "external-fill"])
def test_invalid_inputs_are_rejected_before_any_write(workspace: Path, corruption: str) -> None:
    members = _members()
    if corruption == "archive":
        (workspace / "upstream.tgz").write_bytes(b"wrong archive")
    elif corruption == "license":
        (workspace / ASSETS / "icons/LICENSE.txt").write_bytes(b"modified license")
    elif corruption == "markers":
        (workspace / ASSETS / "components.css").write_bytes(b"no generated section")
    else:
        name, payload, kind = members[0]
        if corruption == "duplicate":
            members.append(members[0])
        elif corruption == "symlink":
            members[0] = (name, b"", tarfile.SYMTYPE)
        elif corruption == "script":
            members[0] = (name, payload.replace(b"</svg>", b"<script>alert(1)</script></svg>"), kind)
        else:
            members[0] = (name, payload.replace(b"#242424", b"url(https://example.test/a.svg)"), kind)
        archive = _archive(members)
        (workspace / "upstream.tgz").write_bytes(archive)
        _save_catalog(workspace, _catalog(archive))
    before = _snapshot(workspace)

    assert _run(workspace, "sync") == 1
    assert _snapshot(workspace) == before


def test_archive_traversal_entries_are_never_extracted(workspace: Path) -> None:
    archive = _archive(_members() + [("package/icons/../../../outside.svg", b"do not extract", tarfile.REGTYPE)])
    catalog = _catalog(archive)
    before = _snapshot(workspace)

    outputs = icons.plan_outputs(workspace, catalog, archive)

    assert _snapshot(workspace) == before
    assert all(Path(name).is_relative_to(ASSETS) and ".." not in Path(name).parts for name in outputs)
    assert not (workspace.parent / "outside.svg").exists()


def test_check_is_read_only_and_sync_restores_owned_drift(workspace: Path) -> None:
    assert _run(workspace, "sync") == 0
    pristine = _snapshot(workspace)
    assert _run(workspace, "check") == 0
    target = workspace / ASSETS / "icons/add_16_regular.svg"
    target.write_bytes(b"corrupted icon")
    corrupt = _snapshot(workspace)

    assert _run(workspace, "check") == 1
    assert _snapshot(workspace) == corrupt
    assert _run(workspace, "sync") == 0
    assert _snapshot(workspace) == pristine
    assert _run(workspace, "check") == 0


@pytest.mark.parametrize("modified", [False, True])
def test_removed_glyph_prunes_only_unchanged_previously_owned_files(workspace: Path, modified: bool) -> None:
    archive = _archive(_members() + _members("save"))
    (workspace / "upstream.tgz").write_bytes(archive)
    _save_catalog(workspace, _catalog(archive, ["add", "save"]))
    assert _run(workspace, "sync") == 0
    _save_catalog(workspace, _catalog(archive, ["add"]))
    if modified:
        (workspace / ASSETS / "icons/save_16_regular.svg").write_bytes(b"local work")
    before = _snapshot(workspace)

    assert _run(workspace, "check") == 1
    assert _snapshot(workspace) == before
    assert _run(workspace, "sync") == int(modified)
    if modified:
        assert _snapshot(workspace) == before
    else:
        assert not list((workspace / ASSETS / "icons").glob("save_*.svg"))
        assert (workspace / ASSETS / "icons/add_16_regular.svg").read_bytes() == _svg(16) + b"\n"


def test_unrelated_file_causes_refusal_without_mutation(workspace: Path) -> None:
    assert _run(workspace, "sync") == 0
    (workspace / ASSETS / "icons/designer-notes.txt").write_bytes(b"keep this")
    before = _snapshot(workspace)

    assert _run(workspace, "sync") == 1
    assert _snapshot(workspace) == before


def test_new_selection_does_not_claim_an_existing_unowned_svg(workspace: Path) -> None:
    (workspace / ASSETS / "icons/add_16_regular.svg").write_bytes(b"unregistered local artwork")
    before = _snapshot(workspace)

    assert _run(workspace, "sync") == 1
    assert _snapshot(workspace) == before


def test_previous_receipt_cannot_authorize_removal_outside_icons(workspace: Path) -> None:
    victim = workspace / ASSETS / "keep.svg"
    victim.write_bytes(b"keep this")
    receipt = {"files": {"../keep.svg": {"packaged_sha256": hashlib.sha256(victim.read_bytes()).hexdigest()}}}
    (workspace / ASSETS / "icons/SOURCE.json").write_text(json.dumps(receipt), encoding="utf-8")
    before = _snapshot(workspace)

    assert _run(workspace, "sync") == 1
    assert _snapshot(workspace) == before


@pytest.mark.parametrize("field,value", [("name", "@other/icons"), ("version", "2.0.0"), ("gitHead", "b" * 40)])
def test_archive_identity_must_match_the_reviewed_pin(workspace: Path, field: str, value: str) -> None:
    metadata = {"name": "@fluentui/svg-icons", "version": "1.1.334", "gitHead": "a" * 40}
    metadata[field] = value
    archive = _archive(_members(), metadata)
    (workspace / "upstream.tgz").write_bytes(archive)
    _save_catalog(workspace, _catalog(archive))
    before = _snapshot(workspace)

    assert _run(workspace, "sync") == 1
    assert _snapshot(workspace) == before


@pytest.mark.parametrize("glyph", ["../add", "Add", "add/foo", "add_16_regular", "add\"", "__proto__"])
def test_catalog_rejects_glyphs_that_cannot_be_fixed_identifiers(tmp_path: Path, glyph: str) -> None:
    _save_catalog(tmp_path, _catalog(_archive(_members()), [glyph]))

    with pytest.raises(ValueError):
        icons.load_catalog(tmp_path / "tools/icons.json")


def test_catalog_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "icons.json"
    path.write_text('{"schema_version":1,"schema_version":2}', encoding="utf-8")

    with pytest.raises(ValueError):
        icons.load_catalog(path)
