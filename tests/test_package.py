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
