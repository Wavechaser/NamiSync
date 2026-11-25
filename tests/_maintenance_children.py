"""Child-process scripts that hold a database pair the way maintenance's neighbours do.

Run with ``python -c`` through ``_child_process.Child``; each prints a line the
parent waits for, then blocks (a stopped restore on a sleep, the others on stdin).
"""

RESTORE = r"""
import os, sys, time
from datetime import datetime, timezone
import namisync.db.maintenance as maintenance
from namisync.workflows.database_maintenance import restore_database_from_backup

ledger, history, role, backup, stage, nth = sys.argv[1:7]


def hang():
    print("stopped", flush=True)
    time.sleep(120)


def stop(module, name, nth, *, after):
    original = getattr(module, name)
    calls = [0]

    def wrapped(*args, **kwargs):
        calls[0] += 1
        if not after and calls[0] == nth:
            hang()
        result = original(*args, **kwargs)
        if after and calls[0] == nth:
            hang()
        return result

    setattr(module, name, wrapped)


class Clock:
    def now(self):
        return datetime.now(timezone.utc)


if stage == "backed-up":
    stop(maintenance, "backup_database", 1, after=True)
elif stage == "image-written":
    stop(maintenance, "_prepare_image", 1, after=True)
elif stage == "mid-copy":
    # One page per step; stop between steps with the transaction open.
    maintenance._COPY_PAGES = 1
    checked = maintenance._copy_progress

    def progress(status, remaining, total):
        checked(status, remaining, total)
        if remaining > 0:
            hang()

    maintenance._copy_progress = progress
elif stage == "committed":
    stop(maintenance, "_copy_into_place", 1, after=True)
elif stage == "renamed":
    stop(os, "rename", int(nth), after=True)
print("ready", flush=True)
result = restore_database_from_backup(ledger, history, role, backup, clock=Clock())
print(f"finished {result.contract.state} {result.contract.reason}", flush=True)
"""
HOLD = r"""
import sys
from pathlib import Path
kind, ledger, history = sys.argv[1:4]
if kind == "recorder":
    from datetime import datetime, timezone
    from namisync.db.recorder import LedgerRecorder

    class Clock:
        def now(self):
            return datetime.now(timezone.utc)

    held = LedgerRecorder(ledger, clock=Clock())
elif kind == "observer":
    from datetime import datetime, timezone
    from namisync.core.session import SessionId, SessionRecord, SessionState
    from namisync.db.history import HistoryContext, HistoryStore

    class Clock:
        def now(self):
            return datetime.now(timezone.utc)

    store = HistoryStore(history, clock=Clock())
    record = SessionRecord(
        SessionId("7" * 32), "inventory", SessionState.PENDING, (), b"payload", False, 0,
        Clock().now(),
    )
    held = store.observer(record, HistoryContext("held-run", "host"))
elif kind == "pin":
    from namisync.interfaces.web.paths import WindowsPathLeaseNative
    held = WindowsPathLeaseNative().open(Path(ledger), directory=False)
print("held", flush=True)
sys.stdin.read()
"""
# A desktop beside maintenance: both mains pinned, an admitted owner and an
# idle repository on the ledger, as an open window holds them.
DESKTOP = r"""
import sys
from pathlib import Path
from namisync.db.contracts import DatabaseConnectionOwner
from namisync.db.repositories import LedgerRepository
from namisync.interfaces.web.paths import WindowsPathLeaseNative
ledger, history = sys.argv[1:3]
native = WindowsPathLeaseNative()
pins = [native.open(Path(path), directory=False) for path in (ledger, history)]
owner = DatabaseConnectionOwner(ledger, history=False)
repository = LedgerRepository(ledger, database=owner)
print("held " + repository.ledger_instance_id(), flush=True)
for line in sys.stdin:
    owner.validate()
    print("instance " + repository.ledger_instance_id(), flush=True)
"""
