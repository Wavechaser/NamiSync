"""Package setup smoke tests."""

import ast
import sys
import tomllib
from pathlib import Path

import namisync
import namisync.core
import namisync.db
import namisync.dispatcher
import namisync.interfaces
import namisync.modules
import namisync.workflows
import xxhash

from namisync.core.planning import OpId, plan_fingerprint, selection_digest
from namisync.core.session import ResourceId
from namisync.db.history import _hash as history_hash
from namisync.db.recorder import _payload_hash as recorder_hash
from namisync.dispatcher.custody import WindowsNamedMutexProvider

from _db_fixtures import plan


def test_canonical_package_imports() -> None:
    assert namisync.__name__ == "namisync"


def test_declared_xxhash_dependency_is_importable() -> None:
    project = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert "xxhash>=3.8.1,<4" in project["project"]["dependencies"]
    assert len(xxhash.xxh3_128().digest()) == 16


def test_core_has_no_third_party_imports() -> None:
    core_root = Path(namisync.core.__file__).parent
    allowed = set(sys.stdlib_module_names) | {"namisync"}
    imported_roots: set[str] = set()
    for path in core_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.partition(".")[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported_roots.add(node.module.partition(".")[0])
    assert imported_roots <= allowed


def test_only_runtime_composition_imports_the_concrete_xxh3_constructor() -> None:
    package_root = Path(namisync.__file__).parent
    importers: set[Path] = set()
    for path in package_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                alias.name.partition(".")[0] == "xxhash"
                for alias in node.names
            ):
                importers.add(path.relative_to(package_root))
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module is not None
                and node.module.partition(".")[0] == "xxhash"
            ):
                importers.add(path.relative_to(package_root))
    assert importers == {Path("workflows") / "runtime.py"}


def test_identity_hash_vectors_remain_sha256_and_ignore_content_factory() -> None:
    assert plan_fingerprint(plan(())) == (
        "b95a910f52dcbfcd2eb04bf7f7df373c51b351be9f324ee488cf53b5826fa758"
    )
    assert selection_digest(
        frozenset(
            {
                OpId("0" * 32),
                OpId("f" * 32),
            }
        )
    ).hex() == "d9342093bcb74d1506e36b230763b53c4a04cc6a374fa23bfaa0c7c1d78a8f38"
    assert WindowsNamedMutexProvider.mutex_name(
        ResourceId("volume", "serial:NTFS")
    ) == (
        "Global\\NamiSync.Resource."
        "cf9779f1bbc0c12deac62fffb7b87366a1a88a6e87dd4fe1e3ff6fcdc3bd351c"
    )
    assert history_hash({"kind": "history", "sequence": 1}).hex() == (
        "df3b27d2f25d4c3fd118edbc88de6b5ca90673645f98f3e283d9490823ea5fd8"
    )
    assert recorder_hash({"kind": "recorder", "item": 7}).hex() == (
        "ffc8da507eddc1f4894332afe720a982a7ca1f3aa727c106ee64a4c509be1164"
    )

    package_root = Path(namisync.__file__).parent
    for relative in (
        Path("core") / "planning.py",
        Path("dispatcher") / "custody.py",
        Path("db") / "history.py",
        Path("db") / "recorder.py",
    ):
        assert "hasher_factory" not in (
            package_root / relative
        ).read_text(encoding="utf-8")
