"""Package setup smoke tests."""

import namisync
import namisync.core
import namisync.db
import namisync.dispatcher
import namisync.interfaces
import namisync.modules
import namisync.workflows


def test_canonical_package_imports() -> None:
    assert namisync.__name__ == "namisync"
