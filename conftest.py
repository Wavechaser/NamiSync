"""Repository-level pytest command-line options."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("namisync")
    group.addoption(
        "--dept",
        "--department",
        action="append",
        default=None,
        dest="departments",
        metavar="NAME",
        help="select tests owned by a department; repeat to select a union",
    )
