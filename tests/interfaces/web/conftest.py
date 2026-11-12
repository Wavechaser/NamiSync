"""Local fixtures for desktop web-interface evidence."""

from __future__ import annotations

from pathlib import Path

import pytest

from _tree_window_fixture import (
    TreeWindowFixture,
    write_tree_window_fixture,
)
from tests.conftest import BuiltWheel, HeadedInstalledWheel, InstalledWheel


__all__ = (
    "BuiltWheel",
    "HeadedInstalledWheel",
    "InstalledWheel",
    "tree_window_fixture",
)


@pytest.fixture
def tree_window_fixture(tmp_path: Path) -> TreeWindowFixture:
    """Return one function-local production-derived tree manifest."""

    return write_tree_window_fixture(tmp_path)
